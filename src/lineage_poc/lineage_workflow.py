"""Independent lineage pipeline stages over recorded, portable evidence.

Each stage writes only beneath its destination. Parsing captures exact relevant
source bytes and hashes; graph and column builders never consult live checkouts.
Rendering consumes the supplied JSON snapshots and never rebuilds column records.
"""

import hashlib
from pathlib import Path
from typing import Any

from .columns import account_outputs, dwacc, dwrel
from .columns.serialization import write_inventory
from .graph.account import build_account_graph, _related_columns
from .graph.enterprise import PRODUCTS, _build_extension
from .graph.pilot import compose_graphs
from .graph.tmv import compose_tmv_graphs
from .parsers import (
    parse_dbt_project,
    parse_kb_accounts,
    parse_landing_repo,
    parse_protect_downstream,
)
from .parsers.full import GraphAccumulator, parse_core_graph
from .parsers.snapshot import (
    ACCOUNT_PRODUCTS,
    ACCOUNT_DOMAIN_PRODUCTS,
    ENTERPRISE_PRODUCTS,
    capture_sources,
    graph_document,
    graph_payload,
    load_snapshot,
    materialize_snapshot,
    normalize_evidence,
    read_json,
    write_json,
)
from .publishing.hvr_metadata import build_metadata
from .viewers.graph import columns as column_view
from .viewers.graph import dwrel as dwrel_view
from .viewers.graph import focused


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _separate_destination(destination: Path, *inputs: Path, allow_parent: bool = False) -> Path:
    destination = Path(destination).resolve()
    for input_path in inputs:
        input_path = Path(input_path).resolve()
        if destination == input_path or destination.is_relative_to(input_path) or (input_path.is_relative_to(destination) and not allow_parent):
            raise ValueError(f"Destination must be separate from the input snapshot: {input_path}")
    return destination


def _record_stage(destination: Path, stage: str, outputs: dict[str, Path], **details: Any) -> dict:
    summary = {
        "stage": stage,
        "destination": str(destination),
        "outputs": {name: str(path) for name, path in outputs.items()},
        **details,
    }
    write_json(destination / "manifest.json", summary)
    return summary


def parse_sources(source_root: Path, destination: Path, parser: str = "all") -> dict:
    """Record parser fragments plus immutable source evidence, without building graphs."""
    source_root = Path(source_root).resolve()
    destination = Path(destination).resolve()
    parser = parser.lower()
    manifest = capture_sources(source_root, destination, parser)
    with materialize_snapshot(manifest, destination, destination) as (_, evidence_root):
        outputs, counts = _parse_snapshot(evidence_root, destination, parser)
    archive_path = destination / manifest["snapshot_archive"]["path"]
    outputs["source_snapshot"] = archive_path
    manifest.update({
        "stage": "parse",
        "source_root": str(source_root),
        "artifacts": [
            {"path": path.relative_to(destination).as_posix(), "sha256": _fingerprint(path)}
            for path in outputs.values() if path != archive_path
        ],
        "counts": {"source_files": len(manifest["files"]), **counts},
    })
    if parser == "tmv-account":
        from .parsers.tmv_account import account_scope
        manifest["account_scope"] = account_scope()
    elif parser == "account-domain":
        from .parsers.tmv_account import domain_scope
        manifest["account_scope"] = domain_scope()
    elif parser == "cdp-account":
        from .parsers.tmv_account import cdp_account_scope
        tenant = read_json(destination / "fragments/cdp_account.json")
        products = tenant["account_scope"]["account_products"]
        manifest["account_scope"] = cdp_account_scope(products)
    write_json(destination / "manifest.json", manifest)
    return {
        "stage": "parse",
        "parser": parser,
        "destination": str(destination),
        "outputs": {name: str(path) for name, path in outputs.items()},
        "manifest": str(destination / "manifest.json"),
        "counts": manifest["counts"],
        "evidence_type": manifest["evidence_type"],
    }


