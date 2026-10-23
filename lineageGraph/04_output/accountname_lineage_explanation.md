# Account_Name Column Lineage

## Field Mapping

- `ACCOUNT<28,2>` → DWACC position 51 `AccountName` → `ACCOUNTNAME` in `snowflake:relation:PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL` (`confirmed`). KWDW_ACC writes AREC<28,2> to DWACC position 51; DWACC.param names it AccountName; dbt reads DATA:AccountName.

## End-to-End Route

`KWDW_ACC` reads Ultracs ACCOUNT/TRAN records and writes the pipe-delimited DWACC extract. The HVR S3 route converts DWACC text to Parquet (`ult_s3_acc1`), then delivers it to HVR S3 (`ult_s3_acc2`). The account Airflow DAG copies files to Datalake S3 and loads `RAW.ACCOUNTS_V1__ACCOUNTS`. The dbt source resolves to that RAW relation; account dbt models expose the mapped public Snowflake columns.

## Separate Branch and Caveats

The direct `ult_sf_acc` HVR branch ends at `LOADACCOUNTS_INGEST`, which defines row `payload` and `integration_timestamp`, not these named business columns. No checked repository evidence connects that relation to the account RAW route. The filename-pattern association from DWACC to HVR capture is inferred; do not join the routes.

Evidence is static repository configuration/source, not live HVR, Airflow, or Snowflake runtime state.
