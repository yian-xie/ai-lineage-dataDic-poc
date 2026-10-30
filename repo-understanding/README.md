# Understanding the additional source repositories

Reviewed: 2026-10-30.

This is the read-only understanding step for **kb-cdp-tenant-landing** and
**kb-cdp-tenant-protect-downstream**. It records their structure, relevant data
flows, evidence boundaries and the work needed before integrating their metadata
into the main lineage report.

**No parser, graph builder, confidence rule, dictionary data or generated HTML
was changed. No source jobs, migrations, dbt builds or repository tests were run.**
The accompanying application README changes only make this report discoverable
and describe the six downloaded repositories.

## How these two repositories help us

**Yes, they add useful lineage evidence, but they do not prove one complete
production flow.** Landing explains more of the processing before domain
consumption; Protect-downstream explains additional consumers, transformations
and output boundaries. Their value is both greater coverage and fewer incorrect
connections.

| Repository | What we can understand better | Practical benefit |
| --- | --- | --- |
| Landing | How an HVR-style payload position becomes a typed column, how changes/history are handled, and which public view a domain product consumes. | Explain the field's technical origin and processing instead of stopping at a raw table name. |
| Protect-downstream | Which Account/Enterprise interfaces are consumed, how fields are renamed, joined, filtered or combined, and which outputs are configured for export. | Identify additional downstream dependencies and assess which consumers might be affected by an upstream change. |
| Both together | Exact field identities, transformations, configuration constraints and missing evidence at repository boundaries. | Improve lineage explanations and dictionary provenance without inventing missing links or business meanings. |

### Concrete examples from this review

1. **Landing adds positional and transformation evidence.**
   Its [new-account raw SQL](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/loadnewaccounts_raw/loadnewaccounts_raw.sql)
   converts payload position 6 into timestamp field `COL_004`, using explicit
   date-format alternatives. The subsequent Landing and Account projections are
   documented in section 5.3. This is a new-account feed identity, not proof
   that it is the existing DWACC position 54 / `OpenDate`.
2. **Protect extends a known Account field into staging.**
   Its [Ultracs account SQL](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__ultracs_account.sql)
   reads the Account public interface and renames `KIWIBANKACCOUNTNUMBER` to
   `ACCOUNTNUMBER`. The [combined model](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__combined_account.sql)
   projects it as `ACCOUNT_NUMBER`. This identifies a downstream dependency to
   consider when changing the Account field; it does not prove that the Ultracs
   value reaches every final SADP file.
3. **Protect prevents a false opening-date continuation.**
   That combined model assigns `NULL` to `ACCOUNT_OPEN_DATE` in its Ultracs
   branch. A model-to-model dependency therefore cannot justify a value-lineage
   edge from the original Ultracs opening date to this output.
4. **Protect distinguishes candidate code from enabled paths.**
   The [Ultracs new-account model declaration](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1/dbt/models/internal/sys_pds_newaccount_v1__ultracs_account.yml)
   disables the version containing the `COL_004`-to-`OPENDATE` expression.
   The code helps explain a candidate transformation, but it must not be shown
   as an enabled end-to-end route. Section 5.4 also records the parent model's
   disabled union version and selected default version.

### What this does not mean

- The review verified representative paths, not every field in both repositories.
- Additional repository evidence does not automatically raise confidence scores.
  An assessment must still address the exact mapping and its unresolved checks.
- Static code and configuration do not prove successful production execution,
  live-object identity or delivery of an exported file.
- Adding these repositories does not resolve every HVR handoff or create a
  universal route through all six repositories.
- These findings improve our understanding now, but **have not yet been
  integrated into the main lineage JSON, dictionary or combined HTML**.
  The existing optional Landing support is not the same as that integration.

## 1. Scope and method

The review inventoried tracked files in both repositories, read SQL, YAML,
Markdown, Python and Jinja metadata, and examined the relevant account/Ultracs
paths in detail. It compared those paths with the existing Account, HVR and
application parser implementations.

| Measure | Landing | Protect-downstream |
| --- | ---: | ---: |
| Tracked files inventoried | 6,976 | 840 |
| Product directories | 59 | 10 |
| Metadata text files read | 5,870 | 550 |
| Distinct metadata contents within that repository | 5,427 | 436 |
| SQL files under dbt model directories | 2,474 | 77 |
| Credential/profile paths excluded from content reads | 59 | 10 |

