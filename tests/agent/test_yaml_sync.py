"""tests/agent/test_yaml_sync.py"""
import pathlib

import pytest
import yaml
from git import Actor, Repo

from backend.config import get_settings


# ---------------------------------------------------------------------------
# sync_yaml
# ---------------------------------------------------------------------------


def _make_table_row(name: str, layer: str = "ODS") -> dict:
    return {
        "name": name,
        "layer": layer,
        "layer_priority": 1,
        "storage_type": "HIVE",
        "description": f"table {name}",
    }


def _make_field_row(
    name: str,
    type_: str = "string",
    nullable: bool = True,
    partition: bool = False,
    expression: str | None = None,
    description: str = "",
    upstream: list[dict] | None = None,
) -> dict:
    return {
        "name": name,
        "type": type_,
        "nullable": nullable,
        "partition": partition,
        "expression": expression,
        "description": description,
        "upstream": upstream or [{"table": None, "field": None}],
    }


def test_sync_yaml_writes_files_for_given_tables(monkeypatch, tmpdir):
    """sync_yaml writes YAML files for the tables returned by run_query."""
    monkeypatch.setenv("METADATA_YAML_DIR", str(tmpdir))
    get_settings.cache_clear()

    calls = iter(
        [
            # 1st call (table t1) -> table metadata
            [_make_table_row("t1", "ODS")],
            # 2nd call (fields of t1) -> both field rows
            [
                _make_field_row("f1", "string", upstream=[]),
                _make_field_row("f2", "bigint", nullable=False, upstream=[]),
            ],
        ]
    )

    def fake_run_query(query: str, **params):
        return next(calls)

    monkeypatch.setattr("backend.agent.yaml_sync.run_query", fake_run_query)

    from backend.agent.yaml_sync import sync_yaml

    paths = sync_yaml(["t1"])

    assert len(paths) == 1
    out = pathlib.Path(paths[0])
    assert out.exists()
    assert out.name == "t1.yaml"
    assert "L1-ODS" in out.parent.name

    content = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert content["name"] == "t1"
    assert content["layer"] == "ODS"
    assert content["storage_type"] == "HIVE"
    assert len(content["fields"]) == 2
    assert content["fields"][0]["name"] == "f1"
    assert content["fields"][0]["type"] == "string"
    assert content["fields"][1]["name"] == "f2"


def test_sync_yaml_skips_missing_tables(monkeypatch, tmpdir):
    """Tables not found in the graph are silently skipped."""
    monkeypatch.setenv("METADATA_YAML_DIR", str(tmpdir))
    get_settings.cache_clear()

    calls = iter([[]])  # run_query returns empty list -> table not found

    def fake_run_query(query: str, **params):
        return next(calls)

    monkeypatch.setattr("backend.agent.yaml_sync.run_query", fake_run_query)

    from backend.agent.yaml_sync import sync_yaml

    paths = sync_yaml(["nonexistent"])
    assert paths == []


def test_sync_yaml_upstream_is_filtered(monkeypatch, tmpdir):
    """Null upstream entries are filtered out; valid ones are kept."""
    monkeypatch.setenv("METADATA_YAML_DIR", str(tmpdir))
    get_settings.cache_clear()

    calls = iter(
        [
            [_make_table_row("t1", "ODS")],
            [
                _make_field_row(
                    "f1",
                    "string",
                    upstream=[
                        {"table": "src_t", "field": "src_f"},
                        {"table": None, "field": None},
                    ],
                ),
            ],
        ]
    )

    def fake_run_query(query: str, **params):
        return next(calls)

    monkeypatch.setattr("backend.agent.yaml_sync.run_query", fake_run_query)

    from backend.agent.yaml_sync import sync_yaml

    paths = sync_yaml(["t1"])
    content = yaml.safe_load(pathlib.Path(paths[0]).read_text(encoding="utf-8"))
    assert content["fields"][0]["upstream"] == [{"table": "src_t", "field": "src_f"}]


# ---------------------------------------------------------------------------
# git_commit
# ---------------------------------------------------------------------------


@pytest.fixture
def git_settings(monkeypatch):
    """Set GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL and clear settings cache."""
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test Agent")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@data-gov.local")
    get_settings.cache_clear()


def _init_repo(tmpdir: pathlib.Path) -> Repo:
    """Create a git repo with one initial commit so HEAD exists."""
    repo = Repo.init(tmpdir)
    # Create an initial commit so HEAD is valid
    initial = pathlib.Path(str(tmpdir)) / "README"
    initial.write_text("init\n", encoding="utf-8")
    repo.index.add([str(initial)])
    tester = Actor("tester", "tester@local")
    repo.index.commit("initial", author=tester, committer=tester)
    return repo


def test_git_commit_returns_sha(git_settings, tmpdir):
    """git_commit returns a 40-char hex SHA when a commit is created."""
    tmp = pathlib.Path(str(tmpdir))
    repo = _init_repo(tmp)

    # Create a new untracked file
    new_file = tmp / "data.yaml"
    new_file.write_text("key: value\n", encoding="utf-8")

    from backend.agent.yaml_sync import git_commit

    sha = git_commit("add data.yaml", repo_root=str(tmp))

    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)

    # Verify commit exists in the repo
    commit = repo.commit(sha)
    assert commit.message.strip() == "add data.yaml"
    assert commit.author.name == "Test Agent"
    assert commit.author.email == "test@data-gov.local"


def test_git_commit_returns_empty_when_no_changes(git_settings, tmpdir):
    """git_commit returns empty string when nothing to commit."""
    tmp = pathlib.Path(str(tmpdir))
    _init_repo(tmp)

    from backend.agent.yaml_sync import git_commit

    sha = git_commit("noop", repo_root=str(tmp))
    assert sha == ""


def test_git_commit_returns_empty_for_non_repo(git_settings, tmpdir):
    """git_commit returns empty string when the directory is not a git repo."""
    tmp = pathlib.Path(str(tmpdir))
    from backend.agent.yaml_sync import git_commit

    sha = git_commit("noop", repo_root=str(tmp))
    assert sha == ""
