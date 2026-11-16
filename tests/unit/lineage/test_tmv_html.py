import json
import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lineage_poc.viewers.graph.tmv import GRAPHS, build


def make_graphs(directory):
    graphs = directory / "graphs"
    graphs.mkdir()
    manifest_outputs = {}
    relations = None
    for index, name in enumerate(GRAPHS):
        source = f"node:{index}:source"
        target = f"node:{index}:target"
        relation_type = "SNOWFLAKE_RELATION" if name == "table_lineage" else "DBT_MODEL"
        graph = {
            "nodes": [
                {"id": source, "type": relation_type, "properties": {"name": f"model_{index}"}},
                {"id": target, "type": "SNOWFLAKE_RELATION", "properties": {"name": f"relation_{index}"}},
            ],
            "edges": [{"source": source, "target": target, "type": "MATERIALIZES_AS", "properties": {"confidence": "explicit"}}],
        }
        (graphs / f"{name}.json").write_text(json.dumps(graph), encoding="utf-8")
        manifest_outputs[name] = str(graphs / f"{name}.json")
        if name == "table_lineage":
            relations = (source, target)
    (graphs / "manifest.json").write_text(json.dumps({"scope": "tmv", "outputs": manifest_outputs}), encoding="utf-8")
    return graphs, relations


def test_tmv_html_builds_graph_pages_and_checks_embedded_payloads(tmp_path):
    graphs, _ = make_graphs(tmp_path)

    result = build(graphs, tmp_path / "html")

    assert Path(result["index"]).is_file()
    assert set(result["outputs"]) == {"index"}
    assert result["checks"]["status"] == "passed"
    assert result["checks"]["views"] == ["detailed", "schema", "columns"]
    assert [page.name for page in (tmp_path / "html").glob("*.html")] == ["index.html"]


def test_tmv_html_validates_and_embeds_column_mappings(tmp_path):
    graphs, relation_ids = make_graphs(tmp_path)
    columns = tmp_path / "column_lineage.json"
    gaps = tmp_path / "column_lineage_gaps.json"
    columns.write_text(json.dumps([{
        "field_id": "tmv-column:test",
        "source_relation_id": relation_ids[0],
        "source_relation": "RAW.ACCOUNT",
        "source_column": "ACCOUNT_NO",
        "target_relation_id": relation_ids[1],
        "target_relation": "INTERNAL.ACCOUNT",
        "target_column": "ACCOUNT_NUMBER",
        "repository": "kb-cdp-tenant-landing",
        "transformation_expression": "ACCOUNT_NO AS ACCOUNT_NUMBER",
        "source_path": "model.sql",
    }]), encoding="utf-8")
    gaps.write_text(json.dumps([{"reason": "unresolved bridge"}]), encoding="utf-8")
    (tmp_path / "cross_repository_field_lineage.json").write_text(json.dumps({
        "scope": "fixture", "mappings": [{
            "mapping_id": "cross-repo:fixture", "raw_sql_mapping_id": "tmv-column:test",
            "source_database_relation": "profile.account_profile", "source_database_column": "account_id",
            "source_entity": "AccountProfile", "source_property": "AccountId",
            "event_contract": "AccountProfile.Account", "event_property": "AccountId",
            "consumer_product": "account-profile-topic-v1", "raw_relation": "INTERNAL.PROFILE",
            "raw_column": "ACCOUNTID", "downstream_targets": [
                {"relation_id": "snowflake:relation:PUBLIC.VW_PROFILE", "column": "ACCOUNTID"},
            ], "transport_status": "unverified",
        }], "table_mappings": [], "unresolved": [], "candidate_routes": [],
        "counts": {"table_mappings": 0},
    }), encoding="utf-8")

    result = build(graphs, tmp_path / "html", columns, gaps)

    assert result["checks"]["mappings"] == 1
    assert result["checks"]["gaps"] == 1
    page = (tmp_path / "html" / "index.html").read_text(encoding="utf-8")
    embedded = page.split('<script id="tmv-data" type="application/json">', 1)[1].split('</script>', 1)[0]
    payload = json.loads(embedded)
    assert payload["records"][0]["source_column"] == "ACCOUNT_NO"
    assert payload["records"][0]["target_column"] == "ACCOUNT_NUMBER"
    assert payload["gaps"] == [{"reason": "unresolved bridge"}]
    assert payload["cross_repository"]["mappings"][0]["downstream_targets"][0]["relation_id"] == "snowflake:relation:PUBLIC.VW_PROFILE"
    assert "target.relation||target.relation_id" in page
    assert '<iframe' not in page
    assert 'vis.Network' in page
    assert 'node.type===\'DOTNET_PROJECT\'' in page
    assert 'slice(pageIndex*pageSize' in page
    assert 'id="schemaView"' in page
    assert 'id="columnView"' in page


