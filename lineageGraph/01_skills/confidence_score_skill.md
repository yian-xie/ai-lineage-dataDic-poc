# Lineage Confidence Scoring Skill

## Goal

Assign consistent, evidence-backed confidence labels and display scores to lineage relationships and column mappings during a clean graph run. Preserve the source confidence label; the percentage is a shared evidence-strength heuristic, not a calibrated probability or guarantee.

## Score Scale

Apply the highest level whose evidence requirements are all met. Do not interpolate between levels.

| Confidence label | Display score | Minimum evidence | Do not use when |
| --- | ---: | --- | --- |
| `runtime_verified` | 100% | The exact source-to-target path was observed in a successful production-equivalent runtime execution, and the participating physical objects were independently confirmed in a live catalog or equivalent operational record. Record the run/time, environment, and verification source. | Evidence is only repository code, static configuration, a test fixture, or a matching name/pattern. No current POC edge meets this level. |
| `explicit` / `confirmed` | 95% | Checked-in code, configuration, or metadata directly identifies the relationship or mapping. For a cross-repository hop, the source and target identities must be directly supported. | The relationship depends on name similarity, unverified database/schema substitutions, or runtime assumptions. |
| `confirmed_calculated` | 90% | The source fields and deterministic calculation are present in code, and the calculated output mapping is corroborated by a downstream declaration or mapping. Keep the calculation/evidence path. | The result is only a direct copy, or one or more calculation inputs/targets are guessed. |
| `declared_source` | 85% | A dbt source or similar repository declaration names the source relation and its declared schema/database context. | The declaration is being treated as proof that a live physical relation exists or that a job populated it. |
| `inferred` | 60% | Indirect, reproducible evidence identifies a candidate, such as a BASIC output example matching an HVR `Capture.Pattern`, or a documented candidate composite key. Store the matching pattern/example and rationale. | The match cannot be reproduced, or the candidate is only a vague business-name resemblance. |
| `unconfirmed` | 50% | A specific, reviewable candidate is recorded, but required source, target, owner, or identity evidence is still missing. State exactly what remains to be checked. | There is no concrete candidate to review. Use `unknown`/`unresolved` or omit the unsupported relationship instead. |
| `unknown` / `unresolved` / missing confidence | Not rated | No recognized evidence label exists, or the source record omits confidence. Keep it unscored and report the missing evidence separately. | Never convert missing confidence to 0%, 50%, or another numeric score without new evidence. |

The lowest numeric score currently defined for this POC is **50%** (`unconfirmed`). `runtime_verified` at **100%** is a reserved target level and is not currently assigned. The existing static repository graphs contain `explicit` and `inferred` relationships; static evidence alone cannot earn 100%.

## Label Semantics

- `explicit` means a checked-in declaration, code statement, or configuration directly states the relationship.
- `confirmed` means separate repository evidence corroborates the specific mapping or endpoint identity. The display scale groups it with `explicit` at 95%; retain the original label.
- `confirmed_calculated` records an evidence-backed derived value. Document the formula, inputs, and output mapping; it scores 90% rather than 95% when this label is used.
- `declared_source` records declared dbt/source metadata, not a live-catalog check.
- `inferred` records a reproducible but indirect association. Examples include pattern matching and a proposed composite key.
- `unconfirmed` records a concrete candidate that still needs owner or source validation.
- `unknown`, `unresolved`, and missing confidence are not numeric levels. Missing confidence is a data-quality/reporting condition, not a zero score.

## Clean-Run Procedure

1. Rebuild the graph from checked-in inputs with the documented runbook. Do not score stale generated output without identifying its source snapshot.
2. For each edge or selected column mapping, record its exact source and target IDs, relationship/mapping type, source path, evidence text, and raw confidence label.
3. Verify endpoint identity, not just matching words. Check database, schema, relation name, field name/position, and route direction wherever applicable.
4. Assign the highest score in the scale whose minimum evidence is satisfied. Keep inferred and unconfirmed links visibly distinct from direct declarations.
5. For an inferred pattern match, record the source output path, representative filename, exact HVR capture pattern, and matching rule. A pattern match is not runtime delivery evidence.
6. For a calculated column, record the expression, source fields, and the evidence that names the output column. Do not apply 90% to every mapping that happens to be derived if the graph's preserved label is `confirmed`; maintain the source label and explain its meaning.
7. Report missing or unknown confidence separately. Do not silently fill it from neighboring nodes or edges.
8. Validate graph types, unique node identities, endpoints, and confidence-value counts; run the relevant parser tests. A clean code/test run does not upgrade static evidence to runtime-verified.

## Multi-Hop Paths

Score each hop independently and show each hop's label and evidence. If a consumer requests one summary score for a complete path, use the **lowest numeric hop score** as a conservative path score; do not average scores or multiply them. If any required hop is unrated or missing, state that the overall path is incomplete/unrated rather than hiding the gap behind a numeric score.

For example, a path with explicit 95% hops and one inferred 60% capture match is reported as explicit hops plus the inferred hop; if one path score is necessary, it is 60% inferred. This is still an evidence-strength convention, not a statistical probability.

## Required Reporting

For every score, report:

- The raw label and display score, or `Not rated`.
- The exact edge/mapping and source/target identities.
- Source paths and concise evidence.
- Why the score level was met and what would be needed to raise it.
- Whether the statement describes repository configuration, a candidate association, or runtime verification.

Keep HTML percentages consistent with this table. Generated descriptions are navigation aids, not score evidence. Do not use a generated description, graph size, file count, or test pass as justification for a higher confidence level.