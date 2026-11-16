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


def build_tmv_document(directory: Path) -> str:
    """Use the reference dictionary UI with an explicit TMV display adapter."""
    from lineage_poc.dictionary.tmv import validate as validate_tmv

    validate_tmv(directory)
    assets = Path(__file__).resolve().parent / "assets"
    files = {name: (directory / name).read_bytes() for name in CSV_FILES}
    v1_core = (assets / "v1_core.js").read_text(encoding="utf-8")
    adapter = (assets / "tmv_adapter.js").read_text(encoding="utf-8")
    v1_app = (assets / "v1_viewer.js").read_text(encoding="utf-8")
    v1_app = v1_app.replace("Ultracs source mapping", "Source SQL mapping")
    v1_app = v1_app.replace("'Source program'", "'SQL source path'")
    v1_app = v1_app.replace("'HVR declared type',raw.hvr_type", "'Input declared type',raw.source_data_type")
    v1_app = v1_app.replace("'Extract parameter',raw.extract_column", "'Source column',raw.source_column")
    v1_app = v1_app.replace("'Extract / position',string(raw.extract_file)+'['+string(raw.extract_position)+']'", "'Repository / product',string(raw.repository)+' / '+string(raw.project)")
    v1_app = v1_app.replace("string(row.raw.extract_file)+'['+string(row.raw.extract_position)+'] · '+string(row.raw.extract_column)", "string(row.raw.repository)+' · '+string(row.raw.project)")
    v1_app = v1_app.replace("(row.sourceName||row.sourceId)+' · '+string(row.raw.extract_file)+'['+string(row.raw.extract_position)+']'", "(row.sourceName||row.sourceId)+' · '+row.raw.source_relation")
    registry_app = (assets / "registry_app.js").read_text(encoding="utf-8")
    registry_app = registry_app.replace("function refreshMappingDetails(){", "function refreshMappingDetails(){if(window.TMVViewerAdapter)return;")
    registry_app = registry_app.replace("Source / HVR positions", "SQL source reference")
    registry_app = registry_app.replace("Source system / layer", "Repository / reported layer")
    registry_app = registry_app.replace("Physical source file not supplied", "Declared relation, not runtime verified")
    registry_app = registry_app.replace("'Source system'", "'Repository'")
    registry_app = registry_app.replace("'No source locator'", "'No SQL reference supplied'")
    registry_app = registry_app.replace("'Source, HVR and route details'", "'Source and SQL evidence'")
    payload = json.dumps({"files": {name: blob.decode("utf-8") for name, blob in files.items()},
                          "manifest": {"contract": "tmv-dictionary-v1"}}, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    replacements = {
        "@@V1_CORE@@": v1_core + "\n" + adapter,
        "@@V1_APP@@": v1_app,
        "@@V1_CSV_GZIP@@": base64.b64encode(gzip.compress(files["data_dictionary.csv"], mtime=0)).decode("ascii"),
        "@@V3_CORE@@": (assets / "viewer_core.js").read_text(encoding="utf-8"),
        "@@V3_BUNDLE_CORE@@": (assets / "bundle_core.js").read_text(encoding="utf-8") + "\nwindow.TMVViewerAdapter.installBundle();",
        "@@V3_APP@@": registry_app,
        "@@V3_CSS@@": (assets / "registry.css").read_text(encoding="utf-8"),
        "@@V3_BUNDLE_GZIP@@": base64.b64encode(gzip.compress(payload, mtime=0)).decode("ascii"),
    }
    document = (assets / "viewer.template.html").read_text(encoding="utf-8")
    document = document.replace("Ultracs fields, recorded processing and Snowflake outcomes", "TMV Account fields, recorded SQL processing and Snowflake outcomes")
    run_profile = json.loads((directory / "manifest.json").read_text(encoding="utf-8")).get("run_profile")
    if run_profile in {"account-domain", "cdp-account"}:
        document = document.replace("TMV Account fields", "CDP Account fields" if run_profile == "cdp-account" else "Account-domain fields").replace("recorded SQL processing and Snowflake outcomes", "recorded SQL and EF bindings and database outcomes")
        replacements["@@V1_APP@@"] = replacements["@@V1_APP@@"].replace("Source SQL mapping", "Source mapping declaration").replace("SQL source path", "Source evidence path")
    document = document.replace("Ultracs source mapping", "Source SQL mapping").replace("Ultracs source", "Source relation / column")
    document = document.replace("<label for=\"registry-system\">Source system</label>", "<label for=\"registry-system\">Repository</label>")
    document = document.replace("Ultracs assets may represent program-scoped multi-value contexts; a physical source file is not inferred.", "TMV assets are repository-declared relations; physical deployment is not independently verified.")
    for marker, value in replacements.items():
        require(document.count(marker) == 1, "Reference template marker changed: " + marker)
        if marker.endswith("APP@@") or "CORE@@" in marker:
            require(not re.search(r"</script", value, re.I), "Unsafe script value in " + marker)
        document = document.replace(marker, value)
    return document


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