def test_tmv_html_focus_label_summarizes_exact_selected_mapping_ids(tmp_path):
    graphs, relation_ids = make_graphs(tmp_path)
    all_graph_path = graphs / "all_repositories_lineage.json"
    all_graph = json.loads(all_graph_path.read_text(encoding="utf-8"))
    all_graph["nodes"].extend({"id": identity, "type": "SNOWFLAKE_RELATION", "properties": {"name": identity}}
                              for identity in relation_ids if identity not in {node["id"] for node in all_graph["nodes"]})
    all_graph_path.write_text(json.dumps(all_graph), encoding="utf-8")
    columns = tmp_path / "column_lineage.json"
    columns.write_text(json.dumps([{
        "field_id": "tmv-column:account-field",
        "source_relation_id": relation_ids[0], "source_relation": "RAW.ACCOUNT",
        "source_column": "ACCOUNT_ID", "target_relation_id": relation_ids[1],
        "target_relation": "INTERNAL.ACCOUNT", "target_column": "ACCOUNT_ID", "target_model_id": relation_ids[0],
        "repository": "kb-cdp-tenant-account", "transformation_expression": "ACCOUNT_ID",
        "source_path": "account.sql",
    }]), encoding="utf-8")

    result = build(graphs, tmp_path / "html", columns, selectors=["tmv-column:account-field"], focus_label="Account")

    page = Path(result["index"]).read_text(encoding="utf-8")
    payload = json.loads(page.split('<script id="tmv-data" type="application/json">', 1)[1].split('</script>', 1)[0])
    assert payload["focus"]["selectors"] == ["Account"]
    assert payload["focus"]["matches_per_selector"] == {"Account": 1}
    assert payload["focus"]["dictionary_scope"] == "selected account mappings"
    assert "<title>TMV column lineage | Account</title>" in page


