"""Static parser for dbt source declarations, model dependencies, and materializations."""

import re
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import yaml

from lineage_poc.graph.models import GraphPayload
from .common import add_edge, add_node, qualified_relation

_SOURCE_CALL = re.compile(r"\bsource\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)")
_REF_CALL = re.compile(r"\bref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")


def _model_layer(path: Path, schema: str | None = None) -> str:
    for layer in ("internal", "public"):
        if layer in {part.lower() for part in path.parts}:
            return layer
    return schema.lower() if schema else "unknown"


def _relation_id(name: str, schema: str | None = None, database: str | None = None) -> str:
    return f"snowflake:relation:{qualified_relation(name, schema, database)}"


def _add_physical_relation(
    graph: GraphPayload,
    name: str,
    path: Path,
    kind: str,
    layer: str,
    creation_mechanism: str | None,
    schema: str | None = None,
    database: str | None = None,
    confidence: str = "explicit",
    description: str | None = None,
) -> str:
    relation_id = _relation_id(name, schema, database)
    relation_name = qualified_relation(name, schema, database)
    add_node(
        graph,
        relation_id,
        "SNOWFLAKE_RELATION",
        path,
        confidence=confidence,
        name=relation_name,
        canonical_relation_id=relation_id,
        kind=kind,
        layer=layer,
        creation_mechanism=creation_mechanism,
        **({"description": description} if description else {}),
    )
    return relation_id