These are source-file counts, not deployed-object counts or proven lineage
edges. Model SQL counts include alternative and disabled implementations.
Inventorying all products does not mean every column in every product has been
independently traced.

The detailed review focuses on Landing's `ultracs-v1` product and Protect's
account staging, account and new-account products. Other products were
structurally inventoried and their source/model metadata read for context.
Images, locked dependencies and external Confluence/SharePoint documents were
not treated as independently verified mapping evidence. Credentials, Git
internals and runtime services were not accessed.

Evidence links below resolve against the local, Git-ignored source checkouts.
They describe the following revisions, not necessarily today's production state.

## 2. Source revisions

| Repository | Reviewed commit |
| --- | --- |
| [kb-cdp-tenant-landing](../source-repos/kb-cdp-tenant-landing) | `d098fa5d2fc3118083bc1c7f69d40af7c5051495` |
| [kb-cdp-tenant-protect-downstream](../source-repos/kb-cdp-tenant-protect-downstream) | `4f486f8d0cef2b09ae187c4ae766cc1088205ccf` |
| [kb-cdp-tenant-account](../source-repos/kb-cdp-tenant-account) | `bb5b71a0c875ee58009456d963fa71a9ff23f415` |
| [kb-cdp-hvr](../source-repos/kb-cdp-hvr) | `80b1eed1ea10aa423693195158a7f79bbbd3dc0e` |
| [kb-cdp-tenant-enterprise](../source-repos/kb-cdp-tenant-enterprise) | `e57ca0a55cded4747b95b34ef1b751f4d0f3cc5f` |
| [kb-ultracs-datawarehouse](../source-repos/kb-ultracs-datawarehouse) | `56e3bf8d6c92ef02ec6014d0940e599d44f60e5e` |

## 3. Landing: what it does

### 3.1 Repository role

Landing contains source-system-aligned dbt products. For the reviewed Ultracs
path, it converts HVR-style `PAYLOAD` rows into typed fields, processes changes
and history, and publishes views for downstream domain products.

Its top-level [README](../source-repos/kb-cdp-tenant-landing/README.md) is a
placeholder. The [Ultracs product README](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/README.md)
also retains extensive template guidance. The SQL, model configuration and
pipeline configuration are therefore stronger evidence of this snapshot's
declared behavior than those descriptive templates.

The repository is broader than Ultracs. Its largest model inventories include
Ultracs (390), Activate KB (316), Activate BB (248), SDT CRM (248), TMS (226)
and RoeCalc (188). Those numbers do not make those other systems part of the
current account lineage scope.

### 3.2 Ultracs structure and identities

The [dbt project](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/dbt_project.yml)
contains 390 model SQL files:

- 286 under internal model directories and 104 under public model directories.
- Model YAML declares 208 views and 182 incremental models.
- The [source declaration](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/source.yml)
  names 109 ingestion tables in `ULTRACS_RAW`, using `target.database`.
- Static source-call inspection finds 103 distinct referenced ingestion names,
  all declared. Six declarations have no corresponding source call in this
  product's model SQL; declarations alone must not create data-flow edges.
- Raw/internal models use `ULTRACS_INTERNAL` (including lower-case spelling in
  some configuration); public views use `ULTRACS_PUBLIC`.

The [schema override macro](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/macros/custom_schema_override.sql)
uses the supplied custom schema directly rather than automatically concatenating
it with the target schema. The [source/ref override](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/macros/source_ref_override.sql)
delegates to the dbt unit-testing package. These macros are configuration
context; they were read, not executed.

The [pipeline configuration](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/pipeline/pipeline.yaml)
declares `SIT_LANDING`, `PREPROD_LANDING` and `PROD_LANDING` targets and a
Snowflake task schedule. Its production cron expression specifies 01:30, 02:30,
03:30, 05:30, 07:30, 08:30 and 12:30 in `Pacific/Auckland`. This is a declared
schedule, not evidence that a deployed task ran successfully.

### 3.3 Representative processing: loadnewaccounts

The repository supports this model-level chain:

```text
ULTRACS_RAW.LOADNEWACCOUNTS_INGEST
  -> ULTRACS_INTERNAL.LOADNEWACCOUNTS_RAW          typed view
  -> ULTRACS_INTERNAL.LOADNEWACCOUNTS_DELTA        incremental append
  -> ULTRACS_INTERNAL.LOADNEWACCOUNTS_HISTORY      incremental merge/history
  -> ULTRACS_PUBLIC.LOADNEWACCOUNTS                public view
```

