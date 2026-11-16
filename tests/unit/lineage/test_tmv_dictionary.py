import json
import base64
import gzip
import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lineage_poc.lineage_workflow import parse_sources, build_graphs, build_columns
from lineage_poc.dictionary.tmv import generate, validate
from lineage_poc.dictionary.io import read_tables, write_table
from lineage_poc.enrichment.tmv import prepare, assemble_review, assemble_schema_review, decisions, apply, revalidate_saved_review
from lineage_poc.parsers.snapshot import write_json, TMV_REPOSITORIES


def make_bundle(tmp_path, description=""):
    source = tmp_path / "sources"
    for repository in TMV_REPOSITORIES:
        (source / repository).mkdir(parents=True)
    accounts = source / "kb-accounts" / "App.csproj"
    accounts.write_text("<Project />", encoding="utf-8")
    for repository in ("kb-cdp-tenant-landing", "kb-cdp-tenant-protect-downstream"):
        dbt = source / repository / "products" / "fixture" / "dbt"
        (dbt / "models").mkdir(parents=True)
        write_json(dbt / "dbt_project.yml", {"name": "fixture", "version": "1.0"})
        declaration = {"version": 2, "sources": [{"name": "raw", "schema": "RAW", "tables": [{"name": "INPUT"}]}],
                       "models": [{"name": "mapped", "config": {"schema": "INTERNAL", "materialized": "view"},
                                   "columns": [{"name": "OUTPUT", "data_type": "VARCHAR", "description": description}]}]}
        write_json(dbt / "models/schema.yml", declaration)
        (dbt / "models/mapped.sql").write_text("SELECT A.INPUT_VALUE AS OUTPUT FROM {{ source('raw','INPUT') }} A", encoding="utf-8")
    parsed, graphs, columns, baseline = (tmp_path / name for name in ("parsed", "graphs", "columns", "baseline"))
    parse_sources(source, parsed, "tmv")
    build_graphs(parsed, graphs, "tmv")
    build_columns(parsed, graphs, columns, "TMV")
    generate(columns / "column_lineage.json", parsed, graphs, baseline)
    return baseline


def test_tmv_dictionary_preserves_own_metadata_and_original_records(tmp_path):
    baseline = make_bundle(tmp_path, 'Existing "description"\nsecond line')
    summary = validate(baseline)
    assert summary["existing_descriptions"] == 2
    assert summary["eligible_missing_descriptions"] == 0
    tables = read_tables(baseline)
    targets = [row for row in tables["field_catalog.csv"].rows if row["is_mapped_target"] == "true"]
    assert all(row["description"] == 'Existing "description"\nsecond line' for row in targets)
    assert all(row["repository"] != "kb-accounts" for row in tables["asset_registry.csv"].rows)


def test_tmv_description_application_preserves_archive_and_confidence(tmp_path):
    baseline = make_bundle(tmp_path)
    context = tmp_path / "context"
    prepare(baseline, context)
    review = tmp_path / "review.json"
    write_json(review, {
        "descriptions": {"0": "The recorded SQL projects INPUT_VALUE as OUTPUT; the business definition remains undocumented."},
        "partial_transformation_groups": [],
        "criterion_judgments": {
            "identity_grounding": "Scoped SQL field only; physical binding is not independently verified.",
            "meaning_support": "The supplied projection supports a technical alias only.",
            "corroboration": "Only one projection claim is available.",
            "uncertainty_handling": "The draft leaves business definition and runtime binding undocumented.",
        }, "limitations": ["Static evidence, not business approval."],
    })
    drafts = tmp_path / "drafts.json"
    assemble_review(context / "context.json", review, drafts)
    rebound = tmp_path / "rebound.json"
    summary = revalidate_saved_review(context / "context.json", drafts, rebound)
    assert summary["authoring_mode"] == "revalidated_existing_assistant_drafts"
    assert json.loads(rebound.read_text(encoding="utf-8"))["reused_from"]["method"]
    tables, results = decisions(baseline, json.loads(drafts.read_text(encoding="utf-8")))
    assert len(results) == 2
    enriched = tmp_path / "enriched"
    summary = apply(baseline, drafts, enriched)
    assert summary["drafts_applied"] == 2
    assert validate(enriched, baseline)["status"] == "passed"
    assert (baseline / "asset_registry.csv").read_bytes() == (enriched / "asset_registry.csv").read_bytes()
    mappings = read_tables(enriched)["data_dictionary.csv"]
    mappings.rows[0]["confidence"] = "runtime_verified"
    write_table(enriched / "data_dictionary.csv", mappings.headers, mappings.rows)
    with pytest.raises(ValueError, match="Original mapping value changed"):
        validate(enriched, baseline)


