# Account Slice: End-to-End Column Report

Source: `data-lineage-poc/output/column_lineage.json` (95 records). Scope: `KWDW_ACC` -> `DWACC` extract -> HVR `ult_s3_acc1`/`ult_s3_acc2` -> S3/Datalake -> Airflow `accounts_v1_ingestion_v1` -> `RAW.ACCOUNTS_V1__ACCOUNTS` -> accounts-v1 dbt internal and public models.

All figures are counted from the JSON and come from checked-in repository files (static evidence, not runtime verification).

## Headline Numbers

| Measure | Count |
| --- | ---: |
| Mapping records (one per `DWACC.param` position) | **95** |
| Unique `.param` column names | 95 |
| Unique business-field labels | 94 (`Account_Index_ID` is a two-record composite) |
| Ultracs positions covered (1-95, no gaps or duplicates) | 95 of 95 |
| Records with a complete ingestion route (HVR, S3, DAG, RAW, `DATA:` key) | 95 of 95 |
| Records reaching at least one internal dbt column | 95 of 95 |
| Records reaching a public dbt column (full end-to-end) | **59** |
| Records ending at the internal layer only | 36 |
| dbt target columns (relation + column) | **179** (112 internal, 67 public) |
| Distinct Snowflake column names across targets | 101 |

## Column Count by Stage

| Stage | Object | Columns |
| --- | --- | ---: |
| 1. Ultracs extract | `KWDW_ACC` -> `DWACC` | 95 |
| 2. HVR parameter | `DWACC.param` | 95 |
| 3. S3 / Datalake | `hvr/ultracs/dwacc` (Parquet, named columns) | 95 |
| 4. Snowflake RAW | `RAW.ACCOUNTS_V1__ACCOUNTS`, read as `DATA:<param name>` keys | 95 payload keys |
| 5a. dbt internal | `INTERNAL.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL_V2` | 83 |
| 5b. dbt internal | `INTERNAL.ACCOUNTS_V1__ULTRACS_ACCOUNTS_EOD_BALANCES_V2` | 29 |
| 6a. dbt public | `PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL` | 38 |
| 6b. dbt public | `PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_EOD_BALANCES` | 29 |

The RAW count is payload keys, not physical columns: the dbt SQL reads `DATA:<name>` from a variant column and no physical RAW column per field is evidenced. Internal columns total 112 and public columns total 67 because some fields feed several columns or both tables.

## Where Each Field Lands

| Landing pattern | Fields |
| --- | ---: |
| Internal DETAIL_V2 only | 36 |
| Internal DETAIL_V2 -> public DETAIL | 34 |
| Internal EOD_V2 -> public EOD | 14 |
| Internal DETAIL_V2 + EOD_V2 -> public EOD | 8 |
| Internal DETAIL_V2 + EOD_V2 -> public DETAIL + public EOD | 3 |
| **Total** | **95** |

Five fields produce more than one differently named Snowflake column: `ProdGrp` (`PRODGRP`, `BANKINGPRODUCTTYPE`), `EodDate` (`EODDATE`, `SNAPSHOTDATE`, `VERSIONSTARTDATE`), `AccInt` (`ACCINT`, `ACCRUEDCREDITINTERESTAMOUNT`), `DebAccInt` (`DEBACCINT`, `ACCRUEDDEBITINTERESTAMOUNT`), `LastTranDate` (`LASTTRANDATE`, `LASTMODIFIEDDATE`). 51 records keep the `.param` name (case-insensitive) in their primary Snowflake column; 44 are renamed.

## Confidence

| Label | Records | Display score |
| --- | ---: | ---: |
| `explicit` | 87 | 95% |
| `confirmed` | 5 | 95% |
| `confirmed_calculated` (`Balance`) | 1 | 90% |
| `inferred` (`Account`, `Prod` of `Account_Index_ID`) | 2 | 60% |

Scores are heuristic evidence strength, not probabilities (see `skills/confidence_score_skill.md`).

## Primary Table and Classification

| Primary Snowflake table | Records |
| --- | ---: |
| `PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL` | 37 |
| `PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_EOD_BALANCES` | 22 |
| `INTERNAL.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL_V2` | 36 |

Classification from dbt YAML: 90 `STANDARD`, 5 `SENSITIVE` (`ACCESSNUMBER`, `KIWIBANKACCOUNTNUMBER`, `ACCOUNTNAMESPECIAL`, `ACCOUNTNAME`, `ALTERNATEACCOUNTNAME`). Of the 95 `.param` entries, 94 have cleanup disabled; `AccountNameSuffix` has cleanup enabled (removes `"`). No column is obfuscated in HVR.

## Data Quality Observations

These come from the JSON content and need owner confirmation; none were changed.

1. **Definition coverage gaps.** 23 records have no `source_locator` (the BASIC output is a bare variable such as `PGRP`, `STATUS`, `RCLNO`); only 8 have an Ultracs-side description; 69 of 95 dbt descriptions follow the template "X sourced from Y".
2. **Missing datatypes.** 9 internal DETAIL_V2 targets have no `data_type` (`DEPOSITACCOUNTID`, `LASTMODIFIEDDATE`, `LASTTRANDATE`, `LVR`, `PARR`, `ARREARSDAYCOUNT`, `ARREARSPAYMENTCOUNT`, `LASTTRANID`, `OPENNINGBOOKEDBALANCEAMOUNT`).
3. **Datatype differences between layers.** 21 internal targets differ from the record's primary type, for example internal `NUMBER(38,2)` versus public `FLOAT` for balance/interest fields, and `CLOSEREASONCODE` as `STRING` internally versus `NUMBER`. `ARREARSDAYCOUNT` and `ARREARSPAYMENTCOUNT` are `VARCHAR` internally versus `NUMBER` publicly.
4. **Possible ArrearsDays / ArrearsNumPmts swap.** BASIC writes `ARRNUMPMTS` at position 58 (`ArrearsDays` -> `ARREARSDAYCOUNT`) and `ARRDAYS` at position 59 (`ArrearsNumPmts` -> `ARREARSPAYMENTCOUNT`). Confirm whether the names or the variables are reversed.
5. **Placeholder names.** `MissingColumn1` to `MissingColumn6` (positions 81-86) are `.param` placeholders; their dbt descriptions describe fee-redirect fields, extent count and a resequencing field. Business names need an owner.
6. **Duplicate source expressions.** `Account_Name` (position 51) and `AccountNameSpecial` (position 26) both read `AREC<28,2>`; `MissingColumn1`/`3` and `2`/`4` both output `RCLNO` and `RPROD` from different `REC<3,2,x>` attributes.

## Documentation Impact

This file holds 95 mappings. `CLAUDE.md`, `docs/PROJECT_FINDINGS.*`, `docs/RUNBOOK.md` and `skills/column_lineage_skill.md` still state that the inventory has 8 records (or 7) and that 87 `.param` columns are intentionally unmapped. Those statements no longer match this file; update them (and the validation checks that assert the count) before the next clean run.

## Not Covered

- Only the account tenant and `DWACC` are in this inventory; the Enterprise extension is table-level and has no column counts here.
- The direct `ult_sf_acc` -> `LOADACCOUNTS_INGEST` route lands only `payload` and `integration_timestamp`, so it contributes no named columns (gap GAP-02).
- Counts describe checked-in code and configuration, not objects confirmed in a live Snowflake catalog.