def _parse_snapshot(evidence_root: Path, destination: Path, parser: str) -> tuple[dict, dict]:
    if parser == "cdp-account":
        from .parsers.tmv_account import cdp_account_scope
        outputs, counts = {}, {}
        account_root = evidence_root / "kb-cdp-tenant-account"
        product_names = sorted(path.name for path in (account_root / "products").iterdir() if path.is_dir())
        nodes, edges = parse_protect_downstream(account_root, products=product_names, namespace="account")
        tenant = {"nodes": nodes, "edges": edges, "account_scope": cdp_account_scope(product_names)}
        tenant_path = destination / "fragments/cdp_account.json"
        write_json(tenant_path, tenant)
        outputs["kb_cdp_tenant_account"] = tenant_path
        counts["kb_cdp_tenant_account"] = {"nodes": len(nodes), "edges": len(edges)}
        graph = parse_kb_accounts(evidence_root / "kb-accounts")
        project_path = destination / "fragments/kb_accounts.json"
        write_json(project_path, graph)
        outputs["kb_accounts"] = project_path
        counts["kb_accounts"] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
        from .parsers.dotnet_data import parse_ef_snapshots
        data = parse_ef_snapshots(evidence_root / "kb-accounts")
        data_path = destination / "fragments/kb_accounts_data.json"
        write_json(data_path, data)
        outputs["kb_accounts_data"] = data_path
        counts["kb_accounts_data"] = {"nodes": len(data["nodes"]), "edges": len(data["edges"]),
            "field_bindings": len(data["mappings"]), "event_bindings": len(data["event_mappings"]), "gaps": len(data["unresolved"])}
        return outputs, counts
    if parser == "account-domain":
        from .parsers.tmv_account import PROTECT_ACCOUNT_PRODUCTS, slice_protect_account, domain_scope
        outputs = {}
        counts = {}
        for repository, products, namespace in (
            ("kb-cdp-tenant-account", ACCOUNT_DOMAIN_PRODUCTS, "account"),
            ("kb-cdp-tenant-enterprise", ENTERPRISE_PRODUCTS, "enterprise"),
            ("kb-cdp-tenant-protect-downstream", PROTECT_ACCOUNT_PRODUCTS, "protect"),
        ):
            nodes, edges = parse_protect_downstream(evidence_root / repository, products=products, namespace=namespace)
            graph = slice_protect_account({"nodes": nodes, "edges": edges})
            graph["account_scope"] = domain_scope()
            path = destination / "fragments" / (namespace + ".json")
            write_json(path, graph)
            outputs[namespace] = path
            counts[namespace] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
        path = destination / "fragments/kb_accounts.json"
        graph = parse_kb_accounts(evidence_root / "kb-accounts")
        write_json(path, graph)
        outputs["kb_accounts"] = path
        counts["kb_accounts"] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
        from .parsers.dotnet_data import parse_ef_snapshots
        data = parse_ef_snapshots(evidence_root / "kb-accounts")
        path = destination / "fragments/kb_accounts_data.json"
        write_json(path, data)
        outputs["kb_accounts_data"] = path
        counts["kb_accounts_data"] = {"nodes": len(data["nodes"]), "edges": len(data["edges"]),
                         "field_bindings": len(data["mappings"]), "gaps": len(data["unresolved"])}
        return outputs, counts
    core = parse_core_graph(evidence_root, parser)
    core_path = destination / "fragments" / "table_inputs.json"
    write_json(core_path, normalize_evidence(core, evidence_root))
    projects = {}
    if parser in {"all", "dbt"}:
        for repository, products in (
            ("kb-cdp-tenant-account", ACCOUNT_PRODUCTS),
            ("kb-cdp-tenant-enterprise", ENTERPRISE_PRODUCTS),
        ):
            for product in products:
                path = evidence_root / repository / "products" / product / "dbt"
                if path.is_dir():
                    projects[f"{repository}/{product}"] = graph_document(parse_dbt_project(path), evidence_root)
    project_path = destination / "fragments" / "dbt_projects.json"
    write_json(project_path, projects)
    outputs = {"table_inputs": core_path, "dbt_projects": project_path}
    if parser in {"all", "hvr"}:
        parameters = {}
        for path in sorted((evidence_root / "kb-cdp-hvr" / "hvr-config" / "scripts").glob("*.param")):
            metadata = build_metadata(path, source_root=evidence_root)
            parameters[path.stem] = metadata
            if path.stem.upper() == "DWACC":
                compatibility_name = destination / "hvr_param_metadata.json"
                write_json(compatibility_name, metadata)
                outputs["hvr_param_metadata"] = compatibility_name
        output = destination / "hvr_parameters.json"
        write_json(output, parameters)
        outputs["hvr_parameters"] = output
    landing_root = evidence_root / "kb-cdp-tenant-landing"
    if parser in {"all", "landing", "tmv", "tmv-account"} and landing_root.is_dir():
        if parser == "tmv-account":
            from .parsers.tmv_account import landing_account_graph
            landing_graph = landing_account_graph(landing_root)
        else:
            nodes, edges = parse_landing_repo(landing_root)
            landing_graph = {"nodes": nodes, "edges": edges}
        output = destination / "fragments" / "landing.json"
        write_json(output, landing_graph)
        outputs["landing"] = output
    protect_root = evidence_root / "kb-cdp-tenant-protect-downstream"
    if parser in {"all", "protect_downstream", "tmv", "tmv-account"} and protect_root.is_dir():
        if parser == "tmv-account":
            from .parsers.tmv_account import PROTECT_ACCOUNT_PRODUCTS, slice_protect_account
            nodes, edges = parse_protect_downstream(protect_root, products=PROTECT_ACCOUNT_PRODUCTS)
            scoped = slice_protect_account({"nodes": nodes, "edges": edges})
            nodes, edges = scoped["nodes"], scoped["edges"]
        else:
            nodes, edges = parse_protect_downstream(protect_root)
        output = destination / "fragments" / "protect_downstream.json"
        write_json(output, {"nodes": nodes, "edges": edges})
        outputs["protect_downstream"] = output
    accounts_root = evidence_root / "kb-accounts"
    if parser in {"all", "accounts", "tmv", "tmv-account"} and accounts_root.is_dir():
        output = destination / "fragments" / "kb_accounts.json"
        write_json(output, parse_kb_accounts(accounts_root))
        outputs["kb_accounts"] = output
    return outputs, {"nodes": len(core["nodes"]), "edges": len(core["edges"]), "dbt_projects": len(projects)}


