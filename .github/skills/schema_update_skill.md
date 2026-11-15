
# Schema Update Skill

**Use this only after a repo profile/gap analysis has been reviewed and the exact change has explicit team approval.**
**Never update the schema mid-parser. Schema changes happen separately.**

---

## When This Skill Is Used

A repository was profiled using `.github/skills/repo_exploration_skill.md` and
compared against `.github/skills/lineage-workflow/references/graph-schema.md`.
The team approved a specific entity or relationship extension. A proposal file
or profile alone is not approval; do not infer acceptance from a proposed type.

This skill adds the new type cleanly and consistently.

---

## Steps

### Step 1 — Read the current schema

Read `.github/skills/lineage-workflow/references/graph-schema.md` in full
before making any change. Confirm the approved concept is not already covered
by an entity, relationship, property, layer, or unresolved-declaration rule.

### Step 2 — Add the new entity type (if needed)

Add the entity to the correct existing subsection/table in the graph contract.
Follow that table's actual columns (currently type, meaning, and key properties).
Document only required properties supported by the approved slice. Do not
invent a universal `platform`, `layer`, `github_file`, or key-format table.
`layer` is architectural metadata, not an entity type; add or change a layer
only when the approved concept requires it. Preserve stable, namespaced identity
conventions and the required repository-relative `source_path` provenance.

### Step 3 — Add the new edge type (if needed)

Add the relationship under the relevant existing section (data movement,
orchestration, dbt, migration, or another appropriate group). Follow the graph
contract's direction convention and document allowed endpoints and meaning.
Document operation/evidence properties, `source_path`, and `confidence` plus a
reason for inferred links where applicable. Do not overload a related but
semantically different edge type.

### Step 4 — Update related contract rules

Update only directly affected modeling rules, layer definitions, route
boundaries, or unresolved-declaration constraints. The current graph contract
does not define a mandatory repository-status table or key-format table; do not
add either as a side effect.

### Step 5 — Record and verify the change

Preserve the document's current organization. Add a concise change note only if
the user or repository convention requests one; do not assume a `Change History`
section exists. Check for duplicate/conflicting names and verify directions,
properties, provenance, confidence semantics, and boundaries in context.

---

## Rules

- Apply only the exact approved additions. Do not expand a proposal or add adjacent types without approval.
- The team must agree before this skill runs. Never update unilaterally.
- Preserve existing types, identities, directions, and compatibility notes; do not rename existing values.
- Do not implement parsers in this step. If parser code is separately requested, follow `parser_creation_skill.md` after the schema review/update.
- Run focused tests that assert graph/schema contracts; run broader tests when code is also changed. Report any contract area not directly covered by tests.
