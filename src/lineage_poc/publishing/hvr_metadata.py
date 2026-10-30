"""Export HVR .param declarations as auxiliary metadata, not graph entities."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, source_root as default_source_root

import json
from pathlib import Path


PROJECT_ROOT = REPOSITORY_ROOT
WORKSPACE_ROOT = default_source_root()

from lineage_poc.parsers.hvr import parse_hvr_param
from lineage_poc.parsers.full import scan_instruction_like_content


def build_metadata(source_path: Path, source_root: Path | None = None) -> dict:
    source_path = Path(source_path).resolve()
    workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    input_flags = scan_instruction_like_content([source_path], source_root=workspace_root)
    parsed = parse_hvr_param(source_path)
    file_node = next(node for node in parsed.nodes if node.label == "HVR_PARAM_FILE")
    metadata = {
        "metadata_type": "hvr_param_metadata",
        "source_file": source_path.relative_to(workspace_root).as_posix(),
        "data_source": file_node.properties.get("data_source"),
        "delimiter": file_node.properties.get("delimiter"),
        "input_flags": input_flags,
        "columns": [
            {
                key: value
                for key, value in node.properties.items()
                if key not in {"source_path", "confidence"}
            }
            for node in parsed.nodes
            if node.label == "HVR_COLUMN"
        ],
    }
    return metadata


def export_metadata(source_path: Path, destination: Path, source_root: Path | None = None) -> dict:
    metadata = build_metadata(source_path, source_root=source_root)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")
    return metadata