def build_graphs(parsed_dir: Path, destination: Path, scope: str = "all") -> dict:
    """Build graph snapshots exclusively from a recorded parse run."""
    parsed_dir = Path(parsed_dir).resolve()
    destination = _separate_destination(destination, parsed_dir)
    scope = scope.lower()
    aliases = {"dwacc": "account", "table": "full", "pilot": "full"}
    scope = aliases.get(scope, scope)
    if scope not in {
        "all", "full", "account", "enterprise", "dwrel", "landing",
        "protect_downstream", "accounts", "tmv", "account-domain", "cdp-account",
    }:
        raise ValueError(f"Unknown graph scope: {scope!r}")
    with load_snapshot(parsed_dir, workspace=destination) as (parse_manifest, evidence_root):
        outputs, counts = _build_graph_snapshots(parsed_dir, destination, scope, parse_manifest, evidence_root)
    return _record_stage(
        destination, "build-graphs", outputs, scope=scope,
        parse_manifest_sha256=_fingerprint(parsed_dir / "manifest.json"),
        counts=counts,
    )


def _build_graph_snapshots(parsed_dir: Path, destination: Path, scope: str, parse_manifest: dict, evidence_root: Path) -> tuple[dict, dict]:
    if scope == "account-domain":
        from .graph.tmv import compose_account_domain_graphs
        from .parsers.snapshot import ACCOUNT_DOMAIN_REPOSITORIES
        if parse_manifest["parser"] != "account-domain" or set(parse_manifest["repositories"]) != set(ACCOUNT_DOMAIN_REPOSITORIES):
            raise ValueError("Account-domain graphs require the exact four-repository Account snapshot.")
        names = {"kb-cdp-tenant-account": ("account", "account_domain_lineage"),
                 "kb-cdp-tenant-enterprise": ("enterprise", "enterprise_account_lineage"),
                 "kb-cdp-tenant-protect-downstream": ("protect", "protect_downstream_lineage"),
                 "kb-accounts": ("kb_accounts", "kb_accounts_project_lineage")}
        components = {repository: read_json(parsed_dir / "fragments" / (fragment + ".json")) for repository, (fragment, _) in names.items()}
        graphs = {name: components[repository] for repository, (_, name) in names.items()}
        data = read_json(parsed_dir / "fragments/kb_accounts_data.json")
        graphs["kb_accounts_data_lineage"] = {key: value for key, value in data.items() if key not in {"mappings", "schema_inventory", "migration_evidence", "assignment_evidence", "event_mappings", "field_relationship_assessments"}}
        data_components = {key: value for key, value in components.items() if key != "kb-accounts"}
        data_components["kb-accounts:data"] = graphs["kb_accounts_data_lineage"]
        graphs["table_lineage"] = compose_account_domain_graphs(data_components)
        graphs["all_repositories_lineage"] = compose_account_domain_graphs({**data_components, "kb-accounts": components["kb-accounts"]})
        outputs, counts = {}, {}
        for name, graph in graphs.items():
            outputs[name] = destination / (name + ".json")
            write_json(outputs[name], normalize_evidence(graph, evidence_root))
            counts[name] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
        return outputs, counts
    if scope == "cdp-account":
        from .graph.tmv import compose_account_domain_graphs
        from .parsers.snapshot import CDP_ACCOUNT_REPOSITORIES
        if parse_manifest["parser"] != "cdp-account" or set(parse_manifest["repositories"]) != set(CDP_ACCOUNT_REPOSITORIES):
            raise ValueError("CDP Account graphs require exactly kb-accounts and kb-cdp-tenant-account.")
        tenant = read_json(parsed_dir / "fragments/cdp_account.json")
        software = read_json(parsed_dir / "fragments/kb_accounts.json")
        data = read_json(parsed_dir / "fragments/kb_accounts_data.json")
        data_graph = {key: value for key, value in data.items() if key not in {"mappings", "schema_inventory", "migration_evidence", "assignment_evidence", "event_mappings", "field_relationship_assessments"}}
        graphs = {"account_tenant_lineage": tenant, "kb_accounts_project_lineage": software,
                  "kb_accounts_data_lineage": data_graph}
        data_components = {"kb-cdp-tenant-account": tenant, "kb-accounts:data": data_graph}
        graphs["table_lineage"] = compose_account_domain_graphs(data_components)
        graphs["all_repositories_lineage"] = compose_account_domain_graphs({**data_components, "kb-accounts": software})
        outputs, counts = {}, {}
        for name, graph in graphs.items():
            outputs[name] = destination / (name + ".json")
            write_json(outputs[name], normalize_evidence(graph, evidence_root))
            counts[name] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
        return outputs, counts
    full = read_json(parsed_dir / "fragments" / "table_inputs.json")
    graphs = {}
    counts = {}
    can_slice = parse_manifest["parser"] == "all" and any(
        node["type"] == "PROGRAM" and node.get("properties", {}).get("name", "").upper() == "KWDW_ACC"
        for node in full["nodes"]
    )
    if scope in {"account", "enterprise", "dwrel"} and not can_slice:
        raise ValueError(f"The {scope} graph requires an all-parser snapshot containing the relevant source evidence.")
    if can_slice and scope in {"all", "full", "account", "enterprise"}:
        metadata = read_json(parsed_dir / "hvr_param_metadata.json")
        account = build_account_graph(full_graph=full, param_metadata=metadata)
        if scope in {"all", "full", "enterprise"}:
            projects = read_json(parsed_dir / "fragments" / "dbt_projects.json")
            missing = [product for product in PRODUCTS if f"kb-cdp-tenant-enterprise/{product}" not in projects]
            if missing:
                raise ValueError(f"Required Enterprise project fragments are missing: {', '.join(missing)}")
            enterprise_projects = {
                product: graph_payload(projects[f"kb-cdp-tenant-enterprise/{product}"])
                for product in PRODUCTS
            }
            enterprise = _build_extension(base_graph=account, source_root=evidence_root, parsed_graphs=enterprise_projects)
            full = compose_graphs(full, account, enterprise, source_root=evidence_root)
            if scope != "full":
                graphs["account_enterprise_lineage"] = enterprise
        if scope != "full":
            graphs["account_table_lineage"] = account
    if scope in {"all", "full", "account", "enterprise", "dwrel"}:
        graphs["table_lineage"] = full
    if can_slice and scope in {"all", "dwrel"}:
        dag_path = evidence_root / dwrel.DAG_PATH
        dbt_path = evidence_root / dwrel.PRODUCT_PATH / "dbt"
        missing = []
        if not dag_path.is_file():
            missing.append(dag_path.relative_to(evidence_root).as_posix())
        if not dbt_path.is_dir():
            missing.append(dbt_path.relative_to(evidence_root).as_posix())
        if missing and scope == "dwrel":
            raise FileNotFoundError(f"DWREL graph requires missing source inputs: {', '.join(missing)}")
        if missing:
            counts["skipped_graphs"] = {
                "dwrel_table_lineage": {"reason": "required source inputs are missing", "missing_inputs": missing}
            }
        else:
            graphs["dwrel_table_lineage"] = dwrel.build_graph(full_graph=full, source_root=evidence_root)
    supplemental = (
        ("landing", "landing.json", "landing_tenant_lineage"),
        ("protect_downstream", "protect_downstream.json", "protect_downstream_lineage"),
        ("accounts", "kb_accounts.json", "kb_accounts_project_lineage"),
    )
    for selected_scope, fragment_name, graph_name in supplemental:
        if scope not in {"all", "tmv", selected_scope}:
            continue
        fragment = parsed_dir / "fragments" / fragment_name
        if scope == selected_scope and not fragment.is_file():
            raise FileNotFoundError(
                f"The {selected_scope} repository was not captured in this parse snapshot."
            )
        if fragment.is_file():
            graphs[graph_name] = read_json(fragment)
    if scope == "tmv":
        landing = graphs.get("landing_tenant_lineage")
        protect = graphs.get("protect_downstream_lineage")
        accounts = graphs.get("kb_accounts_project_lineage")
        if landing is None or protect is None or accounts is None:
            raise FileNotFoundError("The TMV graph scope requires all three selected repository fragments.")
        graphs["table_lineage"] = compose_tmv_graphs(landing, protect)
        graphs["all_repositories_lineage"] = compose_tmv_graphs(landing, protect, accounts)
    outputs = {}
    for name, graph in graphs.items():
        output = destination / f"{name}.json"
        write_json(output, normalize_evidence(graph, evidence_root))
        outputs[name] = output
        counts[name] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
    return outputs, counts


