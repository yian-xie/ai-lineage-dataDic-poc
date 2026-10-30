import json

import pytest

from lineage_poc import sources
from lineage_poc.paths import PROJECT_ROOT, source_root


def configuration(tmp_path, url="https://github.com/example/source.git"):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"source_root": "checkouts",
                               "repositories": [{"name": "source", "url": url}]}))
    return path


def test_source_location_is_relative_to_configuration_not_shell(tmp_path, monkeypatch):
    path = configuration(tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    assert sources.configured_root(path) == tmp_path / "checkouts"
    assert sources.configured_root(path, tmp_path / "override") == tmp_path / "override"


def test_project_default_source_checkouts_are_inside_application(tmp_path, monkeypatch):
    monkeypatch.delenv("LINEAGE_SOURCE_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    expected = PROJECT_ROOT / "source-repos"
    assert source_root() == expected
    assert sources.configured_root(PROJECT_ROOT / "sources.json") == expected


def test_explicit_source_location_override_is_preserved(tmp_path, monkeypatch):
    configured = tmp_path / "custom-checkouts"
    monkeypatch.setenv("LINEAGE_SOURCE_ROOT", str(configured))
    assert source_root() == configured
    assert sources.configured_root(PROJECT_ROOT / "sources.json") == configured
    assert sources.configured_root(PROJECT_ROOT / "sources.json", tmp_path / "argument") == tmp_path / "argument"


def test_credentials_are_not_allowed_in_recorded_urls(tmp_path):
    with pytest.raises(ValueError, match="without embedded credentials"):
        sources.source_configuration(configuration(tmp_path, "https://token@github.com/example/source.git"))


def test_query_tokens_and_case_duplicate_checkouts_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="without embedded credentials"):
        sources.source_configuration(configuration(tmp_path, "https://github.com/example/source.git?token=secret"))
    path = configuration(tmp_path)
    value = json.loads(path.read_text())
    value["repositories"].append({"name": "SOURCE", "url": "https://github.com/example/other.git"})
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Duplicate source repository"):
        sources.source_configuration(path)


def test_missing_repository_does_not_implicitly_clone(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sources, "git", lambda args, **kwargs: calls.append(args))
    with pytest.raises(FileNotFoundError, match="--clone"):
        sources.prepare_sources(configuration(tmp_path), tmp_path / "checkouts", tmp_path / "out")
    assert calls == []


def test_clone_and_verification_record_revisions_without_pull_or_reset(tmp_path, monkeypatch):
    config = configuration(tmp_path)
    calls = []

    def fake_git(args, cwd=None):
        calls.append(args)
        if args[0] == "clone":
            from pathlib import Path
            (Path(args[-1]) / ".git").mkdir(parents=True)
            return ""
        if args[:2] == ["remote", "get-url"]:
            return "https://github.com/example/source.git"
        if args == ["status", "--porcelain"]:
            return ""
        if args == ["rev-parse", "HEAD"]:
            return "abc123"
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "main"
        if args == ["rev-parse", "--is-shallow-repository"]:
            return "true"
        raise AssertionError(args)

    monkeypatch.setattr(sources, "git", fake_git)
    report = sources.prepare_sources(config, tmp_path / "checkouts", tmp_path / "out", clone=True)
    assert report["repositories"][0]["commit"] == "abc123"
    assert report["repositories"][0]["cloned"] is True
    assert "core.longpaths=true" in calls[0]
    assert not any(args[0] in {"pull", "reset", "checkout"} for args in calls)
    assert json.loads((tmp_path / "out" / "repositories.json").read_text())["status"] == "passed"


def test_dirty_checkout_is_never_modified(tmp_path, monkeypatch):
    config = configuration(tmp_path)
    (tmp_path / "checkouts" / "source" / ".git").mkdir(parents=True)

    def fake_git(args, cwd=None):
        if args[0] == "remote":
            return "https://github.com/example/source.git"
        if args[0] == "status":
            return " M user-work.sql"
        raise AssertionError("Unexpected write or revision query")

    monkeypatch.setattr(sources, "git", fake_git)
    with pytest.raises(ValueError, match="local changes"):
        sources.prepare_sources(config, tmp_path / "checkouts", tmp_path / "out")
