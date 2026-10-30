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
sources.json                 Four GitHub repositories and checkout location
source-repos\                Local Git checkouts (ignored by this repository)
  kb-ultracs-datawarehouse\
  kb-cdp-hvr\
  kb-cdp-tenant-account\
  kb-cdp-tenant-enterprise\
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

### 1. Download or verify the four repositories

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

Individual parsers can also be tested/run with `--parser hvr`, `--parser basic`,
and the other choices shown by `parse --help`.

### 3. Build the lineage graph and column inventory

```powershell
python -B -m lineage_poc graphs --parsed .\output\02-parsing
python -B -m lineage_poc columns --parsed .\output\02-parsing --graphs .\output\03-lineage-graphs
```

Results: `output\03-lineage-graphs` and
`output\04-column-lineage\column_lineage.json`.
The column JSON is the input to the data dictionary, not the final HTML.

### 4. Generate the three baseline CSVs

```powershell
python -B -m lineage_poc dictionary --input .\output\04-column-lineage\column_lineage.json
```

Result: `output\05-baseline-dictionary`, containing:

- `asset_registry.csv`
- `field_catalog.csv`
- `data_dictionary.csv`

This step preserves supplied descriptions. It does not generate AI prose.

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

Fixtures test the stages without model calls. Source integration uses the four
configured checkouts; optional tenant-landing checks are skipped if that
additional repository is unavailable.
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
