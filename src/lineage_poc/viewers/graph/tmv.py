"""Build graph-only HTML pages for the selected TMV repository snapshots."""

from __future__ import annotations

import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from ._templates import read_template
from .descriptions import describe_graph


GRAPHS = {
    "table_lineage": (
        "Combined data-table lineage",
        "Landing and Protect dbt graphs combined by exact graph identity; unresolved repository bridges remain visible.",
        "DBT",
    ),
    "all_repositories_lineage": (
        "All repository relationships",
        "A disconnected union of the data graphs and .NET project dependencies, not a single data-flow route.",
        "ALL",
    ),
    "landing_tenant_lineage": (
        "Tenant Landing",
        "Static dbt, migration, and declared relation evidence from kb-cdp-tenant-landing.",
        "L",
    ),
    "protect_downstream_lineage": (
        "Protect downstream",
        "Static dbt, orchestration, migration, and relation evidence from kb-cdp-tenant-protect-downstream.",
        "P",
    ),
    "kb_accounts_project_lineage": (
        "kb-accounts project dependencies",
        "Static .NET project-reference declarations; not data or column lineage.",
        ".NET",
    ),
}
GRAPH_TEMPLATE = read_template("account_html.html")
SOURCE_TITLE = "<title>ACCOUNT Lineage | Ultracs to CDP</title>"
SOURCE_HEADING = "ACCOUNT lineage"
SOURCE_SUBTITLE = "Ultracs DWACC → HVR → accounts-v1"


def selector_names(selectors):
    values = [] if selectors is None else [selectors] if isinstance(selectors, str) else selectors
    result, seen = [], set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("TMV column selectors must be nonempty strings.")
        name = value.strip()
        if name.casefold() not in seen:
            seen.add(name.casefold())
            result.append(name)
    return result


def select_columns(records, selectors):
    matches, counts = set(), {}
    for selector in selectors:
        selected = []
        for record in records:
            candidates = {str(record.get(key, "")).casefold() for key in ("field_id", "source_column", "target_column")}
            for relation, column in (("source_relation", "source_column"), ("target_relation", "target_column"), ("target_model", "target_column")):
                candidates.add((str(record.get(relation, "")) + "." + str(record.get(column, ""))).casefold())
            if selector.casefold() in candidates:
                selected.append(record["field_id"])
        if not selected:
            raise ValueError(f"Unknown TMV column selector: {selector}")
        counts[selector] = len(selected)
        matches.update(selected)
    return [record for record in records if record["field_id"] in matches], counts


def _focused_graph(graph, records):
    selected = {record[key] for record in records for key in ("source_relation_id", "target_relation_id", "target_model_id")}
    mapping_ids = {record["field_id"] for record in records}
    nodes = {node["id"]: node for node in graph["nodes"]}
    outgoing = {}
    for edge in graph["edges"]:
        outgoing.setdefault(edge["source"], []).append(edge)
    queue = list(sorted(selected))
    for identity in queue:
        if nodes[identity].get("properties", {}).get("is_boundary_node") is True:
            continue
        for edge in outgoing.get(identity, []):
            if edge["type"] == "ASSIGNS_TO_EVENT" and not mapping_ids.intersection(edge.get("properties", {}).get("related_field_mappings", [])):
                continue
            if edge["type"] in {"DEPENDS_ON", "RESOLVES_TO", "MATERIALIZES_AS", "MAPS_TO", "ASSIGNS_TO_EVENT", "WRAPPED_IN_EVENT", "PUBLISHED_VIA"} and edge["target"] not in selected:
                selected.add(edge["target"])
                queue.append(edge["target"])
    return {**graph,
        "nodes": [node for node in graph["nodes"] if node["id"] in selected],
        "edges": [edge for edge in graph["edges"] if edge["source"] in selected and edge["target"] in selected]}


