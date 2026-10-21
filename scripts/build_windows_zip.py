"""Build a Windows candidate ZIP from an explicit allowlist; no runtime/state/dump copy.

The thin JAR preserves every BOOT-INF/classes byte and Spring Boot launcher byte.
Vendor dependency JARs are obtained directly by the recipient using the reviewed lock.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(output,jar=None,application_source=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    package=output/'UrbanCommute-Demo';package.mkdir()
    def copy(source,target):
        dest=package/target;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,dest)
    for source,target in [('infra/windows/portable.py','launcher/portable.py'),
                          ('infra/windows/bootstrap.ps1','launcher/bootstrap.ps1'),
                          ('infra/windows/components.lock.json','config/components.lock.json'),
                          ('infra/windows/README-FIRST.txt','README-FIRST.txt'),
                          ('infra/windows/DEPENDENCIES.txt','licenses/DEPENDENCIES.txt'),
                          ('database/fixtures/t2-model-seed.json','database/model-seed.json'),
                          ('database/fixtures/t2-warehouse-seed.json','database/warehouse-seed.json'),
                          ('database/fixtures/t2-seed-provenance.json','database/seed-provenance.json')]:copy(source,target)
    for name,action,scenario in [('FIRST-SETUP','setup','model'),('START','start','model'),('STOP','stop','model'),
                                  ('CHECK-ENV','check','model'),('CREDENTIALS','credentials','model'),('START-WAREHOUSE','start','warehouse')]:
        content='@echo off\r\nsetlocal\r\n"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\\bootstrap.ps1" -Action '+action+' -Scenario '+scenario+' %*\r\nset "result=%ERRORLEVEL%"\r\nif not defined URBAN_COMMUTE_NO_PAUSE pause\r\nexit /b %result%\r\n'
        (package/(name+'.bat')).write_bytes(content.encode('ascii'))
    jar=Path(jar).resolve() if jar else ROOT/'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar'
    (package/'app/backend').mkdir(parents=True)
    classes={}
    with zipfile.ZipFile(jar) as source, zipfile.ZipFile(package/'app/backend/application.jar','w',zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            name=info.filename
            if name.startswith('BOOT-INF/lib/') or name in ('BOOT-INF/classpath.idx','BOOT-INF/layers.idx'):continue
            data=source.read(name);target.writestr(info,data)
            if name.startswith('BOOT-INF/classes/') and not name.endswith('/'):classes[name]=hashlib.sha256(data).hexdigest()
        loader=source.read('BOOT-INF/lib/spring-boot-3.5.16.jar')
        with zipfile.ZipFile(io.BytesIO(loader)) as nested:
            for name in nested.namelist():
                if re.search(r'(LICENSE|NOTICE)(\.txt)?$',name,re.I):
                    (package/'licenses'/('spring-boot-'+Path(name).name)).write_bytes(nested.read(name))
    shutil.copytree(ROOT/'frontend/dist',package/'app/frontend')
    notices=[]
    for name in ['vue','echarts','zrender','tslib','@vue/shared','@vue/reactivity','@vue/runtime-core','@vue/runtime-dom']:
        module=ROOT/'frontend/node_modules'/name
        if not module.exists():continue
        for file in module.iterdir():
            if file.is_file() and re.match(r'^(LICEN[CS]E|NOTICE|COPYING)',file.name,re.I):
                dest=package/'licenses'/(name.replace('/','-').replace('@','')+'-'+file.name)
                shutil.copyfile(file,dest);notices.append(dest.name)
    assert notices,'Frontend notices must not be omitted'
    python_files=['scripts/s8_adapter_bridge.py','ml/data_adapter.py','ml/domain_evaluation.py','ml/forecast.py',
                  'bigdata/warehouse.py','ml/requirements.lock.txt','ml/requirements.in','data-pipeline/requirements.lock.txt']
    python_files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'data-pipeline/commute_etl').glob('*.py')]
    for path in python_files:copy(path,'app/'+path)
    copy('infra/windows/bridge_entry.py','app/scripts/windows_bridge_entry.py')
    # Original research-only input for the administrator UI smoke, not preconfirmed.
    import sys
    sys.path.insert(0,str(ROOT/'ml'))
    from examples.fixtures import make_long
    generated=output/'research-fixture'
    raw,review=make_long(generated)
    shutil.copyfile(raw,package/'database/research-demo.csv')
    (package/'database/research-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    application_source=application_source or head
    changed=subprocess.check_output(['git','diff',application_source,'--','backend/src/main','database/migrations','frontend/src',
                                     'frontend/package-lock.json','frontend/vite.config.ts'],cwd=ROOT,text=True)
    if changed:raise RuntimeError('Application working tree differs from the declared frozen source')
    status=subprocess.check_output(['git','status','--porcelain=v1'],cwd=ROOT,text=True)
    owned_sources=['backend/src/main','database/migrations','frontend/src','frontend/package-lock.json','frontend/vite.config.ts']
    source_files=[]
    for path in owned_sources:
        p=ROOT/path
        source_files.extend(p.rglob('*') if p.is_dir() else [p])
    application_files={p.relative_to(ROOT).as_posix():digest(p) for p in source_files if p.is_file()}
    packaging_files={p.relative_to(ROOT).as_posix():digest(p) for p in (ROOT/'infra/windows').rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    build=dict(version='0.9.0-t2-candidate',platform='windows-x64',applicationSource=application_source,
        packagingGitHead=head,workingTreeDirty=bool(status),applicationFiles=application_files,packagingFiles=packaging_files,
        originalFatJarSha256=digest(jar),thinJarSha256=digest(package/'app/backend/application.jar'),
        thinJarClassHashes=classes,frontendFiles={p.relative_to(ROOT/'frontend/dist').as_posix():digest(p) for p in (ROOT/'frontend/dist').rglob('*') if p.is_file()},
        vendorRuntimeBundled=False,firstSetup='verified direct official downloads; no global Java/Node/Python/MySQL install',
        data='synthetic_test; prepublished isolated snapshots',review='SOLO_OWNER_REVIEW; not ACCEPTED; not a formal Release')
    (package/'BUILD.json').write_text(json.dumps(build,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=sorted(p for p in package.rglob('*') if p.is_file())
    manifest=''.join(digest(p)+'  '+p.relative_to(package).as_posix()+'\n' for p in files)
    (package/'MANIFEST.sha256').write_text(manifest,encoding='utf-8')
    archive=output/'UrbanCommute-Demo-0.9.0-t2-candidate-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(package.rglob('*')):
            if p.is_file():z.write(p,package.name+'/'+p.relative_to(package).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        forbidden=[n for n in z.namelist() if any(x in n for x in ('/state/','/data/private/','/data/raw/','/.env','/node_modules/'))]
        assert not forbidden
    receipt=dict(zip=str(archive),bytes=archive.stat().st_size,sha256=digest(archive),files=len(files)+1,build=build)
    (output/'build-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='build'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--jar',type=Path)
    parser.add_argument('--application-source')
    args=parser.parse_args()
    build(args.output,args.jar,args.application_source)
