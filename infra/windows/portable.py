"""Windows-only candidate launcher. No global installs, services, or existing databases.

All mutable files are in state/; downloaded vendor components stay in runtime/.
Windows Job Objects contain owned children even when this supervisor is killed.
"""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import http.client
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import msvcrt
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = (ROOT/'config/desktop.json').is_file()
DATA = Path(os.environ['UC_DATA_HOME']).resolve() if DESKTOP else ROOT
STATE = DATA / 'state'
RUNTIME = DATA / 'runtime'
OFFLINE = (ROOT/'config/offline.json').is_file()
CREATE = subprocess.CREATE_NO_WINDOW
TABLES = ('dataset_registry','city','region','road_segment','traffic_observation',
          'etl_source','etl_batch','etl_rejection','etl_batch_observation',
          'warehouse_release','warehouse_metric','warehouse_current',
          'prediction_model','prediction_job','prediction_evaluation','prediction_result','prediction_current')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.new')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    os.replace(temporary, path)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify():
    for line in (ROOT/'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        path = ROOT / name
        if not path.is_file() or sha(path) != digest:
            raise RuntimeError('Package integrity failed: '+name+'; extract a fresh ZIP. Data retained.')


def private_directory(directory):
    directory.mkdir(parents=True,exist_ok=True)
    # Grant only the current user's SID; do not rely on localized account names.
    import csv
    sid = list(csv.reader(subprocess.check_output(['whoami','/user','/fo','csv','/nh'], text=True).splitlines()))[0][1]
    result = subprocess.run(['icacls',str(directory),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F'],
                            capture_output=True, creationflags=CREATE)
    if result.returncode:
        raise RuntimeError('Cannot protect state directory ACL. Use a writable local NTFS directory.')


def private_state():
    private_directory(STATE)


def mysql_home():
    location=STATE/'mysql-location.json'
    if location.exists():return Path(read(location)['directory'])
    # MySQL's native Windows file handling is unreliable with non-ASCII paths.
    # Keep this install's owned MySQL under LocalAppData; Java/Python/UI stay in the extraction.
    buffer=ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None,0x001c,None,0,buffer):
        raise RuntimeError('Cannot locate current-user LocalAppData')
    candidates=[p for p in ((DATA,) if DESKTOP else (ROOT,*ROOT.parents)) if str(p).isascii() and p.parent!=p]
    local=Path(buffer.value)
    if not str(local).isascii():
        short=ctypes.create_unicode_buffer(32768)
        ctypes.windll.kernel32.GetShortPathNameW(str(local),short,len(short))
        local=Path(short.value or str(local))
    if str(local).isascii():candidates.append(local)
    directory=None
    for parent in candidates:
        candidate=parent/('UrbanCommute-LocalData-'+secrets.token_hex(12))
        try:
            candidate.mkdir(exist_ok=False);private_directory(candidate)
            directory=candidate;break
        except PermissionError:continue
    if directory is None:
        raise RuntimeError('MySQL requires a writable ASCII native storage path. Extract under an ASCII writable parent directory. No database initialized.')
    write(location,dict(directory=str(directory),owned=True,reason='MySQL Unicode path compatibility; own unique directory under nearest writable ASCII ancestor'))
    return directory


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), 'UrbanCommute local demo', None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise RuntimeError('Windows current-user DPAPI operation failed. Initialized data cannot move to a different Windows account.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


def credentials():
    return json.loads(protect((STATE/'secrets.dpapi').read_bytes(), True))


@contextlib.contextmanager
def exclusive():
    private_state()
    with (STATE/'instance.lock').open('a+b') as stream:
        stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('This copy is already starting/running/configuring. Use STOP.bat before retrying.')
        try:
            yield
        finally:
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def clean_env():
    # Never inherit another project's database, JVM agents, Python paths or bootstrap.
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith(
        ('DB_', 'TEST_DB_', 'COMMUTE_', 'PYTHON', 'JAVA_', 'JDK_', '_JAVA_', 'MYSQL_', 'S3_', 'S9_'))}
    env.update(PYTHONUTF8='1', PYTHONNOUSERSITE='1',NO_PROXY='127.0.0.1,::1,localhost')
    return env


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); return sock.getsockname()[1]


