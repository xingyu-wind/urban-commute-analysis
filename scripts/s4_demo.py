"""Start a local S4 demo inside s3_database.py's NEW scoped database environment.

Build the JAR and npm ci first. Stops only its own child processes on Ctrl+C.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from s4_database import sql

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-port', type=int, default=8080)
    parser.add_argument('--vite-port', type=int, default=5173)
    parser.add_argument('--smoke-seconds', type=int, help='Exit after readiness for automated startup verification')
    args = parser.parse_args()
    for port in (args.java_port, args.vite_port):
        if not 1024 <= port <= 65535:
            raise ValueError('Use a non-privileged local port')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    if args.java_port == args.vite_port:
        raise ValueError('Java and Vite need different ports')
    sql('SELECT 1;')  # Actual schema/account/version/server identity gate before migration or fixture.
    if sql('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE();') != '0':
        raise ValueError('Demo requires a newly provisioned empty schema')
    output = ROOT / 'backend/target' / ('s4-demo-' + os.environ['DB_USER'])
    output.mkdir(exist_ok=False)
    children, logs = [], []

    def launch(name, command, env):
        log = (output / (name + '.log')).open('x', encoding='utf-8')
        logs.append(log)
        options = {'cwd': ROOT, 'env': env, 'stdout': log, 'stderr': subprocess.STDOUT}
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NO_WINDOW
        child = subprocess.Popen(command, **options)
        children.append(child)
        return child

    def ready(url, child):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError('Owned demo service exited; inspect ' + str(output))
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        return
            except (OSError, TimeoutError):
                pass
            time.sleep(.2)
        raise RuntimeError('Demo startup timed out')

    try:
        java = str(Path(os.environ['JAVA_HOME']) / 'bin' / ('java.exe' if os.name == 'nt' else 'java'))
        backend = launch('java', [java, '-jar', str(ROOT / 'backend/target/urban-commute-backend-0.1.0-SNAPSHOT.jar'),
                         '--server.address=127.0.0.1', '--server.port=' + str(args.java_port)], os.environ.copy())
        ready(f'http://127.0.0.1:{args.java_port}/health', backend)
        subprocess.run([sys.executable, str(ROOT / 'scripts/s4_database.py'), 'fixture'], check=True)
        subprocess.run([sys.executable, str(ROOT / 'scripts/s4_database.py'), 'oracle'], check=True)
        frontend = launch('vite', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), str(ROOT / 'frontend'),
                          '--host', '127.0.0.1', '--port', str(args.vite_port), '--strictPort'],
                          {**os.environ, 'DEV_BACKEND_URL': f'http://127.0.0.1:{args.java_port}'})
        url = f'http://127.0.0.1:{args.vite_port}'
        ready(url, frontend)
        print('S4_DEMO_READY ' + url + ' | select S4 synthetic city, click synthetic sample window | Ctrl+C to stop', flush=True)
        start = time.monotonic()
        while args.smoke_seconds is None or time.monotonic() - start < args.smoke_seconds:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Owned demo process exited unexpectedly')
            time.sleep(.2)
    except KeyboardInterrupt:
        print('Stopping owned demo services', flush=True)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
