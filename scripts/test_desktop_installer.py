"""Install and uninstall only the new task-owned desktop installation; preserve data."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def fingerprint(installation,data):
    os.environ['UC_DATA_HOME']=str(data)
    payload=installation/'resources/payload'
    spec=importlib.util.spec_from_file_location('desktop_owned',payload/'launcher/portable.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config=module.read(data/'state/instance.json');secret=module.credentials()
    result=dict(serverUuid=config['serverUuid'],schemas=config['schemas'],secretsSha256=module.sha(data/'state/secrets.dpapi'),tables={})
    with module.exclusive():
        job=module.Job()
        try:
            module.start_mysql(job,config,secret)
            for scenario,schema in config['schemas'].items():
                config['schema']=schema;tables={}
                with module.sql(config,secret,'') as connection:
                    with connection.cursor() as cursor:
                        for table in module.TABLES:
                            cursor.execute('SELECT * FROM `'+table+'`')
                            rows=sorted(json.dumps(row,default=str,ensure_ascii=False) for row in cursor.fetchall())
                            tables[table]=dict(rows=len(rows),sha256=hashlib.sha256('\n'.join(rows).encode()).hexdigest())
                result['tables'][scenario]=tables
        finally:
            try:module.shutdown_mysql(config,secret)
            finally:job.close()
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--installation',type=Path,required=True)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--mode',choices=['first','reinstall','uninstall','upgrade','fingerprint'],default='first')
    args=p.parse_args();out=args.output.resolve();installation=args.installation.resolve();data=args.data.resolve()
    assert installation.is_relative_to(ROOT/'dist') and data.is_relative_to(ROOT/'dist'),'Only task-owned test paths are permitted'
    out.mkdir(parents=True,exist_ok=False)
    checks=[];passed=False
    def command(label,argv,timeout=900):
        with (out/(label+'.log')).open('wb') as log:
            code=subprocess.run(list(map(str,argv)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
        checks.append(dict(check=label,exitCode=code))
        if code:raise RuntimeError(label+' failed; inspect '+str(out/(label+'.log')))
    try:
        if args.mode=='uninstall':
            before=fingerprint(installation,data)
            command('uninstall',[installation/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(out/'uninstaller.log')])
            for _ in range(100):
                if not (installation/'UrbanCommute.exe').exists():break
                time.sleep(.2)
            assert not (installation/'UrbanCommute.exe').exists(),'Application EXE still exists'
            assert (data/'state/instance.json').exists() and (data/'state/secrets.dpapi').exists()
            (out/'preserved-identity.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
            checks.append(dict(check='uninstalled-program-kept-user-data',passed=True))
        elif args.mode=='fingerprint':
            (out/'fingerprint.json').write_text(json.dumps(fingerprint(installation,data),indent=2),encoding='utf-8')
        else:
            if args.mode=='first':assert not installation.exists() and not data.exists(),'New directories required'
            command('install',[args.exe.resolve(),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/DIR='+str(installation),'/LOG='+str(out/'installer.log')])
            assert (installation/'UrbanCommute.exe').is_file()
            command('desktop-browser',['node',ROOT/'frontend/scripts/verify-desktop.mjs',installation,data,out/'window',args.mode])
            (out/'fingerprint.json').write_text(json.dumps(fingerprint(installation,data),indent=2),encoding='utf-8')
        passed=True
    finally:
        (out/'summary.json').write_text(json.dumps(dict(passed=passed,mode=args.mode,checks=checks,installation=str(installation),data=str(data),cleanWindows=False),indent=2),encoding='utf-8')

if __name__=='__main__':main()
