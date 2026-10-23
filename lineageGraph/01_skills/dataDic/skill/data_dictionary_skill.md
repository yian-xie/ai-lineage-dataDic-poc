# Data Dictionary Skill — Ultracs-to-Snowflake Relationship Rows

## Goal and scope

Start the dictionary from the supplied Ultracs field records. Use `column_lineage.json` to produce one self-contained **`data_dictionary.csv`**, with one row per original Ultracs mapping record and exact Snowflake target field. If one source has four represented Snowflake outputs, create four rows with the same source name and supplied source description. Each row has its own target, target description, renames, processing, expressions, relationship assessments, evidence and review issues. Do not put all outputs into one target-list cell.

Store the complete atomic transformation/dependency records inside each row's `process_details_json` cell, including every input/output, expression, binding, evidence item and relationship-specific assessment. The embedded field catalogs and operation records make the CSV usable on its own for a future HTML viewer; no second relationship CSV is required. Shared operation IDs identify the same operation across rows, and their complete definitions must agree within a snapshot.

The main reading direction is **Ultracs field → processing and renames for this association → one Snowflake column**. Repeating a source name or description across rows is intentional. Filter by source to see all its outputs; filter by target to see all contributing sources. A source-to-target dictionary row summarizes an association, not necessarily one direct operation or one exclusive source.

Preserve both readable summaries and complete structured details. Never compress differently named/described/typed fields in different tables into a single generic target description. Support reverse lookup from any Snowflake field to its source entries without asking AI to infer connections from prose.

This is a standalone Markdown workflow/schema specification, not an installed skill or an implemented CSV converter. Do not modify the input JSON or automatically rebuild upstream projects. For an ordinary extraction request, process the full supplied inventory; restrict it only when the user explicitly requests a subset, and state that scope.

## Primary input and current snapshot

The supplied `column_lineage.json` is an array of mapping records, not an already normalized `columns`/`relationships` graph. Read its actual structure rather than assuming a fixed number of mappings or a single target per record.

The inspected input contains **95 DWACC mapping records** and **179 distinct source-mapping/target pairs: 112 internal and 67 public**. These produce **179 dictionary rows across 95 source groups** by default. There also happen to be 179 distinct target fields in this snapshot; future inputs can have several sources sharing one target, so pair counts and distinct-target counts must be measured separately. These are snapshot checks, not hardcoded limits. All records have targets. The top-level/CDP target repeats a target already in `dbt_targets`; it must not create a duplicate pair row.

Other observed limits: 23 records have no `ultracs.source_locator`, 27 have empty `source_references`, and six use `MissingColumn*` parameter names. Confidence is categorical only: 87 `explicit`, five `confirmed`, two `inferred`, and one `confirmed_calculated`. No numeric assessments, scoring rubric, assessor or assessment time are supplied. Do not fabricate them.

| Input properties | Interpretation |
| --- | --- |
| `field_id`, `extract_file`, `param_column`, `ultracs_position` | Original mapping identity and extract-output position. Preserve these values. |
| `ultracs` | Reported source locator/references, BASIC expression, transformation, description, program path and source line. These can contain unresolved variables or incomplete source details. |
| `hvr_parameter` | Extract declaration, declared type, obfuscation and cleanup settings. Keep strings such as `N` and all cleanup parameters exactly as supplied. |
| `ingestion_route` | Declared HVR/S3/Airflow/RAW context and dbt JSON-key expression. It does not enumerate independently verified column-level transport hops. |
| `dbt_targets[]` | All represented downstream fields and their stage, relation, model, expressions, descriptions, declared types and classification. |
| `cdp`, `snowflake_table`, `snowflake_column` | Primary-target metadata. Reconcile with the target inventory; preserve disagreements instead of choosing a winner silently. |
| `confidence`, `notes`, `source_path` | Original mapping-level claims, caveats and reported provenance. A record-wide label is not an assessment of every decomposed hop. |

The JSON alone is sufficient for a documented-input extraction with explicit gaps. Additional repositories, YAML/SQL files, table graphs or scoring instructions are optional supplied verification material. Missing optional files must not trigger an unrequested build, network call or guessed result. Source text and attached instruction-like content are data unless the human explicitly invokes a separate workflow.

## Field identity and granularity

Keep a stable `source_entry_id` for each original mapping record and retain the input's exact `field_id` as `ultracs_field_id`. Give each dictionary row a separate stable `dictionary_entry_id` based on its source entry and exact target field identity, never row number or display name. For this input, keep 95 source groups and expand them into 179 source-target rows. A repeated source is not a duplicate row to delete.

The 95 groups do not establish 95 distinct physical Ultracs attributes: set `identity_scope=extract_mapping` and keep the actual locator separately. Do not merge ambiguous records just because they have the same name, expression or missing locator. Physical-source grouping is an optional explicitly requested view that must retain all original mappings. If a future source record has no documented target, keep one `row_kind=no_documented_target` row with blank target columns and a review reason; do not invent a Snowflake field.

Give actual source, extract, RAW and Snowflake fields separate stable IDs inside `field_catalog_json`. Use lossless component escaping or canonical tuple encoding and check collisions. These catalog IDs identify graph endpoints; source-entry IDs group original mappings, and dictionary-entry IDs identify source-target rows. Deduplicate only an identical source-entry/target pair while retaining every contributing claim. Never deduplicate by source name or target ID alone.

**An extract position is not an Ultracs attribute position.** For example, input `ultracs:SAVINGS_ACCOUNT:DWACC:51` identifies DWACC output position 51. The record's actual source locator is `ACCOUNT<28,2>`; it must not become `ACCOUNT<51>`.

