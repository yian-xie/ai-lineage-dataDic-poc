# ai-lineage-dataDic-poc

An offline Ultracs lineage data dictionary, with deterministic JSON-to-CSV
projection and optional AI enrichment of missing source descriptions.

Start with the [data dictionary workflow](./dataDic/README.md) for requirements,
PowerShell commands, validation rules, and the two local skill packages.

The workflow is:

1. Read the supplied [lineage inventory](./dataDic/01-input/column_lineage.json).
2. Generate or reuse the [baseline CSV bundle](./dataDic/03-output/01-baseline/).
3. Fill only missing Ultracs descriptions in a separate
   [AI-enriched bundle](./dataDic/03-output/02-ai-enriched/) and validate it.
4. **As the final publishing step, embed all three validated CSVs in the
   [HTML viewer](./dataDic/03-output/index.html).**

The saved HTML currently contains the AI-enriched bundle and opens without a
server, adjacent CSV files, or manual imports. CSV edits and browser imports do
not update that saved HTML; rebuild it after validating the desired bundle.

This is a static metadata proof of concept, not a connection to production
systems or a verification of business definitions or runtime lineage.