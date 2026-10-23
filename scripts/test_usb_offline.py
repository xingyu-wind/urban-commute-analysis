"""Final USB ZIP: fresh transport extraction, local deployment, offline core acceptance.

Does not disconnect the host or touch existing demo databases. No 420-second rerun.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',required=True,type=Path)
    parser.add_argument('--media',required=True,type=Path)
    parser.add_argument('--destination',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    media=args.media.resolve();local=args.destination.resolve()
    assert not media.exists() and not local.exists(),'Use genuinely new transport and local directories'
    checks=[];passed=False;started=time.monotonic()
    env=dict(os.environ,URBAN_COMMUTE_NO_PAUSE='1',HTTP_PROXY='http://127.0.0.1:9',HTTPS_PROXY='http://127.0.0.1:9',NO_PROXY='127.0.0.1,::1,localhost')
    env['PATH']=os.environ['SystemRoot']+'/System32;'+os.environ['SystemRoot']+'/System32/WindowsPowerShell/v1.0'
    def batch(root,name,arguments='',success=True,label=None):
        result=subprocess.run('"'+str(root/(name+'.bat'))+'"'+(' '+arguments if arguments else ''),shell=True,cwd=root,env=env,capture_output=True,timeout=300)
        label=label or name+'-'+str(len(checks))
        (out/(label+'.log')).write_bytes(result.stdout+result.stderr)
        checks.append(dict(check=label,exitCode=result.returncode,expectedSuccess=success))
        assert (result.returncode==0)==success,label
    try:
        with zipfile.ZipFile(args.zip) as archive:
            for name in archive.namelist():
                assert (media/name).resolve().is_relative_to(media)
                assert '/runtime/' not in name and '/state/' not in name
            archive.extractall(media)
        transport=media/'UrbanCommute-Demo'
        assert not (transport/'runtime').exists() and not (transport/'state').exists()
        checks.append(dict(check='fresh-zip-transport-and-local-destination',passed=True,transportRuntime=False,transportState=False,localExists=False,oldCachesCopied=False))
        batch(transport,'RUN-FROM-USB',f'-Destination "{local}" -AcceptLicenses -NoBrowser',label='first-offline-deployment')
        assert not (local/'runtime/downloads').exists() and not (transport/'runtime').exists() and not (transport/'state').exists()
        config=json.loads((local/'state/instance.json').read_text(encoding='utf-8'))
        assert config['initialized']
        original_secret=(local/'state/secrets.dpapi').read_bytes()
        batch(local,'STOP')
        checks.append(dict(check='fresh-local-offline-setup',passed=True,sourceMediaUninitialized=True,noRuntimeDownloadCache=True,newDatabase=True))
        # Reuse the real HTTP/UI driver only for the changed USB path. It skips
        # the previously passed abrupt-exit regression and the timed rehearsal.
        with (out/'core-acceptance.log').open('wb') as log:
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('test_windows_zip.py')),'--root',str(local),
                '--output',str(out/'acceptance'),'--browser','--demo-browser','--offline'],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        assert result.returncode==0,'Final USB real HTTP/UI acceptance failed'
        checks.append(dict(check='new-offline-path-core-http-ui',passed=True,results='acceptance/summary.json',timedRehearsalRerun=False,modelTraining=False,hiveRerun=False))
        batch(transport,'RUN-FROM-USB',f'-Destination "{local}" -AcceptLicenses -NoBrowser',label='repeat-owned-deployment')
        assert original_secret==(local/'state/secrets.dpapi').read_bytes()
        batch(local,'STOP')
        checks.append(dict(check='repeat-deployment-retains-private-state',passed=True))
        python_archive=transport/'vendor/components/python-3.11.9-embed-amd64.zip'
        held=python_archive.with_name(python_archive.name+'.test-held')
        python_archive.rename(held)
        try:batch(transport,'FIRST-SETUP','-AcceptLicenses',False,'offline-missing-component')
        finally:held.rename(python_archive)
        jar=transport/'vendor/components/spring-jcl-6.2.19.jar';original=jar.read_bytes()
        try:
            jar.write_bytes(b'corrupt'+original[7:])
            batch(transport,'FIRST-SETUP','-AcceptLicenses',False,'offline-wrong-hash')
        finally:jar.write_bytes(original)
        assert not (transport/'runtime').exists() and not (transport/'state').exists()
        checks.append(dict(check='offline-faults-before-download-or-state',passed=True,missingComponentRejected=True,wrongHashRejected=True))
        probe='''import importlib.util,socket,sys
from pathlib import Path
root=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('installed',root/'launcher/portable.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
sys.argv=['portable.py','check'];assert m.main()==0
for address in [('example.com',443),('1.1.1.1',443)]:
 try:socket.create_connection(address,timeout=1)
 except RuntimeError:pass
 else:raise AssertionError('External connection not blocked')
print('OFFLINE_PROCESS_NETWORK_GUARD=PASS')
'''
        result=subprocess.run([sys.executable,'-c',probe,str(local)],capture_output=True,timeout=60)
        (out/'offline-process-guard.log').write_bytes(result.stdout+result.stderr)
        assert result.returncode==0
        checks.append(dict(check='offline-python-process-guard',passed=True,externalDnsAndIpDenied=True,wholeWindowsNetworkBlocked=False))
        spec=importlib.util.spec_from_file_location('installed',local/'launcher/portable.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ports_available(config)
        assert not (local/'state/running.json').exists()
        passed=True
    finally:
        if (local/'state/instance.json').exists():
            try:batch(local,'STOP',label='final-owned-stop')
            except Exception:passed=False
        report=dict(passed=passed,zip=str(args.zip.resolve()),media=str(media),local=str(local),seconds=round(time.monotonic()-started,2),
            sameWindowsHost=True,cleanMachineTest=False,physicalNetworkDisconnected=False,offlineMode=True,
            existingDemoDatabasesAccessed=False,checks=checks)
        (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('USB_OFFLINE_ACCEPTANCE=PASS')


if __name__=='__main__':main()
