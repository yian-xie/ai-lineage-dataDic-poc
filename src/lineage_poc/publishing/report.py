"""Build a linked, static HTML report bundle for local or SharePoint publishing."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT, SKILL_ROOT
from lineage_poc.viewers.graph._templates import read_template

import html
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import markdown

ROOT = REPOSITORY_ROOT
SITE_ROOT = OUTPUT_ROOT / "reports"
SOURCE_ROOTS = (ROOT / "docs", REFERENCE_LINEAGE, SKILL_ROOT, ROOT / "src")
ROOT_DOCS = (ROOT / "README.md", ROOT / "CLAUDE.md")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", ".git"}
ANCHOR_RE = re.compile(r'<a(?P<attrs>[^>]*\bhref="(?P<href>[^"]+)"[^>]*)>(?P<body>.*?)</a>', re.IGNORECASE | re.DOTALL)
EXTENSIONS = ["tables", "fenced_code", "toc", "sane_lists"]


CSS = read_template('report_css.css')


def collect_markdown(
    root: Path = ROOT,
    site_root: Path = SITE_ROOT,
    source_roots: tuple[Path, ...] = SOURCE_ROOTS,
    root_docs: tuple[Path, ...] = ROOT_DOCS,
) -> list[Path]:
    paths = set(root_docs)
    for source_root in source_roots:
        if not source_root.exists():
            continue
        for path in source_root.rglob("*.md"):
            if site_root in path.parents or any(part in SKIP_PARTS for part in path.parts):
                continue
            paths.add(path)
    return sorted((path.resolve() for path in paths if path.is_file()), key=lambda path: path.as_posix().casefold())


def page_title(source: Path, text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if match:
            return match.group(1).strip()
    return source.stem.replace("_", " ").replace("-", " ").title()


def href_for(target: Path, page: Path) -> str:
    return quote(Path(os.path.relpath(target, page.parent)).as_posix(), safe="/._-~")


def rewrite_links(
    body: str,
    source: Path,
    output_page: Path,
    page_map: dict[Path, Path],
    root: Path = ROOT,
    site_root: Path = SITE_ROOT,
) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_href = html.unescape(match.group("href"))
        parsed = urlsplit(raw_href)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        source_target = (source.parent / unquote(parsed.path)).resolve()
        site_target = page_map.get(source_target)
        if site_target is None:
            try:
                relative = source_target.relative_to(root)
                candidate = site_root / relative
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
            source_label = source_target.relative_to(root.parent).as_posix()
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
            relative = source_target.relative_to(root)
        except ValueError:
            return match.group(0)
        site_target = site_root / relative
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


def copy_files(source_root: Path, destination_root: Path, *, skip_markdown: bool = True, site_root: Path = SITE_ROOT) -> None:
    if not source_root.exists():
        return
    for source in source_root.rglob("*"):
        if not source.is_file() or any(part in SKIP_PARTS for part in source.parts):
            continue
        if site_root in source.parents or source.name == ".DS_Store":
            continue
        if skip_markdown and source.suffix.casefold() == ".md":
            continue
        target = destination_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def build_index(
    pages: list[tuple[Path, Path, str]],
    root: Path = ROOT,
    site_root: Path = SITE_ROOT,
    source_labels: dict[Path, Path] | None = None,
) -> str:
    groups: dict[str, list[tuple[Path, Path, str]]] = {}
    for source, target, title in pages:
        rel = source_labels[source] if source_labels is not None else source.relative_to(root)
        category = rel.parts[0] if len(rel.parts) > 1 else "Project guides"
        groups.setdefault(category, []).append((source, target, title))
    labels = {"docs": "Project reports and guides", "output": "Generated output reports", "skills": "Skills and workflows", "src": "Schema references"}
    sections = []
    for category, items in groups.items():
        links = []
        for _, target, title in items:
            links.append('<li><a href="' + html.escape(href_for(target, site_root / "index.html"), quote=True) + '">' + html.escape(title) + '</a></li>')
        sections.append('<section class="panel"><h2>' + html.escape(labels.get(category, category.title())) + '</h2><ul class="report-list">' + ''.join(links) + '</ul></section>')
    graph_links = []
    graph_root = site_root / "output"
    if graph_root.exists():
        for graph in sorted(graph_root.rglob("*.html"), key=lambda path: path.relative_to(site_root).as_posix().casefold()):
            rel = graph.relative_to(site_root).as_posix()
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


def build_site(
    root: Path,
    destination: Path,
    graph_dir: Path | None = None,
    source_roots: tuple[Path, ...] | None = None,
    root_docs: tuple[Path, ...] | None = None,
) -> dict:
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if destination == root or root.is_relative_to(destination):
        raise ValueError("The report destination must not contain the project root.")
    graph_dir = Path(graph_dir).resolve() if graph_dir is not None else root / "examples" / "reference-run" / "lineage"
    source_roots = source_roots if source_roots is not None else (root / "docs", graph_dir, root / ".github" / "skills", root / "src")
    root_docs = root_docs if root_docs is not None else (root / "README.md", root / "CLAUDE.md")
    destination.mkdir(parents=True, exist_ok=True)
    copy_files(root / "docs", destination / "docs", site_root=destination)
    copy_files(graph_dir, destination / "output", site_root=destination)
    copy_files(root / "examples", destination / "examples", site_root=destination)
    copy_files(root / ".github" / "skills", destination / "skills", site_root=destination)
    copy_files(root / "src", destination / "src", site_root=destination)
    # Keep report-relative links to generated graph artifacts working from docs pages.
    copy_files(graph_dir, destination / "docs" / "output", site_root=destination)
    page_sources = collect_markdown(root=root, site_root=destination, source_roots=source_roots, root_docs=root_docs)
    source_labels = {
        source: Path("output") / source.relative_to(graph_dir) if source.is_relative_to(graph_dir) else source.relative_to(root)
        for source in page_sources
    }
    page_map = {source: destination / "reports" / source_labels[source].with_suffix(".html") for source in page_sources}
    page_map.update({
        source.resolve(): destination / "output" / source.relative_to(graph_dir)
        for source in graph_dir.rglob("*") if source.is_file() and source.suffix.casefold() != ".md"
    })
    page_records = []
    for source in page_sources:
        source_rel = source_labels[source].as_posix()
        target = page_map[source]
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8", errors="replace")
        title = page_title(source, text)
        renderer = markdown.Markdown(extensions=EXTENSIONS, output_format="html5")
        body = rewrite_links(renderer.convert(text), source, target, page_map, root=root, site_root=destination)
        home_href = href_for(destination / "index.html", target)
        target.write_text(page_wrapper(title, source_rel, body, home_href), encoding="utf-8")
        page_records.append((source, target, title))
    (destination / "index.html").write_text(build_index(page_records, root=root, site_root=destination, source_labels=source_labels), encoding="utf-8")
    rewrite_graph_report_links(destination)
    return {"destination": str(destination), "index": str(destination / "index.html"), "pages": len(page_records)}


def main() -> dict:
    return build_site(ROOT, SITE_ROOT)


if __name__ == "__main__":
    main()
