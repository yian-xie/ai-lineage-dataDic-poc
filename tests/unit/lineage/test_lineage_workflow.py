import hashlib
import json
import shutil
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from lineage_poc.columns import dwacc
from lineage_poc.graph.account import with_related_columns
from lineage_poc.graph.query_tools import get_alias_chain, get_field_lineage
from lineage_poc.graph.merge import merge_files
from lineage_poc.lineage_workflow import build_columns, build_graphs, parse_sources, render_graphs
from lineage_poc.parsers.snapshot import load_snapshot, read_json, write_json
from lineage_poc.publishing import extract_hvr_map, extract_inventory, repo_access
from lineage_poc.publishing.report import build_site


def test_parse_records_exact_bytes_ordered_metadata_and_hashes(source_factory, tmp_path):
    source = source_factory()
    parsed = tmp_path / "parsed"
    result = parse_sources(source, parsed)
    original = source / "kb-ultracs-datawarehouse" / "KWDW_ACC"
    with load_snapshot(parsed, workspace=tmp_path / "materialized") as (manifest, evidence):
        snapshot = evidence / "kb-ultracs-datawarehouse" / "KWDW_ACC"
        assert snapshot.read_bytes() == original.read_bytes()
        assert b"\r\n" in snapshot.read_bytes()
    assert not evidence.exists()
    assert (parsed / "source-snapshot.zip").is_file()
    assert not (parsed / "source_snapshot").exists()
    assert not list(parsed.glob(".lineage-evidence-*"))
    assert not (parsed / "parameters").exists()
    entry = next(item for item in manifest["files"] if item["path"] == "kb-ultracs-datawarehouse/KWDW_ACC")
    assert entry["sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
    assert not any(".git" in Path(item["path"]).parts for item in manifest["files"])
    assert manifest["evidence_type"] == "exact_source_file_zip_snapshot_with_sha256"
    assert "graph fragments alone do not establish column mappings" in manifest["column_mapping_basis"]
    assert read_json(parsed / "hvr_param_metadata.json")["columns"][0]["name"] == "KiwiAcc"
    assert "table_inputs" in result["outputs"]
    json.dumps(result)


def test_stages_survive_removed_checkouts_and_foreign_cwd(source_factory, tmp_path, monkeypatch):
    description = "Māori account\n</script> & evidence"
    source = source_factory(description=description)
    parsed, graphs, columns, html = (tmp_path / name for name in ("parsed", "graphs", "columns", "html"))
    parse_sources(source, parsed)
    shutil.rmtree(source)
    elsewhere = tmp_path / "unrelated-cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("LINEAGE_SOURCE_ROOT", str(elsewhere / "missing-live-repositories"))

    def no_column_rebuild(*args, **kwargs):
        raise AssertionError("A graph/render stage must not rebuild column records.")

    original_builder = dwacc.build_records
    monkeypatch.setattr(dwacc, "build_records", no_column_rebuild)
    graph_result = build_graphs(parsed, graphs, scope="account")
    monkeypatch.setattr(dwacc, "build_records", original_builder)
    column_result = build_columns(parsed, graphs, columns)
    records = read_json(columns / "column_lineage.json")
    assert len(records) == 1
    assert records[0]["cdp"]["description"] == description
    assert records[0]["ultracs"]["basic_expression"] == "REC<4,8>"
    assert records[0]["confidence"] == "confirmed"
    dictionary = tmp_path / "final-dictionary.html"
    dictionary.write_bytes(("\ufeff<!doctype html>\r\n<title>Final Māori dictionary</title>\r\n").encode("utf-8"))
    monkeypatch.setattr(dwacc, "build_records", no_column_rebuild)
    rendered = render_graphs(graphs, columns, html, dictionary_html=dictionary, selector="KiwiAcc")
    page = (html / "index.html").read_text(encoding="utf-8")
    assert "__TABLE_DATA__" not in page and "__COLUMN_DATA__" not in page and "__ENTERPRISE_DATA__" not in page
    nested = re.search(r'id="embedded-dictionary-document">(.*?)</script>', page, re.S).group(1)
    assert json.loads(nested).encode("utf-8") == dictionary.read_bytes()
    assert ".srcdoc=embeddedDictionaryDocument" in page
    assert 'src="column_lineage_dictionary.html"' not in page
    assert "\\u003c/script>" in page
    assert "\\u0101" in page
    assert set(rendered["outputs"]) == {"index"}
    assert rendered["index"] == str(html / "index.html")
    assert [path.name for path in html.glob("*.html")] == ["index.html"]
    assert all(f'id="{control}"' in page for control in ("detailedView", "schemaView", "dictionaryView"))
    assert not list(graphs.glob(".lineage-evidence-*"))
    assert not list(columns.glob(".lineage-evidence-*"))
    assert {Path(path).parent for path in graph_result["outputs"].values()} == {graphs}
    assert {Path(path).parent for path in column_result["outputs"].values()} == {columns}
    assert {Path(path).parent for path in rendered["outputs"].values()} == {html}
    json.dumps(rendered)


@pytest.mark.parametrize("tamper", ["source", "fragment", "unlisted-source"])
def test_build_rejects_changed_parse_evidence(source_factory, tmp_path, tamper):
    parsed = tmp_path / "parsed"
    parse_sources(source_factory(), parsed)
    if tamper == "fragment":
        (parsed / "fragments" / "table_inputs.json").write_text('{"nodes": [], "edges": []}', encoding="utf-8")
    else:
        archive_path = parsed / "source-snapshot.zip"
        with ZipFile(archive_path) as archive:
            contents = {info.filename: archive.read(info) for info in archive.infolist()}
        if tamper == "source":
            contents["kb-ultracs-datawarehouse/KWDW_ACC"] = b"changed"
        else:
            contents["kb-ultracs-datawarehouse/NEW_PROGRAM"] = b"unrecorded"
        stream = BytesIO()
        with ZipFile(stream, "w") as archive:
            for name, content in contents.items():
                archive.writestr(name, content)
        archive_path.write_bytes(stream.getvalue())
        manifest = read_json(parsed / "manifest.json")
        manifest["snapshot_archive"].update(sha256=hashlib.sha256(stream.getvalue()).hexdigest(), bytes=len(stream.getvalue()))
        write_json(parsed / "manifest.json", manifest)
    with pytest.raises(ValueError, match="integrity check failed"):
        build_graphs(parsed, tmp_path / "graphs", scope="account")


def test_all_parser_requires_every_required_repository(source_factory, tmp_path):
    source = source_factory()
    shutil.rmtree(source / "kb-cdp-tenant-enterprise")
    with pytest.raises(FileNotFoundError, match="kb-cdp-tenant-enterprise"):
        parse_sources(source, tmp_path / "parsed")


def test_selected_basic_parser_does_not_require_other_repositories(tmp_path):
    source = tmp_path / "sources"
    warehouse = source / "kb-ultracs-datawarehouse"
    warehouse.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "KWDW_SAMPLE"
    (warehouse / "KWDW_SAMPLE").write_bytes(fixture.read_bytes())
    parsed, graphs = tmp_path / "parsed", tmp_path / "graphs"
    result = parse_sources(source, parsed, parser="basic")
    shutil.rmtree(source)
    built = build_graphs(parsed, graphs, scope="full")
    assert result["counts"]["source_files"] == 1
    assert built["counts"]["table_lineage"]["nodes"] > 0
    assert set(built["outputs"]) == {"table_lineage"}


def test_columns_reject_graphs_from_a_different_parse_run(source_factory, tmp_path):
    first, second = tmp_path / "parsed-first", tmp_path / "parsed-second"
    parse_sources(source_factory("first", "First description"), first)
    parse_sources(source_factory("second", "Second description"), second)
    graphs = tmp_path / "graphs"
    build_graphs(first, graphs, scope="account")
    with pytest.raises(ValueError, match="different runs"):
        build_columns(second, graphs, tmp_path / "columns")


def test_parallel_runs_keep_source_contexts_independent(source_factory, tmp_path):
    runs = []
    for name, description in (("first", "First Māori description"), ("second", "Second Māori description")):
        parsed, graphs, columns = (tmp_path / f"{name}-{stage}" for stage in ("parsed", "graphs", "columns"))
        parse_sources(source_factory(name, description), parsed)
        build_graphs(parsed, graphs, scope="account")
        runs.append((parsed, graphs, columns))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda args: build_columns(*args), runs))
    assert read_json(runs[0][2] / "column_lineage.json")[0]["cdp"]["description"] == "First Māori description"
    assert read_json(runs[1][2] / "column_lineage.json")[0]["cdp"]["description"] == "Second Māori description"
    assert results[0]["destination"] != results[1]["destination"]


