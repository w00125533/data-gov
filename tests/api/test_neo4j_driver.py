import pytest

from backend.metadata.graph import get_driver, run_query


@pytest.mark.infra
def test_run_query_returns_single_int():
    rows = run_query("RETURN 1 AS n")
    assert rows == [{"n": 1}]


@pytest.mark.infra
def test_run_query_with_params():
    rows = run_query("RETURN $x AS x, $y AS y", x="hello", y=42)
    assert rows == [{"x": "hello", "y": 42}]


@pytest.mark.infra
def test_driver_singleton():
    d1 = get_driver()
    d2 = get_driver()
    assert d1 is d2, "get_driver must memoize"
