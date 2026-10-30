from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT
from pathlib import Path

PROJECT_ROOT = REPOSITORY_ROOT

import lineage_poc.publishing.report as report_site
from lineage_poc.publishing.report import rewrite_graph_report_links


def test_graph_markdown_links_rewrite_to_rendered_report_pages(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    graph_page = output / "account_lineage.html"
    graph_page.write_text(
        '<a href="account_lineage_explanation.md#evidence">Evidence</a>',
        encoding="utf-8",
    )
    (output / "account_lineage_explanation.html").write_text("<h1>Evidence</h1>", encoding="utf-8")
    (output / "account_lineage_explanation.md").write_text("# Evidence", encoding="utf-8")

    rewrite_graph_report_links(tmp_path)

    assert graph_page.read_text(encoding="utf-8") == '<a href="account_lineage_explanation.html#evidence">Evidence</a>'


def test_external_links_are_not_rewritten(tmp_path):
    page = tmp_path / "report.html"
    page.write_text('<a href="https://example.com/report.md">External</a>', encoding="utf-8")

    rewrite_graph_report_links(tmp_path)

    assert page.read_text(encoding="utf-8") == '<a href="https://example.com/report.md">External</a>'


def test_missing_local_repository_link_becomes_a_visible_path(tmp_path):
    page = tmp_path / "report.html"
    page.write_text('<a href="../source/job.py">Job</a>', encoding="utf-8")

    rewrite_graph_report_links(tmp_path)

    content = page.read_text(encoding="utf-8")
    assert '<a href="../source/job.py">' not in content
    assert "../source/job.py" in content
    assert ">Job</span>" in content


def test_site_build_keeps_graph_html_separate_from_same_named_markdown(tmp_path):
    root = tmp_path / "poc"
    docs = root / "docs"
    output = root / "output"
    docs.mkdir(parents=True)
    output.mkdir()
    (docs / "PROJECT_FINDINGS.md").write_text(
        "# Findings\n\n[Graph](../output/table_lineage.html)\n\n![Diagram](assets/diagram.svg)\n", encoding="utf-8"
    )
    assets = docs / "assets"
    assets.mkdir()
    (assets / "diagram.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
    (docs / "SHAREPOINT_PUBLISHING.md").write_text("# SharePoint guide\n", encoding="utf-8")
    (output / "table_lineage.md").write_text("# Table report\n", encoding="utf-8")
    (output / "table_lineage.html").write_text(
        '<!doctype html><title>Graph viewer</title><a href="table_lineage_explanation.md">Evidence</a>',
        encoding="utf-8",
    )
    (output / "table_lineage_explanation.md").write_text("# Evidence\n", encoding="utf-8")
    (output / "column_lineage.html").write_text('<iframe src="column_lineage_dictionary.html"></iframe>', encoding="utf-8")
    (output / "column_lineage_dictionary.html").write_text("<!doctype html><title>Dictionary</title>", encoding="utf-8")

    site = root / "docs" / "sharepoint_site"
    report_site.build_site(
        root,
        site,
        graph_dir=output,
        source_roots=(docs, output, root / "skills", root / "src"),
        root_docs=(),
    )

    graph_page = site / "output" / "table_lineage.html"
    report_page = site / "reports" / "output" / "table_lineage.html"
    assert "Graph viewer" in graph_page.read_text(encoding="utf-8")
    assert "Table report" in report_page.read_text(encoding="utf-8")
    findings_page = site / "reports" / "docs" / "PROJECT_FINDINGS.html"
    assert 'src="../../docs/assets/diagram.svg"' in findings_page.read_text(encoding="utf-8")
    assert '../reports/output/table_lineage_explanation.html' in graph_page.read_text(encoding="utf-8")
    assert (site / "output" / "column_lineage_dictionary.html").exists()
    assert 'reports/docs/SHAREPOINT_PUBLISHING.html' in (site / "index.html").read_text(encoding="utf-8")
