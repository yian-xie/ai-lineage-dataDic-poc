---
name: lineage-poc-business-briefing
description: "Use when assessing the Ultracs-to-CDP lineage POC hypothesis, preparing business-friendly findings, summarizing scope or counts, explaining lineage/confidence/evidence gaps, or generating a static HTML companion from a Markdown report."
---

# Lineage POC Business Briefing

## Purpose

Turn the repository-static Ultracs-to-CDP lineage POC into accurate, business-friendly findings. Use this skill for executive summaries, POC results, hypothesis assessments, demo narratives, and answers about coverage or feasibility.

The original hypothesis is:

> Can an agent use metadata and code checked into GitHub to parse Ultracs and establish field-level lineage into CDP, then create a useful data dictionary without running Ultracs or connecting to production?

Assess feasibility from evidence in the current workspace. Do not treat a prior presentation, spreadsheet, or generated HTML as authoritative when its numbers disagree with the current JSON outputs.

## Start With Current Evidence

1. Read `data-lineage-poc/README.md` and `data-lineage-poc/01_skills/RUNBOOK.md` to confirm the active scope, repository boundaries, and numbered project structure.
2. Read `data-lineage-poc/04_output/account_column_inventory_summary.json` for current feed and field counts.
3. For details, inspect only the relevant records in `data-lineage-poc/04_output/column_lineage.json`, `dwrel_column_lineage.json`, or the selected `*_column_lineage.json` inventory. Use the source and HVR parameter files cited by those records when needed.
4. Treat `data-lineage-poc/05_ docs/PROJECT_FINDINGS.html` as a presentation artifact. Verify every count and assertion against current output JSON before repeating it.
5. Do not use the workspace-level `old build/` archive as current evidence.
6. The current account POC excludes `kb-cdp-tenant-landing`. Do not read or use that repository to resolve a route unless the user explicitly changes the scope.

## Current Snapshot Reference

The checked-in summary currently reports 26 selected feed families, 660 feed-field positions, 579 case-insensitive distinct `.param` labels, 610 positions with an internal dbt target, 410 with a public dbt target, and 1,166 dbt target projections. These values are snapshot-specific. Re-read the summary JSON and generated inventories before using them in a deliverable.

DWACC remains the most complete column slice: 95 ordered positions, all with internal targets, and 59 reaching public dbt outputs. DWREL is a separate relationship feed whose BASIC-to-parameter pairing is ordinal and inferred. The other feeds are individual output families, not one flattened schema.

The summary counts feed-field positions, not unique business concepts. A label repeated in two feeds is counted twice as a field position. Public/internal field counts count feed records reaching that stage; dbt target-projection counts can be higher because one source field may fan out to several targets.

## Hypothesis Assessment

Use a calibrated conclusion:

- **Supported for a bounded static POC:** checked-in BASIC, HVR, Airflow, dbt, and schema metadata can be parsed and connected into useful table- and column-level lineage for selected account feeds.
- **Not established for every account-related output:** the 26 feeds are the current reviewed scope, not an exhaustive inventory of all account-adjacent Ultracs files.
- **Not production-verified:** parsing repository files does not establish that jobs ran, files were delivered, or production tables contain the expected values.

Explain the evidence in plain language. For example, say “the repository configuration describes this route” rather than “the data successfully flowed in production.”

## Coverage and Caveats

State which level of lineage is evidenced for each feed:

- BASIC output and `.param` counts match: field positions can be paired, but names are still **inferred by position** unless BASIC itself identifies the field names.
- HVR capture exists: a configured filename pattern is present; this alone does not establish successful file delivery.
- Airflow or a RAW source exists: a repository route or table declaration is present; this does not by itself prove a downstream curated model.
- dbt `DATA:<key>` projection exists: an exact field-key-to-model-column mapping is evidenced in source SQL.
- Public output exists: count it only when the public model explicitly selects the field.
- No dbt model exists: describe the inventory as stopping at RAW; do not imply curated CDP lineage.

