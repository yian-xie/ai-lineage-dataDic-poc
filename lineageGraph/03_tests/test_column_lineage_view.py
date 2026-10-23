import json
import sys
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from generate_column_lineage import DICTIONARY_OUTPUT, DICTIONARY_TEMPLATE, HTML, _validate_dictionary_snapshot, build_enterprise_overview, build_records
import generate_account_number_lineage as focused_lineage
from generate_account_lineage_html import HTML as ACCOUNT_GRAPH_HTML
from generate_table_lineage_html import HTML as TABLE_GRAPH_HTML
from html_graph_descriptions import describe_graph


def test_column_records_include_ultracs_and_cdp_descriptions():
    records = build_records()

    assert len(records) == 95
    assert [record["ultracs_position"] for record in records] == list(range(1, 96))
    assert sum(len(record["dbt_targets"]) for record in records) == 179
    assert {f"MissingColumn{index}" for index in range(1, 7)} <= {
        record["param_column"] for record in records
    }
    for record in records:
        assert record["ultracs"]["basic_expression"]
        assert record["hvr_parameter"]["name"] == record["param_column"]
        assert record["dbt_targets"]
        assert record["cdp"]["model"]
        assert record["cdp"]["source_path"]
        assert all(target["stage"] in {"internal", "public"} for target in record["dbt_targets"])
    account_number = next(record for record in records if record["param_column"] == "KiwiAcc")
    assert any(
        target["stage"] == "public" and target["column"] == "KIWIBANKACCOUNTNUMBER"
        for target in account_number["dbt_targets"]
    )


def test_column_graph_has_control_to_hide_unmapped_direct_route_nodes():
    assert 'id="hideDirectBranch"' in HTML
    assert "(!hideDirect||node.route!=='direct')" in HTML
    assert "(!hideDirect||edge.route!=='direct')" in HTML
    assert 'id="mappedPathOnly"' in HTML
    assert "(!mappedOnly||mappedPathNodeIds.has(node.id))" in HTML
    assert "record.dbt_targets?.map(target=>target.relation)" in HTML


def test_column_graph_exposes_repository_aware_column_schema_overview():
    assert 'id="detailedView"' in HTML
    assert 'id="schemaView"' in HTML
    assert "schemaRepositories" in HTML
    assert "EXTRACTED_AS" in HTML
    assert "MAPS_TO" in HTML
    assert "record.cdp?.data_type" in HTML
    assert "record.ultracs?.source_locator" in HTML
    assert 'id="editSchema"' in HTML
    assert 'id="resetSchemaEdits"' in HTML
    assert 'data-edit-key="' in HTML
    assert "localStorage.setItem(schemaEditsKey" in HTML
    assert "setGraphView('detailed')" in HTML
    assert "setGraphView('schema')" in HTML
    assert "parser-backed table lineage only" in HTML
    assert "Evidence confidence % is heuristic, not probability" in HTML
    assert "confidenceLabel(record.confidence)" in HTML
    assert "confidenceLabel(edge.confidence)" in HTML


def test_schema_overview_defaults_to_five_generic_collapsed_stages():
    diagram = HTML.split('<section id="schemaDiagram"', 1)[1].split('</section>\n  </section>', 1)[0]
    assert 'id="schemaFanout"' in diagram
    assert 'id="schemaDirectBranch"' in diagram
    assert "const schemaFlowGroups=[" in HTML
    assert "const schemaFlowLinks=[" in HTML
    for entity in ("ACCOUNT", "TRAN", "KWDW_ACC", "DWACC", "ult_s3_acc", "copy_s3_files_to_snowflake_task_for_dwacc", "accounts_v1__ultracs_accounts_detail", "PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL"):
        assert entity in HTML
    assert "LOADACCOUNTS_INGEST" in HTML
    assert "No repository evidence connects the direct HVR landing relation" in HTML
    for shape in ("shape-source", "shape-extract", "shape-staging", "shape-jobs", "shape-target"):
        assert f"{shape}{{" in HTML
    for color in ("#24794f", "#c4893d", "#218b83", "#7963a1", "#397b9d"):
        assert color in HTML
    assert "function renderSchemaFanout()" in HTML
    assert "function renderSchemaLinks()" in HTML
    assert "setTimeout(renderSchemaLinks,160)" in HTML
    assert 'class="schema-flow-links"' in diagram
    assert 'class="schema-flow-arrow"' not in diagram
    assert "body.schema-mode:not(.schema-detail-mode) #network" in HTML
    assert "min-width:900px" in HTML
    assert '<button id="detailedView" type="button" aria-pressed="true">Detailed</button>' in HTML
    assert '<button id="schemaView" type="button" aria-pressed="false">Schema overview</button>' in HTML
    assert '<button id="schemaPresentationView" type="button" aria-pressed="true">Schema view</button>' in HTML
    assert '<button id="schemaPresentationDetail" type="button" aria-pressed="false">Detail view</button>' in HTML
    assert "let graphView='detailed',schemaPresentation='schema'" in HTML
    assert "function setSchemaPresentation(mode)" in HTML
    assert "dataNodes.add(schemaCanvasNodes);dataEdges.add(schemaCanvasEdges)" in HTML
    assert "applyFilters();\n</script>\n</body>\n</html>" in HTML


