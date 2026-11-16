# Old DWACC vs New Account Workflow

## Compared Inputs

- Old workflow: [`output/04-column-lineage/column_lineage.json`](../output/04-column-lineage/column_lineage.json), generated from DWACC/HVR and legacy BASIC evidence.
- New workflow: [`CDP_Account_output/Account/04-column-lineage/column_lineage.json`](../CDP_Account_output/Account/04-column-lineage/column_lineage.json) and [`cross_repository_field_lineage.json`](../CDP_Account_output/Account/04-column-lineage/cross_repository_field_lineage.json), generated from Account EF bindings, C# event assignments, event schemas, and tenant-account SQL.

## Result

The workflows are **partially aligned, not record-for-record equivalent**.

- Old inventory: 95 DWACC field mappings, all from the `DWACC` extract. Targets are `accounts_v1__ultracs_accounts_detail` (37 rows), `accounts_v1__ultracs_accounts_eod_balances` (22), and `accounts_v1__ultracs_accounts_detail_v2` (36).
- New cross-repository inventory: 38 field mappings across Account Profile and End-of-Day Account Balance products, 9 table mappings, and 21 unresolved fields. Its 154 column records additionally include 62 EF bindings and 54 event assignments.
- Six old-to-new pairs have the same normalized target column name: `ACCOUNTNAME`, `ACCOUNTSTATUS`, `ALTERNATEACCOUNTNAME`, `ACCOUNTFREEZETYPE`, `BANKINGPRODUCTCODE`, and `MINIMUMNUMBEROFAUTHORISER`.
- One additional pair is conceptually related but has different target names: old `Balance` to `ACCOUNTBALANCE`; new `AccountBalance.Amount` to `ACCOUNTBALANCEVALUE`.
- `Account_ID` and new `AccountProfile.AccountId` have similar labels but different CDP targets: `KIWIBANKACCOUNTNUMBER` versus `ACCOUNTID`. They are not treated as an equivalent mapping.
- Table paths differ. The old flow maps DWACC/HVR fields to Ultracs account detail and EOD balance models. The new flow maps Account Profile or Account Balance database fields through C# event contracts and JSON paths into Account Profile / EOD topic models.

## Field Checks

The six exact target-column name overlaps are useful candidates for business validation, not proof of equivalent source semantics. In particular, the old `BANKINGPRODUCTCODE` target comes from `Account_Index_ID` / HVR `Prod` and is marked inferred; the old `ACCOUNTFREEZETYPE` target comes from `SPFreezeCode`, while the new field is `AccountFreezeDetails.FreezeType`. The source value sets and business definitions should be checked before declaring these pairs equivalent.

The old mapping confidence distribution is 87 explicit, 5 confirmed, 1 confirmed-calculated, and 2 inferred. The new field links are based on static source declarations; Kafka topic continuity is not runtime verified.

## Validation Conclusion

The new workflow reproduces several core Account attributes and a related balance concept, so its mapping is directionally similar. It is not a replacement for the 95-field DWACC mapping: most legacy loan, arrears, statement, and balance fields have no direct counterpart in the current Account Profile/EOD event crosswalk. Keep the unmatched fields and 21 new unresolved fields visible until their intended scope is confirmed.

See [`field-alignment.csv`](field-alignment.csv) for the row-level candidate pairs.