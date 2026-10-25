# Deterministic projection contract

## Tables, scope and identity

- `asset_registry.csv`: source contexts, reported extract files and reported
  Snowflake relations.
- `field_catalog.csv`: canonical scoped source references, extract slots, logical
  RAW JSON keys and declared Snowflake target columns.
- `data_dictionary.csv`: one original source mapping and one exact declared
  target; every target and original record is preserved.

Join with `(graph_id, snapshot_id, ID)`, never names or CSV line numbers. Snapshot
IDs bind the exact source JSON SHA256. Stable IDs are derived from typed,
canonical identity parts, not folder names, timestamps or traversal counters.
Preserve row order, unknown supplied properties, original columns and input
records. Matching source/target rows repeat the same source metadata. Shared
canonical fields and operations cannot conflict.

## Source normalization

Ultracs is a MultiValue source context, not a physical file inferred from a
record variable or mapping label. The supplied program, source locator and
reported source references remain separate claims.

Only complete simple locators are parsed:

```text
AREC<19>       record reference AREC, attribute 19
AREC<19,2>     attribute 19, value 2
AREC<19,2,3>   attribute 19, value 2, subvalue 3
AREC @ID      record-key reference @ID, not attribute zero
```

Positions must be positive. Expressions, compound references, bare variables,
ambiguous aliases and unsupported syntax remain unnormalized. Different record
variables with the same coordinate are not proven aliases. Preserve conflicts,
unresolved bindings and supplied expressions without executing them.

Extract positions are output slots, not source attributes. A reported extract
file/header is not an invented HVR table. RAW `DATA:key` fields are logical JSON
paths, not asserted physical Snowflake columns. Internal/public target bindings,
renames and transformations are scoped to the exact declared target.

## Descriptions and governance

Descriptions are exact own-field input text; route or model metadata must not be
inherited as a field definition. Six provenance columns retain source type,
author, generator, reference, pointer and complete provenance JSON. Dictionary
source/target mirrors join to their own canonical fields.

Source types:

| Value | Meaning |
| --- | --- |
| `not_supplied` | No non-whitespace text for this exact field |
| `unknown` | Text exists without a recognized scoped origin, or origin claims conflict |
| `existing_metadata` | Explicit column-scoped existing/repository/documentation/human origin claim |
| `ai_generated` | Explicit column-scoped AI/LLM/model origin claim |

These are **reported claims**, not independent verification. Paths, author names
and `recorded_input` labels alone do not prove authorship. Keep conflicting
claims rather than selecting a silent winner. The original JSON description
pointer is the immediate source of supplied text; BASIC/YAML paths are context,
not automatically the author of a description.

Missing governance, physical file binding, owner, steward, domain, PII, row
counts and approved business definitions remain blank or explicitly unknown.
An AI technical draft does not approve a business definition.

## Operations, confidence and coverage

Only supplied categorical mapping confidence is supported by generation.
Preserve it at its original mapping-record scope. Atomic operations remain
unscored when no numeric relationship assessment was supplied; do not invent a
score, convert a label to a percentage, or average relationships into field or
description confidence. Description evidence uses a separate explicit rubric.

Every represented operation retains inputs, outputs, roles, expressions,
output bindings, source evidence, associations and confidence. Field incident
operations and both directions of field/asset adjacency must match those exact
operations. Missing reverse edges are errors, not automatic repairs.

`original_record_json` retains the typed input archive. `input_property_map_json`
accounts for **every** object, array, scalar, null and empty value using exact
JSON pointers. Every pointer keeps its original-record destination; other
destinations must still resolve to the original value. Scalar CSV formula
escaping is reversible and recorded, never applied inside the JSON archive.

New enrichment must reconcile intentionally changed description destinations:
an old blank description must not remain falsely `verified_visible` after AI
text replaces it. Raw archives, operations, confidence and unrelated metadata
never receive the new prose.

## Serialization and validation boundaries

CSV output uses UTF-8 BOM, quoted cells and CRLF records. JSON projection is
canonical and preserves typed values. Duplicate keys, nonfinite JSON numbers,
duplicate headers, ragged rows and conflicting identities are rejected.
Existing optional registry JSON cells may be blank for legacy null values;
new assessment `_json` cells must use JSON `null`, never empty text.

Every decoded cell must fit Excel's 32,767-character text-cell limit when
claiming spreadsheet compatibility. Never truncate descriptions or evidence.
The supplied baseline has 7 assets / 464 fields / 179 mappings and
25 / 47 / 106 columns; enriched examples have 25 / 52 / 111 columns. These are
regression controls for this input, not hardcoded requirements for other inputs.

The implementation lives in `src\lineage_poc\dictionary`,
`src\lineage_poc\validation` and `src\lineage_poc\viewers\dictionary`.
