import pytest
import socket
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


@pytest.mark.infra
def test_hive_metastore_thrift_port_open():
    def _check():
        try:
            with socket.create_connection(("localhost", 9083), timeout=2):
                return True
        except OSError:
            return False

    wait_until(_check, timeout=180, desc="Hive Metastore :9083")


@pytest.mark.infra
def test_kafka_broker_reachable():
    from kafka import KafkaAdminClient

    def _check():
        try:
            client = KafkaAdminClient(bootstrap_servers="localhost:9092", request_timeout_ms=3000)
            brokers = client.describe_cluster()
            client.close()
            return len(brokers.get("brokers", [])) >= 1
        except Exception:
            return False

    wait_until(_check, timeout=180, desc="Kafka broker :9092")


@pytest.mark.infra
def test_starrocks_fe_reachable():
    import pymysql

    def _check():
        try:
            conn = pymysql.connect(host="127.0.0.1", port=9030, user="root", password="", connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
            conn.close()
            return row == (1,)
        except Exception:
            return False

    wait_until(_check, timeout=240, desc="StarRocks FE :9030 SELECT 1")


@pytest.mark.infra
def test_neo4j_http_reachable():
    response = wait_until(
        lambda: _safe_get("http://localhost:7474/"),
        timeout=120,
        desc="Neo4j HTTP :7474",
    )
    assert response.status_code == 200
    payload = response.json()
    assert "neo4j_version" in payload, f"unexpected response payload: {payload!r}"


@pytest.mark.infra
def test_p1_1_all_services_healthy():
    """P1-1: every required service is running + healthy; NN/RM UIs reachable."""
    for service in REQUIRED_SERVICES:
        state = service_state(service)
        assert state, f"{service} not present"
        assert state["State"] == "running", f"{service} state={state['State']!r}"
        health = state.get("Health", "")
        assert health in ("healthy", ""), f"{service} health={health!r}"

    nn = _safe_get("http://localhost:9870/dfshealth.html")
    assert nn is not None and nn.status_code == 200, "NN UI unreachable"

    rm = _safe_get("http://localhost:8088/ws/v1/cluster/info")
    assert rm is not None and rm.status_code == 200, "RM REST unreachable"
    assert rm.json()["clusterInfo"]["state"] == "STARTED"
