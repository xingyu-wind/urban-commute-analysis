"""Offline CITY daily congestion forecasting. No HTTP-triggered training or untrusted pickle loading."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import tempfile

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bigdata'))
from warehouse import snapshot, connect, canonical, sha, write_json, timestamp, stamp

SEED = 20261020
NAMES = ('naive', 'seasonal7', 'random_forest', 'xgboost')
CONFIG = dict(seed=SEED, strategy='recursive-refit-each-origin', horizon=7, min_days=365,
    validation_days=28, test_days=28, origin_stride=7, lags=[1, 7, 14, 28],
    daily_policy='UTC; >=4 samples and all four 6h slots; no missing days; no imputation; same-day collection',
    selection='validation MAE, RMSE, fixed candidate order; ML must improve best baseline MAE by >=1%',
    random_forest=dict(n_estimators=60, max_depth=9, min_samples_leaf=3, n_jobs=1),
    xgboost=dict(n_estimators=80, max_depth=3, learning_rate=0.06, subsample=1.0,
                 colsample_bytree=1.0, n_jobs=1, tree_method='hist', objective='reg:squarederror'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def runtime_config():
    """Bind actual installed runtime, dependency locks and every input/training code file."""
    if sys.version_info[:2] != (3, 11):
        raise ValueError('Python 3.11 required')
    packages = {}
    for lock in ('ml/requirements.lock.txt', 'data-pipeline/requirements.lock.txt'):
        for line in (ROOT / lock).read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            requirement = Requirement(line)
            if requirement.marker and not requirement.marker.evaluate():
                continue
            installed = version(requirement.name)
            if installed not in requirement.specifier:
                raise ValueError('installed runtime differs from dependency lock: ' + requirement.name)
            packages[requirement.name] = installed
    locks = ['ml/requirements.lock.txt', 'ml/requirements.in', 'data-pipeline/requirements.lock.txt']
    code = ['ml/forecast.py', 'bigdata/warehouse.py', 'data-pipeline/commute_etl/clean.py', 'data-pipeline/commute_etl/store.py']
    return dict(**CONFIG, packages=packages, code_sha256=sha(Path(__file__)), python='3.11',
                lock_sha256={p: sha(ROOT / p) for p in locks}, code_sha256s={p: sha(ROOT / p) for p in code},
                publication_verification='fresh deterministic refit/backtest/artifact/inference replay v1')


def daily(records, city, dataset, cutoff):
    """Deduplicate lineage, isolate one CITY/dataset/version, reject incomplete days."""
    end = timestamp(cutoff)
    if end.time() != datetime.min.time():
        raise ValueError('cutoff must be exclusive UTC midnight')
    rows = [r for r in records if r['city_id'] == city and r['dataset_id'] == dataset
            and r['target_type'] == 'CITY' and r['target_id'] == city]
    if not rows or len({(r['dataset_version'], r['source_type']) for r in rows}) != 1:
        raise ValueError('empty or mixed data versions')
    groups, seen = defaultdict(list), {}
    for r in rows:
        observed, collected = timestamp(r['observed_at']), timestamp(r['collected_at'])
        if observed >= end or collected >= end or collected < observed or collected.date() != observed.date():
            raise ValueError('unavailable or late-collected historical sample')
        key = r['observed_at']
        content = {k: v for k, v in r.items() if k not in ('batch_id', 'source_sha256')}
        if key in seen:
            if content != seen[key]:
                raise ValueError('conflicting observations')
            continue
        seen[key] = content
        value = Decimal(r['congestion_index'])
        if not value.is_finite() or not 0 <= value <= 10:
            raise ValueError('invalid congestion index')
        groups[observed.date()].append((observed.hour // 6, value))
    days = sorted(groups)
    if len(days) < CONFIG['min_days'] or days[-1] + timedelta(days=1) != end.date():
        raise ValueError('insufficient history or missing cutoff day; no validity conclusion')
    result = []
    for i, day in enumerate(days):
        values = groups[day]
        if day != days[0] + timedelta(days=i) or len(values) < 4 or {v[0] for v in values} != {0, 1, 2, 3}:
            raise ValueError('missing day or insufficient daily coverage; no imputation')
        result.append(dict(date=day.isoformat(), value=float(sum(v[1] for v in values) / len(values)), sampleCount=len(values)))
    return result


def features(history, day):
    """history ends BEFORE day: lagged rolling windows never include the target."""
    if len(history) < 28:
        raise ValueError('28 historical days required')
    return [history[-lag] for lag in CONFIG['lags']] + [
        float(np.mean(history[-7:])), float(np.mean(history[-28:])), float(np.std(history[-7:])),
        day.weekday(), int(day.weekday() >= 5),
        np.sin(2 * np.pi * day.timetuple().tm_yday / 365.2425),
        np.cos(2 * np.pi * day.timetuple().tm_yday / 365.2425)]


def fit(name, values, start):
    if name in NAMES[:2]:
        return None
    x = [features(values[:i], start + timedelta(days=i)) for i in range(28, len(values))]
    y = values[28:]
    model = (RandomForestRegressor if name == 'random_forest' else XGBRegressor)(random_state=SEED, **CONFIG[name])
    model.fit(np.asarray(x), np.asarray(y))
    return model


def predict(name, model, history, first_day):
    """Only the prefix is accepted; all seven subsequent lags use predictions."""
    history = list(history)
    predictions = []
    for step in range(7):
        value = (history[-1] if name == 'naive' else history[-7] if name == 'seasonal7'
                 else model.predict(np.asarray([features(history, first_day + timedelta(days=step))]))[0])
        value = float(np.clip(value, 0, 10))
        predictions.append(value)
        history.append(value)
    return predictions


def scores(errors):
    a = np.asarray(errors)
    return dict(mae=float(np.abs(a).mean()), rmse=float(np.sqrt(np.square(a).mean())),
                byHorizon=[dict(step=i + 1, mae=float(np.abs(a[:, i]).mean()),
                                rmse=float(np.sqrt(np.square(a[:, i]).mean()))) for i in range(7)])


def backtest(name, values, start, origins):
    errors, windows = [], []
    for origin in origins:
        model = fit(name, values[:origin], start)
        forecast = predict(name, model, values[:origin], start + timedelta(days=origin))
        actual = values[origin:origin + 7]
        errors.append(np.asarray(forecast) - actual)
        windows.append(dict(cutoff=(start + timedelta(days=origin)).isoformat(),
                            predictions=forecast, actual=actual))
    return dict(**scores(errors), windows=windows)


def choose(validation):
    key = lambda n: (validation[n]['mae'], validation[n]['rmse'], NAMES.index(n))
    baseline = min(NAMES[:2], key=key)
    winner = min(NAMES, key=key)
    return baseline if winner in NAMES[2:] and validation[winner]['mae'] >= validation[baseline]['mae'] * .99 else winner


def train(series, identity, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    values = [r['value'] for r in series]
    if len(values) < CONFIG['min_days']:
        raise ValueError('insufficient daily history')
    start, n = date.fromisoformat(series[0]['date']), len(values)
    validation_origins, test_origins = list(range(n - 56, n - 28, 7)), list(range(n - 28, n, 7))
    validation = {name: backtest(name, values, start, validation_origins) for name in NAMES}
    selected = choose(validation)  # Frozen before any test scores are computed.
    test = {name: backtest(name, values, start, test_origins) for name in NAMES}
    config = runtime_config()
    model_version = digest(dict(identity=identity, config=config, series=series))
    model = fit(selected, values, start)
    # Baselines also have a real, inspectable artifact; never load arbitrary joblib via CLI.
    joblib.dump(dict(name=selected, model=model, history=values, config=config), output / 'model.joblib')
    future = predict(selected, model, values, start + timedelta(days=n))
    evaluation = dict(validation=validation, test=test, selected=selected,
        boundaries=dict(trainEnd=(start + timedelta(days=n - 56)).isoformat(),
                        validationEnd=(start + timedelta(days=n - 28)).isoformat(), testEnd=(start + timedelta(days=n)).isoformat()))
    write_json(output / 'evaluation.json', evaluation)
    write_json(output / 'training-input.json', dict(identity=identity, series=series))
    now = stamp(datetime.now(timezone.utc))
    result = dict(modelVersion=model_version, modelName=selected, trainedAt=now, generatedAt=now,
        dataCutoff=identity['cutoff'], dataAsOf=identity['observed_to'], datasetVersion=identity['dataset_version'],
        cityId=identity['city'], datasetId=identity['dataset'], sourceType=identity['source_type'],
        inputSha256=digest(dict(identity=identity, series=series)), config=config,
        batchIds=identity['batch_ids'], sourceHashes=identity['source_hashes'],
        limitation='合成演示：回测误差不代表真实交通预测准确率。' if identity['source_type'] == 'synthetic_test'
                   else '历史回测不保证未来准确率；样本均值非车辆加权、非通勤人数。',
        history=series[-28:], predictions=[dict(date=(start + timedelta(days=n + i)).isoformat(), value=round(v, 6)) for i, v in enumerate(future)],
        metrics=dict(mae=test[selected]['mae'], rmse=test[selected]['rmse']),
        artifacts={p: sha(output / p) for p in ('model.joblib', 'evaluation.json', 'training-input.json')})
    write_json(output / 'run.json', result)
    return result


def verify_run(run_dir, result, series, identity):
    """Reconstruct trusted scientific outputs; NEVER deserialize the submitted model.

    A file digest supplied by that same file's author is not proof of inference.
    Replay under the locked runtime independently binds model bytes, all evaluation
    labels/windows/selection, and each of the seven rounded inference values.
    """
    if result['config'] != runtime_config():
        raise ValueError('configuration/code/dependency lock mismatch')
    with tempfile.TemporaryDirectory(prefix='s7-verify-') as temp:
        reference = train(series, identity, Path(temp) / 'trusted')
        ignored = {'trainedAt', 'generatedAt', 'limitation'}
        if {k: v for k, v in result.items() if k not in ignored} != {k: v for k, v in reference.items() if k not in ignored}:
            raise ValueError('independent model/evaluation/seven-point replay mismatch')
        for name, expected in reference['artifacts'].items():
            if sha(Path(run_dir) / name) != expected:
                raise ValueError('independent model artifact replay mismatch')
        if not isinstance(result['limitation'], str) or not result['limitation'].startswith(reference['limitation']):
            raise ValueError('source limitation changed')
    if timestamp(result['trainedAt']) > timestamp(result['generatedAt']):
        raise ValueError('generation precedes training')
    return dict(method='fresh deterministic replay; no deserialization', verifiedPredictionCount=7,
                modelVersion=reference['modelVersion'], inputSha256=reference['inputSha256'])


def admit(inputs, output, city, dataset, start, cutoff):
    if timestamp(start).time() != datetime.min.time():
        raise ValueError('start must be UTC midnight')
    manifest = snapshot(inputs, output, start, cutoff)
    records = json.loads((Path(output) / 'observations.json').read_text(encoding='utf-8'))
    series = daily(records, city, dataset, cutoff)
    batches = [b for b in manifest['batches'] if b['dataset_id'] == dataset]
    if not batches or len({(b['dataset_version'], b['source_type']) for b in batches}) != 1:
        raise ValueError('mixed batch versions')
    identity = dict(city=city, dataset=dataset, dataset_version=batches[0]['dataset_version'],
        source_type=batches[0]['source_type'], start=start, cutoff=cutoff,
        batch_ids=sorted(b['batch_id'] for b in batches), source_hashes=sorted({b['source_sha256'] for b in batches}),
        batches=sorted(batches, key=lambda b: b['batch_id']), observations_sha256=digest(records),
        observed_to=max(r['observed_at'] for r in records if r['city_id'] == city and r['dataset_id'] == dataset and r['target_type'] == 'CITY'))
    return series, identity


def publish(run_dir, inputs, fail_at=None):
    """Re-admit S5 committed input before publishing; one transaction switches a scoped pointer."""
    run_dir = Path(run_dir)
    result = json.loads((run_dir / 'run.json').read_text(encoding='utf-8'))
    if set(result['artifacts']) != {'model.joblib', 'evaluation.json', 'training-input.json'}:
        raise ValueError('artifact manifest mismatch')
    for name, expected in result['artifacts'].items():
        if sha(run_dir / name) != expected:
            raise ValueError('artifact checksum mismatch')
    saved = json.loads((run_dir / 'training-input.json').read_text(encoding='utf-8'))
    identity = saved['identity']
    with tempfile.TemporaryDirectory(prefix='s7-admit-') as temp:
        series, actual = admit(inputs, Path(temp) / 'bundle', identity['city'], identity['dataset'], identity['start'], identity['cutoff'])
    if saved != dict(identity=actual, series=series) or result['inputSha256'] != digest(saved):
        raise ValueError('training input changed')
    expected_version = digest(dict(identity=actual, config=result['config'], series=series))
    if (result['modelVersion'] != expected_version or result['cityId'] != actual['city']
        or result['datasetId'] != actual['dataset'] or result['dataCutoff'] != actual['cutoff'] or result['dataAsOf'] != actual['observed_to']
        or result['datasetVersion'] != actual['dataset_version'] or result['sourceType'] != actual['source_type']
        or result['batchIds'] != actual['batch_ids'] or result['sourceHashes'] != actual['source_hashes']
        or result['history'] != series[-28:] or result['config']['code_sha256'] != sha(Path(__file__))):
        raise ValueError('run identity mismatch')
    evaluation = json.loads((run_dir / 'evaluation.json').read_text(encoding='utf-8'))
    if (result['modelName'] != choose(evaluation['validation']) or result['modelName'] != evaluation['selected']
        or result['metrics'] != {k: evaluation['test'][result['modelName']][k] for k in ('mae', 'rmse')}):
        raise ValueError('model selection mismatch')
    first = timestamp(result['dataCutoff']).date()
    if len(result['predictions']) != 7 or any(p['date'] != (first + timedelta(days=i)).isoformat()
        or not np.isfinite(p['value']) or not 0 <= p['value'] <= 10 for i, p in enumerate(result['predictions'])):
        raise ValueError('invalid seven-day prediction')
    verification = verify_run(run_dir, result, series, actual)
    stable = {k: v for k, v in result.items() if k not in ('trainedAt', 'generatedAt')}
    content = digest(stable)
    job_id = content[:32]
    connection = connect()
    lock = 's7:' + digest([result['cityId'], result['datasetId']])[:60]
    started = False
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT GET_LOCK(%s,10) acquired', (lock,))
            if cur.fetchone()['acquired'] != 1:
                raise ValueError('prediction publisher busy')
            cur.execute('SELECT * FROM prediction_job WHERE job_id=%s FOR UPDATE', (job_id,))
            prior = cur.fetchone()
            if prior and prior['content_sha256'] != content:
                raise ValueError('job identity conflict')
            if prior and prior['status'] == 'PUBLISHED':
                connection.commit()
                return dict(jobId=job_id, reused=True, verification=verification)
            cur.execute('SELECT j.* FROM prediction_current c JOIN prediction_job j USING(job_id) WHERE c.city_id=%s AND c.dataset_id=%s',
                        (result['cityId'], result['datasetId']))
            current = cur.fetchone()
            if current and (current['data_cutoff'] > timestamp(result['dataCutoff']) or
                            current['generated_at'] >= timestamp(result['generatedAt'])):
                raise ValueError('stale prediction cannot replace newer publication')
            if prior:
                cur.execute("UPDATE prediction_job SET status='STAGING',attempts=attempts+1 WHERE job_id=%s", (job_id,))
            else:
                cur.execute("INSERT INTO prediction_model(model_version,input_sha256,configuration,artifacts) VALUES (%s,%s,%s,%s) "
                    'ON DUPLICATE KEY UPDATE model_version=model_version',
                    (result['modelVersion'], result['inputSha256'], canonical(result['config']), canonical(result['artifacts'])))
                cur.execute('SELECT input_sha256,configuration,artifacts FROM prediction_model WHERE model_version=%s', (result['modelVersion'],))
                registered = cur.fetchone()
                if registered['input_sha256'] != result['inputSha256'] or json.loads(registered['configuration']) != result['config'] or json.loads(registered['artifacts']) != result['artifacts']:
                    raise ValueError('model version conflict')
                cur.execute("INSERT INTO prediction_job(job_id,model_version,city_id,dataset_id,data_cutoff,generated_at,content_sha256,status,document) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,'STAGING',%s)",
                    (job_id, result['modelVersion'], result['cityId'], result['datasetId'], timestamp(result['dataCutoff']),
                     timestamp(result['generatedAt']), content, canonical(result)))
            connection.commit()
            started = True
            for i, p in enumerate(result['predictions']):
                cur.execute('INSERT INTO prediction_result VALUES (%s,%s,%s,%s)', (job_id, i + 1, p['date'], p['value']))
                if fail_at == 'insert':
                    raise RuntimeError('injected insert failure')
            for split in ('validation', 'test'):
                for model in NAMES:
                    cur.execute('INSERT INTO prediction_evaluation VALUES (%s,%s,%s,%s)', (job_id, split, model, canonical(evaluation[split][model])))
            cur.execute('SELECT forecast_date,value FROM prediction_result WHERE job_id=%s ORDER BY step', (job_id,))
            readback = cur.fetchall()
            if [(str(r['forecast_date']), float(r['value'])) for r in readback] != [(p['date'], p['value']) for p in result['predictions']]:
                raise ValueError('prediction readback differs')
            cur.execute("UPDATE prediction_job SET status='PUBLISHED',published_at=UTC_TIMESTAMP(3) WHERE job_id=%s", (job_id,))
            if fail_at == 'commit':
                raise RuntimeError('injected before switch')
            cur.execute('INSERT INTO prediction_current VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE job_id=VALUES(job_id)',
                        (result['cityId'], result['datasetId'], job_id))
            if fail_at == 'switch':
                raise RuntimeError('injected after switch')
            if fail_at == 'crash':
                os._exit(73)  # Test-only hook: socket close must roll back the switch.
            connection.commit()
        return dict(jobId=job_id, reused=False, verification=verification)
    except BaseException:
        connection.rollback()
        if started:
            with connection.cursor() as cur:
                cur.execute("UPDATE prediction_job SET status='FAILED' WHERE job_id=%s", (job_id,))
            connection.commit()
        raise
    finally:
        try:
            with connection.cursor() as cur:
                cur.execute('SELECT RELEASE_LOCK(%s)', (lock,))
            connection.commit()
        finally:
            connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['train', 'publish'])
    parser.add_argument('--batch-output', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--city')
    parser.add_argument('--dataset')
    parser.add_argument('--from', dest='start')
    parser.add_argument('--cutoff')
    args = parser.parse_args()
    if args.action == 'publish':
        print(json.dumps(publish(args.output, args.batch_output)))
    else:
        if not all((args.city, args.dataset, args.start, args.cutoff)) or sys.version_info[:2] != (3, 11):
            parser.error('train requires Python3.11, --city --dataset --from --cutoff')
        bundle = args.output.with_name(args.output.name + '-admission')
        series, identity = admit(args.batch_output, bundle, args.city, args.dataset, args.start, args.cutoff)
        result = train(series, identity, args.output)
        print(json.dumps(dict(modelVersion=result['modelVersion'], modelName=result['modelName'], metrics=result['metrics'])))


if __name__ == '__main__':
    main()
