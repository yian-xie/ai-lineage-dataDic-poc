# Repo Exploration Skill

**Use this skill whenever a new repository is being added to the lineage system.**
**Goal: understand what is in the repo, compare it to the authoritative schema, and produce a gap report before any parser is built.**

---

## When to Use This Skill

- A new repo has been added to the workspace
- You are unsure whether a repo introduces new node types or edge types
- Another developer needs to understand what a repo contains before writing a parser
- The schema needs to be reviewed before extending the system

---

## Inputs Required

| Input                | Where to find it                                                                        |
| -------------------- | --------------------------------------------------------------------------------------- |
| New repo path        | Provided by the developer; for configured checkouts, resolve it from `sources.json` |
| Authoritative schema | `.github/skills/lineage-workflow/references/graph-schema.md`                         |
| Existing parsers     | `src/lineage_poc/parsers/` — read the closest adapter and its test                    |
| Existing profiles    | `output/repo_profile_*.md` — read relevant prior profiles                            |

---

## Steps — Follow in Order, Do Not Skip

### Step 1 — Count and categorise what is in the repo

Walk the repo, excluding `.git/` internals. For every file type found, record:

- File extension
- Count of files with that extension
- What those files appear to define (one plain-English sentence per type)

Do not read every file. Sample 2–3 files per type to understand the pattern.

Output format:

```
| File type | Count | What it defines |
|---|---|---|
| .sql | 47 | dbt model transformations |
| .yml | 23 | dbt source declarations and column metadata |
```

---

### Step 2 — Identify what concepts the repo introduces

For each file type, answer:

- What real-world thing does this file describe? (a job, a table, a rule, a channel?)
- Does it define how data moves, how data is shaped, or how data is governed?
- Does it reference other systems — Snowflake tables, S3 paths, Airflow DAGs?

Write one paragraph per file type. Plain English. No code.

---

### Step 3 — Compare against the authoritative schema

Read `.github/skills/lineage-workflow/references/graph-schema.md`. It is the
authoritative schema for the current `lineage_poc` graph payloads; do not use an
older `src/lineage/data_lineage_schema.md` path or a copied schema list.

For each concept found in Step 2, check:

- Is there already an entity type in the schema that covers this? If yes — which one?
- Is there already an edge type that covers how this connects to other things? If yes — which one?
- If no match exists — describe the gap in one sentence

Format your comparison as a table:

```
| Concept found in repo | Covered by existing schema? | Existing entity/edge type (if yes) | Gap description (if no) |
|---|---|---|---|
| dbt source declaration | Yes | `DBT_SOURCE` / `RESOLVES_TO` | Keep distinct from physical relation |
| Snowflake table DDL | Yes | `SNOWFLAKE_RELATION` / `MIGRATES` | Covered when the DDL explicitly identifies the relation |
```

Compare semantics and edge direction, not just names. The contract stores graph
nodes as `id`, `type`, `properties` and edges as `source`, `target`, `type`,
`properties`. `source_path` is required provenance. Confidence is scoped to an
edge and inference must remain explicit; do not claim a table edge is a field
mapping.

---

### Step 4 — Propose schema extensions (only if gaps exist)

For each gap identified in Step 3, write a proposal only. Do not edit the
authoritative schema or treat a proposal as approval. Use the existing schema's
entity/relationship section and key-property conventions rather than inventing
a separate `platform`, `layer`, `github_file`, or key-format contract. Include:

```
## Proposed entity type: `CLASSIFICATION_RULE`
- Meaning and candidate properties: state what source evidence actually declares.
- Evidence: exact repository-relative path(s).
- Justification: explain why no current entity type or properties cover it.

## Proposed relationship type: `GOVERNS`
- Direction and candidate endpoints: `CLASSIFICATION_RULE` -> supported target type(s).
- Evidence: exact repository-relative path(s) proving both endpoints and link.
- Justification: explain why no current relationship expresses this connection.
```

Write one block per proposed addition. Keep it short. Do not propose something the existing schema already covers under a different name.

---

### Step 5 — Write the profile report

Output to `output/repo_profile_<repo_name>.md` with these sections:

1. **What this repo contains** — file type table from Step 1
2. **What it defines in plain English** — paragraphs from Step 2
3. **Comparison against schema** — table from Step 3
4. **Proposed schema extensions** — blocks from Step 4 (or "None — existing schema covers all concepts found")
5. **Open questions** — anything ambiguous that a developer or SME needs to clarify

---

## Rules

- **Never invent** — only report what you actually found in the files
- **Label evidence clearly** — mark observations as CONFIRMED when directly read from a file and INFERRED when based on a pattern. These report labels are not graph relationship confidence; parser edges use the graph contract's `explicit`/`inferred` conventions.
- **Do not modify the schema** — the profile is a proposal only. Schema changes happen in a separate step after review
- **Do not build a parser** — this skill is exploration only. Parser creation uses a separate skill
- **One repo per run** — do not profile two repos in one skill execution
- **Keep it readable** — the output will be read by developers who did not write this code. Plain English throughout

---

## Comparison Cheat Sheet — Existing Entity Types

Use the full graph contract when checking Step 3. Common entity types include:

| If the repo contains...                  | Use this entity type       |
| ---------------------------------------- | -------------------------- |
| A legacy BASIC extract program           | `PROGRAM`                |
| A MultiValue source file (ACCOUNT, TRAN) | `MV_FILE`                |
| A pipe-delimited output file             | `EXTRACT_FILE`           |
| An HVR channel config                    | `HVR_CHANNEL`            |
| An HVR named location                    | `HVR_LOCATION`           |
| An S3 bucket path                        | `S3_PATH`                |
| A product directory                      | `CDP_PRODUCT`            |
| An Airflow DAG Python file               | `AIRFLOW_DAG`            |
| An Airflow task or operator              | `AIRFLOW_TASK`           |
| A dbt source declaration (.yml)          | `DBT_SOURCE`             |
| A dbt SQL model                          | `DBT_MODEL`              |
| A physical Snowflake table or view       | `SNOWFLAKE_RELATION`     |
| A schemachange migration script          | `SCHEMACHANGE_MIGRATION` |
| A concrete Snowflake task defined in SQL DDL | `SNOWFLAKE_TASK` |
| A dbt macro/custom materialization definition | `DBT_MACRO` |

This list is illustrative, not exhaustive. A missing row is not by itself a
schema gap: check all contract entities and relationships, properties, and
architectural layers. Keep unsupported concepts as reported facts/open questions
until a team-approved schema extension exists.
