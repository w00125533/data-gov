"""模板加载 + 占位符注入。"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal


_CODE_TYPE_TO_DIR = {
    "spark_sql": "spark-sql",
    "flink_sql": "flink-sql",
    "java_flink": "flink-java",
}


def _repo_root() -> Path:
    # 容器内是 /app；本地是仓库根。
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "templates" / "spark-sql" / "pom.xml").exists():
            return parent
    raise RuntimeError("Cannot locate repo root with templates/ dir.")


def load_template(code_type: str) -> Path:
    if code_type not in _CODE_TYPE_TO_DIR:
        raise ValueError(f"Unknown code_type: {code_type!r}")
    return _repo_root() / "templates" / _CODE_TYPE_TO_DIR[code_type]


def _replace_in_file(path: Path, mapping: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for k, v in mapping.items():
        text = text.replace(k, v)
    path.write_text(text, encoding="utf-8")


def inject(
    *,
    code_type: str,
    dest_dir: Path,
    user_code: str,
    sandbox_uuid: str,
) -> Path:
    """把模板目录递归 copy 到 dest_dir, 替换 ${user_sql}/${user_code_block}/${sandbox_uuid}。"""
    src = load_template(code_type)
    dest_dir = Path(dest_dir)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(src, dest_dir)

    placeholder = "${user_code_block}" if code_type == "java_flink" else "${user_sql}"
    mapping = {placeholder: user_code, "${sandbox_uuid}": sandbox_uuid}
    for java_file in dest_dir.rglob("*.java"):
        _replace_in_file(java_file, mapping)
    # pom.xml 也支持 sandbox_uuid（用户骨架可能在 finalName 里引用，预留）
    pom = dest_dir / "pom.xml"
    if pom.exists():
        _replace_in_file(pom, {"${sandbox_uuid}": sandbox_uuid})
    return dest_dir