def test_columns_do_not_build_missing_upstream_graphs(source_factory, tmp_path):
    parsed, graphs = tmp_path / "parsed", tmp_path / "graphs"
    parse_sources(source_factory(), parsed)
    graphs.mkdir()
    with pytest.raises(FileNotFoundError, match="Required graph snapshot"):
        build_columns(parsed, graphs, tmp_path / "columns")
    assert list(graphs.iterdir()) == []


def test_related_columns_are_explicit_presentation_composition(source_factory, tmp_path):
    parsed, graphs, columns = (tmp_path / name for name in ("parsed", "graphs", "columns"))
    parse_sources(source_factory(), parsed)
    build_graphs(parsed, graphs, scope="account")
    build_columns(parsed, graphs, columns)
    graph = read_json(graphs / "account_table_lineage.json")
    records = read_json(columns / "column_lineage.json")
    composed = with_related_columns(graph, records)
    before = next(node for node in graph["nodes"] if node["id"] == "extract:DWACC")
    after = next(node for node in composed["nodes"] if node["id"] == "extract:DWACC")
    assert before["properties"]["related_columns"] == []
    assert after["properties"]["related_columns"][0]["hvr_param_column"] == "KiwiAcc"
    aliases = get_alias_chain("KiwiAcc", graphs / "account_table_lineage.json", columns / "column_lineage.json")
    assert aliases["aliases"]
    custom_graph = tmp_path / "composed.json"
    custom_graph.write_text(json.dumps(composed), encoding="utf-8")
    assert get_field_lineage("KiwiAcc", graph_path=custom_graph)["field_mappings"] == []


