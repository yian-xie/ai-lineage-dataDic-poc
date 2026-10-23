# Data Lineage POC Presentation Guide

## Purpose

Present the POC as a **static, evidence-backed lineage prototype** for the Ultracs account data path. It makes checked-in source/configuration relationships visible, lets the audience inspect a field mapping, and records where evidence stops. It is not a live production trace, a data-quality result, or a guarantee that a configured job ran.

**Suggested length:** 10–12 minutes, plus questions  
**Audience:** business, data, platform, and engineering stakeholders  
**Primary page:** `data-lineage-poc/output/column_lineage.html`  
**Focused example:** `data-lineage-poc/output/authorisationamount_lineage.html`

## Before the Demo

1. Run from the workspace root and confirm the generated pages are current.
2. Keep `column_lineage.html` and `column_lineage_dictionary.html` together. The Data Dictionary view loads the latter as a companion page.
3. Open the main column-lineage page. Its outer view starts in **Detailed**. The outer switch is **Detailed / Schema overview / Data Dictionary**.
4. If using the focused example, open the `Authorisation_Amount` graph in a second tab.
5. Be ready to distinguish the two Schema Overview presentations: nested **Schema view** is the generic five-stage diagram; nested **Detail view** is the older force-directed schema graph with the node inspector.

If rebuilding is required, use the ordered commands in `docs/RUNBOOK.md`. For a focused field refresh, use:

```powershell
python data-lineage-poc/generate_account_number_lineage.py --column Authorisation_Amount --output-prefix authorisationamount
```

The column generator writes the all-column page and its dictionary companion:

```powershell
python data-lineage-poc/generate_column_lineage.py
```

Do not rebuild the full parser graph during a presentation unless its inputs changed or you explicitly need a clean rebuild.

## Presenter Script

### 1. Set Expectations · 1 minute

**Show:** Main lineage page.

**Say:**

> This proof of concept builds a view of the account-data lineage from repository source and configuration. It shows what those files declare and what our parsers can connect. It does not query production systems or prove that a job ran successfully.

> The goal today is to see how we can inspect a path, understand its evidence and confidence, and make unresolved handoffs visible rather than guessing them.

**Emphasize:** Static repository evidence only; no production credentials or customer rows are needed for this demo.

### 2. Explain What the Graph Represents · 1 minute

**Show:** Detailed graph and one or two node/edge inspectors.

**Say:**

> Nodes represent things such as Ultracs files and programs, extracts, HVR channels, Airflow tasks, dbt models, and physical Snowflake relations. Edges represent declared or inferred relationships between those objects. Each relationship can carry source paths, evidence, and a confidence category.

> The detailed graph has 39 account-slice nodes and 65 relationships. The separate Enterprise extension has 238 nodes and 495 relationships. Those are graph-object counts, not counts of tables, records, or columns.

When inspecting an edge, point out its stored direction, type, confidence, description origin, and source path. A generated description explains the graph object; it is not additional evidence.

### 3. Show the Schema Overview Toggle · 2 minutes

**Show:** Click the outer **Schema overview** button. The nested toggle appears above the graph.

**Say:**

> Schema view is a five-group fan-out: Source, Extract, Staging, Jobs, and Target. Shape identifies the group and color identifies the technical node type. It shows only the selected critical path; the direct HVR landing branch is not shown in this simplified view.

> Expanding a group reveals the selected technical nodes. Selecting one opens the existing inspector with its properties and relationships. Collapsing the group clears its nodes and connectors, and closes the inspector if it was showing one of that group’s nodes.

Expand the five groups to show the fan-out. Connectors are presentation-only and do not add relationships to canonical graph JSON. The direct HVR landing is intentionally left out here; inspect it in Detailed mode.

**Then click nested Detail view. Say:**

> This is the previous force-directed schema graph. It keeps the original node/relationship inspector, confidence filters, and schema editing controls. The graph is generated from the same schema payload; the generic five-stage view is only another presentation of the schema context.

> The target is the public account detail relation. The side branch to `LOADACCOUNTS_INGEST` is not displayed in the simplified Schema view because the repository does not establish that it feeds the account RAW/dbt route.

Return to nested Schema view, then click outer **Detailed** to show the full table graph again.

### 4. Trace the Account Route and Its Limits · 2 minutes

**Show:** In Detailed, inspect `KWDW_ACC`, `ACCOUNT`, `TRAN`, `DWACC`, and the HVR/Airflow/Snowflake nodes.

**Say:**

> The account slice shows the BASIC program reading ACCOUNT and TRAN and writing the DWACC extract. The repository also declares two HVR routes: a direct HVR-to-Snowflake landing and a separate S3/Airflow route to the accounts-v1 RAW relation.

> These routes are kept separate because the checked-in evidence does not establish that the direct `LOADACCOUNTS_INGEST` relation feeds account-v1 RAW. The capture-pattern association is marked inferred. The graph makes that boundary visible instead of drawing a continuous path without evidence.

Explain direction where needed: `READS_FROM` is stored `PROGRAM → MV_FILE`; reverse it for the conceptual source-to-consumer narration. The graph’s stored arrow is not always the direction used in a verbal lineage walk.

### 5. Follow One Column · 2 minutes

