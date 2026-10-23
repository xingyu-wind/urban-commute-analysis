"""Real owned service failures without deleting data or changing system settings."""
import argparse
import ctypes
from ctypes import wintypes
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();args.output.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('installed',root/'launcher/portable.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config=module.read(root/'state/instance.json');module.ports_available(config)
    assert not (root/'state/running.json').exists(),'Stop the test copy before injecting faults'
    env=dict(os.environ,URBAN_COMMUTE_NO_PAUSE='1')
    env['PATH']=os.environ['SystemRoot']+'/System32;'+os.environ['SystemRoot']+'/System32/WindowsPowerShell/v1.0'
    results=[]
    def batch(name,success,label):
        result=subprocess.run('"'+str(root/(name+'.bat'))+'"',shell=True,cwd=root,env=env,capture_output=True,timeout=180)
        (args.output/(label+'.log')).write_bytes(result.stdout+result.stderr)
        assert (result.returncode==0)==success,(label,result.returncode)
        results.append(dict(check=label,exitCode=result.returncode,expectedSuccess=success))
    def released():
        for _ in range(100):
            try:module.ports_available(config);return
            except RuntimeError:time.sleep(.2)
        raise AssertionError('Owned ports not released after failure')
    native=module.mysql_home()
    # Deny sharing of the private log handle for this test only. MySQL must fail
    # opening its error log; no database files are renamed or removed.
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateFileW(str(native/'mysql.log'),0x80000000,1,None,3,0,None)
    assert handle not in (None,ctypes.c_void_p(-1).value),'Cannot hold owned MySQL log'
    try:
        batch('START',False,'mysql-log-sharing-failure');released()
    finally:kernel.CloseHandle(handle)
    # MySQL can start, then Java fails at its owned temp directory; cleanup must
    # still shut down MySQL and release every owned listener.
    temporary=native/'j';backup=native/'j.t3-preserved'
    assert temporary.is_dir() and not backup.exists()
    temporary.rename(backup)
    try:
        temporary.write_text('intentional T3 owned path collision',encoding='ascii')
        batch('START',False,'java-temp-path-failure');released()
    finally:
        if temporary.is_file():temporary.unlink()
        backup.rename(temporary)
    try:
        batch('START',True,'recovery-start')
    finally:batch('STOP',True,'recovery-stop')
    released()
    (args.output/'summary.json').write_text(json.dumps(dict(passed=True,checks=results,
        realMysqlFailure=True,javaFailureAfterMysqlStarted=True,ownedPortsReleased=True,dataFilesRemoved=False,
        systemSettingsChanged=False),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
