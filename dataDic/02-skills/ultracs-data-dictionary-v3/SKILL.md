---
name: ultracs-data-dictionary-v3
description: Generate three linked lineage CSVs and an offline HTML viewer with the original V1 dictionary layout plus Asset Registry and Field Catalog views. Use for the supported Ultracs inventory JSON, preserving MultiValue positions, HVR mappings, Snowflake outputs, descriptions and relationship assessments; not arbitrary graph formats or production verification.
---

# Ultracs data dictionary, version 3

Create three linked CSVs and an English offline HTML viewer for one supplied lineage inventory. Preserve the exact input claims, missing values and disagreements. Generate all three tables from the same canonical fields and operations so their identities, descriptions, processing and relationship assessments agree.

This skill is a local package. It does not need to be installed globally. The scripts use Python's standard library and do not call models, repositories, source databases or external services.

## Package and run

The Desktop `dataDic` folder separates inputs, skills and results by numbered
workflow stage. Both local skills are under `02-skills`.
See the [workspace README](../../README.md) for the full two-skill workflow and
the separate [AI enrichment skill](../ai-description-enrichment/SKILL.md) for
filling missing descriptions.

```text
dataDic\
  README.md
  01-input\
    column_lineage.json
  02-skills\
    ultracs-data-dictionary-v3\
      SKILL.md
      generate.py
      legacy_projection.py
      description_provenance.py
      build_viewer.py
      assets\                 # Eight HTML, JavaScript, CSS and schema assets
    ai-description-enrichment\
      SKILL.md
      references\
  03-output\
    index.html                # Main viewer: latest completed output
    01-baseline\
      asset_registry.csv
      field_catalog.csv
      data_dictionary.csv
    02-ai-enriched\            # Separate enriched CSV bundle
```

From the `dataDic` directory, run one command:

```powershell
python -B .\02-skills\ultracs-data-dictionary-v3\generate.py
```

It reads `01-input\column_lineage.json`, generates and internally validates all three CSVs in `03-output\01-baseline`, and publishes the main `03-output\index.html` from that completed snapshot. The stage folder contains CSVs only. The four Python files sit directly in this skill folder; there is no `scripts` subfolder. `-B` prevents Python bytecode-cache files. The default input/output paths are anchored to the `dataDic` root even if the script is invoked from another directory.

The default command replaces the generated baseline in `03-output\01-baseline`.
To reproduce it without replacing a saved bundle, use a new output folder:

```powershell
python -B .\02-skills\ultracs-data-dictionary-v3\generate.py --output .\03-output\01-baseline-next
```

For another supported inventory, specify its input, output folder and graph label:

```powershell
python -B .\02-skills\ultracs-data-dictionary-v3\generate.py --input .\01-input\another_lineage.json --output .\03-output\another-graph --graph-id another-graph
```

Open `03-output\index.html` in a modern browser for the latest completed result.
For every output bundle written directly under `03-output`, successful generation
publishes its HTML as the main viewer after validation. Outputs elsewhere do not
change it. Later AI enrichment publishes its own completed bundle to the same main
viewer. This is an offline snapshot, not a live CSV connection; refresh an open
page after publication. Do not choose the latest bundle by filenames or guessed
modification times.

Each graph gets its own three-CSV result folder. For direct subfolders of
`03-output`, there is one shared main HTML viewer at `03-output\index.html`,
updated after the most recent completed run. A custom destination outside
`03-output` retains the standalone four-file bundle behavior. `graph_id` is the
explicit graph label, or the input filename stem when omitted; `snapshot_id`
identifies the exact input SHA-256. Do not combine CSVs from different snapshots.
No online publication or connection to other systems is part of this workflow.

## Supported input

The bundled converter accepts the mapping-inventory JSON array used by `column_lineage.json`. Each original record identifies a mapping (`field_id`) and carries source/extract declarations, an `ultracs` object, an `hvr_parameter` object, an `ingestion_route` object, and reported Snowflake/dbt targets. The original top-level `confidence` is a mapping-level categorical label.

