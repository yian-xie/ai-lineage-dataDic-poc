# Graph Merge Protocol

`merge_graphs.py` merges two JSON graph documents without modifying either input. It uses the lineage schema's canonical node `id` and edge `source`, `target`, and `type` fields. For edges it also accepts the equivalent keys `source_key`, `target_key`, and `edge_type`, then normalizes them to the canonical output names.

## Rules

- A node appearing in only one input is included unchanged.
- Nodes with the same `id` and identical records are included once.
- If same-key node records differ, compare the number of keys in their `properties` objects. Keep the node with more properties and log both records and the winner in `output/merge_conflicts.json`.
- If conflicting nodes have equal property counts, keep the record from the first input for deterministic output and log the tie for review.
- An edge's merge key is `(source, target, type)`, equivalent to `(source_key, target_key, edge_type)`. Unique edges are added.
- For duplicate edges with different confidence, keep the higher-ranked confidence and log the conflict. The rank is `explicit` > `confirmed`/`confirmed_calculated` > `inferred` > `declared_reference`/`candidate_composite_key` > `unspecified` or unknown. If ranks tie, including two unrecognized confidence strings, keep the first input and log the conflict.
- If duplicate edges have the same confidence but other record properties differ, keep the first input and log the conflict; the protocol does not silently discard metadata differences.
- For top-level metadata outside `nodes` and `edges`, identical values are preserved, list values are stably unioned, and differing non-list values keep the first input and are logged.
- Merged edges must have both endpoint node IDs in the merged graph. A dangling endpoint is rejected with an error instead of emitting an invalid graph.
- Conflicts include the key, input labels, resolution, and left/right/winner records. Input strings are copied only as inert JSON data; they are never interpreted or executed.

## Command

From the workspace root:

```powershell
python data-lineage-poc/merge_graphs.py data-lineage-poc/output/account_table_lineage.json data-lineage-poc/output/account_enterprise_lineage.json
```

This writes `data-lineage-poc/output/merged_lineage.json` and always writes the conflict report to `data-lineage-poc/output/merge_conflicts.json`, including `{"conflicts": []}` when there are no conflicts. Choose a different merged graph path with `--output`:

```powershell
python data-lineage-poc/merge_graphs.py graph-a.json graph-b.json --output output/combined.json
```

Inputs must be JSON objects with `nodes` and `edges` arrays. Nodes require a non-empty string `id`; edges require endpoint keys and an edge type using either the schema names or the equivalent `*_key` names.