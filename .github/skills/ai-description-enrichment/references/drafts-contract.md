# drafts.json contract: description-drafts-v1

`prepare_context` writes `description-context-v1` context. The active assistant
then authors a separate JSON document. `apply_drafts` accepts **only** this
versioned contract and `description-evidence-v1`; it does not invent a rubric.

## Top-level object

All keys are required; unknown keys are rejected:

```text
schema_version: "description-drafts-v1"
rubric_id: "description-evidence-v1"
input_hashes:
  asset_registry.csv: exact original SHA256
  field_catalog.csv: exact original SHA256
  data_dictionary.csv: exact original SHA256
run_id: actual enrichment identity
generator: actual active assistant attribution
model: actual model identifier, or null if unknown
generated_at: actual ISO-8601 UTC time, with Z or +00:00
results: one decision per canonical eligible scoped ID
```

No name joins, CSV line numbers, implicit default decisions or partial batches.
All eligible fields must have either a draft or an explicit `needs_evidence`
decision. Nonempty descriptions and out-of-scope IDs cannot be submitted.
Manual draft application invokes no AI service. The explicit `generate` or
pipeline `--full-run` mode calls the user's Copilot CLI. It validates each
bounded authoring batch and combines accepted results before application;
partial batches alone are not a complete draft file.

## Draft result

```text
graph_id, snapshot_id, field_id: exact canonical strings
status: "draft"
description: one or two complete, concise sentences (maximum 1,000 characters)
assessment: complete description-evidence-v1 object
```

Do not add surrounding whitespace or mix score/rationale into the description.
Avoid sentence-boundary-ambiguous abbreviations. Existing descriptions are not
subject to this length rule and must never be shortened.

The assessment uses the exact scope/origin/verification values from
[the rubric](./scoring-rubric.md). Components occur exactly once in this order:
`identity_grounding`, `meaning_support`, `transformation_support`,
`corroboration`, `uncertainty_handling`. Each has:

- `criterion`: exact criterion ID.
- `points`: integer 0, 1 or 2 (not a boolean or numeric string).
- Optional `maximum: 2`; no alternative weights.
- `reason`: field-specific support, missing points and applicable limitations.
- `evidence_refs`: unique IDs into the assessment's evidence map. Every positive
  award needs a reference; zero-point reasons explicitly describe missing support.
- Optional `limitations`: text array; overall assessment limitations are required.

`evidence_refs` is a map, for example `"E1": {CSV reference object}`. Each
reference contains exactly the nine keys documented in the rubric. Hash,
scope, row identity, column, JSON pointer and typed value must match the input.
A scalar cell uses `json_pointer: null`; a JSON cell uses a pointer string
(`""` means the JSON root). References must concern this field or its linked
context, not an unrelated field. Generated confidence/provenance cannot be
evidence for itself. Use at most 48 references and bounded values.

`score_10` is the sum of the five integer awards. `calculation` has exactly the
form `"1 + 1 + 2 + 1 + 2 = 7 / 10"` for those actual awards; the example is not
a default rating. Arithmetic mismatches are rejected, not silently corrected.
`rationale` and `limitations` are required. Optional `open_questions` is a text
array. `assessed_by`, `model` and `assessed_at` match top-level generation metadata.
`human_review_status` is `"not_reviewed"` and optional `is_probability` is false.

## Needs-evidence result

```text
graph_id, snapshot_id, field_id: exact canonical strings
status: "needs_evidence"
description: null
assessment: null
reason: field-specific explanation
open_questions: nonempty array of concrete missing evidence questions
```

Input descriptions, origins and canonical objects stay untouched. New status
and rationale columns record the unresolved decision; score is blank and JSON
assessment is `null`. This is not a zero-point completed assessment.

## Executable tiny examples

- [sample-input.json](./sample-input.json): one actual archived mapping record,
  five fields, five assets and two targets. Its exact bytes bind the hashes.
- [drafts.example.json](./drafts.example.json): the existing saved assistant
  description/assessment, re-bound to this reduced fixture's exact evidence.
  It is **archived prose for regression**, not a newly generated AI description.
- [drafts-needs-evidence.example.json](./drafts-needs-evidence.example.json):
  the same scoped field represented without prose or a score.

From the repository root, independently exercise the installed APIs/modules:

```powershell
python -m lineage_poc.dictionary.generate --input .github\skills\ai-description-enrichment\references\sample-input.json --output outputs\example-csv
python -m lineage_poc.enrichment.workflow prepare --input outputs\example-csv --output outputs\example-context
python -m lineage_poc.enrichment.workflow apply --input outputs\example-csv --drafts .github\skills\ai-description-enrichment\references\drafts.example.json --output outputs\example-enriched
python -m lineage_poc.validation.bundle --input outputs\example-enriched --baseline outputs\example-csv
python -m lineage_poc.viewers.dictionary.build_viewer --output-dir outputs\example-enriched --destination outputs\example-html\index.html
```

Do not reformat/rename the sample input and expect its pre-bound hashes to
remain valid. For new input, prepare fresh context and let the active assistant
author actual decisions rather than copying example prose.
