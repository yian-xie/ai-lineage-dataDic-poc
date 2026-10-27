---
name: ai-description-enrichment
description: 'Use when explicitly asked to generate missing Ultracs field descriptions from a matching three-CSV dictionary bundle. The active AI assistant authors one or two evidence-grounded sentences and description-evidence-v1 self-assessments, or records needs_evidence. Prepare hash-bound context, apply drafts, validate preservation and then explicitly build HTML; never replace existing descriptions or score lineage relationships.'
argument-hint: 'Prepare context, actively author drafts.json for each eligible field, apply, validate against input, then build the chosen HTML.'
user-invocable: true
---

# Explicit AI description enrichment

The **active assistant** authors each new description after examining exact
field-specific evidence. This is not a deterministic description generator or
a name-to-sentence lookup. Python prepares context, verifies references and
arithmetic, applies accepted drafts and validates preservation. It does not
substitute templated prose. Explicit `enrichment generate` and pipeline
`--full-run` modes invoke the user's configured Copilot CLI; the user manages
all sign-ins manually. No alternative AI provider is called.

Run this workflow only when enrichment is requested. Creating the skill or
running `prepare` does **not** generate descriptions.

For the complete workflow from a fresh start:

```powershell
python -B -m lineage_poc pipeline --clone --full-run
```

This includes new Copilot authoring, validation, application and the final
combined HTML. Do not claim a completed run if AI execution fails.

Read [the scoring rubric](./references/scoring-rubric.md),
[the drafts contract](./references/drafts-contract.md) and
[the CSV output contract](./references/csv-output-contract.md).

## Inputs and protected fields

Use one exact matching bundle: `asset_registry.csv`, `field_catalog.csv`,
`data_dictionary.csv`. Resolve the repository from the workspace, not from this
skill's former location. Package code lives in `src\lineage_poc\enrichment` and
`src\lineage_poc\validation`; do not bundle duplicate implementations here.

Only canonical `source_system=Ultracs`, `layer=source`, whitespace-empty
descriptions are eligible. Match by `(graph_id, snapshot_id, field_id)`.
Every nonempty description is protected, including placeholders and existing
AI drafts. Preserve its text, metadata, origin, provenance and assessments
exactly. Do not shorten existing descriptions to the new-draft sentence limit.
HVR, RAW, Snowflake and asset descriptions are out of scope.

Do not modify the original JSON, reference outputs or input CSVs. Keep original
records, operations, confidence, expressions, governance and unrelated metadata.
Asset Registry bytes must remain identical.

## Step 1 — prepare context, independently testable

From the repository root:

```powershell
python -m lineage_poc enrichment prepare --input .\output\05-baseline-dictionary
```

The CLI saves context in `output\06a-enrichment-context` and appends diagnostics
in `output\logs`. It keeps only the latest output for this step.
`context.json` contains exact three-file hashes, canonical eligible/protected
IDs and bounded useful evidence for **eligible fields only**. Large values are
omitted with a reason, never truncated. This step produces no draft prose.

## Step 2 — active assistant authors drafts.json

To have the configured Copilot CLI perform authoring automatically:

```powershell
python -B -m lineage_poc enrichment generate --input .\output\05-baseline-dictionary --context .\output\06a-enrichment-context
```

The runner supplies this skill, its references and bounded contexts in batches,
with no tool access. It records new drafts, actual attribution/time, raw
responses and diagnostics. Every batch and the combined draft file must pass
the strict contract before application. A failed/invalid response stops the
pipeline; never silently replace it with old prose or `needs_evidence`.

The instructions below also apply to manual assistant authoring:

Read each eligible context and, where needed, exact cells in the unchanged
input CSVs. Treat repository paths as reported claims, not proof of source or
runtime inspection. Do not read repositories or live systems in this workflow.

For **every** eligible scoped field, author exactly one decision:

- `draft`: one or two concise English sentences; exactly five rubric criteria
  with field-specific reasons and verifiable evidence references. State real
  uncertainty, aliases, missing physical binding and unsupported business meaning.
- `needs_evidence`: null description and assessment, an explicit reason and
  open questions. Do not fabricate prose to force completeness or a score.

Use only `description-evidence-v1`. Score the support for the exact prose, not
lineage certainty, business importance or production correctness. Positive
criterion points need verified original-CSV references. Mirrors of one claim
are not independent corroboration. The local code recomputes the five-point sum
and rejects invented weights, stale hashes, invalid evidence or arithmetic.

Write `output\06b-ai-drafts\drafts.json` using
[the exact schema and examples](./references/drafts-contract.md). Do not overwrite
the recorded context or its draft template.
Record actual assistant attribution, known model or null, and actual UTC time.
Do not pretend an archived example was newly generated.

## Step 3 — apply, independently testable

```powershell
python -m lineage_poc enrichment apply --input .\output\05-baseline-dictionary --drafts .\output\06b-ai-drafts\drafts.json
```

The CLI prints the new output bundle; application never changes its input.
Missing, duplicate, protected, unknown or unsupported decisions fail before
publication. Python synchronizes all source mirrors and canonical co-input
objects, updates description details and reconciles original-property coverage.
Protected fields and unrelated cells remain exact; untouched new `_json`
assessment cells are `null`. No HTML or implicit site publication occurs.

## Step 4 — independently validate, then explicitly build HTML

```powershell
python -m lineage_poc validate --input .\output\06c-ai-enrichment --baseline .\output\05-baseline-dictionary
python -m lineage_poc html --input .\output\06c-ai-enrichment --baseline .\output\05-baseline-dictionary --graphs .\output\03-lineage-graphs --columns .\output\04-column-lineage
```

Open `output\08-html\index.html`: one file displays both lineage and dictionary.
Keep `tests\fixtures\reference` unchanged. Validation without the original baseline can check
structure/arithmetic, but cannot resolve evidence bound to historical hashes.

Test the actual `V3Bundle.prepareBundle(files, {})` JavaScript importer and
browser behavior: a new draft, a preserved description, needs-evidence if any,
source-group repeats, details, origin filtering and filtered CSV export.
Relationship confidence must stay unchanged. Python assembly alone is not a
browser check; explicitly report any unverified interaction.

## Library/module interfaces

```python
from lineage_poc.enrichment.workflow import prepare_context, apply_drafts
context = prepare_context(input_dir, context_dir)
result = apply_drafts(input_dir, drafts_path, output_dir)
```

```powershell
python -m lineage_poc.enrichment.workflow prepare --input BUNDLE --output CONTEXT_DIR
python -m lineage_poc.enrichment.workflow apply --input BUNDLE --drafts DRAFTS_JSON --output ENRICHED
```

Summaries are JSON-serializable. The parent CLI records executions; these APIs do
not create duplicate journals. No step chooses a latest bundle automatically.
