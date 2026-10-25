import json
import re
from pathlib import Path

from lineage_poc.cli import main
from lineage_poc.execution import inventory, read_json
from lineage_poc.paths import INPUT_ROOT, REFERENCE_DICTIONARY, REFERENCE_LINEAGE


def test_reference_replay_reproduces_baseline_and_builds_one_combined_html(tmp_path, capsys):
    runs = tmp_path / "runs"
    arguments = [
        "pipeline", "--run-id", "reference", "--runs-root", str(runs),
        "--inventory", str(INPUT_ROOT / "column_lineage.json"),
        "--enriched", str(REFERENCE_DICTIONARY / "ai-enriched"),
        "--graphs", str(REFERENCE_LINEAGE),
    ]
    assert main(arguments) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    stages = {step["stage"]: Path(step["data_directory"]) for step in result["steps"]}
    assert "02-parsing" not in stages
    for name in ("asset_registry.csv", "field_catalog.csv", "data_dictionary.csv"):
        assert (stages["05-baseline-dictionary"] / name).read_bytes() == (
            REFERENCE_DICTIONARY / "baseline" / name
        ).read_bytes()
        assert (stages["06c-ai-enrichment"] / name).read_bytes() == (
            REFERENCE_DICTIONARY / "ai-enriched" / name
        ).read_bytes()
    assert Path(result["html"]).is_file()
    html = Path(result["html"])
    assert "embedded-dictionary-document" in html.read_text(encoding="utf-8")
    assert list(html.parent.glob("*.html")) == [html]
    assert all(step["status"] == "passed" for step in read_json(runs / "steps.json")["steps"].values())

    def json_script(document, identity):
        match = re.search(
            r'<script\b[^>]*\bid="' + re.escape(identity) + r'"[^>]*>(.*?)</script>',
            document, re.S,
        )
        assert match, identity
        return json.loads(match[1])

    main_before = inventory(html.parent)
    main_record_path = runs / "logs" / "08-html.json"
    main_record_before = main_record_path.read_bytes()
    focused_arguments = [
        "html", "--output-dir", str(runs),
        "--input", str(stages["06c-ai-enrichment"]),
        "--baseline", str(stages["05-baseline-dictionary"]),
        "--graphs", str(REFERENCE_LINEAGE),
        "--columns", str(stages["04-column-lineage"]),
        "--selector", "Account_ID",
    ]
    assert main(focused_arguments) == 0
    focused = json.loads(capsys.readouterr().out)
    focused_path = Path(focused["summary"]["html"])
    assert focused_path == runs / "08-html-accountid" / "index.html"
    focused_document = focused_path.read_text(encoding="utf-8")
    records = json_script(focused_document, "column-data")
    assert [record["param_column"] for record in records] == ["KiwiAcc"]
    assert len(records[0]["dbt_targets"]) == 2
    assert json_script(focused_document, "embedded-dictionary-document") == json_script(
        html.read_text(encoding="utf-8"), "embedded-dictionary-document",
    )
    assert inventory(html.parent) == main_before
    assert main_record_path.read_bytes() == main_record_before

    multi_arguments = focused_arguments + ["OpenDate", "KiwiAcc"]
    assert main(multi_arguments) == 0
    multi = json.loads(capsys.readouterr().out)
    multi_path = Path(multi["summary"]["html"])
    assert multi_path == runs / "08-html-accountid-kiwiacc-opendate" / "index.html"
    selected_records = json_script(multi_path.read_text(encoding="utf-8"), "column-data")
    assert {record["param_column"] for record in selected_records} == {"KiwiAcc", "OpenDate"}
    assert len(selected_records) == 2
    assert "Account_ID, OpenDate, KiwiAcc" in multi_path.read_text(encoding="utf-8")
    assert inventory(html.parent) == main_before
    assert main_record_path.read_bytes() == main_record_before

    multi_before = inventory(multi_path.parent)
    assert main(multi_arguments + ["NotARecordedColumn"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert "NotARecordedColumn" in error["error"]
    assert inventory(multi_path.parent) == multi_before
    assert inventory(html.parent) == main_before

    focused_before = inventory(focused_path.parent)
    assert main(focused_arguments[:-1] + ["NotARecordedColumn"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert read_json(Path(error["record"]))["status"] == "failed"
    assert inventory(html.parent) == main_before
    assert inventory(focused_path.parent) == focused_before

    assert main(focused_arguments[:-1] + ["OpenDate"]) == 0
    other = json.loads(capsys.readouterr().out)
    other_path = Path(other["summary"]["html"])
    assert other_path == runs / "08-html-opendate" / "index.html"
    assert [record["param_column"] for record in json_script(
        other_path.read_text(encoding="utf-8"), "column-data",
    )] == ["OpenDate"]
    assert inventory(focused_path.parent) == focused_before
    assert main(focused_arguments) == 0
    retried = json.loads(capsys.readouterr().out)
    assert retried["attempt"] == "attempt-002"
    assert Path(retried["summary"]["html"]) == focused_path
    assert inventory(html.parent) == main_before
    assert main_record_path.read_bytes() == main_record_before


def test_missing_ai_drafts_are_an_explicit_handoff_not_fake_generation(tmp_path, capsys):
    runs = tmp_path / "runs"
    assert main([
        "pipeline", "--run-id", "needs-ai", "--runs-root", str(runs),
        "--inventory", str(INPUT_ROOT / "column_lineage.json"),
    ]) == 3
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "awaiting_ai_drafts"
    assert Path(result["context"]).is_dir()
    assert not (runs / "08-html").exists()
    assert not (tmp_path / "published").exists()
    assert read_json(runs / "pipeline.json")["status"] == "awaiting_ai_drafts"


def test_failed_pipeline_replaces_running_status_with_failure_record(tmp_path, capsys):
    runs = tmp_path / "runs"
    assert main([
        "pipeline", "--run-id", "failed", "--runs-root", str(runs),
        "--inventory", str(tmp_path / "missing.json"),
    ]) == 1
    result = json.loads(capsys.readouterr().err)
    assert result["status"] == "failed"
    report = read_json(runs / "pipeline.json")
    assert report["status"] == "failed"
    assert Path(report["failed_step_record"]).is_file()


def test_source_configuration_failure_has_an_attempt_record(tmp_path, capsys):
    config = tmp_path / "invalid.json"
    config.write_text('{"repositories": []}', encoding="utf-8")
    assert main(["sources", "--run-id", "invalid-sources", "--runs-root", str(tmp_path / "runs"),
                 "--config", str(config)]) == 1
    error = json.loads(capsys.readouterr().err)
    assert read_json(Path(error["record"]))["status"] == "failed"