This is a documented inventory converter, not a generic `nodes`/`edges` importer or a BASIC/SQL execution engine. It does not discover new relationships or calculate values from expressions. Unsupported shapes or assessments must fail clearly rather than produce a plausible incomplete dictionary. Keep original source records intact, including properties not promoted to presentation columns. If extending the input contract, update the converter, validation and viewer together before claiming support.

## Three tables

| File | Row meaning | Purpose |
| --- | --- | --- |
| `asset_registry.csv` | One represented asset or explicitly scoped source context | Asset type, source system, layer, description, governance metadata and asset dependencies. |
| `field_catalog.csv` | One canonical field/reference within the graph snapshot | MultiValue source references, extract slots, RAW JSON paths and Snowflake columns, with their own metadata. |
| `data_dictionary.csv` | One original source mapping and one exact Snowflake target | Repeated source information plus that target's description, renames, processing, relationships, confidence, evidence and input notes. |

The main dictionary retains the original 81-column contract and appends graph/asset/field references and normalized source coordinates. It remains readable on its own and retains complete JSON detail cells. Do not require another relationship CSV to interpret it. If four outputs are documented for a source mapping, retain four rows with repeated source name and description. Multiple routes for the same source/target pair stay separate within that row's path details; do not turn alternatives into one serial route.

The scripts' explicit header definitions are the output contract. Generation retains graph/snapshot identities, table counts, input/output hashes and interpretation metadata inside the HTML bundle. Managed output folders receive the three CSVs, while the only HTML is the main `03-output\index.html`; it does not write standalone manifest, validation-report or audit files. Completion and the internal validation count are printed in the terminal.

## Source model: MultiValue to HVR to Snowflake

Ultracs is represented using MultiValue files, record contexts and positional attributes. Use table/column terminology for the stages where relational tables and named columns are actually reported. Distinguish the following identities:

1. **Physical MultiValue file**, only when supplied and bound by evidence. A program name, a variable such as `REC`/`AREC`/`TRAN`/`ACCOUNT`, or text inside an original mapping ID does not independently establish a physical file.
2. **Record reference and locator**, preserving the exact reported source expression. For an unambiguous positional locator, separately record attribute, value and subvalue coordinates. These coordinates describe the locator syntax; they do not establish the physical file binding.
3. **Record key**, such as an `@ID` reference, distinct from attribute zero. A computed expression or several operands must remain an expression/reference and must not become a fabricated single physical attribute.
4. **Extract output slot and HVR header**, identified by the program/extract/output position and exact parameter name. An extract slot is not automatically an HVR physical table column.
5. **RAW JSON path**, identified by the reported Snowflake relation and exact `DATA:<key>` path. A JSON key is not a newly established physical SQL column.
6. **Snowflake column**, identified by the exact relation and column. Internal and public columns remain distinct even when their names agree.

Example from the supplied inventory:

```text
Reported Ultracs locator: ACCOUNT<28,2>
BASIC reference:          AREC<28,2>
Extract output:          DWACC position 51
HVR header:              AccountName
RAW JSON path:           DATA:AccountName
Snowflake output:        ACCOUNTNAME, scoped to its exact relation
```

The source position and extract position are different. Preserve both. Do not change `ACCOUNT<28,2>` into `ACCOUNT<51>`. Keep `ACCOUNT` and `AREC` as their separately reported references unless their binding is actually established.

If a source locator and a concrete BASIC reference have the same positions but different record-variable names, syntax alone does not establish an alias. Retain both references, flag `UNCONFIRMED_RECORD_VARIABLE_BINDING`, and keep the source contribution and affected binding unresolved. Do not mark that source path complete merely because the positional numbers agree. Keep the reported association available instead of deleting it or silently rewriting either reference. The current adapter does not interpret extra alias-assertion metadata; archive those claims until an explicit binding adapter is implemented.

For the supplied input, the physical MultiValue file binding is not independently provided. Represent the Ultracs program as a `multivalue_source_context`, explicitly mark the physical file as unknown, and keep the reported locators inside that context. This asset is a navigation scope, not a claim that the program itself is a MultiValue file. `DWACC` is a reported extract file; do not invent an HVR physical table.

## Metadata and unknown values

