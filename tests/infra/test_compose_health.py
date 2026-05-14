import pytest

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
