# HTML-compatible AI-description bundle

## Preserve the original bundle

Write the exact three filenames into a new output folder. Keep every original
header, unknown column, row, scoped ID, graph/snapshot value, target association,
field coordinate, governance value, expression, and relationship assessment.
Preserve row order. Add only the description-enrichment columns described below.

The snapshot IDs continue to identify the original lineage evidence. Record a
separate enrichment run ID, the three input hashes, rubric version, and actual
generation time in the generated descriptions' provenance. Do not pretend a new
AI assessment is a refreshed source snapshot.

Do not change `data\inputs\column_lineage.json` or any original CSV. Recheck their
hashes after completion.

## Existing descriptions are protected

Before generation, test the original description for non-whitespace text.
If it exists, keep its exact description, origin, provenance, canonical object,
description-detail entries, business metadata, and existing assessments unchanged.
Keep matching source-description mirrors unchanged too. Do not put an AI
replacement in the visible description while moving the original into history.

Do not add new generation metadata or AI scores to a protected description.
For newly appended scalar enrichment columns, leave protected rows blank. Use
the JSON text `null` in new `_json` columns to represent no assessment; the
Dictionary importer rejects empty JSON cells. If those columns already exist in
an input bundle, preserve their original values.
Changes to a different missing co-input's catalog object must not alter the
protected field's own object.

Only empty, null, or whitespace-only descriptions are eligible for generation.
Every new description must contain one or two concise sentences. Do not shorten
or otherwise edit an existing description to impose that sentence limit.

## Where description scores live

Append these columns to Field Catalog:

| Column | Value |
| --- | --- |
| `description_generation_status` | `draft` or `needs_evidence` for eligible missing descriptions; no new value for protected existing descriptions or out-of-scope fields. |
| `description_confidence_score_10` | Recalculated 0-10 integer for a draft; blank if unscored. |
| `description_confidence_method` | `description-evidence-v1`. |
| `description_confidence_rationale` | Readable evidence basis, calculation, and limitations. |
| `description_confidence_json` | Complete assessment object, including components and evidence references. |

Append the corresponding `source_`-prefixed columns to Dictionary. Their values
must match the canonical source field for every repeated source/target row.
For example, `source_description_confidence_score_10` mirrors
`description_confidence_score_10`.

For protected existing descriptions and out-of-scope fields/rows, leave new
scalar columns blank and put JSON `null` in new `_json` columns. Preserve any
columns already present in the input. Every added `_json` cell must parse as
valid JSON, including rows without a new assessment.

Also include the full assessment under
`description_provenance_json.description_assessment` and under the matching
`source_description_provenance_json.description_assessment`. The current HTML
already exposes that provenance in Field Catalog details. Extra columns are
available in complete CSV-column disclosure and filtered exports; they do not
create a new visible score column automatically.

**Do not change** `relationship_confidence_summary`,
`relationship_confidence_json`, operation `confidence_score_10`,
`confidence_state`, `confidence_method`, or `confidence_assessment_json`.
Description scores must not appear in the Relationships column or its score
filters.

## Field Catalog changes

For a supported draft on an eligible missing Ultracs description only:

1. Recheck that the input description is missing, then put the new one-or-two-
   sentence AI text in `description`. Reject a draft targeting existing text.
2. Set `description_origin` and `description_source_type` to `ai_generated`.
3. Keep `description_author` blank unless a real author attribution is known;
   record the actual AI assistant in `description_generator`.
4. Set `description_source_reference` to this new bundle's field CSV, exact
   scoped row identity, and `description` column. Do not attribute the generated
   wording to an old BASIC/YAML path. Leave `description_source_pointer` blank
   for a scalar CSV cell; do not invent a JSON pointer into a CSV.
5. In `description_provenance_json`, record:
   - `source_type: "ai_generated"` and `status: "draft"`.
   - Enrichment run ID, actual generator/model/time, generation method, and
     `verification_mode: "supplied_csv_only"`.
   - Input file hashes, supporting CSV evidence references, limitations, and
     the complete description assessment.
   - `previous`: the exact input description, origin, all six description
     provenance columns, and complete input `original_field_json` value.
   - `is_approved_business_definition: false`.
6. Update the canonical field object's description and description origin in
   `original_field_json` to match the new displayed field. This column is the
   viewer's canonical-object mirror in the **enriched** bundle, not an unchanged
   input archive. Preserve the actual pre-enrichment object in `previous`.
   Include AI provenance in the enriched canonical object's metadata.
7. Preserve the supplied business definition, definition status, human review,
   physical binding, source references, and every other field property. A
   technical AI draft does not approve or create a business definition.

For `needs_evidence`, retain the input description and existing origin columns.
Store the failed-generation status, null assessment, and questions in the new
confidence columns and enrichment metadata, without marking unchanged input text
as AI-generated.

