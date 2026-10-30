"""Build the accounts-v1 pilot graph from the full requested parser inputs."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, OUTPUT_ROOT, source_root as default_source_root

import fnmatch
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


PROJECT_ROOT = REPOSITORY_ROOT
WORKSPACE_ROOT = default_source_root()
OUTPUT_PATH = OUTPUT_ROOT / "lineage" / "table_lineage.json"

INSTRUCTION_LIKE_PATTERNS = (
    ("ignore_prior_instructions", re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions\b", re.IGNORECASE)),
    ("prompt_role", re.compile(r"\b(?:system|developer|assistant)\s+prompt\b", re.IGNORECASE)),
    ("assistant_role_assignment", re.compile(r"\byou are\s+(?:an?\s+)?(?:ai assistant|chatgpt|language model)\b", re.IGNORECASE)),
    ("follow_embedded_instructions", re.compile(r"\b(?:follow|obey)\s+the\s+following\s+instructions\b", re.IGNORECASE)),
    ("do_not_follow_instructions", re.compile(r"\b(?:do not|don't)\s+(?:follow|obey)\s+(?:these|the|any|previous|above)\s+instructions\b", re.IGNORECASE)),
)

from lineage_poc.graph.models import GraphPayload
from lineage_poc.parsers import parse_airflow_dag, parse_basic_file, parse_dbt_project, parse_hvr_config, parse_schemachange_file


class GraphAccumulator:
    def __init__(self, source_root: Path | None = None) -> None:
        self.source_root = Path(source_root).resolve() if source_root is not None else default_source_root()
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def _relative_path(self, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            return path.as_posix()
        try:
            return path.resolve().relative_to(self.source_root).as_posix()
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


def _basic_inputs(source_root: Path | None = None) -> Iterable[Path]:
    workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    accepted_suffixes = {"", ".b", ".old", ".ext", ".restrict", ".unrestrict"}
    root = workspace_root / "kb-ultracs-datawarehouse"
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and path.suffix.lower() in accepted_suffixes
    )


def scan_instruction_like_content(paths: Iterable[Path], source_root: Path | None = None) -> list[Dict[str, Any]]:
    """Flag common prompt-like strings as data; never evaluate or follow file text."""
    workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    flags = []
    for path in paths:
        try:
            contents = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            source_path = path.resolve().relative_to(workspace_root).as_posix()
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


def parse_core_graph(source_root: Path | None = None, parser: str = "all") -> dict:
    """Parse the source-ingest pilot inputs without invoking graph or column builders."""
    evidence_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    accumulator = GraphAccumulator(source_root=evidence_root)
    scanned = []
    if parser in {"all", "basic"}:
        paths = list(_basic_inputs(source_root=evidence_root))
        scanned.extend(paths)
        for path in paths:
            graph = parse_basic_file(path)
            program = next((node for node in graph.nodes if node.label == "PROGRAM"), None)
            if program and (program.properties.get("operations") or program.properties.get("assignments")):
                accumulator.add_graph(graph)
    if parser in {"all", "hvr"}:
        paths = sorted(
            path for path in (evidence_root / "kb-cdp-hvr").rglob("*.json")
            if "templates" not in {part.lower() for part in path.parts}
        )
        scanned.extend(paths)
        for path in paths:
            accumulator.add_graph(parse_hvr_config(path))
    account = evidence_root / "kb-cdp-tenant-account" / "products" / "accounts-v1"
    if parser in {"all", "airflow"}:
        path = account / "airflow" / "accounts_v1" / "src" / "dags" / "accounts_v1_ingestion_v1.py"
        if path.is_file():
            scanned.append(path)
            accumulator.add_graph(parse_airflow_dag(path))
    if parser in {"all", "dbt"} and (account / "dbt").is_dir():
        accumulator.add_graph(parse_dbt_project(account / "dbt"))
        scanned.extend(
            path for pattern in ("*.sql", "*.yml", "*.yaml")
            for path in (account / "dbt" / "models").rglob(pattern)
        )
    if parser in {"all", "schemachange"}:
        paths = sorted(
            path for path in (account / "schemachange" / "scripts").glob("*")
            if path.is_file() and (path.suffix.lower() == ".sql" or path.name.lower().endswith(". sql"))
        )
        scanned.extend(paths)
        for path in paths:
            accumulator.add_graph(parse_schemachange_file(path))
    graph = accumulator.payload()
    _add_capture_relationships(graph)
    graph["input_flags"] = scan_instruction_like_content(scanned, source_root=evidence_root)
    return graph
