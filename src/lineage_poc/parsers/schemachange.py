"""Read-only extraction of relation DDL from schemachange SQL migration files."""

import re
from pathlib import Path
from typing import Optional

from lineage_poc.graph.models import GraphPayload
from .common import add_edge, add_node, qualified_relation

_NAME = r'(?:(?:"?[\w$-]+"?)\.){0,2}"?[\w$-]+"?'
_CREATE = re.compile(
    rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:TEMPORARY|TRANSIENT)\s+)?(TABLE|VIEW|DYNAMIC\s+TABLE)\s+(?:IF\s+NOT\s+EXISTS\s+)?({_NAME})",
    re.IGNORECASE,
)
_ALTER = re.compile(rf"\bALTER\s+(TABLE|VIEW)\s+({_NAME})", re.IGNORECASE)
_USE_SCHEMA = re.compile(r"\bUSE\s+SCHEMA\s+(?:\S+\.)?([\w$-]+)", re.IGNORECASE)


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", " ", sql)


def _relation_name(name: str, current_schema: Optional[str]) -> str:
    parts = [part.strip(' "`') for part in name.split(".")]
    if len(parts) == 1 and current_schema:
        return qualified_relation(parts[0], current_schema)
    return qualified_relation(parts[-1], parts[-2] if len(parts) > 1 else None, parts[-3] if len(parts) > 2 else None)


def parse_schemachange_file(path: str | Path) -> GraphPayload:
    """Extract CREATE and ALTER relation operations; this does not apply migrations."""
    migration_path = Path(path)
    sql = _strip_sql_comments(migration_path.read_text(encoding="utf-8", errors="replace"))
    graph = GraphPayload(nodes=[], edges=[])
    migration_id = f"schemachange:migration:{migration_path.name}"
    add_node(graph, migration_id, "SCHEMACHANGE_MIGRATION", migration_path, name=migration_path.name)
    schema_match = _USE_SCHEMA.search(sql)
    current_schema = schema_match.group(1) if schema_match else None

    for match in _CREATE.finditer(sql):
        relation_kind, raw_name = match.groups()
        relation = _relation_name(raw_name, current_schema)
        relation_id = f"snowflake:relation:{relation}"
        relation_kind = relation_kind.upper().replace("DYNAMIC ", "")
        add_node(
            graph,
            relation_id,
            "SNOWFLAKE_RELATION",
            migration_path,
            name=relation,
            canonical_relation_id=relation_id,
            kind=relation_kind,
            creation_mechanism="SCHEMACHANGE",
        )
        add_edge(graph, migration_id, relation_id, "MIGRATES", migration_path, operation="CREATE")

    for match in _ALTER.finditer(sql):
        relation_kind, raw_name = match.groups()
        relation = _relation_name(raw_name, current_schema)
        relation_id = f"snowflake:relation:{relation}"
        add_node(
            graph,
            relation_id,
            "SNOWFLAKE_RELATION",
            migration_path,
            name=relation,
            canonical_relation_id=relation_id,
            kind=relation_kind.upper(),
            creation_mechanism="SCHEMACHANGE",
        )
        add_edge(graph, migration_id, relation_id, "MIGRATES", migration_path, operation="ALTER")
    return graph