def ports_available(config):
    held = []
    try:
        for key in ('dbPort','apiPort','webPort'):
            sock = socket.socket(); held.append(sock)
            sock.bind(('127.0.0.1',config[key]))
    except OSError:
        raise RuntimeError('A configured loopback port is occupied. No process was stopped. Check state/instance.json and CHECK-ENV.bat.')
    finally:
        for sock in held: sock.close()


def runtime(kind):
    folder = mysql_home()/'runtime' if kind=='mysql' else RUNTIME/kind
    filename = {'java':'java.exe','mysql':'mysqld.exe','python':'python.exe'}[kind]
    matches = list(folder.rglob(filename))
    if len(matches) != 1:
        raise RuntimeError('Runtime missing or ambiguous: '+kind+'. Run FIRST-SETUP.bat.')
    return matches[0]


def download_component(item, cache):
    """Only promote complete pinned bytes; preserve failures without poisoning retries."""
    if OFFLINE:
        file=ROOT/'vendor/components'/item['filename']
        if not file.is_file():
            raise RuntimeError('Offline component missing: '+item['filename']+'. Restore the complete USB ZIP; no download attempted.')
        if file.stat().st_size!=item['bytes'] or sha(file)!=item['sha256']:
            raise RuntimeError('Offline component size/SHA256 mismatch: '+item['filename']+'. Restore the complete USB ZIP; no download attempted.')
        print('Verified offline component: '+item['filename'],flush=True)
        return file
    file = cache/item['filename']
    def valid(path):
        return path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
    def retain(path):
        if path.exists():
            os.replace(path, path.with_name(path.name+'.failed-'+str(time.time_ns())))
    if file.exists():
        if valid(file):
            print('Verified cache: '+file.name,flush=True)
            return file
        retain(file)
        print('Invalid cache retained for diagnosis: '+file.name,flush=True)
    temporary = file.with_name(file.name+'.partial')
    retain(temporary)
    for attempt in range(1,4):
        print(f'Downloading {file.name} (attempt {attempt}/3) from {item["url"]}',flush=True)
        try:
            with urllib.request.urlopen(item['url'],timeout=90) as response, temporary.open('wb') as target:
                shutil.copyfileobj(response,target)
            if not valid(temporary):
                raise ValueError('size/SHA256 mismatch; verification was not bypassed')
            os.replace(temporary,file)
            return file
        except (OSError,urllib.error.URLError,http.client.HTTPException,ValueError) as error:
            retain(temporary)
            reason=f'{type(error).__name__}: {error}'
            print(f'Download failed: {file.name}; {reason}',flush=True)
            if attempt==3:
                raise RuntimeError(f'Download failed after 3 attempts: {file.name}; source={item["url"]}; {reason}. Completed verified files retained. Run FIRST-SETUP again.') from error
            time.sleep(attempt)


def install_components():
    lock = read(ROOT/'config/components.lock.json')
    cache = RUNTIME/'downloads'
    if not OFFLINE:cache.mkdir(parents=True,exist_ok=True)
    for item in lock['components']:
        file = download_component(item,cache)
        if item['kind']=='jar':
            destination=RUNTIME/'backend-libs'/item['filename']
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(file,destination)
            continue
        destination=mysql_home()/'runtime' if item['kind']=='mysql' else RUNTIME/('python/Lib/site-packages' if item['kind']=='wheel' else item['kind'])
        destination.mkdir(parents=True,exist_ok=True)
        marker=destination/('.'+item['filename']+'.verified')
        if not marker.exists() or marker.read_text(encoding='ascii') != item['sha256']:
            with zipfile.ZipFile(file) as archive:
                for name in archive.namelist():
                    if not (destination/name).resolve().is_relative_to(destination.resolve()):
                        raise RuntimeError('Unsafe vendor archive path')
                archive.extractall(destination)
            marker.write_text(item['sha256'],encoding='ascii')
    # CPython embed uses its own explicit search path, not a nonportable venv.
    (RUNTIME/'python/python311._pth').write_text('python311.zip\n.\nLib/site-packages\nimport site\n',encoding='ascii')
    import importlib
    sys.path.insert(0,str(RUNTIME/'python/Lib/site-packages'))
    importlib.invalidate_caches()
    result = subprocess.run([str(runtime('python')),'-I','-c',
        'import numpy,scipy,sklearn,xgboost,pymysql,cryptography,zoneinfo; zoneinfo.ZoneInfo("Asia/Shanghai"); print("PORTABLE_PYTHON_IMPORTS=PASS")'],
        env=clean_env(),capture_output=True,creationflags=CREATE)
    if result.returncode:
        (STATE/'python-diagnostic.log').write_bytes(result.stderr)
        raise RuntimeError('Portable Python dependency import failed. See state/python-diagnostic.log; check Microsoft VC++ x64 runtime.')
    print('Portable runtime imports verified.',flush=True)


