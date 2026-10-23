#!/usr/bin/env python3
"""Build the accounts-v1 pilot graph from the full requested parser inputs."""

import json
import fnmatch
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
OUTPUT_PATH = PROJECT_ROOT / "output/table_lineage.json"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

INSTRUCTION_LIKE_PATTERNS = (
    ("ignore_prior_instructions", re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions\b", re.IGNORECASE)),
    ("prompt_role", re.compile(r"\b(?:system|developer|assistant)\s+prompt\b", re.IGNORECASE)),
    ("assistant_role_assignment", re.compile(r"\byou are\s+(?:an?\s+)?(?:ai assistant|chatgpt|language model)\b", re.IGNORECASE)),
    ("follow_embedded_instructions", re.compile(r"\b(?:follow|obey)\s+the\s+following\s+instructions\b", re.IGNORECASE)),
    ("do_not_follow_instructions", re.compile(r"\b(?:do not|don't)\s+(?:follow|obey)\s+(?:these|the|any|previous|above)\s+instructions\b", re.IGNORECASE)),
)

from lineage.models import GraphPayload
from lineage.parsers import (
    parse_airflow_dag,
    parse_basic_file,
    parse_dbt_project,
    parse_hvr_config,
    parse_schemachange_file,
)


class GraphAccumulator:
    def __init__(self) -> None:
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def _relative_path(self, value: str) -> str:
        path = Path(value)
        try:
            return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    def _merge_properties(self, target: Dict[str, Any], incoming: Dict[str, Any]) -> None:
        for key, value in incoming.items():
            if key == "source_path":
                source_path = self._relative_path(str(value))
                source_paths = target.setdefault("source_paths", [])
                if source_path not in source_paths:
                    source_paths.append(source_path)
                target.setdefault("source_path", source_path)
                target.setdefault("source_file", source_path)
            elif key not in target or target[key] in (None, "", [], {}):
                target[key] = value
            elif target[key] != value and key in {"role", "operations"}:
                values = target[key] if isinstance(target[key], list) else [target[key]]
                if value not in values:
                    values.append(value)
                target[key] = values

    def add_graph(self, graph: GraphPayload) -> Tuple[int, int]:
        nodes_before = len(self.nodes)
        edges_before = len(self.edges)
        id_map: Dict[str, str] = {}

        for node in graph.nodes:
            source_path = node.properties.get("source_path")
            if source_path and node.label in {"PROGRAM", "EXTRACT_FILE"}:
                relative_source = self._relative_path(str(source_path))
                prefix = "program" if node.label == "PROGRAM" else "extract"
                id_map[node.id] = f"{prefix}:{relative_source}:{node.id}"
            else:
                id_map[node.id] = node.id

        for node in graph.nodes:
            node_id = id_map[node.id]
            properties = dict(node.properties)
            if "source_path" in properties:
                properties["source_path"] = self._relative_path(str(properties["source_path"]))
                properties.setdefault("source_file", properties["source_path"])
            if node_id in self.nodes:
                if self.nodes[node_id]["type"] != node.label:
                    raise ValueError(
                        f"Node ID {node_id!r} has conflicting types "
                        f"{self.nodes[node_id]['type']!r} and {node.label!r}"
                    )
                self._merge_properties(self.nodes[node_id]["properties"], properties)
            else:
                if "source_path" in properties:
                    properties["source_paths"] = [properties["source_path"]]
                self.nodes[node_id] = {
                    "id": node_id,
                    "type": node.label,
                    "properties": properties,
                }

        for edge in graph.edges:
            source_id = id_map.get(edge.source, edge.source)
            target_id = id_map.get(edge.target, edge.target)
            key = (source_id, target_id, edge.type)
            properties = dict(edge.properties)
            if "source_path" in properties:
                properties["source_path"] = self._relative_path(str(properties["source_path"]))
                properties.setdefault("source_file", properties["source_path"])
            if key in self.edges:
                self._merge_properties(self.edges[key]["properties"], properties)
            else:
                if "source_path" in properties:
                    properties["source_paths"] = [properties["source_path"]]
                self.edges[key] = {
                    "source": source_id,
                    "target": target_id,
                    "type": edge.type,
                    "properties": properties,
                }

        return len(self.nodes) - nodes_before, len(self.edges) - edges_before

    def payload(self) -> Dict[str, list[Dict[str, Any]]]:
        node_ids = set(self.nodes)
        dangling = [
            edge
            for edge in self.edges.values()
            if edge["source"] not in node_ids or edge["target"] not in node_ids
        ]
        if dangling:
            raise ValueError(f"Graph contains {len(dangling)} edges with missing endpoints")
        return {
            "nodes": sorted(self.nodes.values(), key=lambda item: item["id"]),
            "edges": sorted(
                self.edges.values(),
                key=lambda item: (item["source"], item["type"], item["target"]),
            ),
        }


def _basic_inputs() -> Iterable[Path]:
    accepted_suffixes = {"", ".b", ".old", ".ext", ".restrict", ".unrestrict"}
    root = WORKSPACE_ROOT / "kb-ultracs-datawarehouse"
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and path.suffix.lower() in accepted_suffixes
    )


