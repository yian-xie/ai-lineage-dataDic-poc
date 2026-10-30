"""Static AST adapter for Airflow DAG declarations and explicit table maps."""

import ast
from pathlib import Path
from typing import Any, Dict

from lineage_poc.graph.models import GraphPayload
from .common import add_edge, add_node, qualified_relation


def parse_airflow_dag(path: str | Path) -> GraphPayload:
    """Read Airflow task IDs and literal file-to-table dictionaries without importing DAGs."""
    dag_path = Path(path)
    tree = ast.parse(dag_path.read_text(encoding="utf-8"), filename=str(dag_path))
    graph = GraphPayload(nodes=[], edges=[])
    dag_id = f"airflow:dag:{dag_path.stem}"
    add_node(graph, dag_id, "AIRFLOW_DAG", dag_path, name=dag_path.stem)
    product_root = next(
        (parent for parent in dag_path.parents if (parent / "dbt").is_dir()),
        dag_path.parent,
    )
    product_id = f"cdp:product:{product_root.name}"
    add_node(graph, product_id, "CDP_PRODUCT", dag_path, name=product_root.name)
    add_edge(graph, product_id, dag_id, "CONTAINS", dag_path)
    dbt_task_id = f"airflow:task:{dag_path.stem}:run_dbt_bash"
    dbt_task_found = False

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if any(isinstance(target, ast.Name) and target.id == "file_and_table_names" for target in targets):
                try:
                    mapping: Dict[str, Any] = ast.literal_eval(value)
                except (ValueError, TypeError):
                    continue
                for file_name, table_name in mapping.items():
                    copy_task_name = f"copy_s3_files_from_hvr_to_datalake_task_for_{file_name}"
                    load_task_name = f"copy_s3_files_to_snowflake_task_for_{file_name}"
                    copy_task_id = f"airflow:task:{dag_path.stem}:{copy_task_name}"
                    load_task_id = f"airflow:task:{dag_path.stem}:{load_task_name}"
                    hvr_path_id = f"s3:path:HVR:ultracs:{file_name}"
                    datalake_path_id = f"s3:path:DATALAKE:ultracs:{file_name}"
                    relation_name = qualified_relation(str(table_name), schema="RAW")
                    relation_id = f"snowflake:relation:{relation_name}"

                    add_node(
                        graph,
                        copy_task_id,
                        "AIRFLOW_TASK",
                        dag_path,
                        task_id=copy_task_name,
                        task_kind="copy_hvr_to_datalake",
                        source_file=file_name,
                    )
                    add_node(
                        graph,
                        load_task_id,
                        "AIRFLOW_TASK",
                        dag_path,
                        task_id=load_task_name,
                        task_kind="load_s3_to_snowflake",
                        source_file=file_name,
                    )
                    add_node(
                        graph,
                        hvr_path_id,
                        "S3_PATH",
                        dag_path,
                        uri_or_prefix=f"hvr/ultracs/{file_name}",
                        bucket_role="HVR",
                    )
                    add_node(
                        graph,
                        datalake_path_id,
                        "S3_PATH",
                        dag_path,
                        uri_or_prefix=f"{{tenancy}}/hvr/ultracs/{file_name}{{date_partition}}",
                        bucket_role="DATALAKE",
                    )
                    add_node(
                        graph,
                        relation_id,
                        "SNOWFLAKE_RELATION",
                        dag_path,
                        name=relation_name,
                        canonical_relation_id=relation_id,
                        kind="TABLE",
                        layer="landing",
                        creation_mechanism="AIRFLOW_COPY",
                    )
                    add_edge(graph, dag_id, copy_task_id, "CONTAINS_TASK", dag_path)
                    add_edge(graph, dag_id, load_task_id, "CONTAINS_TASK", dag_path)
                    add_edge(graph, copy_task_id, hvr_path_id, "COPIES_FROM", dag_path)
                    add_edge(graph, copy_task_id, datalake_path_id, "COPIES_TO", dag_path)
                    add_edge(graph, load_task_id, datalake_path_id, "LOADS_FROM", dag_path)
                    add_edge(graph, load_task_id, relation_id, "LOADS_TO", dag_path, source_file=file_name)
                    add_edge(graph, copy_task_id, load_task_id, "PRECEDES", dag_path)
                    if dbt_task_found:
                        add_edge(graph, load_task_id, dbt_task_id, "PRECEDES", dag_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_dbt_bash":
            dbt_task_found = True
            add_node(
                graph,
                dbt_task_id,
                "AIRFLOW_TASK",
                dag_path,
                task_id=node.name,
                task_kind="dbt_build",
            )
            add_edge(graph, dag_id, dbt_task_id, "CONTAINS_TASK", dag_path)
            models_root = product_root / "dbt" / "models"
            for model_path in sorted(models_root.rglob("*.sql")) if models_root.is_dir() else []:
                model_id = f"dbt:model:{model_path.stem}"
                add_node(graph, model_id, "DBT_MODEL", model_path, name=model_path.stem)
                add_edge(graph, dbt_task_id, model_id, "EXECUTES_DBT", dag_path)
            for task in [
                item for item in graph.nodes
                if item.label == "AIRFLOW_TASK"
                and item.properties.get("task_kind") == "load_s3_to_snowflake"
            ]:
                add_edge(graph, task.id, dbt_task_id, "PRECEDES", dag_path)

        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "task_id" or not isinstance(keyword.value, ast.Constant):
                continue
            task_name = keyword.value.value
            task_id = f"airflow:task:{dag_path.stem}:{task_name}"
            add_node(graph, task_id, "AIRFLOW_TASK", dag_path, task_id=task_name)
            add_edge(graph, dag_id, task_id, "CONTAINS_TASK", dag_path)

    return graph