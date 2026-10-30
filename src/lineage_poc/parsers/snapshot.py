"""Portable, hash-verified source evidence used between independent stages.

The snapshot is exact source text, not a claim that table graph fragments prove
column mappings. Column extraction still inspects BASIC expressions, ordered HVR
parameters, and dbt SQL/schema evidence using the original extraction algorithms.
"""

import hashlib
import json
import stat
import subprocess
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from lineage_poc.graph.models import Edge, GraphPayload, Node

REQUIRED_REPOSITORIES = (
    "kb-ultracs-datawarehouse",
    "kb-cdp-hvr",
    "kb-cdp-tenant-account",
    "kb-cdp-tenant-enterprise",
)
ACCOUNT_PRODUCTS = (
    "accounts-v1",
    "account-relationship-v1",
    "ult-account-fees-v1",
    "ult-account-payment-v1",
)
ENTERPRISE_PRODUCTS = (
    "int-account-v1",
    "enterprise-integrated-account-v1",
    "cur-dimaccount-v1",
    "cur-factaccount-v1",
)
PARSERS = ("all", "basic", "hvr", "airflow", "dbt", "schemachange", "landing")
FORMAT = "lineage-poc-source-evidence-v2"
SNAPSHOT_NAME = "source-snapshot.zip"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_evidence(value: Any, evidence_root: Path) -> Any:
    """Keep repository-relative evidence locators stable when a run is moved."""
    if isinstance(value, str):
        prefix = evidence_root.resolve().as_posix() + "/"
        return value.replace("\\", "/")[len(prefix):] if value.replace("\\", "/").startswith(prefix) else value
    if isinstance(value, list):
        return [normalize_evidence(item, evidence_root) for item in value]
    if isinstance(value, dict):
        return {key: normalize_evidence(item, evidence_root) for key, item in value.items()}
    return value


def graph_document(graph: GraphPayload, evidence_root: Path) -> dict:
    return normalize_evidence(graph.to_dict(), evidence_root)


def graph_payload(document: dict) -> GraphPayload:
    return GraphPayload(
        nodes=[Node(node["id"], node.get("label", node.get("type")), node.get("properties", {})) for node in document["nodes"]],
        edges=[Edge(edge["source"], edge["target"], edge["type"], edge.get("properties", {})) for edge in document["edges"]],
    )


def discover_sources(source_root: Path, parser: str) -> list[Path]:
    if parser not in PARSERS:
        raise ValueError(f"Unknown parser {parser!r}; choose from {', '.join(PARSERS)}")
    needed = {
        "all": REQUIRED_REPOSITORIES,
        "basic": REQUIRED_REPOSITORIES[:1],
        "hvr": REQUIRED_REPOSITORIES[1:2],
        "airflow": REQUIRED_REPOSITORIES[2:],
        "dbt": REQUIRED_REPOSITORIES[2:],
        "schemachange": REQUIRED_REPOSITORIES[2:],
        "landing": ("kb-cdp-tenant-landing",),
    }[parser]
    missing = [name for name in needed if not (source_root / name).is_dir()]
    if missing:
        raise FileNotFoundError(f"Required source repositories are missing under {source_root}: {', '.join(missing)}")
    paths: set[Path] = set()
    if parser in {"all", "basic"}:
        paths.update(
            path for path in (source_root / REQUIRED_REPOSITORIES[0]).rglob("*")
            if path.is_file() and ".git" not in path.parts
            and path.suffix.lower() in {"", ".b", ".old", ".ext", ".restrict", ".unrestrict"}
        )
    if parser in {"all", "hvr"}:
        paths.update(
            path for path in (source_root / REQUIRED_REPOSITORIES[1]).rglob("*")
            if path.is_file() and ".git" not in path.parts and path.suffix.lower() in {".json", ".param"}
        )
    for repository, products in (
        (REQUIRED_REPOSITORIES[2], ACCOUNT_PRODUCTS),
        (REQUIRED_REPOSITORIES[3], ENTERPRISE_PRODUCTS),
    ):
        if parser not in {"all", "airflow", "dbt", "schemachange"}:
            continue
        for product in products:
            root = source_root / repository / "products" / product
            paths.update(
                path for path in root.rglob("*")
                if path.is_file() and ".git" not in path.parts
                and (path.suffix.lower() in {".py", ".sql", ".yml", ".yaml"} or path.name.lower().endswith(". sql"))
            )
    landing = source_root / "kb-cdp-tenant-landing"
    if parser == "landing" or parser == "all" and landing.is_dir():
        paths.update(
            path for path in landing.rglob("*")
            if path.is_file() and ".git" not in path.parts and path.suffix.lower() in {".sql", ".yml", ".yaml", ".py"}
        )
    return sorted(paths)