def test_tmv_html_rejects_graphs_outside_the_selected_scope(tmp_path):
    graphs = tmp_path / "graphs"
    graphs.mkdir()
    (graphs / "manifest.json").write_text(
        json.dumps({"outputs": {**{name: f"{name}.json" for name in GRAPHS}, "extra": "extra.json"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="three TMV components and their two composed graphs"):
        build(graphs, tmp_path / "html")


def test_tmv_report_javascript_and_default_scope_execute(tmp_path):
    runtime = shutil.which("node")
    if not runtime:
        specification = importlib.util.find_spec("playwright")
        if specification and specification.origin:
            bundled = Path(specification.origin).parent / "driver" / "node.exe"
            runtime = str(bundled) if bundled.is_file() else None
    if not runtime:
        pytest.skip("JavaScript validation requires Node or the installed Playwright Node runtime.")
    graphs, _ = make_graphs(tmp_path)
    result = build(graphs, tmp_path / "html")
    page = Path(result["index"]).read_text(encoding="utf-8")
    scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', page, re.S)
    payload = json.loads(scripts[0])
    for index in range(160):
        payload["graph"]["nodes"].append({
            "id": f"large-node:{index}", "type": "DBT_MODEL",
            "properties": {"name": f"model_{index}", "display_repository": "kb-cdp-tenant-landing"},
        })
        if index:
            payload["graph"]["edges"].append({
                "source": f"large-node:{index - 1}", "target": f"large-node:{index}",
                "type": "DEPENDS_ON", "properties": {"confidence": "explicit"},
            })
    payload["records"] = [{
        "field_id": "tmv:test-flow", "repository": "kb-cdp-tenant-landing",
        "project": "ultracs-v1", "source_relation_id": "node:1:source",
        "source_relation": "RAW.ACCOUNT", "source_column": "PAYLOAD",
        "target_model_id": "node:1:source", "target_model": "accounts_raw",
        "target_relation_id": "node:1:target", "target_relation": "INTERNAL.ACCOUNT",
        "target_column": "KIWIACC", "source_path": "model.sql",
        "transformation_expression": "PAYLOAD AS KIWIACC", "confidence": "explicit",
    }]
    payload["dictionary"] = {"tables": {
        "field_catalog.csv": {"headers": ["field_id", "description"], "rows": [
            {"field_id": "draft", "field_name": "KIWIACC", "relation_id": "relation:target", "repository": "kb-cdp-tenant-landing", "description": "Technical draft.", "description_source_type": "ai_generated", "description_confidence_json": "null"},
            {"field_id": "existing", "field_name": "PAYLOAD", "relation_id": "relation:source", "repository": "kb-cdp-tenant-landing", "description": "Existing text.", "description_source_type": "existing_metadata"},
        ]},
        "data_dictionary.csv": {"headers": ["source_field_id", "target_field_id"], "rows": [
            {"source_field_id": "existing", "target_field_id": "draft", "source_description": "Existing text.", "target_description": "Technical draft.", "repository": "kb-cdp-tenant-landing"},
        ]},
        "asset_registry.csv": {"headers": ["asset_id"], "rows": [{"asset_id": "asset", "repository": "kb-cdp-tenant-landing"}]},
    }}
    program = r"""
const vm=require('vm'), fs=require('fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element {
    constructor(){this.children=[];this.dataset={};this.value='';this.textContent='';this.hidden=false;this.checked=false;this.attributes={};this.classList={toggle(){}};}
  append(...items){this.children.push(...items)}
  replaceChildren(...items){this.children=items}
  add(item){this.children.push(item)}
  addEventListener(){}
  setAttribute(key,value){this.attributes[key]=value}
  click(){}
}
const ids=new Map();
const get=id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)};
get('tmv-data').textContent=JSON.stringify(input.payload);
const tabs=['detailed','schema','columns'].map(name=>{const el=new Element();el.dataset.view=name;return el});
const context={console,Option:function(label,value){this.label=label;this.value=value},
    document:{body:new Element(),getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>tabs},
  window:{},setTimeout,clearTimeout,Blob,URL};
vm.createContext(context);
new vm.Script(input.code).runInContext(context);
if(get('graphPanel').hidden)throw Error('Detailed graph must be the initial view, like the default report');
let captured;
const vis={Network:function(container,data,options){captured={data,options};this.destroy=()=>{};this.on=()=>{};this.fit=()=>{}}};
context.vis=vis;context.window.vis=vis;
vm.runInContext("showView('detailed')",context);
if(captured.options.physics.solver!=='forceAtlas2Based'||!captured.options.physics.enabled)throw Error('Must use the default report force-directed configuration');
if(!captured.data.nodes.length||captured.data.nodes.some(node=>node.shape!=='dot'))throw Error('Default report circular graph nodes are required');
if(captured.data.nodes.some(node=>'x' in node||'y' in node))throw Error('Fixed grid positions must not override default physics');
if(captured.data.nodes.length!==input.payload.graph.nodes.length)throw Error('The initial graph must include every node, not a capped neighborhood');
if(captured.data.edges.filter(edge=>edge.stored).length!==input.payload.graph.edges.length)throw Error('The initial graph must include every recorded relationship');
vm.runInContext("repoSelect.value='kb-cdp-tenant-landing';showView('detailed')",context);
if(captured.data.nodes.length!==160)throw Error('Repository scope must retain all matching nodes without a 120-node cap');
vm.runInContext("repoSelect.value='';showView('detailed')",context);
vm.runInContext("showView('schema')",context);
if(get('schemaPanel').hidden)throw Error('Schema overview must open');
if(get('schemaDiagram').hidden)throw Error('The default report-style flow diagram must be the initial schema presentation');
if(get('schemaFanout').children.length!==9)throw Error('Expected five stages and four arrows');
if(!get('flowContext').textContent.includes('not a cross-repository route'))throw Error('Flow evidence scope must be explicit');
vm.runInContext("openMapping(records[0])",context);
if(!get('details').children.length)throw Error('Mapping inspector is empty');
vm.runInContext("repoSelect.value='kb-accounts';renderFlow()",context);
if(get('schemaFanout').children.length)throw Error('A project dependency repository must not have a fabricated column flow');
vm.runInContext("repoSelect.value='';renderFlow()",context);
vm.runInContext("schemaPresentation='objects';renderSchemaPresentation()",context);
if(get('repositories').children.length!==3)throw Error('Expected three distinct repository groups');
vm.runInContext("showView('columns')",context);
if(get('columnsPanel').hidden||!get('schemaPanel').hidden)throw Error('Column switch failed');
vm.runInContext("showView('dictionary')",context);
if(get('dictionaryPanel').hidden||get('dictionaryRows').children.length!==1)throw Error('Embedded Dictionary view failed');
if(get('dictionaryHeaders').children[0].children.length!==7)throw Error('Dictionary must match the reference seven-column format');
vm.runInContext("byId('dictionaryRelation').value='relation:source';renderDictionary()",context);
if(get('dictionaryRows').children.length!==1)throw Error('Source relation filter must use canonical field binding');
vm.runInContext("byId('dictionaryRelation').value='relation:target';renderDictionary()",context);
if(get('dictionaryRows').children.length!==1)throw Error('Target relation filter must use canonical field binding');
vm.runInContext("byId('dictionaryRelation').value='relation:unknown';renderDictionary()",context);
if(get('dictionaryRows').children.length)throw Error('Unknown relation must have no rows');
vm.runInContext("byId('dictionaryRelation').value='';renderDictionary()",context);
vm.runInContext("byId('dictionarySection').value='field_catalog.csv';byId('descriptionOrigin').value='ai_generated';renderDictionary()",context);
if(get('dictionaryRows').children.length!==1)throw Error('AI description origin filter failed');
vm.runInContext("inspectDictionary(dictionaryFiltered[0])",context);
if(!get('dictionaryDetailBody').children.length)throw Error('Description modal details are empty');
delete context.window.vis;
vm.runInContext("showView('detailed')",context);
if(get('graphPanel').hidden||get('graphError').hidden)throw Error('Missing graph-library fallback failed');
console.log('Schema boot, view switching, and unavailable-library fallback passed');
"""
    completed = subprocess.run(
        [runtime, "-e", program],
        input=json.dumps({"payload": payload, "code": scripts[-1]}),
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert completed.returncode == 0, completed.stderr