# Confidence scopes

Graph display ratings preserve the source label:

| Label | Heuristic display |
| --- | --- |
| runtime_verified | 100%, reserved for independently established runtime/catalog evidence |
| explicit / confirmed | 95% |
| confirmed_calculated | 90% |
| declared_source | 85% |
| inferred | 60% |
| unconfirmed | 50% |
| unknown / unresolved / absent | Not rated |

These are evidence-strength conventions, not calibrated probabilities. Preserve
the exact relationship or mapping scope and its supporting source paths.
Never upgrade static evidence because a parser or test succeeded.

For a multi-hop explanation, show each hop separately. If a summary is explicitly
requested, use the lowest numeric supported hop and disclose every missing or
unrated required segment. Do not average away a gap.

Dictionary operations have a separate contract. The supplied mapping-level
categories do not provide numeric assessments for every decomposed operation.
Those operations remain Unscored unless a supported explicit assessment exists.

AI description scores are another concept. Follow the
[enrichment skill](../../ai-description-enrichment/SKILL.md) and its
description-evidence-v1 rubric only for newly authored missing descriptions.
Never put description scores into relationship fields or treat a draft as an
approved business definition.