Evidence:

1. [Raw SQL](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/loadnewaccounts_raw/loadnewaccounts_raw.sql)
   splits the pipe-delimited payload. Position 1 becomes `NEWACCOUNT`, position 2
   becomes `PRODUCT`, and position 6 is parsed into timestamp field `COL_004`
   using several explicit date formats. The original positional identity must
   remain distinct from a later business label such as `OPENDATE`.
2. [Delta SQL](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/loadnewaccounts_delta/loadnewaccounts_delta.sql)
   reads the raw model, handles snapshots/deletions and incremental state.
   [Its configuration](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/loadnewaccounts_delta/loadnewaccounts_delta.yml)
   declares append materialization.
3. [History SQL](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/loadnewaccounts_history/loadnewaccounts_history.sql)
   retains historical/current state.
   [Its configuration](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/loadnewaccounts_history/loadnewaccounts_history.yml)
   uses a merge key of `NEWACCOUNT`, `PRODUCT`, `COL_025`, `VERSIONSTARTDATE`.
4. [Public SQL](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/public/loadnewaccounts/loadnewaccounts.sql)
   projects the history fields and derives a version number.
   [Its configuration](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/public/loadnewaccounts/loadnewaccounts.yml)
   declares the `ULTRACS_PUBLIC` view.

This is not a claim that every Landing feed uses identical keys, date formats
or deletion semantics. Each feed requires its own field-level evidence.

### 3.4 HVR boundary and the existing DWACC route

The HVR [ult_sf_ac declaration](../source-repos/kb-cdp-hvr/hvr-config/apps/channels/ult_sf_ac.json)
captures an `AC...TXT` filename pattern and declares `loadnewaccounts_ingest`
with `payload` and `integration_timestamp` columns. The
[ult_sf_fee60 declaration](../source-repos/kb-cdp-hvr/hvr-config/apps/channels/ult_sf_fee60.json)
similarly names `feeexemption_v1_ingest`, consumed by Landing's
[feeexemption raw model](../source-repos/kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/feeexemption_raw/feeexemption_raw.sql).
Those declarations corroborate the table names and payload shape, but the
reviewed channel files do not independently establish the deployed target's
full database/schema binding.

Importantly, HVR's [ult_sf_acc declaration](../source-repos/kb-cdp-hvr/hvr-config/apps/channels/ult_sf_acc.json)
lands the direct DWACC branch in `loadaccounts_ingest`. That table is **not**
declared in this revision of Landing's Ultracs source list. Do not equate it
with `loadnewaccounts_ingest`, or connect it to the existing Account
`RAW.ACCOUNTS_V1__ACCOUNTS` route merely because the names are similar.

## 4. Protect-downstream: what it does

### 4.1 Repository role

Protect builds system-aligned data products (SADPs), downstream-compatible
outputs and assurance controls. It is not an AI privacy-protection component.
The [account staging design](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/README.md)
describes a transition from Enterprise IDP dependencies toward domain/raw-aligned
inputs. Actual reviewed SQL consumes declared domain `PUBLIC` interfaces and
Protect `STAGE` tables; the word "RAW" in the design does not mean every input
is a physical object in a schema named `RAW`.

The top-level [README](../source-repos/kb-cdp-tenant-protect-downstream/README.md)
is a placeholder, but several product READMEs contain substantial design and
transition information. Design descriptions of future behavior must still be
checked against enabled model versions.

### 4.2 Product inventory

| Product | Model SQL files | Snapshot role / declared output area |
| --- | ---: | --- |
| [sys-pds-stg-account-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1) | 9 | Account/balance/relationship staging; seven STAGE and two INTERNAL SQL files. |
| [sys-pds-stg-customer-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-customer-v1) | 3 | Customer staging. |
| [sys-pds-stg-trans-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-trans-v1) | 3 | Transaction staging. |
| [sys_pds_account_v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys_pds_account_v1) | 9 | Account SADP and PUBLIC account view. The directory uses underscores. |
| [sys-pds-newaccount-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1) | 10 | New-account SADP and PUBLIC new-account view. |
| [sys-pds-accountbal-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-accountbal-v1) | 6 | Account-balance SADP. |
| [sys-pds-accountrel-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-accountrel-v1) | 6 | Account-relationship SADP. |
| [sys-pds-accounttransdet-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-accounttransdet-v1) | 14 | Transaction, transaction-detail, legacy transaction and withholding-tax outputs. |
| [sys-pds-da-controls-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-da-controls-v1) | 14 | Data-assurance validation and summary/detail outputs. |
| [sys-pds-dra-controls-v1](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-dra-controls-v1) | 3 | Delivered Risk Assessment controls. |

