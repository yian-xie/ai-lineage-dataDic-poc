"""Clone or verify explicit upstream checkouts without pulling or resetting user work."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .execution import read_json, utc_now, validate_identifier, write_json

REPOSITORY_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


def git(arguments: list[str], *, cwd: Path | None = None) -> str:
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    result = subprocess.run(
        ["git", "-c", "credential.interactive=never", *arguments],
        cwd=cwd, env=environment, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600,
    )
    if result.returncode:
        raise ValueError(f"Git operation failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def source_configuration(path: Path) -> dict:
    value = read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("repositories"), list):
        raise ValueError("Source configuration must contain a repositories array.")
    if not value["repositories"]:
        raise ValueError("Source configuration must contain at least one repository.")
    seen = set()
    for repository in value["repositories"]:
        if not isinstance(repository, dict):
            raise ValueError("Each repository must be an object with name and URL.")
        name, url = repository.get("name"), repository.get("url")
        if not isinstance(name, str) or not REPOSITORY_NAME.fullmatch(name) or name in {".", ".."}:
            raise ValueError("Repository names must be single safe directory names.")
        validate_identifier(name, "repository name")
        if name.casefold() in seen:
            raise ValueError(f"Duplicate source repository name: {name}")
        seen.add(name.casefold())
        if not isinstance(url, str):
            raise ValueError(f"Repository URL is missing: {name}")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment
        ):
            raise ValueError(f"Use an HTTPS repository URL without embedded credentials: {name}")
    return value


def configured_root(config_path: Path, override: Path | None = None) -> Path:
    if override is not None:
        return override.resolve()
    environment = os.environ.get("LINEAGE_SOURCE_ROOT")
    if environment:
        return Path(environment).expanduser().resolve()
    configuration = source_configuration(config_path)
    location = configuration.get("source_root")
    if not isinstance(location, str) or not location:
        raise ValueError("Configure source_root or pass --source-root.")
    return (config_path.resolve().parent / location).resolve()


def prepare_sources(config_path: Path, root: Path, destination: Path, *, clone: bool = False) -> dict:
    configuration = source_configuration(config_path)
    if clone:
        root.mkdir(parents=True, exist_ok=True)
    repositories = []
    for specification in configuration["repositories"]:
        name, url = specification["name"], specification["url"]
        checkout = root / name
        cloned = False
        if not checkout.exists():
            if not clone:
                raise FileNotFoundError(f"Source repository is missing: {checkout}. Use sources --clone.")
            git(["clone", "--quiet", "--depth", "1", "--config", "core.longpaths=true",
                 url, str(checkout)])
            cloned = True
        if not (checkout / ".git").exists():
            raise ValueError(f"Existing source directory is not a Git checkout: {checkout}")
        remote = git(["remote", "get-url", "origin"], cwd=checkout)
        if remote.rstrip("/").removesuffix(".git").casefold() != url.rstrip("/").removesuffix(".git").casefold():
            raise ValueError(f"Origin URL differs from the configuration for {name}; checkout left unchanged.")
        status = git(["status", "--porcelain"], cwd=checkout)
        if status:
            raise ValueError(f"Source checkout has local changes: {checkout}. No pull/reset was attempted.")
        repositories.append({
            "name": name, "url": url, "path": str(checkout.resolve()),
            "commit": git(["rev-parse", "HEAD"], cwd=checkout),
            "branch": git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=checkout),
            "shallow": git(["rev-parse", "--is-shallow-repository"], cwd=checkout) == "true",
            "working_tree": "clean", "cloned": cloned,
        })
        write_json(destination / "repositories.json", {
            "schema_version": 1, "status": "partial", "source_root": str(root.resolve()),
            "repositories": repositories,
        })
        print(f"Verified {name} at {repositories[-1]['commit']}")
    report = {"schema_version": 1, "status": "passed", "checked_at": utc_now(), "source_root": str(root.resolve()),
              "repositories": repositories}
    write_json(destination / "repositories.json", report)
    return report
