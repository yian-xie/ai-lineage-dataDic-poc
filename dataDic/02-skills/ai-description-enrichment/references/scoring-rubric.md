# Description evidence rubric: description-evidence-v1

## What is being scored

The score rates **support in the supplied CSV evidence for the exact
AI-generated description**. It is an AI self-assessment using an explicit
checklist, not calibrated model certainty, lineage confidence, or production
verification.

Apply this rubric only when filling a missing description. Existing descriptions
and any existing assessments must remain unchanged; do not generate a replacement
description or new confidence score for them.

Score the finished description, not the field's importance or how familiar its
name sounds. Unsupported assertions must be removed or rewritten before scoring.
A low score is not permission to publish an invented business meaning.

## Five criteria, each worth 0-2 points

| Criterion | 0 points | 1 point | 2 points |
| --- | --- | --- | --- |
| `identity_grounding` | The relevant field/context cannot be uniquely identified. | A unique scoped reference is known, but its physical binding, aliases, or operands remain unresolved and the draft states that boundary. | The identity and source locator/binding used in the description are explicitly and consistently supported. |
| `meaning_support` | Meaning is guessed from a name, abbreviation, or general domain knowledge. | Supplied evidence supports a limited technical role; business meaning remains undocumented or only indirectly suggested. | Supplied source description/comment or equivalent field-specific evidence explicitly supports the described meaning. |
| `transformation_support` | The described processing is absent, opaque, or contradictory. | A recorded expression or summary supports only part of the processing and the draft does not claim more. | Recorded input/output bindings and the relevant expression/summary consistently support the complete processing claimed in the draft. |
| `corroboration` | No distinct supporting claim exists, or relevant claims conflict. | A relevant linked projection, target definition, or other distinct claim supports part of the draft. | At least two distinct, mutually consistent field-specific claims support its interpretation; duplicate copies do not count. |
| `uncertainty_handling` | The draft hides a known gap, contradiction, inference, or unsupported certainty. | The draft is cautious but leaves an important limitation or distinction unclear. | The draft accurately limits its claims and explicitly states applicable missing meaning, unresolved bindings, inference, or conflicts. |

For a direct field with no transformation claimed, explicit direct
binding/projection evidence can earn transformation points. Do not award points
just because a transformation is unnecessary.

For `identity_grounding`, a canonical field ID establishes uniqueness within the
snapshot, not a physical MultiValue file. For `meaning_support`, a Snowflake
description is not automatically a source definition. A bare variable does not
prove a calculation. Macro names do not prove their implementation.

For `uncertainty_handling`, two points require checking the actual notes,
bindings, and conflicts. A generic "AI-generated" disclaimer alone is insufficient.

## Calculation and interpretation

```text
score_10 =
    identity_grounding.points
  + meaning_support.points
  + transformation_support.points
  + corroboration.points
  + uncertainty_handling.points
```

Each component is an integer in `{0, 1, 2}`. Compute the final score locally
rather than accepting the AI's arithmetic without checking it.

| Score | Evidence-support label |
| --- | --- |
| 0-2 | Limited |
| 3-5 | Partial |
| 6-8 | Grounded within supplied evidence |
| 9-10 | Strong, consistent supplied evidence |
| null | Unscored: no supportable draft was produced |

All labels remain within the `supplied_csv_only` boundary. Even 10/10 is not a
probability, certified business definition, human approval, or runtime check.
Do not display a converted percentage as probability.

An absent assessment is null, not zero. Zero is valid only for an explicitly
completed assessment with zero earned points. If the field cannot be identified
or the draft still makes unsupported claims, use `needs_evidence` instead of a
score. Do not invent evidence to reach a preferred threshold.

## Evidence requirements

For each criterion, record:

- Criterion ID and awarded points.
- A short, field-specific reason for the award and any missing points.
- Relevant evidence references, or an explicit explanation that evidence is
  missing. Every positive award must have a verifiable supporting reference.
- Any conflict or limitation affecting the criterion.

An evidence reference identifies:

```text
file: asset_registry.csv | field_catalog.csv | data_dictionary.csv
input_sha256: exact hash of that source file
graph_id and snapshot_id
row_id_column: asset_id | field_id | dictionary_entry_id
row_id: exact scoped row identity
column: exact CSV column name
json_pointer: exact pointer within a JSON cell, or null for a scalar cell
value: the exact cited scalar or parsed JSON value
```

Resolve each reference back to the unchanged source CSV and compare its value.
Do not cite a CSV line number: quoted multiline cells make line numbers
different from row identities. Do not use the generated draft or its own
assessment as evidence for itself.

Projections, descriptions, and notes in the CSV are **reported claims**.
Recording a repository path does not prove that file was read or that production
executes it. Do not claim independent corroboration from mirrors of one original
claim across the three CSVs.

## Assessment object

Use the following structure; placeholders are schema guidance, not real scores:

```text
assessment_scope: "description_evidence"
assessment_origin: "ai_self_assessment"
rubric_id: "description-evidence-v1"
verification_mode: "supplied_csv_only"
score_10: sum of the five component points, or null
components: one entry per criterion, with points, reason, evidence_refs, limitations
calculation: the actual arithmetic, such as "1 + 1 + 1 + 1 + 2 = 6 / 10"
rationale: concise explanation of why the exact description earns that result
limitations: applicable unresolved questions and evidence boundaries
assessed_by: actual assistant identity when known
model: actual model identifier when known; otherwise null
assessed_at: actual UTC assessment time
human_review_status: "not_reviewed"
```

The arithmetic above is illustrative, not a rating to reuse for unrelated fields.
No hidden weights, extra bonuses, categorical-label lookup, or relationship-score
average is permitted by this rubric. A changed method requires a new rubric ID.