def scan_instruction_like_content(paths: Iterable[Path]) -> list[Dict[str, Any]]:
    """Flag common prompt-like strings as data; never evaluate or follow file text."""
    flags = []
    for path in paths:
        try:
            contents = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            source_path = path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
        except ValueError:
            source_path = path.as_posix()
        for line_number, line in enumerate(contents.splitlines(), start=1):
            for flag_name, pattern in INSTRUCTION_LIKE_PATTERNS:
                if pattern.search(line):
                    flags.append({
                        "source_path": source_path,
                        "line": line_number,
                        "flag": flag_name,
                        "handling": "data_only_not_followed",
                    })
    return sorted(flags, key=lambda flag: (flag["source_path"], flag["line"], flag["flag"]))


def _example_extract_name(output_path: str) -> str:
    filename = output_path.replace("\\", "/").rsplit("/", 1)[-1]
    examples = {"HEAD": "01A.TXT", "BHEAD": "MON.TXT", "VAR": "1", "DATE": "20250101"}
    return re.sub(r"\{([A-Z0-9_]+)\}", lambda match: examples.get(match.group(1), match.group(0)), filename, flags=re.IGNORECASE)


def _add_capture_relationships(graph: Dict[str, Any]) -> None:
    channels = [node for node in graph["nodes"] if node["type"] == "HVR_CHANNEL"]
    for extract in graph["nodes"]:
        if extract["type"] != "EXTRACT_FILE":
            continue
        properties = extract.get("properties", {})
        output_path = properties.get("output_path")
        if not output_path:
            continue
        example_name = _example_extract_name(str(output_path))
        for channel in channels:
            channel_properties = channel.get("properties", {})
            patterns = channel_properties.get("capture_patterns") or []
            if not patterns and channel_properties.get("capture_pattern"):
                patterns = [channel_properties["capture_pattern"]]
            for pattern in patterns:
                if not fnmatch.fnmatchcase(example_name.casefold(), str(pattern).casefold()):
                    continue
                channel_source = channel_properties.get("source_path")
                extract_source = properties.get("source_path")
                source_paths = sorted({path for path in (extract_source, channel_source) if path})
                graph["edges"].append({
                    "source": extract["id"],
                    "target": channel["id"],
                    "type": "CARRIED_BY",
                    "properties": {
                        "confidence": "inferred",
                        "match_status": "INFERRED",
                        "capture_pattern": pattern,
                        "matched_filename_example": example_name,
                        "evidence": f"BASIC output path {output_path} matches the HVR Capture.Pattern.",
                        "source_path": extract_source or channel_source,
                        "source_paths": source_paths,
                    },
                })


def _add_stage(
    accumulator: GraphAccumulator,
    stage_name: str,
    graphs: Iterable[GraphPayload],
    input_count: int,
) -> None:
    nodes_added = 0
    edges_added = 0
    for graph in graphs:
        new_nodes, new_edges = accumulator.add_graph(graph)
        nodes_added += new_nodes
        edges_added += new_edges
    print(
        f"{stage_name}: inputs={input_count}, "
        f"nodes_added={nodes_added}, edges_added={edges_added}"
    )