class Job:
    def __init__(self):
        # JOBOBJECT_EXTENDED_LIMIT_INFORMATION: set KILL_ON_JOB_CLOSE.
        class Basic(ctypes.Structure):
            _fields_=[('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',wintypes.DWORD),
                      ('Min',ctypes.c_size_t),('Max',ctypes.c_size_t),('Active',wintypes.DWORD),
                      ('Affinity',ctypes.c_size_t),('Priority',wintypes.DWORD),('Scheduling',wintypes.DWORD)]
        class Info(ctypes.Structure):
            _fields_=[('Basic',Basic),('IO',ctypes.c_uint64*6),('ProcessMemory',ctypes.c_size_t),
                      ('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]
        kernel=ctypes.windll.kernel32
        kernel.CreateJobObjectW.restype=wintypes.HANDLE
        kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
        kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        self.handle=kernel.CreateJobObjectW(None,None)
        info=Info();info.Basic.Flags=0x2000
        if not self.handle or not kernel.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            raise RuntimeError('Cannot create owned-process Windows Job Object')
        self.children=[];self.logs=[]

    def launch(self,command,name,env=None,cwd=ROOT):
        log=(STATE/(name+'.log')).open('ab');self.logs.append(log)
        child=subprocess.Popen(list(map(str,command)),cwd=cwd,env=env or clean_env(),stdout=log,stderr=subprocess.STDOUT,creationflags=CREATE)
        self.children.append(child)
        if not ctypes.windll.kernel32.AssignProcessToJobObject(self.handle,int(child._handle)):
            child.terminate();child.wait();raise RuntimeError('Cannot contain owned child process')
        return child

    def close(self):
        ctypes.windll.kernel32.CloseHandle(self.handle)
        for child in self.children:
            try: child.wait(timeout=15)
            except subprocess.TimeoutExpired: raise RuntimeError('Owned child did not exit')
        for log in self.logs:log.close()


def sql(config,secrets_,query,root=False):
    import pymysql
    return pymysql.connect(host='127.0.0.1',port=config['dbPort'],user='root' if root else config['dbUser'],
        password=secrets_['rootPassword' if root else 'dbPassword'],database=None if root else config['schema'],
        charset='utf8mb4',autocommit=True,connect_timeout=3)


def db_command(config,secret,query,expired=False):
    mysql=runtime('mysql').parent/'mysql.exe'
    env=clean_env();env['MYSQL_PWD']=secret;env['MYSQL_TEST_LOGIN_FILE']=str(STATE/'absent-login.cnf')
    command=[str(mysql),'--no-defaults','--protocol=TCP','-h127.0.0.1','-P'+str(config['dbPort']),'-uroot','--default-character-set=utf8mb4']
    if expired:command.append('--connect-expired-password')
    result=subprocess.run(command,input=query.encode('utf-8'),env=env,capture_output=True,creationflags=CREATE)
    if result.returncode:
        raise RuntimeError('Private database configuration command failed; data retained. No SQL or credentials logged.')


def mysql_config(config):
    base=runtime('mysql').parent.parent
    settings={'basedir':base.as_posix(),'datadir':(mysql_home()/'data').as_posix(),'port':config['dbPort'],
              'bind-address':'127.0.0.1','mysqlx':'OFF','default-time-zone':'+00:00',
              'local-infile':'OFF','secure-file-priv':'NULL','log-error':(mysql_home()/'mysql.log').as_posix(),
              'innodb-buffer-pool-size':'64M'}
    (mysql_home()/'my.ini').write_text('[mysqld]\n'+'\n'.join(f'{k}="{v}"' for k,v in settings.items())+'\n',encoding='ascii')


def start_mysql(job,config,secret,initial=False):
    mysql_config(config)
    child=job.launch([runtime('mysql'),'--defaults-file='+str(mysql_home()/'my.ini')],'mysql-console')
    for _ in range(180):
        if child.poll() is not None:raise RuntimeError('Owned MySQL failed; inspect '+str(mysql_home()/'mysql.log')+' and state/mysql-console.log; check Microsoft VC++ x64 runtime. Do not remove data or reuse another server.')
        try:
            if initial:
                with socket.create_connection(('127.0.0.1',config['dbPort']),timeout=1):break
            else:
                with sql(config,secret,'',root=True) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT @@datadir,@@server_uuid')
                        directory,identity=cursor.fetchone()
                        if Path(directory).resolve()!=(mysql_home()/'data').resolve() or identity!=config['serverUuid']:
                            raise RuntimeError('Owned database identity mismatch')
                break
        except (OSError,Exception) as error:
            if isinstance(error,RuntimeError):raise
            time.sleep(.4)
    else:raise RuntimeError('Owned MySQL readiness timeout; inspect '+str(mysql_home()/'mysql.log'))
    return child


def start_java(job,config,secret,bootstrap=False):
    env=clean_env()
    native_tmp=mysql_home()/'j'
    native_tmp.mkdir(exist_ok=True)
    env.update(DB_URL=f'jdbc:mysql://127.0.0.1:{config["dbPort"]}/{config["schema"]}?connectionTimeZone=UTC',
               DB_USER=config['dbUser'],DB_PASSWORD=secret['dbPassword'],
               COMMUTE_PYTHON=str(runtime('python')),COMMUTE_BRIDGE=str(ROOT/'app/scripts/windows_bridge_entry.py'),
               COMMUTE_PRIVATE_ROOT=str(STATE/'uploads'),COMMUTE_UPLOAD_TMP=str(STATE/'multipart'))
    if bootstrap:
        for role in ('ADMIN','READER'):
            env['COMMUTE_BOOTSTRAP_'+role+'_USER']=secret[role]['username']
            env['COMMUTE_BOOTSTRAP_'+role+'_PASSWORD']=secret[role]['password']
    child=job.launch([runtime('java'),'-Djdk.net.unixdomain.tmpdir='+str(native_tmp),'-Dloader.path='+str(RUNTIME/'backend-libs'),'-cp',ROOT/'app/backend/application.jar',
        'org.springframework.boot.loader.launch.PropertiesLauncher','--server.address=127.0.0.1','--server.port='+str(config['apiPort'])],
        'backend',env=env,cwd=ROOT/'app')
    for _ in range(180):
        if child.poll() is not None:raise RuntimeError('Backend startup failed; inspect state/backend.log. Flyway was not bypassed.')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{config["apiPort"]}/api/v1/cities',timeout=2) as response:
                if response.status==200:
                    if bootstrap:
                        with sql(config,secret,'') as connection:
                            with connection.cursor() as cursor:
                                cursor.execute('SELECT username,role FROM app_user WHERE enabled=TRUE')
                                if set(cursor.fetchall())!={(secret[r]['username'],r) for r in ('ADMIN','READER')}:
                                    time.sleep(.2);continue
                    return child
        except Exception:time.sleep(.4)
    raise RuntimeError('Backend business readiness timeout; inspect state/backend.log')


def shutdown_mysql(config,secret):
    command=[runtime('mysql').parent/'mysqladmin.exe','--no-defaults','--protocol=TCP','-h127.0.0.1',
             '-P'+str(config['dbPort']),'-uroot','shutdown']
    env=clean_env();env['MYSQL_PWD']=secret['rootPassword'];env['MYSQL_TEST_LOGIN_FILE']=str(STATE/'absent-login.cnf')
    subprocess.run(list(map(str,command)),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,creationflags=CREATE)


def setup():
    verify()
    with exclusive():
        if (STATE/'instance.json').exists():
            if read(STATE/'instance.json').get('initialized'):
                print('Already configured. Existing data and credentials retained. Use START.bat.');return
            raise RuntimeError('Prior setup was incomplete. Data retained. Inspect state logs; use a new extraction directory to retry safely.')
        progress=STATE/'setup-progress.json'
        identity=read(ROOT/'BUILD.json')['thinJarSha256']
        if (STATE/'mysql-location.json').exists():
            location=read(STATE/'mysql-location.json')
            if (not progress.exists() or read(progress)!=dict(phase='components',applicationJar=identity)
                or not location.get('owned') or (Path(location['directory'])/'data').exists()):
                raise RuntimeError('Unrecognized existing data directory; refusing initialization. Data retained.')
        write(progress,dict(phase='components',applicationJar=identity))
        install_components()
        config=dict(initialized=False,schemas={name:'commute_'+secrets.token_hex(8) for name in ('model','warehouse')},dbUser='app_'+secrets.token_hex(8),
                    dbPort=free_port(),apiPort=free_port(),webPort=free_port(),package=read(ROOT/'BUILD.json')['applicationSource'],
                    applicationJar=read(ROOT/'BUILD.json')['thinJarSha256'])
        secret=dict(rootPassword=secrets.token_hex(24),dbPassword=secrets.token_hex(24),
                    ADMIN=dict(username='demo-admin',password=secrets.token_urlsafe(24)),
                    READER=dict(username='demo-reader',password=secrets.token_urlsafe(24)))
        write(STATE/'instance.json',config)
        (STATE/'secrets.dpapi').write_bytes(protect(json.dumps(secret).encode()))
        for name in ('uploads','multipart'): (STATE/name).mkdir()
        ports_available(config);mysql_config(config)
        initialize_job=Job()
        try:
            initializer=initialize_job.launch([runtime('mysql'),'--defaults-file='+str(mysql_home()/'my.ini'),'--initialize'],'initialize')
            initialize_code=initializer.wait(timeout=180)
        finally:initialize_job.close()
        if initialize_code:raise RuntimeError('MySQL initialization failed; see '+str(mysql_home()/'mysql.log')+' and state/initialize.log; check Microsoft VC++ x64 runtime. No old directory was overwritten.')
        import re
        match=re.search(r'A temporary password is generated for root@localhost: (\S+)',(mysql_home()/'mysql.log').read_text(encoding='utf-8',errors='replace'))
        if not match:raise RuntimeError('Cannot locate initial MySQL credential in private log')
        job=Job()
        try:
            start_mysql(job,config,secret,initial=True)
            db_command(config,match[1],"ALTER USER 'root'@'localhost' IDENTIFIED BY '"+secret['rootPassword']+"';",expired=True)
            db_command(config,secret['rootPassword'],f"CREATE USER '{config['dbUser']}'@'localhost' IDENTIFIED BY '{secret['dbPassword']}';")
            with sql(config,secret,'',root=True) as connection:
                with connection.cursor() as cursor:cursor.execute('SELECT @@server_uuid');config['serverUuid']=cursor.fetchone()[0]
            counts={};config['seedSha256']={}
            for scenario,schema in config['schemas'].items():
                config['schema']=schema
                grant=schema.replace('_',r'\_')
                db_command(config,secret['rootPassword'],f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;\n"
                    f"GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,REFERENCES ON `{grant}`.* TO '{config['dbUser']}'@'localhost';")
                backend=start_java(job,config,secret,bootstrap=True)
                seed=read(ROOT/('database/'+scenario+'-seed.json'))
                if tuple(seed['tables'])!=TABLES or seed['sourceType']!='synthetic_test':raise RuntimeError('Unexpected seed scope')
                with sql(config,secret,'') as connection:
                    connection.autocommit(False)
                    try:
                        with connection.cursor() as cursor:
                            for table in TABLES:
                                cursor.execute('SELECT COUNT(*) FROM `'+table+'`')
                                if cursor.fetchone()[0]:raise RuntimeError('Demo target is not empty; refusing seed import')
                            for table,data in seed['tables'].items():
                                columns=data['columns']
                                if not all(re.fullmatch('[a-z][a-z0-9_]*',c) for c in columns):raise RuntimeError('Unsafe seed column')
                                if data['rows']:
                                    cursor.executemany('INSERT INTO `'+table+'` ('+','.join('`'+c+'`' for c in columns)+') VALUES ('+','.join(['%s']*len(columns))+')',data['rows'])
                        connection.commit()
                    except Exception:connection.rollback();raise
                backend.terminate();backend.wait(timeout=20)
                counts[scenario]={t:len(d['rows']) for t,d in seed['tables'].items()}
                config['seedSha256'][scenario]=sha(ROOT/('database/'+scenario+'-seed.json'))
            config['initialized']=True
            write(STATE/'instance.json',config)
            write(progress,dict(phase='complete',applicationJar=identity))
            write(STATE/'setup-result.json',dict(passed=True,newOwnedDatabase=True,oldDatabasesAccessed=False,
                seedSha256=config['seedSha256'],tables=counts,accounts='unique random passwords; current-user DPAPI'))
            print('First setup complete. Run CREDENTIALS.bat privately, then START.bat.',flush=True)
        finally:
            try:shutdown_mysql(config,secret)
            finally:job.close()


def handler(config):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'app/frontend'),**kwargs)
        def log_message(self,*args):pass
        def list_directory(self,path):self.send_error(404);return None
        def dispatch(self):
            # Block DNS rebinding and cross-origin browser writes before proxying.
            host=self.headers.get('Host','')
            expected='127.0.0.1:'+str(config['webPort'])
            if host!=expected or self.headers.get('Origin') not in (None,'http://'+expected):
                self.send_error(403);return
            if self.path.startswith(('/api/','/health')):
                try:length=int(self.headers.get('Content-Length','0'))
                except ValueError:self.send_error(400);return
                if self.headers.get('Transfer-Encoding') or not 0<=length<=3*1024*1024:
                    self.send_error(413);return
                connection=http.client.HTTPConnection('127.0.0.1',config['apiPort'],timeout=60)
                try:
                    headers={k:v for k,v in self.headers.items() if k.lower() not in ('connection','host','transfer-encoding','upgrade')}
                    headers['Host']='127.0.0.1:'+str(config['apiPort'])
                    body=self.rfile.read(length)
                    connection.request(self.command,self.path,body,headers)
                    response=connection.getresponse();data=response.read()
                    self.send_response(response.status)
                    for k,v in response.getheaders():
                        if k.lower() not in ('connection','transfer-encoding','content-length'):self.send_header(k,v)
                    self.send_header('Content-Length',str(len(data)));self.end_headers()
                    if self.command!='HEAD':self.wfile.write(data)
                except (OSError,http.client.HTTPException):self.send_error(502,'Backend unavailable; inspect private state/backend.log')
                finally:connection.close()
            elif self.command in ('GET','HEAD'):
                super().do_HEAD() if self.command=='HEAD' else super().do_GET()
            else:self.send_error(405)
        do_GET=do_HEAD=do_POST=do_PUT=do_DELETE=do_PATCH=do_OPTIONS=do_TRACE=dispatch
    return Handler