- **Asset registry:** provide asset name/type, source system, layer, domain, owner, steward, description, update frequency, approximate operational row count, lineage reference, PII/sensitivity and status. Populate only supplied or explicitly attributable structural values. `field_count` is the number of represented catalog entries, not the number of production records.
- **Field catalog:** retain asset membership, field kind/name, business name, data type, description/origin, definition/review, source coordinates, extract/HVR identity, upstream/downstream field IDs, transformations, samples, allowed values, nullability, PII, primary/foreign keys, rules, verification date, notes and evidence. Keep original canonical field objects available for inspection.
- **Main dictionary:** preserve source descriptions and display-name origins, target metadata, BASIC/HVR declarations and flags, cleanup settings, target-specific processing/renames, output bindings, path alternatives, route context and original notes. Retain exact original records and the input-property coverage information.
- Blank CSV cells mean information is unavailable in that column. HTML renders this as **Unknown** or **Not supplied** as appropriate. Preserve missing versus null versus empty arrays/strings in original JSON payloads; do not replace those original values.
- Supplied descriptions are not automatically reviewed business definitions. Keep their provenance and review state separate. Do not copy a downstream definition backward to an undocumented source or invent an owner, steward, reviewer or verification date.
- Column classification does not establish asset classification or PII. Missing PII is unknown, not false. Do not infer primary keys from identifier-like names or allowed values from a filter predicate.
- Preserve HVR cleanup flags and removal characters exactly as declared, including `Y`, `N` and empty arrays. An enabled cleanup configuration belongs in the processing summary and relevant operation context, while remaining a declaration rather than proof of execution, ordering or a separately established runtime hop. Inactive settings remain inspectable without inventing a transformation result.

## Column descriptions and their provenance

Retain each field's own supplied description verbatim. The source description comes from that mapping's `ultracs.description`; a Snowflake target description comes from its selected `dbt_targets` object. Keep the additional primary-target `cdp` claims in the original payload. Do not overwrite a target description with a sibling target, a model/table description or a source description. An undocumented HVR header or RAW JSON key must not inherit another field's text.

An optional `hvr_parameter.description` and its own scoped provenance are supported for that HVR slot. A generic `ingestion_route.description` is route context and must not become a RAW JSON-key description.

Keep two questions separate: **where the description was read** and **how it was originally authored**. The compatibility value `recorded_input` means the text was copied from the supplied JSON. It does not prove that a person wrote it, that it came from a repository, or that AI did not generate it upstream. A nearby source-code/YAML path also does not by itself establish the description's authorship.

The field catalog adds `description_source_type`, `description_author`, `description_generator`, `description_source_reference`, `description_source_pointer` and `description_provenance_json`. The main dictionary has the same six facts for each side, using the prefixes `source_description_` and `snowflake_description_`. These values must agree with the matching canonical field. Preserve exact input JSON pointers and the reported references, author/generator and complete declared metadata in the provenance JSON.

Use an explicitly supplied description-specific reference when available. Otherwise the description reference identifies the immediate input JSON, with its exact property pointer. A generic parent `source_path` stays a reported context reference in provenance; do not promote it to the description's original source. A nonempty description pointer must resolve to an actual property. If that property is absent, leave the description pointer blank while retaining the parent-object location.

| `description_source_type` | Required basis | Viewer label |
| --- | --- | --- |
| `ai_generated` | Explicit description metadata says AI/model generated. | AI generated |
| `existing_metadata` | Explicit description metadata says existing repository/documentation metadata or human authored. | Existing metadata |
| `unknown` | Description text exists, but its original authorship/source type is unspecified, ambiguous or contradictory. | Input JSON · origin not specified |
| `not_supplied` | No description text is supplied for that field. | Not supplied |

Do not classify authorship from writing style, a person's name, an arbitrary generator name or a path alone. Conflicting supplied origin labels remain unknown with every claim preserved. Missing author or generator values stay unknown. These labels report the supplied provenance; they do not claim independent repository verification. No new model call or description generation is performed by the bundled converter.

For future inputs, add optional `description_provenance` beside the existing `description` in that exact source or target object. For example, the following is a column-metadata fragment, not a replacement for the complete mapping-record input contract:

```json
{
  "description": "Account name as recorded in the source system.",
  "description_provenance": {
    "origin": "existing_metadata",
    "source_reference": "repository/path/field_dictionary.yaml#account_name",
    "author": null,
    "method": "Copied from the supplied field dictionary"
  }
}
```

For an upstream AI draft, use `origin: "ai_generated"` and record the reported `generated_by`, `model`, `method`, `generated_at` and `evidence_refs` when available. This documents an existing upstream action; it does not instruct this skill to run a model. The scoped aliases `description_origin`, `description_source_type`, `description_author`, `description_generated_by` and `description_source_reference` are also accepted. Generic `generated` and `recorded_input` labels remain ambiguous. Metadata not promoted to columns still stays in the complete declared metadata/original JSON.

In Field Catalog, show each field's own description and source label together; expose the author/generator, reference, exact input pointer and full provenance in its detail view. The main dictionary preserves V1's source and target description cells and original detail layout; all appended description-provenance columns remain accessible in its complete CSV-field disclosure. Source-type filtering belongs to the canonical field view and must not silently change V1's filters or layout. The current input has no explicit description-authorship metadata: its nonempty descriptions therefore have unknown original origin, while their input JSON locations remain known.

## Relationships and confidence

Document direct mappings, renames, casts, calculations, conditionals and other reported processing with exact expressions and original evidence. Keep opaque macro calls and precomputed variables explicit when their implementation is not supplied. Preserve filter/join/context dependencies without claiming they contribute a value unless that role is reported.

Confidence belongs to an individual recorded relationship/operation. A field or a source-to-target row may contain several operations, each with its own assessment. Do not average these into a field score or copy one mapping label onto every step as a numeric score.

For a supported numeric assessment, preserve its score out of 10, origin, scoring method, rationale, assessor, date, rubric and evidence references together with the relationship it rates. Missing assessment components stay unknown. Do not invent numbers from `explicit`, `confirmed`, `inferred` or other text labels. The supplied snapshot contains mapping-level labels but no numeric relationship assessments, so all its operations are **Unscored**. An unscored relationship is not a zero-score relationship. The bundled input converter rejects unsupported scoring extensions until an adapter is implemented.

Transport arrays such as HVR channels, S3 paths and Airflow tasks are reported route context. Their order does not prove a serial per-column pipeline. Keep them distinct from evidenced field dependencies. A structurally complete recorded path is not production verification. Preserve source/summary contradictions and cross-artifact path/line ambiguity as review items.

## Viewer behavior

V3 uses the same three-table data contract as V2 and the original V1 main dictionary presentation. Keep the main table's seven columns, column order, styles, single-source selector, review controls, advanced/custom conditions, sorting, row pagination, target-specific processing, details, keyboard access and filtered export. Do not replace it with V2's grouped source sections or multiselect. Its readable columns remain Ultracs source, Source description, Snowflake target, Target description, Recorded processing, Relationships and Review.

Expose exactly **three tabs for the three CSVs**: **Dictionary** for `data_dictionary.csv`, **Asset Registry** for `asset_registry.csv`, and **Field Catalog** for `field_catalog.csv`. Dictionary retains the original V1 main presentation and controls. Asset Registry represents all seven supplied asset/context records; it is not a Snowflake-only summary. The old derived **Assets** overview is no longer a user-facing entry. Keep only its hidden, disabled compatibility hook where the unchanged V1 script requires it; do not expose a fourth tab. Field Catalog includes source references, HVR slots, RAW JSON paths and Snowflake fields, each with its own stable identity. Provide explicit system/layer/kind and field description-origin filters so Ultracs source fields can be selected without omitting the other stages from the data.

Field Catalog retains its original 47-column canonical CSV schema and seven visible table columns: **Field / attribute**, **Source system / layer**, **Description / origin**, **Data type**, **Source / HVR positions**, **Physical binding** and **PII / keys**. Preserve its complete metadata, description provenance, details, search, sorting and full CSV export without adding source-display extension columns or deriving physical file names from record-variable prefixes.