def test_report_helpers_use_explicit_sources_not_process_cwd(source_factory, tmp_path, monkeypatch):
    source = source_factory()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    inventory_text = extract_inventory.generate_report(source_root=source)
    access_text = repo_access.generate_report(source_root=source)
    assert "KWDW_ACC" in inventory_text and "KWDW_ACC" in access_text
    assert "1 BASIC/BASIC-like" in inventory_text
    inventory = tmp_path / "inventory.md"
    inventory.write_text(inventory_text, encoding="utf-8")
    report = extract_hvr_map.generate_report(inventory=inventory, source_root=source)
    assert "Ultracs Extract to HVR Map" in report
    assert not list(elsewhere.iterdir())


def test_report_site_accepts_recorded_artifacts_outside_project_root(tmp_path):
    root, recorded, destination = (tmp_path / name for name in ("project", "recorded", "published"))
    (root / "docs").mkdir(parents=True)
    recorded.mkdir()
    (root / "docs" / "guide.md").write_text("# Guide\n\n[Graph](../../recorded/graph.html)\n", encoding="utf-8")
    (recorded / "evidence.md").write_text("# Recorded evidence\n", encoding="utf-8")
    (recorded / "graph.html").write_text('<!doctype html><a href="evidence.md">Evidence</a>', encoding="utf-8")
    result = build_site(root, destination, graph_dir=recorded, root_docs=())
    assert result["pages"] == 2
    assert (destination / "reports" / "output" / "evidence.html").is_file()
    assert '../reports/output/evidence.html' in (destination / "output" / "graph.html").read_text(encoding="utf-8")
    assert '../../output/graph.html' in (destination / "reports" / "docs" / "guide.html").read_text(encoding="utf-8")


def test_merge_writes_conflicts_beside_explicit_output(tmp_path):
    graph = {"nodes": [{"id": "fixture", "type": "PROGRAM", "properties": {}}], "edges": []}
    left, right = tmp_path / "left.json", tmp_path / "right.json"
    left.write_text(json.dumps(graph), encoding="utf-8")
    right.write_text(json.dumps(graph), encoding="utf-8")
    destination = tmp_path / "merged" / "graph.json"
    result = merge_files(left, right, destination)
    assert Path(result["conflicts"]) == destination.parent / "merge_conflicts.json"
    assert read_json(destination)["nodes"] == graph["nodes"]
    assert read_json(Path(result["conflicts"])) == {"conflicts": []}