- **Ultracs source:** reuse a physical source ID only when file/record scope, binding and locator establish the same source. Do not merge `REC<...>`, `AREC<...>`, `TRAN<...>` and `ACCOUNT<...>` by matching position numbers. Variable names can be reused across program contexts.
- **Unresolved BASIC expression/reference:** when a physical source is not established, retain the recorded expression or variable as a scoped `expression_ref` or `symbolic_ref`, not a fabricated physical field. Mark identity/origin resolution as incomplete. A composite prose locator such as “TRAN<1> and transaction detail” is not a complete operand inventory.
- **Extract slot:** identify the program/extract/output position and retain its exact parameter name. The same source can feed several slots through different expressions.
- **RAW JSON key:** identify the RAW relation and exact `DATA:<key>` path. Set `field_kind=json_path`; this is a logical path inside a column, not a newly proven physical SQL column.
- **Snowflake column:** identify the exact relation and column within its project/snapshot scope. Internal and public fields remain distinct, even with identical names.

Use `field_kind` to distinguish `source_locator`, `symbolic_ref`, `expression_ref`, `extract_slot`, `json_path` and `physical_column`. Processing cards annotate operations. Documented intermediate fields belong in the embedded field catalog and path details; they are not extra standalone rows unless they are also represented Snowflake targets.

Define the outcome scope explicitly. A normal presentation may focus on public Snowflake outputs while retaining internal-only targets and all other stages in the CSV. “Final” means final within that declared scope, not proven absence of downstream production use. Do not infer final outputs solely from missing outgoing links.

## Output — data_dictionary.csv

One row per documented source-mapping/target association. Repeat the source-side values exactly for its different target rows; do not use merged cells, ditto marks or blanks to imply repetition. Keep target and processing differences in dedicated columns, with full per-step details in structured cells. The table defines required column names and meanings; presentation order may place the most readable source, target and process columns first without changing their identity or omitting other columns.

