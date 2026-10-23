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
Validate preservation, scores, mirrors and the real three-file import
        |
        v
FINAL: embed the validated bundle in 03-output\index.html
```

### 1. Generate the baseline dictionary

Use Python 3.10 or newer. The bundled Python scripts use only the standard
library; no package installation, credentials, or model API key is required.
Run the following PowerShell commands from this `dataDic` folder.

If the existing [baseline output](./03-output/01-baseline/) is sufficient, skip regeneration.
To build a fresh copy without replacing the baseline CSVs, choose a new destination:

```powershell
python -B .\02-skills\ultracs-data-dictionary-v3\generate.py --output .\03-output\01-baseline-next
```

The default input is [01-input/column_lineage.json](./01-input/column_lineage.json).
An explicit alternative input can be supplied with `--input`; `--graph-id`
sets its graph label. The script reports `status: passed` after its internal
checks succeed.

Running the same command **without `--output` replaces the files in
`03-output\01-baseline`**. Successful generation also refreshes the main
`03-output\index.html`, **including when a new stage folder is chosen**. This
temporarily makes the baseline the main viewer; it does not change an earlier
enriched CSV bundle. To check generation without publishing a new main viewer,
use an output folder outside `03-output`.

Do not run the generator against an enriched bundle: it projects the original
JSON and does not retain later AI descriptions. Publish the validated enriched
bundle in the final step below to make it the main viewer again.

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
As the final publishing step, embed all three validated CSVs in 03-output\index.html.
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

### 3. Validate the complete bundle before publication

Check row counts/order, scoped identities, endpoint references, JSON cells,
canonical field mirrors, the one-or-two-sentence limit, assessment arithmetic
and evidence. Compare the new bundle with its input: existing descriptions and
their metadata, raw source records, lineage relationships and the Asset Registry
must be preserved. See the
[AI CSV output contract](./02-skills/ai-description-enrichment/references/csv-output-contract.md)
for the complete checks.

Then exercise the real HTML importer:

1. Open the existing [main viewer](./03-output/index.html) in a modern browser.
2. Choose **Open 3 CSV bundle** and select all three CSVs from the exact result
   folder together. Do not mix baseline and enriched files.
3. Select **Field Catalog**, then filter **Source system** to **Ultracs**.
4. Use **Description origin** to inspect an **AI generated** draft and an
   unchanged supplied description. Open their details to check provenance,
   evidence and the new draft's assessment.
5. Check the Dictionary and Asset Registry views and a filtered CSV export.
   Resolve any import or preservation errors before publishing.

A browser import previews that bundle in the current page only. It does **not**
save the imported CSVs into the HTML file. A single-CSV import loads Dictionary
only and is not a complete-bundle validation.

The Python HTML builder checks CSV shape, but does not perform all cross-file
semantic or enrichment-preservation checks. Building HTML alone is not proof that
the bundle passed validation.

### 4. Final step: embed the validated bundle in HTML

After validation succeeds, run the builder with the **actual final result
folder**, not the baseline generator:

```powershell
python -B .\02-skills\ultracs-data-dictionary-v3\build_viewer.py --output-dir .\03-output\02-ai-enriched
```

Substitute the versioned folder if the new result is, for example,
`02-ai-enriched-next`. This embeds all three matching CSV texts and the viewer
assets into **[03-output/index.html](./03-output/index.html)**. It creates or
replaces only that main HTML, without changing any CSV, regenerating the source
JSON, or leaving another HTML copy inside the stage folder.

Open or refresh the main HTML and confirm that all three views load the final
bundle **without importing any CSVs manually**. The saved snapshot is fully
offline and needs no server or adjacent files. The currently saved main HTML
embeds the [AI-enriched bundle](./03-output/02-ai-enriched/).

**Latest means the most recently completed publication**, not the highest folder
number or a guessed file-modification time. Successful generation or a standard
HTML build for any direct subfolder of `03-output` replaces the main viewer.
A failed build leaves the previous main viewer intact. An explicit
`--destination` creates a preview without publishing it as latest; builds outside
`03-output` also leave the main viewer unchanged.

Changing CSVs by hand or importing another bundle in the browser never refreshes
the saved HTML automatically. Repeat validation and this final build after any
intentional CSV changes.

## What each CSV contains

| File | Row meaning | Baseline columns | AI-enriched columns |
| --- | --- | --- | --- |
| `asset_registry.csv` | One represented asset or scoped source context. This file is unchanged by the default AI enrichment. | 25 | 25 |
| `field_catalog.csv` | One scoped field/reference: Ultracs source, extract slot, RAW JSON key or Snowflake column. New AI description scores are stored here. | 47 | 52 |
| `data_dictionary.csv` | One source mapping and one exact Snowflake target, with target-specific processing and synchronized source-description information. | 106 | 111 |

Keep the three files together. Their graph/snapshot IDs, canonical field
objects, source-description mirrors and references must agree.
The enriched Field Catalog and Dictionary each append five description
assessment columns. These schema counts describe the supplied bundles; future
inputs may retain additional columns.

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
