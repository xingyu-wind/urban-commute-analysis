"""Collect public package identities and verified download receipts; never copy secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--zip',required=True,type=Path)
    parser.add_argument('--previous-zip',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=args.root
    lock=json.loads((root/'config/components.lock.json').read_text(encoding='utf-8'))
    downloads=[]
    for item in lock['components']:
        path=root/'runtime/downloads'/item['filename']
        entry={k:item[k] for k in ('kind','filename','url','sha256','bytes')}
        entry.update(actualBytes=path.stat().st_size,actualSha256=sha(path))
        assert entry['bytes']==entry['actualBytes'] and entry['sha256']==entry['actualSha256']
        downloads.append(entry)
    with zipfile.ZipFile(args.zip) as current,zipfile.ZipFile(args.previous_zip) as previous:
        prefix='UrbanCommute-Demo/'
        current_build=json.loads(current.read(prefix+'BUILD.json'))
        previous_build=json.loads(previous.read(prefix+'BUILD.json'))
        for key in ('applicationSource','originalFatJarSha256','thinJarSha256','thinJarClassHashes','frontendFiles','applicationFiles'):
            assert current_build[key]==previous_build[key],key
        changed=[n for n in current.namelist() if n not in previous.namelist() or current.read(n)!=previous.read(n)]
    frozen=subprocess.check_output(['git','diff','97f30db15a5292c0be9a0103359ccc7e97f5ddfa','--',
        'backend/src/main','frontend/src','ml','data-pipeline','bigdata','database/migrations','scripts/s8_adapter_bridge.py'],text=True)
    assert not frozen,'Business source changed'
    result=dict(passed=True,zip=str(args.zip.resolve()),sha256=sha(args.zip),bytes=args.zip.stat().st_size,
        applicationSource=current_build['applicationSource'],packagingGitHead=current_build['packagingGitHead'],
        originalFatJarSha256=current_build['originalFatJarSha256'],thinJarSha256=current_build['thinJarSha256'],
        frontendFiles=current_build['frontendFiles'],lockSha256=sha(root/'config/components.lock.json'),
        businessSourceUnchanged=True,applicationArtifactsIdenticalToT2=True,changedPackageFiles=changed,
        initialCacheEvidence='final-empty-cache.json; no files copied from T2 or other caches',
        acquiredFiles=len(downloads),acquiredArchiveBytes=sum(d['actualBytes'] for d in downloads),downloads=downloads,
        setup=json.loads((root/'state/setup-result.json').read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
