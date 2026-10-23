"""Read-only, allowlisted export of already verified OWNED synthetic fixtures.

No auth, audit, uploads, passwords, Flyway history, dump or model weights are exported.
This restores published demo snapshots; it does not bypass publication or train a model.
"""
import argparse
from datetime import datetime,date
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import zipfile

import pymysql

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from s7_fixture import generate

TABLES=('dataset_registry','city','region','road_segment','traffic_observation','etl_source',
        'etl_batch','etl_rejection','etl_batch_observation','warehouse_release','warehouse_metric',
        'warehouse_current','prediction_model','prediction_job','prediction_evaluation','prediction_result','prediction_current')


def serial(value):
    if isinstance(value,datetime):return value.isoformat(sep=' ',timespec='milliseconds')
    if isinstance(value,date):return value.isoformat()
    if isinstance(value,Decimal):return str(value)
    raise TypeError(type(value).__name__)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials',type=Path,required=True)
    parser.add_argument('--model-schema',required=True)
    parser.add_argument('--warehouse-schema',required=True)
    parser.add_argument('--warehouse-artifact',type=Path,help='Optional independently verified final CI ZIP for exact metric comparison')
    args=parser.parse_args()
    password=json.loads(args.credentials.read_text())['admin']
    result={}
    for scenario,schema in [('model',args.model_schema),('warehouse',args.warehouse_schema)]:
        assert re.fullmatch('s3test_[a-f0-9]{32}',schema)
        connection=pymysql.connect(host='127.0.0.1',port=33067,user='root',password=password,database=schema)
        tables={}
        with connection:
            with connection.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY');cur.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT')
                cur.execute('SELECT dataset_id,source_type FROM dataset_registry')
                assert all(row[1]=='synthetic_test' for row in cur.fetchall())
                cur.execute('SHOW TABLES');available={row[0] for row in cur.fetchall()}
                for table in TABLES:
                    if table not in available:
                        tables[table]=dict(columns=[],rows=[]);continue
                    cur.execute('SELECT * FROM `'+table+'`')
                    columns=[c[0] for c in cur.description];rows=list(cur.fetchall())
                    tables[table]=dict(columns=columns,rows=rows)
                if scenario=='model':
                    with tempfile.TemporaryDirectory(prefix='t2-fixture-') as temp:
                        fixture=generate(Path(temp)/'fixture')
                        expected=json.loads((fixture/'traffic.json').read_text())
                    data=tables['traffic_observation'];columns=data['columns']
                    observed=[dict(zip(columns,row)) for row in data['rows'] if row[columns.index('dataset_id')]=='s7-synthetic-v1']
                    assert len(observed)==len(expected)==4368
                    actual={r['observed_at'].isoformat(timespec='milliseconds')+'Z':(r['avg_speed_kmh'],r['congestion_index']) for r in observed}
                    for row in expected:
                        stamp=datetime.fromisoformat(row['observed_at'].replace('Z','+00:00')).replace(tzinfo=None).isoformat(timespec='milliseconds')+'Z'
                        assert actual[stamp]==(Decimal(str(row['velocity'])),Decimal(str(row['index'])))
                    pointer=tables['prediction_current'];assert len(pointer['rows'])==1
                    job=pointer['rows'][0][pointer['columns'].index('job_id')]
                    jobs=tables['prediction_job'];jobs['rows']=[r for r in jobs['rows'] if r[jobs['columns'].index('job_id')]==job]
                    assert len(jobs['rows'])==1 and jobs['rows'][0][jobs['columns'].index('status')]=='PUBLISHED'
                    model=jobs['rows'][0][jobs['columns'].index('model_version')]
                    models=tables['prediction_model'];models['rows']=[r for r in models['rows'] if r[models['columns'].index('model_version')]==model]
                    for table in ('prediction_evaluation','prediction_result'):
                        d=tables[table];d['rows']=[r for r in d['rows'] if r[d['columns'].index('job_id')]==job]
                    assert len(tables['prediction_result']['rows'])==7
                else:
                    pointer=tables['warehouse_current'];assert len(pointer['rows'])==1
                    release=pointer['rows'][0][pointer['columns'].index('release_id')]
                    for table in ('warehouse_release','warehouse_metric'):
                        d=tables[table];d['rows']=[r for r in d['rows'] if r[d['columns'].index('release_id')]==release]
                    assert len(tables['warehouse_metric']['rows'])==40
                    assert tables['warehouse_release']['rows'][0][tables['warehouse_release']['columns'].index('status')]=='PUBLISHED'
                    # Compare the selected published metrics to the original independent oracle.
                    oracle=json.loads((ROOT/'backend/target/s6-local-chain/hive-reconciliation.json').read_text())['rows']
                    metric=tables['warehouse_metric'];actual=[]
                    for values in metric['rows']:
                        row=dict(zip(metric['columns'],values));item={}
                        for key in oracle[0]:
                            value=row[key]
                            item[key]=value.isoformat(timespec='milliseconds')+'Z' if isinstance(value,datetime) else (str(value) if value is not None else None)
                        actual.append(item)
                    assert sorted(actual,key=lambda x:json.dumps(x,sort_keys=True))==sorted(oracle,key=lambda x:json.dumps(x,sort_keys=True))
                    if args.warehouse_artifact:
                        with zipfile.ZipFile(args.warehouse_artifact) as archive:
                            final=json.loads(archive.read('s6-ci/hive-reconciliation.json'))
                        assert final['passed'] and final['ods']==39 and final['dwd']==21 and final['ads']==40
                        assert sorted(actual,key=lambda x:json.dumps(x,sort_keys=True))==sorted(final['rows'],key=lambda x:json.dumps(x,sort_keys=True))
                connection.rollback()
        target=ROOT/f'database/fixtures/t2-{scenario}-seed.json'
        content=json.dumps(dict(sourceType='synthetic_test',snapshot='prepublished; not a new training/Hive execution',tables=tables),
                           default=serial,ensure_ascii=False,separators=(',',':'))+'\n'
        assert not re.search(r'[A-Za-z]:[\\/]|password_hash|DB_PASSWORD|s3test_[a-f0-9]{32}',content)
        target.write_text(content,encoding='utf-8',newline='\n')
        result[scenario]=dict(sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            rows={t:len(d['rows']) for t,d in tables.items()},excluded=['app_user','security_audit','managed_job','managed_import','flyway_schema_history'],
            modelFixture4368PointComparison=scenario=='model',warehouseAll40MetricsCompared=scenario=='warehouse',
            finalWarehouseArtifactSha256=hashlib.sha256(args.warehouse_artifact.read_bytes()).hexdigest() if scenario=='warehouse' and args.warehouse_artifact else None,
            originalPublisher='S7 trusted replay / S6 independently reconciled real Hive',
            sourceEvidence='docs/stage-reports/evidence/S9/release' if scenario=='model' else 'backend/target/s6-local-chain')
    (ROOT/'database/fixtures/t2-seed-provenance.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
