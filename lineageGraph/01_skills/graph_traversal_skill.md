# Graph Traversal Skill

## Goal

Answer lineage questions by traversing `output/account_table_lineage.json` and `output/column_lineage.json`.
Use the executable query workflow in [graph_query_skill.md](graph_query_skill.md) to discover nodes, inspect edges, and produce semantic traces before explaining the result.

## Traversal Rules

- Forward traversal (source to consumer): follow edges in stored direction except `READS_FROM` and `DEPENDS_ON`, which must be reversed.
- Backward traversal (consumer to source): reverse all edges.
- Never cross nodes with `is_boundary_node=true`; lineage stops at those nodes. A missing flag is not equivalent to `true`.
- Never join the direct HVR route and the S3 route. They are separate branches unless explicit configuration/runtime evidence links them.
- Always report confidence on every hop. If an edge or association has no confidence property, report it as `unspecified` rather than silently treating it as confirmed.
- Flag every hop where `confidence=inferred` and include the recorded reason/evidence.
- Show each hop as node key, edge type, and next node key. Preserve the stored relationship direction and mark any reverse traversal explicitly.
- If a traversal terminates at an intermediate relation because the graph lacks a bridge, report the gap; do not invent a connection.

## Standard Queries

### Q1 — Where does this Ultracs field end up in Snowflake?

Traverse conceptually from `MV_FILE` → `PROGRAM` → `EXTRACT_FILE` → HVR route → `SNOWFLAKE_RELATION`. Reverse `READS_FROM` for `MV_FILE` → `PROGRAM`. Follow the direct HVR branch or the S3/Airflow branch independently. If the request is column-specific, join the path to the matching record in `column_lineage.json` and report its confidence.

### Q2 — What Ultracs fields feed this Snowflake table?

Traverse backward from `SNOWFLAKE_RELATION`: reverse `LOADS_TO`, reverse applicable Airflow `COPIES_TO`/`COPIES_FROM` movement, follow HVR and extract relationships, then reverse `WRITES_TO` to reach `PROGRAM` and reverse `READS_FROM` to reach `MV_FILE`. Join to `column_lineage.json` for field positions and names. Do not cross route boundaries without evidence.

### Q3 — What breaks if this extract file changes?

Find the `EXTRACT_FILE` node and follow all applicable relationships in semantic forward data-flow direction. Account for stored edge orientation (`READS_FROM` and `DEPENDS_ON` are reversed for forward traversal). List each reachable `SNOWFLAKE_RELATION`, downstream model, and public output; identify any broken/missing bridge and inferred hop.