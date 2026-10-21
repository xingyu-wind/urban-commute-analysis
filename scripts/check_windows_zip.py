"""Inspect an actual candidate ZIP, including nested JAR and private-value exclusions.

Optional --private-values-file is an owner-only JSON credential map. Its values are
compared in memory and NEVER included in evidence or diagnostics.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',type=Path,required=True)
    parser.add_argument('--private-values-file',type=Path,action='append',default=[])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    private=[]
    def collect(value):
        if isinstance(value,str) and len(value)>=16:private.append(value.encode())
        elif isinstance(value,dict):
            for x in value.values():collect(x)
        elif isinstance(value,list):
            for x in value:collect(x)
    for path in args.private_values_file:collect(json.loads(path.read_text(encoding='utf-8')))
    with zipfile.ZipFile(args.zip) as archive:
        assert archive.testzip() is None
        prefix='UrbanCommute-Demo/'
        names=archive.namelist()
        build=json.loads(archive.read(prefix+'BUILD.json'))
        for name in names:
            assert name.startswith(prefix) and '..' not in Path(name).parts
            assert not any(x in name for x in ('/state/','/runtime/','/node_modules/','/data/raw/','/data/private/','/.env','synthetic.sql'))
            assert not name.endswith(('.exe','.dll','.pyd','.joblib','.pkl','.pem','.key','.log'))
            raw=archive.read(name)
            assert not any(value in raw for value in private),'Private value detected; withheld'
        for line in archive.read(prefix+'MANIFEST.sha256').decode().splitlines():
            expected,name=line.split('  ',1)
            assert hashlib.sha256(archive.read(prefix+name)).hexdigest()==expected
        with zipfile.ZipFile(io.BytesIO(archive.read(prefix+'app/backend/application.jar'))) as jar:
            assert not any(n.startswith('BOOT-INF/lib/') and n.endswith('.jar') for n in jar.namelist())
            for name,expected in build['thinJarClassHashes'].items():
                raw=jar.read(name)
                assert hashlib.sha256(raw).hexdigest()==expected
                assert not any(value in raw for value in private),'Private value in JAR; withheld'
        seeds={}
        provenance=json.loads(archive.read(prefix+'database/seed-provenance.json'))
        for scenario in ('model','warehouse'):
            raw=archive.read(prefix+'database/'+scenario+'-seed.json')
            assert hashlib.sha256(raw).hexdigest()==provenance[scenario]['sha256']
            seed=json.loads(raw)
            assert seed['sourceType']=='synthetic_test' and len(seed['tables'])==17
            assert not set(seed['tables']) & {'app_user','managed_job','managed_import','security_audit','flyway_schema_history'}
            assert not re.search(r'password_hash|[A-Za-z]:[\\/]',json.dumps(seed))
            seeds[scenario]={t:len(d['rows']) for t,d in seed['tables'].items()}
        result=dict(passed=True,zip=str(args.zip.resolve()),bytes=args.zip.stat().st_size,
            sha256=hashlib.sha256(args.zip.read_bytes()).hexdigest(),fileCount=len(names),files=names,
            manifestVerified=True,applicationClassesVerified=True,vendorBinaryArchivesBundled=False,
            privateCredentialValuesChecked=len(private),privateValueMatches=0,privateDataPaths=0,
            thinJarContainsVendorDependencies=False,seedTables=seeds,applicationSource=build['applicationSource'],
            packagingGitHead=build['packagingGitHead'],workingTreeDirty=build['workingTreeDirty'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('T2_ZIP_CONTENTS=PASS; SHA256='+result['sha256'])


if __name__=='__main__':main()
