import pytest
import requests

from tests.conftest import service_state, wait_until


REQUIRED_SERVICES = [
    "hms-db",
    "namenode",
    "datanode",
    "resourcemanager",
    "nodemanager",
    "hive-metastore",
    "kafka",
    "starrocks",
    "neo4j",
]


@pytest.mark.infra
@pytest.mark.parametrize("service", REQUIRED_SERVICES)
def test_service_is_healthy(service):
    state = wait_until(
        lambda: service_state(service) if service_state(service).get("Health") in ("healthy", "") else None,
        timeout=180,
        desc=f"service {service} healthy",
    )
    assert state, f"service {service} not present in compose output"
    assert state["State"] == "running", f"{service} state={state['State']!r}"
    # Some images may not declare a healthcheck; in that case Health == "".
    health = state.get("Health", "")
    assert health in ("healthy", ""), f"{service} health={health!r}"


@pytest.mark.infra
def test_namenode_web_ui_reachable():
    response = wait_until(
        lambda: _safe_get("http://localhost:9870/dfshealth.html"),
        timeout=120,
        desc="HDFS NameNode UI :9870",
    )
    assert response.status_code == 200
    assert "Hadoop" in response.text


def _safe_get(url: str):
    try:
        r = requests.get(url, timeout=3)
        return r if r.status_code < 500 else None
    except requests.RequestException:
        return None


@pytest.mark.infra
def test_yarn_resourcemanager_ui_reachable():
    response = wait_until(
        lambda: _safe_get("http://localhost:8088/ws/v1/cluster/info"),
        timeout=180,
        desc="YARN RM REST :8088",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["clusterInfo"]["state"] == "STARTED"
