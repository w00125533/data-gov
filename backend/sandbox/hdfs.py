"""HDFS CLI 包装 -- ``hdfs dfs ...`` subprocess。所有错误归一为 HdfsError。"""
from __future__ import annotations

import os
import subprocess


class HdfsError(RuntimeError):
    pass


_HDFS_BIN = os.environ.get("HADOOP_HOME", "/opt/hadoop") + "/bin/hdfs"


def _run(args: list[str], timeout: int = 30) -> str:
    cmd = [_HDFS_BIN, "dfs", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode != 0:
        raise HdfsError(
            f"hdfs {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}"
        )
    return r.stdout


def hdfs_mkdir(path: str) -> None:
    """Create remote directory (``hdfs dfs -mkdir -p <path>``)."""
    _run(["-mkdir", "-p", path])


def hdfs_put(local_path: str, remote_path: str) -> None:
    """Upload local file (``hdfs dfs -put -f <local> <remote>``)."""
    _run(["-put", "-f", local_path, remote_path])


def hdfs_cat(remote_path: str) -> str:
    """Return remote file content as a string (``hdfs dfs -cat <path>``)."""
    return _run(["-cat", remote_path])


def hdfs_rm(remote_path: str, *, recursive: bool = False) -> None:
    """Remove remote path (``hdfs dfs -rm [-r] -f <path>``)."""
    args = ["-rm"]
    if recursive:
        args.append("-r")
    args += ["-f", remote_path]
    _run(args)


def hdfs_ls(remote_path: str) -> list[str]:
    """List remote directory and return bare paths (``hdfs dfs -ls <path>``).

    The Hadoop ``-ls`` output format (8+ columns per line):

        drwxr-xr-x   - user supergroup          0 2024-01-01 12:00 /path/to/item
    """
    out = _run(["-ls", remote_path])
    paths: list[str] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 8:
            paths.append(parts[-1])
    return paths
