"""Sandbox 接口 — slice 2c 起委托给 backend.sandbox.controller.execute。

文件名保留为 sandbox_stub.py 以兼容 slice 2b 已写的导入路径，
但实质已经不是 stub 而是 thin re-export。
"""
from __future__ import annotations

from typing import Literal

from backend.sandbox.controller import execute  # noqa: F401
from backend.sandbox.models import DryRunResult  # noqa: F401


CodeType = Literal["spark_sql", "flink_sql", "java_flink"]
