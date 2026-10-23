# Account Data Lineage POC Findings

## Executive Summary

This proof of concept describes how account data is represented as moving from Ultracs through HVR and account ingestion into Snowflake and selected Enterprise dbt consumers. It parses checked-in source and configuration files. It is a **static repository view**, not a live production trace.

Current snapshot:

| Graph | Nodes | Relationships | Scope |
| --- | ---: | ---: | --- |
| Full repository graph | 2,005 | 3,033 | Parsed Ultracs, HVR, account Airflow/dbt, and schema-change evidence |
| Account slice | 39 | 65 | Focused DWACC/account route |
| Enterprise extension | 238 | 495 | Account context plus selected Enterprise consumer products |
| Column mapping inventory | 95 fields | 179 DBT targets | 112 internal and 67 public projections; 59 fields reach public models |

The workspace has five source/platform repositories plus this POC. The data path in scope uses Ultracs, HVR, the account tenant, and selected Enterprise products. `kb-ultracs-platform-admin` is an infrastructure/DR repository and is not currently part of the business-data graph.

## How to Read the Graph

A **node** represents an object such as a BASIC program, source file, extract, HVR channel, Airflow task, dbt model, or physical Snowflake relation. A **relationship** connects two node IDs and records the relationship type, direction, provenance, and confidence where available. The JSON graph is primarily table/process-level; the column mapping inventory is separate.

The graph contract is defined in the [authoritative schema](../src/lineage/data_lineage_schema.md). Important distinctions:

- `DBT_SOURCE` is a dbt declaration; `SNOWFLAKE_RELATION` is the physical object it resolves to.
- `DBT_MODEL` is transformation code; `MATERIALIZES_AS` connects it to its physical output.
- `READS_FROM` and `DEPENDS_ON` point toward dependencies. Reverse those edges for a conceptual source-to-consumer walk.
- The direct `ult_sf_acc` HVR route and the S3/Airflow route remain separate because repository evidence does not join them.

## Repository Contributions

| Repository | Contribution to this POC |
| --- | --- |
| [`kb-ultracs-datawarehouse`](../../kb-ultracs-datawarehouse/KWDW_ACC) | `KWDW_ACC` reads ACCOUNT and TRAN and writes the pipe-delimited DWACC extract. |
| [`kb-cdp-hvr`](../../kb-cdp-hvr/hvr-config/apps/channels/ult_s3_acc1.json) | HVR channel exports define file capture, conversion, and delivery paths; [`DWACC.param`](../../kb-cdp-hvr/hvr-config/scripts/DWACC.param) provides 95 ordered field names/positions. |
| [`kb-cdp-tenant-account`](../../kb-cdp-tenant-account/products/accounts-v1/airflow/accounts_v1/src/dags/accounts_v1_ingestion_v1.py) | Airflow copy/load declarations, account dbt sources/models, physical outputs, and schema migrations. |
| [`kb-cdp-tenant-enterprise`](../../kb-cdp-tenant-enterprise/products/int-account-v1/dbt) | Selected downstream account consumers, with dbt and schema-change evidence. |
| [`data-lineage-poc`](../README.md) | Read-only parsers, graph builders, validators, focused views, and this report. |
| [`kb-ultracs-platform-admin`](../../kb-ultracs-platform-admin/README.md) | Present in the workspace but outside the current business-data graph; operational scheduling/preload linkage needs validation. |

## Current Demo Views

1. Open the [column lineage viewer](output/column_lineage.html) in Detailed mode. Show `KWDW_ACC` reading ACCOUNT/TRAN and writing DWACC, then point out that the direct HVR and S3/Airflow routes are distinct.
2. Select **Schema overview**. The nested **Schema view** is the five-group simplified critical path; expanded nodes are selected from the generated payload. **Detail view** shows the earlier schema graph and its inspector.
3. Open a [focused Account Number graph](output/account_number_lineage.html) or [Authorisation Amount graph](../output/authorisationamount_lineage.html), and inspect its field-specific evidence and confidence.
4. Select **Data Dictionary** to show the V3 Dictionary, Asset Registry, and Field Catalog. The embedded snapshot contains 179 target rows, 95 source mappings, 369 relationships, 7 assets, and 464 fields.
5. Open the [Enterprise extension](output/account_enterprise_lineage.html). Explain that it is selected downstream context and table-level, not a full Enterprise catalog or column map.

