"""Independent leakage, UTC coverage, recursive horizon and selection checks."""
import copy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forecast as f


def records(days=365):
    rows = []
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(days):
        for hour in (0, 6, 12, 18):
            t = start + timedelta(days=i, hours=hour, minutes=17)
            rows.append(dict(city_id='test-city', target_id='test-city', target_type='CITY', dataset_id='test-v1',
                dataset_version='1', source_type='synthetic_test', observed_at=f.stamp(t), collected_at=f.stamp(t + timedelta(minutes=1)),
                congestion_index=str(hour / 6), observation_id=len(rows), batch_id='test', source_sha256='a' * 64))
    return rows, f.stamp(start + timedelta(days=days))


def test_daily_utc_mean_and_lineage_dedup():
    rows, cutoff = records()
    result = f.daily(rows + [dict(rows[0], batch_id='repeat')], 'test-city', 'test-v1', cutoff)
    assert len(result) == 365 and result[0] == dict(date='2024-01-01', value=1.5, sampleCount=4)


@pytest.mark.parametrize('mutation', ['short', 'gap', 'sparse', 'slot', 'version', 'late', 'future', 'no-midnight', 'nan'])
def test_invalid_history_fails_closed(mutation):
    rows, cutoff = records()
    if mutation == 'short': rows = rows[4:]
    if mutation == 'gap': rows = rows[:400] + rows[404:]
    if mutation == 'sparse': rows = rows[1:]
    if mutation == 'slot': rows[1]['observed_at'] = '2024-01-01T01:17:00.000Z'
    if mutation == 'version': rows[1]['dataset_version'] = '2'
    if mutation == 'late': rows[0]['collected_at'] = '2024-01-02T00:00:00.000Z'
    if mutation == 'future': rows[-1]['observed_at'] = cutoff
    if mutation == 'no-midnight': cutoff = cutoff.replace('00:00:00', '01:00:00')
    if mutation == 'nan': rows[0]['congestion_index'] = 'NaN'
    with pytest.raises((ValueError, ArithmeticError)):
        f.daily(rows, 'test-city', 'test-v1', cutoff)


def test_city_region_dataset_isolation():
    rows, cutoff = records()
    polluted = [dict(r, target_type='REGION', congestion_index='10') for r in rows]
    polluted += [dict(r, dataset_id='other-v1', congestion_index='10') for r in rows]
    assert f.daily(rows + polluted, 'test-city', 'test-v1', cutoff) == f.daily(rows, 'test-city', 'test-v1', cutoff)


def test_shifted_features_are_independently_correct():
    h = list(range(1, 29))
    x = f.features(h, date(2024, 1, 29))
    assert x[:4] == [28, 22, 15, 1]
    assert x[4] == 25 and x[5] == 14.5 and x[6] == np.std([22, 23, 24, 25, 26, 27, 28])
    assert x[7:9] == [0, 0]


def test_recursive_model_never_sees_future_actuals():
    class Spy:
        def __init__(self): self.rows = []
        def predict(self, x): self.rows.append(x[0].tolist()); return np.array([x[0][0] + 1])
    model = Spy()
    result = f.predict('random_forest', model, [1] * 28, date(2024, 2, 1))
    assert result == [2, 3, 4, 5, 6, 7, 8]
    assert [r[0] for r in model.rows] == [1, 2, 3, 4, 5, 6, 7]


def test_baselines_and_clipping():
    assert f.predict('naive', None, [3] * 28, date(2024, 2, 1)) == [3] * 7
    assert f.predict('seasonal7', None, list(range(4)) * 7, date(2024, 2, 1)) == [1, 2, 3, 0, 1, 2, 3]
    class OutOfRange:
        def predict(self, x): return [99]
    assert f.predict('xgboost', OutOfRange(), [3] * 28, date(2024, 2, 1)) == [10] * 7


def test_backtest_prefix_and_future_poisoning(monkeypatch):
    calls = []
    def fit(name, values, start): calls.append(list(values)); return None
    monkeypatch.setattr(f, 'fit', fit)
    values = [3.] * 49
    original = f.backtest('seasonal7', values, date(2024, 1, 1), [28, 35])
    values[28:35] = [9.] * 7
    poisoned = f.backtest('seasonal7', values, date(2024, 1, 1), [28])
    assert original['windows'][0]['predictions'] == poisoned['windows'][0]['predictions']
    assert [len(c) for c in calls] == [28, 35, 28]
    assert poisoned['mae'] == 6 and poisoned['rmse'] == 6


def test_selection_baseline_fallback_and_ties():
    scores = {n: dict(mae=1., rmse=1.) for n in f.NAMES}
    assert f.choose(scores) == 'naive'
    scores['random_forest']['mae'] = .995
    assert f.choose(scores) == 'naive'
    scores['random_forest']['mae'] = .98
    assert f.choose(scores) == 'random_forest'


@pytest.mark.parametrize('name', ['random_forest', 'xgboost'])
def test_seeded_model_reproducibility(name):
    values = [4 + np.sin(i / 7) for i in range(90)]
    a, b = f.fit(name, values, date(2024, 1, 1)), f.fit(name, values, date(2024, 1, 1))
    assert f.predict(name, a, values, date(2024, 3, 31)) == f.predict(name, b, values, date(2024, 3, 31))


def test_test_set_never_selects_model(monkeypatch, tmp_path):
    calls = []
    def bt(name, values, start, origins):
        calls.append((name, list(origins)))
        # Validation prefers seasonal7, test deliberately prefers xgboost.
        return dict(mae=0. if name == ('seasonal7' if origins[0] == 309 else 'xgboost') else 1., rmse=1.)
    monkeypatch.setattr(f, 'backtest', bt)
    series = [dict(date=(date(2024, 1, 1) + timedelta(days=i)).isoformat(), value=3., sampleCount=4) for i in range(365)]
    identity = dict(cutoff='2024-12-31T00:00:00.000Z', dataset_version='1', city='test-city', dataset='test-v1', source_type='synthetic_test',
                    batch_ids=['test'], source_hashes=['a' * 64], observed_to='2024-12-30T18:17:00.000Z')
    result = f.train(series, identity, tmp_path / 'train')
    assert result['modelName'] == 'seasonal7'
    assert len(result['predictions']) == 7 and result['predictions'][0]['date'] == '2024-12-31'
    assert [n for n, o in calls[:4]] == list(f.NAMES)