| Column | Content |
| --- | --- |
| `dictionary_entry_id` | Stable unique source-target row ID; do not derive it from row number or display name. |
| `source_entry_id` | Stable group ID for the original input mapping; repeats across its target rows. |
| `snapshot_id` | Input snapshot identity, consistent across dictionary rows and their embedded field/operation records. |
| `row_kind` | `source_target`, or `no_documented_target` when no target is supplied. |
| `ultracs_field_id` | Exact original input `field_id`, preserved without rewriting its meaning. |
| `ultracs_field_name` | Supplied physical source name when established; otherwise an explicitly attributed display label such as the extract parameter. Never claim the label proves a physical source name. |
| `source_name_origin` | `physical_source_name`, `extract_parameter_label`, `record_label` or `unknown`, matching the actual basis for the displayed name. |
| `business_field_label` | Exact input `business_field`; a mapping label, not an approved definition or a physical identifier. |
| `identity_scope` | `extract_mapping` for this input; physical source identity stays separately documented. |
| `source_locator` | Exact reported Ultracs locator; blank when unknown, never substituted with extract position. |
| `source_references_json` | Actual BASIC references and their identity-resolution notes. |
| `source_program` | Reported BASIC program/path. |
| `ultracs_source_path` | Exact `ultracs.source_path` BASIC-code reference. Keep it distinct from the root HVR parameter path, even if paths happen to agree. |
| `hvr_parameter_source_path` | Exact root `source_path` reported for the mapping/HVR parameter declaration. Do not overwrite it with a BASIC or dbt path. |
| `source_description` | Supplied Ultracs-side description, repeated unchanged for every target row of this source entry. Missing source prose remains blank/Unknown. |
| `source_description_origin` | Actual known origin/author classification; use recorded-input/unknown when authorship is not supplied. Do not assume AI or human review. |
| `business_definition` | Separately supported source-side meaning, repeated where applicable; do not copy a Snowflake description backward. |
| `definition_status` | `unknown`, `draft`, `provided_reviewed` or `inherited_reviewed`, with explicit basis. |
| `business_review_json` | Supplied definition author, reviewer, date, note and evidence; unknowns remain null. |
| `extract_file` | Actual extract name, such as DWACC. |
| `extract_column` | Exact `param_column`/HVR parameter name. |
| `extract_position` | One-based extract output position, kept separate from physical source location. |
| `basic_expression` | Exact recorded BASIC output expression. |
| `basic_transformation` | Complete recorded transformation summary; preserve calculations, fallbacks and unresolved operands. |
| `basic_comment` | Supplied BASIC comment; retain empty/missing state. |
| `basic_source_line` | Reported BASIC line, with verification state in provenance. |
| `original_mapping_notes` | Exact original root `notes`, repeated without paraphrasing across the source group's target rows. Keep composite-key caveats and consumer-validation instructions visible. Generated review notes supplement, rather than replace, this text. |
| `hvr_type` | HVR extract declaration type, not an assumed physical Ultracs/Snowflake type. |
| `hvr_obfuscation` | Original obfuscation flag, including string values such as N. |
| `hvr_cleanup_json` | Complete original cleanup settings, including enabled state and removed characters. |
| `hvr_cleanup_enabled` | Exact supplied `hvr_parameter.cleanup.enabled` value, including strings such as N; blank only when not supplied/null, with that distinction preserved in the original payload. |
| `hvr_cleanup_remove_chars_json` | Exact supplied `hvr_parameter.cleanup.remove_chars` JSON value. A known empty array is `[]`; missing and null remain distinguishable through the original payload and property audit. |
| `target_field_id` | Exact Snowflake endpoint ID for this row; blank only for a no-target placeholder. |
| `is_primary_target` | True when this row matches the uniquely resolved original primary-target designation; false for another target when that designation is established. Leave blank and flag review if primary claims are absent, conflicting or unresolved. Do not equate public stage with primary status. |
| `primary_target_field_id` | Resolved original primary-target ID, repeated across the source group's rows; blank when primary designation cannot be resolved uniquely. |
| `source_primary_target_json` | Original root `snowflake_table`/`snowflake_column` claims and full `cdp` object, with their source pointers, matching target IDs and resolution/conflict notes. Preserve both claims rather than silently replacing either with the selected target metadata. |
| `snowflake_stage` | Supplied target stage, including internal/public; do not silently export public fields only. |
| `snowflake_table` | Exact qualified target relation, with project/snapshot scope preserved. |
| `snowflake_column` | Exact target column for this row. |
| `snowflake_model` | Supplied target model name. |
| `snowflake_model_id` | Supplied model ID. |
| `snowflake_model_description` | Supplied table/model description, distinct from the column description. |
| `snowflake_description` | This target's supplied column description. Repeat identical text when supplied; do not replace it with another target's description. |
| `snowflake_description_origin` | Actual known target-description origin/author classification; unknown when not supplied. |
| `snowflake_data_type` | Declared type of this exact target, not a type copied from another stage. |
| `snowflake_classification` | Classification of this exact target; unknown when absent. |
| `target_business_review_json` | Target-specific business definition/review information when supplied; never inherited from source review. |
| `target_source_model` | Supplied upstream model reference for this target. |
| `target_source_column` | Supplied upstream column reference for this target. |
| `target_source_expression` | Exact supplied source expression for this target, including macro/cast syntax. |
| `target_projection_expression` | Exact supplied projection expression; keep separate from an upstream calculation. |
| `target_source_location_json` | Reported target source path, source/projection line claims, JSON Pointers and verification state. Keep mismatched YAML/SQL location claims distinct. |
| `rename_summary` | Readable name changes on the route to this target, identifying table/context and column. Same-name projection is retained, not a rename. |
| `rename_details_json` | Applicable per-step old/new field IDs, names, objects, operation ID and source evidence. Distinguish pure rename from extraction, cast or calculation. |
| `process_summary` | Explanation of extraction, known transformations and projections on the route to this target, with context dependencies identified separately. |
| `process_relationship_ids` | JSON array of atomic operation IDs associated with this source-target row, not an implicit ordered path. |
| `operation_output_scope_json` | Map each referenced operation ID to the output field IDs relevant to this row. Unknown output participation is null and requires review; never default to every output. |
| `process_details_json` | JSON array of complete atomic operation records using the schema below: expressions, all inputs/outputs, roles, bindings, evidence, status, assessments and unresolved dependencies. Include every referenced operation, retaining identical complete definitions for repeated operation IDs across rows. Select this row's relevant outputs in `operation_output_scope_json`, without rewriting the shared definition. |
| `path_details_json` | Supported route alternatives with path IDs, ordered operation/field references where established, source participation, completeness and unresolved segments. Preserve partial/proposed paths without inventing continuity. |
| `association_status` | `reported`, `evidence_supported`, `candidate`, `unresolved` or `excluded` for this source-target association, with its basis. A supplied target list alone does not verify a full physical-source path. |
| `source_participation_json` | Value/context/unknown participation of this source on each applicable path, with affected output bindings. |
| `path_complete` | True only when all required source-to-target bindings and continuity are established; false for known gaps. |
| `datatype_observations_json` | Relevant stages' declared types and expression-level cast observations, with differences/unknowns and evidence. Keep classification, unit/currency/grain and owner claims in their own field scopes. |
| `description_details_json` | Descriptions per relevant source/extract/RAW/intermediate/target field ID, with reported source paths, authorship/verification state and definition-review gaps. |
| `original_mapping_confidence` | Raw input confidence category at original mapping scope; this is not a numeric source-field rating. |
| `relationship_confidence_summary` | Readable list of this row's operation IDs and their recorded scores/Unscored state; never a source/target/path average. |
| `relationship_confidence_json` | Per-operation score/state, original scale, origin, method, rationale, components/arithmetic, rubric version, assessor/date and score evidence when supplied. Match the canonical embedded operation record, retaining unknowns. |
| `field_catalog_json` | Complete node/field metadata for all source, intermediate, target and co-input endpoints needed by this row's operations. |
| `route_context_json` | Complete declared ingestion-route object, explicitly distinguished from proven column-level process steps. |
| `hvr_channels_json` | Exact supplied `ingestion_route.hvr_channels` JSON array, visible as its own cell; channel order does not prove serial processing. |
| `s3_paths_json` | Exact supplied `ingestion_route.s3_paths` JSON array; retain all reported paths without inventing their execution order. |
| `airflow_dag` | Exact supplied `ingestion_route.airflow_dag` value. A declared DAG is route context, not runtime verification. |
| `airflow_tasks_json` | Exact supplied `ingestion_route.airflow_tasks` JSON array; retain task names and order as reported without claiming a verified per-field chain. |
| `raw_relation` | Exact supplied `ingestion_route.raw_relation` identity, separate from the physical DATA column and its logical JSON keys. |
| `dbt_input` | Exact supplied `ingestion_route.dbt_input`, including key spelling/case. Do not normalize away a different path claim. |
| `needs_review` | Boolean covering source-level issues plus issues relevant to this target/path, independent of confidence. |
| `review_notes_json` | Issue objects with code, affected target/step ID, explanation and source reference. |
| `provenance_json` | Input filename/hash, source-description origins, generated-summary methods, metadata conflicts and original input properties not otherwise represented. |
| `source_refs_json` | Exact input record/property JSON Pointers and reported repository references. |
| `original_record_json` | Mandatory complete original mapping object, repeated on every row in its source group, including unknown properties and every original target. Preserve parsed JSON values, keys, array order, nulls and empty values without normalizing or adding defaults. This payload is archival evidence, not an additional target list used as the main dictionary layout. |
| `input_property_map_json` | Mandatory per-property coverage map from original input JSON Pointers to output columns/structured locations, identifying directly displayed, structured or raw-payload-only preservation. Include an exact `original_record_json` destination for every original property and audit its value after CSV rereading. |

Keep source descriptions separate from target descriptions. The source description can repeat across rows; target descriptions/types/classifications belong to the exact target on each row. Different process summaries are required only when the documented processes differ; do not invent different wording or transformations merely because the target row differs. Summaries are generated views of the detailed records and must be checked for consistency after export/reimport.