def supervise(scenario='model'):
    with exclusive():
        verify();config=read(STATE/'instance.json');secret=credentials()
        if not config.get('initialized'):raise RuntimeError('First setup is incomplete')
        if config['applicationJar']!=read(ROOT/'BUILD.json')['thinJarSha256']:
            raise RuntimeError('Application version changed. In-place migration is not supported; back up state and extract a new copy.')
        config['schema']=config['schemas'][scenario]
        if config['seedSha256'][scenario]!=sha(ROOT/('database/'+scenario+'-seed.json')):
            raise RuntimeError('Seed version changed; in-place upgrade is not supported. Back up existing state and use a new extraction.')
        ports_available(config)
        job=Job();server=None
        try:
            start_mysql(job,config,secret)
            start_java(job,config,secret)
            server=ThreadingHTTPServer(('127.0.0.1',config['webPort']),handler(config))
            server.daemon_threads=True;threading.Thread(target=server.serve_forever,daemon=True).start()
            write(STATE/'running.json',dict(pid=os.getpid(),url=f'http://127.0.0.1:{config["webPort"]}',
                 children=[c.pid for c in job.children],ready=True,scenario=scenario))
            while not (STATE/'stop.request').exists():
                if any(c.poll() is not None for c in job.children):raise RuntimeError('Owned service exited; inspect private logs')
                time.sleep(.25)
        finally:
            if server:server.shutdown();server.server_close()
            try:shutdown_mysql(config,secret)
            finally:
                job.close()
                write(STATE/'stopped.json',dict(ownedChildrenStopped=True,at=time.time()))
                (STATE/'running.json').unlink(missing_ok=True)


