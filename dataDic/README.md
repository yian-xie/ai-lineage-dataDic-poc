# Ultracs Data Dictionary

Two local skills turn an existing lineage inventory into a browsable data
dictionary and optionally fill missing Ultracs descriptions with AI.

This is a **static metadata workflow**. It does not connect to Ultracs, HVR,
Snowflake or other production services, execute BASIC/SQL, or verify deployed
lineage. The AI step uses the supplied CSV evidence, not a live source catalog.

## Folder structure

```text
dataDic\
  README.md
  01-input\
    column_lineage.json
  02-skills\
    ultracs-data-dictionary-v3\
      SKILL.md
      generate.py
      build_viewer.py
      description_provenance.py
      legacy_projection.py
      assets\
    ai-description-enrichment\
      SKILL.md
      references\
        scoring-rubric.md
        csv-output-contract.md
  03-output\
    index.html                   Main viewer: latest completed output
    01-baseline\
      asset_registry.csv
      field_catalog.csv
      data_dictionary.csv
    02-ai-enriched\
      asset_registry.csv
      field_catalog.csv
      data_dictionary.csv
```

- [01-input](./01-input/) is the starting evidence. Keep it unchanged.
- [02-skills](./02-skills/) contains the two reusable workflow packages.
- [03-output](./03-output/) contains the results in processing order:
  [01-baseline](./03-output/01-baseline/) holds the deterministic CSV bundle and
  [02-ai-enriched](./03-output/02-ai-enriched/) holds the CSVs with missing
  descriptions filled by AI. These stage folders contain CSVs only.
- **Open [03-output/index.html](./03-output/index.html)** to see the latest
  completed workflow output without importing CSVs manually.

The previous `input`, `skills`, `output` and `output_ai` folders have been moved
into this numbered layout. The supplied JSON and CSV contents are unchanged.

## The two skills

| Skill | Input | Work performed | Output |
| --- | --- | --- | --- |
| [Ultracs data dictionary v3](./02-skills/ultracs-data-dictionary-v3/SKILL.md) | Supported mapping-inventory JSON | Deterministically projects and validates recorded metadata; preserves supplied descriptions and uncertainty. No AI generation or new numeric scores. | Baseline CSVs and the main HTML viewer. |
| [AI description enrichment](./02-skills/ai-description-enrichment/SKILL.md) | All three matching CSVs from one baseline folder | Uses the active AI assistant to fill only missing Ultracs source descriptions and assess evidence supporting each new description. | A separate enriched CSV bundle; refreshes the main HTML after validation. |

These are **local skill packages**. Reference their `SKILL.md` files explicitly
in an AI prompt. The chosen visible `02-skills` layout is not Copilot's
auto-discovery layout, and does not install them globally or guarantee slash
commands.

## End-to-end process

```text
Supplied lineage JSON
        |
        v
Skill 1: deterministic projection and validation
        |
        v
Baseline: three CSVs + embedded HTML
        |
        v
Skill 2: AI fills missing Ultracs descriptions only
        |
        v
New enriched three-CSV bundle
        |
        v
Refresh 03-output\index.html to display the newly completed bundle
```

### 1. Generate the baseline dictionary

Use Python 3.10 or newer. The bundled Python scripts use only the standard
library; no package installation, credentials, or model API key is required.
Run the following PowerShell commands from this `dataDic` folder.

If the existing [baseline output](./03-output/01-baseline/) is sufficient, skip regeneration.
To build a fresh copy without replacing saved files, choose a new destination:

```powershell
python -B .\02-skills\ultracs-data-dictionary-v3\generate.py --output .\03-output\01-baseline-next
```

The default input is [01-input/column_lineage.json](./01-input/column_lineage.json).
An explicit alternative input can be supplied with `--input`; `--graph-id`
sets its graph label. The script reports `status: passed` after its internal
checks succeed.

Running the same command **without `--output` replaces the files in
`03-output\01-baseline`**. Successful generation also refreshes the main
`03-output\index.html`. Do not run it against an enriched bundle: it projects
the original JSON and does not retain later AI descriptions.

### 2. Fill missing Ultracs descriptions with AI

Open this folder in VS Code and give the assistant a prompt such as:

```text
Follow 02-skills\ai-description-enrichment\SKILL.md.
Read the three matching CSVs from 03-output\01-baseline.
Preserve every existing description and its metadata exactly.
Fill only missing Ultracs source descriptions, each in one or two sentences.
Score evidence supporting only those new descriptions and explain the arithmetic.
Write all three matching CSVs to a new 03-output\02-ai-enriched-next folder.
Leave lineage relationship scores unchanged and validate the HTML bundle import.
Build that folder's HTML and refresh 03-output\index.html with the new result.
```

Use a destination that does not already exist, or explicitly approve replacing
an earlier run. If step 1 used `03-output\01-baseline-next`, name that folder as
the input instead of `03-output\01-baseline`; do not mix baseline versions.