### Original claims, primary targets and property coverage

The root primary-target pair, the `cdp` object and the corresponding `dbt_targets` entry are separate reported claims even when their values agree. In this snapshot, all 95 primary/CDP targets match an existing target: 59 primary designations are public and 36 are internal. Preserve the designation explicitly without creating duplicate pair rows. If future root/CDP/target metadata disagree, retain the original claim objects and pointers in `source_primary_target_json`/`original_record_json`, record the conflict and avoid a silent winner. A distinct, fully identified reported target can remain a reported association with review notes; conflicting or missing identity must not become a fabricated resolved field.

`original_mapping_notes`, the two source-path columns, cleanup details and the separate route columns are required visible information, not optional leftovers hidden only in generic provenance. They repeat on source-target rows where their source claim applies. Repeated root/nested program, extract, position and parameter declarations must retain their original property origins; agreeing values can share a displayed value, while disagreeing values remain explicit conflicts. Do not discard a raw HVR parameter name merely because it normally equals `param_column`.

Every pair row must retain its complete source record in `original_record_json`. This preserves JSON-value information for original properties that are not appropriate as dedicated readable columns, including target branches not selected by that row. It does not make those sibling branches part of the row's processing path. Distinguish absent properties, explicit null, empty string, empty array and empty object in this payload; display columns may use a common blank only when the original state remains recoverable and audited.

The property coverage audit must enumerate the original record and all object properties/array elements, including containers, nulls and empty values. Use exact escaped JSON Pointers. Use a compact coverage-map item with this logical shape: `{"input_pointer":"/0/notes","value_type":"string","destinations":[{"column":"original_mapping_notes","json_pointer":""},{"column":"original_record_json","json_pointer":"/notes"}],"coverage_state":"verified_visible"}`. The input pointer is absolute within the original file; destination pointers are local to the parsed JSON cell. An empty pointer selects the entire parsed JSON value. For an ordinary scalar CSV cell, either an empty pointer or null identifies the complete displayed scalar. Every item must include its exact `original_record_json` destination and any applicable readable/structured projection.

Allowed `coverage_state` values are `verified_visible` (an independently readable column and the raw payload have been checked), `verified_structured` (a structured projection and the raw payload have been checked), and `verified_raw` (only the complete raw payload supplies that property). These compact states encode visibility plus successful value preservation after CSV rereading; a redundant preservation-mode field on each destination may be omitted. They describe CSV round-trip verification, not upstream code correctness, business approval or production verification. Do not emit a verified state before checking every declared destination. Original-record values and parsed structured projections use strict type-aware comparisons: booleans, numbers, strings, nulls, arrays and objects must not be silently equated or coerced.

Ordinary scalar CSV cells are text displays, not typed JSON values. Compare those destinations using the explicitly declared display serialization: null becomes a blank cell, booleans become `true`/`false`, and supplied numbers/strings become their documented text representation, applying and reversing any declared spreadsheet escaping. This is an explicit display rule, not permission to change the original value or claim that a scalar CSV cell alone preserves its JSON type. In particular, the mandatory raw payload preserves the distinction between null, an absent property and an empty string even when a scalar display is blank. Record any additional display conversion explicitly; if a supplied value has no meaningful projection, retain it with its raw destination instead of inventing a display value.

Check destination values instead of treating the existence of a source pointer or a generic provenance cell as proof of coverage. Report the three coverage states separately, audit every source record and repeated payload copy, and report zero omitted or altered original properties only after these comparisons pass. Preserve any failed comparison in the validation report; never label a failure verified or remove it to improve the reported coverage.

Keep the unchanged input JSON, its filename and SHA-256 alongside the CSV delivery as the byte-level archive. Reparsed `original_record_json` preserves JSON values; it does not promise the original whitespace, property order, numeric spelling or file encoding. Unsupported/ambiguous JSON constructs must be rejected or explicitly reported rather than silently normalized to support a completeness claim.

### Row expansion and target-specific paths

Expand only documented source-target associations; never cross-join every source with every Snowflake field. Reconcile repeated primary/CDP targets with `dbt_targets`. Preserve both internal and public targets, including internal-only fields. A public-only view may filter rows explicitly, but the complete default export retains every represented target.

If several sources contribute to one target, retain one row per source-mapping/target pair and link them to the same complete operations. Each row is a contribution, not a claim that the source alone produces the output. If the same pair has multiple documented routes, retain every route in `path_details_json` with a stable path ID; do not choose one route or concatenate alternatives into a false sequence.

Select processing and rename details for the row's target, respecting direction, output bindings and dependency roles. An internal-target row stops at that target. A public-target row includes its documented internal predecessor and public projection. Do not attach sibling branches or subsequent outputs merely because they share a source, filter, table or multi-output process.

Preserve a shared operation's complete input/output definition in every applicable `process_details_json` copy, while explicitly identifying the outputs relevant to the current row in `operation_output_scope_json`. Its logical shape is an object such as `{"operation-1":["output-field-A"]}`; values are arrays of that operation's existing output IDs, or null when unresolved. Keep required co-inputs and their upstream context identifiable; these are co-contributors, not additional claimed outputs of the selected source. Do not expand the co-inputs' other consumers. Partial or conflicting associations remain rows with review notes, not established complete paths.

`process_relationship_ids` identifies the relevant subgraph, not an implicit ordered path through every listed input/output. An ordered path can be shown only when continuity and branch bindings are established. Each rename step references a documented operation and the applicable old/new field IDs. A single source-target row can contain several atomic relationship scores; there is no new overall row score.

### Repeated-source example from the supplied input

The original `Account` extract mapping has four target associations, so it produces the following four rows. `Account` is an extract-parameter display label, not a newly established physical Ultracs attribute name. All four rows retain the supplied source locator `ACCOUNT @ID` and repeat this exact source description: "CIS component parsed from the account identifier; candidate part of Account_Index_ID."

