#!/usr/bin/env python3
"""Build one fully offline dictionary HTML file at an explicit destination."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path

from lineage_poc.dictionary.io import CSV_FILES, atomic_write, require
from lineage_poc.validation.bundle import validate_bundle


def build(output_dir: Path, destination: Path | None = None, *,
          manifest: dict | None = None, verbose: bool = True) -> Path:
    """Validate a matching CSV bundle and atomically write only the chosen HTML.

    Without ``destination`` the target is exactly ``output_dir / 'index.html'``.
    There is no publication root, latest-folder search, or CSV mutation.
    """
    output_dir = Path(output_dir).resolve()
    target = Path(destination).resolve() if destination is not None else output_dir / 'index.html'
    require(target not in {output_dir / name for name in CSV_FILES},
            'HTML destination must not replace an input CSV')
    validation = validate_bundle(output_dir)
    source_bytes = {name: (output_dir / name).read_bytes() for name in CSV_FILES}
    for name in CSV_FILES:
        require(hashlib.sha256(source_bytes[name]).hexdigest() == validation['outputs'][name]['sha256'],
                'Input bundle changed while building HTML: ' + name)
    manifest = {} if manifest is None else manifest
    require(isinstance(manifest, dict), 'HTML manifest must be an object')
    if manifest.get('outputs'):
        for name in CSV_FILES:
            claim = manifest['outputs'].get(name, {})
            require(all(claim.get(metric) == value
                        for metric, value in validation['outputs'][name].items()),
                    'Manifest hash or counts do not match ' + name)
    files = {name: contents.decode('utf-8') for name, contents in source_bytes.items()}
    payload = json.dumps({'files': files, 'manifest': manifest}, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    assets = Path(__file__).resolve().parent / 'assets'
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
        require(not re.search(r'</script', replacements[marker], flags=re.I),
                'Unsafe closing script tag in ' + marker)
    html = (assets / 'viewer.template.html').read_text(encoding='utf-8')
    for marker, value in replacements.items():
        require(html.count(marker) == 1, 'Template must contain exactly one ' + marker)
        html = html.replace(marker, value)
    atomic_write(target, html.encode('utf-8'))
    if verbose:
        print(json.dumps({'html': str(target), 'bytes': target.stat().st_size,
                          'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                          'embedded_csv_files': list(CSV_FILES)}, indent=2))
    return target


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Folder containing all three matching CSVs')
    parser.add_argument('--destination', type=Path,
                        help='HTML destination (default: OUTPUT_DIR/index.html); never publishes elsewhere')
    args = parser.parse_args(argv)
    build(args.output_dir, args.destination)


if __name__ == '__main__':
    main()
