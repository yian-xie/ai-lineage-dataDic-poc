from lineage_poc.graph.term_deposit_comparison import _comparison_html


def test_comparison_index_links_two_separate_graph_snapshots():
    html = _comparison_html({
        "options": [
            {
                "option_id": "account_context",
                "title": "Account-context graph",
                "scope": "DWTDS to Account RAW",
                "nodes": 25,
                "edges": 22,
                "mapped_columns": 40,
                "unmapped_columns": 2,
                "candidate_links": 0,
                "boundary": "Account route only.",
                "snapshot_file": "option_a_account_context.json",
                "report_link": "../12-term-deposit-rich-html/index.html",
            },
            {
                "option_id": "tenant_landing",
                "title": "Tenant Landing graph",
                "scope": "DWTDS to ultracs-v1 Landing",
                "nodes": 23,
                "edges": 25,
                "mapped_columns": 41,
                "unmapped_columns": 1,
                "candidate_links": 1,
                "boundary": "HVR and Landing database/schema identity is unresolved.",
                "snapshot_file": "option_b_tenant_landing.json",
                "report_link": "../13-term-deposit-landing-lineage/index.html",
            },
        ],
    })

    assert "Account-context graph" in html
    assert "Tenant Landing graph" in html
    assert "option_a_account_context.json" in html
    assert "option_b_tenant_landing.json" in html
    assert "../12-term-deposit-rich-html/index.html" in html
    assert "../13-term-deposit-landing-lineage/index.html" in html