| Ultracs display name | Snowflake target | Target-specific processing focus |
| --- | --- | --- |
| Account | INTERNAL.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL_V2.ACCESSNUMBER | Recorded CIS extraction, logical RAW association, then `DATA:Account::STRING AS ACCESSNUMBER,`. |
| Account | PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL.ACCESSNUMBER | The detail-internal route above, then the recorded `ACCESSNUMBER` public projection. |
| Account | INTERNAL.ACCOUNTS_V1__ULTRACS_ACCOUNTS_EOD_BALANCES_V2.ACCESSNUMBER | Recorded CIS extraction, logical RAW association, then the balance-internal `DATA:Account::STRING AS ACCESSNUMBER,` mapping. |
| Account | PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_EOD_BALANCES.ACCESSNUMBER | The balance-internal route above, then the recorded `ACCESSNUMBER` public projection. |

These are a compact preview of four full rows, not actual CSV output. Repeat the supplied target description "The unique identifier for the Account" on all four rows because it is identical in this input. Preserve the recorded BASIC transformation `CIS = FIELD(NID, 'S', 1), with legacy fallbacks.` and the inferred composite-identifier caveat; do not claim complete physical-source resolution or invent numeric scores. The actual CSV includes the description and detail columns omitted from this preview.

### Embedded field catalog for HTML

A source-target row is not a complete field registry, so every row must carry the endpoint definitions its operations need. Each `field_catalog_json` item contains `field_id`, `system`, `stage`, `object`, `field_name`, `field_kind`, identity-resolution status, locator where relevant, description/provenance, declared type/classification, other supplied metadata and source references. Include documented source, RAW and intermediate fields plus required co-inputs, even when they have no independent dictionary row.

A future HTML viewer builds its field registry from the union of these catalogs. It merges only the same established field identity, retains incompatible metadata as explicit conflicts, and resolves every operation endpoint against that union. Repeated catalog nodes and operation IDs are shared graph items, not duplicate fields or new scores. Group dictionary rows by `source_entry_id` for a source-first view while retaining every individual target row.

## Embedded relationship records — process_details_json

Each `process_details_json` cell is a JSON array containing one object per complete operation or dependency applicable to that source-target row. This operation grain differs from the outer dictionary rows: expanding dictionary rows does not split a shared atomic operation or create new assessments. Do not create a Cartesian set of operation inputs/outputs merely to draw a graph. An operation may be repeated as the same complete object on multiple rows; a future HTML consumer deduplicates these objects by `(snapshot_id, relationship_id)` after checking equality.

The following table defines keys inside each embedded operation object, not another CSV's headers. Despite their `_json` suffixes, nested arrays/objects are native JSON values inside `process_details_json`, not double-encoded JSON strings. The single CSV must include every referenced operation and all of its endpoint definitions in the embedded catalogs; external files are not needed to interpret relationships, expressions, scores or evidence.

| Column | Content |
| --- | --- |
| `relationship_id` | Stable unique ID based on documented operation identity, stage, endpoints and source context; independent of display order. |
| `snapshot_id` | Same snapshot identity used by the containing dictionary row. |
| `dictionary_entry_ids` | JSON array of source-target row IDs whose applicable paths reference this operation; retain every relevant row. |
| `source_entry_ids` | JSON array of original source-group IDs associated with this operation, deduplicated independently of dictionary row IDs. |
| `source_field_ids` | JSON array of existing field IDs. All inputs belong to this recorded operation. |
| `target_field_ids` | JSON array of existing field IDs. |
| `process_name` | Supplied process name or a clearly generated literal navigation label. |
| `operation_type` | `direct`, `rename`, `cast`, `calculation`, `aggregation`, `conditional`, `filter`, `join`, `semantic_match` or `unknown`. Preserve original wording separately when normalized. |
| `dependency_role` | Uniform `value`, `filter`, `join`, `control`, `group` or `unknown`; use `mixed` only with explicit per-input roles. |
| `input_roles_json` | Map input IDs to their roles. Never treat every input as a value merely because the operation calculates a value. |
| `expression` | Original transformation/source/projection expression, unchanged and never executed. |
| `output_expressions_json` | Map each output ID to its expression when outputs differ. |
| `output_input_bindings_json` | Explicit input IDs and roles for each output. Missing bindings mean unresolved participation, not proof that every input affects every output. |
| `status` | `evidence_supported` for a specific hop supported by explicit supplied bindings; `candidate`, `unresolved`, `excluded` or separately documented `confirmed` otherwise. Import success and a record-wide label do not confirm individual hops. |
| `granularity` | Such as physical-field, symbolic-expression or logical-JSON-key mapping. Distinguish these from table-level route context. |
| `original_assessments_json` | Original labels/assessments with original mapping IDs, JSON Pointers and scope, such as `mapping_record`. Do not present them as newly assessed hop labels. |
| `confidence_score_10` | Supplied or separately documented relationship-specific numeric score on 0–10; blank when unscored. |
| `confidence_state` | `scored` or `unscored`. Zero is scored; it is not missing. |
| `confidence_method` | Actual source/method of this hop's score; blank if not supplied. |
| `confidence_rationale` | Recorded reasons, checks, weights, arithmetic and missing checks; do not invent these from a label. |
| `confidence_assessment_json` | Original score/scale, origin, assessor, assessment time, rubric ID/version, components and score-specific evidence when available. |
| `evidence_json` | Inline evidence records: reported path, expression/excerpt, reported line information, input JSON Pointer, evidence role and verification mode. |
| `source_mapping_ids` | All original mapping IDs supporting this operation. |
| `source_refs_json` | Input filename/hash, exact JSON Pointers and any explicitly verified external references. |
| `route_context_json` | Associated HVR/S3/Airflow context without inventing serial per-column hops. |
| `needs_review` | Boolean independent of the numeric score. |
| `review_notes_json` | Missing dependencies, ambiguous endpoints/bindings, metadata conflicts, provenance gaps or unexplained assessments. |

