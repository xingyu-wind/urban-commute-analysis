"""S7 real training -> S5/S6 lineage -> isolated MySQL -> Java HTTP -> Chromium."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
from forecast import admit, publish, connect, write_json
from s7_fixture import generate, START, CUTOFF


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release-checks', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    steps, negatives = [], []
    passed = False
    def run(name, cmd, cwd=ROOT, expected=0):
        with (output / (name + '.log')).open('x', encoding='utf-8') as log:
            code = subprocess.run(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT).returncode
        if code != expected:
            raise RuntimeError(name + ' failed, inspect log; exit=' + str(code))
        steps.append(dict(name=name, command=list(map(str, cmd)), exitCode=code))
        print('PASS ' + name, flush=True)
    def reject(name, action):
        try: action()
        except ValueError: negatives.append(name); return
        raise AssertionError(name + ' accepted unexpectedly')
    def current():
        c = connect()
        try:
            with c.cursor() as cur:
                cur.execute('SELECT job_id FROM prediction_current WHERE city_id=%s AND dataset_id=%s', ('s7-city', 's7-synthetic-v1'))
                return cur.fetchone()['job_id']
        finally: c.close()
    try:
        maven = ['cmd', '/c', 'backend\\mvnw.cmd'] if os.name == 'nt' else ['bash', 'backend/mvnw']
        npm = ['cmd', '/c', 'npm'] if os.name == 'nt' else ['npm']
        run('backend', maven + ['-f', 'backend/pom.xml', '-B', '-ntp', 'verify'])
        run('python-unit', [sys.executable, '-m', 'pytest', 'ml/tests', '-q', '--junitxml=' + str(output / 'pytest.xml')])
        run('frontend-types', npm + ['run', 'type-check'], ROOT / 'frontend')
        run('frontend-unit', npm + ['test', '--', '--reporter=json', '--outputFile=' + str(output / 'frontend-unit.json')], ROOT / 'frontend')
        run('frontend-build', npm + ['run', 'build'], ROOT / 'frontend')
        fixture = generate(output / 'fixture')
        etl = output / 'etl'
        run('etl', [sys.executable, '-m', 'commute_etl', '--config', str(fixture / 'config.json'),
            '--input', str(fixture / 'traffic.json'), '--batch', 's7-history', '--load', '--output', str(etl)], ROOT / 'data-pipeline')
        report = json.loads((etl / 'batch.json').read_text(encoding='utf-8'))
        assert report['status'] == 'SUCCEEDED' and report['written_count'] == 4368 and report['rejected_count'] == 0
        prefix = [sys.executable, 'ml/forecast.py']
        train_args = ['--batch-output', str(etl), '--city', 's7-city', '--dataset', 's7-synthetic-v1', '--from', START, '--cutoff', CUTOFF]
        run('train', prefix + ['train', '--output', str(output / 'train')] + train_args)
        run('train-repeat', prefix + ['train', '--output', str(output / 'repeat')] + train_args)
        result = json.loads((output / 'train/run.json').read_text(encoding='utf-8'))
        repeat = json.loads((output / 'repeat/run.json').read_text(encoding='utf-8'))
        stable = lambda r: {k: v for k, v in r.items() if k not in ('trainedAt', 'generatedAt')}
        assert stable(result) == stable(repeat)
        assert (output / 'train/evaluation.json').read_bytes() == (output / 'repeat/evaluation.json').read_bytes()
        write_json(output / 'reproducibility.json', dict(passed=True, sameInputConfiguration=True,
            sameEvaluationBytes=True, sameModelArtifact=True, modelVersion=result['modelVersion']))
        first = publish(output / 'train', [etl])
        assert not first['reused'] and publish(output / 'train', [etl])['reused']
        assert publish(output / 'repeat', [etl])['reused']
        visible = first['jobId']
        assert first['verification']['verifiedPredictionCount'] == 7
        import shutil
        tampered = output / 'tampered-forecast'
        shutil.copytree(output / 'train', tampered)
        changed = copy.deepcopy(result)
        changed['predictions'][3]['value'] = round(changed['predictions'][3]['value'] + .125, 6)
        assert 0 <= changed['predictions'][3]['value'] <= 10
        write_json(tampered / 'run.json', changed)
        reject('legal-value-tampering-independent-replay', lambda: publish(tampered, [etl]))
        assert current() == visible
        c = connect()
        with c.cursor() as cur:
            cur.execute('SELECT COUNT(*) n FROM prediction_job')
            assert cur.fetchone()['n'] == 1
            cur.execute('SELECT value FROM prediction_result WHERE job_id=%s AND step=4', (visible,))
            assert float(cur.fetchone()['value']) == result['predictions'][3]['value']
        c.close()
        write_json(output / 'prediction-integrity.json', dict(passed=True, mutatedStep=4,
            originalValue=result['predictions'][3]['value'], tamperedValue=changed['predictions'][3]['value'],
            sameInput=True, legalDatesAndRange=True, rejected=True, pointerUnchanged=visible,
            erroneousJobRows=0, verification=first['verification']))
        # Separate candidate generated times exercise failure/retry with the exact same model.
        candidate = output / 'candidate'
        shutil.copytree(output / 'train', candidate)
        doc = copy.deepcopy(result)
        from datetime import datetime, timedelta, timezone
        from forecast import stamp, timestamp
        def next_generation():
            doc['generatedAt'] = stamp(max(datetime.now(timezone.utc).replace(tzinfo=None), timestamp(doc['generatedAt']) + timedelta(milliseconds=1)))
        for failure in ('insert', 'commit', 'switch'):
            next_generation()
            doc['limitation'] = result['limitation'] + ' 发布恢复检查 ' + failure
            write_json(candidate / 'run.json', doc)
            try:
                publish(candidate, [etl], fail_at=failure)
                raise AssertionError('failure hook did not fail')
            except RuntimeError as error:
                assert 'injected' in str(error)
            assert current() == visible
            c = connect()
            with c.cursor() as cur:
                cur.execute("SELECT COUNT(*) n FROM prediction_result r JOIN prediction_job j USING(job_id) WHERE j.status='FAILED'")
                assert cur.fetchone()['n'] == 0
            c.close()
            retry = publish(candidate, [etl])
            assert not retry['reused']
            visible = retry['jobId']
            assert current() == visible
            negatives.append(failure + '-rollback-retry')
        # Uncatchable subprocess death leaves durable STAGING and rolls back all result rows/current.
        doc['limitation'] = result['limitation'] + ' 硬中断恢复检查'
        next_generation()
        write_json(candidate / 'run.json', doc)
        crash_code = "import sys; sys.path.insert(0,'ml'); from forecast import publish; publish(sys.argv[1],[sys.argv[2]],fail_at='crash')"
        run('hard-crash', [sys.executable, '-c', crash_code, str(candidate), str(etl)], expected=73)
        assert current() == visible
        c = connect()
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM prediction_job WHERE status='STAGING'")
            assert cur.fetchone()['n'] == 1
            cur.execute("SELECT COUNT(*) n FROM prediction_result r JOIN prediction_job j USING(job_id) WHERE j.status='STAGING'")
            assert cur.fetchone()['n'] == 0
        c.close()
        visible = publish(candidate, [etl])['jobId']
        negatives.append('hard-crash-rollback-safe-recovery')
        # A fresh newer generation is visible; old successful replay cannot move it backwards.
        doc['limitation'] = result['limitation']
        next_generation()
        write_json(candidate / 'run.json', doc)
        # generation time alone is excluded from identity; change an explicit review note to make a distinct job.
        doc['limitation'] += ' 完整验证发布'
        write_json(candidate / 'run.json', doc)
        visible = publish(candidate, [etl])['jobId']
        successful_document = copy.deepcopy(doc)
        assert publish(output / 'train', [etl])['reused'] and current() == visible
        old = copy.deepcopy(result); old['limitation'] += ' stale'
        write_json(candidate / 'run.json', old)
        reject('stale-generation', lambda: publish(candidate, [etl]))
        # Leave a real FAILED job as final state while current remains queryable.
        next_generation()
        doc['limitation'] += ' 最终失败检查'
        write_json(candidate / 'run.json', doc)
        try: publish(candidate, [etl], fail_at='switch')
        except RuntimeError: pass
        assert current() == visible
        same_generation = copy.deepcopy(successful_document)
        same_generation['limitation'] += ' ambiguous generation'
        write_json(candidate / 'run.json', same_generation)
        reject('same-generation-cannot-overwrite', lambda: publish(candidate, [etl]))
        invalid = copy.deepcopy(successful_document)
        invalid['predictions'][1]['date'] = invalid['predictions'][0]['date']
        write_json(candidate / 'run.json', invalid)
        reject('noncontinuous-prediction', lambda: publish(candidate, [etl]))
        write_json(candidate / 'run.json', successful_document)
        artifact = candidate / 'model.joblib'
        original_bytes = artifact.read_bytes()
        artifact.write_bytes(original_bytes + b'changed')
        reject('artifact-checksum', lambda: publish(candidate, [etl]))
        artifact.write_bytes(original_bytes)
        reject('duplicate-batch-input', lambda: publish(output / 'train', [etl, etl]))
        bad = output / 'bad-etl'
        shutil.copytree(etl, bad)
        altered = json.loads((bad / 'normalized.json').read_text(encoding='utf-8')); altered[0]['congestion_index'] = '9.99'
        write_json(bad / 'normalized.json', altered)
        reject('changed-committed-input', lambda: publish(output / 'train', [bad]))
        failed_report = json.loads((bad / 'batch.json').read_text(encoding='utf-8'))
        failed_report['status'] = 'FAILED'
        write_json(bad / 'batch.json', failed_report)
        reject('failed-batch-input', lambda: publish(output / 'train', [bad]))
        c = connect()
        with c.cursor() as cur:
            cur.execute("UPDATE dataset_registry SET dataset_version='2' WHERE dataset_id='s7-synthetic-v1'")
        c.commit(); c.close()
        try: reject('changed-dataset-version', lambda: publish(output / 'train', [etl]))
        finally:
            c = connect()
            with c.cursor() as cur: cur.execute("UPDATE dataset_registry SET dataset_version='1' WHERE dataset_id='s7-synthetic-v1'")
            c.commit(); c.close()
        c = connect()
        with c.cursor() as cur:
            cur.execute('SELECT job_id,status,attempts,model_version,data_cutoff,generated_at,published_at FROM prediction_job ORDER BY generated_at,job_id')
            jobs = cur.fetchall()
            cur.execute('SELECT j.document FROM prediction_current c JOIN prediction_job j USING(job_id) WHERE c.job_id=%s', (visible,))
            published = json.loads(cur.fetchone()['document'])
            cur.execute('SELECT * FROM prediction_result WHERE job_id=%s ORDER BY step', (visible,))
            points = cur.fetchall()
            cur.execute('SELECT COUNT(*) n FROM warehouse_current')
            assert cur.fetchone()['n'] == 0
            cur.execute('SELECT COUNT(*) n FROM prediction_evaluation WHERE job_id=%s', (visible,))
            assert cur.fetchone()['n'] == 8
        c.close()
        assert len(points) == 7 and [float(p['value']) for p in points] == [p['value'] for p in result['predictions']]
        evaluation = json.loads((output / 'train/evaluation.json').read_text(encoding='utf-8'))
        write_json(output / 'expected.json', dict(jobId=visible, result=published, evaluation=evaluation))
        write_json(output / 'mysql-publication.json', dict(passed=True, visible=visible, jobs=jobs, points=points, negativeCases=negatives))
        run('browser', ['node', 'frontend/scripts/verify-s7.mjs', str(output / 'browser'), str(output / 'expected.json')])
        if args.release_checks:
            run('s9-release', [sys.executable, 'scripts/s9_release_checks.py', '--output', str(output/'s9-release')])
        passed = True
        return 0
    finally:
        write_json(output / 'summary.json', dict(passed=passed, steps=steps, negativeCases=negatives))


if __name__ == '__main__':
    sys.exit(main())