The total is 77 model SQL files. Fifteen YAML model declarations are versioned.
These counts must not be presented as 77 enabled, deployed datasets.

Source groups include Account and Enterprise public interfaces, Protect internal
and staging relations, and dependencies on other domains such as Party and
Markets/Treasury. Some dependencies are outside the repositories or product
scopes currently covered by the application.

The [staging source definitions](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/sources.yml)
derive domain databases from `SNOWFLAKE_PIPELINE_DOMAIN_DATABASE`, for example
replacing `PROTECTDS` with `ACCOUNT` or `ENTERPRISE`. This supplies an explicit
environment-relative naming rule, not live-catalog verification.

### 4.3 Orchestration and delivery

Static inspection found 11 DAG declarations. The
[account staging DAG](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/airflow/sys_pds_stg_account_v1/src/dags/generate_pds_stg_account.py)
declares a build every 20 minutes during hours 0 through 10 in the configured
New Zealand timezone, with source-freshness checks. Its default selector builds
models under the stage directory.

The [new-account DAG](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1/airflow/sys_pds_newaccount_v1/src/dags/generate_pds_newaccount.py)
declares `30 3 * * *`, runs a dbt build, and then invokes the external Airflow
library to unload `PUBLIC.SYS_PDS_NEWACCOUNT_V1__ACCOUNT` to a dated
`CDP_AC...TXT` file in S3. The declaration, library invocation and task ordering
are evidence; successful extraction or subsequent on-premises delivery was not
observed. Comments mentioning other schedule times are not preferred over the
actual cron argument.

The repository contains 46 SQL files under dbt test directories. All 79 tracked
Python files were syntax-parsed without importing them; no syntax errors were
reported. Ten Python test functions were identified, but **none were executed**.
Declared tests, disabled tests and successful test runs are different facts.

## 5. Verified representative connections

### 5.1 Existing DWACC Account_ID reaches Protect staging, with limits

The existing Account
[internal SQL](../source-repos/kb-cdp-tenant-account/products/accounts-v1/dbt/models/internal/accounts_v1__ultracs_accounts_detail_v2/accounts_v1__ultracs_accounts_detail_v2.sql)
maps `DATA:KiwiAcc` to `KIWIBANKACCOUNTNUMBER` and `DATA:OpenDate` through its
date macro to `ACCOUNTOPENDATE`. The
[public SQL](../source-repos/kb-cdp-tenant-account/products/accounts-v1/dbt/models/public/accounts_v1__ultracs_accounts_detail/accounts_v1__ultracs_accounts_detail.sql)
projects both columns.

Protect's [Ultracs account SQL](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__ultracs_account.sql)
then explicitly reads `account_public_views.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL`
and projects:

```text
KIWIBANKACCOUNTNUMBER -> ACCOUNTNUMBER
ACCOUNTOPENDATE       -> CAST(... AS TIMESTAMP_TZ(9)) AS ACCOUNTOPENDATE
```

The [combined account SQL](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__combined_account.sql)
preserves the first field as `ULTRACS.ACCOUNTNUMBER AS ACCOUNT_NUMBER`.
The [stage history model](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__account_v1.sql)
reads the combined model, and
[its configuration](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__account_v1.yml)
declares `STAGE` incremental merge materialization.

This establishes a repository-configured continuation into Protect staging.
It does not prove that the entire historical dataset reaches a downstream file.
For example, the latest declared
[Account version 2 SQL](../source-repos/kb-cdp-tenant-protect-downstream/products/sys_pds_account_v1/dbt/models/internal/sys_pds_account_v1__account_v2.sql)
filters the relevant account input to `RECORD_SOURCE = 'TMV'`.

### 5.2 Counterexample: DWACC OpenDate does not continue through that union

The same combined account SQL sets this value in its **Ultracs branch**:

```sql
CAST(NULL AS TIMESTAMP_TZ(9)) AS ACCOUNT_OPEN_DATE
```

