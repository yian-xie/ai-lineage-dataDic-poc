# Data Dictionary Template

This folder is a CSV workbook template. Import each CSV as a separate spreadsheet tab:

- `asset_registry.csv`: one row per data-bearing asset.
- `field_catalog.csv`: one row per physical asset + field.
- `lineage_links.csv`: one row per actual graph relationship.
- `glossary.csv`: approved business terms and definitions.
- `change_log.csv`: reviewed dictionary changes.

Use `Not documented` where repository evidence is absent. Do not infer owner, steward, refresh cadence, row count, sample values, enum, nullability, primary/foreign keys, PII status, or verification date. `SENSITIVE` classification is not by itself proof of PII. Do not add customer values. Keep repository-relative evidence paths for every sourced claim.

The template does not add graph nodes or edges. Composite keys, inferred links, and unresolved route boundaries must retain their confidence and open questions.
