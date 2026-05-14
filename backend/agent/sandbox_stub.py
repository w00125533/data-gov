"""Sandbox 接口占位 - slice 2c 用真实 SandboxController 替换。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


CodeType = Literal["spark_sql", "flink_sql", "java_flink"]


@dataclass
class DryRunResult:
    success: bool
    preview_row: Optional[dict] = None
    error_log: Optional[str] = None
    application_id: Optional[str] = None


def execute(code: str, code_type: CodeType) -> DryRunResult:
    """slice 2c 实现: copy template + maven_compile + YARN submit + read result。"""
    raise NotImplementedError(
        "Sandbox.execute is a stub in slice 2b; real impl arrives in slice 2c."
    )
