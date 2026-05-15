"""沙箱层重试 — 失败时让 LLM 改代码 (spec §5.4 execute_with_retry)。"""
from __future__ import annotations

import re
from typing import Any

from backend.sandbox.controller import execute
from backend.sandbox.models import DryRunResult


SANDBOX_FIX_PROMPT = """以下代码在沙箱执行失败。请根据错误日志修正代码，保持原意图。

代码类型: {code_type}

错误日志:
{error_log}

当前代码:
```
{code}
```

只输出修正后的代码 (用 ``` 包裹), 不要解释。
"""


_CODE_FENCE = re.compile(r"```(?:[\w-]+)?\s*\n(.*?)```", re.DOTALL)


def _extract_code(content: str, original: str) -> str:
    m = _CODE_FENCE.search(content)
    return m.group(1).strip() if m else original


def execute_with_retry(
    code: str,
    code_type: str,
    *,
    llm_client: Any,
    max_retries: int = 2,
) -> DryRunResult:
    current_code = code
    last: DryRunResult | None = None
    for attempt in range(max_retries + 1):
        result = execute(current_code, code_type)
        if result.success:
            return result
        last = result
        if attempt == max_retries:
            break
        prompt = SANDBOX_FIX_PROMPT.format(
            code_type=code_type,
            error_log=result.error_log or "(no log)",
            code=current_code,
        )
        try:
            resp = llm_client.invoke(prompt)
            content = getattr(resp, "content", str(resp))
            current_code = _extract_code(content, current_code)
        except Exception:
            break
    return last or DryRunResult(success=False, error_log="execute_with_retry exhausted")
