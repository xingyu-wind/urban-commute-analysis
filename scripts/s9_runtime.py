"""Loopback single-machine candidate deployment. Own and stop only our child processes.

Prerequisites: built JAR/dist, Java21, Node24, installed project dependencies,
authorized DB_URL/DB_USER/DB_PASSWORD. Startup applies/validates Flyway V1-V6.
No service installation, data cleanup, port-owner termination or HDFS formatting.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); return sock.getsockname()[1]

def preflight():
    files={'jar':ROOT/'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar',
           'dist':ROOT/'frontend/dist/index.html','vite':ROOT/'frontend/node_modules/vite/bin/vite.js'}
    versions={}
    for name,arguments in (('java',['java','-version']),('node',['node','--version'])):
        if shutil.which(name):
            result=subprocess.run(arguments,capture_output=True,text=True,timeout=10)
            versions[name]=(result.stdout+result.stderr).strip()
    return dict(files={k:p.is_file() for k,p in files.items()},versions=versions,
        commands={k:bool(shutil.which(k)) for k in ('java','node','docker','hdfs','hive')},
        python=__import__('sys').version.split()[0],databaseVariables={k:bool(os.environ.get(k)) for k in ('DB_URL','DB_USER','DB_PASSWORD')},
        binding='127.0.0.1',hiveMode='existing isolated CI; no local service created')

@contextmanager
def services(output, env=None):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ if env is None else env)
    if not all(env.get(k) for k in ('DB_URL','DB_USER','DB_PASSWORD')):
        raise RuntimeError('Set authorized private database process environment first')
    api,web=port(),port()
    children=[]; logs=[]
    try:
        for name,command,cwd,child_env,url in (
            ('java',['java','-jar',str(ROOT/'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar'),
                     '--server.address=127.0.0.1','--server.port='+str(api)],ROOT,env,f'http://127.0.0.1:{api}/health'),
            ('web',['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'preview','--host','127.0.0.1','--port',str(web),'--strictPort'],
             ROOT/'frontend',{**env,'DEV_BACKEND_URL':f'http://127.0.0.1:{api}'},f'http://127.0.0.1:{web}/')):
            log=(output/(name+'.log')).open('x',encoding='utf-8'); logs.append(log)
            child=subprocess.Popen(command,cwd=cwd,env=child_env,stdout=log,stderr=subprocess.STDOUT); children.append(child)
            for _ in range(180):
                if child.poll() is not None: raise RuntimeError(name+' startup failed; inspect owned log')
                try:
                    with urllib.request.urlopen(url,timeout=1) as response:
                        if response.status==200: break
                except Exception: time.sleep(.25)
            else: raise RuntimeError(name+' readiness timed out')
        (output/'runtime.json').write_text(json.dumps(dict(api=f'http://127.0.0.1:{api}',web=f'http://127.0.0.1:{web}',
            productionBundle=True,loopback=True,pids=[c.pid for c in children]),indent=2)+'\n',encoding='utf-8')
        yield f'http://127.0.0.1:{web}'
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=15)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=10)
        for log in logs: log.close()
        (output/'stopped.json').write_text(json.dumps(dict(ownedChildrenStopped=all(c.poll() is not None for c in children)))+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.check: print(json.dumps(preflight(),indent=2)); return
    if args.output is None: parser.error('--output is required for serving')
    try:
        with services(args.output) as url:
            print('Candidate ready: '+url+' ; Ctrl+C stops owned web/Java children',flush=True)
            while True: time.sleep(1)
    except KeyboardInterrupt: pass

if __name__=='__main__': main()
