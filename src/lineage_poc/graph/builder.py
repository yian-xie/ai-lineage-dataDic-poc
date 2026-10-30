from typing import Iterable, List, Tuple

from lineage_poc.graph.models import Edge, GraphPayload, Node


def _add_node(nodes: List[Node], node_id: str, label: str, **properties) -> None:
    if not any(node.id == node_id for node in nodes):
        nodes.append(Node(id=node_id, label=label, properties=properties))
    else:
        for node in nodes:
            if node.id == node_id:
                node.label = label
                node.properties.update(properties)
                break


def _add_edge(edges: List[Edge], source: str, target: str, type_name: str, **properties) -> None:
    edges.append(Edge(source=source, target=target, type=type_name, properties=properties))


def build_sample_graph() -> GraphPayload:
    """Build a sample lineage graph for the Ultracs account summary extract."""
    nodes: List[Node] = []
    edges: List[Edge] = []

    # System and source file
    _add_node(nodes, "ULTRACS", "system", name="Ultracs Legacy", domain="core-banking")
    _add_node(nodes, "KWDW_ACC", "file", path="kb-ultracs-datawarehouse/KWDW_ACC", format="legacy-variable-record")
    _add_node(nodes, "dw_acc_daily_account_summary", "extract", name="Daily Account Summary Extract", file_name="KWDW_ACC")

    # Raw layer
    _add_node(nodes, "raw_ultracs_account_summary", "table", name="raw_ultracs_account_summary", layer="raw", warehouse="snowflake")
    _add_node(nodes, "stg_account_daily", "table", name="stg_account_daily", layer="stage", warehouse="snowflake")
    _add_node(nodes, "dim_account", "table", name="dim_account", layer="dimensional", warehouse="snowflake")
    _add_node(nodes, "fact_account_balance", "table", name="fact_account_balance", layer="fact", warehouse="snowflake")

    # Logical process nodes
    _add_node(nodes, "job_kwdw_acc", "job", name="KWDW_ACC batch job", scheduler="legacy-batch")
    _add_node(nodes, "process_daily_account_extract", "process", name="Daily Account Extract Process")

    # Edges
    _add_edge(edges, "ULTRACS", "KWDW_ACC", "contains_file", owner="Kiwibank")
    _add_edge(edges, "KWDW_ACC", "dw_acc_daily_account_summary", "generated_by", job="KWDW_ACC")
    _add_edge(edges, "job_kwdw_acc", "dw_acc_daily_account_summary", "runs", description="legacy extraction job")
    _add_edge(edges, "dw_acc_daily_account_summary", "raw_ultracs_account_summary", "loaded_to", method="daily-batch")
    _add_edge(edges, "raw_ultracs_account_summary", "stg_account_daily", "transformed_to", rule_set="account_snapshot")
    _add_edge(edges, "stg_account_daily", "dim_account", "curated_as", scope="account-dimension")
    _add_edge(edges, "stg_account_daily", "fact_account_balance", "aggregated_into", scope="daily-balance")
    _add_edge(edges, "process_daily_account_extract", "stg_account_daily", "creates", source_system="legacy_extract")

    # Column-level lineage examples
    column_examples: Iterable[Tuple[str, str, str, str]] = [
        ("CIS", "raw_ultracs_account_summary", "dim_account", "account_id"),
        ("PID", "raw_ultracs_account_summary", "dim_account", "product_id"),
        ("BAL", "raw_ultracs_account_summary", "fact_account_balance", "eod_balance"),
        ("UNCLEARED", "raw_ultracs_account_summary", "fact_account_balance", "uncleared_amount"),
        ("AVAILBAL", "raw_ultracs_account_summary", "fact_account_balance", "available_balance"),
    ]

    for source_column, source_table, target_table, target_column in column_examples:
        source_node = f"{source_table}.{source_column}"
        target_node = f"{target_table}.{target_column}"
        _add_node(nodes, source_node, "column", table=source_table, column=source_column)
        _add_node(nodes, target_node, "column", table=target_table, column=target_column)
        _add_edge(edges, source_node, target_node, "maps_to", source_column=source_column, target_column=target_column)

    return GraphPayload(nodes=nodes, edges=edges)


def build_graph_from_lines(lines: List[str]) -> GraphPayload:
    """Minimal parser for a text export file. Intended for a future real mapping implementation."""
    graph = build_sample_graph()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if index == 0:
            graph.nodes.append(Node(id=f"row_{index}", label="raw_row", properties={"content": line[:120]}))
        else:
            graph.nodes.append(Node(id=f"row_{index}", label="raw_row", properties={"content": line[:120]}))
    return graph
