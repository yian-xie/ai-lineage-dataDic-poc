#!/usr/bin/env python3
"""Build a linked, static HTML report bundle for local or SharePoint publishing."""

import html
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import markdown

ROOT = Path(__file__).resolve().parent
SITE_ROOT = ROOT / "docs" / "sharepoint_site"
SOURCE_ROOTS = (ROOT / "docs", ROOT / "output", ROOT / "skills", ROOT / "src")
ROOT_DOCS = (ROOT / "README.md", ROOT / "CLAUDE.md")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", ".git"}
ANCHOR_RE = re.compile(r'<a(?P<attrs>[^>]*\bhref="(?P<href>[^"]+)"[^>]*)>(?P<body>.*?)</a>', re.IGNORECASE | re.DOTALL)
EXTENSIONS = ["tables", "fenced_code", "toc", "sane_lists"]


CSS = r"""
:root{color-scheme:light;--ink:#193238;--green:#24794f;--deep:#183e33;--bg:#eef4f1;--panel:#fff;--line:#d6e1de;--muted:#62777b;--teal:#218b83;--blue:#397b9d;--purple:#7963a1;--amber:#c4893d;--coral:#d87968}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Segoe UI",sans-serif}.top{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:16px 24px;background:var(--deep);color:#fff}.top a{color:#fff;text-decoration:none;font-weight:750}.top small{color:#d9e9df}.shell{max-width:1240px;margin:0 auto;padding:24px}.panel{background:#fff;border:1px solid var(--line);border-radius:8px;padding:20px;margin:0 0 18px}.intro{border-left:5px solid var(--green)}h1,h2,h3{line-height:1.25}h1{font-size:26px;margin:0 0 8px}h2{margin-top:28px;border-bottom:1px solid var(--line);padding-bottom:7px}h3{margin-top:22px}a{color:#176b58}a:hover{color:#0d4f40}table{display:block;width:100%;overflow:auto;border-collapse:collapse}th,td{padding:8px 10px;border:1px solid var(--line);text-align:left;vertical-align:top}th{background:#e7f0e9}code{background:#edf3ef;padding:1px 4px;border-radius:3px}pre{overflow:auto;padding:14px;background:#183e33;color:#eef7f0;border-radius:6px}pre code{background:transparent;color:inherit;padding:0}blockquote{margin:12px 0;padding:10px 15px;border-left:4px solid var(--teal);background:#f4f8f6}img,svg{max-width:100%;height:auto}.meta{font-size:12px;color:var(--muted)}.repo-ref{border-bottom:1px dotted var(--amber);cursor:help}.repo-ref-path{color:var(--muted);font-size:11px;overflow-wrap:anywhere}.toc{padding:12px 16px;background:#f6f9f7;border:1px solid var(--line);border-radius:6px}.report-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;padding:0;list-style:none}.report-list a{display:block;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:#fff;text-decoration:none}.report-list a:hover{background:#eaf3eb}.footer{padding:20px 0;color:var(--muted);font-size:12px}@media(max-width:680px){.top{padding:14px}.shell{padding:14px}.panel{padding:14px}h1{font-size:22px}}
"""


def collect_markdown() -> list[Path]:
    paths = set(ROOT_DOCS)
    for source_root in SOURCE_ROOTS:
        if not source_root.exists():
            continue
        for path in source_root.rglob("*.md"):
            if SITE_ROOT in path.parents or any(part in SKIP_PARTS for part in path.parts):
                continue
            paths.add(path)
    return sorted((path.resolve() for path in paths if path.is_file()), key=lambda path: path.relative_to(ROOT).as_posix().casefold())


