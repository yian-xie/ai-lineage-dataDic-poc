"""Render the DWTDS field graph as a self-contained offline HTML page."""

import json
from typing import Any

from ._templates import read_template

_HTML = read_template("term_deposit_column_graph.html")


def render_term_deposit_column_graph(graph: dict[str, Any]) -> str:
    embedded = json.dumps(graph, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    return _HTML.replace("__GRAPH_DATA__", embedded)