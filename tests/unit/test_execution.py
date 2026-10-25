import json
import zipfile
from pathlib import Path

import pytest

from lineage_poc.execution import StepFailure, accepted_data, execute_step, read_json


def test_success_records_inputs_outputs_and_implementation(tmp_path):
    source = tmp_path / "input.json"
    source.write_text('{"value": 1}', encoding="utf-8")

    def work(output):
        (output / "result.json").write_bytes(source.read_bytes())
        print("Recorded diagnostic")
        return {"rows": 1}

    result = execute_step(tmp_path / "runs", "example", "04-columns", inputs=[source],
                          parameters={}, operation=work)
    assert result["status"] == "passed"
    assert result["inputs"][0]["sha256"] == result["outputs"]["files"][0]["sha256"]
    assert result["implementation"]["sha256"]
    assert result["runtime"]["python"] and result["runtime"]["platform"]
    assert "Recorded diagnostic" in Path(result["log"]).read_text()
    assert accepted_data(Path(result["data_directory"]))["status"] == "passed"


def test_latest_result_replaces_previous_files_and_logs_keep_failures(tmp_path):
    def fail(output):
        (output / "partial.txt").write_text("debug evidence")
        raise ValueError("Deliberate fixture failure")

    with pytest.raises(StepFailure) as caught:
        execute_step(tmp_path, "example", "03-graphs", inputs=[], parameters={}, operation=fail)
    failed = read_json(caught.value.record)
    assert failed["status"] == "failed"
    assert "Deliberate fixture failure" in Path(failed["log"]).read_text()
    with zipfile.ZipFile(failed["failed_outputs_archive"]) as archive:
        assert archive.read("partial.txt") == b"debug evidence"
    retried = execute_step(tmp_path, "example", "03-graphs", inputs=[],
                           parameters={}, operation=lambda output: {"count": 0})
    assert retried["attempt"] == "attempt-002"
    assert read_json(caught.value.record)["status"] == "passed"
    assert retried["data_directory"] == str(tmp_path / "03-graphs")
    assert not (tmp_path / "example").exists()
    index = read_json(tmp_path / "steps.json")
    assert index["steps"]["03-graphs"]["status"] == "passed"
    assert "Deliberate fixture failure" in Path(retried["log"]).read_text()


@pytest.mark.parametrize("run_id", ["../other", "", "CON", "NUL.txt", "ends.", "a\\b"])
def test_invalid_run_ids_do_not_create_output(tmp_path, run_id):
    with pytest.raises(ValueError):
        execute_step(tmp_path / "runs", run_id, "test", inputs=[], parameters={},
                     operation=lambda output: {})
    assert not (tmp_path / "runs").exists()


def test_changed_input_is_not_accepted(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("before")

    def work(output):
        source.write_text("after")
        return {}

    with pytest.raises(StepFailure, match="input changed"):
        execute_step(tmp_path / "runs", "example", "test", inputs=[source],
                     parameters={}, operation=work)


def test_tampered_outputs_cannot_be_reused(tmp_path):
    def work(output):
        (output / "result.txt").write_text("original")
        return {}

    result = execute_step(tmp_path / "runs", "example", "test", inputs=[],
                          parameters={}, operation=work)
    (Path(result["data_directory"]) / "result.txt").write_text("modified")
    with pytest.raises(ValueError, match="outputs have changed"):
        accepted_data(Path(result["data_directory"]))


def test_missing_input_and_nonfinite_results_are_recorded_failures(tmp_path):
    with pytest.raises(StepFailure):
        execute_step(tmp_path / "runs", "missing", "missing-test", inputs=[tmp_path / "absent"],
                     parameters={}, operation=lambda output: {})
    with pytest.raises(StepFailure):
        execute_step(tmp_path / "runs", "nonfinite", "nonfinite-test", inputs=[], parameters={},
                     operation=lambda output: {"score": float("nan")})
    records = list((tmp_path / "runs" / "logs").glob("*.json"))
    assert len(records) == 2
    assert all(json.loads(path.read_text())["status"] == "failed" for path in records)


def test_concurrent_implementation_change_rejects_the_attempt(tmp_path, monkeypatch):
    from lineage_poc import execution

    original = execution.inventory
    implementation = Path(execution.__file__).parent.resolve()
    reads = 0

    def changing_inventory(path):
        nonlocal reads
        if path.resolve() == implementation:
            reads += 1
            return {"path": str(implementation), "sha256": str(reads)}
        return original(path)

    monkeypatch.setattr(execution, "inventory", changing_inventory)
    with pytest.raises(StepFailure, match="Application code changed"):
        execute_step(tmp_path / "runs", "changing-code", "test", inputs=[], parameters={},
                     operation=lambda output: {})


def test_failed_upstream_data_cannot_be_used_as_a_completed_step(tmp_path):
    def partial(output):
        (output / "apparently-valid.json").write_text('{"value": 1}')
        raise ValueError("Upstream did not complete")

    with pytest.raises(StepFailure) as caught:
        execute_step(tmp_path / "runs", "example", "01-upstream", inputs=[], parameters={},
                     operation=partial)
    data = tmp_path / "runs" / "01-upstream"
    called = False

    def downstream(output):
        nonlocal called
        called = True
        return {}

    with pytest.raises(StepFailure, match="successful recorded step"):
        execute_step(tmp_path / "runs", "example", "02-downstream",
                     inputs=[data / "apparently-valid.json"], parameters={}, operation=downstream)
    assert called is False


def test_failed_rerun_restores_previous_good_files(tmp_path):
    def good(output):
        (output / "index.html").write_text("good report")
        return {}

    result = execute_step(tmp_path, "test", "08-html", inputs=[], parameters={}, operation=good)

    def bad(output):
        (output / "index.html").write_text("partial report")
        raise ValueError("Rendering failed")

    with pytest.raises(StepFailure):
        execute_step(tmp_path, "test", "08-html", inputs=[], parameters={}, operation=bad)
    assert Path(result["data_directory"], "index.html").read_text() == "good report"
    failed = read_json(Path(result["record"]))
    assert failed["previous_output_restored"] is True
    assert failed["status"] == "failed"
    with pytest.raises(ValueError, match="successful recorded step"):
        accepted_data(Path(result["data_directory"]))


def test_cleanup_denial_reports_warning_without_misreporting_a_saved_result(tmp_path, monkeypatch):
    def work(output):
        (output / "result.txt").write_text("complete")
        return {}

    execute_step(tmp_path, "test", "step", inputs=[], parameters={}, operation=work)
    original = Path.rmdir

    def deny_work_cleanup(path):
        if path.name == ".work":
            raise PermissionError("Fixture OneDrive cleanup restriction")
        original(path)

    monkeypatch.setattr(Path, "rmdir", deny_work_cleanup)
    result = execute_step(tmp_path, "test", "step", inputs=[], parameters={}, operation=work)
    assert result["status"] == "passed"
    assert "cleanup restriction" in result["cleanup_warning"]
    assert "Cleanup warning:" in Path(result["log"]).read_text()
    assert accepted_data(Path(result["data_directory"]))["status"] == "passed"
