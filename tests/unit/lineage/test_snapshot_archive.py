import hashlib
import stat
from io import BytesIO
from zipfile import ZipFile, ZipInfo

import pytest

from lineage_poc.lineage_workflow import parse_sources
from lineage_poc.parsers.snapshot import load_snapshot, read_json, write_json


def rewrite_archive(parsed, extra_name=None, *, symbolic=False, duplicate=False, change_bytes=False):
    archive_path = parsed / "source-snapshot.zip"
    manifest = read_json(parsed / "manifest.json")
    with ZipFile(archive_path) as archive:
        members = [(info, archive.read(info)) for info in archive.infolist()]
    if change_bytes:
        info, contents = members[0]
        members[0] = (info, bytes([contents[0] ^ 1]) + contents[1:])
    if extra_name is not None:
        content = b"untrusted source data; never executed"
        info = ZipInfo(extra_name)
        info.external_attr = ((stat.S_IFLNK if symbolic else stat.S_IFREG) | 0o600) << 16
        members.append((info, content))
        manifest["files"].append({
            "path": extra_name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
        })
    if duplicate:
        info, contents = members[0]
        duplicate_info = ZipInfo(info.filename.upper())
        duplicate_info.external_attr = (stat.S_IFREG | 0o600) << 16
        members.append((duplicate_info, contents))
        manifest["files"].append({
            "path": duplicate_info.filename, "sha256": hashlib.sha256(contents).hexdigest(), "bytes": len(contents),
        })
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for info, content in members:
            archive.writestr(info, content)
    archive_path.write_bytes(stream.getvalue())
    manifest["snapshot_archive"].update(sha256=hashlib.sha256(stream.getvalue()).hexdigest(), bytes=len(stream.getvalue()))
    write_json(parsed / "manifest.json", manifest)


@pytest.mark.parametrize("name", [
    "../outside.py", "/absolute.py", "C:/outside.py", "repo\\outside.py",
    "repo/../outside.py", "repo/file:stream", "repo/file.", "repo/NUL.sql",
])
def test_replay_rejects_unsafe_archive_paths(source_factory, tmp_path, name):
    parsed, workspace = tmp_path / "parsed", tmp_path / "workspace"
    parse_sources(source_factory(), parsed)
    rewrite_archive(parsed, name)
    with pytest.raises(ValueError, match="Invalid evidence archive path"):
        with load_snapshot(parsed, workspace=workspace):
            pytest.fail("Invalid archived paths must never be materialized.")
    assert not list(workspace.glob(".lineage-evidence-*"))
    assert not (tmp_path / "outside.py").exists()


@pytest.mark.parametrize("tamper,match", [
    ("symbolic", "Non-file evidence archive member"),
    ("duplicate", "Duplicate evidence archive path"),
    ("content", "Source snapshot integrity check failed"),
])
def test_replay_checks_member_kind_uniqueness_and_content_hash(source_factory, tmp_path, tamper, match):
    parsed, workspace = tmp_path / "parsed", tmp_path / "workspace"
    parse_sources(source_factory(), parsed)
    rewrite_archive(
        parsed,
        "repo/symbolic.py" if tamper == "symbolic" else None,
        symbolic=tamper == "symbolic", duplicate=tamper == "duplicate", change_bytes=tamper == "content",
    )
    with pytest.raises(ValueError, match=match):
        with load_snapshot(parsed, workspace=workspace):
            pytest.fail("Tampered archive must not be replayed.")
    assert not list(workspace.glob(".lineage-evidence-*"))


def test_replay_cleans_only_its_own_directory_after_success_and_failure(source_factory, tmp_path):
    parsed, workspace = tmp_path / "parsed", tmp_path / "workspace"
    parse_sources(source_factory(), parsed)
    workspace.mkdir()
    sentinel = workspace / "keep.txt"
    sentinel.write_bytes(b"unrelated output")
    with load_snapshot(parsed, workspace=workspace) as (_, evidence):
        assert evidence.is_dir()
        assert evidence.parent == workspace
    assert not evidence.exists()
    with pytest.raises(RuntimeError, match="downstream failure"):
        with load_snapshot(parsed, workspace=workspace) as (_, evidence):
            raise RuntimeError("downstream failure")
    assert not evidence.exists()
    assert list(workspace.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"unrelated output"


@pytest.mark.parametrize("tamper", ["archive-bytes", "claimed-hash"])
def test_replay_validates_whole_archive_before_materializing(source_factory, tmp_path, tamper):
    parsed, workspace = tmp_path / "parsed", tmp_path / "workspace"
    parse_sources(source_factory(), parsed)
    if tamper == "archive-bytes":
        archive_path = parsed / "source-snapshot.zip"
        archive_path.write_bytes(archive_path.read_bytes() + b"unrecorded trailing bytes")
    else:
        manifest = read_json(parsed / "manifest.json")
        manifest["snapshot_archive"]["sha256"] = "0" * 64
        write_json(parsed / "manifest.json", manifest)
    with pytest.raises(ValueError, match="archive hash or size differs"):
        with load_snapshot(parsed, workspace=workspace):
            pytest.fail("The archive claim must be verified before materialization.")
    assert not workspace.exists()


def test_replay_rejects_file_directory_conflicts(source_factory, tmp_path):
    parsed, workspace = tmp_path / "parsed", tmp_path / "workspace"
    parse_sources(source_factory(), parsed)
    first_file = read_json(parsed / "manifest.json")["files"][0]["path"]
    rewrite_archive(parsed, first_file + "/child.sql")
    with pytest.raises(ValueError, match="Conflicting evidence archive paths"):
        with load_snapshot(parsed, workspace=workspace):
            pytest.fail("A source file cannot also be an archive directory.")
    assert not list(workspace.glob(".lineage-evidence-*"))


def test_parse_replay_archive_is_deterministic_and_immutable(source_factory, tmp_path):
    source, parsed = source_factory(), tmp_path / "parsed"
    parse_sources(source, parsed)
    before = (parsed / "source-snapshot.zip").read_bytes()
    manifest = (parsed / "manifest.json").read_bytes()
    parse_sources(source, parsed)
    assert (parsed / "source-snapshot.zip").read_bytes() == before
    assert (parsed / "manifest.json").read_bytes() == manifest
    (source / "kb-ultracs-datawarehouse" / "KWDW_ACC").write_bytes(b"different evidence")
    with pytest.raises(FileExistsError, match="Immutable parse evidence differs"):
        parse_sources(source, parsed)
    assert (parsed / "source-snapshot.zip").read_bytes() == before