def _require_graph(graphs_dir: Path, name: str) -> dict:
    path = graphs_dir / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Required graph snapshot is missing: {path}; run build-graphs with the appropriate scope.")
    return read_json(path)


def build_columns(parsed_dir: Path, graphs_dir: Path, destination: Path, feed: str = "DWACC") -> dict:
    """Extract column mappings using the explicit graph and immutable source evidence."""
    parsed_dir, graphs_dir = Path(parsed_dir).resolve(), Path(graphs_dir).resolve()
    destination = _separate_destination(destination, parsed_dir, graphs_dir)
    graph_manifest_path = graphs_dir / "manifest.json"
    if graph_manifest_path.is_file():
        graph_manifest = read_json(graph_manifest_path)
        expected = graph_manifest.get("parse_manifest_sha256")
        if expected and expected != _fingerprint(parsed_dir / "manifest.json"):
            raise ValueError("The graph and parse snapshots belong to different runs.")
    feed = feed.upper()
    available = ("DWACC", "DWREL", *account_outputs.FEEDS)
    if feed != "ALL" and feed not in {*available, "TMV"}:
        raise ValueError(f"Unknown feed {feed!r}; choose from {', '.join(available)}, TMV, or all.")
    feeds = available if feed == "ALL" else (feed,)
    with load_snapshot(parsed_dir, workspace=destination) as (parse_manifest, evidence_root):
        if feed == "TMV" and parse_manifest.get("parser") not in {"tmv", "tmv-account", "account-domain", "cdp-account"}:
            raise ValueError("TMV column lineage requires an accepted account or TMV parse snapshot.")
        inventories, outputs = _build_column_snapshots(
            parsed_dir, graphs_dir, destination, feeds, evidence_root, parse_manifest
        )
    if feed == "ALL":
        summary_path = destination / "account_column_inventory_summary.json"
        write_inventory(summary_path, account_outputs.build_summary(inventories, existing_inventories={}))
        outputs["inventory_summary"] = summary_path
    counts = {
        name: {
            "records": len(records),
            "dbt_targets": sum(len(record.get("dbt_targets", [])) for record in records),
        }
        for name, records in inventories.items()
    }
    if feed == "TMV":
        gaps = read_json(destination / "column_lineage_gaps.json")
        counts["TMV"] = {
            "records": len(inventories["TMV"]),
            "resolved_column_mappings": len(inventories["TMV"]),
            "unresolved_gaps": len(gaps),
        }
    return _record_stage(
        destination, "build-columns", outputs, feed=feed,
        parse_manifest_sha256=_fingerprint(parsed_dir / "manifest.json"),
        counts=counts,
    )


