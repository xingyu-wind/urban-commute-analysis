"""Wrap the verified Workbench offline payload, preserving its provenance and notices."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'dist/ui-workbench-candidate-03/UrbanCommute-Demo'

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def build(output,tools,base=BASE):
    output=output.resolve();tools=tools.resolve();base=base.resolve()
    if output.exists():raise RuntimeError('Use a new build output directory; existing candidates are preserved.')
    lock=json.loads((ROOT/'infra/desktop/tools.lock.json').read_text())
    for item in lock.values():
        if digest(tools/item['filename'])!=item['sha256']:raise RuntimeError('Build tool hash mismatch: '+item['filename'])
    for line in (base/'MANIFEST.sha256').read_text().splitlines():
        expected,name=line.split('  ',1)
        if digest(base/name)!=expected:raise RuntimeError('Baseline integrity failed: '+name)
    previous=json.loads((base/'BUILD.json').read_text(encoding='utf-8'))
    diff=subprocess.check_output(['git','diff',previous['applicationSource'],'--','backend/src/main','frontend/src','frontend/package-lock.json','database/migrations'],cwd=ROOT)
    if diff:raise RuntimeError('Application changed; rebuild the offline payload before wrapping it.')
    dirty=subprocess.check_output(['git','status','--porcelain=v1'],cwd=ROOT,text=True)
    if dirty:raise RuntimeError('Commit reviewed source before building; dirty source is not a release identity.')
    output.mkdir(parents=True)
    stage=output/'application';stage.mkdir()
    with zipfile.ZipFile(tools/lock['electron']['filename']) as archive:archive.extractall(stage)
    (stage/'electron.exe').rename(stage/'UrbanCommute.exe')
    shutil.copytree(ROOT/'infra/desktop',stage/'resources/app',ignore=shutil.ignore_patterns('installer.iss','tools.lock.json','TERMS.txt','INSTALL-NOTES.txt'))
    payload=stage/'resources/payload'
    # Keep original archives intact, but flatten the duplicate human-readable
    # notices so normal Windows install paths do not exceed MAX_PATH.
    shutil.copytree(base,payload,ignore=lambda folder,names: ['vendor'] if Path(folder)==base/'licenses' else [])
    notice_map=[]
    for index,source in enumerate(sorted((base/'licenses/vendor').rglob('*'))):
        if not source.is_file():continue
        relative=Path('licenses/vendor')/(str(index)+'-'+source.name[:60])
        destination=payload/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)
        notice_map.append(dict(original=source.relative_to(base).as_posix(),file=relative.as_posix(),sha256=digest(source)))
    write(payload/'licenses/NOTICE-INDEX.json',dict(files=[n['file'] for n in notice_map],originalPaths=notice_map))
    for name in ('portable.py','bootstrap.ps1'):shutil.copyfile(ROOT/'infra/windows'/name,payload/'launcher'/name)
    write(payload/'config/desktop.json',dict(version=1,dataLayout=1,offline=True))
    write(payload/'BASELINE-BUILD.json',previous)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    version=json.loads((ROOT/'infra/desktop/package.json').read_text(encoding='utf-8'))['version']
    previous.update(version=version,desktopGitHead=head,packagingGitHead=head,workingTreeDirty=False,
                    desktopRuntime=lock['electron'],dataLayout=1,review='WINDOWS_DESKTOP_CANDIDATE; pending independent acceptance')
    write(payload/'BUILD.json',previous)
    manifest=''.join(digest(p)+'  '+p.relative_to(payload).as_posix()+'\n' for p in sorted(payload.rglob('*')) if p.is_file() and p.name!='MANIFEST.sha256')
    (payload/'MANIFEST.sha256').write_text(manifest,encoding='utf-8')
    prerequisites=stage/'prerequisites';prerequisites.mkdir()
    vc=ROOT/'dist/t3-usb-prerequisites/VC_redist.x64.exe'
    if digest(vc)!='843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c':raise RuntimeError('VC++ original hash mismatch')
    shutil.copyfile(vc,prerequisites/vc.name)
    for name in ('TERMS.txt','INSTALL-NOTES.txt'):shutil.copyfile(ROOT/'infra/desktop'/name,stage/name)
    subprocess.run([str(tools/'inno/ISCC.exe'),'/Qp','/DStageDir='+str(stage),'/DOutputDir='+str(output),
                    '/DAppVersion='+version,str(ROOT/'infra/desktop/installer.iss')],check=True,cwd=ROOT)
    exe=output/('UrbanCommute-Setup-'+version+'.exe')
    write(output/'build-receipt.json',dict(exe=str(exe),bytes=exe.stat().st_size,sha256=digest(exe),
        source=head,applicationSource=previous['applicationSource'],baselineManifestSha256=digest(base/'MANIFEST.sha256'),
        payloadManifestSha256=digest(payload/'MANIFEST.sha256'),tools=lock,syntheticData=True,
        sourceFiles={p.relative_to(ROOT).as_posix():digest(p) for folder in ('infra/desktop','infra/windows') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p)}))
    print(json.dumps(dict(exe=str(exe),bytes=exe.stat().st_size,sha256=digest(exe)),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--tools',default=ROOT/'dist/desktop-tools',type=Path)
    parser.add_argument('--base',default=BASE,type=Path)
    args=parser.parse_args();build(args.output,args.tools,args.base)
