import json
from html.parser import HTMLParser

import pytest

from lineage_poc.lineage_workflow import build_columns, build_graphs, parse_sources, render_graphs
from lineage_poc.viewers.graph.columns import render_html


def json_scripts(document):
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.identifier = None
            self.scripts = {}

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "script" and attributes.get("type") == "application/json":
                self.identifier = attributes.get("id")
                self.scripts[self.identifier] = ""

        def handle_data(self, data):
            if self.identifier is not None:
                self.scripts[self.identifier] += data

        def handle_endtag(self, tag):
            if tag == "script":
                self.identifier = None

    parser = Parser()
    parser.feed(document)
    return {key: json.loads(value) for key, value in parser.scripts.items()}


@pytest.fixture
def recorded_snapshots(source_factory, tmp_path):
    parsed, graphs, columns = (tmp_path / name for name in ("parsed", "graphs", "columns"))
    parse_sources(source_factory(), parsed)
    build_graphs(parsed, graphs, scope="account")
    build_columns(parsed, graphs, columns)
    return graphs, columns


def test_combined_index_embeds_exact_dictionary_and_retains_graph_controls(recorded_snapshots, tmp_path):
    graphs, columns = recorded_snapshots
    destination = tmp_path / "combined"
    destination.mkdir()
    dictionary = destination / "_dictionary.html"
    original = '\ufeff<!doctype html>\r\n<title>Māori & "dictionary"</title>\r\n<script>window.test="</script>";</script>\r\n'
    dictionary.write_bytes(original.encode("utf-8"))
    result = render_graphs(graphs, columns, destination, dictionary_html=dictionary)
    page = (destination / "index.html").read_text(encoding="utf-8")
    assert json_scripts(page)["embedded-dictionary-document"] == original
    assert "\\u003c/script>" in page
    assert ".srcdoc=embeddedDictionaryDocument" in page
    assert all(f'id="{control}"' in page for control in ("detailedView", "schemaView", "dictionaryView"))
    assert result["iframe_id"] == "dictionaryAppFrame"
    assert result["index"] == str(destination / "index.html")
    assert set(result["outputs"]) == {"index"}
    dictionary.unlink()
    assert [path.name for path in destination.glob("*.html")] == ["index.html"]
    assert 'src="column_lineage_dictionary.html"' not in page


def test_dictionary_is_read_before_overwriting_same_index(recorded_snapshots, tmp_path):
    graphs, columns = recorded_snapshots
    destination = tmp_path / "combined"
    destination.mkdir()
    index = destination / "index.html"
    original = "<!doctype html><title>Final dictionary before combination</title>"
    index.write_text(original, encoding="utf-8")
    render_graphs(graphs, columns, destination, dictionary_html=index, selector="KiwiAcc")
    page = index.read_text(encoding="utf-8")
    assert json_scripts(page)["embedded-dictionary-document"] == original
    assert "KiwiAcc (DWACC) Column Lineage" in page
    assert [path.name for path in destination.glob("*.html")] == ["index.html"]


def test_multiple_aliases_do_not_duplicate_mappings_and_unknown_selectors_fail(recorded_snapshots, tmp_path):
    graphs, columns = recorded_snapshots
    destination = tmp_path / "focused"
    result = render_graphs(graphs, columns, destination, selector=["KiwiAcc", "Account ID", "KiwiAcc"])
    document = (destination / "index.html").read_text(encoding="utf-8")
    assert result["records"] == 1
    assert [record["param_column"] for record in json_scripts(document)["column-data"]] == ["KiwiAcc"]
    with pytest.raises(ValueError, match="NoSuchColumn"):
        render_graphs(graphs, columns, tmp_path / "rejected", selector=["KiwiAcc", "NoSuchColumn"])
    assert not (tmp_path / "rejected" / "index.html").exists()
    assert (destination / "index.html").read_text(encoding="utf-8") == document


def test_combined_index_can_live_at_parent_output_root(recorded_snapshots, tmp_path):
    graphs, columns = recorded_snapshots
    before_graph = (graphs / "account_table_lineage.json").read_bytes()
    before_columns = (columns / "column_lineage.json").read_bytes()
    result = render_graphs(graphs, columns, tmp_path)
    assert result["index"] == str(tmp_path / "index.html")
    assert (graphs / "account_table_lineage.json").read_bytes() == before_graph
    assert (columns / "column_lineage.json").read_bytes() == before_columns


def test_omitted_dictionary_uses_existing_derived_view_not_a_prebuilt_snapshot(recorded_snapshots, tmp_path):
    graphs, columns = recorded_snapshots
    destination = tmp_path / "combined"
    render_graphs(graphs, columns, destination)
    page = (destination / "index.html").read_text(encoding="utf-8")
    assert json_scripts(page)["embedded-dictionary-document"] == ""
    assert "function buildDictionarySections()" in page
    assert [path.name for path in destination.glob("*.html")] == ["index.html"]


def test_relationship_template_substitutions_never_rewrite_embedded_evidence():
    original = "DWACC evidence, accounts-v1 and literal __DICTIONARY_DOCUMENT__ / __COLUMN_DATA__ must remain exact."
    graph = {"nodes": [{"id": "fixture", "type": "PROGRAM", "properties": {"name": "KWDW_ACC", "evidence": original}}], "edges": []}
    page = render_html(graph, [], dictionary_document=original, feed="DWREL", selector="RelType")
    payloads = json_scripts(page)
    assert payloads["embedded-dictionary-document"] == original
    table = next(value for value in payloads.values() if isinstance(value, dict) and "nodes" in value and value["nodes"])
    assert table["nodes"][0]["properties"]["evidence"] == original
    assert "RelType (DWREL) Column Lineage" in page
    assert "schemaFlowFind('DBT_MODEL','name','account_relationship_v1__customer_account_relationship_v1')" in page
    assert "schemaFlowFind('SNOWFLAKE_RELATION','name','INTERNAL.ACCOUNT_RELATIONSHIP_V1__CUSTOMER_ACCOUNT_RELATIONSHIP_V1')" in page
