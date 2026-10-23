# Column Lineage Skill

## Goal

For a normal request, trace one explicitly selected account DWACC field using the prebuilt 95-field inventory, account graph, and Enterprise context. Generate only that field's JSON/HTML/explanation outputs. Do not load, print, or regenerate the complete inventory unless the user requests a batch or source refresh.

## Inputs Required

- `output/column_lineage.json` — prebuilt 95-field inventory with BASIC expressions and internal/public DBT target projections.
- `output/account_table_lineage.json` — account table graph and `DWACC.related_columns` base.
- `output/account_enterprise_lineage.json` — downstream Enterprise context used by the HTML generator; table-level only unless column evidence exists.
- `output/hvr_param_metadata.json` — optional position/name cross-check; not required by the focused generator when the other generated outputs are current.
- `src/lineage/data_lineage_schema.md` — authoritative schema.
- The relevant Ultracs BASIC source and extract inventory when source positions or output fields are not present in the two JSON inputs.

## Default One-Column Workflow

1. Accept one selector: `.param` name, Snowflake column, `field_id`, or business-field name. Stop for ambiguity. `Account_Index_ID` intentionally returns its two inferred components (`Account` and `Prod`).
2. Check that `output/column_lineage.json`, `output/account_table_lineage.json`, and `output/account_enterprise_lineage.json` exist. Record that these are the snapshot used; do not rebuild if the user has not reported source changes and the artifacts are present.
3. Run `python data-lineage-poc/generate_account_number_lineage.py --column SELECTOR`. This script filters the full inventory outside model context and writes focused JSON, HTML, and explanation files. Do not read or paste the full `column_lineage.json` into the conversation.
4. Inspect only the focused JSON and explanation. Confirm the position, BASIC expression, `.param` name, every target stage/relation/column, confidence, and source paths.
5. Open only the cited BASIC, HVR, Airflow, SQL, or YAML files needed to verify the selected field or requested data-dictionary facts. Never crawl all 95 fields for a one-column question.
6. Preserve route boundaries and direction. The direct `ult_sf_acc` HVR route remains separate from the S3/Airflow/RAW route. Reverse `READS_FROM` and `DEPENDS_ON` only for conceptual source-to-consumer narration.
7. Return the focused JSON path, HTML path, a short verified hop summary, confidence/evidence, and open questions. Publish copies only if requested or required by the runbook workflow.

Run the full parser build only when an input/output is missing, the user reports repository source changes, validation reveals stale artifacts, or the user explicitly asks for regeneration. Follow the ordered full build in `docs/RUNBOOK.md`; do not rebuild the full graph for an ordinary selector request.

## Rules

- Keep the HVR `.param` field name distinct from the Snowflake column name. A Snowflake target is supported when account dbt SQL maps `DATA:<param_column>` to the target alias and the matching dbt YAML declares that target column. Do not require the target name to appear in `.param`; do not claim a target without the SQL/schema evidence.
- Mark `Account_Index_ID` as `confidence=inferred`; it is a candidate composite of `Account` + `Prod` at positions 1 and 2.
- Keep column-lineage output separate from table lineage. Do not merge the JSON files.
- Every record must have a `source_path` pointing to the file that defines the mapping. Use the actual repository path and filename; Ultracs BASIC files are mostly extensionless, so do not append `.b`.
- Preserve evidence and confidence. Do not connect separate HVR branches without configuration or runtime evidence.
- Prefer descriptions from BASIC comments, HVR config, dbt YAML, and checked-in mapping evidence. Keep their `source_path`.
- In HTML only, every node and relationship receives a description and origin tag. `Repository sourced`/`Repository evidence` means text exists in checked-in sources; `Generated` means a concise fallback was made for navigation. Generated descriptions are not new lineage evidence and must not be written into canonical graph JSON as authoritative business definitions.
- Keep the HTML confidence percentages as heuristic evidence-strength labels, not statistical probabilities. Preserve the original confidence category next to the percentage.
- In graph views, use the relationship-confidence checkboxes to combine or isolate categories without removing endpoint nodes needed as context. All are checked initially; test multiple selections in Detailed and Schema overview modes, then Reset to all.
- The current inventory aligns all 95 DWACC positions to BASIC expressions and internal DBT projections; only 59 reach a public model. Do not imply every parameter is a business-named/public field. `MissingColumn1`–`MissingColumn6` remain technical labels, and the `Account_Index_ID` composite remains inferred.