Preserve known discrepancies. For example, the DWTDS inventory keeps `Prod` distinct from `Product`, DWPP `Desc2` is unmatched, and DWNOMACC `RefDate` is not silently equated with `ReferenceDate`. DWTDET has 28 BASIC/parameter positions but 29 dbt DATA projections; map only exact keys and do not assign the extra projection by guesswork.

The ACCREC_*, DWNOMACC, and DWUNCLD route statuses remain limited based on account-repository evidence. Do not resolve them by consulting the excluded Landing Tenancy repository. Four current feeds stop at RAW because no dbt SQL model was found in the reviewed account repos.

HVR-only or partially traced candidates such as DWAFFP, DWAUDIT_*, DWLNBRL, and DWLRATE2 are not included in the 660-field count. Keep their status as discovered candidates unless an account-owned BASIC-to-HVR-to-ingestion/dbt path is established. Do not count broker/general-ledger outputs as customer-account columns without an explicit business-scope decision.

## Data Dictionary Claims

A DWACC-focused data-dictionary artifact/viewer exists. Describe it as a POC artifact for the traced input fields, not as a complete authoritative enterprise dictionary. Distinguish:

- source evidence from a business-approved definition;
- an extract parameter label from a proven physical Ultracs attribute;
- a repository-sourced description from generated navigation text;
- known datatype/description from missing metadata.

Never claim all account fields have validated definitions if there are unmapped outputs, missing descriptions, positional inferences, or unresolved business meanings. Keep unsupported entries blank or explicitly marked as undocumented, according to the requested artifact format.

## Business-Friendly Writing

Prefer plain terms and explain technical nouns once:

- “legacy Ultracs programs” for BASIC;
- “configured file replication” for HVR;
- “scheduled ingestion workflow” for Airflow;
- “transformation models” for dbt;
- “initial Snowflake landing tables” for RAW.

Avoid “all fields validated,” “successfully flowed end to end,” “production verified,” or “complete account lineage” unless the evidence actually supports those claims. Prefer “mapped in the repository,” “field positions inventoried,” “candidate mapping,” “public model target,” and “not runtime-verified.”

A concise results summary should include:

1. The feasibility conclusion and the bounded scope.
2. Current counts with units (feed positions, distinct labels, target projections).
3. What is complete versus inferred, raw-only, or unresolved.
4. The key runtime and coverage limitations.
5. The next evidence needed to expand or confirm scope.

## HTML Companion

When the user requests HTML for a Markdown briefing or findings report:

1. Keep the requested Markdown file as the source of truth; write a sibling `.html` file unless the user specifies another destination.
2. Use the existing `lineage_poc.publishing.report` rendering conventions: Python-Markdown extensions in `EXTENSIONS`, `page_wrapper`, and the shared `CSS`. Do not create a second visual style or invoke the full report-site builder when only one page is requested.
3. Keep the HTML static and self-contained. Do not query production, execute pipelines, or embed a graph unless requested. Clearly retain the report's repository-static and not-runtime-verified caveats.
4. Preserve headings, tables, lists, fenced code, inline emphasis, and links. Keep relative links valid from the HTML's location; where a linked Markdown page is not rendered alongside it, leave the source path visible rather than creating a broken HTML link.
5. Escape the page title and source label, and use the shared wrapper's responsive layout and print styling.
6. Validate that the output exists, has no unexpanded template markers, contains the expected headings/tables, and that relative links resolve or are visibly represented as source paths. Recheck key counts against the current JSON evidence before publishing them.

For a one-off page, call the Markdown renderer and shared wrapper directly rather than running `build_site`, which copies and renders a broader report bundle. Use the source Markdown's parent-relative path in the page metadata and make the page's home link point back to the Markdown source.

## Example Conclusion

> The POC demonstrates that checked-in Ultracs, HVR, ingestion, and dbt metadata can be used to build field-level lineage and a DWACC data-dictionary view for a bounded set of account feeds. The current inventory covers 26 selected feeds and 660 field positions; it is not an exhaustive count of all account-adjacent outputs. Some source-to-parameter matches are inferred, several feeds stop at RAW, and the repository snapshot has not been runtime-verified.
