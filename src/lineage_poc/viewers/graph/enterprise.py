"""Create a separate interactive viewer for account_enterprise_lineage.json."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT

import json
from pathlib import Path
from lineage_poc.viewers.graph.descriptions import describe_graph


ROOT = REPOSITORY_ROOT
INPUT = REFERENCE_LINEAGE / "account_enterprise_lineage.json"
OUTPUT = OUTPUT_ROOT / "lineage" / "account_enterprise_lineage.html"

from lineage_poc.viewers.graph.account import HTML


def render_html(graph: dict) -> str:
    graph = describe_graph(graph)
    embedded = json.dumps(graph, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    html = HTML.replace("ACCOUNT lineage", "ACCOUNT lineage · Enterprise extension")
    html = html.replace("__GRAPH_DATA__", embedded)
    return html


def main(input_path: Path = INPUT, destination: Path = OUTPUT) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_html(json.loads(Path(input_path).read_text(encoding="utf-8"))), encoding="utf-8")


if __name__ == "__main__":
    main()