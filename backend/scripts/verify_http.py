"""Start only this project's packaged jar, validate real HTTP, and stop owned processes.

Run with contracts/.venv/Scripts/python.exe. No server-side fault routes are added.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
sys.path.insert(0, str(REPOSITORY / "contracts"))
from validate_contract import body_errors, error_summary, load_contract  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BACKEND / "target" / "live-http-evidence")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)  # Preserve prior evidence, never overwrite it.
    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        raise RuntimeError("Set JAVA_HOME for this process before running")
    java = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
    jar = BACKEND / "target" / "urban-commute-backend-0.1.0-SNAPSHOT.jar"
    if not jar.is_file():
        raise RuntimeError("Build the executable jar with mvnw.cmd verify first")
    spec, registry, checker = load_contract()
    evidence = []
    processes = []
    junit_evidence = []
    started_at = datetime.now(timezone.utc)

    def capture(port, name, path, status=200, contract_path="/api/v1/cities",
                method="GET", accept="application/json", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            connection.request(method, path, body=body, headers={"Accept": accept})
            response = connection.getresponse()
            raw = response.read()
            headers = {key: response.getheader(key) for key in ("Content-Type", "Allow", "X-Request-Id")}
            actual_status = response.status
        finally:
            connection.close()
        (output / (name + ".json")).write_bytes(raw)
        assert actual_status == status, f"{name}: HTTP {actual_status}, expected {status}"
        assert headers["Content-Type"].startswith("application/json"), name
        payload = json.loads(raw)
        errors = body_errors(spec, registry, checker, contract_path, str(status), payload)
        assert not errors, name + ": " + error_summary(errors)
        request_id = headers["X-Request-Id"]
        uuid.UUID(request_id)
        if "meta" in payload:
            assert payload["meta"]["requestId"] == request_id, name
        if status == 405:
            assert "GET" in headers["Allow"], name
        row = {"name": name, "method": method, "url": f"http://127.0.0.1:{port}{path}",
               "accept": accept, "requestBody": body, "status": actual_status,
               "contractPath": contract_path, "headers": headers,
               "bodyFile": name + ".json", "schemaValidation": "PASS"}
        evidence.append(row)
        print(f"PASS {name} HTTP={status} SCHEMA=PASS requestId={request_id}", flush=True)
        return payload

    def run_server(mode):
        command = [str(java), "-jar", str(jar), "--server.address=127.0.0.1", "--server.port=0"]
        if mode == "empty":
            command.append("--commute.cities.dataset-filter=absent-ci-dataset")
        with (output / (mode + "-server.log")).open("x", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=BACKEND, stdout=log, stderr=subprocess.STDOUT)
            row = {"mode": mode, "pid": process.pid, "command": command,
                   "startedAt": datetime.now(timezone.utc).isoformat()}
            processes.append(row)
            try:
                deadline = time.monotonic() + 90
                port = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"{mode} server exited at startup: {process.returncode}")
                    text = (output / (mode + "-server.log")).read_text(encoding="utf-8", errors="replace")
                    match = re.search(r"Tomcat started on port (\d+)", text)
                    if match and "Started UrbanCommuteApplication" in text:
                        port = int(match.group(1)); break
                    time.sleep(0.2)
                if port is None:
                    raise RuntimeError(f"{mode} server did not become ready")
                row["port"] = port
                if mode == "empty":
                    payload = capture(port, "cities-empty", "/api/v1/cities")
                    assert payload["data"] == []
                    return
                health = capture(port, "health", "/health", contract_path="/health")
                next_health = capture(port, "health-next", "/health", contract_path="/health")
                for item in (health, next_health):
                    stamp = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
                    assert started_at <= stamp <= datetime.now(timezone.utc)
                assert health["timestamp"] != next_health["timestamp"]
                first = capture(port, "cities", "/api/v1/cities")
                second = capture(port, "cities-next", "/api/v1/cities")
                assert first["meta"]["requestId"] != second["meta"]["requestId"]
                assert [item["id"] for item in first["data"]] == ["sample-beijing", "sample-shanghai"]
                capture(port, "bad-query", "/api/v1/cities?limit=unexpected", 400)
                capture(port, "get-body", "/health", 400, "/health", body="{}")
                capture(port, "not-found", "/not-a-route", 404)
                capture(port, "wrong-method", "/api/v1/cities", 405, method="POST")
                capture(port, "health-wrong-method", "/health", 405, "/health", method="POST")
                capture(port, "not-acceptable", "/api/v1/cities", 406, accept="application/xml")
                capture(port, "health-not-acceptable", "/health", 406, "/health", accept="text/plain")
            finally:
                # Popen is the exact child created above; never discover/kill arbitrary port owners.
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=10)
                row["processExitCode"] = process.returncode
                row["stoppedAt"] = datetime.now(timezone.utc).isoformat()
                row["stopMethod"] = "terminate owned Popen child; Windows may report nonzero termination"
                row["stopped"] = process.poll() is not None

    exit_code = 0
    try:
        test_directory = BACKEND / "target" / "http-test-evidence"
        for name in ("health", "cities", "cities-empty", "error-500", "error-503"):
            metadata = json.loads((test_directory / (name + ".http.json")).read_text(encoding="utf-8"))
            captured = datetime.fromisoformat(metadata["capturedAt"].replace("Z", "+00:00"))
            age = (started_at - captured).total_seconds()
            if not 0 <= age <= 600:
                raise ValueError("JUnit HTTP evidence is stale; run Maven Wrapper verify immediately before this script")
            payload = json.loads((test_directory / (name + ".json")).read_text(encoding="utf-8"))
            errors = body_errors(spec, registry, checker, metadata["contractPath"], str(metadata["status"]), payload)
            assert not errors, "JUnit HTTP " + name + ": " + error_summary(errors)
            junit_evidence.append({"name": name, "status": metadata["status"],
                                   "schemaValidation": "PASS",
                                   "testServiceSubstitution": metadata["testServiceSubstitution"]})
            print(f"PASS JUnit real embedded HTTP {name} SCHEMA=PASS", flush=True)
        run_server("synthetic")
        run_server("empty")
    except Exception as error:
        exit_code = 1
        print(f"FAIL {type(error).__name__}: {error}", file=sys.stderr)
    finally:
        summary = {"startedAt": started_at.isoformat(), "finishedAt": datetime.now(timezone.utc).isoformat(),
                   "driverExitCode": exit_code, "javaOptions": os.environ.get("JDK_JAVA_OPTIONS"),
                   "processes": processes, "responses": evidence,
                   "junitHttpValidation": junit_evidence,
                   "scope": "Standalone packaged jar real HTTP; empty mode uses configuration, no test service mocks"}
        (output / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"LIVE_HTTP_RESPONSES={len(evidence)} DRIVER_EXIT={exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
