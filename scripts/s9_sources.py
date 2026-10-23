"""Public source recheck. No credentials, training, data download or rights inference."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for url in ('https://zenodo.org/api/records/5724362',
                'https://raw.githubusercontent.com/liyaguang/DCRNN/master/README.md',
                'https://raw.githubusercontent.com/liyaguang/DCRNN/master/LICENSE',
                'https://opendata.sz.gov.cn/data/api/toApiDetails/29200_00403590',
                'https://opendata.sz.gov.cn/maintenance/forward/toTermOfService',
                'https://dot.ca.gov/programs/traffic-operations/mpr/pems-source',
                'https://pems.dot.ca.gov/'):
        row = dict(url=url, checkedAt=datetime.now(timezone.utc).isoformat())
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'UrbanCommute-S9-source-audit/1.0'}), timeout=20) as response:
                raw = response.read(2_000_001)
                row.update(httpStatus=response.status, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                if url.endswith('/5724362'):
                    metadata=json.loads(raw)
                    row.update(version=metadata['metadata'].get('version'), recordId=metadata['id'],
                        licenseDeclaration=metadata['metadata'].get('license'),
                        files=[{k:f.get(k) for k in ('key','size','checksum')} for f in metadata['files']])
        except Exception as error:
            row.update(errorType=type(error).__name__,httpStatus=getattr(error,'code',None))
        records.append(row)
    local=[]
    expected={'METR-LA.csv':(72467662,'7c463fcbd28ecc6c9cd93e1ca120aaaa'),
              'PEMS-BAY.csv':(85718439,'c8dea58987a5882e946217c22fdb8256')}
    for name,(size,md5) in expected.items():
        file=ROOT/'data/raw/s7-v32-research'/name
        if not file.exists():
            local.append(dict(file=name,status='NOT_PRESENT')); continue
        raw=file.read_bytes()
        local.append(dict(file=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            md5=hashlib.md5(raw).hexdigest(),expectedBytes=size,expectedMd5=md5,
            complete=len(raw)==size and hashlib.md5(raw).hexdigest()==md5,status='NOT_EVALUABLE'))
    result=dict(checkedAt=datetime.now(timezone.utc).isoformat(),requests=records,localFiles=local,
        trainingExecuted=False,realMappingConfirmed=False,rawDataExported=False,
        decision='BLOCKED / NOT_EVALUABLE',
        releaseConditions=['complete distribution checksum','version-specific unit/timezone/zero semantics',
                           'upstream data rights and permitted use','explicit human mapping confirmation','task suitability'])
    (args.output/'sources.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('S9_SOURCE_AUDIT_RECORDED (not training authorization)')

if __name__=='__main__': main()
