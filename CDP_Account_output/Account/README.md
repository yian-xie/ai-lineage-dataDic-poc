# CDP Account-Only Output

This focused run includes Account Profile and End-of-Day Account Balance data from the same two-repository source snapshot. It excludes transaction-topic flows, term-deposit tables, and generic product-rate models.

## Reports And Data

- [Account-only lineage report](08-html-account/index.html)
- [Validated Account dictionary](06c-ai-enrichment/data_dictionary.csv)
- [Account-only field crosswalk](04-column-lineage/cross_repository_field_lineage.json)
- [Selected column mappings](04-column-lineage/column_lineage.json)

In the HTML report, open the **Columns** view to see the cross-repository field table: source database field, `kb-accounts` entity property, event field, CDP raw field, DBT target, and transport status.

The selection contains 154 mapping records: 38 tenant Account SQL projections, 62 EF bindings across the Account Profile and Account Balance tables, and 54 Account Profile/Balance event assignments. The crosswalk contains 38 event-schema/JSON-path field mappings, nine table mappings, and 21 unresolved Account fields.

The dictionary has 25 assets, 204 fields, and 154 mappings. All 74 eligible descriptions were reused only after exact field identity and every cited evidence value matched; they were rebound to this scoped dictionary's hashes.

## Limits

The `transaction.account_balance` EF table is included only because it maps to the End-of-Day Account Balance event. Transaction-event flows are excluded. This remains repository-static evidence: event-to-raw mappings do not verify runtime Kafka delivery, and the consuming topic remains configured by external Secret Manager/Airflow variables.