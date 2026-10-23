# JSON Payload Skill

## Goal

Produce `output/column_lineage.json` as a JSON array. Each array item represents one field mapping and must follow this structure:

```json
[
  {
    "field_id": "ultracs:SAVINGS_ACCOUNT:DWACC:54",
    "ultracs_position": 54,
    "ultracs_program": "kb-ultracs-datawarehouse/KWDW_ACC",
    "extract_file": "DWACC",
    "param_column": "OpenDate",
    "snowflake_table": "snowflake:relation:RAW.ACCOUNTS_V1__ACCOUNTS",
    "snowflake_column": "ACCOUNTOPENDATE",
    "confidence": "confirmed",
    "source_path": "kb-cdp-hvr/hvr-config/scripts/DWACC.param",
    "notes": "Include supporting evidence or caveats."
  }
]
```

## Field Requirements

- `field_id`: stable identifier following `ultracs:SAVINGS_ACCOUNT:DWACC:[position]`.
- `ultracs_position`: integer source/extract position.
- `ultracs_program`: actual repository-relative program filename/path. Most Ultracs programs are extensionless; do not append `.b`.
- `extract_file`: extract name, without a fabricated extension.
- `param_column`: exact column name from the `.param` metadata.
- `snowflake_table`: canonical `SNOWFLAKE_RELATION` node key from table lineage.
- `snowflake_column`: exact physical column name, and only assert existence when supported by the `.param` declaration as required by the column-lineage skill.
- `confidence`: `confirmed` or `inferred`, selected using the evidence requirements in [confidence_score_skill.md](confidence_score_skill.md). Store the raw label and put its heuristic display percentage in this field or add a percentage property to this payload.
- `source_path`: repository-relative path to the file that defines the mapping.
- `notes`: caveats, evidence, transformations, or composite-key explanation.
- `ultracs.description` and `cdp.description`: repository-backed source/target column text when available; do not fabricate these descriptions from the column name.

## Rules

- Output valid JSON only: no comments, trailing commas, or Markdown fences.
- For a new table/process graph payload, start from [lineage_graph_payload_template.json](../examples/lineage_graph_payload_template.json) and replace every placeholder with repository-backed values. Use only entity and relationship types from the [authoritative graph schema](../src/lineage/data_lineage_schema.md); keep `source_path` and confidence evidence on nodes/edges. The template is a graph-object skeleton, not a column mapping payload.
- Keep column-level mappings as a separate JSON array using the record structure above; do not change them into a `{nodes, edges}` graph object. Apply [confidence_score_skill.md](confidence_score_skill.md) to the raw `confidence` label.
- Keep this payload separate from `account_table_lineage.json` and `table_lineage.json`.
- Keep HTML-only `html_description` and `html_description_origin` fields out of canonical graph JSON and this mapping inventory. The HTML helper enriches a deep copy for display only.
- Apply the [confidence scoring skill](confidence_score_skill.md) when evaluating evidence. Its `runtime_verified` 100% level is reserved for independently verified runtime/catalog evidence and must not be assigned from static repository files or a clean parser/test run.
- Use `null` only when the consumer explicitly permits an unknown value; otherwise omit unsupported mappings rather than guessing.
- `Account_Index_ID` is inferred as `Account` + `Prod` at positions 1 and 2 and must state this in `notes`.