Its TMV branch instead supplies `TMV.ACCOUNTOPENEDDATETIME`.
Therefore the earlier Ultracs `ACCOUNTOPENDATE` is not a value dependency of
that combined Ultracs `ACCOUNT_OPEN_DATE` output. A table dependency between
the models is insufficient to draw that column edge.

This is a source behavior observation, not an implementation bug corrected by
this review. Confirm the intended field contract with the product owner before
changing the source logic or claiming the date is preserved.

### 5.3 Landing loadnewaccounts reaches an Account public interface

Account's [source declaration](../source-repos/kb-cdp-tenant-account/products/accounts-v1/dbt/models/account_raw_source.yml)
names `ultracs_landing.loadnewaccounts` in `ULTRACS_PUBLIC`, deriving the database
by replacing `ACCOUNT` with `LANDING`.
Its [new-account public model](../source-repos/kb-cdp-tenant-account/products/accounts-v1/dbt/models/public/accounts_v1__ultracs_new_accounts/accounts_v1__ultracs_new_accounts.sql)
reads that source, renames `NEWACCOUNT` to `ACCESSNUMBER`, renames `PRODUCT` to
`BANKINGPRODUCTCODE`, and retains `COL_004`.

Together with the Landing public model, this supports the declared,
environment-relative boundary:

```text
Landing.ULTRACS_PUBLIC.LOADNEWACCOUNTS.COL_004
  -> Account.PUBLIC.ACCOUNTS_V1__ULTRACS_NEW_ACCOUNTS.COL_004
```

It is a different feed and field identity from DWACC position 54 / `OpenDate`.
Matching future business labels must not merge those identities.

### 5.4 Protect's apparent Ultracs new-account continuation is disabled

Protect's [Ultracs new-account SQL](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1/dbt/models/internal/sys_pds_newaccount_v1__ultracs_account_v1.sql)
reads the Account new-account interface, selects current records updated today,
and defines `TO_CHAR(COL_004, 'DD/MM/YYYY') AS OPENDATE`.
However, [its model declaration](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1/dbt/models/internal/sys_pds_newaccount_v1__ultracs_account.yml)
marks version 1 **enabled: false**.

The [new-account version 3 SQL](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1/dbt/models/internal/sys_pds_newaccount_v1__account_v3.sql)
contains a TMV/Ultracs union, but
[the parent model declaration](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1/dbt/models/internal/sys_pds_newaccount_v1__account.yml)
also disables version 3 and sets **latest_version: 2**.

The [PUBLIC new-account view](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1/dbt/models/public/sys_pds_newaccount_v1__account_vw.sql)
uses an unversioned ref to that parent model and overrides its physical alias to
`sys_pds_newaccount_v1__account`. Its declared default is consequently version 2,
whose [SQL](../source-repos/kb-cdp-tenant-protect-downstream/products/sys-pds-newaccount-v1/dbt/models/internal/sys_pds_newaccount_v1__account_v2.sql)
selects TMV staging records.

The disabled Ultracs expression is useful candidate mapping evidence, but is
**not an enabled source-to-public/file path in this snapshot**.

## 6. Fit with the current lineage application

| Surface | Current behavior | Integration implication |
| --- | --- | --- |
| [Repository configuration](../sources.json) | Lists all six repositories for download/verification. | Download availability is not parser or graph coverage. |
| [Snapshot discovery](../src/lineage_poc/parsers/snapshot.py) | Supports four required repositories and optional Landing; no Protect discovery. | Add explicit Protect metadata discovery and recorded revision handling before claiming coverage. |
| [Landing parse hook](../src/lineage_poc/lineage_workflow.py) | An all-parser run can capture Landing and create a separate fragment. | Existing support is reusable; it currently scans Landing broadly, not just Ultracs. |
| [Landing adapter](../src/lineage_poc/parsers/landing.py) | Namespaces models/sources by Landing product. | Reuse the identity principle, not the hard-coded Landing namespace, for Protect. |
| [dbt parser](../src/lineage_poc/parsers/dbt.py) | Matches model declarations to SQL stems and reads top-level model config. It does not resolve these version declarations, version enablement or SQL alias overrides. | Resolve versions/aliases/config before attaching physical targets or presenting enabled paths. |
| [Airflow parser](../src/lineage_poc/parsers/airflow.py) | Includes account-ingestion-specific file-map logic and special handling for `run_dbt_bash`. | Protect's build/export tasks and environment-dependent destinations require their own explicit extraction support. |
| [Graph composition](../src/lineage_poc/lineage_workflow.py) | Landing can be emitted as `landing_tenant_lineage.json`, separately from the main table graph. | Do not assume it has already been joined into the combined report. |
| [DWACC column builder](../src/lineage_poc/columns/dwacc.py) | Builds the existing DWACC-to-Account mappings. | It is not a general SQL lineage engine for Protect joins, unions, filters, versioned refs and constant outputs. |

