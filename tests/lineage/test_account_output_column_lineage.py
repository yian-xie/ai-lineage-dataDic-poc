from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT
from pathlib import Path

PROJECT_ROOT = REPOSITORY_ROOT

import lineage_poc.columns.account_outputs as account_outputs
from lineage_poc.columns import dwacc, dwrel


RECORDS = {
    feed: account_outputs.build_feed_records(feed)
    for feed in account_outputs.FEEDS
}
BY_NAME = {
    feed: {record["param_column"]: record for record in records}
    for feed, records in RECORDS.items()
}


def test_basic_output_counts_match_parameter_columns():
    assert {feed: len(records) for feed, records in RECORDS.items()} == {
        "DWDBUST": 19,
        "DWTDS": 42,
        "DWACFEE": 19,
        "DWSWEEP": 7,
        "ACCREC_": 5,
        "DWNOMACC": 10,
        "DWUNCLD": 10,
    }
    assert all(
        [record["ultracs_position"] for record in records] == list(range(1, len(records) + 1))
        for records in RECORDS.values()
    )


def test_only_exact_case_sensitive_dbt_keys_are_attached():
    assert all(record["dbt_targets"] for record in RECORDS["DWDBUST"])
    assert all(record["dbt_targets"] for record in RECORDS["DWACFEE"])
    assert all(record["dbt_targets"] for record in RECORDS["DWSWEEP"])
    assert all(record["dbt_targets"] for record in RECORDS["ACCREC_"])
    assert all(record["dbt_targets"] for record in RECORDS["DWUNCLD"])

    assert not BY_NAME["DWTDS"]["Prod"]["dbt_targets"]
    assert not BY_NAME["DWTDS"]["col40"]["dbt_targets"]
    assert "Product" in BY_NAME["DWTDS"]["Prod"]["notes"]
    assert "position 2" in BY_NAME["DWTDS"]["Prod"]["notes"]
    assert not BY_NAME["DWNOMACC"]["RefDate"]["dbt_targets"]
    assert "ReferenceDate" in BY_NAME["DWNOMACC"]["RefDate"]["notes"]


def test_public_targets_follow_explicit_model_projections():
    # These current public models consume tenant landing, not the parsed internal models.
    assert all(target["stage"] == "internal" for record in RECORDS["DWDBUST"] for target in record["dbt_targets"])
    assert all(target["stage"] == "internal" for record in RECORDS["DWTDS"] for target in record["dbt_targets"])
    assert all(target["stage"] == "internal" for record in RECORDS["DWACFEE"] for target in record["dbt_targets"])
    assert all(target["stage"] == "internal" for record in RECORDS["DWSWEEP"] for target in record["dbt_targets"])


def test_landing_handoff_gaps_are_preserved():
    for feed in ("ACCREC_", "DWNOMACC", "DWUNCLD"):
        assert all(record["route_status"] == "landing_handoff_unverified" for record in RECORDS[feed])
    for feed in ("DWDBUST", "DWTDS", "DWACFEE", "DWSWEEP"):
        assert all(record["route_status"] == "repository_static_route_found" for record in RECORDS[feed])


def test_combined_account_column_count_is_a_feed_position_count():
    summary = account_outputs.build_summary(
        RECORDS,
        existing_inventories={"DWACC": dwacc.build_records(), "DWREL": dwrel.build_records()},
    )

    assert summary["field_positions_across_scoped_feeds"] == 222
    assert summary["distinct_parameter_labels_case_insensitive"] == 207
    assert summary["feed_fields_with_internal_dbt_target"] == 215
    assert summary["feed_fields_with_public_dbt_target"] == 62
    assert summary["dbt_target_projections_across_scoped_feeds"] == 334