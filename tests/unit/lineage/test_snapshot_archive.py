import hashlib
import stat
from io import BytesIO
from zipfile import ZipFile, ZipInfo

import pytest

from lineage_poc.lineage_workflow import parse_sources
from lineage_poc.parsers.snapshot import TMV_REPOSITORIES, discover_sources, load_snapshot, read_json, write_json


def test_account_domain_discovery_is_four_repository_account_only(tmp_path):
    from lineage_poc.parsers.snapshot import ACCOUNT_DOMAIN_REPOSITORIES
    for repository in ACCOUNT_DOMAIN_REPOSITORIES:
        (tmp_path / repository).mkdir()
    selected = [
        "kb-accounts/src/Account/Account.csproj",
        "kb-cdp-tenant-account/products/accounts-v1/dbt/models/account.sql",
        "kb-cdp-tenant-account/products/account-profile-topic-v1/dbt/models/account.sql",
        "kb-cdp-tenant-enterprise/products/int-account-v1/dbt/models/account.sql",
        "kb-cdp-tenant-protect-downstream/products/sys_pds_account_v1/dbt/models/account.sql",
    ]
    excluded = [
        "kb-cdp-tenant-account/products/customer-v1/dbt/models/customer.sql",
        "kb-cdp-tenant-enterprise/products/int-customer-v1/dbt/models/customer.sql",
        "kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/accounts.sql",
    ]
    for name in selected + excluded:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("static fixture", encoding="utf-8")
    assert [path.relative_to(tmp_path).as_posix() for path in discover_sources(tmp_path, "account-domain")] == sorted(selected)


def test_cdp_account_discovery_is_exactly_two_repositories_and_captures_event_schemas(tmp_path):
    from lineage_poc.parsers.snapshot import CDP_ACCOUNT_REPOSITORIES
    for repository in CDP_ACCOUNT_REPOSITORIES:
        (tmp_path / repository).mkdir()
    selected = [
        "kb-accounts/src/profile/Account.Profile.Shared/Entities/AccountProfile.cs",
        "kb-accounts/src/profile/Account.Profile.Shared/Infrastructure/Migrations/AccountProfileDbContextModelSnapshot.cs",
        "kb-accounts/src/profile/Account.Profile.Processor/Publishers/AccountProfileEventBuilder.cs",
        "kb-accounts/topic-definitions/schemas/AccountProfile.g.json",
        "kb-accounts/catalog/kafka-events.yaml",
        "kb-cdp-tenant-account/products/account-profile-topic-v1/dbt/models/profile.sql",
        "kb-cdp-tenant-account/products/account-profile-topic-v1/airflow/profile.py",
    ]
    excluded = [
        "kb-accounts/src/profile/Account.Profile.Processor.UnitTests/BuilderTests.cs",
        "kb-cdp-tenant-enterprise/products/int-account-v1/dbt/models/account.sql",
    ]
    for name in selected + excluded:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source fixture", encoding="utf-8")
    assert [path.relative_to(tmp_path).as_posix() for path in discover_sources(tmp_path, "cdp-account")] == sorted(selected)


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


def test_all_parser_discovers_optional_landing_protect_and_dotnet_sources(source_factory):
    source = source_factory()
    optional_files = {
        "kb-cdp-tenant-landing": "products/ultracs-v1/model.sql",
        "kb-cdp-tenant-protect-downstream": "products/sys-pds-account-v1/model.sql",
        "kb-accounts": "src/App/App.csproj",
    }
    for repository, relative_path in optional_files.items():
        path = source / repository / relative_path
        path.parent.mkdir(parents=True)
        path.write_text("evidence", encoding="utf-8")

    discovered = {path.relative_to(source).as_posix() for path in discover_sources(source, "all")}

    assert {f"{repository}/{relative_path}" for repository, relative_path in optional_files.items()} <= discovered


def test_tmv_parser_discovers_only_the_three_selected_repositories(source_factory):
    source = source_factory()
    optional_files = {
        "kb-cdp-tenant-landing": "products/ultracs-v1/dbt/dbt_project.yml",
        "kb-cdp-tenant-protect-downstream": "products/protect-v1/dbt/dbt_project.yml",
        "kb-accounts": "src/App/App.csproj",
    }
    for repository, relative_path in optional_files.items():
        path = source / repository / relative_path
        path.parent.mkdir(parents=True)
        path.write_text("<Project />" if path.suffix == ".csproj" else "name: fixture", encoding="utf-8")

    discovered = {path.relative_to(source).as_posix() for path in discover_sources(source, "tmv")}

    assert {path.split("/")[0] for path in discovered} == set(TMV_REPOSITORIES)
    assert all(f"{repository}/{relative_path}" in discovered for repository, relative_path in optional_files.items())
