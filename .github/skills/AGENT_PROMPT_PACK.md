# Agent Prompt Pack

**Data Exploration + Parser Creation Workflow**
*Use these prompts in order. One prompt per session. Do not skip steps.*

---

## How This Works — Plain English

There are three skills and four prompts. Think of it like this:

```
New repo arrives
      ↓
Prompt 1 — EXPLORE    "What is in this repo?"
      ↓
Prompt 2 — COMPARE    "Does it fit our schema or do we need to extend it?"
      ↓
(Team reviews. Agrees on any schema changes.)
      ↓
Prompt 3 — UPDATE     "Update the schema with the agreed changes."  ← only if needed
      ↓
Prompt 4 — PARSE      "Now build the parser."
```

The skills are the instruction manuals the agent reads before it does anything.
The prompts are what you type into Copilot to start each step.

---

## Prompt 1 — Explore a New Repo

**What it does:** Profiles the new repo. Counts file types. Explains what each file defines in plain English. Does not touch the schema or write any code.

**Type this into Copilot:**

> *"Read @.github/skills/repo_exploration_skill.md and @.github/skills/lineage-workflow/references/graph-schema.md. Follow the exploration skill for the configured repo [repository name or path]. Do not build a parser or change the schema. Save the profile to output/repo_profile_[repo name].md."*

**What you get back:** A markdown report with five sections — what the repo contains, what it defines, how it compares to the existing schema, any gaps, and open questions.

**What to do next:** Read the profile. If there are no gaps — go straight to Prompt 4. If there are gaps — go to Prompt 2.

---

## Prompt 2 — Detailed Schema Comparison

**What it does:** Takes the profile from Prompt 1 and produces a side-by-side comparison of what the new repo introduces versus what the existing schema already covers. Proposes specific additions if needed. Easy to read — no code.

**Type this into Copilot:**

> *"Read @.github/skills/repo_exploration_skill.md, @.github/skills/lineage-workflow/references/graph-schema.md, and @output/repo_profile_[repo name].md. Produce a comparison table mapping each evidenced concept to existing entity/relationship types or an explicit gap. List candidate extensions with one-line justifications in output/schema_comparison_[repo name].md. This is a proposal only; do not edit the schema or treat proposals as approved."*

**What you get back:**

```
Concept in repo          | Existing schema type  | Match?  | Gap / Proposal
─────────────────────────|───────────────────────|─────────|──────────────────
Data classification rule | —                     | No gap  | Propose: CLASSIFICATION_RULE
Landing zone config      | SNOWFLAKE_RELATION    | ✓ Covered | —
Sensitivity label file   | —                     | No gap  | Propose: SENSITIVITY_LABEL
```

**What to do next:** Share this with the team. Agree which proposals to accept. If none — go to Prompt 4. If some — go to Prompt 3.

---

## Prompt 3 — Update the Schema (Only If Team Agreed)

**What it does:** Adds the agreed new types to the authoritative schema cleanly and consistently. Writes a change note so the history is tracked.

**Only run this after the team has reviewed and agreed on the proposals from Prompt 2.**

**Type this into Copilot:**

> *"Read @.github/skills/schema_update_skill.md and @.github/skills/lineage-workflow/references/graph-schema.md. The team approved exactly these changes: [list entity/relationship changes and approval reference]. Apply only those changes to the correct graph-schema.md sections; preserve canonical node/edge payload and provenance conventions. Do not invent extra types. Run focused schema/parser tests and report coverage."*

**What you get back:** An updated `.github/skills/lineage-workflow/references/graph-schema.md` with only the explicitly approved types and relationship semantics added to the relevant sections.

**What to do next:** Confirm the tests pass. Then go to Prompt 4.

---

## Prompt 4 — Build the Parser

**What it does:** Builds the actual Python parser for the new repo. The caveman-style skill keeps instructions short so the agent uses fewer tokens and stays focused.

**Type this into Copilot:**

> *"Read @.github/skills/parser_creation_skill.md, @.github/skills/lineage-workflow/references/graph-schema.md, and @output/repo_profile_[repo name].md. Check the existing adapter and test pattern under src/lineage_poc/parsers/. Build the smallest requested parser using only schema-approved entity and relationship types, canonical graph fields, repository-relative source_path, and explicit/inferred confidence with reasons. Run it against the configured read-only source checkout, write output/[repo name]_raw.json, and run focused schema/endpoint tests. Do not treat a standalone adapter as integrated into the staged CLI unless that integration is explicitly requested."*

**What you get back:**

- `parsers/[repo name]_parser.py` — the new parser
- `output/[repo name]_raw.json` — the validated JSON payload
- A validation report showing all checks pass

---

## For New Developers — Start Here

You are adding a new repo to a lineage system that already has:

- An existing `lineage_poc` package under `src/lineage_poc/`
- An authoritative graph contract at `.github/skills/lineage-workflow/references/graph-schema.md`
- Exploration, schema-update, parser-creation, and workflow instructions under `.github/skills/`
- Six configured source checkouts in `sources.json`; configured does not mean parsed or graph-integrated

**Your job is simple:**

1. Run Prompt 1 on your repo
2. Read the profile that comes back
3. If there are gaps — run Prompt 2 and show the team
4. If the team explicitly approves schema changes — run Prompt 3; otherwise skip it
5. Run Prompt 4 to build and test the parser

**Do not:**

- Write a parser before running Prompt 1
- Change the schema without a reviewed comparison and explicit approval
- Skip the validator at the end of Prompt 4

**If something is confusing:** Read the skill file for that step. The skill file is the full explanation. The prompt is just the trigger.

---

## Quick Reference — Which Skill Does What

| Skill file | What it does | When to use |
| --- | --- | --- |
| `.github/skills/repo_exploration_skill.md` | Profiles one repo and compares concepts with the graph contract | Before parser work |
| `.github/skills/parser_creation_skill.md` | Builds a schema-compliant adapter using existing package patterns | After profile and scope are agreed |
| `.github/skills/schema_update_skill.md` | Applies explicitly approved changes to the authoritative graph contract | Only after team approval |
