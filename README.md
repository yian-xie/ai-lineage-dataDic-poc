# Lineage Graph and Data Dictionary

This project reads Ultracs, HVR, Airflow and dbt metadata, builds lineage JSON,
creates a three-CSV data dictionary, and displays **both the graph and dictionary
in one final HTML report**.

Every step can run separately. All intermediate results and debug logs are saved
under **one `output` folder**. Each step keeps only its latest files; rerunning
does not create another run/attempt directory tree.

## Structure

```text
README.md                    Setup, steps and how to use the result
pyproject.toml               Python package and dependencies
sources.json                 Repository URLs and checkout location
source-repos\                Local Git checkouts (ignored by this repository)
  kb-ultracs-datawarehouse\
  kb-cdp-hvr\
  kb-cdp-tenant-account\
  kb-cdp-tenant-enterprise\
  kb-cdp-tenant-protect-downstream\
  kb-cdp-tenant-landing\
  kb-accounts\
  kb-cdp-tenant-protect-downstream\
  kb-cdp-tenant-landing\
repo-understanding\          Source repository roles, evidence and integration notes
.github\skills\              Lineage, dictionary and AI-description instructions
src\lineage_poc\              Working parsers, builders and viewer code
tests\                       Tests and required regression fixtures
output\                      All step outputs, logs and the final HTML
```

The source checkouts live **inside this application folder**, under
`ai-lineage-dataDic-poc\source-repos`. Each keeps its own Git history, but the
entire folder is excluded from the application's Git tracking. Their URLs and
location are configured in [sources.json](./sources.json). No production
credentials are required.

The configuration includes seven repositories. Landing and Protect-downstream
are parsed into separate graph snapshots. `kb-accounts` contributes a separate
.NET project-reference graph; it is not data lineage and is not merged into the
canonical data graph. The [repository understanding report](./repo-understanding/README.md)
documents the evidence boundaries between these sources.

The configured location is relative to that configuration file, not to the
terminal's working directory. `--source-root` or `LINEAGE_SOURCE_ROOT` can still
select another explicit checkout location when needed.

## Install

Use Python 3.10+ and Git. Run commands from this application folder:

```powershell
python -m pip install -e ".[test]"
python -B -m lineage_poc --help
```

Git uses your existing GitHub sign-in. Do not put passwords or tokens in
configuration files. Existing source checkouts are never automatically pulled,
reset or overwritten.

## Run everything in VS Code Copilot Chat

Open this application folder in VS Code, select **Agent** mode in Copilot Chat,
and ask:

```text
Follow .github/skills/lineage-workflow/SKILL.md.
Complete the full workflow and resume from the first unfinished step.
Generate missing Ultracs descriptions in this chat, validate them,
and finish with the combined lineage graph and data dictionary HTML.
```

If VS Code offers `/lineage-workflow` in its slash-command menu, you can invoke
that instead. If it does not, use the explicit file instruction above.
The [existing skill](./.github/skills/lineage-workflow/SKILL.md) guides the current
Copilot Chat agent; it does not start a separate AI process.

**No Copilot CLI installation, executable-path setting or separate CLI AI
sign-in is needed.** The current chat session authors the descriptions.
Git access to the configured source repositories is still required, and VS Code
may ask you to approve local tool execution.

The agent runs the existing Python parsers, validators and renderer internally,
so Python remains installed, but you do not need to type each command yourself.
All outputs and debug records remain under the same `output` folder.

### Resume from a completed step

For example, tell Copilot Chat:

```text
Follow .github/skills/lineage-workflow/SKILL.md.
Steps 1 and 2 are already completed. Verify their saved records,
start at step 3, and complete the remaining steps.
Do not clone or parse the repositories again.
```

The skill checks recorded status and input/output hashes before skipping work.
A folder existing is not enough. Missing, failed or changed prerequisites are
reported rather than silently reused. A fresh workspace starts at step 1.

