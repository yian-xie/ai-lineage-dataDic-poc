# CDP Account Lineage Output

This output is scoped to exactly two repositories: `kb-accounts` and `kb-cdp-tenant-account`. The source snapshot contains 2,043 files (907 and 1,136 respectively) and is retained at [02-parsing/source-snapshot.zip](02-parsing/source-snapshot.zip). Its SHA-256 is recorded in [02-parsing/manifest.json](02-parsing/manifest.json).

## Account-Only Output

The focused Account-only regeneration is under [Account/](Account/README.md). It retains Account Profile and End-of-Day Account Balance data only; the original broad evidence stages below remain available for provenance.

## Reports

- [Full lineage and dictionary report](08-html/index.html)
- [Account ID focused report](08-html-accountid/index.html)
- [Cross-repository field crosswalk](04-column-lineage/cross_repository_field_lineage.json)

The full graph contains 1,163 nodes and 1,337 edges. Column lineage contains 3,332 mappings and 376 parser gaps. The crosswalk contains 119 event-schema/JSON-path field mappings, 18 table mappings, and 45 unresolved mappings.

## Dictionary

The validated dictionary contains 193 assets, 5,871 fields, and 3,332 mappings. All 228 eligible blank descriptions have technical drafts: 82 authored for this run and 146 reused only after exact field identity and all evidence values matched the earlier Account-domain drafts. These are unapproved technical descriptions, not business definitions.

## Scope And Limits

This is repository-static evidence, not execution or production verification. The parser captures declared EF schema/property bindings, C# event assignments, local event schemas, SQL JSON paths, and downstream DBT projections. A matching event property and JSON path does not prove broker delivery. The consumer topic is configured through external Secret Manager/Airflow variables, so topic continuity remains unverified; unresolved mappings and column parser gaps remain visible in the reports.

Every pipeline stage is recorded under `logs/` and indexed in [steps.json](steps.json). No other output root is used by this run.