def _validate_graph(graph: dict, name: str) -> None:
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise ValueError(f"Invalid graph payload for {name}: expected nodes and edges arrays.")
    node_ids = [node.get("id") for node in graph["nodes"] if isinstance(node, dict)]
    if len(node_ids) != len(graph["nodes"]) or any(not isinstance(node_id, str) or not node_id for node_id in node_ids):
        raise ValueError(f"Invalid graph payload for {name}: every node needs a string ID.")
    if len(node_ids) != len(set(node_ids)):
        raise ValueError(f"Duplicate node IDs in {name}.")
    known_ids = set(node_ids)
    dangling = [
        edge for edge in graph["edges"]
        if not isinstance(edge, dict)
        or edge.get("source") not in known_ids
        or edge.get("target") not in known_ids
    ]
    if dangling:
        raise ValueError(f"Graph {name} contains {len(dangling)} edges with missing endpoints.")


def render_graph(graph: dict, title: str, subtitle: str, mark: str) -> str:
    _validate_graph(graph, title)
    displayed = describe_graph(graph)
    for edge in displayed["edges"]:
        if edge["type"] == "COLUMN_PROJECTIONS":
            edge["properties"]["html_description_origin"] = "Generated"
    embedded = json.dumps(displayed, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    page = GRAPH_TEMPLATE.replace("__GRAPH_DATA__", embedded)
    page = page.replace(SOURCE_TITLE, f"<title>{html.escape(title)} | Repository lineage</title>")
    page = page.replace(SOURCE_HEADING, html.escape(title))
    page = page.replace(SOURCE_SUBTITLE, html.escape(subtitle))
    page = page.replace('<div class="mark">A</div>', f'<div class="mark">{html.escape(mark)}</div>')
    return page


class _EmbeddedGraph(HTMLParser):
    def __init__(self, identifier: str = "account-data") -> None:
        super().__init__()
        self.identifier = identifier
        self.capture = False
        self.payload = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.capture = tag == "script" and attributes.get("id") == self.identifier

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.capture = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.payload += data


def _column_page(records: list[dict], gaps: list[dict]) -> str:
    payload = json.dumps({"records": records, "gaps": gaps}, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TMV Column Lineage</title><style>
:root{{--ink:#172a31;--muted:#607178;--line:#d5dfdf;--paper:#f2f6f5;--green:#176d52;--amber:#bd7a2a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:13px/1.45 "Segoe UI",sans-serif}}
header{{background:#fff;border-bottom:1px solid var(--line);padding:18px max(16px,calc((100vw - 1300px)/2))}}
h1{{font-size:21px;margin:0}}p{{color:var(--muted);margin:5px 0 0}}main{{max-width:1300px;margin:18px auto;padding:0 16px}}
.bar{{display:flex;gap:12px;align-items:center;margin-bottom:12px}}input{{height:36px;max-width:560px;width:100%;padding:0 10px;border:1px solid var(--line);border-radius:5px;font:inherit}}#count{{color:var(--muted)}}
.table-wrap{{overflow:auto;max-height:72vh;background:#fff;border:1px solid var(--line);border-radius:6px}}table{{border-collapse:collapse;width:100%;min-width:900px}}th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #e8eded;vertical-align:top}}th{{position:sticky;top:0;background:#edf3f2;font-size:11px}}td{{font-size:11px;overflow-wrap:anywhere}}code{{font:10px Consolas,monospace;color:#43565b}}
.gaps{{margin-top:16px;padding:12px 14px;background:#fff9ed;border-left:3px solid var(--amber);border-radius:4px}}.gaps h2{{font-size:14px;margin:0 0 5px}}.gaps p{{font-size:12px}}
@media(max-width:600px){{header{{padding:14px}}main{{margin:12px auto;padding:0 10px}}.bar{{align-items:flex-start;flex-direction:column}}}}
</style></head><body><header><h1>TMV Column Lineage</h1><p>SQLGlot traces from declared or materialized relations to target model columns. Static SQL evidence only; unresolved bindings are listed below.</p></header>
<main><div class="bar"><input id="search" type="search" placeholder="Filter relation, column, model, or repository"><span id="count"></span></div>
<div class="table-wrap"><table><thead><tr><th>Repository / project</th><th>Source relation.column</th><th>Target relation.column</th><th>Target model</th><th>Expression</th><th>Evidence</th></tr></thead><tbody id="rows"></tbody></table></div>
<section class="gaps"><h2>Unresolved lineage gaps: <span id="gap-count"></span></h2><p>These gaps were not converted into mappings. They include unresolved dbt references, unsupported Jinja, ambiguous or unknown relation identities, and projections without a unique materialized target.</p><details><summary>Show gap records</summary><pre id="gap-data"></pre></details></section></main>
<script id="column-data" type="application/json">{payload}</script><script>
const data=JSON.parse(document.getElementById('column-data').textContent),rows=document.getElementById('rows'),search=document.getElementById('search'),count=document.getElementById('count');
function render(){{const q=search.value.trim().toLowerCase();const found=data.records.filter(r=>!q||JSON.stringify(r).toLowerCase().includes(q));rows.replaceChildren();for(const r of found.slice(0,250)){{const tr=document.createElement('tr');for(const value of [r.repository+' / '+r.project,r.source_relation+'.'+r.source_column,r.target_relation+'.'+r.target_column,r.target_model,r.transformation_expression,r.source_path+':'+(r.source_line||'?')]){{const td=document.createElement('td');td.textContent=value||'';tr.append(td)}}rows.append(tr)}}count.textContent=found.length.toLocaleString()+' mappings'+(found.length>250?' · showing first 250':'')}}
search.addEventListener('input',render);document.getElementById('gap-count').textContent=data.gaps.length.toLocaleString();document.getElementById('gap-data').textContent=JSON.stringify(data.gaps,null,2);render();
</script></body></html>"""


def _check_column_page(path: Path, expected_records: list[dict], expected_gaps: list[dict], relation_ids: set[str]) -> dict:
    document = path.read_text(encoding="utf-8")
    start = document.index('<script id="column-data" type="application/json">') + len('<script id="column-data" type="application/json">')
    end = document.index("</script>", start)
    payload = json.loads(document[start:end])
    records, gaps = payload["records"], payload["gaps"]
    if len(records) != len(expected_records) or len(gaps) != len(expected_gaps):
        raise ValueError("TMV column HTML payload counts differ from stage-04 inputs.")
    if any(row["source_relation_id"] not in relation_ids or row["target_relation_id"] not in relation_ids for row in records):
        raise ValueError("TMV column HTML contains a relation endpoint absent from table_lineage.json.")
    if len({row["field_id"] for row in records}) != len(records):
        raise ValueError("TMV column HTML contains duplicate mapping IDs.")
    return {"status": "passed", "mappings": len(records), "gaps": len(gaps), "html_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _check_embedded(path: Path, expected: dict, title: str) -> dict:
    parser = _EmbeddedGraph()
    parser.feed(path.read_text(encoding="utf-8"))
    embedded = json.loads(parser.payload)
    _validate_graph(embedded, title)
    expected_nodes = {node["id"] for node in expected["nodes"]}
    expected_edges = {(edge["source"], edge["type"], edge["target"]) for edge in expected["edges"]}
    embedded_edges = {(edge["source"], edge["type"], edge["target"]) for edge in embedded["edges"]}
    if {node["id"] for node in embedded["nodes"]} != expected_nodes or embedded_edges != expected_edges:
        raise ValueError(f"HTML payload changed graph identities for {title}.")
    return {
        "status": "passed",
        "nodes": len(embedded["nodes"]),
        "edges": len(embedded["edges"]),
        "html_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "embedded_graph_sha256": hashlib.sha256(parser.payload.encode("utf-8")).hexdigest(),
    }


def _index_page(cards: list[dict[str, Any]], column_card: dict[str, Any] | None = None) -> str:
    all_cards = cards + ([column_card] if column_card else [])
    rows = "\n".join(
        "<article><div class=\"mark\">{mark}</div><div><h2>{title}</h2><p>{description}</p>"
        "<small>{summary}</small></div><a href=\"{file}\">Open view</a></article>".format(
            mark=html.escape(item["mark"]),
            title=html.escape(item["title"]),
            description=html.escape(item["description"]),
            summary=html.escape(item.get("summary", f"{item['nodes']:,} nodes · {item['edges']:,} edges")),
            file=html.escape(item["file"], quote=True),
        )
        for item in all_cards
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TMV repository lineage</title><style>
:root{{--ink:#172a31;--muted:#607178;--line:#d5dfdf;--paper:#f2f6f5;--green:#176d52;--amber:#bd7a2a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 "Segoe UI",sans-serif}}
header{{background:#fff;border-bottom:1px solid var(--line);padding:24px max(20px,calc((100vw - 1060px)/2))}}
h1{{font-size:25px;margin:0}}header p{{color:var(--muted);max-width:760px;margin:8px 0 0}}
main{{max-width:1060px;margin:26px auto;padding:0 20px}}.list{{display:grid;gap:12px}}
article{{display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:15px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:7px;padding:17px}}
.mark{{width:36px;height:36px;border-radius:6px;display:grid;place-items:center;background:var(--green);color:white;font-size:12px;font-weight:800}}
h2{{font-size:17px;margin:0}}article p{{color:var(--muted);margin:4px 0}}small{{color:var(--muted)}}a{{color:var(--green);font-weight:700;text-decoration:none}}a:hover{{text-decoration:underline}}
.note{{margin-top:20px;padding:14px 16px;border-left:3px solid var(--amber);background:#fff9ed;color:#554b39;font-size:13px}}
@media(max-width:620px){{header{{padding:20px}}main{{margin:18px auto}}article{{grid-template-columns:36px minmax(0,1fr)}}article a{{grid-column:2}}}}
</style></head><body><header><h1>TMV repository lineage</h1><p>Static graph snapshots for the three selected repositories. The pages preserve each graph separately; they do not imply cross-repository or column-level links without supporting evidence.</p></header>
<main><section class="list">{rows}</section><p class="note">Repository declarations are static evidence, not proof of deployed or runtime behavior. The .NET project-reference view is software dependency lineage, not data lineage.</p></main></body></html>"""


def _schema_graph(graph: dict, records: list[dict]) -> dict:
    nodes = {node["id"]: node for node in graph["nodes"]}
    selected = set()
    groups = {}
    for record in records:
        source, target = record["source_relation_id"], record["target_relation_id"]
        if source not in nodes or target not in nodes:
            raise ValueError("Column mapping endpoint is absent from the combined graph.")
        selected.update((source, target))
        groups.setdefault((source, target), []).append(record)
    edges = [
        {
            "source": source, "target": target, "type": "COLUMN_PROJECTIONS",
            "properties": {
                "description": f"{len(mappings)} recorded SQL column projections; display-only summary, not a stored table edge.",
                "related_columns": mappings,
                "lineage_granularity": "display-only column mapping summary",
            },
        }
        for (source, target), mappings in groups.items()
    ]
    return {"nodes": [nodes[node_id] for node_id in sorted(selected)], "edges": edges}


def _combined_page(documents: dict[str, str]) -> str:
    embedded = json.dumps(documents, ensure_ascii=True).replace("<", "\\u003c")
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TMV Lineage</title><style>
:root{color-scheme:light;--ink:#142f36;--muted:#5e7378;--line:#d7e2df;--green:#16784f}
*{box-sizing:border-box}html,body{height:100%;margin:0}body{display:grid;grid-template-rows:auto minmax(0,1fr);font:13px Aptos,"Segoe UI",sans-serif;color:var(--ink);background:#eef4f1}
header{display:flex;align-items:center;gap:18px;padding:12px 18px;background:white;border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:18px;margin:0}small{display:block;color:var(--muted);font-size:11px;margin-top:4px}nav{display:flex;border:1px solid #b9cbc6;border-radius:6px;overflow:hidden}
button{font:inherit;padding:9px 13px;background:white;border:0;color:var(--ink);cursor:pointer}button+button{border-left:1px solid var(--line)}button[aria-selected=true]{background:#e4f1eb;color:var(--green);font-weight:700}button:focus-visible{outline:2px solid var(--green);outline-offset:-3px}
main{min-height:0}iframe{display:block;width:100%;height:100%;border:0}iframe[hidden]{display:none}
@media(max-width:640px){header{padding:10px;gap:10px}nav{width:100%}button{flex:1;padding:9px 6px;font-size:12px}}
</style></head><body><header><div><h1>TMV lineage</h1><small>Landing / Protect downstream / kb-accounts</small></div>
<nav role="tablist" aria-label="Lineage views">
<button id="detailedView" role="tab" aria-selected="true" aria-controls="detailedPanel" data-view="detailed">Detailed</button>
<button id="schemaView" role="tab" aria-selected="false" aria-controls="schemaPanel" data-view="schema">Schema overview</button>
<button id="columnView" role="tab" aria-selected="false" aria-controls="columnsPanel" data-view="columns">Column lineage</button>
</nav></header><main>
<iframe id="detailedPanel" role="tabpanel" aria-labelledby="detailedView" title="Detailed repository lineage"></iframe>
<iframe id="schemaPanel" role="tabpanel" aria-labelledby="schemaView" title="Schema overview" hidden></iframe>
<iframe id="columnsPanel" role="tabpanel" aria-labelledby="columnView" title="Column lineage" hidden></iframe>
</main><script id="tmv-documents" type="application/json">__DOCUMENTS__</script><script>
const documents=JSON.parse(document.getElementById('tmv-documents').textContent);
function showView(name){for(const button of document.querySelectorAll('[data-view]')){const active=button.dataset.view===name;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;const panel=document.getElementById(button.getAttribute('aria-controls'));panel.hidden=!active;if(active&&!panel.dataset.loaded){panel.srcdoc=documents[name];panel.dataset.loaded='true'}}}
const tabs=[...document.querySelectorAll('[data-view]')];for(const button of tabs){button.addEventListener('click',()=>showView(button.dataset.view));button.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const step=event.key==='ArrowLeft'?-1:1;const index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(tabs.indexOf(button)+step+tabs.length)%tabs.length;tabs[index].focus();showView(tabs[index].dataset.view)})}showView('detailed');
</script></body></html>""".replace("__DOCUMENTS__", embedded)


def build(graphs_dir: Path, destination: Path, columns_path: Path | None = None, gaps_path: Path | None = None,
          dictionary_dir: Path | None = None, baseline_dir: Path | None = None, selectors=None,
          focus_label: str | None = None) -> dict:
    graphs_dir, destination = Path(graphs_dir), Path(destination)
    manifest_path = graphs_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Graph stage manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    domain = manifest.get("scope") == "account-domain"
    cdp_account = manifest.get("scope") == "cdp-account"
    expected_graphs = ({"account_tenant_lineage", "kb_accounts_project_lineage", "kb_accounts_data_lineage",
                        "table_lineage", "all_repositories_lineage"} if cdp_account else {"account_domain_lineage", "enterprise_account_lineage", "protect_downstream_lineage",
                        "kb_accounts_project_lineage", "kb_accounts_data_lineage", "table_lineage", "all_repositories_lineage"} if domain else set(GRAPHS))
    if set(manifest.get("outputs", {})) != expected_graphs:
        raise ValueError("The graph stage must contain the three TMV components and their two composed graphs.")

    graph = json.loads((graphs_dir / "all_repositories_lineage.json").read_text(encoding="utf-8"))
    _validate_graph(graph, "all_repositories_lineage")
    table_graph = json.loads((graphs_dir / "table_lineage.json").read_text(encoding="utf-8"))
    _validate_graph(table_graph, "table_lineage")
    records, gaps = [], []
    if columns_path is not None:
        columns_path = Path(columns_path)
        records = json.loads(columns_path.read_text(encoding="utf-8"))
        gaps_path = Path(gaps_path) if gaps_path else columns_path.with_name("column_lineage_gaps.json")
        gaps = json.loads(gaps_path.read_text(encoding="utf-8")) if gaps_path.is_file() else []
        if not isinstance(records, list) or not isinstance(gaps, list):
            raise ValueError("TMV column lineage and gap inputs must be JSON arrays.")
        table_graph = json.loads((graphs_dir / "table_lineage.json").read_text(encoding="utf-8"))
        relation_ids = {
            node["id"] for node in table_graph.get("nodes", [])
            if node.get("type") in ({"SNOWFLAKE_RELATION", "POSTGRES_RELATION", "DOTNET_ENTITY", "DOTNET_EVENT", "EVENT_PUBLISHER"} if domain or cdp_account else {"SNOWFLAKE_RELATION"})
        }
        if any(row["source_relation_id"] not in relation_ids or row["target_relation_id"] not in relation_ids for row in records):
            raise ValueError("TMV column mapping endpoint is absent from table_lineage.json.")
        if len({row["field_id"] for row in records}) != len(records):
            raise ValueError("Duplicate TMV column mapping IDs.")
    selectors = selector_names(selectors)
    focus = None
    if selectors:
        records, matched = select_columns(records, selectors)
        graph = _focused_graph(graph, records)
        selected_models = {record["target_model_id"] for record in records}
        selected_columns = {record[key].casefold() for record in records for key in ("source_column", "target_column")}
        gaps = [gap for gap in gaps if gap.get("model_id") in selected_models
                and (not gap.get("target_column") or gap["target_column"].casefold() in selected_columns)]
        focus = {"selectors": selectors, "matches_per_selector": matched,
                 "dictionary_scope": "complete", "graph_scope": "selected mappings and dependency context"}
        if focus_label:
            focus.update(selectors=[focus_label], matches_per_selector={focus_label: len(records)},
                 dictionary_scope="selected account mappings")
    displayed = describe_graph(graph)
    displayed_nodes = {node["id"]: node for node in displayed["nodes"]}
    repositories = ["kb-cdp-tenant-landing", "kb-cdp-tenant-protect-downstream", "kb-accounts"]
    components = ["landing_tenant_lineage", "protect_downstream_lineage", "kb_accounts_project_lineage"]
    if domain:
        repositories = ["kb-cdp-tenant-account", "kb-cdp-tenant-enterprise", "kb-cdp-tenant-protect-downstream", "kb-accounts"]
        components = ["account_domain_lineage", "enterprise_account_lineage", "protect_downstream_lineage", "kb_accounts_project_lineage"]
    elif cdp_account:
        repositories = ["kb-cdp-tenant-account", "kb-accounts"]
        components = ["account_tenant_lineage", "kb_accounts_project_lineage"]
    component_pairs = list(zip(repositories, components))
    if domain or cdp_account:
        component_pairs.append(("kb-accounts", "kb_accounts_data_lineage"))
    for repository, component in component_pairs:
        local = json.loads((graphs_dir / f"{component}.json").read_text(encoding="utf-8"))
        for node in local["nodes"]:
            if node["id"] not in displayed_nodes:
                continue
            properties = displayed_nodes[node["id"]].setdefault("properties", {})
            properties["display_repository"] = repository
            path = str(node.get("properties", {}).get("source_path", "")).replace("\\", "/")
            parts = path.split("/")
            product = node.get("properties", {}).get("project")
            if not product and "products" in parts:
                position = parts.index("products") + 1
                product = parts[position] if position < len(parts) else None
            if not product and repository == "kb-accounts" and "src" in parts:
                position = parts.index("src") + 1
                product = parts[position] if position < len(parts) else None
            properties["display_product"] = product or "(repository)"
    payload = {"graph": displayed, "records": records, "gaps": gaps, "repositories": repositories}
    crosswalk_path = Path(columns_path).parent / "cross_repository_field_lineage.json" if columns_path is not None else None
    if crosswalk_path and crosswalk_path.is_file():
        crosswalk = json.loads(crosswalk_path.read_text(encoding="utf-8"))
        if focus:
            selectors_folded = {selector.casefold() for selector in selectors}
            selected_mapping_ids = {record["field_id"] for record in records}
            crosswalk["mappings"] = [item for item in crosswalk.get("mappings", [])
                if item.get("raw_sql_mapping_id") in selected_mapping_ids or any(selector in {str(item.get(key, "")).casefold() for key in
                    ("source_property", "event_property", "raw_column", "mapping_id")}
                    or selector in str(item.get("source_entity", "")).casefold()
                    or selector in str(item.get("event_json_path", "")).casefold()
                    for selector in selectors_folded)]
        payload["cross_repository"] = crosswalk
    elif cdp_account:
        raise FileNotFoundError("CDP Account report requires the generated cross_repository_field_lineage.json artifact.")
    if focus:
        payload["focus"] = focus
    dictionary_checks = None
    if dictionary_dir is not None:
        from lineage_poc.dictionary.tmv import validate as validate_tmv
        from lineage_poc.dictionary.io import read_tables, digest_file

        dictionary_checks = validate_tmv(dictionary_dir, baseline_dir)
        dictionary_manifest = json.loads((dictionary_dir / "manifest.json").read_text(encoding="utf-8"))
        if columns_path is None or dictionary_manifest["input_sha256"] != digest_file(columns_path):
            raise ValueError("TMV dictionary and column inventory do not match.")
        tables = read_tables(dictionary_dir)
        payload["dictionary"] = {
            "contract": "tmv-dictionary-v1",
            "tables": {name: {"headers": table.headers, "rows": table.rows, "sha256": table.sha256} for name, table in tables.items()},
        }
        from lineage_poc.viewers.dictionary.build_viewer import build_tmv_document
        payload["dictionary_document"] = build_tmv_document(dictionary_dir)
        if dictionary_manifest.get("account_scope"):
            payload["account_scope"] = dictionary_manifest["account_scope"]
    embedded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    default_template = read_template("dwacc_html.html")
    style = re.search(r"<style>(.*?)</style>", default_template, re.S).group(1)
    style += re.search(r'<style id="schema-diagram-styles">(.*?)</style>', default_template, re.S).group(1)
    network_options = re.search(
        r"const network=new vis.Network\(container,\{nodes:dataNodes,edges:dataEdges\},(.*?)\);\n",
        default_template,
        re.S,
    ).group(1)
    report_template = read_template("tmv_report.html")
    if domain:
        report_template = report_template.replace("<title>TMV lineage</title>", "<title>Account domain lineage</title>")
        report_template = report_template.replace("<h1>TMV lineage", "<h1>Account domain lineage")
        report_template = report_template.replace('<div class="mark">TMV</div>', '<div class="mark">ACC</div>')
        report_template = report_template.replace("Landing / Protect downstream / kb-accounts", "Account / Enterprise / Protect / kb-accounts")
        report_template = report_template.replace("All three repositories", "All four repositories")
        report_template = report_template.replace("repeat(3,minmax(230px,1fr))", "repeat(4,minmax(230px,1fr))")
        report_template = report_template.replace("Software project dependencies only; no dataset or column bridge.", "EF schema/property bindings and separate software dependencies; no proven cross-repository bridge.")
        report_template = report_template.replace("node.type==='DOTNET_PROJECT'", "['DOTNET_PROJECT','DOTNET_ENTITY','POSTGRES_RELATION','DOTNET_EVENT','EVENT_PUBLISHER'].includes(node.type)")
        report_template = report_template.replace("Target SQL model", "Target model / entity").replace("label:'SQL model'", "label:'Model / entity'")
        report_template = report_template.replace("SQL-projection evidence within this repository", "Mapping declarations within this repository")
        report_template = report_template.replace("Selected SQL column path", "Selected column mapping path")
        report_template = report_template.replace("Recorded SQL input", "Recorded mapping input").replace("Recorded SQL output", "Recorded mapping output")
        report_template = report_template.replace("Recorded SQL value dependencies;", "Recorded SQL dependencies and EF property bindings;")
        report_template = report_template.replace("SNOWFLAKE_RELATION:'#397b9d'", "SNOWFLAKE_RELATION:'#397b9d',POSTGRES_RELATION:'#397b9d',DOTNET_ENTITY:'#218b83',DOTNET_EVENT:'#218b83',EVENT_PUBLISHER:'#738286'")
    if cdp_account:
        report_template = report_template.replace("<title>TMV lineage</title>", "<title>CDP Account lineage</title>")
        report_template = report_template.replace("<h1>TMV lineage", "<h1>CDP Account lineage")
        report_template = report_template.replace('<div class="mark">TMV</div>', '<div class="mark">CDP</div>')
        report_template = report_template.replace("Landing / Protect downstream / kb-accounts", "kb-cdp-tenant-account / kb-accounts")
        report_template = report_template.replace("All three repositories", "Both repositories")
        report_template = report_template.replace("repeat(3,minmax(230px,1fr))", "repeat(2,minmax(230px,1fr))")
        report_template = report_template.replace("Software project dependencies only; no dataset or column bridge.", "EF schema, C# event field mappings, and software dependencies; cross-repository transport is separately qualified.")
        report_template = report_template.replace("node.type==='DOTNET_PROJECT'", "['DOTNET_PROJECT','DOTNET_ENTITY','POSTGRES_RELATION','DOTNET_EVENT','EVENT_PUBLISHER'].includes(node.type)")
        report_template = report_template.replace("Target SQL model", "Target model / event / entity").replace("label:'SQL model'", "label:'Model / event / entity'")
        report_template = report_template.replace("SQL-projection evidence within this repository", "Repository mapping evidence within this repository")
        report_template = report_template.replace("Selected SQL column path", "Selected column mapping path")
        report_template = report_template.replace("Recorded SQL value dependencies;", "Recorded SQL and C# event mappings;")
        report_template = report_template.replace("SNOWFLAKE_RELATION:'#397b9d'", "SNOWFLAKE_RELATION:'#397b9d',POSTGRES_RELATION:'#397b9d',DOTNET_ENTITY:'#218b83',DOTNET_EVENT:'#218b83',EVENT_PUBLISHER:'#738286'")
        report_template = report_template.replace("<span id=\"stats\"", "<span id=\"stats\"")
    if payload.get("account_scope"):
        report_template = report_template.replace("<title>TMV lineage</title>", "<title>Account lineage | TMV</title>")
        report_template = report_template.replace("<h1>TMV lineage", "<h1>Account lineage")
    if focus:
        title = html.escape(focus_label or " / ".join(selectors))
        heading = "CDP Account lineage" if cdp_account else "TMV column lineage"
        report_template = re.sub(r"<title>.*?</title>", lambda _: f"<title>{heading} | {title}</title>", report_template, count=1)
    page = (report_template
            .replace("__REPORT_STYLE__", style)
            .replace("__NETWORK_OPTIONS__", network_options)
            .replace("__TMV_PAYLOAD__", embedded))
    destination.mkdir(parents=True, exist_ok=True)
    index_path = destination / "index.html"
    index_path.write_text(page, encoding="utf-8")
    saved = _EmbeddedGraph("tmv-data")
    saved.feed(index_path.read_text(encoding="utf-8"))
    if json.loads(saved.payload) != payload:
        raise ValueError("Saved TMV report payload differs from the selected inputs.")
    checks = {
        "status": "passed", "views": ["detailed", "schema", "columns"] + (["dictionary"] if dictionary_dir else []),
        "nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
        "schema_relations": len({record["source_relation_id"] for record in records} | {record["target_relation_id"] for record in records}),
        "mappings": len(records), "gaps": len(gaps),
        "embedded_documents_verified": True,
        "html_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "scope": "static payload checks; browser interactions not verified",
    }
    if focus:
        checks["selection"] = focus
    if dictionary_checks is not None:
        checks["dictionary_validation"] = dictionary_checks
        checks["embedded_csv_sha256"] = {name: table["sha256"] for name, table in payload["dictionary"]["tables"].items()}
    return {"index": str(index_path), "outputs": {"index": str(index_path)}, "checks": checks}