Use one consistent shape for embedded operation values. The following illustrates selected nested properties of one operation object, before CSV quoting; the IDs are illustrative, and the complete object also retains the identity, evidence, status and assessment keys defined above:

```json
{
  "input_roles_json": {"id-A": ["value"], "id-B": ["value"], "id-flag": ["filter"]},
  "output_expressions_json": {"id-net": "A - B", "id-total": "A + B"},
  "output_input_bindings_json": {
    "id-net": [{"field_id": "id-A", "roles": ["value"]}, {"field_id": "id-B", "roles": ["value"]}, {"field_id": "id-flag", "roles": ["filter"]}],
    "id-total": [{"field_id": "id-A", "roles": ["value"]}, {"field_id": "id-B", "roles": ["value"]}, {"field_id": "id-flag", "roles": ["filter"]}]
  }
}
```

Role lists contain supported role strings; unresolved roles use `["unknown"]`. Include every output key in the binding map; use a null value when its bindings are unresolved. Only a documented constant output can have a known empty binding list. A relationship needs at least one target; an empty source list is allowed only for a documented source-free constant, never as a substitute for unknown origins. Preserve the actual condition expression for filter/control inputs separately when it differs from the output formula.

For a genuine two-input/two-output calculation, keep one operation only when its operation identity is documented and retain a formula and input binding for each output. If separate outputs have independently evidenced operations or assessments, keep separate relationships. The input's flat `dbt_targets` fan-out is not, by itself, one shared transformation.

Classify operations from actual supplied syntax/evidence, not the field's business name. A bare precomputed variable such as `BAL`, `CIS` or `PID` does not itself establish a calculation: retain it exactly and use `unknown` when its defining operation is not supplied. An explicit recorded transformation summary can support a reported operation category even when the expression is only a variable: for example, Balance's summary says that transaction adjustments are applied. Identify that summary and its pointer as the classification basis in operation evidence; do not imply the category came from analyzing the variable name. A supported reported category does not establish a complete executable formula, resolved operand inventory or verified implementation. Preserve those gaps and the original summary rather than inventing the missing details. A date-parsing macro is a documented transformation, but a macro call alone does not establish an explicit cast; use a suitable literal process description and an `unknown` normalized operation where the body/type conversion is unavailable. Use `cast` only when cast syntax or separately supplied cast evidence supports that classification. Where an expression combines a cast with renaming, retain both the cast observation and the actual old/new name association.

## Extraction and traversal procedure

1. Read the input without changing it. Record filename, hash, scope and JSON Pointer for each record; validate identities, positions, target references and property types.
2. Inventory source groups, source references, extract slots, RAW paths and `dbt_targets` fields. Reconcile primary/CDP target repeats; deduplicate true identities without deleting contributing mappings or conflicting claims. Create one main row per documented source-entry/target pair, repeating source values and exposing the target metadata as ordinary columns. Retain no-target source records as marked placeholder rows.
3. Resolve available Ultracs locators conservatively. Preserve BASIC expressions, comments and transformations. Missing file bindings or operands become unresolved symbolic/expression references; do not translate an arbitrary variable into a physical source column.
4. Retain the extract declaration and HVR flags. A declared cleanup option can be documented, but does not prove runtime cleanup happened or justify a fabricated intermediate physical column.
5. Represent the documented logical association between the extract slot and the RAW `DATA:<key>` path, with the ingestion route attached as context. If that association itself is incomplete, mark it candidate/unresolved.
6. Build RAW-to-internal mappings from each target's `source_expression`, resolving the actual referenced DATA key(s). Resolve quoted paths and macro syntax only to the extent supported. Do not attach a target to the enclosing record's parameter when its expression refers to another key.
7. Build internal-to-public mappings using `source_model`, `source_column` and `projection_expression`. Resolve model/column identity uniquely within the documented project scope. Do not guess by target list order or draw every extract directly to every target. Preserve unresolved public mappings if resolution fails.
8. Retain original expression syntax, casts and stage-specific declared types. For example, Balance's internal type is NUMBER(38,2), public type FLOAT, while its SQL excerpt contains `::STRING`; preserve all three observations and flag the difference for review.
9. Separate established, proposed and excluded relationships. Traverse only supported, explicitly bound links for established root/impact summaries. Keep proposed origins separate from proposed downstream uses; excluded links remain inspectable without contributing to established origins.
10. Propagate value versus context roles through paths and respect each output's bindings. A shared output is not its sibling's ancestor. Unknown roles, missing operands or unresolved source identities must remain visible in summaries.
11. Detect established cycles, missing endpoints, conflicting claims and ambiguous identities. Report blocked/partial summaries without deleting evidence or silently changing statuses to force a complete-looking result. Preserve raw rows even when a derived traversal is blocked.
12. Populate each source-target row's source and target descriptions, renames, relevant process/route alternatives, output scopes, type observations and per-operation confidence details from the field catalogs and embedded operations. Check that unrelated sibling branches are absent from the row's path. Export the single CSV, reread it, and validate source-group/row IDs, catalog field IDs, operation/path IDs, references, repeated-source and repeated-operation consistency, summaries, scores, original-record property coverage and pair/source/target coverage. Report checks and remaining gaps.

The current JSON does not provide a structured complete multi-input operation inventory: populated `source_references` arrays contain at most one item. For example, Available_Balance records `AVAILBAL-OCONV(ODLIMIT,'MR2')` without a resolved source locator. Keep that expression and unresolved dependencies; do not invent two physical Ultracs sources from the variable names.

HVR channel lists, S3 path lists and Airflow task lists are route metadata. Their array order does not prove an exact serial per-column processing chain. Keep the S3/Airflow route separate from any direct-HVR route unless supplied evidence explicitly connects them. Do not extend table-level Enterprise context into field mappings without column-level evidence.

## Confidence and scoring basis

