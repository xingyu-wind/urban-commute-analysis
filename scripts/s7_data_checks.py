"""V3.2 reproducible synthetic CSV/JSON CLI chain. Never reads external raw files."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
from examples.fixtures import make_long


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    steps = []

    def run(name, action, source, target, *extra, expected=0):
        command = [sys.executable, str(ROOT / 'ml/data_cli.py'), action,
                   '--input', str(source), '--output', str(target), *map(str, extra)]
        with (output / (name + '.txt')).open('x', encoding='utf-8') as log:
            code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
        assert code == expected, (name, code)
        steps.append(dict(name=name, command=command, exitCode=code))
        return json.loads(target.read_text(encoding='utf-8')) if code == 0 else None

    normalized = {}
    for domain, fmt in [('alpha', 'csv'), ('beta', 'json')]:
        folder = output / domain
        raw, _ = make_long(folder, domain=domain, fmt=fmt)
        proposal = run(domain + '-inspect', 'inspect', raw, folder / 'proposal.json', '--synthetic-fixture')
        assert not proposal['executable']
        run(domain + '-unconfirmed', 'convert', raw, folder / 'refused.json', '--config', folder / 'proposal.json', expected=1)
        assert not (folder / 'refused.json').exists()
        run(domain + '-confirm', 'confirm', folder / 'proposal.json', folder / 'confirmed.json',
            '--review', folder / 'review.json', '--actor', 'original-synthetic-fixture-owner',
            '--acknowledgement', proposal['proposalSha256'])
        dataset = folder / 'normalized.json'
        normalized[domain] = dataset
        converted = run(domain + '-convert', 'convert', raw, dataset, '--config', folder / 'confirmed.json')
        assert converted['source_type'] == 'synthetic_test' and converted['target'] == 'speed'
        assert converted['unit'] == 'km/h' and converted['spatial_grain'] == 'SENSOR'
        assert converted['rows'][0]['timestamp'] == '2023-12-31T16:00:00.000Z'
        readiness = run(domain + '-quality', 'quality', dataset, folder / 'quality.json')
        assert readiness['status'] == 'TRAINABLE'
        report = run(domain + '-evaluate', 'evaluate', dataset, folder / 'evaluation.json')
        repeated = run(domain + '-repeat', 'evaluate', dataset, folder / 'evaluation-repeat.json')
        assert report == repeated and report['evaluationOnly'] and not report['apiPublication']
        assert set(report['test']) == {'naive', 'seasonal', 'random_forest', 'xgboost'}
        for score in report['test'].values():
            assert score['count'] == 12 and len(score['windows']) == 2 and len(score['byHorizon']) == 6
    transfer = run('transfer', 'transfer', normalized['alpha'], output / 'transfer.json', '--target', normalized['beta'])
    assert transfer['status'] == 'EVALUATED' and transfer['realGeneralizationConclusion'] == 'NOT_EVALUABLE'
    assert not transfer['targetLabelsUsedForFitOrSelection'] and transfer['exactOverlapRatio'] == 0
    same = run('same-domain', 'transfer', normalized['alpha'], output / 'same-domain.json', '--target', normalized['alpha'])
    assert same['status'] == 'NOT_EVALUABLE'
    summary = dict(passed=True, sourceType='synthetic_test', realTrafficConclusion='NOT_EVALUABLE',
                   sameInputEvaluationExactlyReproduced=True, models=list(transfer['models']), steps=steps)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print('S7_DATA=PASS; synthetic CLI, confirmation refusal, two domains, four models and exact reproducibility')


if __name__ == '__main__': main()
