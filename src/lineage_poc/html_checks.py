"""Check the actual saved dictionary payload, independently of browser rendering."""

import base64
import csv
import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from .execution import read_json, sha256_file

CSV_FILES = ("asset_registry.csv", "field_catalog.csv", "data_dictionary.csv")


def validate_view_inputs(bundle_dir: Path, columns_dir: Path, graphs_dir: Path) -> dict:
    """Tie both displayed views to the same inventory and compatible graph context."""
    inventory_path = columns_dir / "column_lineage.json"
    records = read_json(inventory_path)
    if not isinstance(records, list) or not records or not all(isinstance(row, dict) for row in records):
        raise ValueError("The combined report requires a nonempty column inventory.")
    by_id = {}
    expected_pairs = set()
    for record in records:
        identity = record.get("field_id")
        if not isinstance(identity, str) or not identity or identity in by_id:
            raise ValueError("Column inventory needs unique mapping field_id values.")
        by_id[identity] = record
        for target in record.get("dbt_targets", []):
            expected_pairs.add((identity, target["relation"], target["column"]))
    fingerprint = sha256_file(inventory_path)
    represented = set()
    pairs = set()
    with (bundle_dir / "data_dictionary.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            original = json.loads(row["original_record_json"])
            provenance = json.loads(row["provenance_json"])
            identity = original.get("field_id")
            if identity not in by_id or original != by_id[identity]:
                raise ValueError("The dictionary and graph column inventory contain different source records.")
            if (
                row["snapshot_id"] != "sha256:" + fingerprint
                or provenance.get("input_sha256") != fingerprint
            ):
                raise ValueError("The dictionary snapshot does not match the selected column inventory bytes.")
            represented.add(identity)
            pairs.add((identity, row["snowflake_table"], row["snowflake_column"]))
    if represented != set(by_id) or pairs != expected_pairs:
        raise ValueError("The dictionary and selected column inventory have different target coverage.")
    manifests = [directory / "manifest.json" for directory in (columns_dir, graphs_dir)]
    if all(path.is_file() for path in manifests):
        column_manifest, graph_manifest = [read_json(path) for path in manifests]
        left, right = (value.get("parse_manifest_sha256") for value in (column_manifest, graph_manifest))
        if left and right and left != right:
            raise ValueError("The graph and column inventory were built from different parse snapshots.")
    graph_ids = set()
    for name in ("account_table_lineage.json", "table_lineage.json",
                 "account_enterprise_lineage.json"):
        path = graphs_dir / name
        if path.is_file():
            graph = read_json(path)
            graph_ids.update(node["id"] for node in graph["nodes"])
    if not graph_ids or any(relation not in graph_ids for _, relation, _ in pairs):
        raise ValueError("The selected graph context does not contain every dictionary target relation.")
    return {"status": "passed", "input_sha256": fingerprint,
            "mapping_records": len(by_id), "target_pairs": len(pairs)}


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.identities: set[str] = set()
        self.tabs = 0
        self.external_scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        identity = attributes.get("id")
        if identity:
            if identity in self.identities:
                raise ValueError(f"Duplicate HTML ID: {identity}")
            self.identities.add(identity)
        if attributes.get("role") == "tab":
            self.tabs += 1
        if tag == "script" and attributes.get("src"):
            self.external_scripts.append(str(attributes["src"]))


def check_html(html_path: Path, bundle_dir: Path) -> dict:
    outer_html = html_path.read_text(encoding="utf-8")
    embedded = re.findall(
        r'<script\b[^>]*\bid="embedded-dictionary-document"[^>]*>(.*?)</script>',
        outer_html, flags=re.S,
    )
    combined = bool(embedded)
    html = outer_html
    graph_scripts = []
    if combined:
        if len(embedded) != 1:
            raise ValueError("The combined report must contain one embedded dictionary document.")
        html = json.loads(embedded[0])
        if not isinstance(html, str):
            raise ValueError("The embedded dictionary document must be HTML text.")
        outer = _Page()
        outer.feed(outer_html)
        if not {"detailedView", "schemaView"} <= outer.identities:
            raise ValueError("The combined report is missing its lineage graph controls.")
        graph_scripts = outer.external_scripts

    def unpack(identity: str) -> bytes:
        matches = re.findall(
            r'<script\b[^>]*\bid="' + re.escape(identity) + r'"[^>]*>(.*?)</script>',
            html, flags=re.S,
        )
        if len(matches) != 1:
            raise ValueError(f"Expected one embedded payload: {identity}")
        return gzip.decompress(base64.b64decode(matches[0].strip(), validate=True))

    payload = json.loads(unpack("embedded-registry-bundle"))
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        raise ValueError("The embedded registry bundle must contain a files object.")
    if set(payload["files"]) != set(CSV_FILES):
        raise ValueError("The HTML must embed exactly the three matching CSV filenames.")
    hashes = {}
    for name in CSV_FILES:
        original = (bundle_dir / name).read_bytes()
        if payload["files"][name] != original.decode("utf-8"):
            raise ValueError(f"Embedded HTML differs from the selected CSV: {name}")
        hashes[name] = hashlib.sha256(original).hexdigest()
    if unpack("embedded-csv") != (bundle_dir / "data_dictionary.csv").read_bytes():
        raise ValueError("The legacy Dictionary and registry payloads disagree.")
    if re.search(r"@@[A-Z0-9_]+@@", html):
        raise ValueError("The saved HTML contains an unexpanded template marker.")
    page = _Page()
    page.feed(html)
    if page.tabs != 3:
        raise ValueError(f"Expected exactly three dictionary tabs, found {page.tabs}.")
    if page.external_scripts:
        raise ValueError("The standalone dictionary must not require external scripts.")
    return {
        "status": "passed", "scope": "saved payload and HTML structure, not a browser UI test",
        "html_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
        "dictionary_html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "combined_graph_and_dictionary": combined,
        "graph_external_scripts": graph_scripts,
        "embedded_csv_sha256": hashes, "tabs": page.tabs, "external_scripts": [],
    }
