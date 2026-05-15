"""Maven / YARN 错误解析 — 输出 ≤2000 字摘要喂给 LLM。"""
from __future__ import annotations

import re

_MAX = 2000

_MVN_ERROR_LINE = re.compile(r"^\[ERROR\]\s+(?P<msg>.+)$", re.MULTILINE)
_JAVA_EXCEPTION = re.compile(
    r"(java(?:x)?\.\w[\w\.]*Exception(?::\s.*)?)", re.MULTILINE
)
_JAVA_AT_FRAME = re.compile(
    r"^\s*at\s+(?P<frame>[\w\.\$<>]+)\(([^)]+)\)", re.MULTILINE
)


def parse_maven_error(stderr: str) -> str:
    if not stderr or "BUILD FAILURE" not in stderr and "[ERROR]" not in stderr:
        return ""
    raw_lines = stderr.splitlines()
    # 收集 [ERROR] 行 + 后续缩进 continuation 行
    merged: list[str] = []
    for line in raw_lines:
        m = _MVN_ERROR_LINE.match(line)
        if m:
            merged.append(m.group("msg"))
        elif merged and line and (line.startswith(" ") or line.startswith("\t")):
            # continuation line — 拼到上一条末尾
            merged[-1] = merged[-1] + " " + line.strip()
        # else: skip (INFO lines, blank, etc.)
    # 去掉 BUILD FAILURE / Reactor Summary 这种汇总性
    keep = [l for l in merged if "BUILD FAILURE" not in l and "Reactor" not in l]
    body = "\n".join(keep[:30])
    return body[:_MAX]


def parse_yarn_diagnostics(diagnostics: str) -> str:
    if not diagnostics:
        return ""
    excs = _JAVA_EXCEPTION.findall(diagnostics)
    frames = _JAVA_AT_FRAME.findall(diagnostics)
    parts: list[str] = []
    if excs:
        parts.append("Exceptions:")
        parts.extend(f"  {e}" for e in excs[:5])
    if frames:
        parts.append("First frames:")
        parts.extend(f"  at {fr}({loc})" for fr, loc in frames[:5])
    if not parts:
        # 兜底: 把 Diagnostics 行抽出来
        snippet = "\n".join(
            l
            for l in diagnostics.splitlines()
            if l.startswith("Diagnostics:") or "exitCode" in l
        )
        return snippet[:_MAX]
    return "\n".join(parts)[:_MAX]
