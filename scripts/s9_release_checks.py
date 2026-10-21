"""Actual candidate deployment, modest HTTP load and isolated logical backup/restore.

Invoke after S7 or S6 in the SAME s3_database.py --with-restore-target child.
Only synthetic_test inputs are allowed. Dumps stay under ignored data/private.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import subprocess
import time
import urllib.request
import pymysql
from s9_runtime import services, ROOT, preflight

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(); output=args.output.resolve(); output.mkdir(parents=True,exist_ok=False)
    match=re.fullmatch(r'jdbc:mysql://127\.0\.0\.1:(\d+)/(s3test_[0-9a-f]{32})\?connectionTimeZone=UTC',os.environ['DB_URL'])
    if not match: raise RuntimeError('isolated source required')
    target=os.environ['S9_RESTORE_SCHEMA']
    if not re.fullmatch(r's3test_[0-9a-f]{32}',target) or target==match[2]: raise RuntimeError('distinct isolated target required')
    def connect(restore=False):
        return pymysql.connect(host='127.0.0.1',port=int(match[1]),
            database=target if restore else match[2],user=os.environ['S9_RESTORE_USER'] if restore else os.environ['DB_USER'],
            password=os.environ['S9_RESTORE_PASSWORD'] if restore else os.environ['DB_PASSWORD'])
    def query(sql,restore=False):
        with connect(restore) as connection:
            with connection.cursor() as cursor: cursor.execute(sql); return cursor.fetchall()
    def snapshot(restore=False):
        tables=[row[0] for row in query('SHOW TABLES',restore)]
        result={}
        for table in tables:
            if not re.fullmatch(r'[a-z_]+',table): raise RuntimeError('unexpected table name')
            rows=sorted(json.dumps(row,default=str,ensure_ascii=False,separators=(',',':')) for row in query('SELECT * FROM `'+table+'`',restore))
            result[table]=dict(rows=len(rows),sha256=hashlib.sha256(('\n'.join(rows)).encode()).hexdigest())
        return result
    assert query('SELECT DATABASE(),CURRENT_USER(),@@server_uuid')[0]==(match[2],os.environ['TEST_DB_USER']+'@%',os.environ['TEST_DB_SERVER_UUID'])
    assert query('SELECT DATABASE(),CURRENT_USER(),@@server_uuid',True)[0]==(target,os.environ['S9_RESTORE_USER']+'@%',os.environ['TEST_DB_SERVER_UUID'])
    assert query('SHOW TABLES',True)==(), 'never restore over existing objects'
    assert all(row[0] in ('synthetic_test','dev_seed') for row in query('SELECT DISTINCT source_type FROM dataset_registry'))
    assert query('SELECT COUNT(*) FROM traffic_observation')[0][0]>0
    prediction=query('SELECT job_id FROM prediction_current')
    warehouse=query('SELECT release_id FROM warehouse_current')
    assert prediction or warehouse, 'drill requires an actual published pointer'
    kind='prediction' if prediction else 'warehouse'
    published_id=(prediction or warehouse)[0][0]
    city,dataset=query('SELECT city_id,dataset_id FROM traffic_observation ORDER BY city_id LIMIT 1')[0]
    paths=['/api/v1/cities','/api/v1/predictions?cityId='+city+'&datasetId='+dataset,
           '/api/v1/warehouse/metrics?cityId='+city+'&datasetId='+dataset,
           '/api/v1/traffic/summary?cityId='+city+'&datasetId='+dataset+'&from=2026-10-15T00:00:00.000Z&to=2026-10-17T00:00:00.000Z']
    def read(base,path):
        with urllib.request.urlopen(base+path,timeout=15) as response:
            assert response.status==200; return json.load(response)
    api_before={}; load=[]
    with services(output/'source-runtime') as base:
        for path in paths:
            api_before[path]=read(base,path)['data']
            for _ in range(3): read(base,path)
            def timed(_):
                start=time.perf_counter(); read(base,path); return (time.perf_counter()-start)*1000
            start=time.perf_counter()
            with ThreadPoolExecutor(max_workers=4) as pool: samples=list(pool.map(timed,range(40)))
            elapsed=time.perf_counter()-start; ordered=sorted(samples)
            load.append(dict(path=path,requests=40,concurrency=4,errors=0,p50Ms=round(ordered[19],3),
                p95Ms=round(ordered[37],3),maxMs=round(max(samples),3),elapsedSeconds=round(elapsed,3),requestsPerSecond=round(40/elapsed,3)))
        with (output/'browser.log').open('x',encoding='utf-8') as log:
            code=subprocess.run(['node','frontend/scripts/verify-s9.mjs',str(output/'browser'),base,city,kind,published_id],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        assert code==0,'production Chromium failed; see browser.log'
    before=snapshot()
    private=ROOT/'data/private'/('s9-backup-'+secrets.token_hex(12)); private.mkdir(parents=True,exist_ok=False)
    dump=private/'synthetic.sql'
    client=os.environ.get('MYSQL_CLIENT','mysql')
    suffix='.exe' if os.name=='nt' else ''
    dump_tool=Path(client).with_name('mysqldump'+suffix) if Path(client).is_absolute() else Path(shutil.which('mysqldump') or 'mysqldump')
    common=['--no-defaults','--protocol=TCP','-h127.0.0.1','-P'+match[1],'--default-character-set=utf8mb4']
    source_env={**os.environ,'MYSQL_PWD':os.environ['DB_PASSWORD'],'MYSQL_TEST_LOGIN_FILE':str(private/'absent.cnf')}
    with dump.open('xb') as file:
        result=subprocess.run([str(dump_tool),*common,'-u'+os.environ['DB_USER'],'--single-transaction',
            '--no-tablespaces','--skip-lock-tables','--skip-add-locks','--set-gtid-purged=OFF','--skip-add-drop-table',match[2]],env=source_env,stdout=file,stderr=subprocess.PIPE)
    (private/'dump-stderr.txt').write_bytes(result.stderr)
    assert result.returncode==0,'logical dump failed (private diagnostic withheld)'
    restore_env={**os.environ,'MYSQL_PWD':os.environ['S9_RESTORE_PASSWORD'],'MYSQL_TEST_LOGIN_FILE':str(private/'absent.cnf')}
    with dump.open('rb') as file:
        result=subprocess.run([client,*common,'-u'+os.environ['S9_RESTORE_USER'],target],env=restore_env,stdin=file,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (private/'restore-stderr.txt').write_bytes(result.stderr)
    error_code=re.search(rb'ERROR (\d+) \(([A-Z0-9]+)\)',result.stderr)
    assert result.returncode==0,'restore failed '+(error_code.group().decode() if error_code else '(see private diagnostic)')
    after=snapshot(True)
    assert before==after, 'full table content mismatch'
    assert before==snapshot(), 'source changed during restore'
    restored={**os.environ,'DB_URL':f'jdbc:mysql://127.0.0.1:{match[1]}/{target}?connectionTimeZone=UTC',
        'DB_USER':os.environ['S9_RESTORE_USER'],'DB_PASSWORD':os.environ['S9_RESTORE_PASSWORD']}
    with services(output/'restored-runtime',restored) as base:
        assert all(read(base,path)['data']==api_before[path] for path in paths)
    assert snapshot(True)==after, 'migration/startup changed restored rows'
    def write(name,value): (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    write('backup-restore.json',dict(passed=True,sourceSchema=match[2],targetSchema=target,targetInitiallyEmpty=True,
        allTables=before,restoredAllTables=after,sourceUnchanged=True,restoredApiDataEqual=True,
        flywayRevalidation=True,dumpBytes=dump.stat().st_size,dumpSha256=hashlib.sha256(dump.read_bytes()).hexdigest(),
        privateDumpExcluded=True,pointers={t:query('SELECT * FROM '+t) for t in ('warehouse_current','prediction_current')}))
    write('performance.json',dict(measuredAt=datetime.now(timezone.utc).isoformat(),os=platform.platform(),cpu=platform.processor(),
        logicalCpus=os.cpu_count(),data='synthetic_test',observationRows=before['traffic_observation']['rows'],
        route='production dist -> Vite loopback preview proxy -> Java -> real MySQL',warmup=3,api=load,
        limitation='Small local warm-cache smoke; not public capacity/SLA or large-data throughput'))
    write('preflight.json',preflight())
    write('summary.json',dict(passed=True,backupRestore=True,productionBrowser=True,httpLoad=True,realTraffic=False))
    print('S9_RELEASE_CHECKS=PASS',flush=True)

if __name__=='__main__': main()
