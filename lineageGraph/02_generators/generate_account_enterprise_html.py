#!/usr/bin/env python3
"""Create a separate interactive viewer for account_enterprise_lineage.json."""

import json
import sys
from pathlib import Path
from html_graph_descriptions import describe_graph


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "output/account_enterprise_lineage.json"
OUTPUT = ROOT / "output/account_enterprise_lineage.html"
sys.path.insert(0, str(ROOT))

from generate_account_lineage_html import HTML


def main() -> None:
    graph = describe_graph(json.loads(INPUT.read_text(encoding="utf-8")))
    embedded = json.dumps(graph, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    html = HTML.replace("ACCOUNT lineage", "ACCOUNT lineage · Enterprise extension")
    html = html.replace("__GRAPH_DATA__", embedded)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)} ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")


if __name__ == "__main__":
    main()