def page_title(source: Path, text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if match:
            return match.group(1).strip()
    return source.stem.replace("_", " ").replace("-", " ").title()


def href_for(target: Path, page: Path) -> str:
    return quote(Path(os.path.relpath(target, page.parent)).as_posix(), safe="/._-~")


def rewrite_links(body: str, source: Path, output_page: Path, page_map: dict[Path, Path]) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_href = html.unescape(match.group("href"))
        parsed = urlsplit(raw_href)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        source_target = (source.parent / unquote(parsed.path)).resolve()
        site_target = page_map.get(source_target)
        if site_target is None:
            try:
                relative = source_target.relative_to(ROOT)
                candidate = SITE_ROOT / relative
                if candidate.exists():
                    site_target = candidate
            except ValueError:
                relative = None
        if site_target is not None:
            rewritten_path = href_for(site_target, output_page)
            rewritten = urlunsplit(("", "", rewritten_path, parsed.query, parsed.fragment))
            attrs = re.sub(r'\bhref="[^"]+"', 'href="' + html.escape(rewritten, quote=True) + '"', match.group("attrs"), count=1)
            return '<a' + attrs + '>' + match.group("body") + '</a>'
        try:
            source_label = source_target.relative_to(ROOT.parent).as_posix()
        except ValueError:
            source_label = parsed.path
        title = html.escape("Source repository reference: " + source_label, quote=True)
        return '<span class="repo-ref" title="' + title + '">' + match.group("body") + '</span><small class="repo-ref-path">(' + html.escape(source_label) + ')</small>'

    body = ANCHOR_RE.sub(replace, body)

    def replace_asset(match: re.Match[str]) -> str:
        parsed = urlsplit(html.unescape(match.group("src")))
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        source_target = (source.parent / unquote(parsed.path)).resolve()
        try:
            relative = source_target.relative_to(ROOT)
        except ValueError:
            return match.group(0)
        site_target = SITE_ROOT / relative
        if not site_target.is_file():
            return match.group(0)
        rewritten_path = href_for(site_target, output_page)
        rewritten = urlunsplit(("", "", rewritten_path, parsed.query, parsed.fragment))
        return match.group("prefix") + html.escape(rewritten, quote=True) + match.group("suffix")

    return re.sub(r'(?P<prefix>\bsrc=")(?P<src>[^"]+)(?P<suffix>")', replace_asset, body, flags=re.IGNORECASE)


def page_wrapper(title: str, source_rel: str, body: str, home_href: str) -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>{html.escape(title)} · Lineage POC</title><style>{CSS}</style></head>
<body><header class="top"><a href="{html.escape(home_href, quote=True)}">Data Lineage POC Reports</a><small>Static report bundle · no live systems queried</small></header><main class="shell"><article class="panel"><p class="meta">Source: <code>{html.escape(source_rel)}</code></p><h1>{html.escape(title)}</h1>{body}</article><footer class="footer">Generated from repository Markdown. Graph pages are separate static artifacts. Repository-source references outside this bundle are shown as paths.</footer></main></body></html>'''


def copy_files(source_root: Path, destination_root: Path, *, skip_markdown: bool = True) -> None:
    if not source_root.exists():
        return
    for source in source_root.rglob("*"):
        if not source.is_file() or any(part in SKIP_PARTS for part in source.parts):
            continue
        if SITE_ROOT in source.parents or source.name == ".DS_Store":
            continue
        if skip_markdown and source.suffix.casefold() == ".md":
            continue
        target = destination_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def build_index(pages: list[tuple[Path, Path, str]]) -> str:
    groups: dict[str, list[tuple[Path, Path, str]]] = {}
    for source, target, title in pages:
        rel = source.relative_to(ROOT)
        category = rel.parts[0] if len(rel.parts) > 1 else "Project guides"
        groups.setdefault(category, []).append((source, target, title))
    labels = {"docs": "Project reports and guides", "output": "Generated output reports", "skills": "Skills and workflows", "src": "Schema references"}
    sections = []
    for category, items in groups.items():
        links = []
        for _, target, title in items:
            links.append('<li><a href="' + html.escape(href_for(target, SITE_ROOT / "index.html"), quote=True) + '">' + html.escape(title) + '</a></li>')
        sections.append('<section class="panel"><h2>' + html.escape(labels.get(category, category.title())) + '</h2><ul class="report-list">' + ''.join(links) + '</ul></section>')
    graph_links = []
    graph_root = SITE_ROOT / "output"
    if graph_root.exists():
        for graph in sorted(graph_root.rglob("*.html"), key=lambda path: path.relative_to(SITE_ROOT).as_posix().casefold()):
            rel = graph.relative_to(SITE_ROOT).as_posix()
            graph_links.append('<li><a href="' + html.escape(quote(rel, safe="/._-"), quote=True) + '">' + html.escape(graph.stem.replace("_", " ").title()) + '</a></li>')
    sections.append('<section class="panel"><h2>Interactive graph viewers</h2><ul class="report-list">' + ''.join(graph_links) + '</ul><p class="meta">Keep <code>column_lineage.html</code> beside <code>column_lineage_dictionary.html</code>.</p></section>')
    sections.append('<section class="panel"><h2>Publishing</h2><p><a href="reports/docs/SHAREPOINT_PUBLISHING.html">SharePoint publishing guide</a></p></section>')
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>Data Lineage POC Reports</title><style>' + CSS + '</style></head><body><header class="top"><strong>Data Lineage POC Reports</strong><small>SharePoint-ready static report bundle</small></header><main class="shell"><section class="panel intro"><h1>Data Lineage POC</h1><p>Browse generated findings, evidence reports, workflows, skills, schema references, and interactive graph viewers. All reports are static snapshots; repository-source links outside this bundle are shown as paths.</p></section>' + ''.join(sections) + '<footer class="footer">Upload this entire <code>sharepoint_site</code> folder while preserving its directory structure. See <code>SHAREPOINT_PUBLISHING.md</code> before publishing interactive HTML.</footer></main></body></html>'


def rewrite_graph_report_links(site_root: Path) -> None:
    """Resolve bundled Markdown links and make outside-repository references readable."""
    for page in site_root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="replace")

        def replace(match: re.Match[str]) -> str:
            parsed = urlsplit(html.unescape(match.group("href")))
            if parsed.scheme or parsed.netloc or not parsed.path:
                return match.group(0)
            local_path = unquote(parsed.path)
            rendered = None
            if local_path.casefold().endswith(".md"):
                rendered = (page.parent / local_path).with_suffix(".html")
                if not rendered.is_file():
                    rendered_name = Path(local_path).with_suffix(".html").name
                    rendered = next((candidate for candidate in site_root.rglob(rendered_name) if candidate.is_file()), rendered)
            if rendered is not None and rendered.is_file():
                href = quote(Path(os.path.relpath(rendered, page.parent)).as_posix(), safe="/._-~")
                href = urlunsplit(("", "", href, parsed.query, parsed.fragment))
                attrs = re.sub(r'\bhref="[^"]+"', 'href="' + html.escape(href, quote=True) + '"', match.group("attrs"), count=1)
                return '<a' + attrs + '>' + match.group("body") + '</a>'
            if (page.parent / local_path).exists():
                return match.group(0)
            source_path = local_path
            title = html.escape("Repository source reference: " + source_path, quote=True)
            return '<span title="' + title + '">' + match.group("body") + '</span><small class="repo-ref-path">(' + html.escape(source_path) + ')</small>'

        updated = ANCHOR_RE.sub(replace, text)
        if updated != text:
            page.write_text(updated, encoding="utf-8")


def main() -> None:
    SITE_ROOT.mkdir(parents=True, exist_ok=True)
    copy_files(ROOT / "docs", SITE_ROOT / "docs")
    copy_files(ROOT / "output", SITE_ROOT / "output")
    copy_files(ROOT / "examples", SITE_ROOT / "examples")
    copy_files(ROOT / "skills", SITE_ROOT / "skills")
    copy_files(ROOT / "src", SITE_ROOT / "src")
    # Keep report-relative links to generated graph artifacts working from docs pages.
    copy_files(ROOT / "output", SITE_ROOT / "docs" / "output")
    page_sources = collect_markdown()
    page_map = {source: SITE_ROOT / "reports" / source.relative_to(ROOT).with_suffix(".html") for source in page_sources}
    page_records = []
    for source in page_sources:
        source_rel = source.relative_to(ROOT).as_posix()
        target = page_map[source]
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8", errors="replace")
        title = page_title(source, text)
        renderer = markdown.Markdown(extensions=EXTENSIONS, output_format="html5")
        body = rewrite_links(renderer.convert(text), source, target, page_map)
        home_href = href_for(SITE_ROOT / "index.html", target)
        target.write_text(page_wrapper(title, source_rel, body, home_href), encoding="utf-8")
        page_records.append((source, target, title))
    (SITE_ROOT / "index.html").write_text(build_index(page_records), encoding="utf-8")
    rewrite_graph_report_links(SITE_ROOT)
    print(f"Generated {len(page_records)} report/reference pages under {SITE_ROOT.relative_to(ROOT)}")
    print(f"Generated {SITE_ROOT.relative_to(ROOT)}/index.html")


if __name__ == "__main__":
    main()