## Dictionary mirrors and archival evidence

Apply a newly filled canonical result everywhere the eligible field appears.
Do not change protected existing descriptions or their metadata:

- For rows whose `source_field_id` matches, update `source_description`,
  `source_description_origin`, and the six `source_description_*` provenance
  columns from Field Catalog.
- Update **every** matching field object inside `field_catalog_json`, including
  occurrences in other mappings' co-input context. Each enriched canonical
  object must exactly equal the corresponding Field Catalog
  `original_field_json`.
- Update matching `description_details_json` entries with the same description,
  origin, and explicit AI provenance. Preserve their original source claims
  separately; do not relabel the old evidence as the author of new prose.
- Include the prior canonical metadata and description assessment in the new
  provenance, rather than silently losing supplied text.
- Keep `original_record_json` unchanged as a typed JSON-value archive of the
  original lineage record. Do not insert AI prose, scores, or metadata into it.

Keep `process_details_json`, `transformation_logic_json`, original mapping notes,
operation identities, expressions, paths, and all relationship-confidence values
unchanged. No new lineage edges, assets, fields, or source/target pairs are
created by description enrichment.

The old `input_property_map_json` may reference description projections that have
now intentionally changed. Re-audit those destinations:

1. Preserve every original input pointer and its exact `original_record_json`
   destination.
2. Remove or redirect destinations that no longer preserve the input value.
   An archived value under generated provenance may be used only after comparing
   its parsed value with the actual original.
3. Set the coverage state from the destinations that still genuinely preserve
   that input property. Do not retain `verified_visible` for an original blank
   description projection that has now been filled with AI text.
4. Verify container, null, empty-string, and absent-property distinctions.
   Do not claim the old raw-input coverage audit validates the new AI prose.

All repeated copies of one field's description, assessment, and provenance must
agree within the same graph/snapshot. Do not join by names or take the last
occurrence as a silent conflict winner.

## Asset Registry

The default task does not create asset descriptions or asset confidence scores.
Copy `asset_registry.csv` unchanged into the new bundle; verify its bytes match
the original. It is still a required part of the three-file import.

Do not derive asset-level PII, ownership, sensitivity, or a confidence aggregate
from the generated field descriptions.

## Validation before publishing

- Parse the three output CSVs again; require unique headers and correct widths.
- Parse all populated `_json` cells; reject nonfinite numeric scores.
- Check original row counts/order, IDs, graph/snapshot scopes, asset membership,
  target coverage, and endpoint references.
- Require one result per eligible missing source description, with no duplicate,
  unknown, or protected enrichment identities. Account separately for existing
  descriptions preserved without AI changes.
- Compare every originally nonempty description, origin, provenance, canonical
  object, existing assessment, and description-detail mirror with the input.
  They must remain unchanged, not merely archived behind replacement text.
- Check every new description contains one or two sentences. Keep scoring
  rationale and detailed caveats outside the description text.
- Recompute all five criterion points and their sum. Resolve evidence references
  against the original CSVs and check the cited values.
- Check description-source-type availability and the same `source_type` inside
  provenance. A changed description must have AI origin, never an inherited
  repository-authored label.
- Compare source-description mirrors and canonical embedded fields exactly.
- Compare original raw records, operations, relationship scores, expressions,
  governance metadata, nonselected fields, and Asset Registry with the inputs.
- Recheck original-property coverage after intentional projection changes.
- Confirm every decoded cell fits Excel's 32,767-character limit when claiming
  spreadsheet compatibility. Never truncate evidence, descriptions, or archives.
  Report an exceeded limit explicitly.
- Pass all three matching CSV texts to the actual HTML
  `V3Bundle.prepareBundle(files, {})` importer before claiming compatibility.
  The Python HTML builder alone does not perform all cross-file semantic checks.
- Import all three files together and inspect at least one new description, one
  previously documented field with preserved source text, one unresolved case
  where applicable, source-group repeats, score/rationale, origin filtering, and
  filtered CSV export. Verify relationship scores remain unchanged.

Publish only a complete validated bundle. When browser tools are unavailable,
report that browser import remains unverified instead of claiming a successful
display check.

After validation, explicitly run `python -m lineage_poc html --input ENRICHED
--baseline BASELINE --graphs GRAPH_DIRECTORY --columns COLUMN_DIRECTORY`,
using the actual saved step directories. The final
`output\08-html\index.html` embeds both the lineage graph and the matching
dictionary. Only the latest files are kept per step; diagnostics are appended
under `output\logs`.
The package API `lineage_poc.viewers.dictionary.build_viewer.build(bundle,
destination)` atomically writes only that destination. With no destination its
only default is `bundle\index.html`; it never publishes to a shared root or
guesses a latest folder. Baseline generation and draft application create CSVs
only. Keep `tests\fixtures\reference` immutable.