def test_expanded_schema_groups_reuse_existing_node_inspector():
    assert "source:new Set(['MV_FILE'])" in HTML
    assert "extract:new Set(['PROGRAM','EXTRACT_FILE'])" in HTML
    assert "staging:new Set(['HVR_CHANNEL','HVR_LOCATION'])" in HTML
    assert "'DBT_MODEL'" in HTML and "'SNOWFLAKE_RELATION'" in HTML
    assert "for(const node of tableGraph.nodes)" in HTML
    assert "groupOnly:true" in HTML
    assert "schemaNodes.filter(node=>!node.groupOnly)" in HTML
    assert "function renderSchemaFanout()" in HTML
    assert "function schemaFlowNodeButton(entry)" in HTML
    assert "schemaFlowNodeGroupIds" not in HTML
    assert "function renderSchemaGroup(group)" not in HTML
    assert "function openSchemaInspector(id)" in HTML
    assert "setNodePanel(id)" in HTML
    assert "schemaNodeGroupById.get(selectedSchemaNodeId)===group" in HTML
    assert "body.schema-mode:not(.schema-inspector-open) .inspector{display:none}" in HTML


def test_column_graph_has_derived_data_dictionary_view():
    assert 'id="dictionaryView"' in HTML
    assert 'id="dataDictionaryView"' in HTML
    assert 'data-dictionary-tab="assets"' in HTML
    assert 'data-dictionary-tab="fields"' in HTML
    assert 'data-dictionary-tab="lineage"' in HTML
    assert "const dictionaryNotDocumented='Not documented'" in HTML
    assert "buildDictionarySections()" in HTML
    assert "enterpriseOverview.nodes" in HTML
    assert "enterpriseOverview.edges" in HTML
    assert "dictionaryGraphEdges" in HTML
    assert "'Owner':properties.owner||dictionaryNotDocumented" in HTML
    assert "'Sample Values':dictionaryNotDocumented" in HTML
    assert "'Is PII?':dictionaryNotDocumented" in HTML
    assert "downloadDictionaryCsv()" in HTML


def test_data_dictionary_has_filtered_catalog_paging_and_evidence_dialog():
    for element_id in (
        "dd-source", "dd-stage", "dd-table", "dd-column", "dd-review",
        "dd-clear", "dd-page-size", "dd-prev", "dd-next", "dd-row-dialog",
        "dd-dialog-body", "dd-dialog-prev", "dd-dialog-next",
    ):
        assert f'id="{element_id}"' in HTML
    assert "function updateDictionaryFilterOptions()" in HTML
    assert "function filterDictionaryRows()" in HTML
    assert "function openDictionaryRow(index)" in HTML
    assert "function dictionaryPublicColumns(row)" in HTML
    assert "return dictionaryPublicColumns(row).map(column=>[column,column])" in HTML
    assert "filteredDictionaryRows=filterDictionaryRows()" in HTML
    assert "dictionaryPageSize==='all'" in HTML
    assert "data-dictionary-row=\"" in HTML
    assert "row._reviewReasons" in HTML
    assert "download='data_dictionary_'+activeDictionarySection+'.csv'" in HTML


def test_poc_dictionary_embeds_v3_viewer_and_schema_palette():
    template = PROJECT_ROOT / "templates/data_dictionary_v3.html"
    assert 'id="dictionaryAppFrame"' in HTML
    assert 'src="column_lineage_dictionary.html"' in HTML
    assert template.exists()
    assert DICTIONARY_TEMPLATE == template
    assert DICTIONARY_OUTPUT.name == "column_lineage_dictionary.html"
    viewer = template.read_text(encoding="utf-8")
    for feature in (
        'id="csv-file"', 'id="registry-bundle-files"', 'id="filter-operation"',
        'id="add-custom"', 'id="tab-asset-registry"', 'id="tab-field-catalog"',
        'id="record-dialog"', 'id="registry-dialog"', 'id="embedded-registry-bundle"',
        "window.DDV3", "function exportFilteredCSV()",
    ):
        assert feature in viewer
    assert 'id="poc-schema-palette"' in viewer
    assert "--teal:#218b83" in viewer
    assert "--blue:#397b9d" in viewer
    assert "--purple:#7963a1" in viewer
    assert "--coral:#d87968" in viewer


def test_v3_dictionary_snapshot_matches_current_column_input():
    _validate_dictionary_snapshot(build_records())


