"""Fallback service acceptance when local App Control denies unsigned desktop EXEs.

This does NOT prove the installer or Electron shell works. It verifies the exact
packaged desktop payload using its bundled runtimes and a real installed browser.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from test_desktop_installer import fingerprint

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--application',type=Path,required=True)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resume',action='store_true',help='Resume only this task-owned data directory after a test-driver failure')
    args=p.parse_args();application=args.application.resolve();payload=application/'resources/payload';data=args.data.resolve();out=args.output.resolve()
    assert application.is_relative_to(ROOT/'dist') and data.is_relative_to(ROOT/'dist')
    assert args.resume or not data.exists();out.mkdir(parents=True,exist_ok=False)
    node=shutil.which('node');powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    env=dict(os.environ,UC_DATA_HOME=str(data),HTTP_PROXY='http://127.0.0.1:9',HTTPS_PROXY='http://127.0.0.1:9',
        NO_PROXY='127.0.0.1,::1,localhost',PATH=os.environ['SystemRoot']+'/System32',JAVA_HOME='Z:/absent',PYTHONPATH='Z:/absent',DB_URL='jdbc:mysql://invalid/no')
    env.pop('UC_PARENT_PID',None)
    checks=[];passed=False
    def run(label,argv,success=True,timeout=480):
        with (out/(label+'.log')).open('wb') as log:code=subprocess.run(list(map(str,argv)),cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
        checks.append(dict(check=label,exitCode=code,expectedSuccess=success));print(label+' exit='+str(code),flush=True)
        assert (code==0)==success,label
    python=data/'runtime/python/python.exe'
    def action(label,name,scenario='model',root=payload,success=True):
        run(label,[python,'-I',root/'launcher/portable.py',name,'--scenario',scenario],success=success)
    def assert_stopped():
        import socket
        config=json.loads((data/'state/instance.json').read_text())
        for port in (config['dbPort'],config['apiPort'],config['webPort']):
            with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))!=0
        assert not (data/'state/running.json').exists()
    try:
        run('first-offline-setup',[powershell,'-NoProfile','-ExecutionPolicy','Bypass','-File',payload/'launcher/bootstrap.ps1','-Action','setup','-AcceptLicenses'])
        assert not (payload/'state').exists() and not (payload/'runtime').exists()
        initial=fingerprint(application,data)
        for scenario,city,kind in [('model','s7-city','prediction'),('warehouse','s5-city','warehouse')]:
            action('start-'+scenario,'start',scenario)
            action('duplicate-start-'+scenario,'start',scenario,success=False)
            running=json.loads((data/'state/running.json').read_text(encoding='utf-8'))
            seed=json.loads((payload/'database/warehouse-seed.json').read_text(encoding='utf-8'))
            columns=seed['tables']['warehouse_release']['columns'];rows=seed['tables']['warehouse_release']['rows']
            identity=str(rows[0][columns.index('release_id')]) if rows else ''
            run('browser-'+scenario,[node,ROOT/'frontend/scripts/verify-s9.mjs',out/('browser-'+scenario),running['url'],city,kind,identity])
            action('stop-'+scenario,'stop');assert_stopped()
        assert fingerprint(application,data)==initial,'Business data changed during read-only page checks'
        # A desktop crash closes the original parent's kernel handle. The new
        # watchdog must exit its supervisor and release every owned service.
        parent=subprocess.Popen([str(python),'-I','-c','import time;time.sleep(180)'],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        watch_env=dict(env,UC_PARENT_PID=str(parent.pid))
        (data/'state/stop.request').unlink(missing_ok=True)
        (data/'state/running.json').unlink(missing_ok=True)
        with (out/'parent-watch.log').open('wb') as log:
            owned=subprocess.Popen([str(python),'-I',str(payload/'launcher/portable.py'),'supervise'],env=watch_env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                import time
                for _ in range(240):
                    if (data/'state/running.json').exists():break
                    assert owned.poll() is None,'Watchdog supervisor failed before readiness'
                    time.sleep(.25)
                assert (data/'state/running.json').exists(),'Watchdog service readiness timeout'
                parent.terminate();parent.wait(timeout=15)
                assert owned.wait(timeout=30)==71,'Parent-loss watcher did not close the supervisor'
                # Abrupt exit intentionally leaves stale running.json; startup
                # checks the live lock and recreates readiness, never trusts PIDs.
                action('recover-after-parent-exit','start');action('stop-after-parent-exit','stop');assert_stopped()
                checks.append(dict(check='desktop-parent-loss-owned-job-cleanup-and-recovery',passed=True))
            finally:
                if parent.poll() is None:parent.terminate();parent.wait(timeout=15)
                if owned.poll() is None:action('watchdog-final-stop','stop');owned.wait(timeout=60)
        # Build a test-only backend identity change without altering application classes.
        fixture=out/'upgrade-fixture';shutil.copytree(payload,fixture)
        jar=fixture/'app/backend/application.jar'
        with zipfile.ZipFile(jar,'a') as archive:archive.writestr('DESKTOP-UPGRADE-TEST.txt','identity-only upgrade fixture; not a released backend')
        build=json.loads((fixture/'BUILD.json').read_text(encoding='utf-8'))
        build['thinJarSha256']=hashlib.sha256(jar.read_bytes()).hexdigest();build['version']='1.0.1-upgrade-test'
        (fixture/'BUILD.json').write_text(json.dumps(build,indent=2),encoding='utf-8')
        files=[f for f in sorted(fixture.rglob('*')) if f.is_file() and f.name!='MANIFEST.sha256']
        (fixture/'MANIFEST.sha256').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.relative_to(fixture).as_posix()+'\n' for f in files))
        action('backup-and-migrate-changed-jar','upgrade',root=fixture)
        result=json.loads((data/'state/upgrade-result.json').read_text())
        assert result['passed'] and not result['reseeded'] and (Path(result['backup'])/'databases.sql').stat().st_size>0
        action('restart-after-upgrade','start',root=fixture);action('stop-after-upgrade','stop',root=fixture);assert_stopped()
        assert fingerprint(application,data)==initial,'Upgrade changed existing business data or accounts'
        (out/'business-fingerprint.json').write_text(json.dumps(initial,indent=2),encoding='utf-8')
        (out/'upgrade-receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        checks.append(dict(check='changed-jar-backup-flyway-restart-retained-both-databases',passed=True))
        assert not (payload/'state').exists() and not (payload/'runtime').exists()
        passed=True
    finally:
        if python.exists() and (data/'state/instance.json').exists():
            try:action('final-stop','stop');assert_stopped()
            except Exception:passed=False
        (out/'summary.json').write_text(json.dumps(dict(passed=passed,checks=checks,installerVerified=False,electronWindowVerified=False,
            cleanWindows=False,physicalNetworkDisconnected=False,unreachableProxy=True,developerPathRemoved=True,originalPayloadUnchanged=True),indent=2),encoding='utf-8')

if __name__=='__main__':main()
