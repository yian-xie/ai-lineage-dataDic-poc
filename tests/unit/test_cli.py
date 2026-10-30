import json
from pathlib import Path

import pytest

from lineage_poc.cli import main
from lineage_poc.paths import REFERENCE_LINEAGE


def test_cli_import_is_recorded_and_retries_do_not_overwrite(tmp_path, capsys):
    source = REFERENCE_LINEAGE / "column_lineage.json"
    arguments = ["columns", "--input", str(source), "--run-id", "fixture",
                 "--runs-root", str(tmp_path / "runs")]
    assert main(arguments) == 0
    first = json.loads(capsys.readouterr().out)
    assert Path(first["data_directory"], "column_lineage.json").read_bytes() == source.read_bytes()
    assert main(arguments) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["attempt"] == "attempt-001"
    assert second["attempt"] == "attempt-002"


def test_cli_errors_are_nonzero_and_findable(tmp_path, capsys):
    assert main(["columns", "--input", str(tmp_path / "missing.json"), "--run-id", "fixture",
                 "--runs-root", str(tmp_path / "runs")]) == 1
    error = json.loads(capsys.readouterr().err)
    assert error["status"] == "failed"
    assert Path(error["record"]).is_file()


def test_query_keeps_existing_read_only_behavior(capsys):
    assert main(["query", "--columns", str(REFERENCE_LINEAGE / "column_lineage.json"),
                 "--column", "KiwiAcc"]) == 0
    assert json.loads(capsys.readouterr().out)["match_count"] == 1


@pytest.mark.parametrize("selector", ["", "..\\", "/"])
def test_unsafe_or_empty_focused_selector_does_not_touch_reports(tmp_path, capsys, selector):
    output = tmp_path / "output"
    assert main([
        "html", "--output-dir", str(output), "--input", str(tmp_path / "bundle"),
        "--graphs", str(tmp_path / "graphs"), "--columns", str(tmp_path / "columns"),
        "--selector", selector,
    ]) == 1
    assert json.loads(capsys.readouterr().err)["status"] == "failed"
    assert not output.exists()


def test_focused_report_names_are_stable_for_reordered_or_repeated_selectors(tmp_path, monkeypatch, capsys):
    from lineage_poc import cli

    def recorded(args, stage, inputs, operation, parameters):
        return {"status": "passed", "stage": stage, **parameters}

    monkeypatch.setattr(cli, "_record", recorded)
    arguments = [
        "html", "--output-dir", str(tmp_path), "--input", str(tmp_path / "bundle"),
        "--graphs", str(tmp_path / "graphs"), "--columns", str(tmp_path / "columns"),
        "--selector",
    ]

    def name(selectors):
        assert main(arguments + selectors) == 0
        return json.loads(capsys.readouterr().out)

    first = name(["Account_ID", "OpenDate"])
    assert first["stage"] == "08-html-accountid-opendate"
    assert name(["OpenDate", "Account_ID"])["stage"] == first["stage"]
    assert name(["account_id", "Account ID", "OpenDate"])["stage"] == first["stage"]
    long_selection = ["Column" + str(index) for index in range(20)]
    long_name = name(long_selection)["stage"]
    assert len(long_name) <= 80
    assert name(list(reversed(long_selection)))["stage"] == long_name
    assert name(long_selection + ["OtherColumn"])["stage"] != long_name
