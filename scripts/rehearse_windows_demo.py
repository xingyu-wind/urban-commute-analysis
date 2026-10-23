"""Paced seven-minute rehearsal against the installed ZIP, with real HTTP and UI.

No generated responses. Timings include narration windows, not performance claims.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    repository=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('installed',root/'launcher/portable.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    secret=module.credentials();checks=[];start=time.monotonic()
    env=dict(os.environ,URBAN_COMMUTE_NO_PAUSE='1')
    env['PATH']=os.environ['SystemRoot']+'/System32;'+os.environ['SystemRoot']+'/System32/WindowsPowerShell/v1.0'
    def save():
        (out/'timeline.json').write_text(json.dumps(dict(elapsedSeconds=round(time.monotonic()-start,2),checks=checks),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def stage(at,name):
        if time.monotonic()-start>at+45:raise AssertionError('Rehearsal exceeded stage budget: '+name)
        while time.monotonic()-start<at:time.sleep(min(1,max(0,at-(time.monotonic()-start))))
        checks.append(dict(stage=name,seconds=round(time.monotonic()-start,2)));save();print(name,flush=True)
    def batch(name):
        with (out/(name+'-'+str(len(checks))+'.log')).open('wb') as log:
            result=subprocess.run('"'+str(root/(name+'.bat'))+'"',shell=True,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        assert result.returncode==0,name
    def base():return module.read(root/'state/running.json')['url']
    def get(path):
        with urllib.request.urlopen(base()+path,timeout=30) as response:
            assert response.status==200
            result=json.load(response)
        checks.append(dict(method='GET',path=path,status=200,seconds=round(time.monotonic()-start,2)));save();return result
    def browser(script,arguments,stdin=None):
        with (out/(script+'.log')).open('wb') as log:
            result=subprocess.run([shutil.which('node'),str(repository/'frontend/scripts'/script),*arguments],cwd=repository,
                input=stdin,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        assert result.returncode==0,script
    try:
        stage(0,'startup-health-source');batch('START');get('/health');cities=get('/api/v1/cities')
        assert cities['data']
        stage(45,'city-statistics-and-trend')
        query='?cityId=s7-city&datasetId=s7-synthetic-v1&from=2026-10-15T00:00:00.000Z&to=2026-10-17T00:00:00.000Z'
        summary=get('/api/v1/traffic/summary'+query)
        series=get('/api/v1/traffic/series'+query+'&granularity=day')
        assert summary['meta']['sourceType']=='synthetic_test' and series['data']['items']
        stage(105,'seven-day-prediction-and-synthetic-errors')
        prediction=get('/api/v1/predictions?cityId=s7-city&datasetId=s7-synthetic-v1')
        assert prediction['meta']['sourceType']=='synthetic_test' and len(prediction['data']['predictions'])==7
        assert prediction['data']['release']['metrics'] and prediction['data']['evaluations']
        (out/'prediction-public.json').write_text(json.dumps(prediction,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        browser('verify-s9.mjs',[str(out/'browser-model'),base(),'s7-city','prediction',prediction['data']['release']['jobId']])
        stage(170,'admin-explicit-review-import-reader-logout')
        browser('verify-t3-demo.mjs',[str(out/'browser-management'),base(),str(root)],json.dumps({r:secret[r] for r in ('ADMIN','READER')}).encode())
        stage(250,'stop-switch-published-warehouse');batch('STOP');batch('START-WAREHOUSE')
        warehouse=get('/api/v1/warehouse/metrics?cityId=s5-city&datasetId=s5-synthetic-v1&grain=WINDOW')
        assert warehouse['meta']['sourceType']=='synthetic_test' and warehouse['data']['items']
        browser('verify-s9.mjs',[str(out/'browser-warehouse'),base(),'s5-city','warehouse',warehouse['data']['release']['id']])
        stage(320,'stop-restart-persistent-prediction');batch('STOP');batch('START')
        restored=get('/api/v1/predictions?cityId=s7-city&datasetId=s7-synthetic-v1')
        assert restored['data']==prediction['data'];batch('STOP')
        stage(370,'review-exact-baseline-ci-and-limitations')
        checks.append(dict(sourceType='synthetic_test',realData='BLOCKED',realAccuracy='NOT_EVALUABLE',
            localHiveExecution=False,browserTraining=False,ciScope='97f30db business baseline only; no T3 remote CI'))
        stage(420,'complete');save()
        (out/'summary.json').write_text(json.dumps(dict(passed=True,elapsedSeconds=round(time.monotonic()-start,2),
            pacedNarrationWindows=True,actualHttp=True,actualProductionBrowser=True,predictionRestoredEqual=True,
            liveTraining=False,liveHive=False,warehouseItems=len(warehouse['data']['items']),checks=checks),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    finally:
        save()
        if (root/'state/running.json').exists():batch('STOP')


if __name__=='__main__':main()