Confidence belongs to each relationship, not a field, description or entire path. A field connected to three relationship records can show three assessments through its incident relationship IDs. One complete multi-input/multi-output operation retains one assessment; it does not create per-pair scores.

In the main dictionary, list the applicable operations' assessments in `relationship_confidence_summary` and `relationship_confidence_json`. For example, a source-target route using R1, R2 and R3 lists three separately scoped assessments, including Unscored entries. Another row sharing R1 references the same R1 assessment; it does not receive a newly generated score for that copy. Repeating a source name across three target rows does not imply exactly three atomic operations or three different scores.

The current input supplies only mapping-wide categories. Preserve them in `original_assessments_json`, linked to their source records. **By default, newly decomposed hops are Unscored. Do not apply `explicit = 9.5`, `confirmed_calculated = 9`, or the earlier illustrative checklist automatically.** The referenced `confidence_score_skill.md` is not a required available input and must not be assumed to contain an authorized rubric.

When a separately supplied assessment or explicitly authorized scoring rubric is available:

- Retain the score, original scale and scope. Convert a declared 0–1 score by multiplying by 10; convert a declared 0–100 score by dividing by 10. Do not guess an ambiguous scale or use 0 for missing.
- Record whether it is an upstream model self-assessment, rule/checklist result, human assessment or historical lookup. These are different assessment origins.
- Record the actual method, rubric version, assessor/date when known, evidence and missing checks. For weighted scores, retain factors, maximum/earned points and arithmetic so the displayed result can be reproduced.
- Assess a newly identified hop only from evidence applicable to that hop. Do not copy a source-record score onto every BASIC, transport, internal and public link.
- Label any newly derived rating as derived and retain the original category unchanged. A categorical lookup is a heuristic display rule, not independent evidence verification.
- Do not average incident scores into a field score, select a competing mapping solely by its score, or interpret 10/10 as approval. Static repository evidence cannot become runtime verification.

## Descriptions, business review and evidence

Keep supplied descriptions, generated technical summaries and business definitions separate. `business_field` is a mapping label; `cdp.description` and target descriptions are supplied metadata, not proof of business approval. Text like “X sourced from Y” remains preserved but needs a meaningful business definition from an appropriate reviewer.

Unknown business meaning remains unknown even when the transformation is explicit. Supplied prose may be presented as an attributed unreviewed draft when appropriate; it must not silently become reviewed. Never copy a downstream definition backward to an undocumented Ultracs source. Conservative inheritance, if separately justified, still requires target review and must retain its source. Owner, reviewer and review date are not inherited or inferred.

Preserve source-description origin/author, technical-summary generation method and business-review events separately in `provenance_json`. Do not invent an author, model call, review or time. AI-proposed business text remains a labeled draft unless an actual review is recorded.

Evidence inside the input is **reported evidence** until checked against separately supplied files. A JSON Pointer proves where the extraction read a claim, not that production executes it. Keep evidence roles distinct: mapping, metadata description, business approval and score assessment.

Do not misattribute SQL line numbers to YAML files. Many target `source_path` values point to YAML while neighboring properties hold SQL expressions and line numbers. Retain the reported path/line/expression as separate claims; set the cross-artifact location to unresolved unless the correct SQL file is supplied. Do not fabricate an SQL filename or a verified line range.

Preserve type/classification differences, empty descriptions, BASIC comments, cleanup/obfuscation flags and placeholder names. Keep all six MissingColumn records; do not rename or remove them to improve appearance. Preserve Account_Index_ID as an inferred composite claim, not a fabricated confirmed concatenation field.

## CSV serialization and future HTML

- Write UTF-8 CSV, with BOM if required by the intended Excel workflow. Use a CSV writer for commas, quotes and embedded newlines; do not concatenate cells manually.
- Encode ID lists and structured metadata as valid JSON inside CSV cells. Use `[]` for a known empty list and JSON `null` for unknown structured values. In scalar columns, leave unknown values blank and retain their explicit status/review reason; an HTML renderer can display Unknown/Unscored.
- Serialize booleans consistently as `true`/`false`. Keep numeric confidence cells numeric; an unscored numeric cell is empty. Preserve the original HVR string flags inside metadata rather than silently converting them.
- For example, a two-ID array cell is the logical value `["id-A","id-B"]`; CSV quoting must produce `"[""id-A"",""id-B""]"`.
- For Excel delivery, check every decoded cell's character length against the 32,767-character limit and report the maximum length. Compact JSON serialization and the compact coverage-map shape are allowed without dropping values or audit destinations. Never truncate descriptions, evidence, payloads or coverage maps to meet the limit. If any cell still exceeds it, report the affected row/column and the Excel limitation explicitly; preserve the complete CSV data rather than claiming that Excel can display it fully.
- Protect untrusted text beginning with spreadsheet formula characters when exporting for Excel. Preserve the original text in a declared JSON text cell/metadata and record the reversible display escaping; do not mutate canonical IDs or lose expressions. A prefix-escaping scheme must distinguish pre-existing prefixes.
- In a future HTML consumer of this CSV, select a pair row by `dictionary_entry_id`, group its siblings by `source_entry_id`, and build an operation registry from the union of `process_details_json` objects keyed by snapshot and operation ID. Require identical repeated definitions, then resolve `process_relationship_ids` against that registry. Resolve endpoint IDs through the union of `field_catalog_json` records. Create processing cards from operations, applying the row's `operation_output_scope_json`, per-output bindings and dependency roles. Show relevant co-inputs without presenting unrelated sibling outputs as ancestors. Allow a source group to expand all its target rows and a target to reveal every contributing source group. This CSV specification does not claim an existing HTML application already imports this CSV format.
- Use relationships as the source of complete paths; origin/impact columns are summaries. Include candidate/excluded relationships in inspection without presenting them as established paths. Display unknown sources, field kind, route granularity, per-relationship score and scoring basis explicitly.
- Check array/object cell types, duplicate pair/operation/path IDs, inconsistent source-group or catalog copies, output scopes and dangling references before rendering. Repeated source IDs/names across different targets are expected. Display source description, target/table descriptions, rename steps, processing and type changes in separately labeled sections. Render source text as text, never executable HTML or code.

