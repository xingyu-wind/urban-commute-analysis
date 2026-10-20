import copy
from datetime import datetime, timedelta
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import domain_evaluation as e
from data_adapter import inspect_file, confirm, convert, hash_json
from examples.fixtures import make_long


def dataset(tmp_path, domain='alpha', days=14, frequency=3600):
    path, review = make_long(tmp_path / domain, domain, days, frequency)
    proposal = inspect_file(path)
    cfg = confirm(proposal, review, 'synthetic-fixture-owner', proposal['proposalSha256'])
    return convert(path, cfg)


@pytest.fixture(scope='module')
def domains(tmp_path_factory):
    p = tmp_path_factory.mktemp('domains')
    return dataset(p, 'alpha'), dataset(p, 'beta')


@pytest.mark.parametrize('days,status', [(1, 'NOT_EVALUABLE'), (4, 'BASELINE_ONLY'), (14, 'TRAINABLE')])
def test_task_specific_readiness(tmp_path, days, status):
    d = dataset(tmp_path, days=days)
    result = e.suitability(d)
    assert result['status'] == status
    assert result['task']['fullRequiredSteps'] == 264
    assert result['task']['noUniversal365DayRequirement']


def test_five_minute_speed_and_daily_tasks_do_not_require_365_days(tmp_path):
    high = dataset(tmp_path, 'alpha', 14, 300)
    daily = dataset(tmp_path, 'beta', 100, 86400)
    assert e.suitability(high)['status'] == e.suitability(daily)['status'] == 'TRAINABLE'
    assert e.suitability(high)['task']['horizon'] == 12
    assert e.suitability(daily)['task']['horizon'] == 7


def test_quality_missing_irregular_unknown_units_and_rights(domains):
    original = domains[0]
    for kind in ('missing', 'irregular', 'unit', 'rights'):
        d = copy.deepcopy(original)
        if kind == 'missing':
            for row in d['rows'][:100]: row['value'] = None
        if kind == 'irregular': d['rows'][2]['timestamp'] = '2023-12-31T18:17:00.000Z'
        if kind == 'unit': d['unit'] = 'mph'
        if kind == 'rights': d.update(source_type='historical_snapshot', license_status='unverified')
        d['normalized_sha256'] = hash_json(d['rows'])
        assert e.suitability(d)['status'] == 'NOT_EVALUABLE'


def test_shifted_features_and_missing_labels_never_imputed():
    task = dict(seasonSteps=24, frequencySeconds=3600)
    values = [1.] * 24 + [None] + [3.] * 8
    x, y = e.training_rows(values, datetime(2024, 1, 1), task)
    assert len(y) == 8 and all(v == 3 for v in y)
    assert x[0][:3] == [1., 1., 1.]
    changed = list(values); changed[25] = 200
    xx, yy = e.training_rows(changed, datetime(2024, 1, 1), task)
    assert xx[0] == x[0] and yy[0] == 200  # Target is a label, never its own feature.


def test_recursive_horizon_uses_own_predictions():
    class Spy:
        def __init__(self): self.lags = []
        def predict(self, x): self.lags.append(x[0][0]); return [x[0][0] + 1]
    model = Spy()
    task = dict(seasonSteps=24, frequencySeconds=3600, horizon=6, target='speed')
    assert e.recursive('random_forest', model, [1.] * 24, datetime(2024, 1, 2), task) == [2, 3, 4, 5, 6, 7]
    assert model.lags == [1, 2, 3, 4, 5, 6]


def test_real_models_backtests_reproduce_and_report_each_window_horizon(domains):
    d = domains[0]
    a, b = e.evaluate(d), e.evaluate(d)
    assert a == b and a['status'] == 'TRAINABLE'
    assert a['task']['unit'] == 'km/h' and a['evaluationOnly'] and not a['apiPublication']
    for split in ('validation', 'test'):
        for name in e.NAMES:
            r = a[split][name]
            assert len(r['byHorizon']) == 6 and len(r['windows']) == 2
            assert all(h['count'] == 2 for h in r['byHorizon'])
            assert r['count'] == 12 and 0 <= r['mae'] <= r['rmse']
    assert a['readiness']['sourceType'] == 'synthetic_test'


def test_final_test_poisoning_cannot_select_models(domains):
    d = copy.deepcopy(domains[0]); reference = e.evaluate(d)
    for r in d['rows'][-48:]: r['value'] += 100
    d['normalized_sha256'] = hash_json(d['rows'])
    poisoned = e.evaluate(d)
    assert poisoned['validation'] == reference['validation']
    assert poisoned['selected'] == reference['selected']
    assert poisoned['test'] != reference['test']


def test_baseline_only_does_not_fit_candidate_models(tmp_path):
    result = e.evaluate(dataset(tmp_path, days=4))
    assert result['status'] == 'BASELINE_ONLY' and set(result['test']) == {'naive', 'seasonal'}


def test_missing_validation_or_test_labels_refuse_validity(domains):
    for split in ('validation', 'test'):
        d = copy.deepcopy(domains[0]); task = e.task_profile(d)
        for origin in e.origins(len(d['rows']), task, True)[split]:
            for row in d['rows'][origin:origin + task['horizon']]: row['value'] = None
        d['normalized_sha256'] = hash_json(d['rows'])
        assert e.suitability(d)['status'] == 'TRAINABLE'
        assert e.evaluate(d)['status'] == 'NOT_EVALUABLE'


def test_transfer_uses_source_only_and_does_not_claim_synthetic_generalization(domains, monkeypatch):
    source, target = domains
    maxima = []
    class Model:
        def predict(self, x): return np.asarray([42.] * len(x))
    def fitted(name, rows):
        maxima.append(max(v for x, y in rows for v in y))
        return None if name in e.NAMES[:2] else Model()
    monkeypatch.setattr(e, 'fitted', fitted)
    r = e.transfer(source, target)
    assert r['status'] == 'EVALUATED' and r['realGeneralizationConclusion'] == 'NOT_EVALUABLE'
    assert not r['targetLabelsUsedForFitOrSelection']
    assert all(v < 50 for v in maxima)  # Target domain values are all >50.
    assert set(r['models']) == set(e.NAMES)


@pytest.mark.parametrize('kind', ['same_file', 'same_city', 'renamed_copy', 'incompatible', 'future_source'])
def test_transfer_rejects_fake_isolation_and_time_travel(domains, kind, monkeypatch):
    a, b = copy.deepcopy(domains)
    if kind == 'same_file': b['source_sha256'] = a['source_sha256']
    if kind == 'same_city': b['city_id'] = a['city_id']
    if kind == 'renamed_copy':
        b['rows'] = copy.deepcopy(a['rows'])
        for r in b['rows']: r['entity_id'] = 'renamed'
        b['normalized_sha256'] = hash_json(b['rows'])
    if kind == 'incompatible': b['unit'] = 'mph'
    if kind == 'future_source':
        for r in a['rows']:
            r['timestamp'] = (datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) + timedelta(days=365)).isoformat().replace('+00:00', 'Z')
        a['normalized_sha256'] = hash_json(a['rows'])
        monkeypatch.setattr(e, 'evaluate', lambda d: dict(status='TRAINABLE', selected='naive'))
    assert e.transfer(a, b)['status'] == 'NOT_EVALUABLE'
