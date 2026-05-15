"""Sandbox dataclasses — shared by all submodules and re-exported by sandbox_stub for slice 2b 兼容。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CompileResult:
    success: bool
    jar_path: Optional[str] = None
    error_log: Optional[str] = None


@dataclass
class SubmitResult:
    application_id: str
    final_state: str            # "FINISHED" | "FAILED" | "KILLED" | "RUNNING" | ...
    diagnostics: str = ""


@dataclass
class DryRunResult:
    success: bool
    preview_row: Optional[dict] = None
    error_log: Optional[str] = None
    application_id: Optional[str] = None
