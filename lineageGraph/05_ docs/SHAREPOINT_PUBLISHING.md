# SharePoint Publishing Guide

## Generate the Bundle

Run from the workspace root after refreshing the reports/graphs you want to publish:

```powershell
python -m pip install -r data-lineage-poc/requirements.txt
python data-lineage-poc/generate_report_site.py
```

The static bundle is generated at `data-lineage-poc/docs/sharepoint_site/`:

- `index.html` is the report landing page.
- `reports/` contains HTML renderings of Markdown reports, guides, skills, and schema references, preserving their source-relative hierarchy.
- `output/` contains copied graph/viewer artifacts and data snapshots.
- `docs/output/` inside the generated site is populated from canonical `data-lineage-poc/output/` assets to keep report-relative links working; do not maintain a separate source mirror under `data-lineage-poc/docs/output/`.
- `examples/`, `skills/`, and `src/` are mirrored for local references.

The generator rewrites links between Markdown reports to their rendered HTML pages and graph explanation links to the corresponding rendered reports where available. Links to sibling source repositories outside this bundle are displayed as repository paths rather than broken SharePoint URLs. It does not modify source Markdown or canonical graph JSON.

Keep `output/column_lineage.html` beside `output/column_lineage_dictionary.html`; the graph’s Data Dictionary mode loads the second page. Focused lineage HTML pages also expect their explanation file alongside them where applicable.

## Upload

Upload the **entire `sharepoint_site` directory contents** to a SharePoint document library or approved static site location while preserving all subfolders. Open `index.html` as the landing page; users can then navigate the linked reports and graph viewers. Do not upload only the index page or only the top-level graph HTML.

After upload, verify:

1. `index.html` opens and all report links resolve.
2. `output/column_lineage.html` opens and its Data Dictionary iframe loads `output/column_lineage_dictionary.html`.
3. Focused graph pages open their explanation pages.
4. Browser access to `https://unpkg.com/vis-network/standalone/umd/vis-network.min.js` is permitted for the interactive graph. If external CDN access is blocked, use an organization-approved way to host that dependency locally before publishing.
5. The site’s viewers can see the documents under the intended permissions.

## SharePoint Limitations and Access

Whether SharePoint will execute standalone `.html` files from a document library depends on tenant security policy and site configuration. Some environments block, sanitize, or download HTML/JavaScript instead of rendering it. Test the bundle in the target tenant before presenting it as a hosted site.

If the document library does not serve the pages as interactive HTML, practical alternatives are:

- Publish the report content as modern SharePoint pages and link the graph artifacts where permitted.
- Host the static bundle on an organization-approved static web host (for example, an approved Azure Static Web Apps or Storage static website) and link to it from SharePoint.

“Anyone can view” is controlled by SharePoint/hosting permissions and organization policy. The bundle itself does not grant access or create anonymous sharing; ask the site owner/admin to configure the intended audience. Keep repository source paths and lineage artifacts within approved internal access boundaries.

The bundle is a static snapshot. It does not watch source repositories, query live Snowflake/HVR/Airflow/dbt, or update itself after upload. Regenerate and republish after the source reports or graph snapshots change.
