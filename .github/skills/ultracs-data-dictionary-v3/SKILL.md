---
name: ultracs-data-dictionary-v3
description: 'Use when generating or validating the three-CSV Ultracs data dictionary from exported mapping JSON, or explicitly building its offline HTML viewer. Preserve reported identities, normalization, raw-property coverage, original records, descriptions and relationship confidence. Missing-description AI authorship is a separate, explicit ai-description-enrichment step.'
argument-hint: 'Generate a CSV bundle, validate it, optionally enrich missing descriptions with the active assistant, then explicitly build HTML.'
user-invocable: true
---

# Ultracs data dictionary

## Scope

The implementation is the installed `lineage_poc` Python package, **not** scripts
copied into this skill. Work from the repository root. Read
[the projection contract](./references/projection-contract.md) before changing
normalization, identity, evidence or metadata handling.

Input is a supported exported mapping-record JSON array. A generic nodes/edges
graph, numeric confidence assessment, or conflicting declaration needs an
explicit adapter; never guess or silently repair it.

Use `output\04-column-lineage\column_lineage.json` from the column step.
Golden regression fixtures are under `tests\fixtures\reference`; do not modify
them or treat them as an automatic replacement for missing processing inputs.

## Independently runnable steps

All CLI results are saved under one `output` folder. Each step keeps its latest
files and appends diagnostics under `output\logs`. Use the printed paths.

1. Generate **CSV only**:

   ```powershell
   python -m lineage_poc dictionary --input .\output\04-column-lineage\column_lineage.json
   ```

   Result: `asset_registry.csv`, `field_catalog.csv`, `data_dictionary.csv`.
   Generation performs deterministic projection and shared bundle validation.
   It does not generate AI prose, build HTML, or publish a latest viewer.

2. Validate the printed bundle directory independently:

   ```powershell
   python -m lineage_poc validate --input .\output\05-baseline-dictionary
   ```

3. If the user requests missing Ultracs descriptions, explicitly invoke the
   repository **ai-description-enrichment** skill. Its prepare step makes
   bounded, hash-bound context; the **active assistant** authors and assesses
   each draft, or records `needs_evidence`; application validates those decisions.
   Python never substitutes a sentence template. Explicit `enrichment generate`
   or pipeline `--full-run` invokes the user's configured Copilot CLI; generation
   is not hidden inside the deterministic dictionary step.
   Existing descriptions and unrelated lineage evidence remain untouched.

4. Validate the resulting enriched bundle against its original bundle:

   ```powershell
   python -m lineage_poc validate --input .\output\06c-ai-enrichment --baseline .\output\05-baseline-dictionary
   ```

5. Explicitly build HTML from the chosen validated bundle:

   ```powershell
   python -m lineage_poc html --input .\output\06c-ai-enrichment --baseline .\output\05-baseline-dictionary --graphs .\output\03-lineage-graphs --columns .\output\04-column-lineage
   ```

   The final `output\08-html\index.html` displays both the lineage graph and the
   embedded dictionary. It does not modify CSVs or upload anything.

## Library and module interfaces

```python
from pathlib import Path
from lineage_poc.dictionary.workflow import generate_bundle
from lineage_poc.validation.bundle import validate_bundle
from lineage_poc.viewers.dictionary.build_viewer import build

summary = generate_bundle(Path("input.json"), Path("output") / "csv")
validation = validate_bundle(Path("output") / "csv")
html = build(Path("output") / "csv", Path("output") / "preview.html")
```

The dictionary-only component `build(bundle)` defaults to `bundle\index.html`.
Use the main `html` CLI for the final combined report. Explicit destinations
are written atomically, only there. Returned summaries are JSON-serializable;
invalid inputs raise an error rather than being repaired.

Standalone module interfaces also remain available:

```powershell
python -m lineage_poc.dictionary.generate --input INPUT --output BUNDLE
python -m lineage_poc.validation.bundle --input BUNDLE --baseline BASELINE
python -m lineage_poc.viewers.dictionary.build_viewer --output-dir BUNDLE --destination HTML
```

## Validation and presentation

Shared Python validation covers CSV quoting/header widths, JSON values and cell
limits, scoped IDs, joins, canonical objects, repeated source mirrors,
description details, operations, paths, incident relationships, asset/field
topology and original-property coverage. Supplying a baseline additionally
checks exact input preservation and resolves newly authored description evidence
against its original hashes. It does not prove business meaning or runtime use.

Keep the existing viewer assets and UI behavior: three-CSV import, seven-column
Dictionary layout, asset/field tabs, complete details, source groups, target
processing, provenance, filters and CSV exports. Test the actual
`V3Bundle.prepareBundle` JavaScript importer and the browser interactions;
successful Python generation or HTML assembly is not browser verification.
