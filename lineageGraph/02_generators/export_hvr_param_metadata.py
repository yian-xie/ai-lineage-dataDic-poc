"""Export HVR .param declarations as auxiliary metadata, not graph entities."""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lineage.parsers.hvr import parse_hvr_param
from generate_full_parser_lineage import scan_instruction_like_content


def main() -> None:
    source_path = WORKSPACE_ROOT / "kb-cdp-hvr/hvr-config/scripts/DWACC.param"
    input_flags = scan_instruction_like_content([source_path])
    parsed = parse_hvr_param(source_path)
    file_node = next(node for node in parsed.nodes if node.label == "HVR_PARAM_FILE")
    metadata = {
        "metadata_type": "hvr_param_metadata",
        "source_file": source_path.relative_to(WORKSPACE_ROOT).as_posix(),
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
    output_path = PROJECT_ROOT / "output/hvr_param_metadata.json"
    output_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()