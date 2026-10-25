"""Command-line entry points for individually recorded lineage workflow steps."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from .execution import (
    StepFailure, execute_step, inventory, read_json, validate_identifier, write_json,
)
from .paths import OUTPUT_ROOT, PROJECT_ROOT

STAGES = {
    "sources": "01-sources", "parse": "02-parsing", "graphs": "03-lineage-graphs",
    "columns": "04-column-lineage", "dictionary": "05-baseline-dictionary",
    "prepare": "06a-enrichment-context", "apply": "06c-ai-enrichment",
    "validate": "07-validation", "html": "08-html",
}


def _record(args: argparse.Namespace, stage: str, inputs: list[Path], operation,
            parameters: dict | None = None) -> dict:
    return execute_step(args.runs_root, args.run_id, STAGES.get(stage, stage), inputs=inputs,
                        parameters=parameters or {}, operation=operation)


def _dictionary(args: argparse.Namespace) -> dict:
    from .dictionary.workflow import generate_bundle

    return _record(args, "dictionary", [args.input],
                   lambda output: generate_bundle(args.input, output, args.graph_id),
                   {"graph_id": args.graph_id})


def _enrichment(args: argparse.Namespace) -> dict:
    from .enrichment.workflow import apply_drafts, prepare_context

    if args.action == "prepare":
        return _record(args, "prepare", [args.input],
                       lambda output: prepare_context(args.input, output))
    return _record(args, "apply", [args.input, args.drafts],
                   lambda output: apply_drafts(args.input, args.drafts, output))


def _validate(args: argparse.Namespace) -> dict:
    from .validation.bundle import validate_bundle

    def operation(output: Path) -> dict:
        report = validate_bundle(args.input, args.baseline)
        write_json(output / "validation.json", report)
        return report

    return _record(args, "validate", [args.input] + ([args.baseline] if args.baseline else []),
                   operation, {"preservation_baseline": str(args.baseline) if args.baseline else None})


def _html(args: argparse.Namespace) -> dict:
    from .html_checks import check_html, validate_view_inputs
    from .validation.bundle import validate_bundle
    from .viewers.dictionary.build_viewer import build
    from .viewers.graph.focused import normalize, selection_names

    stage = "html"
    selectors = selection_names(args.selector)
    if selectors:
        keys = sorted(normalize(name) for name in selectors)
        stage = "08-html-" + "-".join(keys)
        if len(stage) > 80:
            suffix = hashlib.sha256("\0".join(keys).encode("utf-8")).hexdigest()[:12]
            stage = "08-html-" + keys[0][:32] + "-" + suffix
        validate_identifier(stage, "focused report name")

    def operation(output: Path) -> dict:
        if not args.graphs or not args.columns:
            raise ValueError("The combined report requires both --graphs and --columns.")
        validation = validate_bundle(args.input, args.baseline)
        consistency = validate_view_inputs(args.input, args.columns, args.graphs)
        write_json(output / "validation.json", validation)
        dictionary = build(args.input, output / "_dictionary.html", verbose=False)
        from .lineage_workflow import render_graphs

        rendered = render_graphs(args.graphs, args.columns, output,
                                dictionary_html=dictionary, selector=selectors or None)
        target = output / "index.html"
        dictionary.unlink(missing_ok=True)
        checks = check_html(target, args.input)
        write_json(output / "html-checks.json", checks)
        return {"html": str(target), "validation": validation,
                "view_consistency": consistency, "graphs": rendered, "html_checks": checks}

    inputs = [args.input] + ([args.baseline] if args.baseline else [])
    inputs += [path for path in (args.graphs, args.columns) if path]
    return _record(args, stage, inputs, operation, {"selectors": selectors})


def _sources(args: argparse.Namespace) -> dict:
    from .sources import configured_root, prepare_sources

    def operation(output: Path) -> dict:
        root = configured_root(args.config, args.source_root)
        return prepare_sources(args.config, root, output, clone=args.clone)

    return _record(args, "sources", [args.config],
                   operation,
                   {"source_root_override": str(args.source_root) if args.source_root else None,
                    "clone_missing": args.clone})


def _parse(args: argparse.Namespace) -> dict:
    from .lineage_workflow import parse_sources
    from .sources import configured_root

    def operation(output: Path) -> dict:
        root = configured_root(args.config, args.source_root)
        before = inventory(root)
        result = parse_sources(root, output, args.parser)
        if inventory(root) != before:
            raise ValueError("Source files changed during parsing; the attempt was not accepted.")
        result["source_inputs"] = {
            "path": before["path"], "sha256": before["sha256"],
            "file_count": len(before.get("files", [])),
        }
        return result

    step = "parse" if args.parser == "all" else "02-parsing-" + args.parser
    return _record(args, step, [args.config], operation,
                   {"parser": args.parser,
                    "source_root_override": str(args.source_root) if args.source_root else None})


def _graphs(args: argparse.Namespace) -> dict:
    from .lineage_workflow import build_graphs

    return _record(args, "graphs", [args.parsed],
                   lambda output: build_graphs(args.parsed, output, args.scope),
                   {"scope": args.scope})


def _columns(args: argparse.Namespace) -> dict:
    if args.input:
        def operation(output: Path) -> dict:
            value = read_json(args.input)
            if not isinstance(value, list) or not value:
                raise ValueError("A column inventory must be a nonempty JSON array.")
            if not all(isinstance(row, dict) and row.get("field_id") for row in value):
                raise ValueError("Every inventory record requires a field_id.")
            if len({row["field_id"] for row in value}) != len(value):
                raise ValueError("Column inventory contains duplicate mapping IDs.")
            target = output / "column_lineage.json"
            shutil.copyfile(args.input, target)
            return {"origin": "explicitly_imported_inventory", "records": len(value),
                    "inventory": str(target), "source_rebuild_performed": False}
        return _record(args, "columns", [args.input], operation, {"mode": "import"})
    if args.graphs is None:
        raise ValueError("Building column lineage requires --graphs as well as --parsed.")
    from .lineage_workflow import build_columns

    return _record(args, "columns", [args.parsed, args.graphs],
                   lambda output: build_columns(args.parsed, args.graphs, output, args.feed),
                   {"feed": args.feed, "mode": "build"})


def _query(args: argparse.Namespace) -> dict:
    from .graph.query import load_graph, node_details, query_columns, search_graph, shortest_path, trace_graph

    if args.column:
        if args.columns is None:
            raise ValueError("--column requires --columns INVENTORY_JSON.")
        return query_columns(args.columns, args.column, args.limit)
    if args.graph is None:
        raise ValueError("A graph query requires --graph GRAPH_JSON.")
    graph = load_graph(args.graph)
    if args.search is not None:
        return search_graph(graph, args.search, args.limit)
    if args.node:
        return node_details(graph, args.node)
    if args.trace:
        return trace_graph(graph, args.trace, args.direction, args.depth)
    return shortest_path(graph, *args.path)


def _pipeline(args: argparse.Namespace) -> dict:
    from .pipeline import run_pipeline

    return run_pipeline(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    recorded = argparse.ArgumentParser(add_help=False)
    recorded.add_argument("--run-id", default="current", help="Optional label recorded in the log")
    recorded.add_argument("--output-dir", "--runs-root", dest="runs_root", type=Path,
                          default=OUTPUT_ROOT, help="One folder containing each step's latest results")
    source_options = argparse.ArgumentParser(add_help=False)
    source_options.add_argument("--config", type=Path, default=PROJECT_ROOT / "sources.json")
    source_options.add_argument("--source-root", type=Path, help="Existing or requested source-checkout parent")

    command = subcommands.add_parser("sources", parents=[recorded, source_options],
                                     help="Verify or clone explicitly configured source repositories")
    command.add_argument("--clone", action="store_true", help="Clone missing checkouts; never pull or reset")
    command.set_defaults(handler=_sources)
    command = subcommands.add_parser("parse", parents=[recorded, source_options],
                                     help="Record parser results and immutable source evidence")
    command.add_argument("--parser", default="all",
                         choices=["all", "basic", "hvr", "airflow", "dbt", "schemachange"])
    command.set_defaults(handler=_parse)
    command = subcommands.add_parser("graphs", parents=[recorded], help="Build graphs from a recorded parse")
    command.add_argument("--parsed", type=Path, required=True)
    command.add_argument("--scope", default="all", choices=["all", "account", "enterprise"])
    command.set_defaults(handler=_graphs)
    command = subcommands.add_parser("columns", parents=[recorded], help="Build or explicitly import column inventories")
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--parsed", type=Path)
    source.add_argument("--input", type=Path, help="Import a supplied inventory without pretending to parse sources")
    command.add_argument("--graphs", type=Path)
    command.add_argument("--feed", default="DWACC", help="DWACC, DWREL, a supported feed, or all")
    command.set_defaults(handler=_columns)
    command = subcommands.add_parser("dictionary", parents=[recorded], help="Generate only the three baseline CSVs")
    command.add_argument("--input", type=Path, required=True)
    command.add_argument("--graph-id")
    command.set_defaults(handler=_dictionary)
    enrichment = subcommands.add_parser("enrichment", help="Prepare AI context or apply saved assistant drafts")
    actions = enrichment.add_subparsers(dest="action", required=True)
    for action in ("prepare", "apply"):
        command = actions.add_parser(action, parents=[recorded])
        command.add_argument("--input", type=Path, required=True)
        if action == "apply":
            command.add_argument("--drafts", type=Path, required=True)
        command.set_defaults(handler=_enrichment)
    command = subcommands.add_parser("validate", parents=[recorded], help="Check bundle contracts and optional baseline preservation")
    command.add_argument("--input", type=Path, required=True)
    command.add_argument("--baseline", type=Path)
    command.set_defaults(handler=_validate)
    command = subcommands.add_parser("html", parents=[recorded], help="Build one HTML showing the lineage graph and dictionary")
    command.add_argument("--input", type=Path, required=True)
    command.add_argument("--baseline", type=Path)
    command.add_argument("--graphs", type=Path, required=True)
    command.add_argument("--columns", type=Path, required=True)
    command.add_argument(
        "--selector",
        nargs="+",
        help="One or more columns for a separate focused report; keep the main report unchanged",
    )
    command.set_defaults(handler=_html)
    command = subcommands.add_parser("query", help="Read-only search, trace, path and column queries")
    command.add_argument("--graph", type=Path)
    command.add_argument("--columns", type=Path)
    actions = command.add_mutually_exclusive_group(required=True)
    actions.add_argument("--search")
    actions.add_argument("--node")
    actions.add_argument("--trace")
    actions.add_argument("--path", nargs=2)
    actions.add_argument("--column")
    command.add_argument("--direction", default="downstream", choices=["downstream", "upstream", "both"])
    command.add_argument("--depth", type=int, default=6)
    command.add_argument("--limit", type=int, default=100)
    command.set_defaults(handler=_query)
    command = subcommands.add_parser("pipeline", parents=[recorded, source_options],
                                     help="Connect the same steps; stop explicitly when AI drafts are needed")
    command.add_argument("--clone", action="store_true")
    command.add_argument("--inventory", type=Path, help="Start from a supplied inventory instead of rebuilding source lineage")
    command.add_argument("--graphs", type=Path, help="Existing graphs when starting from --inventory")
    ai_result = command.add_mutually_exclusive_group()
    ai_result.add_argument("--drafts", type=Path, help="Apply explicit assistant-authored draft JSON")
    ai_result.add_argument("--enriched", type=Path, help="Replay an existing enriched bundle after preservation validation")
    command.set_defaults(handler=_pipeline)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if hasattr(args, "run_id"):
            validate_identifier(args.run_id)
        if hasattr(args, "depth") and args.depth < 1:
            raise ValueError("--depth must be at least 1.")
        if hasattr(args, "limit") and args.limit < 1:
            raise ValueError("--limit must be at least 1.")
        result = args.handler(args)
        if result.get("error"):
            raise ValueError(str(result["error"]))
        console = result
        if result.get("record") and result.get("stage"):
            console = {key: result[key] for key in (
                "status", "run_id", "stage", "attempt", "data_directory", "record", "summary",
            )}
            console["summary"] = dict(console["summary"])
            source_inputs = console["summary"].get("source_inputs")
            if isinstance(source_inputs, dict) and isinstance(source_inputs.get("files"), list):
                console["summary"]["source_inputs"] = {
                    key: value for key, value in source_inputs.items() if key != "files"
                }
                console["summary"]["source_inputs"]["file_count"] = len(source_inputs["files"])
            if "publication" in result:
                console["publication"] = result["publication"]
            for key in ("cleanup_warning", "cleanup_directory"):
                if key in result:
                    console[key] = result[key]
        print(json.dumps(console, indent=2, ensure_ascii=False, allow_nan=False))
        return 3 if result.get("status") == "awaiting_ai_drafts" else 0
    except StepFailure as error:
        print(json.dumps({"status": "failed", "error": str(error), "record": str(error.record)},
                         ensure_ascii=False), file=sys.stderr)
        return 1
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
