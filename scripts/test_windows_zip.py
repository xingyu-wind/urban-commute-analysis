"""Real Windows package acceptance: BAT entrypoints, MySQL, HTTP auth, bridge, Job cleanup.

Never connects to the repository's existing MySQL. Evidence excludes credentials/cookies.
"""
import argparse
import ctypes
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--browser',action='store_true',help='Reuse existing S9 Chromium driver against the installed package URL')
    parser.add_argument('--demo-browser',action='store_true',help='Also perform real ADMIN upload/review/import and READER browser actions')
    parser.add_argument('--offline',action='store_true',help='Validate the new USB offline path and reuse prior abrupt-supervisor regression evidence')
    args=parser.parse_args();root=args.root.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,URBAN_COMMUTE_NO_PAUSE='1',DB_URL='invalid-inherited-project-database',DB_USER='invalid',DB_PASSWORD='invalid',
             JDK_JAVA_OPTIONS='--invalid-inherited-option',PYTHONPATH='invalid-inherited-python-path')
    env['PATH']=os.environ['SystemRoot']+'/System32;'+os.environ['SystemRoot']+'/System32/WindowsPowerShell/v1.0'
    results=[]
    def browser(scenario,city,kind,identity):
        if not args.browser:return
        repository=Path(__file__).resolve().parents[1]
        with (output/('browser-'+scenario+'.log')).open('wb') as log:
            result=subprocess.run([shutil.which('node'),str(repository/'frontend/scripts/verify-s9.mjs'),
                str(output/('browser-'+scenario)),running()['url'],city,kind,identity],cwd=repository,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        assert result.returncode==0,'Production browser smoke failed: '+scenario
        results.append(dict(check='production-chromium-'+scenario,passed=True,widths=[1440,390],requestInterception=False))
    def batch(name,arguments='',success=True):
        command='"'+str(root/(name+'.bat'))+'"'+(' '+arguments if arguments else '')
        started=time.monotonic()
        result=subprocess.run(command,shell=True,cwd=root.parent,env=env,capture_output=True,timeout=240)
        # These entrypoints never print credentials; CREDENTIALS is intentionally excluded.
        (output/(name+'-'+str(len(results))+'.log')).write_bytes(result.stdout+result.stderr)
        assert (result.returncode==0)==success,(name,result.returncode,(result.stdout+result.stderr)[-800:])
        results.append(dict(check=name,expectedSuccess=success,exitCode=result.returncode,seconds=round(time.monotonic()-started,2)))
    def running():return json.loads((root/'state/running.json').read_text())
    def client():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(who,method,path,expected,body=None,headers=None):
        req=urllib.request.Request(running()['url']+path,data=body,method=method,headers=headers or {})
        try:response=who.open(req,timeout=70)
        except urllib.error.HTTPError as e:response=e
        raw=response.read()
        results.append(dict(check='http',method=method,path=path,status=response.status,expected=expected))
        assert response.status==expected,(method,path,response.status)
        return json.loads(raw) if raw and response.headers.get_content_type()=='application/json' else raw
    def post(who,path,expected,body,content='application/json'):
        token=request(who,'GET','/api/v1/auth/csrf',200)
        return request(who,'POST',path,expected,body,{token['headerName']:token['token'],'Content-Type':content})
    # Load the installed copy, not the source module, solely to decrypt local credentials in memory.
    spec=importlib.util.spec_from_file_location('installed_launcher',root/'launcher/portable.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if args.offline:
        assert module.OFFLINE and not (root/'runtime/downloads').exists()
        env.update(HTTP_PROXY='http://127.0.0.1:9',HTTPS_PROXY='http://127.0.0.1:9')
        results.append(dict(check='offline-package-mode',passed=True,vendorFilesIncluded=True,
            runtimeDownloadCachePresent=False,physicalNetworkDisconnected=False))
    try:
        batch('CHECK-ENV')
        batch('FIRST-SETUP','-AcceptLicenses') # Also verifies repeat setup is non-destructive.
        secret=module.credentials()
        assert secret['ADMIN']['password']!=secret['READER']['password'] and len(secret['ADMIN']['password'])>=24
        batch('START')
        base=running()['url'];anonymous=client();admin=client();reader=client()
        request(anonymous,'GET','/',200)
        request(anonymous,'GET','/health',200)
        cities=request(anonymous,'GET','/api/v1/cities',200);assert cities['data']
        predictions=request(anonymous,'GET','/api/v1/predictions?cityId=s7-city&datasetId=s7-synthetic-v1',200)
        assert predictions['data']['release'] and len(predictions['data']['predictions'])==7
        browser('model','s7-city','prediction',predictions['data']['release']['jobId'])
        if args.demo_browser:
            repository=Path(__file__).resolve().parents[1]
            with (output/'browser-management.log').open('wb') as log:
                result=subprocess.run([shutil.which('node'),str(repository/'frontend/scripts/verify-t3-demo.mjs'),
                    str(output/'browser-management'),base,str(root)],input=json.dumps({r:secret[r] for r in ('ADMIN','READER')}).encode(),
                    cwd=repository,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            assert result.returncode==0,'Browser management rehearsal failed'
            results.append(dict(check='browser-admin-reader-research-import',passed=True))
        request(anonymous,'GET','/api/v1/traffic/summary?cityId=s7-city&datasetId=s7-synthetic-v1&from=2026-10-15T00:00:00.000Z&to=2026-10-17T00:00:00.000Z',200)
        request(anonymous,'GET','/api/v1/traffic/series?cityId=s7-city&datasetId=s7-synthetic-v1&from=2026-10-15T00:00:00.000Z&to=2026-10-17T00:00:00.000Z&granularity=day',200)
        request(anonymous,'GET','/api/v1/operations/tasks',401)
        request(anonymous,'POST','/api/v1/operations/uploads',401,b'x',{'Content-Type':'application/octet-stream'})
        for role,who in [('ADMIN',admin),('READER',reader)]:
            body=urllib.parse.urlencode(secret[role]).encode()
            post(who,'/api/v1/auth/login',200,body,'application/x-www-form-urlencoded')
            me=request(who,'GET','/api/v1/auth/me',200);assert me['role']==role
            request(who,'GET','/api/v1/operations/tasks',200)
        request(admin,'POST','/api/v1/operations/uploads',403,b'x',{'Content-Type':'application/octet-stream'})
        post(reader,'/api/v1/operations/uploads',403,b'x','application/octet-stream')
        boundary='t2-owned-fixture-upload'
        raw=(root/'database/research-demo.csv').read_bytes()
        upload=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode())
        proposed=post(admin,'/api/v1/operations/uploads',200,upload,'multipart/form-data; boundary='+boundary)
        assert proposed
        review=json.loads((root/'database/research-review.json').read_text())
        post(admin,'/api/v1/operations/imports/'+proposed['id']+'/confirm',200,
             json.dumps(dict(review=review,acknowledgement=proposed['proposal']['proposalSha256'])).encode())
        imported=post(admin,'/api/v1/operations/imports/'+proposed['id']+'/execute',200,b'')
        assert imported['status']=='SUCCEEDED'
        # Real installed CPython bridge has now parsed the original fixture through Java HTTP.
        results.append(dict(check='actual-http',passed=True,cities=len(cities['data']),predictionPoints=7,
            adminLogin=True,readerLogin=True,anonymousDenied=True,readerUploadDenied=True,csrfDenied=True,pythonBridgeInspect=True,researchImport='SUCCEEDED'))
        batch('START',success=False)
        config=json.loads((root/'state/instance.json').read_text())
        import pymysql
        with pymysql.connect(host='127.0.0.1',port=config['dbPort'],user=config['dbUser'],password=secret['dbPassword'],database=config['schemas']['model']) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT VERSION(),@@datadir');version,directory=cursor.fetchone()
                assert Path(directory).resolve()==module.mysql_home()/'data'
                cursor.execute('SELECT COUNT(*) FROM traffic_observation');assert cursor.fetchone()[0]==4369
                cursor.execute('SELECT version,success FROM flyway_schema_history ORDER BY installed_rank');migrations=cursor.fetchall()
                assert [x[0] for x in migrations]==['1','2','3','4','5','6'] and all(x[1] for x in migrations)
        results.append(dict(check='real-owned-database',version=version,ownedDatadir=True,observationRows=4369,flyway='V1-V6'))
        batch('STOP');batch('STOP')
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1',config['webPort']));occupied.listen()
            batch('START',success=False)
        batch('START')
        request(admin,'GET','/api/v1/auth/me',401) # Session cannot survive JVM restart.
        request(anonymous,'GET','/api/v1/predictions?cityId=s7-city',200)
        post(reader,'/api/v1/auth/login',200,urllib.parse.urlencode(secret['READER']).encode(),'application/x-www-form-urlencoded')
        persisted=request(reader,'GET','/api/v1/operations/tasks',200)
        assert any(item['status']=='SUCCEEDED' for item in persisted['imports'])
        results.append(dict(check='research-import-persists-after-restart',passed=True))
        live=running()
        # Kill only the process just created by this test, using its live HANDLE.
        kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        if not args.offline:
            handle=kernel.OpenProcess(0x0001|0x00100000,False,live['pid']);assert handle
            try:assert kernel.TerminateProcess(handle,91)
            finally:kernel.CloseHandle(handle)
            for _ in range(100):
                try:
                    module.ports_available(config);break
                except RuntimeError:time.sleep(.2)
            else:raise AssertionError('Job Object did not close owned listening services')
            results.append(dict(check='abrupt-supervisor-exit',passed=True,allOwnedPortsReleased=True))
            batch('START') # Normal MySQL crash recovery, same initialized directory.
            request(anonymous,'GET','/api/v1/predictions?cityId=s7-city',200)
        batch('STOP');batch('START-WAREHOUSE')
        warehouse=request(client(),'GET','/api/v1/warehouse/metrics?cityId=s5-city&datasetId=s5-synthetic-v1&grain=WINDOW',200)
        assert warehouse['data']['release'] and warehouse['data']['items']
        browser('warehouse','s5-city','warehouse',warehouse['data']['release']['id'])
        results.append(dict(check='prepublished-hive-query',passed=True,items=len(warehouse['data']['items']),localHiveExecution=False))
        batch('STOP')
        if args.offline:
            assert not (root/'runtime/downloads').exists()
            results.append(dict(check='offline-no-download-cache-created',passed=True))
        (output/'summary.json').write_text(json.dumps(dict(passed=True,root=str(root),sameWindowsHost=True,
            cleanMachineTest=False,developerExecutablesRemovedFromPath=True,checks=results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('WINDOWS_PACKAGE_ACCEPTANCE=PASS')
    finally:
        (output/'checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if (root/'state/instance.json').exists():
            try:batch('STOP')
            except Exception:pass


if __name__=='__main__':main()
