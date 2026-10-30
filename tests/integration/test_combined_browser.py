"""Opt-in browser acceptance for the actual final report, using an installed Edge."""

import os

import pytest

from lineage_poc.execution import sha256_file, write_json
from lineage_poc.paths import OUTPUT_ROOT

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("LINEAGE_BROWSER_TEST") != "1",
                       reason="Set LINEAGE_BROWSER_TEST=1 after building the final report."),
]


def test_final_html_displays_graph_and_embedded_dictionary():
    playwright = pytest.importorskip("playwright.sync_api",
                                    reason="Install the optional browser extra to run this check.")
    html = OUTPUT_ROOT / "08-html" / "index.html"
    if not html.is_file():
        pytest.skip("Build the final combined HTML before its browser acceptance check.")
    errors = []
    with playwright.sync_playwright() as driver:
        try:
            browser = driver.chromium.launch(channel="msedge", headless=True, timeout=30000)
        except playwright.Error as error:
            if "DevTools remote debugging is disallowed by the system admin" not in str(error):
                raise
            write_json(OUTPUT_ROOT / "logs" / "browser-checks.json", {
                "status": "blocked", "html": str(html), "html_sha256": sha256_file(html),
                "reason": "Organization policy disallows DevTools remote debugging.",
                "next_action": "Use an approved interactive browser; do not bypass the policy.",
            })
            pytest.skip("Organization policy blocks automated browser control; manual UI check required.")
        try:
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(html.as_uri(), wait_until="load", timeout=60000)
            page.locator("#network canvas").first.wait_for(state="visible", timeout=30000)
            graph = page.evaluate("""() => ({
                nodes: typeof dataNodes !== 'undefined' ? dataNodes.length : null,
                edges: typeof dataEdges !== 'undefined' ? dataEdges.length : null
            })""")
            assert graph["nodes"] and graph["edges"], "The graph must contain actual nodes and edges."
            page.get_by_role("button", name="Data Dictionary", exact=True).click()
            frame = page.frame_locator("#dictionaryAppFrame")
            frame.get_by_role("tab", name="Field Catalog", exact=True).wait_for(timeout=30000)
            frame.get_by_role("tab", name="Field Catalog", exact=True).click()
            frame.locator("#registry-system").select_option("Ultracs")
            frame.locator("#registry-description-origin").select_option("ai_generated")
            result = frame.locator("body").evaluate("""() => {
                const app=window.DDV3, state=app.getState(), bundle=state.bundle;
                if(!bundle) throw new Error('The embedded dictionary did not load');
                const expected=bundle.fields.rows.filter(r=>
                    r.raw.source_system==='Ultracs' && r.raw.description_source_type==='ai_generated').length;
                if(state.filtered.length!==expected) throw new Error('Origin filtering changed');
                const exported=window.V3Core.parseCSV(app.exportRegistryCSV());
                if(exported.rows.length!==expected || exported.headers.length!==bundle.fields.headers.length)
                    throw new Error('The filtered export lost records or columns');
                return {assets:bundle.assets.rows.length, fields:bundle.fields.rows.length,
                    mappings:bundle.dictionary.rows.length, operations:bundle.operationCount,
                    aiDescriptions:expected, exportedRows:exported.rows.length,
                    tabs:Array.from(document.querySelectorAll('[role="tab"]')).map(e=>e.textContent)};
            }""")
            assert result["tabs"] == ["Dictionary", "Asset Registry", "Field Catalog"]
            assert result["fields"] > 0 and result["mappings"] > 0
            assert frame.locator("#error").text_content() == ""
            page.get_by_role("button", name="Detailed", exact=True).click()
            page.locator("#network canvas").first.wait_for(state="visible")
            assert not errors, errors
            write_json(OUTPUT_ROOT / "logs" / "browser-checks.json", {
                "status": "passed", "html": str(html), "html_sha256": sha256_file(html),
                "graph": graph, "dictionary": result, "page_errors": errors,
                "checks": ["visible graph", "dictionary srcdoc", "origin filtering",
                           "complete filtered export", "switch back to graph"],
            })
        finally:
            browser.close()
