"""Maintainer-only official source acquisition. Never executed by the USB launcher."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import time
import tarfile
import urllib.request
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    lock=json.loads(Path('infra/windows/components.lock.json').read_text(encoding='utf-8'))
    tasks=[dict(filename='mysql-8.4.11.tar.gz',url='https://cdn.mysql.com/archives/mysql-8.4/mysql-8.4.11.tar.gz',kind='source',license='GPL-2.0; matching MySQL 8.4.11 source'),
           dict(filename='Python-3.11.9.tar.xz',url='https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tar.xz',kind='source',license='PSF-2.0')]
    for item in lock['components']:
        if item['kind']=='jar':
            tasks.append(dict(filename=item['filename'][:-4]+'-sources.jar',url=item['url'][:-4]+'-sources.jar',kind='source',license='Upstream source license; see accompanying binary notices'))
            tasks.append(dict(filename=item['filename'][:-4]+'.pom',url=item['url'][:-4]+'.pom',kind='metadata',license='Upstream Maven publication metadata'))
    def acquire(item):
        file=args.output/item['filename'];partial=file.with_suffix(file.suffix+'.partial')
        def validate(path):
            if item['filename'].endswith('.jar'):
                with zipfile.ZipFile(path) as archive:assert archive.testzip() is None
            elif item['filename'].endswith(('.tar.gz','.tar.xz')):
                with tarfile.open(path) as archive:
                    assert archive.getmembers(),'Empty source archive'
            elif item['filename'].endswith('.pom'):
                import xml.etree.ElementTree as ET
                ET.parse(path)
        if file.exists():
            try:validate(file)
            except Exception:
                file.rename(file.with_name(file.name+'.failed-'+str(time.time_ns())))
        if not file.exists():
            for attempt in range(3):
                try:
                    print('ACQUIRE '+item['filename'],flush=True)
                    if item['filename']=='mysql-8.4.11.tar.gz':
                        with urllib.request.urlopen(urllib.request.Request(item['url'],method='HEAD'),timeout=30) as head:
                            expected=int(head.headers['Content-Length'])
                        parts=args.output/'mysql-source-parts';parts.mkdir(exist_ok=True)
                        def part(start):
                            end=min(start+8*1024**2,expected)-1
                            path=parts/(str(start)+'.part')
                            if path.exists() and path.stat().st_size==end-start+1:return path
                            request=urllib.request.Request(item['url'],headers={'Range':f'bytes={start}-{end}'})
                            for trial in range(3):
                                try:
                                    with urllib.request.urlopen(request,timeout=60) as source,path.open('wb') as target:
                                        assert source.status==206 and source.headers['Content-Range']==f'bytes {start}-{end}/{expected}'
                                        shutil.copyfileobj(source,target)
                                    assert path.stat().st_size==end-start+1
                                    return path
                                except Exception:
                                    if trial==2:raise
                        with ThreadPoolExecutor(max_workers=12) as pieces:
                            ordered=list(pieces.map(part,range(0,expected,8*1024**2)))
                        with partial.open('wb') as target:
                            for path in ordered:
                                with path.open('rb') as source:shutil.copyfileobj(source,target)
                        print('Validated official byte ranges: '+str(expected),flush=True)
                    else:
                        with urllib.request.urlopen(item['url'],timeout=120) as source,partial.open('wb') as target:
                            expected=int(source.headers.get('Content-Length',0))
                            shutil.copyfileobj(source,target)
                    if partial.stat().st_size<100:raise RuntimeError('Unexpected short response')
                    if expected and partial.stat().st_size!=expected:raise RuntimeError('HTTP response truncated')
                    validate(partial)
                    partial.replace(file);break
                except Exception:
                    if partial.exists():partial.rename(partial.with_name(partial.name+'.failed-'+str(time.time_ns())))
                    if attempt==2:raise
                    time.sleep(attempt+1)
        return dict(**item,bytes=file.stat().st_size,sha256=hashlib.file_digest(file.open('rb'),'sha256').hexdigest(),provenance='Direct official HTTPS; SHA256 pinned on acquisition; not an independent signature assertion')
    with ThreadPoolExecutor(max_workers=5) as pool:result=list(pool.map(acquire,tasks))
    Path('infra/windows/usb-sources.lock.json').write_text(json.dumps(dict(files=result),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('USB_SOURCES_LOCKED='+str(len(result)),flush=True)


if __name__=='__main__':main()
