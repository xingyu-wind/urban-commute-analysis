"""Authorized empty development schema: real application migration and two startups."""
import argparse
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    java = Path(os.environ['JAVA_HOME']) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
    jar = ROOT / 'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar'
    evidence = []
    for attempt in (1, 2):
        logfile = output / f'start-{attempt}.log'
        with logfile.open('x', encoding='utf-8') as log:
            child = subprocess.Popen([str(java), '-jar', str(jar), '--server.port=0'], cwd=ROOT / 'backend',
                                     stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 90
                port = None
                while time.monotonic() < deadline:
                    text = logfile.read_text(encoding='utf-8', errors='replace')
                    match = re.search(r'Tomcat started on port (\d+)', text)
                    if match and 'Started UrbanCommuteApplication' in text:
                        port = int(match[1]); break
                    if child.poll() is not None:
                        raise RuntimeError('Development application startup failed')
                    time.sleep(0.2)
                if port is None:
                    raise RuntimeError('Development application did not become ready')
                responses = {}
                for path in ('/health', '/api/v1/cities'):
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                    try:
                        connection.request('GET', path, headers={'Accept': 'application/json'})
                        response = connection.getresponse()
                        assert response.status == 200
                        responses[path] = json.loads(response.read())
                    finally:
                        connection.close()
                cities = responses['/api/v1/cities']
                assert cities['data'] == []
                assert cities['meta']['sourceType'] == 'database_catalog'
                assert cities['meta']['datasetId'] is None and cities['meta']['dataAsOf'] is None
                assert responses['/health']['status'] == 'UP'
                if attempt == 2:
                    assert 'No migration necessary' in text
                evidence.append({'attempt': attempt, 'port': port, 'responses': responses,
                                 'repeatMigrationSkipped': attempt == 2})
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=15)
    (output / 'summary.json').write_text(json.dumps({'exitCode': 0, 'attempts': evidence}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS real development empty schema migration, two startups, HTTP, no-op repeat')


if __name__ == '__main__':
    main()