def upgrade():
    """Back up both owned schemas before running new Flyway migrations; never reseed."""
    verify()
    with exclusive():
        config=read(STATE/'instance.json');secret=credentials()
        if not config.get('initialized'):raise RuntimeError('Incomplete initialization; data retained.')
        identity=read(ROOT/'BUILD.json')['thinJarSha256']
        if config['applicationJar']==identity:return
        if (STATE/'upgrade-pending.json').exists():
            raise RuntimeError('An earlier migration was interrupted. Restore the private backup before retrying; no automatic overwrite.')
        ports_available(config)
        backup=STATE/'backups'/('before-upgrade-'+str(time.time_ns()))
        backup.mkdir(parents=True);private_directory(backup)
        write(backup/'instance.json',config)
        job=Job()
        try:
            start_mysql(job,config,secret)
            env=clean_env();env['MYSQL_PWD']=secret['rootPassword'];env['MYSQL_TEST_LOGIN_FILE']=str(STATE/'absent-login.cnf')
            dump=backup/'databases.sql'
            with dump.open('wb') as stream:
                result=subprocess.run([str(runtime('mysql').parent/'mysqldump.exe'),'--no-defaults','--protocol=TCP',
                    '-h127.0.0.1','-P'+str(config['dbPort']),'-uroot','--single-transaction','--routines','--events','--triggers',
                    '--set-gtid-purged=OFF','--databases',*config['schemas'].values()],env=env,stdout=stream,
                    stderr=subprocess.PIPE,creationflags=CREATE,timeout=180)
            if result.returncode or not dump.stat().st_size:raise RuntimeError('Upgrade backup failed; migrations not started.')
            write(backup/'receipt.json',dict(sha256=sha(dump),bytes=dump.stat().st_size,previousJar=config['applicationJar'],nextJar=identity))
            write(STATE/'upgrade-pending.json',dict(backup=str(backup),nextJar=identity))
            for schema in config['schemas'].values():
                config['schema']=schema
                backend=start_java(job,config,secret)
                backend.terminate();backend.wait(timeout=20)
            config['applicationJar']=identity;config['package']=read(ROOT/'BUILD.json')['applicationSource']
            write(STATE/'instance.json',config)
            (STATE/'upgrade-pending.json').unlink()
            write(STATE/'upgrade-result.json',dict(passed=True,backup=str(backup),reseeded=False,applicationJar=identity))
        finally:
            try:shutdown_mysql(config,secret)
            finally:job.close()


