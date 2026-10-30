"""Render recorded column and graph snapshots without extracting source again."""

import json
import re
from html import escape
from typing import Any

from lineage_poc.columns.dwacc import build_enterprise_overview
from lineage_poc.graph.account import with_related_columns
from ._templates import read_template
from .descriptions import describe_graph
from .focused import FLOW_STYLE, flow_section

HTML = read_template("dwacc_html.html")


def embed_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")


def _schema_flow_entry(kind: str, name: str, group: str) -> str:
    return f"schemaFlowEntry(schemaFlowFind('{kind}','name','{name}'),'{name}','{group}')"


def render_html(
    graph: dict,
    records: list[dict],
    enterprise_graph: dict | None = None,
    *,
    dictionary_document: str | None = None,
    feed: str = "DWACC",
    selector: str | None = None,
) -> str:
    table_graph = describe_graph(with_related_columns(graph, records))
    overview = build_enterprise_overview(records, graph=enterprise_graph or {"nodes": [], "edges": []})
    template = HTML
    if feed == "DWREL":
        substitutions = {
            _schema_flow_entry("DBT_MODEL", "accounts_v1__ultracs_accounts_detail", "jobs"):
                _schema_flow_entry("DBT_MODEL", "account_relationship_v1__customer_account_relationship_v1", "jobs"),
            _schema_flow_entry("SNOWFLAKE_RELATION", "PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL", "target"):
                _schema_flow_entry("SNOWFLAKE_RELATION", "INTERNAL.ACCOUNT_RELATIONSHIP_V1__CUSTOMER_ACCOUNT_RELATIONSHIP_V1", "target"),
            "DWACC": "DWREL", "dwacc": "dwrel",
            "accounts-v1": "account-relationship-v1",
            "ult_s3_acc": "ult_s3_rel", "ult_sf_acc": "ult_sf_rel",
            "LOADACCOUNTS_INGEST": "LOADRELATIONSHIPS_INGEST",
            "loadaccounts_ingest": "loadrelationships_ingest",
            "ACCOUNTS_V1__ACCOUNTS": "ACCOUNT_RELATIONSHIP_V1__RELATIONSHIPS",
            "accounts_v1__ultracs_accounts_detail_v2": "account_relationship_v1__customer_account_relationship_v1",
            "accounts_v1__ultracs_accounts_detail": "account_relationship_v1__customer_account_relationship",
            "accounts_v1__ultracs_accounts_eod_balances_v2": "v_account_relationship_v1__accrelationship_v1",
            "accounts_v1__ultracs_accounts_eod_balances": "vw_account_relationship_v1__accrelationship_v1",
            "ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL": "ACCOUNT_RELATIONSHIP_V1__CUSTOMER_ACCOUNT_RELATIONSHIP",
            "'TRAN'": "'EMAIL.DETAILS'",
        }
        for old in sorted(substitutions, key=len, reverse=True):
            template = template.replace(old, substitutions[old])
    if selector is not None:
        title = escape(f"{selector} ({feed})")
        template = template.replace(f"<title>{feed} Column Lineage</title>", f"<title>{title} Column Lineage</title>")
        template = template.replace(f"{feed} column lineage", f"{title} lineage")
    replacements = {
        "__TABLE_DATA__": embed_json(table_graph),
        "__COLUMN_DATA__": embed_json(records),
        "__ENTERPRISE_DATA__": embed_json(describe_graph(overview)),
        "__DICTIONARY_DOCUMENT__": embed_json(dictionary_document or ""),
    }
    rendered = re.sub("|".join(replacements), lambda match: replacements[match.group(0)], template)
    if selector is not None and records:
        marker = "</header>\n<main>"
        if rendered.count(marker) != 1 or rendered.count("</head>") != 1:
            raise ValueError("The selected-column template must contain one field-path insertion point.")
        rendered = rendered.replace(
            "</head>", '<style id="field-path-styles">' + FLOW_STYLE + "</style>\n</head>", 1,
        )
        related = [
            mapping for node in table_graph["nodes"]
            for mapping in node.get("properties", {}).get("related_columns", [])
        ]
        rendered = rendered.replace(
            marker, "</header>\n" + flow_section(records, related) + "\n<main>", 1,
        )
    return rendered
