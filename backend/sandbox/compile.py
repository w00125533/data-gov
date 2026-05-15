"""Maven 编译 — 在指定项目目录跑 `mvn -q -B -DskipTests package`。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from backend.config import get_settings
from backend.sandbox.error_parser import parse_maven_error
from backend.sandbox.models import CompileResult


def maven_compile(project_dir: Path) -> CompileResult:
    settings = get_settings()
    project_dir = Path(project_dir)
    cmd = ["mvn", "-q", "-B", "-DskipTests", "package"]
    r = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=settings.sandbox_compile_timeout,
        check=False,
    )
    if r.returncode != 0:
        return CompileResult(success=False,
                              error_log=parse_maven_error(r.stdout + "\n" + r.stderr))
    target = project_dir / "target"
    jars = sorted(target.glob("*.jar"))
    if not jars:
        return CompileResult(success=False,
                              error_log=f"No JAR produced in {target}")
    return CompileResult(success=True, jar_path=str(jars[0]))
