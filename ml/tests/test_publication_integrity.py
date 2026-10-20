"""Scientific integrity checks, including lawful-value tampering and untrusted artifacts."""
import copy
from datetime import date, timedelta
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forecast as f


@pytest.fixture(scope='module')
def trained(tmp_path_factory):
    path = tmp_path_factory.mktemp('integrity') / 'run'
    series = [dict(date=(date(2024, 1, 1) + timedelta(days=i)).isoformat(), value=4., sampleCount=4) for i in range(365)]
    identity = dict(cutoff='2024-12-31T00:00:00.000Z', observed_to='2024-12-30T18:00:00.000Z',
        dataset_version='1', city='unit-city', dataset='unit-v1', source_type='synthetic_test', batch_ids=['batch'], source_hashes=['a' * 64])
    return path, series, identity, f.train(series, identity, path)


def test_verified_without_loading_submitted_pickle(trained, monkeypatch):
    path, series, identity, run = trained
    def forbidden(*args, **kwargs):
        raise AssertionError('untrusted joblib deserialization')
    monkeypatch.setattr(f.joblib, 'load', forbidden)
    assert f.verify_run(path, run, series, identity)['verifiedPredictionCount'] == 7


@pytest.mark.parametrize('step', range(7))
def test_each_lawful_prediction_change_rejected(trained, step):
    path, series, identity, original = trained
    run = copy.deepcopy(original)
    run['predictions'][step]['value'] += .125
    with pytest.raises(ValueError, match='replay mismatch'):
        f.verify_run(path, run, series, identity)


@pytest.mark.parametrize('kind', ['config', 'lock', 'evaluation', 'model'])
def test_self_declared_configuration_or_digest_is_not_authority(trained, tmp_path, kind):
    import shutil
    path, series, identity, original = trained
    candidate = tmp_path / 'candidate'; shutil.copytree(path, candidate)
    run = copy.deepcopy(original)
    if kind == 'config': run['config']['seed'] += 1
    if kind == 'lock': run['config']['lock_sha256']['ml/requirements.lock.txt'] = 'f' * 64
    if kind == 'evaluation':
        e = json.loads((candidate / 'evaluation.json').read_text(encoding='utf-8'))
        e['test']['naive']['mae'] = .1
        f.write_json(candidate / 'evaluation.json', e)
        run['artifacts']['evaluation.json'] = f.sha(candidate / 'evaluation.json')
    if kind == 'model':
        (candidate / 'model.joblib').write_bytes(b'not a trusted model')
        run['artifacts']['model.joblib'] = f.sha(candidate / 'model.joblib')
    with pytest.raises(ValueError):
        f.verify_run(candidate, run, series, identity)
