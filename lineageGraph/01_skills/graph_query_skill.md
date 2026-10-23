# Generated Graph Query Skill

## Goal

Use the repository's generated lineage JSON through `query_graph.py` to find nodes, inspect relationships, trace semantic lineage, find shortest downstream paths, and look up column mappings. The tool emits JSON so results can be reused or inspected without changing the source graph.

## Inputs

- Default graph: `data-lineage-poc/output/account_table_lineage.json`.
- Other graph payloads: pass `--graph data-lineage-poc/output/table_lineage.json` or another generated graph JSON path.
- Default column mapping records: `data-lineage-poc/output/column_lineage.json`; override with `--columns PATH`.
- Run commands from the workspace root with Python 3.10 or later. The query tool uses only the Python standard library.

## Commands

```powershell
# Search node IDs, types, properties, edge types and evidence
python data-lineage-poc/query_graph.py --search "ACCOUNT"

# Inspect one node and its incident edges
python data-lineage-poc/query_graph.py --node "basic:file:ACCOUNT"

# Trace semantic data flow, with edge confidence and direction notes on every hop
python data-lineage-poc/query_graph.py --trace "basic:file:ACCOUNT" --direction downstream --depth 6
python data-lineage-poc/query_graph.py --trace "snowflake:relation:PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL" --direction upstream --depth 6

# Find the shortest semantic downstream path between exact node IDs
python data-lineage-poc/query_graph.py --path "airflow:task:accounts_v1_ingestion_v1:copy_s3_files_to_snowflake_task_for_dwacc" "snowflake:relation:RAW.ACCOUNTS_V1__ACCOUNTS"

# Look up column records by HVR parameter, Snowflake column, field ID or business-field label
python data-lineage-poc/query_graph.py --column "AltAccountName"
python data-lineage-poc/query_graph.py --column "Alternative Account Name"

# Use a different graph or limit a broad search result
python data-lineage-poc/query_graph.py --graph data-lineage-poc/output/table_lineage.json --search "accounts_v1" --limit 25
```

Choose exactly one query action: `--search`, `--node`, `--trace`, `--path`, or `--column`. Results are JSON on stdout; input and validation errors are JSON on stderr with a nonzero exit status.

## Named Query Functions

For Python callers, run from `data-lineage-poc/` and import the named helpers:

```python
from query_tools.tools import get_alias_chain, get_consumers, get_field_lineage

field_path = get_field_lineage("Account")
extract_consumers = get_consumers("DWACC")
aliases = get_alias_chain("Account")
```

These return dictionaries with `nodes`, `edges`, `confidence`, and per-path details. `get_field_lineage` also returns matching column mapping records separately from graph paths; when a dbt target has no explicit graph bridge, it reports that gap instead of inventing an edge.

## Interpretation Rules

- `--trace` and `--path` use semantic data-flow direction. `READS_FROM` and `DEPENDS_ON` are reversed relative to their stored edge direction; each hop reports `traversal` as `stored` or `reversed`.
- `--node` preserves stored edge direction and also reports the semantic flow direction for each incident edge.
- A node with `properties.is_boundary_node=true` terminates traversal. A missing boundary flag is not a boundary.
- A path query returns the shortest directed semantic path, not every possible route. Run separate traces when a source has multiple branches.
- Keep direct HVR-to-Snowflake and S3/Airflow routes separate unless an explicit graph edge connects them. Do not invent bridges across missing evidence.
- Report each hop's confidence. Missing confidence is `unspecified`; `inferred` is not confirmed and its recorded edge properties should be included in the explanation.
- Graph traversal finds table-level relationships. For source-to-target column evidence, run `--column` and report each target projection independently; do not claim a graph edge proves column-level lineage.
- The tool reads generated snapshots only. It does not query live HVR, Airflow, dbt, or Snowflake state.

## Error Handling

- If an exact node ID is unknown, run `--search` to discover the generated IDs; do not guess an ID from a label.
- If a query returns no path, report that no path is represented in this graph rather than inferring a connection.
- If a column selector returns multiple records, retain all matching target records and their distinct evidence.
- If input JSON is malformed or lacks the graph schema, stop and report the validation error; do not silently repair the graph.