Namespacing is necessary, not optional: Protect repeats SQL model names such as
`int_account_v1__account`, `int_account_v1__balance` and
`int_customer_v1__customer_details` across independent products. Other repeated
names include product-code masters and transaction-detail masters. A merge by
unqualified model name would incorrectly combine separate project identities.

Physical relation identity also needs database, schema, alias, model version
and environment context. Preserve unresolved expressions rather than evaluating
them against guessed production settings.

## 7. Evidence boundaries and questions to resolve

1. **Enabled is not deployed.** Configured enablement, source declarations and
   cron schedules do not establish production catalog state or successful runs.
2. **HVR handoffs need full identity.** The matching raw table names above do not
   by themselves independently confirm HVR location-to-Landing database/schema
   bindings.
3. **No universal six-repository chain exists.** The existing DWACC S3 route,
   direct-HVR branches, Landing feeds, Enterprise dependencies and Protect
   outputs are distinct paths. They cannot be concatenated just to include
   every repository in a diagram.
4. **Inactive paths must be labelled.** Decide whether later reports should show
   disabled/alternative versions as separate candidate views or omit them from
   the default enabled view. Do not silently promote them to active lineage.
5. **Fields can stop at joins/unions/filters.** Preserve branch conditions,
   row filters and literal/null assignments. The OpenDate counterexample above
   must be a regression case for any future column-lineage extension.
6. **Cross-domain coverage is incomplete.** Preserve Party, Markets/Treasury and
   out-of-scope Account/Enterprise inputs as external boundaries until their
   defining metadata is actually included.
7. **Business approval remains separate.** A copied/generated description or
   a `SENSITIVE` classification does not establish an approved business
   definition, owner review, PII assessment or field equivalence.
8. **Operational delivery remains unverified.** Source code invoking an external
   export library does not prove a file arrived in S3 or on-premises.

No new numeric confidence was assigned. Existing mapping labels and fixed
display percentages were not changed. AI description confidence, lineage
confidence and operational verification remain separate concepts.

## 8. Recommended next implementation step - not performed

Start with Landing `ultracs-v1` and the three Protect products examined in
detail: account staging, Account SADP and New Account SADP. Expand to other
products only after the relevant dependency boundaries are clear.

1. Add tests and parser handling for versioned refs, latest-version selection,
   disabled versions and physical aliases before integrating Protect.
2. Extend snapshot discovery/provenance for the selected Protect products,
   keeping the source checkouts read-only and the selected files reproducible.
3. Build product-scoped fragments and explicit cross-repository relation
   matches, without silently merging the standalone Landing graph.
4. Test the positive Account_ID-to-stage projection, the OpenDate null barrier,
   the disabled new-account branch and the missing DWACC direct-Landing bridge.
5. Only then extend supported column mappings and regenerate the affected
   dictionary, validation and combined HTML stages. Preserve current inputs and
   clearly mark table-level-only continuations.

This review did not implement that work or rerun those stages.

## 9. Review checks and limitations

- Both new repository inventories and cross-repository source references were
  inspected at the commits listed above. Their worktrees remained clean.
- YAML inspection identified 53 Landing schemachange configurations containing
  unrendered Jinja and one Protect account-relationship configuration containing
  unquoted Jinja expressions. A generic YAML parser cannot consume those files
  as supplied. They require the appropriate rendering context; this observation
  is not a claim that a deployed schemachange run failed.
- Python syntax checks used AST parsing only. No DAG imports, environment-secret
  reads, repository tests, database connections or external document requests
  were performed.
- The pipeline output inventory remained 98 files, with aggregate SHA-256
  `fbe35417867e5336bef75efcc8e9b2c5dc6e3ff6335e19b537b649db38f752e4`.
  This preservation check hashes sorted relative paths and file bytes; it is
  not a business-data correctness or runtime verification claim.
- Local documentation links were checked against the source checkouts.
  Future pulls may change the cited implementation; revisit this report after
  updating a source revision.