def test_schema_review_reauthors_same_field_when_evidence_changes(tmp_path):
    baseline = make_bundle(tmp_path)
    context_dir = tmp_path / "context"
    prepare(baseline, context_dir)
    context_path = context_dir / "context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    review_path = tmp_path / "review.json"
    write_json(review_path, {
        "descriptions": {"0": "The captured SQL maps the source value to this field; business meaning is not documented."},
        "partial_transformation_groups": [], "criterion_judgments": {}, "limitations": ["Static evidence only."],
    })
    prior_path = tmp_path / "prior.json"
    assemble_review(context_path, review_path, prior_path)
    context["eligible_fields"][0]["evidence_refs"]["E5"]["value"] += " changed"
    write_json(context_path, context)
    schema_review = {
        "descriptions": {"0": "The changed source binding maps to this field; business meaning is not documented."},
        "criteria": {
            "identity_grounding": {"points": 1, "reason": "Field identity is scoped by supplied evidence.", "evidence_refs": ["E1", "E2", "E3"]},
            "meaning_support": {"points": 1, "reason": "Only technical mapping meaning is described.", "evidence_refs": ["E4", "E5"]},
            "transformation_support": {"points": 2, "reason": "The recorded mapping supports the technical statement.", "evidence_refs": ["E4", "E5"]},
            "corroboration": {"points": 0, "reason": "The mapping is not independently corroborated.", "evidence_refs": []},
            "uncertainty_handling": {"points": 2, "reason": "Business meaning and runtime behavior remain unverified.", "evidence_refs": ["E2", "E4", "E6"]},
        }, "limitations": ["Static evidence only."],
    }
    schema_review_path = tmp_path / "schema-review.json"
    write_json(schema_review_path, schema_review)
    output = tmp_path / "mixed-drafts.json"
    summary = assemble_schema_review(context_path, prior_path, schema_review_path, output)
    assert summary["revalidated"] == 1
    assert summary["newly_authored"] == 1


def test_tmv_report_embeds_exact_validated_dictionary(tmp_path):
    from lineage_poc.viewers.graph.tmv import build, _EmbeddedGraph
    baseline = make_bundle(tmp_path, "Repository description.")
    output = tmp_path / "html"
    result = build(tmp_path / "graphs", output, tmp_path / "columns/column_lineage.json",
                   tmp_path / "columns/column_lineage_gaps.json", baseline)
    parser = _EmbeddedGraph("tmv-data")
    parser.feed((output / "index.html").read_text(encoding="utf-8"))
    payload = json.loads(parser.payload)
    original = read_tables(baseline)
    for name, table in original.items():
        assert payload["dictionary"]["tables"][name] == {
            "headers": table.headers, "rows": table.rows, "sha256": table.sha256,
        }
    assert result["checks"]["dictionary_validation"]["status"] == "passed"
    assert "dictionary" in result["checks"]["views"]
    document = payload["dictionary_document"]
    for marker in ("registry-custom-filters", "registry-page-size", "page-size", "previous-detail",
                   "registry-detail-next", "registry-bundle-files", "filter-reviewReason", "filter-scoreMin",
                   "custom-mode", "add-custom", "data-sort", "TMVViewerAdapter.installBundle"):
        assert marker in document
    assert "@@V1_APP@@" not in document
    embedded = re.search(r'id="embedded-registry-bundle">([^<]+)</script>', document)
    bundle = json.loads(gzip.decompress(base64.b64decode(embedded.group(1))))
    for name, text in bundle["files"].items():
        assert text.encode("utf-8") == (baseline / name).read_bytes()


