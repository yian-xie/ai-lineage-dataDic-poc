"""Keep the latest result of each step and append diagnostics in one output folder."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import time
import traceback
import zipfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from . import __version__

IGNORED_DIRECTORIES = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_identifier(value: str, label: str = "label") -> str:
    if (
        not IDENTIFIER.fullmatch(value) or value.endswith(".")
        or value.split(".", 1)[0].upper() in WINDOWS_RESERVED
    ):
        raise ValueError(f"Invalid {label}: use 1-80 letters, digits, dots, dashes or underscores.")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def nonfinite(value: str) -> None:
        raise ValueError(f"Nonfinite JSON number in {path}: {value}")

    return json.loads(path.read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique, parse_constant=nonfinite)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=".record-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def inventory(path: Path) -> dict:
    path = path.resolve()
    if path.is_file():
        return {"path": str(path), "kind": "file", "bytes": path.stat().st_size,
                "sha256": sha256_file(path)}
    if not path.is_dir():
        raise FileNotFoundError(f"Input does not exist: {path}")
    entries = []
    for root, directories, filenames in os.walk(path):
        directories[:] = sorted(name for name in directories if name not in IGNORED_DIRECTORIES)
        for name in directories + sorted(filenames):
            if (Path(root) / name).is_symlink():
                raise ValueError(f"Resolve symlink inputs explicitly: {Path(root) / name}")
        for name in sorted(filenames):
            candidate = Path(root) / name
            entries.append({"path": str(candidate.relative_to(path)),
                            "bytes": candidate.stat().st_size, "sha256": sha256_file(candidate)})
    encoded = json.dumps(entries, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {"path": str(path), "kind": "directory", "files": entries,
            "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()}


def _brief(value: dict) -> dict:
    result = {key: item for key, item in value.items() if key != "files"}
    if "files" in value:
        result["file_count"] = len(value["files"])
    return result


@contextmanager
def record_lock(path: Path) -> Iterator[None]:
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "r+b") as stream:
        if os.name == "nt":
            import msvcrt

            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"0")
                stream.flush()
            deadline = time.monotonic() + 10
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if time.monotonic() >= deadline:
                        raise OSError(f"Another command is using this step: {path}") from error
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def _update_index(root: Path, record: dict) -> None:
    with record_lock(root / "logs" / ".index.lock"):
        path = root / "steps.json"
        value = read_json(path) if path.exists() else {"schema_version": 2, "steps": {}}
        if not isinstance(value, dict) or not isinstance(value.get("steps"), dict):
            raise ValueError(f"Invalid output index: {path}")
        value["steps"][record["stage"]] = {
            key: record[key] for key in ("status", "attempt", "data_directory", "record", "log")
        }
        value["updated_at"] = utc_now()
        write_json(path, value)


def _find_record(path: Path) -> tuple[Path, dict] | None:
    resolved = path.resolve()
    for directory in [resolved, *resolved.parents]:
        candidate = directory.parent / "logs" / (directory.name + ".json")
        if candidate.is_file():
            value = read_json(candidate)
            if not isinstance(value, dict):
                raise ValueError(f"Invalid step record: {candidate}")
            if Path(value.get("data_directory", "")).resolve() == directory:
                return directory, value
    return None


def accepted_data(path: Path, expected_stage: str | None = None) -> dict:
    found = _find_record(path)
    if found is None:
        raise FileNotFoundError(f"No successful recorded step was found for: {path}")
    data, record = found
    if record.get("status") != "passed":
        raise ValueError(f"A successful recorded step is required: {record['record']}")
    if expected_stage is not None and record.get("stage") != expected_stage:
        raise ValueError(f"Expected {expected_stage}, not {record.get('stage')}.")
    if inventory(data) != record.get("outputs"):
        raise ValueError(f"Recorded outputs have changed: {data}")
    return record


class StepFailure(RuntimeError):
    def __init__(self, message: str, record: Path):
        super().__init__(message)
        self.record = record


def _remove_owned_backup(path: Path) -> None:
    def clear_readonly(function, name, exception):
        if not isinstance(exception[1], PermissionError):
            raise exception[1]
        os.chmod(name, stat.S_IWRITE | stat.S_IREAD)
        function(name)

    shutil.rmtree(path, onerror=clear_readonly)


def _archive_failure(data: Path, target: Path) -> None:
    descriptor, name = tempfile.mkstemp(dir=target.parent, suffix=".zip")
    os.close(descriptor)
    temporary = Path(name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(data.rglob("*")):
                if path.is_symlink():
                    raise ValueError(f"Refusing a symlink in failed outputs: {path}")
                if path.is_file():
                    archive.write(path, str(path.relative_to(data)))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def execute_step(
    output_root: Path,
    run_id: str,
    stage: str,
    *,
    inputs: list[Path],
    parameters: dict,
    operation: Callable[[Path], dict],
) -> dict:
    """Replace only this step's latest files; keep logs and restore good data on failure."""
    validate_identifier(run_id)
    validate_identifier(stage, "step")
    root = output_root.resolve()
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    data = root / stage
    record_path, log_path = logs / (stage + ".json"), logs / (stage + ".log")
    with record_lock(logs / (stage + ".lock")):
        previous = read_json(record_path) if record_path.exists() else {}
        if not isinstance(previous, dict):
            raise ValueError(f"Invalid step record: {record_path}")
        number = int(previous.get("attempt_number", 0)) + 1
        record = {
            "schema_version": 2, "run_id": run_id, "stage": stage,
            "attempt": f"attempt-{number:03d}", "attempt_number": number,
            "status": "running", "started_at": utc_now(), "package_version": __version__,
            "runtime": {"python": platform.python_version(), "platform": sys.platform},
            "parameters": parameters, "record": str(record_path), "log": str(log_path),
            "output_root": str(root), "data_directory": str(data),
        }
        write_json(record_path, record)
        _update_index(root, record)
        backup = None
        created_data = False
        started = time.monotonic()
        with log_path.open("a", encoding="utf-8", newline="\n", buffering=1) as log:
            try:
                with redirect_stdout(log), redirect_stderr(log):
                    print(f"\n{record['started_at']} {stage} {record['attempt']} START")
                    for path in inputs:
                        resolved = path.resolve()
                        if resolved == data or data in resolved.parents or (
                            resolved.is_dir() and resolved in data.parents
                        ):
                            raise ValueError("A step cannot overwrite its own input location.")
                        if _find_record(path) is not None:
                            accepted_data(path)
                    before = [inventory(path) for path in inputs]
                    implementation = inventory(Path(__file__).parent)
                    record["inputs"] = before
                    record["implementation"] = _brief(implementation)
                    print(json.dumps({"inputs": [_brief(item) for item in before],
                                      "parameters": parameters,
                                      "implementation": record["implementation"]}))
                    write_json(record_path, record)
                    if data.exists():
                        if not data.is_dir() or data.is_symlink():
                            raise ValueError(f"Step output must be a regular directory: {data}")
                        work = root / ".work"
                        work.mkdir(exist_ok=True)
                        backup = Path(tempfile.mkdtemp(dir=work, prefix=stage + "-"))
                        data.rename(backup / "previous")
                    data.mkdir()
                    created_data = True
                    summary = operation(data)
                    if not isinstance(summary, dict):
                        raise TypeError("A step must return a JSON object summary.")
                    if summary.get("status") in {"failed", "error"}:
                        raise ValueError("The step reported failure; see the log.")
                    json.dumps(summary, allow_nan=False)
                    if [inventory(path) for path in inputs] != before:
                        raise ValueError("An input changed during this step; outputs were not accepted.")
                    if inventory(Path(__file__).parent) != implementation:
                        raise ValueError("Application code changed during this step; rerun with stable code.")
                    record.update(status="passed", summary=summary, outputs=inventory(data))
                    print(f"{utc_now()} {stage} PASSED")
            except BaseException as error:
                traceback.print_exc(file=log)
                record.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
                try:
                    if created_data and data.exists():
                        if any(data.iterdir()):
                            archive = logs / (stage + "-failed.zip")
                            _archive_failure(data, archive)
                            record["failed_outputs_archive"] = str(archive)
                        _remove_owned_backup(data)
                    if backup is not None and (backup / "previous").exists():
                        (backup / "previous").rename(data)
                        record["previous_output_restored"] = True
                        os.chmod(backup, stat.S_IWRITE | stat.S_IREAD)
                        backup.rmdir()
                except (OSError, ValueError) as recovery:
                    record["recovery_error"] = str(recovery)
                    record["recovery_directory"] = str(backup) if backup else str(data)
                    traceback.print_exc(file=log)
                record["completed_at"] = utc_now()
                record["duration_seconds"] = round(time.monotonic() - started, 3)
                write_json(record_path, record)
                _update_index(root, record)
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise
                raise StepFailure(str(error), record_path) from error
        record["completed_at"] = utc_now()
        record["duration_seconds"] = round(time.monotonic() - started, 3)
        write_json(record_path, record)
        _update_index(root, record)
        if backup is not None and backup.exists():
            try:
                _remove_owned_backup(backup)
            except OSError as error:
                record["cleanup_warning"] = str(error)
                record["cleanup_directory"] = str(backup)
                write_json(record_path, record)
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(f"Cleanup warning: {error}\n")
        work = root / ".work"
        if work.exists() and not any(work.iterdir()):
            try:
                os.chmod(work, stat.S_IWRITE | stat.S_IREAD)
                work.rmdir()
            except OSError as error:
                record["cleanup_warning"] = str(error)
                record["cleanup_directory"] = str(work)
                write_json(record_path, record)
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(f"Cleanup warning: {error}\n")
        return record
