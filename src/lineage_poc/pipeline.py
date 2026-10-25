"""An optional coordinator over the same independently callable CLI step handlers."""

import argparse
import shutil
from pathlib import Path

from .execution import StepFailure, validate_identifier, write_json


def run_pipeline(args: argparse.Namespace) -> dict:
    validate_identifier(args.run_id)
    path = args.runs_root / "pipeline.json"
    write_json(path, {"status": "running", "run_id": args.run_id})
    try:
        return _run_pipeline(args)
    except (StepFailure, ValueError, OSError, TypeError, KeyError) as error:
        failure = {"status": "failed", "run_id": args.run_id,
                   "error": {"type": type(error).__name__, "message": str(error)}}
        if isinstance(error, StepFailure):
            failure["failed_step_record"] = str(error.record)
        write_json(path, failure)
        raise


def _run_pipeline(args: argparse.Namespace) -> dict:
    from . import cli

    common = {"run_id": args.run_id, "runs_root": args.runs_root}
    steps = []

    def run(handler, **options) -> Path:
        record = handler(argparse.Namespace(**common, **options))
        steps.append({"stage": record["stage"], "record": record["record"],
                      "data_directory": record["data_directory"]})
        return Path(record["data_directory"])

    graphs = args.graphs
    if args.inventory:
        columns = run(cli._columns, input=args.inventory, parsed=None, graphs=None, feed="DWACC")
    else:
        run(cli._sources, config=args.config, source_root=args.source_root, clone=args.clone)
        parsed = run(cli._parse, config=args.config, source_root=args.source_root, parser="all")
        graphs = run(cli._graphs, parsed=parsed, scope="all")
        columns = run(cli._columns, input=None, parsed=parsed, graphs=graphs, feed="DWACC")
    baseline = run(cli._dictionary, input=columns / "column_lineage.json", graph_id=None)
    context = run(cli._enrichment, action="prepare", input=baseline)
    if args.drafts:
        enriched = run(cli._enrichment, action="apply", input=baseline, drafts=args.drafts)
    elif args.enriched:
        from .validation.bundle import validate_bundle

        def import_enriched(output: Path) -> dict:
            validation = validate_bundle(args.enriched, baseline)
            for name in ("asset_registry.csv", "field_catalog.csv", "data_dictionary.csv"):
                shutil.copyfile(args.enriched / name, output / name)
            return {"origin": "explicitly_reused_enriched_bundle", "validation": validation,
                    "new_AI_generation_performed": False}
        record = cli._record(args, "apply", [baseline, args.enriched], import_enriched,
                             {"mode": "reuse_validated_enriched_bundle"})
        steps.append({"stage": record["stage"], "record": record["record"],
                      "data_directory": record["data_directory"]})
        enriched = Path(record["data_directory"])
    else:
        report = {
            "status": "awaiting_ai_drafts", "run_id": args.run_id, "steps": steps,
            "baseline": str(baseline), "context": str(context),
            "next_action": "Follow .github\\skills\\ai-description-enrichment\\SKILL.md to author "
                           "drafts from this exact context, then run enrichment apply, validate and html.",
            "note": "No model API was called, no generated prose was substituted, and nothing was published.",
        }
        write_json(args.runs_root / "pipeline.json", report)
        return report
    run(cli._validate, input=enriched, baseline=baseline)
    html = run(cli._html, input=enriched, baseline=baseline, graphs=graphs,
               columns=columns if graphs else None, selector=None)
    report = {"status": "passed", "run_id": args.run_id, "steps": steps,
              "html": str(html / "index.html")}
    write_json(args.runs_root / "pipeline.json", report)
    return report
