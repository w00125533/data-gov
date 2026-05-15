"""tests/sandbox/test_yarn.py — 用 responses 库 mock RM REST。"""
import pytest
import responses

from backend.sandbox.yarn import YarnError, fetch_app_diagnostics, get_app_state, wait_for_app


@responses.activate
def test_get_app_state_returns_state_field():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/application_1_0001",
        json={"app": {"state": "RUNNING", "finalStatus": "UNDEFINED"}},
        status=200,
    )
    assert get_app_state("application_1_0001", rm_url="http://rm:8088") == "RUNNING"


@responses.activate
def test_wait_for_app_returns_finished():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/app_x",
        json={"app": {"state": "FINISHED", "finalStatus": "SUCCEEDED", "diagnostics": ""}},
        status=200,
    )
    out = wait_for_app("app_x", rm_url="http://rm:8088", timeout=2, poll_interval=0.05)
    assert out.final_state == "FINISHED"


@responses.activate
def test_wait_for_app_raises_on_failure():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/app_y",
        json={"app": {"state": "FINISHED", "finalStatus": "FAILED",
                       "diagnostics": "NullPointerException at line 17"}},
        status=200,
    )
    with pytest.raises(YarnError, match="FAILED"):
        wait_for_app("app_y", rm_url="http://rm:8088", timeout=2, poll_interval=0.05)


@responses.activate
def test_wait_for_app_times_out_when_stuck_running():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/app_z",
        json={"app": {"state": "RUNNING", "finalStatus": "UNDEFINED"}},
        status=200,
    )
    with pytest.raises(YarnError, match="timeout"):
        wait_for_app("app_z", rm_url="http://rm:8088", timeout=0.2, poll_interval=0.05)


@responses.activate
def test_fetch_app_diagnostics():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/app_w",
        json={"app": {"state": "FINISHED", "finalStatus": "FAILED",
                       "diagnostics": "boom"}},
        status=200,
    )
    assert "boom" in fetch_app_diagnostics("app_w", rm_url="http://rm:8088")