For the complete field inventory, use the [column lineage graph](output/column_lineage.html). A reusable [generic schema diagram](generic_lineage_schema.svg) illustrates common lineage concepts; it is not the schema used by the detailed evidence graph.

## Column Mapping Inventory

DWACC.param declares 95 ordered fields. All 95 align by position with BASIC output expressions and internal DBT `DATA:` projections. Those fields produce 112 internal and 67 public DBT targets; 59 source fields reach public models. Public targets are included only when the public SQL selects the same internal column. Six `MissingColumn` slots are retained under their declared names with their BASIC expressions and DBT schema descriptions; no business meaning is invented for them.

| Representative field path | Ultracs source and transformation | DWACC / HVR field | Snowflake output and datatype | Confidence |
| --- | --- | --- | --- | --- |
| Account opened date | `ACCOUNT<1>`; `OCONV(AREC<1>, 'D4')` | `OpenDate` · 54 | `ACCOUNTOPENDATE` · `TIMESTAMP_TZ(9)` | Confirmed · 95% |
| Account name | `ACCOUNT<28,2>`; direct output | `AccountName` · 51 | `ACCOUNTNAME` · `VARCHAR` | Confirmed · 95% |
| Signatory count | `TRAN<4,4>`; output 1 when source value is zero, otherwise source value | `NumOfSignaturesReq` · 62 | `MINIMUMNUMBEROFAUTHORISER` · `NUMBER` | Confirmed · 95% |
| Account Index ID · CIS component | `ACCOUNT @ID`; `CIS = FIELD(NID, 'S', 1)` with legacy fallbacks | `Account` · 1 | `ACCESSNUMBER` · `VARCHAR(100)` | Inferred · 60% |
| Account Index ID · PID component | `ACCOUNT @ID`; `PID = ID[LEN(CIS)+1,9]` | `Prod` · 2 | `BANKINGPRODUCTCODE` · `VARCHAR(30)` | Inferred · 60% |
| Account ID | `TRAN<4,8>`; direct output | `KiwiAcc` · 7 | `KIWIBANKACCOUNTNUMBER` · `VARCHAR(100)` | Confirmed · 95% |
| Alternative account name | `TRAN<4,2>`; direct output | `AltAccountName` · 53 | `ALTERNATEACCOUNTNAME` · `VARCHAR` | Confirmed · 95% |
| End-of-day balance | `TRAN<1>` plus transaction detail; starts from REC<1> and applies post-run-date transaction adjustments | `Balance` · 5 | `ACCOUNTBALANCE` · `FLOAT` | Confirmed calculated · 90% |

This table shows representative examples; the complete 95-field inventory, including internal/public fan-out and provenance, is in [column_lineage.json](output/column_lineage.json). The Account Index ID composite remains inferred. The migration mapping sheet defines `Account_Index_ID` as a bank account number (`38 + source`) and `Account_ID` as the Ultracs account ID, while this POC labels the `CIS` + `PID` composite as `Account_Index_ID` and maps `REC<4,8>` as `Account_ID`. Resolve that naming conflict with the data owner before treating either identifier path as verified. Balance is calculated by BASIC and retains the `confirmed_calculated` evidence category.

### Mapping-Sheet Cross-Check

The workbook's **Data Mapping** sheet contains 9 `rFuel` source-to-ADS rows and 7 source-to-CDP rows for this slice. Comparison against the column payload in `column_lineage.html` gives the following field-level results. These are semantic comparisons: the POC ends in Snowflake/dbt columns, while the workbook names ADS/CDP fields, so they are not exact destination-schema validations.

| Path | Semantically aligned | Conflict | Unverified |
| --- | ---: | ---: | ---: |
| Source to ADS | 5 of 9 | 2 of 9 | 2 of 9 |
| Source to CDP | 3 of 7 | 2 of 7 | 2 of 7 |

Account opened date, account name, and alternative account name align across both paths. Signatory count and balance align with ADS fields. The two identifier rows conflict with the workbook's definitions. The `RWT_Rate_Code` and `NRWT_Tax_Rate` paths remain unverified because the graph does not establish their corresponding withholding-rate mappings. `Apply_Tax_Flag`, `Associated_Client`, and `Operational_Relationship_Code` are marked for transformation use in the workbook, not direct ADS/CDP output, so they are not counted as missing destinations.

