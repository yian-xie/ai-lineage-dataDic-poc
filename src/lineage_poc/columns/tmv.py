"""Extract evidence-resolved dbt column mappings for the TMV repository set."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage
from sqlglot.optimizer.scope import traverse_scope


TMV_REPOSITORIES = (
    "kb-cdp-tenant-landing",
    "kb-cdp-tenant-protect-downstream",
)
_DBT_MACRO = re.compile(
    r"\{\{\s*(source|ref)\s*\(\s*(['\"])([^'\"]+)\2"
    r"(?:\s*,\s*(['\"])([^'\"]+)\4)?\s*\)\s*\}\}",
    re.IGNORECASE | re.DOTALL,
)
_CONFIG_MACRO = re.compile(r"\{\{\s*config\(.*?\)\s*\}\}", re.IGNORECASE | re.DOTALL)
_JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)


@contextmanager
def _quiet_sqlglot_dialect_warnings():
    logger = logging.getLogger("sqlglot")
    previous_level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(previous_level)


def _normalized_identifier(value: str) -> str:
    return value.replace('"', "").replace("`", "").replace("[", "").replace("]", "").strip().upper()


def _project_name(node_id: str, properties: dict) -> str:
    project = str(properties.get("project", ""))
    if project:
        return project
    parts = node_id.split(":")
    return parts[3] if len(parts) > 4 and parts[0] == "dbt" else ""


def _graph_indexes(graph: dict) -> dict[str, Any]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    models_by_project: dict[tuple[str, str], list[str]] = {}
    sources_by_project: dict[tuple[str, str, str], list[str]] = {}
    model_relations: dict[str, list[str]] = {}
    source_relations: dict[str, list[str]] = {}
    relation_nodes = {
        node_id: node for node_id, node in nodes.items()
        if node.get("type") == "SNOWFLAKE_RELATION"
    }

    for node_id, node in nodes.items():
        properties = node.get("properties", {})
        project = _project_name(node_id, properties)
        name = str(properties.get("name", ""))
        if node.get("type") == "DBT_MODEL" and project and name:
            models_by_project.setdefault((project, name.casefold()), []).append(node_id)
        elif node.get("type") == "DBT_SOURCE" and project and name:
            key = (project, str(properties.get("source_name", "")).casefold(), name.casefold())
            sources_by_project.setdefault(key, []).append(node_id)

    for edge in graph.get("edges", []):
        if edge.get("type") == "MATERIALIZES_AS" and edge.get("target") in relation_nodes:
            model_relations.setdefault(edge["source"], []).append(edge["target"])
        elif edge.get("type") == "RESOLVES_TO" and edge.get("target") in relation_nodes:
            source_relations.setdefault(edge["source"], []).append(edge["target"])

    relation_names: dict[str, list[str]] = {}
    for node_id, node in relation_nodes.items():
        name = _normalized_identifier(str(node.get("properties", {}).get("name", "")))
        if name:
            relation_names.setdefault(name, []).append(node_id)
            relation_names.setdefault(name.split(".")[-1], []).append(node_id)

    return {
        "nodes": nodes,
        "models_by_project": models_by_project,
        "sources_by_project": sources_by_project,
        "model_relations": model_relations,
        "source_relations": source_relations,
        "relation_nodes": relation_nodes,
        "relation_names": relation_names,
    }


def _only_relation(values: list[str]) -> str | None:
    unique = list(dict.fromkeys(values))
    return unique[0] if len(unique) == 1 else None


def _resolve_macro(kind: str, first: str, second: str | None, project: str, indexes: dict[str, Any]) -> str | None:
    if kind.casefold() == "source" and second is not None:
        source_ids = indexes["sources_by_project"].get(
            (project, first.casefold(), second.casefold()), []
        )
        relation_ids = [
            relation_id
            for source_id in source_ids
            for relation_id in indexes["source_relations"].get(source_id, [])
        ]
        return _only_relation(relation_ids)
    if kind.casefold() == "ref" and second is None:
        model_ids = indexes["models_by_project"].get((project, first.casefold()), [])
        relation_ids = [
            relation_id
            for model_id in model_ids
            for relation_id in indexes["model_relations"].get(model_id, [])
        ]
        return _only_relation(relation_ids)
    return None


def _replace_macros(sql: str, project: str, indexes: dict[str, Any]) -> tuple[str | None, dict[str, str], str | None]:
    normalized = _CONFIG_MACRO.sub("", sql)
    normalized = _JINJA_COMMENT.sub("", normalized)
    relation_tokens: dict[str, str] = {}
    unresolved: list[str] = []

    def replace(match: re.Match[str]) -> str:
        kind, first, second = match.group(1), match.group(3), match.group(5)
        relation_id = _resolve_macro(kind, first, second, project, indexes)
        if relation_id is None:
            unresolved.append(match.group(0))
            return "__TMV_UNRESOLVED_RELATION__"
        token = f"__TMV_REL_{len(relation_tokens)}__"
        relation_tokens[token.casefold()] = relation_id
        return token

    normalized = _DBT_MACRO.sub(replace, normalized)
    if unresolved:
        return None, relation_tokens, f"unresolved_dbt_reference:{unresolved[0]}"
    if "{{" in normalized or "{%" in normalized:
        return None, relation_tokens, "unsupported_jinja_expression"
    return normalized, relation_tokens, None


def _table_name_from_leaf(leaf: Any) -> tuple[str | None, str | None]:
    source_sql = str(leaf.source)
    try:
        source_ast = sqlglot.parse_one(f"SELECT * FROM {source_sql}", read="snowflake")
    except sqlglot.errors.ParseError:
        return None, None
    tables = list(source_ast.find_all(exp.Table))
    if isinstance(source_ast, exp.Table):
        tables.insert(0, source_ast)
    unique = {table.sql(dialect="snowflake"): table for table in tables}
    if len(unique) != 1:
        return None, None
    table = next(iter(unique.values()))
    return table.name, ".".join(part for part in (table.catalog, table.db, table.name) if part)


def _schema_from_explicit_sql_references(query: exp.Expression) -> dict[str, dict[str, str]]:
    """Give SQLGlot only the columns explicitly referenced against table aliases."""
    schema: dict[str, dict[str, str]] = {}
    for scope in traverse_scope(query):
        tables = {
            alias: source
            for alias, source in scope.sources.items()
            if isinstance(source, exp.Table)
        }
        for column in scope.columns:
            if column.table:
                source = tables.get(column.table)
                if source is not None:
                    schema.setdefault(source.name, {})[column.name] = "TEXT"
            elif len(tables) == 1:
                source = next(iter(tables.values()))
                schema.setdefault(source.name, {})[column.name] = "TEXT"
    return schema


def _relation_for_leaf(leaf: Any, token_relations: dict[str, str], indexes: dict[str, Any]) -> str | None:
    table_name, qualified_name = _table_name_from_leaf(leaf)
    if not table_name:
        return None
    token_id = token_relations.get(table_name.casefold())
    if token_id:
        return token_id
    candidates = []
    for name in (qualified_name, table_name):
        candidates.extend(indexes["relation_names"].get(_normalized_identifier(name), []))
    return _only_relation(candidates)


def _mapping_id(values: tuple[str, ...]) -> str:
    encoded = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    return "tmv-column:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def _leaf_paths(node: Any, parents: tuple = ()):
    path = (*parents, node)
    if not node.downstream:
        yield node, path
    else:
        for child in node.downstream:
            yield from _leaf_paths(child, path)


def build_column_inventory(
    graphs: dict[str, dict],
    evidence_root: Path,
    snapshot_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Trace direct dbt projections and retain only source relations resolved in the same graph."""
    records: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    seen: set[str] = set()

    components = {"landing": "kb-cdp-tenant-landing", "cdp_account": "kb-cdp-tenant-account", "account": "kb-cdp-tenant-account",
                  "enterprise": "kb-cdp-tenant-enterprise", "protect_downstream": "kb-cdp-tenant-protect-downstream"}
    for graph_name, repository in components.items():
        if graph_name not in graphs:
            continue
        graph = graphs[graph_name]
        indexes = _graph_indexes(graph)
        for model_id, model in indexes["nodes"].items():
            if model.get("type") != "DBT_MODEL":
                continue
            properties = model.get("properties", {})
            if properties.get("confidence") == "declared_reference":
                continue
            project = _project_name(model_id, properties)
            source_path = str(properties.get("source_path", ""))
            if not source_path.lower().endswith(".sql"):
                continue
            sql_path = evidence_root / repository / source_path
            if not sql_path.is_file():
                gaps.append({
                    "repository": repository,
                    "model_id": model_id,
                    "source_path": source_path,
                    "reason": "model_sql_missing_from_snapshot",
                })
                continue

            raw_sql = sql_path.read_text(encoding="utf-8", errors="replace")
            sql, token_relations, macro_gap = _replace_macros(raw_sql, project, indexes)
            if macro_gap:
                gaps.append({
                    "repository": repository,
                    "project": project,
                    "model_id": model_id,
                    "source_path": source_path,
                    "reason": macro_gap,
                })
                continue

            try:
                query = sqlglot.parse_one(sql, read="snowflake")
            except (sqlglot.errors.ParseError, ValueError, TypeError) as error:
                gaps.append({
                    "repository": repository,
                    "project": project,
                    "model_id": model_id,
                    "source_path": source_path,
                    "reason": "sqlglot_parse_or_lineage_failed",
                    "detail": str(error)[:400],
                })
                continue

            target_relations = indexes["model_relations"].get(model_id, [])
            target_relation_id = _only_relation(target_relations)
            if not target_relation_id:
                gaps.append({
                    "repository": repository,
                    "project": project,
                    "model_id": model_id,
                    "source_path": source_path,
                    "reason": "model_has_no_unique_materialized_relation",
                })
                continue

            select = query if isinstance(query, exp.Select) else query.find(exp.Select)
            expressions = {}
            if select is not None:
                for expression in select.expressions:
                    output_name = expression.alias_or_name
                    if output_name:
                        expressions.setdefault(output_name.casefold(), expression)

            for target_column, target_expression in expressions.items():
                target_column = target_column.upper()
                if target_column == "*" or target_expression is None:
                    gaps.append({
                        "repository": repository,
                        "project": project,
                        "model_id": model_id,
                        "source_path": source_path,
                        "target_column": target_column,
                        "reason": "target_projection_not_uniquely_identified",
                    })
                    continue

                try:
                    with _quiet_sqlglot_dialect_warnings():
                        trace = lineage(
                            target_column,
                            sql,
                            schema=_schema_from_explicit_sql_references(query),
                            dialect="snowflake",
                        )
                except (sqlglot.errors.SqlglotError, ValueError, TypeError) as error:
                    gaps.append({
                        "repository": repository,
                        "project": project,
                        "model_id": model_id,
                        "source_path": source_path,
                        "target_column": target_column,
                        "reason": "column_lineage_requires_unavailable_schema_or_unsupported_sql",
                        "detail": str(error)[:400],
                    })
                    continue

                leaves = list(_leaf_paths(trace))
                if not leaves:
                    gaps.append({
                        "repository": repository,
                        "project": project,
                        "model_id": model_id,
                        "source_path": source_path,
                        "target_column": target_column,
                        "reason": "no_source_column_in_lineage_trace",
                    })
                    continue

                for leaf, trace_path in leaves:
                    if not isinstance(leaf.expression, exp.Table):
                        gaps.append({
                            "repository": repository, "project": project,
                            "model_id": model_id, "source_path": source_path,
                            "target_column": target_column,
                            "reason": "constant_or_unresolved_expression_has_no_source_column",
                            "expression": leaf.expression.sql(dialect="snowflake"),
                        })
                        continue
                    source_relation_id = _relation_for_leaf(leaf, token_relations, indexes)
                    source_column = str(leaf.name).split(".")[-1].strip('"`').upper()
                    if not source_relation_id or not source_column or source_column == "*":
                        gaps.append({
                            "repository": repository,
                            "project": project,
                            "model_id": model_id,
                            "source_path": source_path,
                            "target_column": target_column,
                            "source_expression": str(leaf.source)[:300],
                            "reason": "source_relation_or_column_not_resolved",
                        })
                        continue

                    projection = trace_path[1].expression if isinstance(query, exp.SetOperation) and len(trace_path) > 2 else target_expression
                    transformation = projection.sql(dialect="snowflake")
                    identity = (
                        repository,
                        model_id,
                        source_relation_id,
                        source_column,
                        target_relation_id,
                        target_column,
                        source_path,
                        transformation,
                    )
                    mapping_id = _mapping_id(identity)
                    if mapping_id in seen:
                        continue
                    seen.add(mapping_id)
                    source_relation = indexes["relation_nodes"][source_relation_id]
                    target_relation = indexes["relation_nodes"][target_relation_id]
                    records.append({
                        "field_id": mapping_id,
                        "graph_id": "tmv_column_lineage",
                        "snapshot_id": snapshot_id,
                        "repository": repository,
                        "project": project,
                        "source_relation_id": source_relation_id,
                        "source_relation": source_relation.get("properties", {}).get("name"),
                        "source_column": source_column,
                        "target_model_id": model_id,
                        "target_model": properties.get("name"),
                        "target_relation_id": target_relation_id,
                        "target_relation": target_relation.get("properties", {}).get("name"),
                        "target_column": target_column,
                        "transformation_expression": transformation,
                        "expression_chain": [item.expression.sql(dialect="snowflake") for item in trace_path[:-1]],
                        "confidence": "explicit",
                        "confidence_reason": "SQLGlot traced the selected target projection to this exact declared or materialized relation and source column in the captured SQL.",
                        "source_path": source_path,
                        "source_line": target_expression.meta.get("line"),
                        "lineage_granularity": "column-level-within-repository",
                    })

    records.sort(key=lambda row: (row["repository"], row["project"], row["target_relation_id"], row["target_column"], row["source_relation_id"], row["source_column"]))
    gaps.sort(key=lambda row: (row.get("repository", ""), row.get("source_path", ""), row.get("reason", ""), row.get("target_column", "")))
    return records, gaps