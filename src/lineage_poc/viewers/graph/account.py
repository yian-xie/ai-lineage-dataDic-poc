"""Create a self-contained interactive viewer for account_table_lineage.json."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT
from lineage_poc.viewers.graph._templates import read_template

import json
from pathlib import Path

from lineage_poc.viewers.graph.descriptions import describe_graph


ROOT = REPOSITORY_ROOT
INPUT = REFERENCE_LINEAGE / "account_table_lineage.json"
OUTPUT = OUTPUT_ROOT / "lineage" / "account_table_lineage.html"

HTML = read_template('account_html.html')


def render_html(graph: dict) -> str:
    graph = describe_graph(graph)
    embedded = json.dumps(graph, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    return HTML.replace("__GRAPH_DATA__", embedded)


def main(input_path: Path = INPUT, destination: Path = OUTPUT) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_html(json.loads(Path(input_path).read_text(encoding="utf-8"))), encoding="utf-8")


if __name__ == "__main__":
    main()