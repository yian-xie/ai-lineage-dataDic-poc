#!/usr/bin/env python3
"""Map Ultracs extract paths to HVR capture routes and destinations."""

import fnmatch
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "output" / "extract_file_inventory.md"
HVR_CHANNELS = ROOT.parent / "kb-cdp-hvr" / "hvr-config" / "apps" / "channels"
OUTPUT = ROOT / "output" / "extract_to_hvr_map.md"


def inventory_extracts() -> dict[str, set[str]]:
    extracts: dict[str, set[str]] = defaultdict(set)
    for line in INVENTORY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ["):
            continue
        cells = [cell.strip().replace("\\|", "|") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        source_match = re.search(r"\[([^]]+)\]", cells[0])
        output_path = cells[1]
        if not source_match or output_path == "-":
            continue
        extracts[output_path].add(source_match.group(1))
    return dict(extracts)


def load_channels() -> dict[str, dict[str, Any]]:
    channels: dict[str, dict[str, Any]] = {}
    for config_path in sorted(HVR_CHANNELS.glob("ult_*.json")):
        try:
            raw_text = config_path.read_text(encoding="utf-8")
            document = json.loads(raw_text)
            config = document["changes"][0]["add_channel"]
        except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            continue
        channels[config_path.name] = {
            "filename": config_path.name,
            "raw_text": raw_text,
            "config": config,
            "patterns": capture_patterns(config),
        }
    return channels


def capture_patterns(config: dict[str, Any]) -> list[str]:
    patterns = []
    for action in config.get("actions", []):
        pattern = action.get("params", {}).get("Pattern")
        if action.get("type") == "Capture" and isinstance(pattern, str) and pattern:
            patterns.append(pattern)
    return patterns


def example_filename(output_path: str) -> str | None:
    name = output_path.rsplit("/", 1)[-1]
    if name.startswith("DYNAMIC(") or name in {"KBDOSOUTPUT", "KBDOSOUTPUT2", "KBDOSOUTPUT3", "&HOLD&"}:
        return None
    substitutions = {
        "HEAD": "01A.TXT",
        "BHEAD": "MON.TXT",
        "VAR": "1",
        "DATE": "20250101",
    }
    for key, value in substitutions.items():
        name = name.replace("{" + key + "}", value)
    if "{" in name or "}" in name:
        return None
    return name


def channel_tables(config: dict[str, Any]) -> list[str]:
    return sorted(config.get("tables", {}).keys())


def target_locations(config: dict[str, Any]) -> list[str]:
    return config.get("loc_groups", {}).get("TARGET", {}).get("members", [])


def s3_pair(channel_filename: str, all_channels: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    stem = Path(channel_filename).stem
    if not stem.startswith("ult_s3_") or not stem.endswith("1"):
        return None
    second_filename = stem[:-1] + "2.json"
    second = all_channels.get(second_filename)
    if second:
        return Path(second_filename).stem, second
    return None


def s3_path(config: dict[str, Any]) -> str:
    for action in config.get("actions", []):
        rename = action.get("params", {}).get("RenameExpression")
        if action.get("type") == "Integrate" and rename:
            return rename
    return "(target path not declared in channel config)"


def destination_for(
    channel_filename: str,
    channel_data: dict[str, Any],
    all_channels: dict[str, dict[str, Any]],
) -> tuple[str, str, str, str, str]:
    config = channel_data["config"]
    targets = target_locations(config)
    tables = channel_tables(config)
    if channel_filename.startswith("ult_sf_"):
        destination = ", ".join(targets) or "Snowflake target not declared"
        table = ", ".join(tables) if tables else "(no destination table declared)"
        return "Snowflake", table, channel_filename, destination, Path(channel_filename).stem

    pair = s3_pair(channel_filename, all_channels)
    if pair:
        step2_name, step2_data = pair
        final_targets = target_locations(step2_data["config"])
        destination = ", ".join(final_targets) or "S3 target not declared"
        path = s3_path(step2_data["config"])
        table = f"(S3 object path; no HVR table) `{path}`"
        config_files = f"{channel_filename}; {step2_data['filename']}"
        route_name = f"{Path(channel_filename).stem} -> {step2_name}"
        return "S3", table, config_files, destination, route_name

    if any(location.lower().startswith("s3") for location in targets):
        return "S3", "(S3 object path; no HVR table)", channel_filename, ", ".join(targets), Path(channel_filename).stem
    return "UNRESOLVED", "(no destination table declared)", channel_filename, ", ".join(targets) or "(target not declared)", Path(channel_filename).stem


def matching_rows(extracts: dict[str, set[str]], all_channels: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[tuple[str, list[str]]]]:
    source_channels = {
        filename: value
        for filename, value in all_channels.items()
        if "fs_ultracs" in value["config"].get("loc_groups", {}).get("SOURCE", {}).get("members", [])
    }
    matches: list[dict[str, Any]] = []
    unmatched: list[tuple[str, list[str]]] = []
    for output_path, programs in sorted(extracts.items(), key=lambda item: item[0].casefold()):
        filename = example_filename(output_path)
        found = []
        if filename:
            for channel_filename, channel_data in source_channels.items():
                for pattern in channel_data["patterns"]:
                    if not fnmatch.fnmatchcase(filename.casefold(), pattern.casefold()):
                        continue
                    config = channel_data["config"]
                    status = "CONFIRMED" if pattern.casefold() == output_path.rsplit("/", 1)[-1].casefold() else "INFERRED"
                    destination_type, table, config_files, target, route_name = destination_for(
                        channel_filename,
                        channel_data,
                        all_channels,
                    )
                    found.append({
                        "extract": output_path,
                        "channel": route_name,
                        "config_files": config_files,
                        "destination_type": destination_type,
                        "destination_table": table,
                        "status": status,
                        "pattern": pattern,
                        "target": target,
                        "programs": sorted(programs),
                    })
        if found:
            matches.extend(found)
        else:
            unmatched.append((output_path, sorted(programs)))
    return matches, unmatched


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def generate_report() -> str:
    extracts = inventory_extracts()
    channels = load_channels()
    matches, unmatched = matching_rows(extracts, channels)
    lines = [
        "# Ultracs Extract to HVR Map",
        "",
        f"Source inventory: [extract_file_inventory.md](extract_file_inventory.md), containing {len(extracts)} unique output paths from the Ultracs BASIC sweep. HVR mapping scanned {len(channels)} Ultracs channel configurations.",
        "",
        "`CONFIRMED` means the output filename (case-insensitive) is written literally in an HVR Capture `Pattern`. `INFERRED` means a representative expansion of an inventory placeholder such as `{HEAD}` or `{BHEAD}` matched the HVR Capture pattern. S3 routes pair the `ult_s3_*1` capture/conversion config with its `ult_s3_*2` S3 delivery config. Destination table is `-` for S3 because these HVR S3 configs define file paths, not tables.",
        "",
        f"Matched routes: {len(matches)} rows across {len({row['extract'] for row in matches})} extract paths. Unmatched inventory paths: {len(unmatched)}.",
        "",
        "## Matched Routes",
        "",
        "| extract_file | hvr_channel_name | channel_config_file | destination_type | destination_table | match_status | matched_capture_pattern |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in matches:
        config_links = []
        for filename in row["config_files"].split("; "):
            target = f"../../kb-cdp-hvr/hvr-config/apps/channels/{filename}"
            config_links.append(f"[{filename}]({target})")
        cells = [
            row["extract"],
            row["channel"],
            "; ".join(config_links),
            row["destination_type"],
            row["destination_table"],
            row["status"],
            row["pattern"],
        ]
        lines.append("| " + " | ".join(markdown_cell(str(cell)) for cell in cells) + " |")

    lines.extend([
        "",
        "## No Matching Capture Pattern",
        "",
        "These inventory outputs did not match a capture pattern in the scanned Ultracs HVR configs. Container/dynamic expressions are listed as inventory items but are not concrete extract filenames. Absence of a match does not prove there is no external or environment-specific ingestion route.",
        "",
        "| extract_file_or_expression | source_programs | status |",
        "|---|---|---|",
    ])
    for output_path, programs in unmatched:
        lines.append(f"| {markdown_cell(output_path)} | {markdown_cell('; '.join(programs))} | NO MATCH |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generate_report(), encoding="utf-8")
    print(f"Generated {OUTPUT}")
