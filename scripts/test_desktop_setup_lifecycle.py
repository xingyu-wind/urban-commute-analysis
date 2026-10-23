"""Real installer-only checks, kept separate from the blocked Electron window.

Only the explicitly named workspace test install is changed. Existing task-owned
demo databases are fingerprinted before/after; GUI-driven upgrades are not claimed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from test_desktop_installer import fingerprint

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',required=True,type=Path)
    p.add_argument('--installation',required=True,type=Path)
    p.add_argument('--application',required=True,type=Path)
    p.add_argument('--data',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();exe=a.exe.resolve();installation=a.installation.resolve();data=a.data.resolve();out=a.output.resolve()
    assert installation.is_relative_to(ROOT/'dist') and data.is_relative_to(ROOT/'dist')
    assert not (installation/'UrbanCommute.exe').exists(),'Use this after the first recorded uninstall'
    out.mkdir(parents=True,exist_ok=False);checks=[];passed=False
    def run(label,args):
        with (out/(label+'.log')).open('wb') as log:
            r=subprocess.run(list(map(str,args)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        checks.append(dict(check=label,exitCode=r.returncode));print(label+' exit='+str(r.returncode),flush=True)
        assert r.returncode==0,label
    def shortcuts():
        script="""$w=New-Object -ComObject WScript.Shell; $desktop=[Environment]::GetFolderPath('Desktop'); $menu=[Environment]::GetFolderPath('StartMenu'); $paths=@((Join-Path $desktop '城市通勤演示版.lnk'),(Join-Path $menu 'Programs/城市通勤演示版/城市通勤演示版.lnk')); @($paths | ForEach-Object { $present=Test-Path -LiteralPath $_; $target=$null;if($present){$target=$w.CreateShortcut($_).TargetPath}; [pscustomobject]@{path=$_;exists=$present;target=$target}}) | ConvertTo-Json"""
        powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        import base64
        encoded=base64.b64encode(script.encode('utf-16-le')).decode()
        result=subprocess.run([str(powershell),'-NoProfile','-EncodedCommand',encoded],capture_output=True,check=True)
        # Force Unicode output through PowerShell's UTF-16-safe JSON escapes.
        try:return json.loads(result.stdout.decode('utf-8-sig'))
        except UnicodeDecodeError:return json.loads(result.stdout.decode('gbk'))
    try:
        before=fingerprint(a.application.resolve(),data)
        for label in ('reinstall-after-uninstall','same-version-overwrite'):
            run(label,[exe,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/DIR='+str(installation),'/LOG='+str(out/(label+'-setup.log'))])
            assert (installation/'UrbanCommute.exe').is_file()
            links=shortcuts();assert len(links)==2
            assert all(x['exists'] and Path(x['target']).resolve()==installation/'UrbanCommute.exe' for x in links)
            (out/(label+'-shortcuts.json')).write_text(json.dumps(links,ensure_ascii=False,indent=2),encoding='utf-8')
            checks.append(dict(check=label+'-desktop-and-startmenu-targets',passed=True))
        run('final-uninstall',[installation/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(out/'final-uninstaller.log')])
        for _ in range(100):
            if not (installation/'UrbanCommute.exe').exists():break
            time.sleep(.2)
        assert not (installation/'UrbanCommute.exe').exists()
        assert all(not x['exists'] for x in shortcuts()),'Shortcut cleanup failed'
        after=fingerprint(a.application.resolve(),data)
        assert before==after,'Existing task-owned data changed during installer lifecycle'
        (out/'retained-data-fingerprint.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
        checks.append(dict(check='program-and-shortcuts-removed-existing-isolated-database-and-credentials-retained',passed=True))
        passed=True
    finally:
        (out/'summary.json').write_text(json.dumps(dict(passed=passed,checks=checks,electronWindowVerified=False,
            crossVersionInstallerUpgradeVerified=False,existingDataScope='previous task-owned service data; Electron initialization remains blocked',
            applicationControlDisabled=False,installation=str(installation)),indent=2),encoding='utf-8')

if __name__=='__main__':main()
