"""Validate actual browser -> Vite -> Java payloads using the WP2 OpenAPI schemas."""
import json
import sys
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'contracts'))
from validate_contract import body_errors, error_summary, load_contract

directory = Path(sys.argv[1])
manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
spec, registry, checker = load_contract()
accepted = []
transport = []
java_logs = '\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in directory.glob('java-*.log'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


started = datetime.fromisoformat(manifest['startedAt'].replace('Z', '+00:00'))
finished = datetime.fromisoformat(manifest['finishedAt'].replace('Z', '+00:00'))
require(manifest['driverExitCode'] == 0 and manifest['noRequestMocking'] is True, 'Browser driver failed or used mocks')
require(not manifest['pageErrors'], 'Uncaught browser error')
require(manifest['cleanup']['remainingOwnedChildren'] == 0 and manifest['cleanup']['javaPortAvailable'] and manifest['cleanup']['vitePortAvailable'], 'Owned processes or ports were not cleaned up')
expected_steps = {'real-beijing-selection', 'real-shanghai-selection-and-source', 'responsive-layout-no-horizontal-overflow',
                  'backend-stop-detected-automatically', 'backend-restart-manual-retry-restored-success',
                  'actual-browser-network-offline-state', 'browser-network-retry-restored-success', 'real-java-empty-list-rendered-as-success'}
require(expected_steps <= {step['name'] for step in manifest['steps']}, 'Incomplete browser regression steps')
request_ids = set()
phases = {}
for response in manifest['responses']:
    require(not response.get('captureError'), 'Failed to capture a real response')
    if response['source'] == 'vite-proxy-transport-failure':
        require(response['phase'] == 'backend-stopped' and response['status'] in (500, 502, 503, 504)
                and not response['headers'].get('x-request-id'), 'Not an actual stopped-backend proxy failure')
        transport.append({'index': response['index'], 'status': response['status'], 'note': 'Vite infrastructure error, not a Java OpenAPI error envelope'})
        continue
    require(response['source'] == 'java-via-vite' and response['status'] == 200, 'Java response did not succeed')
    body = json.loads((directory / response['bodyFile']).read_text(encoding='utf-8'))
    errors = body_errors(spec, registry, checker, response['contractPath'], str(response['status']), body)
    require(not errors, error_summary(errors))
    request_id = response['headers']['x-request-id']
    require(request_id not in request_ids, 'Duplicate historical requestId reused')
    request_ids.add(request_id)
    require(re.search(r'requestId=' + re.escape(request_id) + r'\s', java_logs), 'Browser response must correlate to an actual Java request log')
    if 'meta' in body:
        require(body['meta']['requestId'] == request_id, 'RequestId header/body mismatch')
        if response['phase'] == 'empty':
            require(body['data'] == [], 'Empty-list configuration did not return []')
    else:
        timestamp = datetime.fromisoformat(body['timestamp'].replace('Z', '+00:00'))
        require(started <= timestamp <= finished, 'Historical health timestamp outside this regression run')
    phases.setdefault(response['phase'], set()).add(response['contractPath'])
    accepted.append({'index': response['index'], 'path': response['contractPath'], 'phase': response['phase'], 'requestId': request_id, 'schemaValidation': 'PASS', 'javaLogCorrelation': 'PASS'})
for phase in ('initial', 'restored', 'network-restored', 'empty'):
    require(phases.get(phase) == {'/health', '/api/v1/cities'}, 'Missing real endpoint response in phase: ' + phase)
require({row['contractPath'] for row in manifest['responses'] if row['source'] == 'vite-proxy-transport-failure'} == {'/health', '/api/v1/cities'}, 'Backend-stop test must capture both actual proxy failures')
result = {'exitCode': 0, 'javaResponsesAccepted': accepted, 'infrastructureFailures': transport, 'note': 'Real captured browser responses; no mock success payloads'}
(directory / 'schema-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'CAPTURED_OPENAPI_VALIDATION=PASS; JAVA_RESPONSES={len(accepted)}; PROXY_FAILURES={len(transport)}; JAVA_LOG_CORRELATION=PASS')