def _load_yaml(path: Path) -> Dict[str, Any]:
    text = "\n".join(
        line.rstrip("\t")
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _walk_model_yaml(model_root: Path) -> Iterable[Tuple[Path, Dict[str, Any]]]:
    for yaml_path in sorted((*model_root.rglob("*.yml"), *model_root.rglob("*.yaml"))):
        document = _load_yaml(yaml_path)
        for source in document.get("sources", []) or []:
            source_name = source.get("name")
            for table in source.get("tables", []) or []:
                table_name = table.get("name")
                if source_name and table_name:
                    yield yaml_path, {
                        "kind": "source",
                        "source_name": source_name,
                        "table_name": table_name,
                        "description": table.get("description", source.get("description", "")),
                        "schema": table.get("schema", source.get("schema")),
                        "database": table.get("database", source.get("database")),
                    }
        for model in document.get("models", []) or []:
            if model.get("name"):
                yield yaml_path, {"kind": "model", **model}


def parse_dbt_project(path: str | Path) -> GraphPayload:
    """Parse dbt YAML declarations and SQL source()/ref() calls under a project or models directory."""
    project_path = Path(path)
    model_root = project_path / "models" if (project_path / "models").is_dir() else project_path
    graph = GraphPayload(nodes=[], edges=[])
    sources: Dict[Tuple[str, str], str] = {}
    models: Dict[str, Dict[str, Any]] = {}
    model_yaml: Dict[str, Path] = {}

    for yaml_path, declaration in _walk_model_yaml(model_root):
        if declaration["kind"] == "source":
            source_name = declaration["source_name"]
            table_name = declaration["table_name"]
            node_id = f"dbt:source:{source_name}.{table_name}"
            relation = qualified_relation(table_name, declaration.get("schema"), declaration.get("database"))
            add_node(
                graph,
                node_id,
                "DBT_SOURCE",
                yaml_path,
                name=table_name,
                source_name=source_name,
                relation=relation,
                **({"description": declaration.get("description")} if declaration.get("description") else {}),
                schema=declaration.get("schema"),
                database=declaration.get("database"),
            )
            sources[(source_name, table_name)] = node_id
            schema = declaration.get("schema")
            source_description = str(declaration.get("description", "")).lower()
            if schema and schema.upper() == "RAW":
                relation_kind = "TABLE"
                relation_layer = "landing"
                relation_confidence = "explicit"
            elif schema and "PUBLIC" in schema.upper() and "view" in source_description:
                relation_kind = "VIEW"
                relation_layer = "landing"
                relation_confidence = "explicit"
            else:
                relation_kind = "TABLE"
                relation_layer = "landing"
                relation_confidence = "inferred"
            relation_id = _add_physical_relation(
                graph,
                table_name,
                yaml_path,
                relation_kind,
                relation_layer,
                None,
                schema,
                declaration.get("database"),
                relation_confidence,
                declaration.get("description"),
            )
            add_edge(graph, node_id, relation_id, "RESOLVES_TO", yaml_path, confidence=relation_confidence)
        else:
            model_name = declaration["name"]
            models[model_name] = declaration
            model_yaml[model_name] = yaml_path

    sql_files = sorted(model_root.rglob("*.sql"))
    sql_by_stem = {sql_path.stem: sql_path for sql_path in sql_files}
    for model_name, declaration in models.items():
        model_path = sql_by_stem.get(model_name, model_yaml[model_name])
        model_id = f"dbt:model:{model_name}"
        config = declaration.get("config") or {}
        materialized = str(config.get("materialized", "view")).lower()
        schema = config.get("schema")
        layer = _model_layer(model_path, schema)
        effective_schema = schema or (layer.upper() if layer in {"internal", "public"} else None)
        add_node(
            graph,
            model_id,
            "DBT_MODEL",
            model_path,
            name=model_name,
            **({"description": declaration.get("description")} if declaration.get("description") else {}),
            materialized=materialized,
            schema=schema,
            database=config.get("database"),
            layer=layer,
        )
        if materialized in {"table", "incremental", "view"}:
            relation_kind = "VIEW" if materialized == "view" else "TABLE"
            relation_id = _add_physical_relation(
                graph,
                model_name,
                model_path,
                relation_kind,
                layer,
                "DBT",
                effective_schema,
                config.get("database"),
                description=declaration.get("description"),
            )
            add_edge(graph, model_id, relation_id, "MATERIALIZES_AS", model_path)
        sql_text = model_path.read_text(encoding="utf-8", errors="replace") if model_path.suffix == ".sql" else ""
        for source_name, table_name in _SOURCE_CALL.findall(sql_text):
            source_id = sources.get((source_name, table_name), f"dbt:source:{source_name}.{table_name}")
            if not any(node.id == source_id for node in graph.nodes):
                add_node(graph, source_id, "DBT_SOURCE", model_path, confidence="declared_reference", source_name=source_name, name=table_name)
                relation_id = _add_physical_relation(
                    graph,
                    table_name,
                    model_path,
                    "TABLE",
                    "landing",
                    None,
                    confidence="declared_reference",
                )
                add_edge(graph, source_id, relation_id, "RESOLVES_TO", model_path, confidence="declared_reference")
            add_edge(graph, model_id, source_id, "DEPENDS_ON", model_path)
        for referenced_model in _REF_CALL.findall(sql_text):
            target_id = f"dbt:model:{referenced_model}"
            if not any(node.id == target_id for node in graph.nodes):
                add_node(graph, target_id, "DBT_MODEL", model_path, confidence="declared_reference", name=referenced_model)
            add_edge(graph, model_id, target_id, "DEPENDS_ON", model_path)

    for sql_path in sql_files:
        if sql_path.stem in models:
            continue
        model_id = f"dbt:model:{sql_path.stem}"
        layer = _model_layer(sql_path)
        schema = layer.upper() if layer in {"internal", "public"} else None
        add_node(graph, model_id, "DBT_MODEL", sql_path, name=sql_path.stem, materialized="view", layer=layer)
        relation_id = _add_physical_relation(
            graph,
            sql_path.stem,
            sql_path,
            "VIEW",
            layer,
            "DBT",
            schema,
        )
        add_edge(graph, model_id, relation_id, "MATERIALIZES_AS", sql_path)
        sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
        for source_name, table_name in _SOURCE_CALL.findall(sql_text):
            source_id = sources.get((source_name, table_name), f"dbt:source:{source_name}.{table_name}")
            if not any(node.id == source_id for node in graph.nodes):
                add_node(graph, source_id, "DBT_SOURCE", sql_path, confidence="declared_reference", source_name=source_name, name=table_name)
                relation_id = _add_physical_relation(
                    graph,
                    table_name,
                    sql_path,
                    "TABLE",
                    "landing",
                    None,
                    confidence="declared_reference",
                )
                add_edge(graph, source_id, relation_id, "RESOLVES_TO", sql_path, confidence="declared_reference")
            add_edge(graph, model_id, source_id, "DEPENDS_ON", sql_path)
        for referenced_model in _REF_CALL.findall(sql_text):
            target_id = f"dbt:model:{referenced_model}"
            if not any(node.id == target_id for node in graph.nodes):
                add_node(graph, target_id, "DBT_MODEL", sql_path, confidence="declared_reference", name=referenced_model)
            add_edge(graph, model_id, target_id, "DEPENDS_ON", sql_path)

    return graph