## Object and History Counts

| Scope | Physical Snowflake relations | dbt models | Schemachange migration scripts |
| --- | ---: | ---: | ---: |
| Focused account slice | 8 | 6 | 6 |
| Selected Enterprise extension | 86 | 50 | 21 |

The Enterprise extension includes 20 dbt models connected in the focused schema overview; its broader graph retains additional dependency/context nodes. Four of the Enterprise repository's 34 product directories are selected; 30 are outside this account-focused extension.

“Migration scripts” means checked-in SQL files parsed for declared CREATE/ALTER targets. These counts do **not** say which scripts ran in production. The repository evidence does not establish a row-history window, live history-table count, or retention policy.

## Confidence Scale

Percentages are fixed heuristic evidence-strength labels, not statistical probabilities, runtime success rates, or guarantees.

| Graph label | Display score | Interpretation |
| --- | ---: | --- |
| `runtime_verified` | 100% | Reserved for an exact path observed in a successful production-equivalent run and corroborated against live object metadata. No current POC edge has this evidence. |
| `explicit` / `confirmed` | 95% | Direct repository code/configuration evidence; static configuration is not runtime verification. |
| `confirmed_calculated` | 90% | Calculation is documented, but the result is derived rather than a direct copy. |
| `declared_source` | 85% | Declared in repository metadata; not checked against a live catalog. |
| `inferred` | 60% | Supported indirectly, for example by filename-pattern matching or a proposed composite key. |
| `unconfirmed` | 50% | Candidate remains unresolved and needs owner/source validation. |
| Unknown / unresolved / missing | Not rated | No score is assigned without a recognized evidence category; missing confidence is not zero. |

The lowest numeric level currently defined is 50% (`unconfirmed`). These percentages are heuristic evidence-strength labels, not probabilities. For clean-run scoring rules and multi-hop handling, see the [confidence scoring skill](../skills/confidence_score_skill.md).

The graph viewers provide confidence-level checkboxes. All levels are selected initially; multiple levels can be combined. Filtering hides relationships but leaves endpoint nodes as context.

## Description Provenance

HTML graph descriptions carry origin tags:

- **Repository sourced**: description copied from checked-in BASIC, HVR, dbt, or other repository metadata.
- **Repository evidence**: a relationship summary comes from checked-in edge evidence or mapping notes.
- **Generated**: a literal node-role or edge-direction summary added when source text is unavailable. It is a navigation aid, not evidence or an authoritative data-dictionary definition.

HTML enrichment is applied to a copy of each graph payload. Canonical JSON remains unchanged. Enterprise continuation is table-level unless Enterprise sources establish column mappings and datatypes.

## Known Gaps

1. A source-to-consumer walk from ACCOUNT reverses the stored `PROGRAM --READS_FROM--> MV_FILE` direction.
2. `ult_sf_acc` lands in `LOADACCOUNTS_INGEST`; no checked-in evidence connects that relation to account-v1 RAW.
3. dbt dependencies connect models, and materialization edges connect models to physical relations, but there is no continuous physical-relation-only chain across every model boundary.
4. The graph preserves the matched HVR `Capture.Pattern`, representative filename, and evidence on inferred `CARRIED_BY` relationships. A filename-pattern match remains inferred because it does not prove runtime capture or delivery.
5. The Enterprise extension covers four selected products, not the entire 34-product repository, and its focused continuation is table-level.

## Clean Rebuild and Further Reading

For exact dependencies, commands, publication steps, and validation, follow the [runbook](RUNBOOK.md). Agent instructions are in [`CLAUDE.md`](../CLAUDE.md). Start at the [skills index](../skills/README.md), then see the [column-lineage skill](../skills/column_lineage_skill.md), [single-column explanation skill](../skills/column_lineage_explanation_skill.md), [HTML rendering rules](../skills/html_graph_render_skill.md), [JSON payload contract](../skills/json_payload_skill.md), and [graph traversal guidance](../skills/graph_traversal_skill.md).

Default focused work to **one requested column**. Keep `column_lineage.json` as the reusable 95-record inventory with 179 dbt target projections, and only generate multiple focused outputs when explicitly requested. The HTML pages are static local artifacts; repository content is not executed and no production service is queried.