def start(scenario='model'):
    verify()
    if not (STATE/'instance.json').exists():raise RuntimeError('Run FIRST-SETUP.bat first.')
    # Check lock without changing live state; supervisor takes the same lock.
    with exclusive():
        (STATE/'stop.request').unlink(missing_ok=True)
    (STATE/'running.json').unlink(missing_ok=True)
    with (STATE/'supervisor.log').open('ab') as log:
        child=subprocess.Popen([sys.executable,'-I',str(Path(__file__)),'supervise','--scenario',scenario],cwd=ROOT,env=clean_env(),
            stdout=log,stderr=subprocess.STDOUT,creationflags=CREATE|subprocess.CREATE_NEW_PROCESS_GROUP)
    for _ in range(240):
        if child.poll() is not None:raise RuntimeError('Startup failed; inspect state/supervisor.log and service logs. No unknown process was stopped.')
        if (STATE/'running.json').exists():
            print('Ready: '+read(STATE/'running.json')['url']);return
        time.sleep(.5)
    # Ask this instance to stop; never terminate a PID from an old state file.
    (STATE/'stop.request').touch()
    raise RuntimeError('Startup timed out; stop requested. Inspect state logs before retrying.')


def stop():
    if not STATE.exists():print('Not configured; nothing to stop.');return
    (STATE/'stop.request').touch()
    for _ in range(160):
        try:
            with exclusive():
                print('Stopped. Persistent data retained.');return
        except RuntimeError:time.sleep(.25)
    raise RuntimeError('Stop still pending. Inspect owned logs. No PID-based termination was attempted.')


