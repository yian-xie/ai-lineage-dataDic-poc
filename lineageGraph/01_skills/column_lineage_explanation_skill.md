# Column Lineage Explanation Skill

## Goal

Create a readable, evidence-backed explanation of one requested column's end-to-end lineage across the repositories, and make the same explanation visible in its focused HTML graph. Default to one selected field; only process multiple fields when explicitly asked. This skill is for both the GitHub Copilot agent and the future Data Dictionary Builder agent.

## Inputs Required

- The focused column record from `output/column_lineage.json` (or a one-column file such as `output/account_number_lineage.json`).
- `output/account_table_lineage.json` for structural and route context.
- `output/hvr_param_metadata.json` for exact HVR `.param` names and positions.
- The relevant Ultracs BASIC, HVR configuration, Airflow, and dbt source/model files cited by the graph.
- `src/lineage/data_lineage_schema.md` as the authoritative graph contract.
- The focused HTML generator/output for the field being explained.

## Steps

1. Select a mapped record with `python data-lineage-poc/generate_account_number_lineage.py --column SELECTOR`. Selectors can be `.param` name, Snowflake column, `field_id`, or business-field name. The default is `KiwiAcc`; `Account_Index_ID` resolves to both inferred component records.
2. Identify the selected field and its exact `.param` column/position from the column-lineage record and metadata file.
3. Verify the source position and output/extract evidence in the actual BASIC program. Preserve the repository filename exactly; do not append `.b` to extensionless programs.
4. Trace each configured HVR branch independently. Verify channel capture patterns, source/target locations, conversion or S3 path evidence, and relation targets. Mark pattern-based associations inferred.
5. For an S3 route, continue through the Airflow copy/load task and its RAW relation, then follow dbt `source()` and `ref()` declarations to physical internal/public relations.
6. For a direct HVR route, report only the configured target relation. Do not join it to a separate S3/Airflow route or claim a field-level Snowflake column if HVR only lands a row payload.
7. Write a concise Markdown explanation listing each hop, relationship, confidence, evidence path, and any unresolved boundary.
8. Add the same summary to the focused HTML as a visible end-to-end flow section. Keep the interactive graph and node inspector available below it.
9. For every displayed node and relationship, show a concise description and an origin tag. Cite repository text with its `source_path`; tag generic fallback prose `Generated` and do not treat it as evidence or a dictionary definition.

## Required Outputs

- `output/<field>_lineage_explanation.md`
- Update/regenerate `output/<field>_lineage.html` with an end-to-end flow section, unless the requester explicitly asks for a separate companion HTML.

The selector only operates on existing evidence-backed records in `column_lineage.json`; unmapped parameter names require more source/model evidence before a lineage output can be claimed.

## Rules

- Cite repository files for every asserted mapping or route.
- Distinguish HVR `.param` column names from actual physical Snowflake columns. A named parameter alone does not prove that a corresponding physical Snowflake column exists.
- Show confidence on every nontrivial mapping/hop. Use `inferred` where the relation is based on a filename-pattern match or a proposed composite key, and explain why.
- Preserve the HTML confidence percentage and its original category. The percentage is a heuristic evidence-strength score, not probability.
- Keep Enterprise downstream context at table level unless Enterprise SQL/YAML establishes column-level lineage. Do not copy table descriptions onto columns.
- Keep direct HVR and HVR S3/Airflow branches separate unless repository/runtime evidence connects them.
- Preserve the column JSON payload and table graph as separate outputs; do not mutate them merely to add narrative.
- Explain limits where edges point against data-flow direction or where model dependencies do not provide a physical-relation bridge.