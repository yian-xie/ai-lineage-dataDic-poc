#!/usr/bin/env python3
"""Bundle a matching three-CSV dictionary into one fully offline HTML viewer."""
from __future__ import annotations
import argparse
import base64
import csv
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path

CSV_FILES = ('asset_registry.csv', 'field_catalog.csv', 'data_dictionary.csv')
DATA_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = DATA_ROOT / '03-output'
DEFAULT_OUTPUT = OUTPUT_ROOT / '01-baseline'


def latest_html_path(output_dir: Path) -> Path | None:
    if output_dir.resolve().parent == OUTPUT_ROOT.resolve():
        return OUTPUT_ROOT / 'index.html'
    return None


def publish_latest_snapshot(snapshot: Path, output_dir: Path) -> Path | None:
    """Publish a completed snapshot while its source and output-root locks are held."""
    latest = latest_html_path(output_dir)
    if latest is None:
        return None
    contents = snapshot.read_bytes()
    descriptor, temporary = tempfile.mkstemp(dir=latest.parent, prefix='.latest-', suffix='.tmp')
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(latest)
    finally:
        temporary.unlink(missing_ok=True)
    return latest

@contextmanager
def output_lock(directory: Path):
    """An OS-released writer lock; lock files live outside the project folder."""
    identity = os.path.normcase(str(directory.resolve()))
    key = hashlib.sha256(identity.encode('utf-8')).hexdigest()
    path = Path(tempfile.gettempdir()) / ('datadic-' + key + '.lock')
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, 'r+b') as handle:
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(handle.fileno()).st_size == 0:
                    handle.write(b'0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('Cannot acquire the output-folder lock. Another run may be using '
                             + str(directory) + '; wait for it to finish and retry.') from error
        yield


def build(output_dir: Path, destination: Path | None = None, *, manifest: dict | None = None, verbose: bool = True) -> Path:
    directories = {output_dir.resolve()}
    latest = latest_html_path(output_dir) if destination is None else None
    if destination is not None:
        directories.add(destination.resolve().parent)
    if latest is not None:
        directories.add(latest.parent.resolve())
    with ExitStack() as locks:
        for directory in sorted(directories, key=str):
            locks.enter_context(output_lock(directory))
        target = _build(output_dir, destination if destination is not None else latest,
                        manifest=manifest, verbose=False)
        if verbose:
            print(json.dumps({
                'html': str(target), 'bytes': target.stat().st_size,
                'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'embedded_csv_files': list(CSV_FILES),
                'latest_html': str(latest) if latest is not None else None,
            }, indent=2))
        return target


def _build(output_dir: Path, destination: Path | None = None, *, manifest: dict | None = None, verbose: bool = True) -> Path:
    skill_dir = Path(__file__).resolve().parent
    assets = skill_dir / 'assets'
    output_dir = output_dir.resolve()
    source_bytes = {name: (output_dir / name).read_bytes() for name in CSV_FILES}
    files = {name: value.decode('utf-8') for name, value in source_bytes.items()}
    csv_counts = {}
    for name, value in files.items():
        reader = csv.reader(io.StringIO(value, newline=''))
        try:
            headers = next(reader)
            if headers:
                headers[0] = headers[0].lstrip('\ufeff')
        except StopIteration as exc:
            raise ValueError(f'{name} is empty') from exc
        if not headers or len(headers) != len(set(headers)):
            raise ValueError(f'{name} has empty or duplicate headers')
        row_count = 0
        for n, row in enumerate(reader, 2):
            row_count += 1
            if len(row) != len(headers):
                raise ValueError(f'{name} record {n} has a different cell count')
        csv_counts[name] = {'rows': row_count, 'columns': len(headers)}
    manifest = {} if manifest is None else manifest
    if manifest.get('outputs'):
        for name in CSV_FILES:
            claim = manifest['outputs'].get(name, {})
            if claim.get('sha256') != hashlib.sha256(source_bytes[name]).hexdigest():
                raise ValueError(f'Manifest hash does not match {name}; regenerate a matching bundle')
            for metric, count in csv_counts[name].items():
                if claim.get(metric) != count:
                    raise ValueError(f'Manifest {metric} does not match {name}')
    payload = json.dumps({'files': files, 'manifest': manifest}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    replacements = {
        '@@V1_CORE@@': (assets / 'v1_core.js').read_text(encoding='utf-8'),
        '@@V1_APP@@': (assets / 'v1_viewer.js').read_text(encoding='utf-8'),
        '@@V1_CSV_GZIP@@': base64.b64encode(gzip.compress(source_bytes['data_dictionary.csv'], mtime=0)).decode('ascii'),
        '@@V3_CORE@@': (assets / 'viewer_core.js').read_text(encoding='utf-8'),
        '@@V3_BUNDLE_CORE@@': (assets / 'bundle_core.js').read_text(encoding='utf-8'),
        '@@V3_APP@@': (assets / 'registry_app.js').read_text(encoding='utf-8'),
        '@@V3_CSS@@': (assets / 'registry.css').read_text(encoding='utf-8'),
        '@@V3_BUNDLE_GZIP@@': base64.b64encode(gzip.compress(payload, mtime=0)).decode('ascii'),
    }
    for marker in ('@@V1_CORE@@', '@@V1_APP@@', '@@V3_CORE@@', '@@V3_BUNDLE_CORE@@', '@@V3_APP@@'):
        if re.search(r'</script', replacements[marker], flags=re.I):
            raise ValueError(f'Unsafe closing script tag in {marker}')
    html = (assets / 'viewer.template.html').read_text(encoding='utf-8')
    for marker, value in replacements.items():
        if html.count(marker) != 1:
            raise ValueError(f'Template must contain exactly one {marker}')
        html = html.replace(marker, value)
    target = destination.resolve() if destination else output_dir / 'index.html'
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix='.html-', suffix='.tmp')
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(html)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    if verbose:
        print(json.dumps({'html': str(target), 'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'embedded_csv_files': list(CSV_FILES)}, indent=2))
    return target

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT, help='Folder containing all three matching CSVs')
    parser.add_argument('--destination', type=Path, help='Preview HTML path; overrides the main viewer (default: 03-output/index.html for managed bundles, otherwise OUTPUT_DIR/index.html)')
    args = parser.parse_args()
    build(args.output_dir, args.destination)

if __name__ == '__main__':
    main()
