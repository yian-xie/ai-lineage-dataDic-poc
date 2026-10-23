"""Parsers for HVR exported channel definitions and column parameter files."""

import json
import re
from pathlib import Path
from typing import Any, Dict

from ..models import GraphPayload
from .common import add_edge, add_node


def parse_hvr_config(path: str | Path) -> GraphPayload:
    """Extract channel locations and configured actions from an HVR JSON export."""
    config_path = Path(path)
    document = json.loads(config_path.read_text(encoding="utf-8-sig"))
    graph = GraphPayload(nodes=[], edges=[])

    for change in document.get("changes", []):
        channel_data = change.get("add_channel") or change.get("channel")
        if not isinstance(channel_data, dict):
            continue
        channel_name = channel_data.get("channel")
        if not channel_name:
            continue

        channel_id = f"hvr:channel:{channel_name}"
        capture_patterns = [
            action.get("params", {}).get("Pattern")
            for action in channel_data.get("actions", [])
            if action.get("type") == "Capture"
            and isinstance(action.get("params", {}).get("Pattern"), str)
            and action.get("params", {}).get("Pattern")
        ]
        capture_properties = {"capture_patterns": capture_patterns} if capture_patterns else {}
        if len(capture_patterns) == 1:
            capture_properties["capture_pattern"] = capture_patterns[0]
        add_node(
            graph,
            channel_id,
            "HVR_CHANNEL",
            config_path,
            name=channel_name,
            description=channel_data.get("description", ""),
            hvr_version=document.get("export_header", {}).get("hvr_version"),
            **capture_properties,
        )

        for role, location_group in channel_data.get("loc_groups", {}).items():
            for location in location_group.get("members", []):
                location_id = f"hvr:location:{location}"
                add_node(
                    graph,
                    location_id,
                    "HVR_LOCATION",
                    config_path,
                    name=location,
                    role=role.upper(),
                )
                relation = "CAPTURES_FROM" if role.upper() == "SOURCE" else "INTEGRATES_TO"
                add_edge(graph, channel_id, location_id, relation, config_path, role=role.upper())

        target_locations = [
            location
            for role, location_group in channel_data.get("loc_groups", {}).items()
            if role.upper() == "TARGET"
            for location in location_group.get("members", [])
        ]
        if any(location.lower().startswith("s3") for location in target_locations):
            for action in channel_data.get("actions", []):
                params = action.get("params", {})
                rename_expression = params.get("RenameExpression")
                if action.get("type") != "Integrate" or not rename_expression:
                    continue
                path_match = re.search(
                    r"(?:^|/)hvr/([^/]+)/([^/]+)",
                    rename_expression,
                    re.IGNORECASE,
                )
                if path_match:
                    source_system, file_name = path_match.groups()
                    path_id = f"s3:path:HVR:{source_system.lower()}:{file_name.lower()}"
                    uri_or_prefix = f"hvr/{source_system.lower()}/{file_name.lower()}"
                else:
                    path_id = f"s3:path:HVR:{channel_name}"
                    uri_or_prefix = rename_expression
                add_node(
                    graph,
                    path_id,
                    "S3_PATH",
                    config_path,
                    uri_or_prefix=uri_or_prefix,
                    bucket_role="HVR",
                    path_expression=rename_expression,
                )
                add_edge(graph, channel_id, path_id, "COPIES_TO", config_path)

        if any(location.lower().startswith(("sf", "snowflake")) for location in target_locations):
            for table_name, table_definition in channel_data.get("tables", {}).items():
                relation_name = table_definition.get("base_name", table_name)
                relation_id = f"snowflake:relation:{relation_name.upper()}"
                add_node(
                    graph,
                    relation_id,
                    "SNOWFLAKE_RELATION",
                    config_path,
                    name=relation_name,
                    canonical_relation_id=relation_id,
                    kind="TABLE",
                    layer="landing",
                    creation_mechanism="HVR",
                )
                add_edge(graph, channel_id, relation_id, "LANDS_IN", config_path)

    return graph


def parse_hvr_param(path: str | Path) -> GraphPayload:
    """Extract declared columns and metadata from an HVR JSON .param file."""
    param_path = Path(path)
    document: Dict[str, Any] = json.loads(param_path.read_text(encoding="utf-8-sig"))
    graph = GraphPayload(nodes=[], edges=[])
    file_id = f"hvr:param:{param_path.stem}"
    add_node(
        graph,
        file_id,
        "HVR_PARAM_FILE",
        param_path,
        name=param_path.name,
        data_source=document.get("data_source"),
        delimiter=document.get("delim"),
    )

    for column_name, definition in document.get("columns", {}).items():
        column_id = f"{file_id}:column:{column_name}"
        add_node(
            graph,
            column_id,
            "HVR_COLUMN",
            param_path,
            name=column_name,
            **definition,
        )
        add_edge(graph, file_id, column_id, "DECLARES_COLUMN", param_path)
    return graph