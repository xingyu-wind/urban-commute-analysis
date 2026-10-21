"""Real isolated MySQL + packaged Java HTTP + filesystem + Chromium security checks.

Run ONLY as child of s3_database.py. Evidence explicitly excludes passwords,
sessions, CSRF tokens, file samples and normalized observations.
"""
import argparse
import concurrent.futures
import copy
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
sys.path.insert(0, str(ROOT / 'contracts'))
from examples.fixtures import make_long
from validate_contract import load_contract, body_errors
import pymysql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    match = re.fullmatch(r'jdbc:mysql://127\.0\.0\.1:(\d+)/(s3test_[0-9a-f]{32})\?connectionTimeZone=UTC', os.environ['DB_URL'])
    if not match: raise RuntimeError('isolated DB required')
    private = ROOT / 'data/private' / ('s8test-' + secrets.token_hex(12)); private.mkdir(parents=True)
    multipart_tmp = private / 'multipart'; multipart_tmp.mkdir()
    managed = private / 'imports'
    evidence = []; filesystems = []; process = None; log = None
    passwords = {role: secrets.token_urlsafe(24) for role in ('ADMIN','READER')}
    env = {**os.environ, 'COMMUTE_PRIVATE_ROOT':str(managed), 'COMMUTE_UPLOAD_TMP':str(multipart_tmp),
           'COMMUTE_PYTHON':sys.executable, 'COMMUTE_BRIDGE':str(ROOT / 'scripts/s8_adapter_bridge.py')}
    for role in passwords:
        env['COMMUTE_BOOTSTRAP_' + role + '_USER'] = 's8-' + role.lower()
        env['COMMUTE_BOOTSTRAP_' + role + '_PASSWORD'] = passwords[role]
    def db(sql, parameters=()):
        with pymysql.connect(host='127.0.0.1', port=int(match[1]), user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],database=match[2],autocommit=True) as connection:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql, parameters); return cursor.fetchall()
    def count(table): return db('SELECT COUNT(*) n FROM ' + table)[0]['n']
    def client(): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    anonymous, admin, reader = client(), client(), client()
    base = ''
    spec, registry, checker = load_contract()
    def request(who, method, path, expected, body=None, headers=None, csrf=True, label=None):
        headers = dict(headers or {})
        if method == 'POST' and csrf:
            _, token = request(who,'GET','/api/v1/auth/csrf',200,label='obtain-csrf')
            headers[token['headerName']] = token['token']
        if isinstance(body,dict):
            body = json.dumps(body).encode(); headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(base+path, data=body, method=method, headers=headers)
        try: response = who.open(req, timeout=70)
        except urllib.error.HTTPError as error: response = error
        raw = response.read(); status=response.status
        assert status==expected, f'{label or path}: actual={status}, expected={expected}'
        value=json.loads(raw) if raw else None
        contract_path=re.sub(r'/imports/[0-9a-f-]{36}/','/imports/{id}/',path)
        if contract_path in spec['paths'] and str(status) in spec['paths'][contract_path].get(method.lower(),{}).get('responses',{}):
            errors=body_errors(spec,registry,checker,contract_path,str(status),value,method.lower())
            assert not errors, [(e.validator,list(e.path)) for e in errors]
        assert response.headers.get('X-Request-Id')
        assert not response.headers.get('Access-Control-Allow-Origin')
        # CSRF/session values are intentionally excluded, including from raw error logs.
        evidence.append(dict(case=label or path, method=method,path=contract_path,status=status,
                             requestContentType=headers.get('Content-Type'),responseContentType=response.headers.get('Content-Type'),
                             response=value if status>=400 else ({k:value[k] for k in ('authenticated','jobId','status','outputSha256') if k in value} if isinstance(value,dict) else None),
                             responseCode=value.get('code') if isinstance(value,dict) else None,
                             requestId=response.headers['X-Request-Id']))
        return response,value
    def login(who, role, password=None):
        return request(who,'POST','/api/v1/auth/login',200 if password is None else 401,
            urllib.parse.urlencode({'username':'s8-'+role.lower(),'password':password or passwords[role]}).encode(),
            {'Content-Type':'application/x-www-form-urlencoded'}, label='login-'+role.lower() if password is None else 'invalid-login')
    def upload(who, filename, content, expected=200, mime='text/csv'):
        boundary='S8'+secrets.token_hex(12)
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
        return request(who,'POST','/api/v1/operations/uploads',expected,body,{'Content-Type':'multipart/form-data; boundary='+boundary},label='upload-'+filename)
    def confirm(identity, mapping, expected=200):
        return request(admin,'POST',f'/api/v1/operations/imports/{identity["id"]}/confirm',expected,
            dict(review=mapping,acknowledgement=identity['proposal']['proposalSha256']),label='confirm-mapping')
    def execute(identity, expected=200, retry=False, who=admin):
        return request(who,'POST',f'/api/v1/operations/imports/{identity["id"]}/'+('retry' if retry else 'execute'),expected,label='retry' if retry else 'execute')
    try:
        with socket.socket() as s: s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        log=(output/'java.log').open('x',encoding='utf-8')
        java=Path(os.environ['JAVA_HOME'])/'bin'/('java.exe' if os.name=='nt' else 'java')
        process=subprocess.Popen([str(java),'-jar',str(ROOT/'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar'),
                '--server.port='+str(port),'--server.servlet.session.timeout=1m',
                '--server.tomcat.max-swallow-size=-1'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        for _ in range(120):
            if process.poll() is not None: raise RuntimeError('owned Java startup failed')
            try:
                if urllib.request.urlopen(base+'/health',timeout=1).status==200: break
            except Exception: time.sleep(.5)
        else: raise RuntimeError('Java startup timed out')
        # Gate actual new schema identity before test writes, never a persistent app DB.
        assert db('SELECT DATABASE() d, CURRENT_USER() u, @@server_uuid s')[0] == dict(d=match[2],u=os.environ['TEST_DB_USER']+'@%',s=os.environ['TEST_DB_SERVER_UUID'])
        assert count('managed_import')==count('managed_job')==0
        for _ in range(100):
            if db("SELECT COUNT(*) n FROM app_user WHERE username IN ('s8-admin','s8-reader')")[0]['n']==2: break
            if process.poll() is not None: raise RuntimeError('owned bootstrap failed')
            time.sleep(.1)
        else: raise RuntimeError('explicit test identities not ready')
        # Real MySQL constraint failures, restricted to two synthetic test identities:
        # failed login auditing must undo authentication; failed logout auditing must
        # never prevent framework session invalidation. No table/data is dropped.
        db("INSERT INTO app_user(username,password_hash,role) SELECT 'audit-blocked',password_hash,'READER' FROM app_user WHERE username='s8-admin'")
        db("ALTER TABLE security_audit ADD CONSTRAINT ck_s8_audit_fault CHECK (NOT(actor='audit-blocked' AND action='LOGIN') AND NOT(actor='s8-admin' AND action='LOGOUT'))")
        blocked=client()
        request(blocked,'POST','/api/v1/auth/login',503,
            urllib.parse.urlencode({'username':'audit-blocked','password':passwords['ADMIN']}).encode(),
            {'Content-Type':'application/x-www-form-urlencoded'},label='login-audit-storage-failure')
        request(blocked,'GET','/api/v1/auth/me',401,label='failed-login-audit-left-no-session')
        request(anonymous,'GET','/api/v1/operations/tasks',401)
        request(anonymous,'GET','/api/v1/auth/me',401)
        upload(anonymous,'anonymous.csv',b'a,b,c\n1,2,3',401)
        assert count('managed_import')==0 and not list(managed.iterdir())
        login(admin,'ADMIN','incorrect-test-password')
        session_response, old_csrf=request(admin,'GET','/api/v1/auth/csrf',200)
        # Cookies were set on earlier anonymous CSRF access; inspect their attributes
        # via CookieJar, never serialize their values.
        jar=next(h.cookiejar for h in admin.handlers if isinstance(h,urllib.request.HTTPCookieProcessor))
        old_session=next(c.value for c in jar if c.name=='JSESSIONID')
        assert all('HttpOnly' in c._rest and c._rest.get('SameSite')=='Strict' for c in jar if c.name=='JSESSIONID')
        login(admin,'ADMIN'); login(reader,'READER')
        assert next(c.value for c in jar if c.name=='JSESSIONID')!=old_session
        request(admin,'POST','/api/v1/operations/uploads',403,b'',{old_csrf['headerName']:old_csrf['token']},csrf=False,label='pre-login-csrf-invalidated')
        request(reader,'GET','/api/v1/operations/tasks',200)
        # S9: real HTTP against packaged production JAR. Include valid CSRF so
        # role/method/default-denial checks cannot pass merely due to missing CSRF.
        before = {t: count(t) for t in ('managed_import','managed_job','traffic_observation','warehouse_current','prediction_current')}
        for who, role in ((anonymous,'anonymous'),(reader,'reader'),(admin,'admin')):
            for path in ('/not-a-route','/api/v1/traffic/admin','/api/v1/warehouse/publish',
                         '/api/v1/operations/admin','/api/v1/operations/uploads/extra',
                         '/api/v1/auth/register','/api/v1/operations/imports/'+('0'*36)+'/delete'):
                for method in ('GET','POST','PUT','PATCH','DELETE'):
                    headers = {}
                    if method not in ('GET',):
                        token = request(who,'GET','/api/v1/auth/csrf',200)[1]
                        headers[token['headerName']] = token['token']
                    request(who,method,path,404,b'{}' if method!='GET' else None,headers,csrf=False,label='s9-default-deny-'+role)
            for path in ('/health','/api/v1/cities','/api/v1/traffic/summary','/api/v1/traffic/series',
                         '/api/v1/traffic/regions','/api/v1/traffic/roads','/api/v1/warehouse/metrics','/api/v1/predictions'):
                for method in ('POST','PUT','PATCH','DELETE'):
                    response,_=request(who,method,path,405,b'{}',csrf=False,label='s9-readonly-method-'+role)
                    assert 'GET' in response.headers['Allow']
            for method in ('GET','PUT','PATCH','DELETE'):
                token=request(who,'GET','/api/v1/auth/csrf',200)[1]
                request(who,method,'/api/v1/operations/uploads',401 if role=='anonymous' else 403,
                        headers={token['headerName']:token['token']},csrf=False,label='s9-write-method-'+role)
            for method,path in (('GET','/api/v1/auth/login'),('PUT','/api/v1/auth/login'),
                                ('POST','/api/v1/auth/me'),('POST','/api/v1/auth/csrf'),
                                ('GET','/api/v1/auth/logout'),('POST','/api/v1/operations/tasks')):
                token=request(who,'GET','/api/v1/auth/csrf',200)[1]
                request(who,method,path,401 if role=='anonymous' else 403,
                        headers={token['headerName']:token['token']},csrf=False,label='s9-auth-method-'+role)
        assert before == {t: count(t) for t in before}
        assert not list(managed.iterdir()) and not list(multipart_tmp.iterdir())
        (output/'s9-denied-writes.json').write_text(json.dumps(dict(passed=True,before=before,after={t:count(t) for t in before},
            privateDirectories=0,multipartFiles=0,auditWritesExcluded=True),indent=2)+'\n',encoding='utf-8')
        fixture, review=make_long(private/'fixture',days=14)
        raw=fixture.read_bytes()
        upload(reader,'reader.csv',raw,403)
        fake=dict(id='00000000-0000-0000-0000-000000000000')
        for operation in ('confirm','execute','retry'):
            request(reader,'POST',f'/api/v1/operations/imports/{fake["id"]}/{operation}',403,dict(review=review))
        assert count('managed_import')==count('managed_job')==0 and not list(managed.iterdir())
        reader_last_access=time.monotonic()
        request(admin,'POST','/api/v1/operations/uploads',403,b'',csrf=False,label='missing-csrf-admin')
        request(admin,'POST','/api/v1/operations/imports/------------------------------------/execute',400,label='malformed-uuid')
        request(admin,'POST',f'/api/v1/operations/imports/{fake["id"]}/execute',404,label='unknown-import')
        for filename, data, status, mime in [
            ('../escape.csv',raw,400,'text/csv'),('..\\escape.csv',raw,400,'text/csv'),
            ('payload.exe',raw,400,'text/csv'),('fake.csv',b'<html>execute me</html>',422,'text/csv'),
            ('fake.json',raw,422,'application/json'),('wrong.csv',raw,415,'image/png'),
            ('malformed.csv',b'a,b,c\n1,2\n',422,'text/csv'),('quotes.csv',b'a,b,c\n"unterminated,2,3',422,'text/csv'),
            ('nested.json',b'[{"a":[],"b":1,"c":2}]',422,'application/json'),
            ('duplicate.json',b'[{"a":1,"a":2,"b":3,"c":4}]',422,'application/json'),
            ('large.csv',b'x'*(2*1024*1024+1),413,'text/csv')]:
            upload(admin,filename,data,status,mime)
            assert not list(managed.iterdir()), 'failed upload leaked files'
            assert count('managed_import')==count('managed_job')==0
            filesystems.append(dict(case=filename,status=status,retainedUploadDirectories=len(list(managed.iterdir())),
                                    multipartTemporaryFiles=len(list(multipart_tmp.iterdir())),metadataRows=count('managed_import'),jobRows=count('managed_job')))
        assert not list(multipart_tmp.iterdir()), 'multipart temp leaked'
        assert not (managed.parent/'escape.csv').exists()
        _, identity=upload(admin,'traffic.csv',raw)
        execute(identity,409)
        assert count('managed_job')==0
        mapping=copy.deepcopy(review); mapping['unit']='index_0_10'
        confirm(identity,mapping,422)
        confirm(identity,review)
        confirm(identity,review,409)
        record=db('SELECT confirmed_by,configuration_sha256,confirmed_at FROM managed_import WHERE id=%s',(identity['id'],))[0]
        assert record['confirmed_by']=='s8-admin' and len(record['configuration_sha256'])==64 and record['confirmed_at']
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            # Each call uses a separate HTTP opener with the same authenticated session,
            # avoiding CookieJar mutations during concurrent requests.
            token=request(admin,'GET','/api/v1/auth/csrf',200)[1]
            cookie=next(h.cookiejar for h in admin.handlers if isinstance(h,urllib.request.HTTPCookieProcessor))
            cookie_header='; '.join(c.name+'='+c.value for c in cookie)
            def race():
                req=urllib.request.Request(base+f'/api/v1/operations/imports/{identity["id"]}/execute',data=b'',method='POST',headers={'Cookie':cookie_header,token['headerName']:token['token']})
                try: r=urllib.request.urlopen(req,timeout=70)
                except urllib.error.HTTPError as e: r=e
                value=json.loads(r.read()); return r.status, value
            raced=list(pool.map(lambda _:race(),range(2)))
        assert sorted(r[0] for r in raced)==[200,409], [r[0] for r in raced]
        evidence.append(dict(case='concurrent-import',statuses=sorted(r[0] for r in raced),databaseJobRows=count('managed_job')))
        execute(identity,409); execute(identity,409,retry=True)
        assert count('managed_job')==1 and count('traffic_observation')==0 and count('warehouse_current')==count('prediction_current')==0
        job=db('SELECT status,attempts,output_sha256 FROM managed_job')[0]
        assert job['status']=='SUCCEEDED' and job['attempts']==1
        assert (managed/identity['id']/'normalized.json').exists()
        json_file,json_review=make_long(private/'json-fixture',days=14,fmt='json')
        _, json_input=upload(admin,'traffic.json',json_file.read_bytes(),mime='application/json')
        confirm(json_input,json_review); execute(json_input)
        # Real input checksum failure, then restored input exercises a justified safe retry.
        _, retry_input=upload(admin,'retry.csv',raw)
        confirm(retry_input,review)
        retry_raw=managed/retry_input['id']/'input.csv'; retry_raw.write_bytes(raw+b'corrupted')
        execute(retry_input,422)
        assert not (retry_raw.parent/'normalized.json').exists()
        assert db('SELECT status FROM managed_job WHERE import_id=%s',(retry_input['id'],))[0]['status']=='FAILED'
        retry_raw.write_bytes(raw)
        execute(retry_input,retry=True)
        assert db('SELECT status,attempts FROM managed_job WHERE import_id=%s',(retry_input['id'],))[0]==dict(status='SUCCEEDED',attempts=2)
        # Mapping rights stay unverified: confirmation alone never grants import authority.
        _, unlicensed=upload(admin,'unlicensed.csv',raw)
        restricted=copy.deepcopy(review); restricted.update(source_type='historical_snapshot',license_status='unverified')
        confirm(unlicensed,restricted); execute(unlicensed,422)
        assert not (managed/unlicensed['id']/'normalized.json').exists()
        # Too-short data still cannot bypass task applicability.
        _, short=upload(admin,'short.csv',b'measured_at,sensor,velocity\n2024-01-01T00:00:00Z,test,40\n')
        confirm(short,review); execute(short,422)
        for attempt in (2,3): execute(short,422,retry=True)
        execute(short,409,retry=True)
        assert db('SELECT status,attempts FROM managed_job WHERE import_id=%s',(short['id'],))[0]==dict(status='FAILED',attempts=3)
        assert not list(multipart_tmp.iterdir())
        # Session invalidation and login/CSRF lifecycle; no auth material is retained.
        cookie=next(h.cookiejar for h in admin.handlers if isinstance(h,urllib.request.HTTPCookieProcessor))
        old_cookie='; '.join(c.name+'='+c.value for c in cookie)
        request(admin,'POST','/api/v1/auth/logout',200)
        request(client(),'GET','/api/v1/operations/tasks',401,headers={'Cookie':old_cookie},label='logged-out-session-replay')
        request(admin,'GET','/api/v1/auth/me',401)
        request(admin,'POST','/api/v1/operations/uploads',401,b'',csrf=False)
        login(admin,'ADMIN')
        request(admin,'GET','/api/v1/operations/tasks',200,headers={'Origin':'https://attacker.invalid'})
        env.update(S8_API_BASE=base,S8_FIXTURE=str(fixture),S8_REVIEW=json.dumps(review))
        browser=output/'browser'
        with (output/'browser.log').open('x',encoding='utf-8') as browser_log:
            result=subprocess.run(['node','frontend/scripts/verify-s8.mjs',str(browser)],env=env,cwd=ROOT,stdout=browser_log,stderr=subprocess.STDOUT)
        assert result.returncode==0, 'Chromium checks failed; see browser.log'
        # Test-only one-minute timeout; production default remains 20 minutes.
        remaining=62-(time.monotonic()-reader_last_access)
        if remaining>0: time.sleep(remaining)
        request(reader,'GET','/api/v1/operations/tasks',401,label='idle-session-expired')
        assert count('warehouse_current')==count('prediction_current')==count('traffic_observation')==0
        users=db('SELECT username,password_hash,role FROM app_user')
        assert all(u['password_hash'].startswith('$2a$12$') and all(p not in u['password_hash'] for p in passwords.values()) for u in users)
        state=dict(imports=db('SELECT id,input_sha256,configuration_sha256,confirmed_by,confirmed_at FROM managed_import'),
                   jobs=db('SELECT id,import_id,status,attempts,operated_by,input_sha256,mapping_sha256,output_sha256,error_code FROM managed_job'),
                   audit=db('SELECT action,outcome,COUNT(*) n FROM security_audit GROUP BY action,outcome ORDER BY action,outcome'),
                   observationRows=count('traffic_observation'),warehousePointerRows=count('warehouse_current'),predictionPointerRows=count('prediction_current'),
                   multipartFiles=len(list(multipart_tmp.iterdir())),passwordHashes='BCrypt cost 12; no plaintext',schema=match[2])
        (output/'database.json').write_text(json.dumps(state,indent=2,default=str)+'\n',encoding='utf-8')
        assert any(a['action']=='UPLOAD' and a['outcome']=='FILE_SIZE' for a in state['audit'])
        assert any(a['action']=='LOGIN_FAILED' for a in state['audit'])
        (output/'http.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        (output/'filesystem.json').write_text(json.dumps(filesystems,indent=2)+'\n',encoding='utf-8')
        (output/'summary.json').write_text(json.dumps(dict(passed=True,httpCases=len(evidence),concurrentStatuses=[200,409],
            originalData='synthetic_test',privateRawExcluded=True,filesystemChecks=True,databaseChecks=True,browserChecks=True),indent=2)+'\n',encoding='utf-8')
        print('S8_REAL_SECURITY=PASS', flush=True)
    except Exception:
        (output/'partial-http.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        raise
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        if log: log.close()


if __name__ == '__main__': main()
