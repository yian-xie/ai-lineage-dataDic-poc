---
name: lineage-workflow
description: 'Use when downloading the four source repositories, parsing static metadata, building lineage graphs and column inventories, explaining a field, or creating the final combined graph and dictionary HTML. Run each step independently and keep its latest output under one output folder.'
---

# Lineage workflow

Read [README](../../../README.md) for the current structure and commands.
The [graph schema](./references/graph-schema.md) defines identities and edge
directions. [Confidence guidance](./references/confidence.md) keeps graph labels
separate from dictionary operation and description assessments.

## Steps

1. `sources --clone`: download missing configured repositories or verify existing
   checkouts. Never pull, reset or overwrite local work automatically.
2. `parse`: read BASIC, HVR, Airflow, dbt and migrations as data, never as code
   to execute. Preserve parser results and exact source evidence.
3. `graphs`: assemble graph context from the saved parse.
4. `columns`: build column-lineage JSON from that parse and graph context.
5. Follow [the dictionary skill](../ultracs-data-dictionary-v3/SKILL.md) to
   generate the three baseline CSVs.
6. Follow [the AI enrichment skill](../ai-description-enrichment/SKILL.md)
   when missing Ultracs descriptions need authoring and evidence assessment.
7. Validate preservation, then run `html` to produce one report with both the
   lineage graph and data dictionary.

Every step saves its latest files under `output` and appends diagnostics under
`output\logs`. A rerun replaces only that step's results; it must not silently
run earlier steps. Use explicit input paths and reject stale or failed inputs.

## Read-only questions

Use `query --graph GRAPH_JSON --search TEXT`, `--node ID`, `--trace ID`,
`--path FROM_ID TO_ID`, or `--columns INVENTORY_JSON --column SELECTOR`.
Default to one requested field, retaining every matching target. Do not rebuild
the entire source inventory for a normal lookup.

Explain stored versus semantic direction: READS_FROM and DEPENDS_ON point
toward dependencies and are reversed for source-to-consumer traversal. Respect
explicit boundary nodes and state missing bridges rather than inventing edges.
Keep direct HVR landing separate from the S3/Airflow route unless evidence joins
them. Enterprise table dependencies are not automatically column mappings.

Preserve exact expressions, source paths, confidence, source/extract positions,
target types and unresolved physical bindings. A JSON inventory is a mapping
array, not a nodes/edges graph, and one mapping can have several targets.
Static repository evidence never establishes production execution or approval.
