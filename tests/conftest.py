import json
import subprocess
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = REPO_ROOT / "base-compose.yml"
SHARED_INFRA_ROOT = REPO_ROOT.parent / "shared-data-infra"
SHARED_COMPOSE_FILES = [
    SHARED_INFRA_ROOT / "compose.yaml",
    SHARED_INFRA_ROOT / "compose.lakehouse.yaml",
    SHARED_INFRA_ROOT / "compose.streaming.yaml",
    SHARED_INFRA_ROOT / "compose.starrocks.yaml",
]
SHARED_SERVICES = {
    "hms-db",
    "namenode",
    "datanode",
    "resourcemanager",
    "nodemanager",
    "hive-metastore",
    "kafka",
    "starrocks",
}


def _compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _shared_compose(*args: str) -> subprocess.CompletedProcess:
    command = ["docker", "compose"]
    for compose_file in SHARED_COMPOSE_FILES:
        command.extend(["-f", str(compose_file)])
    return subprocess.run(
        [*command, *args],
        cwd=SHARED_INFRA_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.fixture(scope="session")
def compose():
    """Helper to run `docker compose -f base-compose.yml ...`."""
    return _compose


def service_state(service: str) -> dict:
    """Return the JSON state object for one compose service, or {} if absent."""
    compose = _shared_compose if service in SHARED_SERVICES else _compose
    result = compose("ps", "--format", "json", service)
    if result.returncode != 0 or not (result.stdout or "").strip():
        return {}
    # `docker compose ps --format json` emits one JSON object per line.
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("Service") == service:
            return obj
    return {}


def wait_until(predicate, timeout: float = 60.0, interval: float = 2.0, desc: str = ""):
    """Poll `predicate()` until it returns truthy or timeout (seconds)."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"Timed out after {timeout}s waiting for: {desc}; last={last!r}")
