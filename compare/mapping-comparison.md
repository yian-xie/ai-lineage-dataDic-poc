# Ultracs DWACC vs TMV Accounts-v1

## Compared Scope

- Legacy: 95 distinct DWACC field IDs from `kb-ultracs-datawarehouse` / `KWDW_ACC`, with HVR parameters in `kb-cdp-hvr`.
- New: the `accounts-v1` public TMV Account Detail and End-of-Day Balance models in the full `CDP_Account_output` lineage inventory. Intermediate internal relations and the separate Account Profile event crosswalk are not counted in this comparison.

## Corrected Result

- **95 of 95 legacy fields** have the same destination column in the corresponding new public Account Detail or EOD Balance output.
- **59** are in the same public model; **36** were targeted to a legacy `detail_v2` model and now appear in public Account Detail.
- **62** fields also have the same normalized HVR parameter and TMV source-column name. The remaining **33** use a different source-column name or alias, but still map to the same output field.
- The old and new dictionary descriptions are identical for all **95** matched output fields: business meaning is classified Equivalent. Derivation is Different because the legacy BASIC/HVR path and new TMV SQL path differ; no runtime value equality was tested.
- The new public Account Detail/EOD inventory has **108 unique fields** (110 lineage records, including two duplicate target-field records). **13** public fields have no legacy DWACC counterpart.
- Legacy equation: **95 mapped + 0 Pending + 0 confirmed No match = 95**.

The earlier “35” figure counted source-column-name agreement only within the 59 fields whose public model names were unchanged. It omitted the 36 fields that moved from legacy V2 targets to public Account Detail. The earlier 16-candidate comparison also used the narrower Account Profile/EOD event crosswalk instead of the accounts-v1 TMV field inventory.

## Artifacts

- [HTML reconciliation](account-savings-field-mapping.html)
- [Row-level field alignment](field-alignment.csv)
- Legacy source: [output/04-column-lineage/column_lineage.json](../output/04-column-lineage/column_lineage.json)
- New source: [CDP_Account_output/04-column-lineage/column_lineage.json](../CDP_Account_output/04-column-lineage/column_lineage.json)

This is static mapping and dictionary validation. Matching target fields and descriptions do not establish row-level or runtime value equality.