def _build_column_snapshots(
    parsed_dir: Path,
    graphs_dir: Path,
    destination: Path,
    feeds: tuple,
    evidence_root: Path,
    parse_manifest: dict | None = None,
) -> tuple[dict, dict]:
    inventories = {}
    outputs = {}
    for selected in feeds:
        if selected == "DWACC":
            records = dwacc.build_records(
                table_graph=_require_graph(graphs_dir, "table_lineage"),
                param_data=read_json(parsed_dir / "hvr_param_metadata.json"),
                source_root=evidence_root,
            )
            filename = "column_lineage.json"
        elif selected == "DWREL":
            records = dwrel.build_records(
                graph=_require_graph(graphs_dir, "dwrel_table_lineage"),
                full_graph=_require_graph(graphs_dir, "table_lineage"),
                source_root=evidence_root,
            )
            filename = "dwrel_column_lineage.json"
        elif selected == "TMV":
            from .columns.tmv import build_column_inventory

            if parse_manifest and parse_manifest.get("parser") == "cdp-account":
                graphs = {"cdp_account": _require_graph(graphs_dir, "account_tenant_lineage")}
            else:
                graphs = {"protect_downstream": _require_graph(graphs_dir, "protect_downstream_lineage")}
            if parse_manifest and parse_manifest.get("parser") == "cdp-account":
                pass
            elif parse_manifest and parse_manifest.get("parser") == "account-domain":
                graphs["account"] = _require_graph(graphs_dir, "account_domain_lineage")
                graphs["enterprise"] = _require_graph(graphs_dir, "enterprise_account_lineage")
            else:
                graphs["landing"] = _require_graph(graphs_dir, "landing_tenant_lineage")
            if parse_manifest is None:
                raise ValueError("TMV column lineage requires a recorded parse manifest.")
            snapshot_id = "sha256:" + parse_manifest["snapshot_archive"]["sha256"]
            records, gaps = build_column_inventory(graphs, evidence_root, snapshot_id)
            if parse_manifest.get("parser") in {"account-domain", "cdp-account"}:
                data = read_json(parsed_dir / "fragments/kb_accounts_data.json")
                for mapping in data["mappings"] + data["event_mappings"]:
                    records.append({**mapping, "snapshot_id": snapshot_id})
                gaps.extend(data["unresolved"])
                for assessment in data["field_relationship_assessments"]:
                    gaps.append({"repository": "kb-accounts", "source_path": assessment["source_path"],
                        "model_id": assessment["entity_id"], "source_column": assessment["property"],
                        "target_column": assessment["database_column"],
                        "reason": "kb_accounts_field_relationship_unresolved" if assessment["status"] == "unresolved" else "kb_accounts_event_transport_unresolved",
                        "detail": assessment["reason"], "related_mapping_ids": assessment["related_mapping_ids"]})
                for limitation in data["coverage"]["limitations"]:
                    gaps.append({"repository": "kb-accounts", "source_path": "src/", "reason": "dotnet_data_coverage_boundary", "detail": limitation})
                schema_path = destination / "kb_accounts_schema_inventory.json"
                write_json(schema_path, data["schema_inventory"])
                outputs["kb_accounts_schema_inventory"] = schema_path
                for key in ("migration_evidence", "assignment_evidence", "field_relationship_assessments"):
                    path = destination / ("kb_accounts_" + key + ".json")
                    write_json(path, data[key])
                    outputs["kb_accounts_" + key] = path
                if parse_manifest.get("parser") == "cdp-account":
                    from .cross_repository import build_cdp_account_crosswalk
                    crosswalk = build_cdp_account_crosswalk(data, records, evidence_root)
                    cross_path = destination / "cross_repository_field_lineage.json"
                    write_json(cross_path, normalize_evidence(crosswalk, evidence_root))
                    outputs["cross_repository_field_lineage"] = cross_path
                    gaps.extend(crosswalk["unresolved"])
            gap_path = destination / "column_lineage_gaps.json"
            write_json(gap_path, gaps)
            outputs["TMV_gaps"] = gap_path
            filename = "column_lineage.json"
        else:
            records = account_outputs.build_feed_records(selected, source_root=evidence_root)
            filename = f"{selected.rstrip('_').lower()}_column_lineage.json"
        records = normalize_evidence(records, evidence_root)
        output = destination / filename
        write_inventory(output, records)
        outputs[selected] = output
        inventories[selected] = records
    return inventories, outputs