def check():
    verify()
    if os.name!='nt' or ctypes.sizeof(ctypes.c_void_p)!=8:raise RuntimeError('Only Windows x64 is supported')
    free=shutil.disk_usage(ROOT).free
    if free<3*1024**3:raise RuntimeError('Need at least 3 GiB free space for first setup.')
    print(json.dumps(dict(platform=sys.getwindowsversion().build,architecture='x64',freeGiB=round(free/1024**3,2),
        pathLength=len(str(ROOT)),configured=(STATE/'instance.json').exists(),globalInstallsRequired=False,
        firstSetupNetwork=not OFFLINE),indent=2))
    if len(str(ROOT))>100:raise RuntimeError('Extract under a shorter writable path (under 100 characters); do not change global long-path policy.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['setup','start','stop','supervise','check','credentials','upgrade'])
    parser.add_argument('--scenario',choices=['model','warehouse'],default='model')
    args=parser.parse_args()
    try:
        if DESKTOP and os.environ.get('UC_PARENT_PID'):
            # Kernel handles identify the original parent even if Windows reuses its PID.
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.restype=wintypes.HANDLE
            kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
            kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
            parent=kernel.OpenProcess(0x00100000,False,int(os.environ['UC_PARENT_PID']))
            if not parent:raise RuntimeError('Desktop parent no longer exists; services not started.')
            def parent_watch():
                kernel.WaitForSingleObject(parent,0xFFFFFFFF)
                os._exit(71)  # Closing our Job handles contains all owned service children.
            threading.Thread(target=parent_watch,daemon=True).start()
        if OFFLINE:
            # Process-local guard: offline package code cannot open a remote
            # connection even if a future component path accidentally requests it.
            def offline_guard(event,arguments):
                if event=='socket.connect':
                    address=arguments[1]
                    if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','::1'):
                        raise RuntimeError('Offline mode forbids non-loopback network connections')
                if event=='socket.getaddrinfo' and arguments[0] not in ('127.0.0.1','::1',None):
                    raise RuntimeError('Offline mode forbids external DNS resolution')
            sys.addaudithook(offline_guard)
        if args.action=='credentials':
            s=credentials()
            for role in ('ADMIN','READER'):print(role+': '+s[role]['username']+' / '+s[role]['password'])
        elif args.action in ('start','supervise'):globals()[args.action](args.scenario)
        else:globals()[args.action]()
    except Exception as error:
        # Avoid parser, SQL, HTTP bodies, and secrets in public launcher errors.
        if isinstance(error,RuntimeError):print('ERROR: '+str(error),file=sys.stderr)
        elif isinstance(error,ModuleNotFoundError):print('ERROR: Portable module missing: '+str(error.name)+'. Data retained; extract a fresh package.',file=sys.stderr)
        else:print('ERROR: '+type(error).__name__+'. See private state logs; data retained.',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':sys.exit(main())
