# CLAUDE.md — Data Lineage POC Replication Guide

This guide documents the repeatable workflow used to build the repository-static Ultracs → HVR → Snowflake → CDP lineage artifacts, including the accounts-v1 pilot, the separate Enterprise extension, and evidence-backed column outputs. It is intended for engineers and agents reproducing or extending the work.

## Workspace and Scope

Run commands from the workspace root unless a command explicitly changes directory. Expected sibling repositories:

- `kb-ultracs-datawarehouse` — extensionless BASIC programs and MultiValue file references.
- `kb-cdp-hvr` — channel exports and HVR `.param` files.
- `kb-cdp-tenant-account` — accounts-v1 ingestion DAG, dbt project, and schemachange scripts.
- `kb-cdp-tenant-enterprise` — Enterprise dbt projects, DAGs, and migrations.
- `data-lineage-poc` — parser adapters, schema, generators, reports, and output graphs.

This POC reads committed source/configuration files only. It does not connect to HVR, Airflow, Snowflake, Neo4j, or Neptune at runtime. Never put credentials or production customer rows in generated artifacts.

## Account Output Scope

The account slice is a logical domain scope, not just `DWACC` or `KWDW_ACC`. Account-related outputs are written by multiple Ultracs programs and feed separate account products. Use [the Runbook account-domain matrix](docs/RUNBOOK.md#account-domain-scope) and regenerate `output/extract_file_inventory.md` plus `output/extract_to_hvr_map.md` when checking coverage.

Column inventories now cover nine selected parameterized account outputs: DWACC (95), DWREL (15), DWDBUST (19), DWTDS (42), DWACFEE (19), DWSWEEP (7), ACCREC_* (5), DWNOMACC (10), and DWUNCLD (10). This is 222 feed-field positions and 207 distinct `.param` labels case-insensitively, not 222 unique business concepts or the entire universe of account-adjacent outputs. Across the inventories, 215 positions reach an internal dbt target, 129 reach a public target, and the field mappings fan out to 409 dbt target projections. BASIC-to-`.param` pairings in the new feeds are ordinal and marked inferred. `ACCREC_*`, `DWNOMACC`, and `DWUNCLD` still need their Landing Tenancy handoffs verified. Do not claim a feed is end-to-end from a BASIC writer, HVR capture, or dbt raw source alone; cite every hop and keep unverified outputs as candidates.

## Authoritative Schema

Before changing a parser or graph, read `src/lineage/data_lineage_schema.md`. It is the source of truth for entity and relationship types. Important rules:

- The source-ingest foundation is `PROGRAM`, `MV_FILE`, `EXTRACT_FILE`, and compatibility `SNOWFLAKE_TABLE`.
- Canonical physical relations use `SNOWFLAKE_RELATION` with `kind`, `layer`, and `creation_mechanism`.
- Other entities include `HVR_CHANNEL`, `HVR_LOCATION`, `S3_PATH`, `CDP_PRODUCT`, `AIRFLOW_DAG`, `AIRFLOW_TASK`, `DBT_SOURCE`, `DBT_MODEL`, and `SCHEMACHANGE_MIGRATION`.
- Preserve `source_path` on graph objects and confidence/evidence on inferred associations.
- Ultracs BASIC files are mostly extensionless. Record their actual repository path/name; never append `.b`.
- Keep `DBT_SOURCE` separate from physical relations (`RESOLVES_TO`) and `DBT_MODEL` separate from materialized relations (`MATERIALIZES_AS`).
- Do not infer view/table kind from `public`/`internal`; use configured dbt materialization.
- Keep the direct HVR-to-Snowflake route separate from HVR S3 → Datalake S3 → Airflow RAW ingestion unless evidence connects them.

## Parser and Generator Inventory

Parser adapters live under `src/lineage/parsers/`:

- `basic.py`: wraps the existing Ultracs BASIC structural parser and emits `PROGRAM`, `MV_FILE`, `EXTRACT_FILE`, `READS_FROM`, and `WRITES_TO`.
- `hvr.py`: parses HVR channel exports and `.param` files. Channel output enters lineage; `.param` definitions are exported separately as auxiliary metadata.
- `airflow.py`: statically reads DAG task/file-table declarations without importing or executing the DAG.
- `dbt.py`: reads dbt YAML declarations and SQL `source()`/`ref()` calls. YAML trailing tabs are tolerated; repository files are not rewritten.
- `schemachange.py`: extracts relation DDL as `MIGRATES` edges with `CREATE`/`ALTER` operation metadata.

The parsers are evidence extractors, not language runtimes. Do not expand claims beyond the declarations they actually read.

## Reproduction Workflow

### Focused one-column request (default)

When the user provides one DWACC column selector, do not start with the full parser build. Use the published inventory and base account graph; the focused generator reads them in Python and writes small selected outputs, so the agent does not need to load the full 95-record DWACC inventory into conversation context. This fast path is DWACC-specific; DWREL has a separate inventory, and other account output families require their own column mapping before using a focused workflow.

The minimum generated inputs are:

- `output/column_lineage.json` — all 95 ordered DWACC fields and DBT targets.
- `output/account_table_lineage.json` — base account table graph and field context.
- `output/account_enterprise_lineage.json` — table-level Enterprise context required by the HTML generator.

Also follow `skills/column_lineage_skill.md`. If a data-dictionary entry is requested, follow `skills/dataDic/skill/data_dictionary_skill.md` and inspect only the selected record's cited YAML/SQL/BASIC files. In a workspace session, refer to these paths; do not attach/paste their full contents.

Run:

```powershell
python data-lineage-poc/generate_account_number_lineage.py --column SELECTOR
```

Selectors may be a `.param` name, Snowflake column, `field_id`, or business-field name. `Account_Index_ID` returns both inferred components. Review only the focused `output/<field>_lineage.json` and explanation, report the exact hops/confidence/source paths/open questions, and provide the generated HTML path. Do not regenerate full graphs or print the all-column JSON unless an input is missing, the user reports source changes, validation shows stale outputs, or a rebuild is explicitly requested. If the selector has no evidence-backed mapping, say so; do not derive a replacement mapping by guessing.

Reusable prompt:

```text
Column: <one selector>
Follow data-lineage-poc/skills/column_lineage_skill.md. If a dictionary entry is requested, also follow data-lineage-poc/skills/dataDic/skill/data_dictionary_skill.md. Use the existing output/column_lineage.json and output/account_table_lineage.json as the lineage base, with output/account_enterprise_lineage.json only as table-level context. Run generate_account_number_lineage.py --column <selector>; inspect only the focused outputs and cited source files. Do not load or return the full inventory and do not rebuild parser graphs unless inputs are missing/stale or I explicitly request regeneration. Return the focused JSON/HTML/explanation paths, verified hops, confidence, evidence paths, and open questions. Never invent missing mappings or dictionary values.
```

### Full regeneration

Run these from the workspace root, in order, only when rebuilding all outputs:

```powershell
python data-lineage-poc/generate_extract_file_inventory.py
python data-lineage-poc/generate_extract_to_hvr_map.py
python data-lineage-poc/export_hvr_param_metadata.py
python data-lineage-poc/generate_full_parser_lineage.py
python data-lineage-poc/generate_account_table_lineage.py
python data-lineage-poc/generate_account_enterprise_lineage.py
python data-lineage-poc/generate_account_lineage_html.py
python data-lineage-poc/generate_account_enterprise_html.py
python data-lineage-poc/generate_table_lineage_html.py
python data-lineage-poc/generate_column_lineage.py
python data-lineage-poc/generate_account_number_lineage.py --column KiwiAcc
python data-lineage-poc/generate_dwrel_column_lineage.py
python data-lineage-poc/generate_account_output_column_lineage.py
python -m pytest data-lineage-poc/tests -q
```

Regenerate each HTML view after its corresponding JSON graph. Keep `output/` as the canonical generated artifact directory; do not maintain duplicate `docs/output/` or top-level `build files/` mirrors. To publish current reports and viewers, run `python data-lineage-poc/generate_report_site.py` after generation and tests pass.

Only run the full sequence below for clean builds or explicit refresh requests. For ordinary one-column requests use the focused workflow above. Generate multiple focused outputs only when a batch is explicitly requested; use a distinct `--output-prefix` for each selector.

The full-graph generator processes BASIC inputs, HVR JSON channel exports, the accounts-v1 ingestion DAG, the accounts-v1 dbt project, and its schemachange scripts. It excludes the brace-formatted HVR channel template (not a JSON export) and skips BASIC candidates without recognized parser evidence. It merges nodes by canonical identity, preserves distinct BASIC programs/extracts by source path, and rejects dangling edges.

The `.param` export is auxiliary metadata only. Do not merge `hvr_param_metadata.json` into table-level graph `nodes` or `edges`.

## Output Artifacts

| Artifact | Purpose |
| --- | --- |
| `output/table_lineage.json` | Full repository-static graph from the five parser stages. |
| `output/extract_file_inventory.md` | BASIC output-file discovery across the scanned Ultracs programs. |
| `output/extract_to_hvr_map.md` | Static matching of discovered outputs to checked-in HVR capture patterns. |
| `output/hvr_param_metadata.json` | Auxiliary HVR DWACC parameter-column metadata; not part of lineage graph. |
| `output/account_column_inventory_summary.json` | Counts and coverage status across the nine currently scoped account output inventories. |
| `output/*_column_lineage.json` candidate files | Separate field inventories for DWDBUST, DWTDS, DWACFEE, DWSWEEP, ACCREC_*, DWNOMACC, and DWUNCLD. |
| `output/account_table_lineage.json` | Focused DWACC/account table slice with its `gap_register`. |
| `output/account_table_lineage.html` | Interactive focused account graph with node/edge descriptions and provenance tags. |
| `output/account_enterprise_lineage.json` | Separate interim extension from account public relations through selected Enterprise dbt products. |
| `output/account_enterprise_lineage.html` | Interactive viewer for the interim Enterprise extension. |
| `output/table_lineage.html` | Interactive full table-level graph. |
| `output/column_lineage.json` | Evidence-backed column mappings, kept separate from table lineage. |
| `output/column_lineage.html` | Combined interactive table graph and column overlays. |
| `output/column_lineage_dictionary.html` | V3 Data Dictionary, Asset Registry and Field Catalog loaded by the graph page; keep alongside `column_lineage.html`. |
| `output/account_number_lineage.json` | Single-field KiwiAcc/Account Number mapping. |
| `output/account_number_lineage.html` | Focused Account Number graph plus human-readable flow section. |
| `output/account_number_lineage_explanation.md` | Cited end-to-end explanation for Account Number. |
| `html_graph_descriptions.py` | Adds display-only repository/generated descriptions to a deep-copied graph payload before HTML embedding. |
| `output/repo_understanding.md` | Account-slice summary, confidence notes, and open gaps. |
| `output/senior_developer_questions.txt` | Questions to resolve with domain owners, each with rationale. |

Generated node/edge totals may change when repository contents change. Treat the current JSON as a snapshot, and regenerate through the scripts rather than editing generated files by hand.

## Account Slice and Enterprise Extension

The current `account_table_lineage.json` is specifically the DWACC account-master sub-slice: `KWDW_ACC` reads `ACCOUNT` and `TRAN`, writes `DWACC`, and the account tenant maps `dwacc` to `ACCOUNTS_V1__ACCOUNTS`. It attaches all 95 DWACC parameter positions, BASIC expressions, and evidenced internal/public dbt targets. This is not the complete account-output scope. DWREL has its own 15-column inferred inventory. The new candidate generator covers DWDBUST, DWTDS, DWACFEE, DWSWEEP, ACCREC_*, DWNOMACC, and DWUNCLD; see the Runbook matrix and `account_column_inventory_summary.json` for exact key matches and route status. Three candidate feeds still have unresolved Landing Tenancy handoffs. Keep `Account_Index_ID`'s `Account` and `Prod` components inferred until confirmed; retain the six `MissingColumn` slots by their declared names and do not invent business labels.

The Enterprise extension reuses the dbt and schemachange parsers on selected products in `kb-cdp-tenant-enterprise`. Enterprise DBT source declarations are matched to physical account public relations by normalized schema/table name; Jinja database expressions remain metadata and are not resolved against a live environment. The schema overview follows connected Enterprise models at table level only; do not imply column-level mappings or datatypes unless parser evidence supports them. The extension is interim/static, not proof of deployed runtime execution. A missing DAG must remain missing; never synthesize orchestration edges.

## Column Lineage Rules

- For the existing DWACC inventory, start from the ordered `columns` array in `output/hvr_param_metadata.json`; position is one-based according to DWACC parameter order. Never use DWACC positions or parameter names for another output family.
- Match each of the 95 ordered `.param` fields to its BASIC output expression and DBT `DATA:` projections. Record all supported internal/public targets; do not infer a public target where the public model does not select that field. Preserve the two `Account_Index_ID` components as inferred.
- Treat each account output (`DWREL`, `DWDBUST`, `DWTDS`, `DWACFEE`, and others) as a separate field-mapping problem. Confirm the BASIC record construction, matching HVR `.param` order, ingestion/raw source, and dbt projections independently; retain inferred status when positional alignment is the only evidence.
- For the generated candidate inventories, do not link `.param` names to dbt keys by case-insensitive or semantic similarity. In particular, keep DWTDS `Prod` distinct from `Product`, DWTDS `col40` unmapped, and DWNOMACC `RefDate` distinct from `ReferenceDate` unless new source evidence resolves these differences.
- For a focused lineage request, process one requested column by default. The all-column `column_lineage.json` is a reusable evidence-backed inventory, not a requirement to present multiple columns in each response or focused output.
- Do not call an HVR `.param` name a physical Snowflake column unless that physical column is explicitly evidenced. HVR direct `ult_sf_acc` defines only `payload` and `integration_timestamp`; the named `KiwiAcc` field is traced through the named-column Parquet/S3 route and account dbt models.
- Store `source_path` on each mapping and include caveats/evidence in `notes`.
- Do not merge column records into table graph files. The HTML renderer combines table-level and column-level payloads for display; Enterprise extensions remain explicitly table-level where column mapping evidence is unavailable.
- `generate_account_number_lineage.py --column SELECTOR` creates a separate focused JSON/HTML/explanation set for a mapped `.param` name, Snowflake column name, `field_id`, or business-field name. Without `--column`, it defaults to `KiwiAcc` and preserves the `account_number_lineage.*` filenames.
- `--column Account_Index_ID` emits both inferred component records (`Account` and `Prod`). This selector only chooses mappings already present in `column_lineage.json`; it does not invent lineage for the other `.param` names.

## Confidence Percentages

HTML graph views show a heuristic evidence-strength percentage alongside the original confidence category. Keep the rubric consistent: `explicit`/`confirmed` 95%, `confirmed_calculated` 90%, `declared_source` 85%, `inferred` 60%, and `unconfirmed` 50%. Unknown or unresolved values are `Not rated`. These are not statistical probabilities, runtime success rates, or guarantees; preserve the evidence category and provenance, and keep the disclaimer visible in generated HTML.

Graph viewers provide visible relationship-confidence checkboxes for Explicit/confirmed, Calculated, Declared source, Inferred/candidate, Unconfirmed, and Not rated. All are checked by default; users can combine categories. Filtering hides nonmatching relationships but retains endpoint nodes as context. Verify multiple selections in Detailed and Schema overview modes and confirm Reset checks all levels.

## HTML Descriptions and Data Dictionary Handoff

Every node and relationship shown in an HTML graph needs a description and an origin tag in Detailed and Schema overview modes. Use `html_graph_descriptions.py` to enrich a deep copy immediately before HTML embedding; do not add generated UI prose to the canonical graph JSON. Prefer checked-in node descriptions (BASIC/HVR/dbt/source/migration/mapping metadata) and relationship `description`/`evidence` properties. Tag these `Repository sourced` or `Repository evidence`. If repository text is absent, generate one concise literal description from entity type/name or relationship type/endpoints and tag it `Generated`.

Generated descriptions describe only the graph object's role or the encoded edge direction. They are not evidence, do not claim undocumented business meaning, and must never be promoted as authoritative data-dictionary definitions. Preserve the description-origin tag through every renderer. A future Data Dictionary Builder should use repository-sourced descriptions as candidate definitions, treat generated descriptions as navigation aids, and cite each definition's repository-relative `source_path`.

The Data Dictionary tab is generated from the current account graph, column inventory, and Enterprise table-level extension. It is display-only metadata: do not add dictionary rows to graph nodes/edges. For a one-column request, reuse the current generated payloads and inspect only the focused record and its source files; regenerate the full JSON graphs before HTML only when the full-build conditions above apply. Enterprise continuations remain table-level without column evidence.

The HTML-only description helper tags checked-in node descriptions `Repository sourced`, relationship descriptions/evidence `Repository evidence`, and fallback role/direction text `Generated`. Generated text helps readers navigate the graph but is not evidence and must not become an authoritative dictionary definition. A future dictionary entry should cite source paths and preserve this distinction; use dbt column YAML for actual descriptions and datatypes.

## Traversal Semantics and Known Gaps

For conceptual source-to-consumer traversal, reverse stored `READS_FROM` (`PROGRAM` → `MV_FILE`) and `DEPENDS_ON` (`DBT_MODEL` → dependency). Otherwise follow stored edge direction. Always print each hop’s node key, edge type, direction, and confidence.

Preserve the three account gap-register entries:

1. Starting at `MV_FILE ACCOUNT`, a literal outgoing-edge walk stops because `READS_FROM` points into the file.
2. Direct HVR `ult_sf_acc` ends at `LOADACCOUNTS_INGEST`; do not join it to the accounts-v1 RAW route without new evidence.
3. dbt model dependencies reach public models, but physical relation nodes do not form a continuous relation-only chain across model boundaries.

These are known graph boundaries, not permission to invent edges. If new configuration/runtime evidence resolves one, cite the evidence and update the gap register and graph generator together.

## Validation Checklist

- Parse each output with a JSON parser.
- Check node types and edge types against `data_lineage_schema.md`.
- Check every edge endpoint exists and node IDs are unique.
- Check provenance (`source_path`) and confidence are present where applicable.
- For every HTML node and relationship, check non-empty `html_description` plus `html_description_origin`; confirm generated text is tagged `Generated` and never mutates canonical JSON.
- Check direct and S3 routes remain distinct.
- Check column mappings point to existing relation IDs and parameter positions match the ordered `.param` columns.
- Run `python -m pytest data-lineage-poc/tests -q` after code or generator changes.
- Open regenerated HTML locally and test search, route/layer/confidence filters, node movement, zoom/pan, and inspector details.
- Test each relationship-confidence option in Detailed and Schema overview modes, inspect a filtered node's remaining relationships, and verify Reset restores the unfiltered graph.