def build_pilot_graph() -> Dict[str, list[Dict[str, Any]]]:
    accumulator = GraphAccumulator()
    input_flags = []

    basic_graphs = []
    basic_inputs = list(_basic_inputs())
    input_flags.extend(scan_instruction_like_content(basic_inputs))
    for path in basic_inputs:
        graph = parse_basic_file(path)
        program = next((node for node in graph.nodes if node.label == "PROGRAM"), None)
        if program and (program.properties.get("operations") or program.properties.get("assignments")):
            basic_graphs.append(graph)
    print(
        f"basic.py input discovery: candidates={len(basic_inputs)}, "
        f"with_parser_evidence={len(basic_graphs)}, "
        f"without_parser_evidence={len(basic_inputs) - len(basic_graphs)}"
    )
    _add_stage(accumulator, "basic.py", basic_graphs, len(basic_graphs))

    all_hvr_json = sorted((WORKSPACE_ROOT / "kb-cdp-hvr").rglob("*.json"))
    hvr_inputs = [
        path
        for path in all_hvr_json
        if "templates" not in {part.lower() for part in path.parts}
    ]
    input_flags.extend(scan_instruction_like_content(hvr_inputs))
    print(f"hvr.py input discovery: excluded_templates={len(all_hvr_json) - len(hvr_inputs)}")
    _add_stage(
        accumulator,
        "hvr.py channel parser",
        (parse_hvr_config(path) for path in hvr_inputs),
        len(hvr_inputs),
    )

    airflow_path = (
        WORKSPACE_ROOT
        / "kb-cdp-tenant-account/products/accounts-v1/airflow/accounts_v1/src/dags/"
        / "accounts_v1_ingestion_v1.py"
    )
    input_flags.extend(scan_instruction_like_content([airflow_path]))
    _add_stage(accumulator, "airflow.py", [parse_airflow_dag(airflow_path)], 1)

    dbt_path = WORKSPACE_ROOT / "kb-cdp-tenant-account/products/accounts-v1/dbt"
    dbt_inputs = sorted(
        path
        for pattern in ("*.sql", "*.yml", "*.yaml")
        for path in (dbt_path / "models").rglob(pattern)
    )
    input_flags.extend(scan_instruction_like_content(dbt_inputs))
    dbt_file_count = len(dbt_inputs)
    _add_stage(accumulator, "dbt.py", [parse_dbt_project(dbt_path)], dbt_file_count)

    migration_root = (
        WORKSPACE_ROOT
        / "kb-cdp-tenant-account/products/accounts-v1/schemachange/scripts"
    )
    migration_inputs = sorted(
        path
        for path in migration_root.iterdir()
        if path.is_file()
        and (path.suffix.lower() == ".sql" or path.name.lower().endswith(". sql"))
    )
    input_flags.extend(scan_instruction_like_content(migration_inputs))
    _add_stage(
        accumulator,
        "schemachange.py",
        (parse_schemachange_file(path) for path in migration_inputs),
        len(migration_inputs),
    )

    graph = accumulator.payload()
    _add_capture_relationships(graph)
    graph["input_flags"] = sorted(
        {
            (flag["source_path"], flag["line"], flag["flag"]): flag
            for flag in input_flags
        }.values(),
        key=lambda flag: (flag["source_path"], flag["line"], flag["flag"]),
    )

    from generate_account_table_lineage import build_account_graph
    from generate_account_enterprise_lineage import _build_extension

    account_graph = build_account_graph(full_graph=graph)
    enterprise_graph = _build_extension(base_graph=account_graph)
    combined = GraphAccumulator()
    for payload in (graph, account_graph, enterprise_graph):
        for node in payload["nodes"]:
            node_id = node["id"]
            if node_id not in combined.nodes:
                combined.nodes[node_id] = {
                    "id": node_id,
                    "type": node["type"],
                    "properties": dict(node.get("properties", {})),
                }
                continue
            existing = combined.nodes[node_id]
            if existing["type"] != node["type"]:
                raise ValueError(f"Conflicting node types for {node_id!r}")
            GraphAccumulator._merge_properties(combined, existing["properties"], node.get("properties", {}))
        for edge in payload["edges"]:
            key = (edge["source"], edge["target"], edge["type"])
            if key not in combined.edges:
                combined.edges[key] = {
                    "source": edge["source"],
                    "target": edge["target"],
                    "type": edge["type"],
                    "properties": dict(edge.get("properties", {})),
                }
            else:
                GraphAccumulator._merge_properties(
                    combined,
                    combined.edges[key]["properties"],
                    edge.get("properties", {}),
                )
    result = combined.payload()
    result["input_flags"] = graph["input_flags"]
    result["gap_register"] = account_graph.get("gap_register", [])
    result["extension_notes"] = enterprise_graph.get("extension_notes", [])
    return result


def main() -> None:
    graph = build_pilot_graph()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")

    node_counts: Dict[str, int] = {}
    edge_counts: Dict[str, int] = {}
    for node in graph["nodes"]:
        node_counts[node["type"]] = node_counts.get(node["type"], 0) + 1
    for edge in graph["edges"]:
        edge_counts[edge["type"]] = edge_counts.get(edge["type"], 0) + 1

    print(f"Generated {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Total nodes={len(graph['nodes'])}, total edges={len(graph['edges'])}")
    print(f"Instruction-like input flags={len(graph['input_flags'])}; file contents treated as data only")
    for flag in graph["input_flags"]:
        print(f"DATA_ONLY_FLAG {flag['source_path']}:{flag['line']} ({flag['flag']})")
    print("Nodes by type:", json.dumps(dict(sorted(node_counts.items())), sort_keys=True))
    print("Edges by type:", json.dumps(dict(sorted(edge_counts.items())), sort_keys=True))


if __name__ == "__main__":
    main()