The stages are: **1 repositories > 2 parsing > 3 graphs and column JSON >
4 baseline CSVs > 5 descriptions > 6 validation > 7 combined HTML**.
Open **`output\08-html\index.html`** after all required stages pass.

### Rerun selected steps

You can ask the same skill:

```text
Follow .github/skills/lineage-workflow/SKILL.md.
Rerun step 3 only. Keep the saved source/parse results.
```

Or ask **"rerun steps 4 through 7"**, **"rerun validation only"**, or
**"rebuild the HTML for Account_ID and OpenDate"**.

An explicit rerun executes the requested steps even if they previously passed.
The agent verifies prerequisites, runs them in dependency order, keeps the same
output folders and logs, and does not repeat unrelated work. If an upstream
rerun makes later results stale, it tells you what needs refreshing rather than
silently rerunning everything or presenting an old HTML as current.

The individual commands below are also available for debugging or rerunning a
specific stage. The skill uses these same commands, not a second implementation.

## Processing steps

### 1. Download or verify the configured repositories

```powershell
python -B -m lineage_poc sources --clone
```

Creates missing checkouts and records their exact commits.
Result: `output\01-sources`.

### 2. Parse source metadata

```powershell
python -B -m lineage_poc parse
```

Reads BASIC, HVR, Airflow, dbt and migration files without executing them.
Saves parser results and a compact source-evidence archive for replay/debugging.
Result: `output\02-parsing`.

Individual parsers can also be run with `--parser basic`, `--parser landing`,
`--parser protect_downstream`, or `--parser accounts`; check `parse --help` for
the full set. `--parser all` includes the configured optional repositories when
their checkouts are present.

For exactly Landing, Protect-downstream and `kb-accounts`, use the dedicated
`tmv` parser with a configuration containing only those repositories, then
build with `graphs --scope tmv`. This writes their three standalone graphs,
`table_lineage.json` (the Landing + Protect data-graph union), and
`all_repositories_lineage.json` (the same data graph plus a separate .NET
project component), without capturing the core Ultracs/HVR/Account/Enterprise
repositories. The graph unions add no unsupported bridge edges.

For the Account-only slice of those three repositories, use `parse --parser
tmv-account` instead. It captures Landing Account public-model roots and their
dependencies within `ultracs-v1`, six Protect Account products with unused
source declarations pruned, and the separate `kb-accounts` software component.
The explicit seed list and dependency rules are saved as `account_scope` in the
parse and dictionary manifests. Joined customer/reference fields remain
dependency context, not independently selected products.

`columns --feed TMV` writes a SQL-derived `04-column-lineage\column_lineage.json`
and `column_lineage_gaps.json`. It records mappings only when SQLGlot resolves
the source column to a relation in the same repository graph. It does not infer
cross-repository column links or make this custom TMV inventory a valid input to
the legacy three-CSV dictionary. Use `tmv-html --graphs ... --columns ... --gaps ...`
to render the graph pages and column mapping view under `08-html`.

TMV dictionary generation uses the separate `tmv-dictionary-v1` adapter, not
the Ultracs adapter. Run `tmv-dictionary`, `tmv-enrichment prepare/record/apply`,
and `tmv-validate`, with `--output-dir .\TMV_output` on every stage. Only blank,
mapped TMV target-field descriptions without metadata conflicts are eligible
for assistant-authored technical drafts. Existing descriptions are preserved.
The `.NET` project component does not receive invented dataset/field entries.
Use `tmv-html --dictionary .\TMV_output\06c-ai-enrichment --baseline
.\TMV_output\05-baseline-dictionary` along with the matching graph/column paths
to embed the validated three-CSV bundle in the single HTML report. The TMV CSVs
have their own declared contract and are not compatible with the legacy V3
importer. Full instructions are in `../new_skill/tmv-description-enrichment/SKILL.md`.

### 3. Build the lineage graph and column inventory

### Four-Repository Account Domain