def test_data_dictionary_csv_template_has_manager_fields():
    template = PROJECT_ROOT / "examples/data_dictionary_template"
    with (template / "asset_registry.csv").open(encoding="utf-8", newline="") as stream:
        asset_headers = next(csv.reader(stream))
    with (template / "field_catalog.csv").open(encoding="utf-8", newline="") as stream:
        field_headers = next(csv.reader(stream))
    with (template / "lineage_links.csv").open(encoding="utf-8", newline="") as stream:
        lineage_headers = next(csv.reader(stream))

    assert {"asset_name", "source_system", "layer", "domain", "owner", "steward", "update_frequency", "row_count_approx", "lineage_reference", "pii_sensitivity", "status"} <= set(asset_headers)
    assert {"asset_name", "field_name", "business_name", "data_type", "description", "sample_values", "allowed_values_enum", "nullable", "is_pii", "is_primary_key", "foreign_key_reference", "business_rules", "last_verified_date", "notes"} <= set(field_headers)
    assert {"upstream_sources", "downstream_consumers", "transformation_step", "dependency_notes"} <= set(lineage_headers)
    assert all((template / name).exists() for name in ("README.md", "glossary.csv", "change_log.csv"))


def test_enterprise_schema_overview_tracks_parser_derived_table_lineage():
    overview = build_enterprise_overview(build_records())
    models = [node for node in overview["nodes"] if node["type"] == "DBT_MODEL"]
    sources = [node for node in overview["nodes"] if node["type"] == "DBT_SOURCE"]

    assert overview["input_relations"] == sorted({
        target["relation"]
        for record in build_records()
        for target in record["dbt_targets"]
    })
    assert models
    assert sources
    assert all(node["properties"]["source_path"].startswith("kb-cdp-tenant-enterprise/") for node in models)
    assert {edge["type"] for edge in overview["edges"]} >= {
        "RESOLVES_TO",
        "DEPENDS_ON",
        "MATERIALIZES_AS",
    }


def test_focused_account_number_graph_embeds_enterprise_data_and_datatype(tmp_path, monkeypatch):
    monkeypatch.setattr(focused_lineage, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(focused_lineage, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["generate_account_number_lineage.py", "--column", "KiwiAcc"])

    focused_lineage.main()
    html = (tmp_path / "account_number_lineage.html").read_text(encoding="utf-8")

    assert "__ENTERPRISE_DATA__" not in html
    assert "Datatype: KIWIBANKACCOUNTNUMBER: VARCHAR(100)" in html
    assert "95% evidence" in html
    assert 'id="enterprise-data"' in html
    assert '"model_count":20' in html


def test_confidence_percentage_rubric_is_consistent_across_graph_templates():
    from generate_column_lineage import confidence_percent

    assert confidence_percent("explicit") == 95
    assert confidence_percent("confirmed_calculated") == 90
    assert confidence_percent("declared_source") == 85
    assert confidence_percent("inferred") == 60
    assert confidence_percent("unresolved") is None
    assert "confidenceLabel(node.properties?.confidence)" in ACCOUNT_GRAPH_HTML
    assert "confidenceLabel(edge.properties?.confidence)" in TABLE_GRAPH_HTML
    assert "heuristic, not probability" in ACCOUNT_GRAPH_HTML
    assert "heuristic, not probability" in TABLE_GRAPH_HTML


def test_confidence_level_filter_exists_across_detailed_schema_and_table_views():
    assert 'id="confidenceFilter"' in HTML
    assert 'id="confidenceFilter"' in ACCOUNT_GRAPH_HTML
    assert 'id="confidenceFilter"' in TABLE_GRAPH_HTML
    assert 'type="checkbox" data-confidence value="inferred" checked' in HTML
    assert 'type="checkbox" data-confidence value="explicit" checked' in ACCOUNT_GRAPH_HTML
    assert "activeConfidenceBuckets=new Set" in HTML
    assert "function applySchemaConfidenceFilter()" in HTML
    assert "confidenceAllowed(edge.confidence)" in HTML
    assert "confidenceAllowed(edge.properties?.confidence)" in ACCOUNT_GRAPH_HTML
    assert "confidenceAllowed(edge.properties?.confidence)" in TABLE_GRAPH_HTML
    assert "confidenceFilter.querySelectorAll('[data-confidence]')" in HTML


def test_html_description_metadata_covers_nodes_and_relationships_without_changing_graph_json():
    source = json.loads(
        (PROJECT_ROOT / "output/account_table_lineage.json").read_text(encoding="utf-8")
    )
    described = describe_graph(source)

    assert all(node["properties"]["html_description"] for node in described["nodes"])
    assert all(node["properties"]["html_description_origin"] in {"Repository sourced", "Generated"} for node in described["nodes"])
    assert all(edge["properties"]["html_description"] for edge in described["edges"])
    assert all(edge["properties"]["html_description_origin"] in {"Repository evidence", "Generated"} for edge in described["edges"])
    assert all("html_description" not in item.get("properties", {}) for item in source["nodes"] + source["edges"])
    assert "html_description_origin" in ACCOUNT_GRAPH_HTML
    assert "html_description_origin" in TABLE_GRAPH_HTML
    assert "html_description_origin" in HTML