Each new CSV view supports search, filters, sorting, pagination, record details and complete filtered export. State and filters stay local to the corresponding view. Qualify identical names by asset and graph snapshot. Related-item navigation uses exact scoped IDs and clears incompatible destination filters so a prior search cannot hide the clicked item's connections. Confidence remains attached to operations; a catalog field is not assigned a fabricated field/description score.

Main-table keyword search follows the row's relevant target path. Archived sibling outputs are not keyword matches. Operation type, status and score constraints must match the same operation. Detail views preserve relevant branches and distinguish matched operations without dropping other required steps. Missing numeric assessments remain Unscored. Keep all original V1 review information and controls because the user explicitly requested V1's existing presentation and functionality; V2's simplified presentation rules do not override this requirement.

Add a named **Source, HVR and route details** section to the main row dialog without replacing V1's existing sections or table. Show source program, the distinct BASIC and HVR declaration paths, exact HVR flags and cleanup configuration, original mapping notes, and the reported HVR/S3/Airflow/RAW/dbt route context. Label route arrays and cleanup settings as declarations; their listed order does not prove serial execution. The complete original-column disclosures remain available in all three CSV views, including properties that are more appropriate as structured/raw detail than as table cells.

Embed all three matching CSV texts in one HTML file. Validate a three-file import completely before replacing any view. Reject incomplete or mixed snapshots, conflicting scoped source IDs, inconsistent canonical metadata and broken joins; retain the previous bundle on error. Keep V1's single dictionary CSV import available. A dictionary-only import must not leave old registry data presented as belonging to that new dictionary: either reconcile it against the active bundle or explicitly disable unmatched canonical views until a matching three-file bundle is loaded. Never silently join by display name.

Every export contains the current view's entire matched dataset and all original columns, independent of pagination. The dictionary's 106-column export remains one mapping and exact target per row. Preserve CSV quoting, Unicode, embedded newlines and JSON values. Do not collapse output rows merely to change presentation.

The built page is a saved local snapshot. It needs no adjacent JavaScript, server, model or external network request. Opening another file or rebuilding is explicit; neighboring CSV edits do not update an already embedded snapshot automatically.

## Validation and limits

Run `python -B .\02-skills\ultracs-data-dictionary-v3\generate.py --output .\03-output\01-baseline-next` with a new destination and check that its terminal result reports `status: passed`. Internal validation checks original-record reconstruction, exact target coverage, joins among all three tables, source/extract coordinate separation, description provenance, relationship assessments and CSV round-tripping before the checked snapshot is used to build the HTML. Read the current validation count from the terminal result; it can change with the input and schema. This simplified package has no separate validator, test runner or audit-report scripts to run. Use a temporary destination outside `03-output` for checks that must not publish a new latest viewer.

Generation uses an OS-managed writer lock to reject concurrent runs targeting the same output folder. CSV validation and HTML building finish in staging before delivery; backups support rollback on ordinary replacement failures, and HTML uses atomic temporary-file replacement. Locks and backups use the OS temporary directory, leaving no extra output files, and the OS releases the lock when the process ends. These safeguards were verified on macOS, not Windows; they do not guarantee an all-file transaction after power loss or forced termination such as `SIGKILL`.

Inspect the generated HTML in a browser when available: confirm the Dictionary's seven-column layout and controls, all three CSV tabs, complete details, target-specific processing, per-operation confidence, filters and exports. Test a matching three-file import and confirm an incomplete or conflicting import keeps the previous valid data. Internal checks validate the conversion; they do not replace browser interaction checks. Counts are input-specific controls, not hardcoded generation targets.

For the currently supplied inventory, the expected reconciliation is 95 original source mappings, 179 source/target rows, 464 represented canonical fields, 369 operations and 7 represented assets/contexts. The source mappings are not 95 independently established physical Ultracs attributes. These checks validate preservation and the supplied reported relationships, not source repositories, production runtime behavior or business correctness.

Keep work within the requested `dataDic` folder. Preserve the original input and any earlier versions stored elsewhere. Do not install this package globally, edit upstream repositories, call a model or refresh external lineage unless the user separately requests that work.
