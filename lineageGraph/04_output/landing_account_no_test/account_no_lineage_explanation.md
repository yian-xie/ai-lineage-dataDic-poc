# ACCESSNO Landing Lineage Test

## Scope

This is an isolated one-column trial in `output/landing_account_no_test/`. It parses only `kb-cdp-tenant-landing/products/ultracs-v1`; the other repositories are consulted only for selected source, route, consumer, and gap evidence. The canonical table and column graphs are not modified.

## Selected Column

`ACCESSNO` is the account-number example. `KWDW_FEE` reads the `CLIENT` record by `ID`, writes `ID` before the delimited fields to `DWFEE605.TXT`, and the header labels the leading field `AccessNo`. HVR captures that filename. The landing raw model parses payload field 1 as `NUMBER(38, 0)` and its YAML classifies the field as `SENSITIVE`.

The selected landing path is `feeexemption_raw` -> `feeexemption_delta` -> `feeexemption_history` -> `feeexemption` (`ULTRACS_PUBLIC`). The SQL and YAML retain `ACCESSNO` through those models; history uses it in its unique key. The account tenant separately declares `ultracs_landing.feeexemption` and its `feeexemption` model selects `ACCESSNO`.

## Five-Repository Placement

`kb-ultracs-datawarehouse` -> `kb-cdp-hvr` -> `kb-cdp-tenant-landing` -> `kb-cdp-tenant-account` -> selected `kb-cdp-tenant-enterprise` scope.

The first four repositories have field- or table-level evidence for this example. The selected Enterprise graph contains no `feeexemption` or `ACCESSNO` match, so no Enterprise continuation is drawn.

## Unjoined Relation Identities

1. HVR relation `snowflake:relation:FEEEXEMPTION_V1_INGEST` and landing source relation `snowflake:relation:{{ TARGET.DATABASE }}.ULTRACS_RAW.FEEEXEMPTION_V1_INGEST` share a base table name. The HVR export does not provide the target database/schema identity, so the graph leaves them disconnected.
2. Landing public relation `snowflake:relation:ULTRACS_PUBLIC.FEEEXEMPTION` and the account dbt source relation `snowflake:relation:{{ ENV_VAR('SNOWFLAKE_PIPELINE_DOMAIN_DATABASE') | REPLACE('ACCOUNT', 'LANDING') }}.ULTRACS_PUBLIC.FEEEXEMPTION` share `ULTRACS_PUBLIC.FEEEXEMPTION`. Their database values are different unevaluated templates (`target.database` versus an environment-variable expression), so the graph leaves them disconnected.

These are candidate joins, not edges. No inferred connection is inserted to make the picture look continuous.

## Gap Assessment

- **HVR pattern parser gap:** addressed for this path. The parser retains `Capture.Pattern`, and the existing table graph has an inferred `CARRIED_BY` match for `DWFEE605.TXT` -> `ult_sf_fee60`.
- **Direct HVR to account RAW bridge:** not addressed. This sample follows HVR direct landing into tenant landing; account-v1's separate `RAW` source path remains a different branch.
- **Physical relation continuity:** partially demonstrated at model level, not resolved generally. The landing dbt `ref()` chain is represented, but the two cross-repository physical identity joins remain unresolved as above.
- **Traversal direction:** unchanged. `READS_FROM` is stored PROGRAM -> MV_FILE; traverse it backward to narrate source -> program.
- **Enterprise column continuation:** none found for this selected field in the current Enterprise extension.

## Evidence Files

- `kb-ultracs-datawarehouse/KWDW_FEE`
- `kb-cdp-hvr/hvr-config/apps/channels/ult_sf_fee60.json`
- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/source.yml`
- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/feeexemption_raw/feeexemption_raw.sql` and `.yml`
- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/feeexemption_delta/feeexemption_delta.sql`
- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/feeexemption_history/feeexemption_history.sql` and `.yml`
- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/public/feeexemption/feeexemption.sql` and `.yml`
- `kb-cdp-tenant-account/products/accounts-v1/dbt/models/account_raw_source.yml` and `models/public/feeexemption/feeexemption.sql`

Static repository evidence only; no runtime jobs or Snowflake catalog were queried.