The `account-domain` profile selects `kb-accounts`, `kb-cdp-tenant-account`,
`kb-cdp-tenant-enterprise`, and `kb-cdp-tenant-protect-downstream`. It excludes
Landing, HVR, and Ultracs BASIC checkouts. Account and Enterprise Account product
lists come from `parsers/snapshot.py`; Protect uses the six Account products in
`parsers/tmv_account.py`. Product models and their referenced source/physical
dependencies are retained; unused source declarations are excluded. Joined
customer/reference fields are dependency context, not independently selected
domains. Source/configuration files are archived unchanged and are not executed.

Use the separate `Account_Domain_output/sources.json` configuration. All stages
keep their usual recorded integrity and rollback behavior, starting at parsing:

```powershell
python -B -m lineage_poc parse --parser account-domain --config .\Account_Domain_output\sources.json --source-root .\source-repos --output-dir .\Account_Domain_output
python -B -m lineage_poc graphs --parsed .\Account_Domain_output\02-parsing --scope account-domain --output-dir .\Account_Domain_output
python -B -m lineage_poc columns --parsed .\Account_Domain_output\02-parsing --graphs .\Account_Domain_output\03-lineage-graphs --feed TMV --output-dir .\Account_Domain_output
python -B -m lineage_poc tmv-dictionary --input .\Account_Domain_output\04-column-lineage\column_lineage.json --parsed .\Account_Domain_output\02-parsing --graphs .\Account_Domain_output\03-lineage-graphs --output-dir .\Account_Domain_output
python -B -m lineage_poc tmv-enrichment prepare --input .\Account_Domain_output\05-baseline-dictionary --output-dir .\Account_Domain_output
```

The `tmv-*` commands reuse the strict SQL dictionary contract with explicit
`run_profile=account-domain` and a four-repository allowlist. They do not apply
the legacy Ultracs dictionary adapter or broaden its enrichment eligibility.
The current assistant authors or explicitly revalidates exact-match technical
drafts, then records/applies them with `tmv-enrichment record/apply`. Reuse must
retain `reused_from`, current context/CSV hashes, and the original attribution;
it is not newly generated prose. Existing descriptions remain unchanged.

```powershell
python -B -m lineage_poc tmv-validate --input .\Account_Domain_output\06c-ai-enrichment --baseline .\Account_Domain_output\05-baseline-dictionary --output-dir .\Account_Domain_output
python -B -m lineage_poc tmv-html --graphs .\Account_Domain_output\03-lineage-graphs --columns .\Account_Domain_output\04-column-lineage\column_lineage.json --gaps .\Account_Domain_output\04-column-lineage\column_lineage_gaps.json --dictionary .\Account_Domain_output\06c-ai-enrichment --baseline .\Account_Domain_output\05-baseline-dictionary --output-dir .\Account_Domain_output
```

The final `Account_Domain_output/08-html/index.html` embeds the complete dictionary
using the reference template and application scripts through the SQL adapter.
The .NET project component remains software lineage. The Account-domain profile
also captures production C# entities, configurations, migrations and EF model
snapshots. `kb_accounts_data_lineage.json` records distinct CLR entities and
repository-declared PostgreSQL relations; explicit property/column bindings,
flattened complex properties and named JSON document columns appear in the
dictionary and column view without being relabeled as SQL transformations.
Database/context identities and null schemas remain unverified or unspecified.
The column stage also writes `kb_accounts_schema_inventory.json`,
`kb_accounts_migration_evidence.json` (historical `Up` operations, not executed),
and `kb_accounts_assignment_evidence.json` (unbound mapper assignments, not graph
edges). C# runtime semantics, imported/conditional configuration, unsupported
syntax and cross-repository service/data bindings remain explicit gaps.
Property XML summaries are preserved with their original documentation evidence.
The parser uses Tree-sitter C# syntax trees; it does not execute C#, EF or MSBuild.

