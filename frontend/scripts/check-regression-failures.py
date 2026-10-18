"""Prove the existing regression validators reject broken real captures and startup.

Run only after a successful real browser regression. This is verifier fault testing,
not mock data presented as a successful API or browser integration.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = Path(sys.argv[1]).resolve()
report_directory = Path(sys.argv[2]).resolve()
report_directory.mkdir(parents=True, exist_ok=False)
manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
validator = ROOT / 'frontend/scripts/validate-captures.py'
results = []


def mutate_body(directory, predicate, mutation):
    row = next(row for row in manifest['responses'] if predicate(row))
    file = directory / row['bodyFile']
    body = json.loads(file.read_text(encoding='utf-8'))
    mutation(body)
    file.write_text(json.dumps(body, ensure_ascii=False), encoding='utf-8')


cases = {
    'reject-real-time-source': lambda directory: mutate_body(directory,
        lambda row: row['phase'] == 'initial' and row['contractPath'] == '/api/v1/cities',
        lambda body: body['meta'].update(sourceType='real_time')),
    'reject-missing-required-null': lambda directory: mutate_body(directory,
        lambda row: row['phase'] == 'initial' and row['contractPath'] == '/api/v1/cities',
        lambda body: body['meta'].pop('dataAsOf')),
    'reject-historical-timestamp': lambda directory: mutate_body(directory,
        lambda row: row['phase'] == 'initial' and row['contractPath'] == '/health',
        lambda body: body.update(timestamp='2000-01-01T00:00:00Z')),
    'reject-null-cities': lambda directory: mutate_body(directory,
        lambda row: row['phase'] == 'initial' and row['contractPath'] == '/api/v1/cities',
        lambda body: body.update(data=None)),
    'reject-missing-java-log': lambda directory: [p.write_text('', encoding='utf-8') for p in directory.glob('java-*.log')],
}
for name, mutation in cases.items():
    with tempfile.TemporaryDirectory(prefix=name + '-', dir=report_directory) as temporary:
        directory = Path(temporary)
        for file in source.iterdir():
            if file.suffix in ('.json', '.txt', '.log'):
                shutil.copyfile(file, directory / file.name)
        mutation(directory)
        result = subprocess.run([sys.executable, str(validator), str(directory)], capture_output=True, text=True, encoding='utf-8')
        (report_directory / (name + '.txt')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode == 0:
            raise RuntimeError('Broken real capture was incorrectly accepted: ' + name)
        results.append({'name': name, 'childExitCode': result.returncode, 'expectedNonzero': True})
        print('PASS ' + name + '; actual rejection exit=' + str(result.returncode), flush=True)

# A real process-launch failure must fail the actual E2E entry point; do not mock HTTP.
node = shutil.which('node')
environment = dict(os.environ, JAVA_HOME=str(report_directory / 'missing-jdk'))
failure_output = report_directory / 'java-startup-failure'
result = subprocess.run([node, str(ROOT / 'frontend/scripts/verify-integration.mjs'), str(failure_output)],
                        cwd=ROOT / 'frontend', env=environment, capture_output=True, text=True, encoding='utf-8', timeout=45)
(report_directory / 'java-startup-failure.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
failure_manifest = json.loads((failure_output / 'manifest.json').read_text(encoding='utf-8'))
if result.returncode == 0 or failure_manifest['driverExitCode'] == 0 or failure_manifest['cleanup']['remainingOwnedChildren'] != 0:
    raise RuntimeError('Actual Java startup failure was hidden or leaked owned processes')
results.append({'name': 'actual-java-startup-failure', 'childExitCode': result.returncode, 'expectedNonzero': True,
                'cleanup': failure_manifest['cleanup']})
(report_directory / 'summary.json').write_text(json.dumps({'exitCode': 0, 'checks': results}, indent=2) + '\n', encoding='utf-8')
print('PASS actual-java-startup-failure; driver exit=' + str(result.returncode), flush=True)