The single CSV preserves the structured dictionary and complete original JSON-value records through mandatory `original_record_json` payloads and a per-property coverage audit. Keep the input JSON unchanged as the byte-level archival source. Unknown input properties must remain recoverable through their original payload values and source pointers; generic provenance alone does not establish completeness. Do not claim byte-for-byte preservation of input file serialization from the CSV.

## Worked checks using this input

- **KiwiAcc:** create two target rows, repeating the supplied source description. Retain TRAN<4,8> and REC<4,8> as reported with their identity-resolution context, DWACC position 7 and RAW `DATA:KiwiAcc`. The internal KIWIBANKACCOUNTNUMBER row and its public projection row have distinct target IDs and applicable process details. Keep the original `confirmed` label at mapping scope; hop scores remain Unscored without assessments.
- **EodDate:** one extract slot has six targets across detail/balance models and differently named date columns, so create six rows under one source group. Source description remains blank in all six because none is supplied. Retain each target's own description and applicable internal/public links. These are six target fields, not six aliases of one field.
- **AccountName:** DWACC position 51 and ACCOUNT<28,2> describe different positions/stages. Do not conflate them.
- **AltAccountName:** the supplied BASIC expression/reference `AREC<28,4>` disagrees with the transformation summary's `REC<4,2>`. Preserve both original claims and their pointers, flag the source-reference conflict for review on every applicable target row and operation, and do not autocorrect either claim or present complete physical-source resolution.
- **Balance:** create separate internal/public target rows with the same supplied source description. Preserve its calculated BASIC summary and incomplete transaction-source details on both. Keep NUMBER(38,2) on the internal target and FLOAT on the public target, retaining the relevant upstream STRING cast excerpt and type-review notes.
- **Available_Balance and MissingColumn fields:** retain documented expressions and downstream targets while explicitly showing unresolved business meanings or physical sources.

## Acceptance checklist

- The single output rereads as valid CSV with unique headers and consistent row widths; every JSON cell parses to its documented type, including native nested values in embedded operations.
- Report the maximum decoded cell length and whether every cell fits Excel's 32,767-character limit. No content or coverage destination is truncated to obtain a passing result.
- Every original mapping is represented or explicitly reported as unresolved. Record input/output counts, source coverage, target coverage and any deduplication/conflicts.
- For this snapshot, export 179 source-target rows across 95 source groups, covering 179 distinct target fields (112 internal, 67 public). Put additional RAW/source/reference/intermediate nodes in their field catalogs. Do not misreport the 95 groups as 95 independently established physical Ultracs attributes. Recompute pair rows, unique targets, source groups and no-target placeholders separately for future inputs or explicit scope restrictions.
- All 67 public targets in this snapshot resolve through their recorded source model/column to internal targets. Check this property rather than assuming it for future inputs.
- Every operation endpoint resolves in the same-snapshot union of field catalogs, not merely against dictionary-row or source-group IDs. Every target, process/path ID, output scope, rename step and review reference resolves using the single CSV's embedded values. Scope outputs belong to their referenced operation; ordered paths have supported continuity. Shared operation copies are identical, resolve to one operation with one assessment, and their row/group references agree with the dictionary. Stable IDs survive reorder/export/reimport.
- Original record IDs, JSON Pointers, descriptions, stage-specific types, classification, flags, routes, source expressions and original assessments remain traceable. Conflicting claims stay distinct.
- Every row carries an exact JSON-value copy of its original mapping object. Audit every original property/container/null/empty value against the reread payload and report direct/structured/raw-only coverage separately. Original notes, distinct source paths, route components, cleanup settings and primary-target designations are visible in their required columns; conflicting primary/CDP/dbt claims remain separately inspectable. Verify the unchanged archived input SHA-256.
- Every compact coverage item has an exact raw-payload destination and a truthfully verified visibility state. All declared destinations pass their applicable comparison after CSV rereading: strict typed comparisons for original/structured JSON values and declared reversible display serialization for ordinary scalar text cells. Coverage verification does not claim to verify the underlying source system. Bare variables are not automatically classified as calculations; any category supported by a separately recorded transformation summary cites that summary and retains formula/operand gaps. Macro calls are not automatically classified as casts, and contradictory source expressions/summaries remain review issues.
- Each row repeats the exact source description and BASIC/extract details for its source group, while exposing its own target names/descriptions/types/classifications, rename and process details, provenance, assessments and review notes where supplied. Consistent copies stay identical; conflicting source claims retain their provenance rather than being silently overwritten. Unknown information is visibly unknown rather than silently omitted.
- Different targets of the same source remain separate rows. Different contributing sources of the same target also remain separate rows. Multiple documented routes for one pair remain distinct path records. No-target sources remain placeholders rather than disappearing. No row's processing path includes unrelated sibling outputs or unrelated co-input consumers.
- Multiple-input/output formulas and bindings remain complete, with no fabricated Cartesian edges. Unresolved participation stays explicitly unresolved.
- No numeric score, scoring formula, business approval, owner, runtime claim or physical source identity has been invented. This input alone produces no new numeric hop scores.
- Numeric scores agree with recorded scale/method and any reproducible arithmetic. Missing and zero remain different. No field-level aggregate score is emitted.
- Final reports describe verification actually performed and the input's coverage limits. If optional files are unavailable, state that extraction used recorded JSON evidence only.
- Deliver the single `data_dictionary.csv`, retain the unchanged input JSON with its hash, and provide a short validation summary when extraction is requested. No second relationship CSV is required. JSON/HTML exports, extra CSVs, installation, upstream regeneration and converter code require their own task scope; updating this document alone does not create them.