The Account-domain product allowlist also includes the Account profile,
posting/transaction/EOD topic products and Account migration reconciliation.
Namespace-resolved C# assignments add `ASSIGNS_TO_EVENT` relationships with exact
field-mapping IDs; declared event wrapping and typed outbox calls add
`WRAPPED_IN_EVENT` and `PUBLISHED_VIA`. These are CLR contract relationships,
not inferred JSON-wire or cross-repository field equivalence. Publication stops
at explicit unresolved topic boundaries. Diagnostic exception-message references
are not treated as value dependencies.

Every extracted `kb-accounts` EF field has a record in
`04-column-lineage/kb_accounts_field_relationship_assessments.json`, including
unmapped fields and unresolved transport. These gaps are also retained in
`column_lineage_gaps.json`; successful parsing does not establish full connectivity.

For the focused report, reuse the accepted stages rather than parsing again:

```powershell
python -B -m lineage_poc tmv-html --graphs .\Account_Domain_output\03-lineage-graphs --columns .\Account_Domain_output\04-column-lineage\column_lineage.json --gaps .\Account_Domain_output\04-column-lineage\column_lineage_gaps.json --dictionary .\Account_Domain_output\06c-ai-enrichment --baseline .\Account_Domain_output\05-baseline-dictionary --selector Account_ID ACCOUNTID --report-name accountid --output-dir .\Account_Domain_output
```

This selector also matches case-insensitive EF `AccountId`/`account_id` names,
without treating every matching name as the same business or physical identity.
Graph unions do not invent cross-repository bridges; unresolved SQL, deployment,
and business-meaning questions remain explicit. Prior `output` and `TMV_output`
artifacts are not modified. Static/Node checks are not browser or live-system
verification.

### Default Graph and Column Commands

```powershell
python -B -m lineage_poc graphs --parsed .\output\02-parsing
python -B -m lineage_poc columns --parsed .\output\02-parsing --graphs .\output\03-lineage-graphs
```

Results: `output\03-lineage-graphs` and
`output\04-column-lineage\column_lineage.json`. When present, stage 3 also
contains separate `landing_tenant_lineage.json`,
`protect_downstream_lineage.json`, and `kb_accounts_project_lineage.json`
snapshots. The .NET project graph remains supplemental. The column JSON is the
input to the data dictionary, not the final HTML; repository graph snapshots do
not create column mappings by themselves.

To keep a run separate from the default outputs, pass a different output root
to each stage, for example `--output-dir .\TMV_output`.

### 4. Generate the three baseline CSVs

```powershell
python -B -m lineage_poc dictionary --input .\output\04-column-lineage\column_lineage.json
```

Result: `output\05-baseline-dictionary`, containing:

- `asset_registry.csv`
- `field_catalog.csv`
- `data_dictionary.csv`

This step preserves supplied descriptions. It does not generate AI prose.

**Required scope warning for every fresh dictionary run:** Missing-description
enrichment currently applies only to canonical Ultracs source fields whose
descriptions are blank. It does not create descriptions for HVR, CDP/Airflow/dbt,
RAW/Snowflake, asset, or already-described fields. A broader override is a
workflow contract change, not a run flag: supported identities and evidence,
provenance and preservation validation, CSV projection, viewer behavior, and
tests must all be updated and explicitly approved. Until then, keep enrichment
within the current Ultracs-only scope and do not infer definitions from names.

### 5. Use the AI skill to fill missing Ultracs descriptions

```powershell
python -B -m lineage_poc enrichment prepare --input .\output\05-baseline-dictionary
```

The context is saved in `output\06a-enrichment-context`. The current Copilot Chat
assistant follows [the AI enrichment skill](./.github/skills/ai-description-enrichment/SKILL.md)
to author new descriptions and assessments in this session. It writes the
complete draft payload to the temporary **`output\assistant-drafts.json`**.

Record and validate those drafts:

```powershell
python -B -m lineage_poc enrichment record --input .\output\05-baseline-dictionary --drafts .\output\assistant-drafts.json
```

The validated exact draft file is saved in
**`output\06b-ai-drafts\drafts.json`**, with a successful step record. The
temporary pending file can then be removed. This also replaces an earlier
failed draft-stage record safely; do not write into a failed stage by hand and
pretend it passed.

The assistant authors one-or-two-sentence descriptions. Existing descriptions
stay unchanged. Python checks the evidence and arithmetic; it does not generate
template prose, call a model API, or launch Copilot CLI.

Apply the saved drafts:

```powershell
python -B -m lineage_poc enrichment apply --input .\output\05-baseline-dictionary --drafts .\output\06b-ai-drafts\drafts.json
```

Result: the three enriched CSVs in `output\06c-ai-enrichment`.

### 6. Validate the enriched bundle

```powershell
python -B -m lineage_poc validate --input .\output\06c-ai-enrichment --baseline .\output\05-baseline-dictionary
```

Checks preservation, identities, references, evidence, scores and CSV consistency.
Result: `output\07-validation\validation.json`.

### 7. Build the final combined HTML

```powershell
python -B -m lineage_poc html --input .\output\06c-ai-enrichment --baseline .\output\05-baseline-dictionary --graphs .\output\03-lineage-graphs --columns .\output\04-column-lineage
```

**Open `output\08-html\index.html` in Edge or Chrome.**
Use its graph views to inspect lineage and its **Data Dictionary** view to access
Dictionary, Asset Registry and Field Catalog. Both use the selected saved data.
No manual CSV import is needed. The data is embedded; graph-library requirements
are recorded by the HTML checks.
The dictionary works offline. The graph retains its existing vis.js CDN
dependency, so the browser must be allowed to load that library.

To see an AI description's score: **Data Dictionary > Field Catalog > open a
field > Description provenance**. Description scores are not relationship scores
or business approval.

## Create a separate HTML for one or more columns

You can generate a new report from the existing outputs without downloading
repositories, parsing sources, or running AI enrichment again.

Run these commands from the application root in PowerShell. To ensure Python
uses this checkout (rather than another editable `lineage-poc` installation),
put its `src` directory first on the import path:

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
```

First, check the column mapping. For Account_ID:

```powershell
python -B -m lineage_poc query --columns .\output\04-column-lineage\column_lineage.json --column Account_ID
```

Then generate its separate HTML:

```powershell
python -B -m lineage_poc html --input .\output\06c-ai-enrichment --baseline .\output\05-baseline-dictionary --graphs .\output\03-lineage-graphs --columns .\output\04-column-lineage --selector Account_ID
```

The command writes a separate report; it does not open the browser automatically.
Open it with:

```powershell
Start-Process .\output\08-html-accountid\index.html
```

The main `output\08-html\index.html` is left unchanged.

For several columns in **one** new report, pass each selector after
`--selector`:

```powershell
python -B -m lineage_poc html `
  --input .\output\06c-ai-enrichment `
  --baseline .\output\05-baseline-dictionary `
  --graphs .\output\03-lineage-graphs `
  --columns .\output\04-column-lineage `
  --selector Account_ID OpenDate
```

Open the generated report with:

```powershell
Start-Process .\output\08-html-accountid-opendate\index.html
```

To use a label with spaces, quote it, for example
`--selector "Account ID" "Account Opened Date"`.

- Change `$column` to another recorded selector, such as `OpenDate`, `Balance`,
  or `KIWIBANKACCOUNTNUMBER`. Parameter names, target column names, mapping IDs
  and business-field labels are supported; unknown selectors report an error.
- The output folder uses the selectors in lowercase without punctuation or
  spaces, sorted and joined by dashes. Very long selections use a short hash
  suffix. Changing the order of the same selectors uses the same report folder.
- The graph focuses on the matching column mapping(s) and keeps shared route
  context. The embedded data dictionary stays complete; filter it to the
  selected source when needed.