def capture_sources(source_root: Path, destination: Path, parser: str) -> dict:
    source_root = Path(source_root).resolve()
    destination = Path(destination).resolve()
    if source_root == destination or destination.is_relative_to(source_root) or source_root.is_relative_to(destination):
        raise ValueError("The parse destination must be separate from the source repositories.")
    paths = discover_sources(source_root, parser)
    archive_path = destination / SNAPSHOT_NAME
    contents = {}
    for path in paths:
        contents[path.relative_to(source_root).as_posix()] = path.read_bytes()
    files = [
        {"path": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
        for name, content in contents.items()
    ]
    destination.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        try:
            with ZipFile(archive_path) as archive:
                for info, entry in _checked_members(archive, files):
                    if archive.read(info) != contents[entry["path"]]:
                        raise ValueError(f"Source bytes differ: {entry['path']}")
        except (BadZipFile, ValueError) as error:
            raise FileExistsError("Immutable parse evidence differs; use a new parse destination.") from error
    else:
        with ZipFile(archive_path, "x", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for name, content in contents.items():
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                archive.writestr(info, content)
    revisions = {}
    for name in (*REQUIRED_REPOSITORIES, "kb-cdp-tenant-landing"):
        repository = source_root / name
        if repository.is_dir():
            if not (repository / ".git").exists():
                revisions[name] = None
                continue
            result = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=False,
            )
            revisions[name] = result.stdout.strip() if result.returncode == 0 else None
    return {
        "format": FORMAT,
        "parser": parser,
        "evidence_type": "exact_source_file_zip_snapshot_with_sha256",
        "column_mapping_basis": "BASIC field expressions and ordinal HVR declarations plus dbt SQL projections/schema; graph fragments alone do not establish column mappings.",
        "snapshot_archive": {
            "path": SNAPSHOT_NAME,
            "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "bytes": archive_path.stat().st_size,
        },
        "repositories": revisions,
        "files": files,
    }


def _safe_parts(name: str) -> tuple[str, ...]:
    if not isinstance(name, str) or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError(f"Invalid evidence archive path: {name!r}")
    parts = name.split("/")
    if not parts or any(part in {"", ".", ".."} or part.rstrip(" .") != part for part in parts):
        raise ValueError(f"Invalid evidence archive path: {name!r}")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}
    if any(part.split(".", 1)[0].upper() in reserved for part in parts):
        raise ValueError(f"Invalid evidence archive path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise ValueError(f"Invalid evidence archive path: {name!r}")
    return tuple(parts)


def _checked_members(archive: ZipFile, files: list[dict]) -> list[tuple[ZipInfo, dict]]:
    expected = {}
    folded = set()
    for entry in files:
        name = entry.get("path") if isinstance(entry, dict) else None
        _safe_parts(name)
        if type(entry.get("bytes")) is not int or entry["bytes"] < 0 or not isinstance(entry.get("sha256"), str) or len(entry["sha256"]) != 64 or any(char not in "0123456789abcdef" for char in entry["sha256"]):
            raise ValueError(f"Invalid evidence archive hash or size: {name}")
        if name.casefold() in folded:
            raise ValueError(f"Duplicate evidence archive path: {name}")
        folded.add(name.casefold())
        expected[name] = entry
    for name in expected:
        parts = _safe_parts(name)
        if any("/".join(parts[:index]).casefold() in folded for index in range(1, len(parts))):
            raise ValueError(f"Conflicting evidence archive paths: {name}")
    members = []
    seen = set()
    for info in archive.infolist():
        _safe_parts(info.filename)
        kind = stat.S_IFMT(info.external_attr >> 16)
        if info.is_dir() or kind not in {0, stat.S_IFREG}:
            raise ValueError(f"Non-file evidence archive member: {info.filename}")
        if info.filename.casefold() in seen:
            raise ValueError(f"Duplicate evidence archive path: {info.filename}")
        seen.add(info.filename.casefold())
        entry = expected.get(info.filename)
        if entry is None or info.file_size != entry["bytes"]:
            raise ValueError("Source snapshot integrity check failed: archive file inventory changed.")
        members.append((info, entry))
    if {info.filename for info, _ in members} != set(expected):
        raise ValueError("Source snapshot integrity check failed: archive file inventory changed.")
    return members


@contextmanager
def materialize_snapshot(manifest: dict, parsed_dir: Path, workspace: Path):
    """Validate exact archived bytes and clean only our destination-local directory."""
    parsed_dir, workspace = Path(parsed_dir).resolve(), Path(workspace).resolve()
    claim = manifest.get("snapshot_archive", {})
    if manifest.get("format") != FORMAT or claim.get("path") != SNAPSHOT_NAME or not isinstance(manifest.get("files"), list):
        raise ValueError(f"Unsupported parse artifact format in {parsed_dir}; parse sources again.")
    archive_path = parsed_dir / SNAPSHOT_NAME
    if not archive_path.is_file() or archive_path.stat().st_size != claim.get("bytes") or hashlib.sha256(archive_path.read_bytes()).hexdigest() != claim.get("sha256"):
        raise ValueError("Source snapshot integrity check failed: archive hash or size differs.")
    for entry in manifest.get("artifacts", []):
        path = (parsed_dir / entry["path"]).resolve()
        if not path.is_relative_to(parsed_dir) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Parse artifact integrity check failed: {entry['path']}")
    workspace.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".lineage-evidence-", dir=workspace) as directory:
        evidence_root = Path(directory).resolve()
        try:
            with ZipFile(archive_path) as archive:
                members = _checked_members(archive, manifest["files"])
                for info, entry in members:
                    content = archive.read(info)
                    if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                        raise ValueError(f"Source snapshot integrity check failed: {entry['path']}")
                    target = evidence_root.joinpath(*_safe_parts(info.filename))
                    if not target.resolve().is_relative_to(evidence_root):
                        raise ValueError(f"Invalid evidence archive path: {info.filename!r}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
        except BadZipFile as error:
            raise ValueError("Source snapshot integrity check failed: invalid ZIP archive.") from error
        yield manifest, evidence_root


@contextmanager
def load_snapshot(parsed_dir: Path, workspace: Path | None = None):
    parsed_dir = Path(parsed_dir).resolve()
    manifest = read_json(parsed_dir / "manifest.json")
    with materialize_snapshot(manifest, parsed_dir, workspace or parsed_dir.parent) as result:
        yield result
