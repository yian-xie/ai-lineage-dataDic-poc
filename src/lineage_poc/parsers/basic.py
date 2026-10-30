"""Graph adapter for the existing lightweight Ultracs BASIC parser."""

import re
from pathlib import Path

from lineage_poc.graph.models import GraphPayload
from lineage_poc.parsers.ultracs_basic import parse_ultracs_basic_file
from .common import add_edge, add_node


def parse_basic_file(path: str | Path) -> GraphPayload:
    """Represent BASIC programs and file handles without changing the legacy API."""
    source_path = Path(path)
    program = parse_ultracs_basic_file(source_path)
    graph = GraphPayload(nodes=[], edges=[])
    program_id = f"basic:program:{program.name}"
    add_node(
        graph,
        program_id,
        "PROGRAM",
        source_path,
        name=program.name,
        operations=program.operations,
        assignments=program.assignments,
    )

    handles = {}
    record_outputs = {}
    for operation in program.operations:
        match = re.match(r"OPEN\s+(.+?)\s+TO\s+(\w+)$", operation, re.IGNORECASE)
        if match:
            file_name, handle = match.groups()
            handles[handle.upper()] = file_name.strip(" '")
            continue
        record_match = re.search(
            r"\bOPENSEQ\s+['\"]([^'\"]+)['\"]\s*,\s*(.+?)\s+TO\s+(\w+)\b",
            operation,
            re.IGNORECASE,
        )
        if record_match:
            container, record_expression, handle = record_match.groups()
            record_match = re.match(r"['\"]([^'\"]+)['\"](?::([A-Z0-9_]+))?", record_expression.strip(), re.IGNORECASE)
            if record_match:
                record_name, suffix = record_match.groups()
                if suffix:
                    record_name = f"{record_name}{{{suffix.upper()}}}"
                record_outputs[handle.upper()] = f"{container.strip()}/{record_name}"

    read_handles = set()
    write_handles = set()
    for operation in program.operations:
        read_match = re.search(r"\bREAD(?:V)?\s+.*?\s+FROM\s+(\w+)", operation, re.IGNORECASE)
        write_match = re.search(r"\bWRITE(?:SEQ)?\s+.*?\s+ON\s+(\w+)", operation, re.IGNORECASE)
        if read_match:
            read_handles.add(read_match.group(1).upper())
        if write_match:
            write_handles.add(write_match.group(1).upper())

    for file_name in program.open_files:
        file_id = f"basic:file:{file_name}"
        add_node(graph, file_id, "MV_FILE", source_path, name=file_name)
        add_edge(graph, program_id, file_id, "READS_FROM", source_path)

    for handle in read_handles:
        if handle in handles:
            add_edge(graph, program_id, f"basic:file:{handles[handle]}", "READS_FROM", source_path)
    for handle in write_handles:
        if handle in record_outputs:
            output_path = record_outputs[handle]
            file_name = output_path.rsplit("/", 1)[-1]
            extract_id = f"basic:extract:{file_name}"
            add_node(
                graph,
                extract_id,
                "EXTRACT_FILE",
                source_path,
                name=file_name,
                output_path=output_path,
                format="pipe-delimited",
                output_handle=handle,
            )
            add_edge(graph, program_id, extract_id, "WRITES_TO", source_path)
            continue
        if handle in handles:
            file_name = handles[handle]
            extract_id = f"basic:extract:{file_name}"
            add_node(
                graph,
                extract_id,
                "EXTRACT_FILE",
                source_path,
                name=file_name,
                format="pipe-delimited",
                output_handle=handle,
            )
            add_edge(graph, program_id, extract_id, "WRITES_TO", source_path)
    return graph