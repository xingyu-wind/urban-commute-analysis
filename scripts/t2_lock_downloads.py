"""Maintainer-only lock generator: official HTTPS archives and PyPI Windows wheels.

Does not install anything. Reviewed/pinned output is consumed by the portable setup.
"""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile
import time

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'dist/component-cache'


def fetch(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 2: raise
            time.sleep(1)


def download(item):
    path = CACHE / item['filename']
    if not path.exists():
        data = fetch(item['url'])
        path.write_bytes(data)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if item.get('sha256') and item['sha256'] != digest:
        raise ValueError('Official digest mismatch: ' + item['filename'])
    if item.get('md5') and hashlib.md5(data).hexdigest() != item['md5']:
        raise ValueError('Official MD5 mismatch: ' + item['filename'])
    item.update(sha256=digest, bytes=len(data))
    if item['filename'].endswith(('.zip', '.whl')):
        with zipfile.ZipFile(path) as archive:
            if archive.testzip():
                raise ValueError('Damaged archive')
    print('VERIFIED ' + item['filename'], flush=True)
    return item


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    java_url = 'https://api.azul.com/metadata/v1/zulu/packages/a51c4f91-61c6-4b26-9060-a2b12745e236'
    java = json.loads(fetch(java_url))
    items = [
        dict(kind='python', filename='python-3.11.9-embed-amd64.zip',
             url='https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip',
             provenance='Official python.org HTTPS release; SHA256 pinned on maintainer acquisition',
             license='PSF-2.0 and included third-party notices'),
        dict(kind='java', filename=java['name'], url=java['download_url'], sha256=java['sha256_hash'],
             provenance=java_url, license='GPL-2.0 with Classpath Exception; vendor notices retained'),
        dict(kind='mysql', filename='mysql-8.4.11-winx64.zip',
             url='https://cdn.mysql.com/archives/mysql-8.4/mysql-8.4.11-winx64.zip',
             md5='2e833921898a9a030ea6bfe81bd811bc',
             provenance='Official MySQL CDN archive; MD5 matches CDN ETag, SHA256 pinned on acquisition',
             license='GPL-2.0 and included MySQL third-party notices'),
    ]
    versions = dict(numpy='2.2.6', scipy='1.15.3', **{'scikit-learn':'1.7.2'}, xgboost='3.0.5',
                    joblib='1.5.2', threadpoolctl='3.6.0', tzdata='2025.2', packaging='26.3',
                    PyMySQL='1.1.2', cryptography='50.0.2', cffi='2.1.1', pycparser='3.11')
    for name, version in versions.items():
        url = f'https://pypi.org/pypi/{name}/{version}/json'
        meta = json.loads(fetch(url))
        wheels = [x for x in meta['urls'] if x['filename'].endswith('.whl') and
                  ('win_amd64' in x['filename'] and ('cp311-' in x['filename'] or 'py3-none-' in x['filename'] or
                   ('abi3' in x['filename'] and any('cp'+str(v)+'-' in x['filename'] for v in (37,38,39,310))))
                   or x['filename'].endswith(('py3-none-any.whl', 'py2.py3-none-any.whl')))]
        exact = [x for x in wheels if 'cp311-' in x['filename']]
        if exact: wheels = exact
        if len(wheels) != 1:
            raise ValueError(f'Explicit Windows wheel selection required: {name}: {[x["filename"] for x in wheels]}')
        wheel = wheels[0]
        items.append(dict(kind='wheel', filename=wheel['filename'], url=wheel['url'],
                          sha256=wheel['digests']['sha256'], provenance=url,
                          license=meta['info'].get('license_expression') or meta['info'].get('license') or 'See wheel licenses'))
    # Dependencies are fetched by the recipient, not redistributed in our candidate ZIP.
    jar = ROOT / 'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar'
    maven = Path.home() / '.m2/repository'
    index = {p.name:p for p in maven.rglob('*.jar')}
    with zipfile.ZipFile(jar) as archive:
        for name in archive.namelist():
            if not name.startswith('BOOT-INF/lib/') or not name.endswith('.jar'):
                continue
            filename = Path(name).name
            if filename.startswith('spring-boot-jarmode-tools-'):
                continue  # Build-time layertools, not a business runtime dependency.
            path = index[filename]
            relative = path.relative_to(maven).as_posix()
            data = archive.read(name)
            assert data == path.read_bytes()
            items.append(dict(kind='jar', filename=filename,
                              url='https://repo.maven.apache.org/maven2/'+relative,
                              sha256=hashlib.sha256(data).hexdigest(), provenance=relative,
                              license='See vendor JAR LICENSE/NOTICE and Maven POM; direct recipient download'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        locked = list(pool.map(download, items))
    target = ROOT / 'infra/windows/components.lock.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(platform='windows-x64', components=locked), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
