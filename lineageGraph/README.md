# Data Lineage POC

Repository-static lineage from Ultracs BASIC programs through HVR and account-product ingestion/dbt metadata. The canonical graph payloads and column inventories are generated from checked-in source files; this POC does not query live systems or execute production jobs.

## Numbered Project Map

1. **Start here:** [CLAUDE.md](CLAUDE.md) for agent workflow and [docs/RUNBOOK.md](docs/RUNBOOK.md) for build, validation, and publishing steps.
2. **Source code:** `src/lineage/` contains graph models and parsers. Root-level `generate_*.py` scripts are the supported command entry points; keep them at the project root because imports and documented commands expect these paths.
3. **Tests:** `tests/` verifies parser and generator behavior. Run `python -m pytest data-lineage-poc/tests -q` from the workspace root.
4. **Canonical generated data:** `output/` contains current graph payloads, per-feed column inventories, focused lineage files, and their viewer assets. Regenerate these with the matching scripts; do not edit them by hand.
5. **Documentation and publishing:** `docs/*.md` is the source documentation. `docs/sharepoint_site/` is a generated, publishable HTML bundle, refreshed with `python data-lineage-poc/generate_report_site.py`.
6. **Skills and examples:** `skills/` contains workflow guidance; `skills/dataDic/` is the separate validated data-dictionary bundle. `examples/` and `templates/` hold examples and viewer templates.
7. **Historical archive:** the workspace-level `old build/` contains numbered snapshots and obsolete mirrors. Nothing under that folder is a generator input; use `output/` for current payloads.

## Quick Start

From the workspace root:

```powershell
python -m pip install -r data-lineage-poc/requirements.txt
python -m pytest data-lineage-poc/tests -q
```

For the full regeneration order, focused column workflow, account-output scope, and static-report publishing, follow the numbered sections in [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Current Account Scope

The DWACC account-master slice is one part of the account domain. Current column inventories cover nine selected parameterized feeds; see `output/account_column_inventory_summary.json` for counts and coverage, and the Runbook for unresolved routes and inferred positional mappings.
