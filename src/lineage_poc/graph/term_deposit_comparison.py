"""Snapshot the two recorded DWTDS lineage options for comparison."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from lineage_poc.execution import accepted_data, execute_step, inventory, write_json
from lineage_poc.paths import OUTPUT_ROOT


def _verify_stage(output: Path, stage: str) -> dict[str, Any]:
    record = accepted_data(output / stage, stage)
    changed = [
        item["path"] for item in record.get("inputs", [])
        if inventory(Path(item["path"])) != item
    ]
    if changed:
        raise ValueError(f"Recorded inputs changed for {stage}: {', '.join(changed)}")
    return record


def _comparison_html(comparison: dict[str, Any]) -> str:
    options = comparison["options"]
    cards = []
    for option in options:
        cards.append(
            "<article class=\"option\"><p class=\"eyebrow\">" + html.escape(option["option_id"]) + "</p>"
            "<h2>" + html.escape(option["title"]) + "</h2><p>" + html.escape(option["scope"]) + "</p>"
            "<dl><dt>Nodes</dt><dd>" + str(option["nodes"]) + "</dd>"
            "<dt>Parser edges</dt><dd>" + str(option["edges"]) + "</dd>"
            "<dt>Mapped columns</dt><dd>" + str(option["mapped_columns"]) + "</dd>"
            "<dt>Unmapped columns</dt><dd>" + str(option["unmapped_columns"]) + "</dd>"
            "<dt>Candidate joins</dt><dd>" + str(option["candidate_links"]) + "</dd></dl>"
            "<p class=\"caveat\">" + html.escape(option["boundary"]) + "</p>"
            "<p class=\"actions\"><a href=\"" + html.escape(option["report_link"], quote=True) + "\">Open rich report</a>"
            "<a href=\"" + html.escape(option["snapshot_file"], quote=True) + "\">Graph snapshot JSON</a></p></article>"
        )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DWTDS lineage options</title><style>
:root{color-scheme:light;--ink:#193238;--muted:#607477;--line:#d3dfdc;--paper:#edf3f1;--panel:#fff;--green:#28734e;--gold:#a96b25}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 "Segoe UI",Tahoma,sans-serif}
header{padding:22px max(18px,calc((100vw - 1180px)/2));background:#fff;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:23px}header p{margin:6px 0 0;color:var(--muted)}main{max-width:1180px;margin:0 auto;padding:22px 18px}
.options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.option{padding:18px;background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--green)}
.option:nth-child(2){border-top-color:var(--gold)}.eyebrow{margin:0;color:var(--muted);font-size:11px;text-transform:uppercase;font-weight:700}.option h2{margin:6px 0;font-size:18px}
dl{display:grid;grid-template-columns:1fr auto;gap:6px 14px;padding:12px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}dt{color:var(--muted)}dd{margin:0;font-weight:700}
.caveat{min-height:56px;color:#51676a}.actions{display:flex;gap:9px;flex-wrap:wrap}.actions a{display:inline-block;padding:8px 10px;border:1px solid var(--line);border-radius:4px;color:#155d4b;text-decoration:none;font-weight:650}.actions a:hover{background:#edf5f2}
.note{margin-top:16px;padding:12px 14px;background:#fff;border-left:3px solid var(--gold);color:var(--muted)}
@media(max-width:720px){.options{grid-template-columns:1fr}header{padding:16px 18px}.caveat{min-height:0}}
</style></head><body><header><h1>DWTDS lineage options</h1><p>Separate parser-backed snapshots; neither option modifies the canonical graph.</p></header>
<main><section class="options">""" + "".join(cards) + """</section>
<p class="note">The Landing option keeps the HVR-to-Landing physical relation match as a candidate because HVR database/schema identity is absent. Position 42 (col40) remains unmapped.</p>
</main></body></html>"""


