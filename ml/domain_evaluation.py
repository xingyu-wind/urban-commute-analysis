"""Metric-specific offline evaluation. No DB publication of new research targets.

All fill is causal, labels stay missing, models/selection never consume target
domain test labels. Synthetic domains verify engineering only.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from data_adapter import hash_json, file_identity, CANONICAL_UNITS
from forecast import runtime_config

NAMES = ('naive', 'seasonal', 'random_forest', 'xgboost')
SEED = 20261020
MODEL_CONFIG = dict(random_forest=dict(n_estimators=24, max_depth=6, min_samples_leaf=3, n_jobs=1),
    xgboost=dict(n_estimators=30, max_depth=3, learning_rate=.08, n_jobs=1, tree_method='hist', objective='reg:squarederror'))


def task_profile(data):
    if data['target'] not in ('speed', 'flow', 'congestion_index') or data['unit'] != CANONICAL_UNITS.get(data['target'], data['unit']):
        raise ValueError('target/unit contract mismatch')
    if data['target'] == 'flow' and data['unit'] not in ('vehicles/hour', 'vehicles/interval'): raise ValueError('ambiguous flow unit')
    for r in data['rows']:
        v = r['value']
        if not r['timestamp'].endswith('Z') or (v is not None and (type(v) not in (int, float) or not math.isfinite(v) or v < 0)):
            raise ValueError('invalid UTC/measurement contract')
        if v is not None and ((data['target'] == 'speed' and v > 250) or (data['target'] == 'congestion_index' and v > 10)):
            raise ValueError('measurement outside target range')
    step = data['frequency_seconds']
    if step not in (300, 3600, 86400): raise ValueError('no validated task for this sampling frequency')
    season = 86400 // step if step < 86400 else 7
    horizon = {300: 12, 3600: 6, 86400: 7}[step]
    return dict(target=data['target'], unit=data['unit'], spatialGrain=data['spatial_grain'], frequencySeconds=step,
        seasonSteps=season, horizon=horizon, minTrainingSteps=7 * season, validationSteps=2 * season, testSteps=2 * season,
        minimumCoverage=.9, fullRequiredSteps=11 * season, baselineRequiredSteps=season + 4 * horizon,
        policy='7 seasonal training cycles + 2 validation cycles + 2 test cycles; baseline-only needs one cycle + four horizons',
        missingPolicy='causal past-only carry-forward features; never impute evaluation/training labels',
        noUniversal365DayRequirement=True)


def series(data):
    groups = defaultdict(dict)
    for row in data['rows']:
        t = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
        if t in groups[row['entity_id']]: raise ValueError('normalized duplicate')
        groups[row['entity_id']][t] = row['value']
    if not groups: raise ValueError('no observations')
    result = {}
    for entity, points in sorted(groups.items()):
        start, end = min(points), max(points)
        step = data['frequency_seconds']; span = (end - start).total_seconds()
        if any((t - start).total_seconds() % step for t in points): raise ValueError('irregular off-grid sampling; explicit resampling review required')
        count = int(span // step) + 1
        if count > 200000: raise ValueError('offline small-series limit exceeded')
        result[entity] = (start, [points.get(start + timedelta(seconds=step * i)) for i in range(count)])
    return result


def suitability(data):
    reasons, entities = [], []
    try:
        task = task_profile(data); groups = series(data)
    except ValueError as error:
        return dict(status='NOT_EVALUABLE', reasons=[str(error)], datasetId=data['dataset_id'], entities=[])
    if data['source_type'] != 'synthetic_test' and (data['license_status'] != 'verified' or 'analysis' not in data['allowed_uses']):
        reasons.append('source rights/use not verified')
    if hash_json(data['rows']) != data['normalized_sha256']: reasons.append('normalized content hash mismatch')
    for entity, (start, values) in groups.items():
        observed = sum(v is not None for v in values)
        coverage = observed / len(values)
        gap = longest = 0
        for v in values:
            gap = gap + 1 if v is None else 0; longest = max(longest, gap)
        status = ('TRAINABLE' if len(values) >= task['fullRequiredSteps'] else
                  'BASELINE_ONLY' if len(values) >= task['baselineRequiredSteps'] else 'NOT_EVALUABLE')
        why = []
        if status != 'TRAINABLE': why.append('insufficient seasonal cycles for complete candidate-model comparison')
        if coverage < task['minimumCoverage'] or longest > task['seasonSteps']:
            status = 'NOT_EVALUABLE'; why.append('too many missing labels or gap longer than a seasonal cycle')
        if reasons: status = 'NOT_EVALUABLE'; why += reasons
        entities.append(dict(entityId=entity, status=status, reasons=why, steps=len(values), observedLabels=observed,
            missingLabels=len(values) - observed, coverage=coverage, longestMissingRun=longest,
            fromUtc=start.isoformat(), toUtc=(start + timedelta(seconds=(len(values) - 1) * task['frequencySeconds'])).isoformat(),
            validationOrigins=2 if status == 'TRAINABLE' else 2 if status == 'BASELINE_ONLY' else 0,
            testOrigins=2 if status in ('TRAINABLE', 'BASELINE_ONLY') else 0))
    statuses = [e['status'] for e in entities]
    status = 'NOT_EVALUABLE' if 'NOT_EVALUABLE' in statuses else 'BASELINE_ONLY' if 'BASELINE_ONLY' in statuses else 'TRAINABLE'
    return dict(status=status, reasons=reasons or sorted({v for e in entities for v in e['reasons']}), task=task,
        datasetId=data['dataset_id'], datasetVersion=data['dataset_version'], domainId=data['domain_id'], cityId=data['city_id'],
        target=data['target'], unit=data['unit'], sourceType=data['source_type'], sourceSha256=data['source_sha256'],
        mappingSha256=data['mapping_sha256'], duplicatesRemoved=data['duplicates'], entities=entities,
        interpretation='synthetic engineering readiness only; not real traffic validity' if data['source_type'] == 'synthetic_test' else 'task readiness is not a guarantee of forecast validity')


def fill_prefix(values):
    filled, last = [], None
    for v in values:
        if v is not None: last = v
        filled.append(last)
    return filled


def feature(history, when, season):
    tail = history[-season:]
    if len(tail) < season or any(v is None for v in tail): return None
    seconds = when.hour * 3600 + when.minute * 60 + when.second
    return [history[-1], history[-2], history[-season], float(np.mean(history[-min(12, season):])),
        float(np.mean(tail)), float(np.std(tail)), when.weekday(),
        math.sin(2 * math.pi * seconds / 86400), math.cos(2 * math.pi * seconds / 86400)]


def training_rows(values, start, task):
    h = fill_prefix(values); x, y = [], []
    for i in range(task['seasonSteps'], len(values)):
        if values[i] is None: continue
        row = feature(h[:i], start + timedelta(seconds=i * task['frequencySeconds']), task['seasonSteps'])
        if row is not None: x.append(row); y.append(values[i])
    return x, y


def fitted(name, training):
    if name in NAMES[:2]: return None
    x = [row for xs, ys in training for row in xs]; y = [v for xs, ys in training for v in ys]
    if not x: raise ValueError('no causally usable training rows')
    constructor = RandomForestRegressor if name == 'random_forest' else XGBRegressor
    return constructor(random_state=SEED, **MODEL_CONFIG[name]).fit(np.asarray(x), np.asarray(y))


def recursive(name, model, past, first, task):
    h = fill_prefix(past)
    if not h or h[-1] is None: raise ValueError('no known past for inference')
    output = []
    for step in range(task['horizon']):
        when = first + timedelta(seconds=step * task['frequencySeconds'])
        row = feature(h, when, task['seasonSteps'])
        if row is None: raise ValueError('insufficient causal inference context')
        value = h[-1] if name == 'naive' else h[-task['seasonSteps']] if name == 'seasonal' else float(model.predict(np.asarray([row]))[0])
        value = max(0., value)
        if task['target'] == 'speed': value = min(250., value)
        if task['target'] == 'congestion_index': value = min(10., value)
        h.append(value); output.append(value)
    return output


def metrics(errors):
    values = [v for v in errors if v is not None]
    if not values: return dict(mae=None, rmse=None, count=0)
    return dict(mae=sum(abs(v) for v in values) / len(values), rmse=math.sqrt(sum(v * v for v in values) / len(values)), count=len(values))


def aggregate(windows, horizon):
    errors = [v for window in windows for v in window['errors']]
    return dict(**metrics(errors), byHorizon=[dict(step=i + 1, **metrics([w['errors'][i] for w in windows])) for i in range(horizon)],
                windows=[{k: v for k, v in w.items() if k != 'errors'} for w in windows])


def origins(n, task, full):
    width = task['seasonSteps'] if full else task['horizon']
    return dict(validation=[n - 4 * width, n - 3 * width], test=[n - 2 * width, n - width])


def evaluate(data):
    readiness = suitability(data)
    if readiness['status'] == 'NOT_EVALUABLE': return dict(status='NOT_EVALUABLE', readiness=readiness)
    task = readiness['task']; full = readiness['status'] == 'TRAINABLE'; names = NAMES if full else NAMES[:2]
    groups = series(data); windows = {split: {name: [] for name in names} for split in ('validation', 'test')}
    selections = {}
    boundaries = {}
    # Complete validation before opening test labels for scoring or model selection.
    for split in ('validation', 'test'):
        for entity, (start, values) in groups.items():
            cuts = origins(len(values), task, full)
            boundaries[entity] = {k: [(start + timedelta(seconds=o * task['frequencySeconds'])).isoformat() for o in os] for k, os in cuts.items()}
            for origin in cuts[split]:
                for name in names:
                    model = fitted(name, [training_rows(values[:origin], start, task)])
                    first = start + timedelta(seconds=origin * task['frequencySeconds'])
                    prediction = recursive(name, model, values[:origin], first, task)
                    errors = [p - a if a is not None else None for p, a in zip(prediction, values[origin:origin + task['horizon']])]
                    windows[split][name].append(dict(entityId=entity, originUtc=first.isoformat(), trainingBeforeUtc=first.isoformat(),
                        errors=errors, **metrics(errors), missingLabels=sum(v is None for v in errors)))
        if split == 'validation':
            validation = {name: aggregate(windows[split][name], task['horizon']) for name in names}
            if any(v['count'] == 0 or any(h['count'] == 0 for h in v['byHorizon']) for v in validation.values()):
                return dict(status='NOT_EVALUABLE', reasons=['no usable validation labels at one or more horizons'], readiness=readiness)
            key = lambda n: (validation[n]['mae'], validation[n]['rmse'], NAMES.index(n))
            baseline = min(names[:2], key=key); selected = min(names, key=key)
            if selected in NAMES[2:] and validation[selected]['mae'] >= .99 * validation[baseline]['mae']: selected = baseline
            selections = dict(selected=selected, bestBaseline=baseline, rule='validation MAE/RMSE/fixed order; ML needs >=1% MAE improvement')
    report = dict(status=readiness['status'], readiness=readiness, task=task, **selections,
        boundaries=boundaries, validation=validation, test={name: aggregate(windows['test'][name], task['horizon']) for name in names},
        seed=SEED, modelConfigurations=MODEL_CONFIG, evaluationOnly=True, apiPublication=False,
        sourceSha256=data['source_sha256'], mappingSha256=data['mapping_sha256'], inputSha256=data['normalized_sha256'],
        evaluatorSha256=file_identity(Path(__file__))['sha256'], adapterSha256=file_identity(Path(__file__).with_name('data_adapter.py'))['sha256'],
        runtime=runtime_config())
    if any(v['count'] == 0 or any(h['count'] == 0 for h in v['byHorizon']) for v in report['test'].values()):
        report['status'] = 'NOT_EVALUABLE'; report['reasons'] = ['no usable test labels at one or more horizons']
    report['evaluationVersion'] = hash_json(report)
    return report


def transfer(source, target):
    """Frozen source-selected model; target past supplies lags, never fit/selection labels."""
    a, b = suitability(source), suitability(target)
    reasons = []
    if a['status'] != 'TRAINABLE' or b['status'] != 'TRAINABLE': reasons.append('both domains require complete candidate-model evaluation readiness')
    if any(source[k] != target[k] for k in ('target', 'unit', 'frequency_seconds', 'spatial_grain')): reasons.append('incomparable task semantics')
    if source['domain_id'] == target['domain_id'] or source['city_id'] == target['city_id']: reasons.append('domains/cities are not isolated')
    if source['source_sha256'] == target['source_sha256']: reasons.append('same source file')
    # Ignore dataset/domain/entity aliases so renamed copies cannot fake transfer.
    fingerprints = lambda d: {(r['timestamp'], r['value']) for r in d['rows'] if r['value'] is not None}
    fa, fb = fingerprints(source), fingerprints(target)
    overlap = len(fa & fb) / max(1, min(len(fa), len(fb)))
    if overlap >= .2: reasons.append('>=20% exact time/value overlap; conservative duplicate/overlap rejection')
    if reasons: return dict(status='NOT_EVALUABLE', reasons=reasons, exactOverlapRatio=overlap)
    task = a['task']; source_report = evaluate(source)
    if source_report['status'] == 'NOT_EVALUABLE': return dict(status='NOT_EVALUABLE', reasons=['source validation/test labels not evaluable'])
    selected = source_report['selected']
    training, source_ends = [], []
    for entity, (start, values) in series(source).items():
        cutoff = origins(len(values), task, True)['test'][0]
        training.append(training_rows(values[:cutoff], start, task))
        source_ends.append(start + timedelta(seconds=cutoff * task['frequencySeconds']))
    target_groups = series(target)
    target_first = min(start + timedelta(seconds=origins(len(values), task, True)['test'][0] * task['frequencySeconds']) for start, values in target_groups.values())
    if max(source_ends) > target_first: return dict(status='NOT_EVALUABLE', reasons=['source training would use data after target forecast origin'])
    results = {}
    for name in NAMES:
        model = fitted(name, training); windows = []
        for entity, (start, values) in target_groups.items():
            for origin in origins(len(values), task, True)['test']:
                first = start + timedelta(seconds=origin * task['frequencySeconds'])
                prediction = recursive(name, model, values[:origin], first, task)
                errors = [p - v if v is not None else None for p, v in zip(prediction, values[origin:origin + task['horizon']])]
                windows.append(dict(entityId=entity, originUtc=first.isoformat(), errors=errors, **metrics(errors)))
        results[name] = aggregate(windows, task['horizon'])
    report = dict(status='EVALUATED', sourceDomain=source['domain_id'], targetDomain=target['domain_id'],
        target=task['target'], unit=task['unit'], sourceSelectedModel=selected, models=results, exactOverlapRatio=overlap,
        sourceTrainingBeforeUtc=max(source_ends).isoformat(), targetTestFromUtc=target_first.isoformat(),
        targetLabelsUsedForFitOrSelection=False, sourceInputSha256=source['normalized_sha256'], targetInputSha256=target['normalized_sha256'],
        realGeneralizationConclusion='NOT_EVALUABLE' if 'synthetic_test' in (source['source_type'], target['source_type']) else 'limited cross-dataset transfer only; no universal city generalization claim',
        limitation='synthetic domains demonstrate engineering only' if 'synthetic_test' in (source['source_type'], target['source_type']) else 'different measurement/preprocessing domains may not be comparable',
        task=task, seed=SEED, modelConfigurations=MODEL_CONFIG, runtime=runtime_config(),
        sourceMappingSha256=source['mapping_sha256'], targetMappingSha256=target['mapping_sha256'],
        evaluatorSha256=file_identity(Path(__file__))['sha256'], adapterSha256=file_identity(Path(__file__).with_name('data_adapter.py'))['sha256'],
        evaluationOnly=True, apiPublication=False)
    if any(v['count'] == 0 or any(h['count'] == 0 for h in v['byHorizon']) for v in results.values()):
        report['status'] = 'NOT_EVALUABLE'; report['reasons'] = ['no target test labels at one or more horizons']
    report['evaluationVersion'] = hash_json(report)
    return report
