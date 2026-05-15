"""YARN RM REST API — 轮询应用最终状态 + 抓 diagnostics。"""
from __future__ import annotations

import time

import requests

from backend.sandbox.models import SubmitResult


class YarnError(RuntimeError):
    pass


_TERMINAL_STATES = {"FINISHED", "FAILED", "KILLED"}
_SUCCESS_STATUS = {"SUCCEEDED"}


def _get_app(app_id: str, *, rm_url: str, timeout: float = 5.0) -> dict:
    url = f"{rm_url}/ws/v1/cluster/apps/{app_id}"
    r = requests.get(url, timeout=timeout)
    if r.status_code != 200:
        raise YarnError(f"YARN RM returned {r.status_code} for {app_id}: {r.text[:300]}")
    payload = r.json()
    if "app" not in payload:
        raise YarnError(f"YARN RM payload missing 'app': {payload}")
    return payload["app"]


def get_app_state(app_id: str, *, rm_url: str) -> str:
    return _get_app(app_id, rm_url=rm_url)["state"]


def fetch_app_diagnostics(app_id: str, *, rm_url: str) -> str:
    return _get_app(app_id, rm_url=rm_url).get("diagnostics", "") or ""


def wait_for_app(
    app_id: str,
    *,
    rm_url: str,
    timeout: float,
    poll_interval: float = 1.0,
) -> SubmitResult:
    start = time.monotonic()
    while True:
        app = _get_app(app_id, rm_url=rm_url)
        state = app["state"]
        final_status = app.get("finalStatus", "UNDEFINED")
        if state in _TERMINAL_STATES:
            if state == "FINISHED" and final_status in _SUCCESS_STATUS:
                return SubmitResult(
                    application_id=app_id,
                    final_state=state,
                    diagnostics=app.get("diagnostics", "") or "",
                )
            raise YarnError(
                f"YARN app {app_id} {state} ({final_status}): {app.get('diagnostics', '')[:1000]}"
            )
        if time.monotonic() - start > timeout:
            raise YarnError(f"YARN app {app_id} wait timeout after {timeout}s; last state={state}")
        time.sleep(poll_interval)