- Selected-column reports also show a **FIELD PATH** section above the graph:
  reported Ultracs source, extract position, HVR parameter/route, RAW relation
  and Snowflake target, with confidence and expandable evidence. Multiple
  selected mappings have separate paths. The main all-column report does not
  include this section.
- Account_ID is recorded as `KiwiAcc`, DWACC position 7, mapping to internal
  and public `KIWIBANKACCOUNTNUMBER`. It is different from `Account_Index_ID`,
  whose selector returns both inferred components.
- Overlapping selectors are deduplicated: `Account_ID` and `KiwiAcc` do not
  repeat the same mapping. Every selector must match; unknown names fail instead
  of silently producing a partial report. Select fields from one extract feed
  per report.
- Rerunning the same selection replaces only that selection's report. Other
  focused reports and the main report remain unchanged. Its validation and
  diagnostic records are saved under `output\logs`.

The HTML page's search box filters the current view only. It does not create a
new file; use the commands above to save a separate column-focused report.

## Optional terminal coordinator

```powershell
python -B -m lineage_poc pipeline --clone
```

This deterministic coordinator runs the preparation steps and stops at
`status: awaiting_ai_drafts` and exit code **3**. After authoring drafts, run the
remaining steps above, or rerun with `--drafts .\output\06b-ai-drafts\drafts.json`.
Stale drafts are rejected if the baseline changed.

`--drafts` and `--enriched` explicitly reuse saved work; they do not generate
new descriptions.
For regression verification, `--enriched` can reuse the saved bundle under
`tests\fixtures\reference\dictionary\ai-enriched`, but it must match the new
baseline. For the complete workflow including new AI descriptions, use the
VS Code chat skill described above.

## Find results and debug

```text
output\
  01-sources\
  02-parsing\
  03-lineage-graphs\
  04-column-lineage\
  05-baseline-dictionary\
  06a-enrichment-context\
  06b-ai-drafts\
  06c-ai-enrichment\
  07-validation\
  08-html\index.html
  08-html-accountid\index.html  Optional column-focused report
  08-html-accountid-opendate\index.html  Optional multi-column report
  logs\                      Latest step records and appended diagnostics
  steps.json                 Current status and output location of each step
```

If a step fails, read its `.json` and `.log` under `output\logs`, correct the
input and rerun that step. Failed partial results are retained as a compact debug
archive when present. A failed rerun restores the previous good files; it does
not turn partial data into a successful result.

The assistant-authored `drafts.json` and its validation record preserve the
wording, provenance, scores and cited evidence. These contain dictionary
metadata, so keep them within approved internal access. An inability to
complete authoring or validation is a blocker, not a reason to silently reuse
old prose or label all fields `needs_evidence`.

Use `--output-dir PATH` to put **all** results in another folder.
There are no automatic historical output copies. Save a copy of `output`
yourself if you need to keep an older complete result.

## Tests and boundaries

```powershell
python -B -m pytest -q
```

Fixtures test the stages without model calls. Lineage integration covers the
original four repositories; optional tenant-landing checks are skipped if that
additional repository is unavailable. Protect-downstream lineage integration
has not yet been implemented.
Tests validate supplied assistant drafts and all deterministic steps without
calling an external model or requiring Copilot CLI.

With Edge installed, an optional real-browser check can also verify the final
graph, dictionary tabs and export when organization policy permits automation:

```powershell
python -m pip install -e ".[browser]"
$env:LINEAGE_BROWSER_TEST = "1"
python -B -m pytest tests\integration\test_combined_browser.py -q
```

If policy blocks DevTools/browser control, do not bypass it. Open the final HTML
normally or use an organization-approved integrated browser for the UI check.

This is static repository evidence, not verified production execution. Unknown
bindings and route gaps stay explicit. Original records, existing descriptions
and lineage assessments must not be rewritten to make validation pass.