def record_term_deposit_options_snapshot() -> dict[str, Any]:
    output = Path(OUTPUT_ROOT)
    stages = (
        "04-column-lineage-term-deposits",
        "04b-term-deposit-dictionary-input",
        "12-term-deposit-rich-html",
        "13-term-deposit-landing-lineage",
    )
    for stage in stages:
        _verify_stage(output, stage)

    columns_root = output / stages[0]
    adapter_root = output / stages[1]
    account_report = output / stages[2]
    landing_report = output / stages[3]
    inputs = [output / stage for stage in stages]

    def operation(destination: Path) -> dict[str, Any]:
        table_graph = json.loads((adapter_root / "term_deposit_graph.json").read_text(encoding="utf-8"))
        mapped_fields = json.loads((adapter_root / "column_lineage.json").read_text(encoding="utf-8"))
        all_fields = json.loads((columns_root / "dwtds_column_lineage.json").read_text(encoding="utf-8"))
        landing_graph = json.loads((landing_report / "term_deposit_landing_lineage.json").read_text(encoding="utf-8"))

        option_a = {
            "schema_version": "term-deposit-option-snapshot-v1",
            "option_id": "account_context",
            "title": "Account-context graph",
            "scope": "Ultracs DWTDS through HVR and Account RAW/internal dbt context",
            "graph": table_graph,
            "field_mappings": mapped_fields,
            "all_ultracs_positions": all_fields,
            "summary": {
                "nodes": len(table_graph["nodes"]),
                "edges": len(table_graph["edges"]),
                "mapped_columns": len(mapped_fields),
                "unmapped_columns": len(all_fields) - len(mapped_fields),
                "candidate_links": 0,
            },
            "boundary": "Account graph provides RAW/internal context; it does not establish a Landing handoff for DWTDS.",
            "source_report": "../12-term-deposit-rich-html/index.html",
        }
        option_b = {
            "schema_version": "term-deposit-option-snapshot-v1",
            "option_id": "tenant_landing",
            "title": "Tenant Landing graph",
            "scope": landing_graph["scope"],
            "graph": landing_graph,
            "summary": landing_graph["summary"],
            "boundary": landing_graph["candidate_links"][0]["reason"],
            "source_report": "../13-term-deposit-landing-lineage/index.html",
        }
        write_json(destination / "option_a_account_context.json", option_a)
        write_json(destination / "option_b_tenant_landing.json", option_b)

        comparison = {
            "schema_version": "term-deposit-lineage-options-v1",
            "options": [
                {
                    "option_id": option_a["option_id"],
                    "title": option_a["title"],
                    "scope": option_a["scope"],
                    **option_a["summary"],
                    "boundary": option_a["boundary"],
                    "snapshot_file": "option_a_account_context.json",
                    "report_link": option_a["source_report"],
                },
                {
                    "option_id": option_b["option_id"],
                    "title": option_b["title"],
                    "scope": option_b["scope"],
                    "nodes": option_b["summary"]["nodes"],
                    "edges": option_b["summary"]["edges"],
                    "mapped_columns": option_b["summary"]["landing_columns_mapped"],
                    "unmapped_columns": option_b["summary"]["landing_columns_unmapped"],
                    "candidate_links": option_b["summary"]["candidate_links"],
                    "boundary": option_b["boundary"],
                    "snapshot_file": "option_b_tenant_landing.json",
                    "report_link": option_b["source_report"],
                },
            ],
            "inputs": [
                {"stage": stage, "attempt": accepted_data(output / stage, stage)["attempt"]}
                for stage in stages
            ],
        }
        write_json(destination / "comparison.json", comparison)
        (destination / "index.html").write_text(_comparison_html(comparison), encoding="utf-8", newline="\n")
        return {"options": len(comparison["options"]), "html": str(destination / "index.html"), "snapshots": ["option_a_account_context.json", "option_b_tenant_landing.json"]}

    return execute_step(
        output,
        "term-deposits",
        "14-term-deposit-options-snapshot",
        inputs=inputs,
        parameters={"options": ["account_context", "tenant_landing"]},
        operation=operation,
    )


if __name__ == "__main__":
    result = record_term_deposit_options_snapshot()
    print(json.dumps({"status": result["status"], "stage": result["stage"], "attempt": result["attempt"], "summary": result["summary"]}))