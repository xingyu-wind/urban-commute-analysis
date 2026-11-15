"""Package source observations for real HDFS/Hive and independently reconcile exports.

Only the three explicitly allowed Chicago official datasets may enter a remote
evidence bundle. Teacher-reference and account data are never uploaded.
"""
from __future__ import annotations
import argparse
import collections
from decimal import Decimal
import hashlib
import json
from pathlib import Path

FIELDS=['id','datasetId','cityId','targetType','targetId','localDate','observedAt','speedKmh','congestionIndex','volume','lengthKm','sampleCount']
ALLOWED={'CHICAGO_DAILY','CHICAGO_HOURLY','CHICAGO_ROADS_7D'}
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def bundle(source,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    original=json.loads(Path(source).read_text(encoding='utf-8'))
    datasets={d['id']:d for d in original['datasets'] if d['id'] in ALLOWED}
    if len(datasets)!=3 or any(d['sourceType']!='official_public_historical' for d in datasets.values()):raise ValueError('Only verified public Chicago inputs may be published')
    rows=[r for r in original['observations'] if r['datasetId'] in ALLOWED]
    tsv=output/'source.tsv'
    tsv.write_text('\n'.join('\t'.join('NULL' if r.get(k) is None else str(r[k]) for k in FIELDS) for r in rows)+'\n',encoding='utf-8',newline='\n')
    manifest=dict(schemaVersion='teacher-hive-bundle-v1',parentNormalizedSha256=sha(source),sourceTsvSha256=sha(tsv),
        inputRows=len(rows),byDataset=dict(collections.Counter(r['datasetId'] for r in rows)),
        datasets=list(datasets.values()),scope='Official public Chicago observations only; no teacher-reference, account or personal records',
        sourceFiles=[p for p in original['sourceFiles'] if 'chicago' in p['path']])
    write(output/'manifest.json',manifest)
    print(json.dumps(manifest))
    return manifest

def read_source(path):
    rows=[]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        fields=line.split('\t')
        if len(fields)!=len(FIELDS):raise ValueError('Invalid TSV field count')
        r=dict(zip(FIELDS,fields))
        for key in ('speedKmh','congestionIndex','volume','lengthKm'):
            r[key]=None if r[key]=='NULL' else Decimal(r[key])
        r['sampleCount']=int(r['sampleCount']);rows.append(r)
    return rows

def expected(rows):
    # Every expected value is calculated from original TSV rows, not Hive output.
    grouped={key:collections.defaultdict(list) for key in ('daily','weekday','hour','road_length')}
    from datetime import date
    for r in rows:
        grouped['daily'][(r['datasetId'],r['cityId'],r['localDate'])].append(r)
        grouped['weekday'][(r['datasetId'],r['cityId'],'WEEKEND' if date.fromisoformat(r['localDate']).weekday()>=5 else 'WEEKDAY')].append(r)
        if r['observedAt']!='NULL':grouped['hour'][(r['datasetId'],r['cityId'],r['observedAt'][11:13])].append(r)
        if r['datasetId']=='CHICAGO_ROADS_7D':grouped['road_length'][(r['datasetId'],r['cityId'],r['observedAt'])].append(r)
    def weighted(records,key):
        valid=[r for r in records if r[key] is not None]
        return sum((r[key]*r['sampleCount'] for r in valid),Decimal(0))/sum(r['sampleCount'] for r in valid) if valid else None
    outputs={}
    for topic,groups in grouped.items():
        entries={}
        for key,recs in groups.items():
            count=sum(r['sampleCount'] for r in recs)
            if topic=='daily':vals=[count,len(recs),weighted(recs,'speedKmh'),weighted(recs,'congestionIndex'),weighted(recs,'volume')]
            elif topic=='weekday':vals=[count,weighted(recs,'speedKmh'),weighted(recs,'congestionIndex'),weighted(recs,'volume')]
            elif topic=='hour':vals=[count,weighted(recs,'speedKmh'),weighted(recs,'volume')]
            else:
                length=sum((r['lengthKm'] for r in recs),Decimal(0))
                congested=sum((r['lengthKm'] for r in recs if r['speedKmh']<Decimal('32.18688')),Decimal(0))
                valid=[r for r in recs if r['speedKmh']>0]
                travel=sum((r['lengthKm']/r['speedKmh']*3600 for r in valid),Decimal(0)) if valid else None
                vals=[len(recs),length,congested/length if length else None,sum(r['speedKmh']<Decimal('16.09344') for r in recs),travel,sum(r['speedKmh']==0 for r in recs)]
            entries[key]=vals
        outputs[topic]=entries
    return outputs

def reconcile(bundle_dir,evidence):
    bundle_dir=Path(bundle_dir);evidence=Path(evidence)
    manifest=json.loads((bundle_dir/'manifest.json').read_text(encoding='utf-8'))
    if sha(bundle_dir/'source.tsv')!=manifest['sourceTsvSha256']:raise ValueError('Bundle changed')
    rows=read_source(bundle_dir/'source.tsv');wanted=expected(rows)
    result=dict(passed=False,scope='actual Hive exports versus independently recalculated source TSV',
        inputSha256=manifest['parentNormalizedSha256'],sourceTsvSha256=manifest['sourceTsvSha256'],inputRows=len(rows),topics={})
    for topic,expect in wanted.items():
        path=evidence/(topic+'.tsv');actual={}
        for line in path.read_text(encoding='utf-8').splitlines():
            fields=line.split('\t');key=tuple(fields[:3])
            if key in actual:raise ValueError('Duplicate Hive aggregate key')
            actual[key]=[None if v in ('\\N','NULL','null','NaN','') else Decimal(v) for v in fields[3:]]
        if actual.keys()!=expect.keys():raise ValueError('Hive aggregate key set mismatch: '+topic)
        checked=0
        for key,wants in expect.items():
            if len(actual[key])!=len(wants):raise ValueError('Hive aggregate width mismatch: '+topic)
            for got,want in zip(actual[key],wants):
                if (got is None)!=(want is None) or (got is not None and abs(got-Decimal(want))>Decimal('0.000001')*max(Decimal(1),abs(Decimal(want)))):
                    raise ValueError('Hive metric mismatch: '+topic+' '+str(key))
                checked+=1
        result['topics'][topic]=dict(rows=len(actual),checkedValues=checked,sha256=sha(path))
    if (evidence/'download.tsv').exists() and sha(evidence/'download.tsv')!=manifest['sourceTsvSha256']:raise ValueError('HDFS round trip mismatch')
    result['passed']=True;write(evidence/'reconciliation.json',result);print(json.dumps(result));return result

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('bundle');b.add_argument('--input',type=Path,required=True);b.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('reconcile');r.add_argument('--bundle',type=Path,required=True);r.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();bundle(a.input,a.output) if a.action=='bundle' else reconcile(a.bundle,a.evidence)
if __name__=='__main__':main()