This skill requires the active AI assistant to read field context and author
the descriptions. It is not a standalone enrichment command, and the Python
converter does not generate AI prose.

**Preservation rules**

- A nonempty existing description must not be rewritten, shortened, appended
  to, relabelled as AI, or assigned a new AI score.
- Only null, empty or whitespace-only descriptions are eligible. Nonempty
  text such as `Unknown` is still protected unless the user explicitly permits
  replacing it.
- Each newly generated description contains **one or two sentences**.
- New descriptions are labelled `AI generated` drafts, not approved business
  definitions. Missing meaning or source binding must remain explicit.
- Other fields, original raw records, existing metadata and lineage
  relationship assessments stay unchanged.
- Scores, evidence, calculation and detailed rationale are separate from the
  description text.

### 3. View the enriched bundle

Open **[03-output/index.html](./03-output/index.html)** in a modern browser.
It already embeds the last output published by a completed workflow. After AI
enrichment, it shows that enriched bundle rather than the older baseline.

1. Select **Field Catalog**, then filter **Source system** to **Ultracs**.
2. Use **Description origin** to distinguish AI-generated entries from
   unchanged supplied descriptions.
3. Click a field to inspect its description, evidence and assessment.

The HTML is an embedded snapshot, not a live connection to adjacent CSV files.
Each successful generation or standard HTML build for a direct subfolder of
`03-output` replaces the main viewer with that completed snapshot. **Latest
means the most recently completed publication**, not the highest folder number
or a guessed file-modification time. A failed build leaves the previous main
viewer intact. Refresh an already-open browser page after publication.

Changing CSVs by hand does not refresh the HTML automatically. After an explicitly
validated change, rebuild from the desired bundle:

```powershell
python -B .\02-skills\ultracs-data-dictionary-v3\build_viewer.py --output-dir .\03-output\02-ai-enriched
```

This creates or replaces only the main `03-output\index.html` without changing
any CSV or regenerating the source JSON. It does not leave another HTML copy
inside the stage folder.
Substitute a versioned output folder if needed. Builds outside `03-output` do
not change the main viewer; an explicit `--destination` creates a preview without
publishing it as latest.

**Open 3 CSV bundle** is still available for inspecting another snapshot
manually. Select all three CSVs from one folder together. A single-CSV import
loads Dictionary only and does not populate the matching registry views.

## What each CSV contains

| File | Row meaning |
| --- | --- |
| `asset_registry.csv` | One represented asset or scoped source context. This file is unchanged by the default AI enrichment. |
| `field_catalog.csv` | One scoped field/reference: Ultracs source, extract slot, RAW JSON key or Snowflake column. New AI description scores are stored here. |
| `data_dictionary.csv` | One source mapping and one exact Snowflake target, with target-specific processing and synchronized source-description information. |

Keep the three files together. Their graph/snapshot IDs, canonical field
objects, source-description mirrors and references must agree.

## Description confidence: where and how

For a newly generated description, select:

**Field Catalog -> click field -> Description provenance -> description_assessment**

The score is not a separate visible Field Catalog table column. It is also
available in the complete CSV-column disclosure and in these CSV columns:

- `description_confidence_score_10`
- `description_confidence_method`
- `description_confidence_rationale`
- `description_confidence_json`

Dictionary has matching `source_description_*` assessment columns. An existing
description receives no new AI score.

The [description-evidence-v1 rubric](./02-skills/ai-description-enrichment/references/scoring-rubric.md)
scores five criteria from 0 to 2: identity grounding, meaning support,
transformation support, corroboration, and uncertainty handling. The sum is a
score out of 10. Each award has evidence and a reason; the calculation is checked.

This is an **AI self-assessment of support in the supplied CSVs**, not a
probability, human approval, production verification or lineage-reliability
score. Relationship confidence is a separate concept and is not changed.

## Current saved snapshot

The current baseline contains 7 assets, 464 catalog fields, 179 mapping rows and
369 operations. Its 95 Ultracs source entries include 8 existing descriptions.
The saved AI bundle preserves those 8 exactly and fills the other 87 with
two-sentence drafts. These are snapshot counts, not limits for future inputs.

## Validation and cautions

- The generator validates the supported JSON contract, CSV round-tripping,
  identity/reference consistency and preservation before publishing its output.
- AI enrichment must validate its new scores, evidence, sentence limits,
  existing-description preservation and all cross-file mirrors.
- The viewer rejects incomplete, mismatched or inconsistent three-file imports.
  A Python HTML build alone is not a substitute for checking the real import.
- Do not infer physical source bindings, business definitions or runtime
  execution from labels or successful validation.
- For detailed procedures, see the two skill files and the
  [AI CSV output contract](./02-skills/ai-description-enrichment/references/csv-output-contract.md).