def test_tmv_reference_viewer_adapter_filters_exports_and_rejects_mismatches(tmp_path):
    baseline = make_bundle(tmp_path, "Repository description.")
    runtime = shutil.which("node")
    if not runtime:
        specification = importlib.util.find_spec("playwright")
        if specification and specification.origin:
            path = Path(specification.origin).parent / "driver/node.exe"
            runtime = str(path) if path.is_file() else None
    if not runtime:
        pytest.skip("Reference-viewer JavaScript tests require Node or installed Playwright Node.")
    assets = Path(__file__).parents[3] / "src/lineage_poc/viewers/dictionary/assets"
    scripts = [(assets / name).read_text(encoding="utf-8") for name in ("v1_core.js", "tmv_adapter.js", "viewer_core.js", "bundle_core.js")]
    files = {name: (baseline / name).read_text(encoding="utf-8-sig") for name in ("asset_registry.csv", "field_catalog.csv", "data_dictionary.csv")}
    program = r"""
const vm=require('vm'),fs=require('fs');const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context={window:{},console};vm.createContext(context);
for(const script of input.scripts)new vm.Script(script).runInContext(context);
context.window.TMVViewerAdapter.installBundle();
const bundle=context.window.V3Bundle.prepareBundle(input.files,{}),core=context.window.DDCore;
if(bundle.dictionary.rows.length!==2)throw Error('Mapping count changed');
for(const name of Object.keys(input.files)){
 const table=name==='asset_registry.csv'?bundle.assets:name==='field_catalog.csv'?bundle.fields:bundle.dictionary;
 const exported=core.parseCSV(core.exportCSV(table.headers,table.rows)),original=core.parseCSV(input.files[name]);
 if(JSON.stringify(exported)!==JSON.stringify(original))throw Error('Export changed original cells: '+name);
}
if(core.filterRows(bundle.dictionary.rows,{operation:'sql_projection'}).length!==2)throw Error('Operation filters failed');
if(core.filterRows(bundle.dictionary.rows,{confidence:'scored'}).length)throw Error('Description scores leaked into relationship scores');
if(core.filterRows(bundle.dictionary.rows,{confidence:'unscored'}).length!==2)throw Error('Unscored relationship filter failed');
if(core.filterRows(bundle.dictionary.rows,{scoreMin:'0'}).length)throw Error('Missing relationship scores must not become zero');
if(core.filterRows(bundle.dictionary.rows,{custom:[{column:'source_column',operator:'equals',value:'INPUT_VALUE'}]}).length!==2)throw Error('Custom condition failed');
if(core.filterRows(bundle.dictionary.rows,{custom:[{column:'source_column',operator:'equals',value:'unknown'}]}).length)throw Error('Custom condition matched an unknown value');
if(core.filterRows(bundle.dictionary.rows,{table:'INTERNAL.missing'}).length)throw Error('Target table filter failed');
const altered=Object.assign({},input.files),parsed=core.parseCSV(altered['data_dictionary.csv']);
parsed.rows[0].target_description='Altered';altered['data_dictionary.csv']=core.exportCSV(parsed.headers,parsed.rows);
let rejected=false;try{context.window.V3Bundle.prepareBundle(altered,{})}catch(error){rejected=true}
if(!rejected)throw Error('Mismatched descriptions were accepted');
for(const row of bundle.dictionary.rows){if(row.raw.hvr_field_id!==undefined)throw Error('Invented HVR identity');}
console.log('Reference filters, exact exports, missing scores, and bundle mismatch rejection passed');
"""
    result = subprocess.run([runtime, "-e", program], input=json.dumps({"scripts": scripts, "files": files}),
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stderr


def test_tmv_reference_dictionary_all_inline_scripts_compile(tmp_path):
    from lineage_poc.viewers.dictionary.build_viewer import build_tmv_document
    baseline = make_bundle(tmp_path)
    document = build_tmv_document(baseline)
    scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', document, re.S)
    specification = importlib.util.find_spec("playwright")
    runtime = shutil.which("node")
    if not runtime and specification and specification.origin:
        candidate = Path(specification.origin).parent / "driver/node.exe"
        runtime = str(candidate) if candidate.is_file() else None
    if not runtime:
        pytest.skip("JavaScript compilation requires Node.")
    executable = [script for script in scripts if "function" in script or "TMVViewerAdapter.installBundle()" in script]
    result = subprocess.run([runtime, "-e", "const vm=require('vm'),fs=require('fs');for(const code of JSON.parse(fs.readFileSync(0,'utf8')))new vm.Script(code);"],
                            input=json.dumps(executable), capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr


def test_tmv_named_focused_report_preserves_main_and_full_dictionary(tmp_path):
    from lineage_poc.cli import main
    from lineage_poc.execution import accepted_data
    from lineage_poc.viewers.graph.tmv import _EmbeddedGraph
    baseline = make_bundle(tmp_path, "Repository description.")
    root = tmp_path / "run"
    args = ["--graphs", str(tmp_path / "graphs"), "--columns", str(tmp_path / "columns/column_lineage.json"),
            "--gaps", str(tmp_path / "columns/column_lineage_gaps.json"), "--dictionary", str(baseline),
            "--output-dir", str(root)]
    assert main(["tmv-html", *args]) == 0
    original = (root / "08-html/index.html").read_bytes()
    assert main(["tmv-html", *args, "--selector", "OUTPUT", "INPUT_VALUE", "output", "--report-name", "accountid"]) == 0
    focused = root / "08-html-accountid"
    record = accepted_data(focused, "08-html-accountid")
    assert record["parameters"]["selectors"] == ["OUTPUT", "INPUT_VALUE"]
    parser = _EmbeddedGraph("tmv-data")
    parser.feed((focused / "index.html").read_text(encoding="utf-8"))
    payload = json.loads(parser.payload)
    assert len(payload["records"]) == 2
    assert payload["focus"]["dictionary_scope"] == "complete"
    assert payload["dictionary"]["tables"]["field_catalog.csv"]["rows"] == read_tables(baseline)["field_catalog.csv"].rows
    assert (root / "08-html/index.html").read_bytes() == original


def test_tmv_focus_requires_every_selector_to_match(tmp_path):
    from lineage_poc.viewers.graph.tmv import build
    baseline = make_bundle(tmp_path)
    with pytest.raises(ValueError, match="Unknown TMV column selector: NO_SUCH_COLUMN"):
        build(tmp_path / "graphs", tmp_path / "focused", tmp_path / "columns/column_lineage.json",
              tmp_path / "columns/column_lineage_gaps.json", baseline,
              selectors=["OUTPUT", "NO_SUCH_COLUMN"])
    assert not (tmp_path / "focused/index.html").exists()


def test_account_domain_profile_from_snapshot_through_dictionary_and_report(tmp_path):
    from lineage_poc.lineage_workflow import parse_sources, build_graphs, build_columns
    from lineage_poc.dictionary.tmv import generate, validate
    from lineage_poc.viewers.graph.tmv import build, _EmbeddedGraph
    sources = tmp_path / "sources"
    for repository, product in (
        ("kb-cdp-tenant-account", "accounts-v1"),
        ("kb-cdp-tenant-enterprise", "int-account-v1"),
        ("kb-cdp-tenant-protect-downstream", "sys_pds_account_v1"),
    ):
        models = sources / repository / "products" / product / "dbt/models"
        models.mkdir(parents=True)
        (models.parent / "dbt_project.yml").write_text("name: " + product.replace("-", "_") + "\nversion: '1'\nmodels:\n  +materialized: view\n", encoding="utf-8")
        (models / "account.sql").write_text("SELECT s.ACCOUNT_ID AS ACCOUNT_ID FROM {{ source('raw', 'ACCOUNT') }} s", encoding="utf-8")
        (models / "sources.yml").write_text("version: 2\nsources:\n  - name: raw\n    schema: RAW\n    tables:\n      - name: ACCOUNT\n      - name: UNUSED_CUSTOMER\n", encoding="utf-8")
    projects = sources / "kb-accounts/src"
    projects.mkdir(parents=True)
    (projects / "Account.csproj").write_text("<Project />", encoding="utf-8")
    snapshot = projects / "AppDbContextModelSnapshot.cs"
    snapshot.write_text('''class Snapshot { void Build() { modelBuilder.Entity("App.Account", b => {
        b.Property<string>("AccountId").HasColumnType("text").HasColumnName("account_id");
        b.ToTable("account", "profile");
    }); }}''', encoding="utf-8")
    parsed, graphs, columns, dictionary = [tmp_path / name for name in ("parsed", "graphs", "columns", "dictionary")]
    parse_sources(sources, parsed, "account-domain")
    build_graphs(parsed, graphs, "account-domain")
    build_columns(parsed, graphs, columns, "TMV")
    generate(columns / "column_lineage.json", parsed, graphs, dictionary)
    assert validate(dictionary)["mappings"] == 4
    rows = read_tables(dictionary)["data_dictionary.csv"].rows
    assert [row["mapping_kind"] for row in rows if row["repository"] == "kb-accounts"] == ["ef_property_binding"]
    relationship_assessments = json.loads((columns / "kb_accounts_field_relationship_assessments.json").read_text())
    assert len(relationship_assessments) == 1
    assert relationship_assessments[0]["status"] == "unresolved"
    assert json.loads((dictionary / "manifest.json").read_text())["run_profile"] == "account-domain"
    from lineage_poc.enrichment.tmv import prepare
    context = tmp_path / "context"
    prepare(dictionary, context)
    assert json.loads((context / "context.json").read_text())["run_profile"] == "account-domain"
    table_graph = json.loads((graphs / "table_lineage.json").read_text())
    assert not any("UNUSED_CUSTOMER" in node["id"] for node in table_graph["nodes"])
    report = tmp_path / "report"
    build(graphs, report, columns / "column_lineage.json", columns / "column_lineage_gaps.json", dictionary)
    parser = _EmbeddedGraph("tmv-data")
    parser.feed((report / "index.html").read_text(encoding="utf-8"))
    assert len(json.loads(parser.payload)["repositories"]) == 4