**Show:** Open the focused [Authorisation_Amount lineage page](../output/authorisationamount_lineage.html).

**Say:**

> This focused view follows `Authorisation_Amount` at DWACC position 93 to `AUTHORISATION_AMOUNT` in the public EOD balances relation, with datatype `FLOAT`. The column mapping is supported by the BASIC output, HVR parameter position, and dbt projection metadata.

> The column mapping’s confidence describes the evidence for that mapping. The route’s HVR capture-pattern association is a separate inferred hop. A score on one mapping must not be treated as a probability or as runtime verification of the entire route.

Show the evidence notes link and the separate direct-HVR branch explanation. Avoid describing this as a live sample value or a production execution.

### 6. Show the Data Dictionary · 1.5 minutes

**Show:** Return to the main page and select **Data Dictionary**.

**Say:**

> This view contains the V3 dictionary and registry workflow. It supports the embedded snapshot, loading a single CSV or a matching three-file bundle, advanced filters, custom conditions, sorting, pagination, row-level evidence, and filtered exports. Asset Registry and Field Catalog are separate tabs.

> The embedded snapshot contains 179 source-to-target rows, 95 source mappings, 369 recorded operations, 7 assets, and 464 catalog fields. Unknown governance stays unknown; blank ownership, PII, or business-definition values are not inferred.

When asked about a dictionary field, open a row detail and distinguish supplied metadata from reviewed business definitions. Exported CSV retains the original columns and matched rows.

### 7. Demonstrate the Query Tool · 1 minute

**Show:** Terminal at the workspace root, if appropriate for the audience.

```powershell
python data-lineage-poc/query_graph.py --search ACCOUNT --limit 10
python data-lineage-poc/query_graph.py --trace basic:file:ACCOUNT --direction downstream --depth 6
python data-lineage-poc/query_graph.py --column AltAccountName
```

**Say:**

> The CLI searches the generated JSON snapshots; it does not query Snowflake or HVR. For Python callers, `query_tools.tools` also provides `get_field_lineage`, `get_consumers`, and `get_alias_chain`. Results include graph nodes/edges and confidence, and a missing path is reported as a gap rather than invented.

### 8. Close · 30 seconds

**Say:**

> The POC’s value is a reviewable path with evidence and explicit boundaries. The next step is not to make the graph look more complete; it is to validate the open handoffs with the right owners or runtime/catalog evidence, then update the parsers and regenerate the snapshots.

## Likely Questions

**Does this prove what ran in production?**  
No. It parses checked-in source, configuration, SQL, YAML, and migration files. Production-equivalent runtime evidence and catalog checks would be required for that claim.

**How deterministic is the graph?**  
For unchanged inputs and generator code, the graph data is reproducible. The force-directed visual layout may reposition nodes between browser loads because it uses a physics simulation.

**Why are some links inferred?**  
The repository provides indirect evidence for those associations, such as a filename matching an HVR capture pattern. They remain explicitly marked inferred until a stronger source or runtime check confirms them.

**Why does `READS_FROM` point toward the source file?**  
That is the stored relationship convention: the program reads from the file. For conceptual forward data flow, traverse that relationship in reverse and say so.

**Does the direct HVR landing feed the account RAW table?**  
The current repository graph does not establish that connection. The direct `ult_sf_acc` route ends at `LOADACCOUNTS_INGEST`; the S3/Airflow route loads `RAW.ACCOUNTS_V1__ACCOUNTS`. Do not join them without new evidence.

**Does the Enterprise view provide column-level lineage?**  
Not generally. The selected Enterprise extension is parser-backed at table/model level. It does not infer column mappings or datatypes where the repository contains no such evidence.

**Are all 95 DWACC fields mapped publicly?**  
The inventory has 95 ordered fields and 179 projections: 112 internal and 67 public. Some fields end at internal targets; public outputs are included only where supported by the model SQL/schema.

**Why is Account Index ID inferred?**  
The `Account` and `Prod` components are mapped separately, but the downstream composite-key definition needs domain-owner confirmation. Do not present the combined key as confirmed.

**What does the percentage mean?**  
It is a fixed evidence-strength heuristic tied to the confidence category. It is not a statistical probability, runtime success rate, or guarantee.

**Can I edit schema values?**  
The old schema Detail view has browser-local display-name/datatype overrides. They do not modify repository source or canonical graph JSON. Reset edits clears those local overrides.

**Can the POC publish to Neo4j or Neptune?**  
Exporter functions and a sample graph export exist, but the current parser-driven pipeline produces JSON and HTML snapshots. A live graph-service connection is not part of this demonstration.

**What should be validated next?**  
Confirm the direct-HVR-to-RAW bridge, confirm the Account Index ID definition, and identify an approved runtime/catalog evidence source.

## Presenter Guardrails

- Say “repository evidence shows” or “the configuration declares,” not “production does.”
- Keep the direct HVR and S3/Airflow branches separate.
- State confidence for each relevant hop; do not average confidence across a route.
- Do not infer missing dictionary metadata, field mappings, or Enterprise column lineage.
- If a path stops, present the gap as a question for validation.
- Keep `column_lineage.html` with its sibling `column_lineage_dictionary.html` when copying or publishing the POC viewer.