def render_graphs(
    graphs_dir: Path,
    columns_dir: Path,
    destination: Path,
    dictionary_html: Path | None = None,
    selector: str | list[str] | None = None,
) -> dict:
    """Render one combined index from supplied graph, column and dictionary snapshots."""
    graphs_dir, columns_dir = Path(graphs_dir).resolve(), Path(columns_dir).resolve()
    destination = _separate_destination(destination, graphs_dir, columns_dir, allow_parent=True)
    dictionary_bytes = None
    if dictionary_html is not None:
        dictionary_html = Path(dictionary_html).resolve()
        if not dictionary_html.is_file():
            raise FileNotFoundError(f"Dictionary snapshot is missing: {dictionary_html}")
        dictionary_bytes = dictionary_html.read_bytes()
    if not graphs_dir.is_dir() or not columns_dir.is_dir():
        raise FileNotFoundError("Explicit graph and column snapshot directories are required.")
    graphs = {
        name: read_json(graphs_dir / f"{name}.json")
        for name in ("table_lineage", "account_table_lineage", "account_enterprise_lineage", "dwrel_table_lineage", "landing_tenant_lineage")
        if (graphs_dir / f"{name}.json").is_file()
    }
    if not graphs:
        raise FileNotFoundError(f"No graph snapshots found in {graphs_dir}")
    records_path = columns_dir / "column_lineage.json"
    records = read_json(records_path) if records_path.is_file() else []
    selectors = focused.selection_names(selector)
    selection = {
        name: focused.choose_records(records, _related_columns(records), name)
        for name in selectors
    }
    missing = [name for name, chosen in selection.items() if not chosen]
    selected_ids = {record["field_id"] for chosen in selection.values() for record in chosen}
    matches = [record for record in records if record["field_id"] in selected_ids] if selectors else records
    feed = "DWACC"
    graph = graphs.get("account_table_lineage", graphs.get("table_lineage"))
    dwrel_path = columns_dir / "dwrel_column_lineage.json"
    relationship_selection = {}
    if (not matches or missing) and dwrel_path.is_file() and "dwrel_table_lineage" in graphs:
        relationship_records = read_json(dwrel_path)
        relationship_selection = {
            name: dwrel_view.choose_records(relationship_records, name) for name in selectors
        }
        if not selectors or all(relationship_selection.values()):
            selected_ids = {
                record["field_id"] for chosen in relationship_selection.values() for record in chosen
            }
            matches = [record for record in relationship_records if record["field_id"] in selected_ids] if selectors else relationship_records
            feed, graph = "DWREL", graphs["dwrel_table_lineage"]
            missing = []
    if selectors and (missing or not matches):
        unknown = [
            name for name in selectors
            if not selection.get(name) and not relationship_selection.get(name)
        ]
        if unknown:
            raise ValueError(f"No recorded DWACC or DWREL column matches selector(s): {', '.join(unknown)}.")
        raise ValueError("Selected columns span different extract feeds; generate a separate report for each feed.")
    if graph is None:
        raise FileNotFoundError("The combined viewer requires an account, relationship or full graph snapshot.")
    html = column_view.render_html(
        graph, matches, graphs.get("account_enterprise_lineage"),
        dictionary_document=dictionary_bytes.decode("utf-8") if dictionary_bytes is not None else None,
        feed=feed, selector=", ".join(selectors) if selectors else None,
    )
    destination.mkdir(parents=True, exist_ok=True)
    index = destination / "index.html"
    index.write_text(html, encoding="utf-8", newline="\n")
    return _record_stage(
        destination, "render-graphs", {"index": index}, index=str(index), selector=selector,
        selectors=selectors,
        feed=feed, records=len(matches),
        dictionary_embedded=dictionary_bytes is not None,
        dictionary_sha256=hashlib.sha256(dictionary_bytes).hexdigest() if dictionary_bytes is not None else None,
        iframe_id="dictionaryAppFrame",
    )
