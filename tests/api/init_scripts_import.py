import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INIT_SCRIPT_DIR = REPO_ROOT / "init-scripts"


def load_script_module(filename: str):
    path = INIT_SCRIPT_DIR / filename
    module_name = filename.replace("-", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module
