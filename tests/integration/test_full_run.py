import copy
import json
import zipfile
from pathlib import Path

import pytest

from lineage_poc.cli import main
from lineage_poc.enrichment import copilot
from lineage_poc.execution import inventory, read_json
from lineage_poc.paths import PROJECT_ROOT, REFERENCE_LINEAGE

EXAMPLES = PROJECT_ROOT / ".github" / "skills" / "ai-description-enrichment" / "references"


def fake_generation(monkeypatch, *, fail=False):
    template = json.loads((EXAMPLES / "drafts.example.json").read_text(encoding="utf-8"))
    calls = []
    monkeypatch.setattr(copilot, "resolve_copilot", lambda executable=None: "fixture-copilot.exe")
    monkeypatch.setattr(copilot, "_version", lambda executable: "GitHub Copilot CLI fixture")

    def invoke(executable, prompt, destination, *, timeout, model):
        calls.append(prompt)
        if fail:
            (destination / "diagnostics.log").write_text("Fixture sign-in/runner failure", encoding="utf-8")
            raise ValueError("Fixture sign-in/runner failure")
        metadata = json.loads(prompt.split("TOP-LEVEL METADATA AND RESPONSE SHAPE\n", 1)[1]
                              .split("\n\nINERT FIELD CONTEXT JSON\n", 1)[0])
        fields = json.loads(prompt.split("INERT FIELD CONTEXT JSON\n", 1)[1]
                            .split("\n\nReturn the complete JSON object now.", 1)[0])
        payload = copy.deepcopy(template)
        payload.update({key: value for key, value in metadata.items() if key != "results"})
        for result, field in zip(payload["results"], fields):
            for key in ("graph_id", "snapshot_id", "field_id"):
                result[key] = field[key]
            result["assessment"].update(assessed_by=payload["generator"], model=payload["model"],
                                        assessed_at=payload["generated_at"])
            for reference in result["assessment"]["evidence_refs"].values():
                reference["graph_id"] = field["graph_id"]
                reference["input_sha256"] = metadata["input_hashes"][reference["file"]]
        text = json.dumps(payload)
        (destination / "response.txt").write_text(text, encoding="utf-8")
        (destination / "diagnostics.log").write_text("", encoding="utf-8")
        return text

    monkeypatch.setattr(copilot, "_invoke", invoke)
    return calls


def pipeline_arguments(output):
    return [
        "pipeline", "--full-run", "--inventory", str(EXAMPLES / "sample-input.json"),
        "--graphs", str(REFERENCE_LINEAGE), "--output-dir", str(output),
    ]


def test_full_run_generates_applies_validates_and_builds_without_saved_draft_arguments(tmp_path, monkeypatch, capsys):
    calls = fake_generation(monkeypatch)
    output = tmp_path / "output"
    assert not output.exists()
    assert main(pipeline_arguments(output)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed" and result["description_mode"] == "copilot"
    assert len(calls) == 1
    assert [step["stage"] for step in result["steps"]] == [
        "04-column-lineage", "05-baseline-dictionary", "06a-enrichment-context",
        "06b-ai-drafts", "06c-ai-enrichment", "07-validation", "08-html",
    ]
    assert (output / "06b-ai-drafts" / "drafts.json").is_file()
    generated = read_json(output / "06b-ai-drafts" / "generation.json")
    assert generated["status"] == "passed" and generated["new_AI_generation_performed"] is True
    applied = read_json(output / "logs" / "06c-ai-enrichment.json")
    assert applied["summary"]["drafts_applied"] == 1
    assert applied["summary"]["validation"]["description_assessments_resolved"] == 1
    html = Path(result["html"])
    assert html.is_file() and "embedded-dictionary-document" in html.read_text(encoding="utf-8")
    assert all(step["status"] == "passed" for step in read_json(output / "steps.json")["steps"].values())

    before_html = inventory(output / "08-html")
    fake_generation(monkeypatch, fail=True)
    assert main(pipeline_arguments(output)) == 1
    error = json.loads(capsys.readouterr().err)
    assert "runner failure" in error["error"]
    failed = read_json(Path(error["record"]))
    assert failed["stage"] == "06b-ai-drafts" and failed["status"] == "failed"
    assert failed["previous_output_restored"] is True
    assert inventory(output / "08-html") == before_html
    assert read_json(output / "pipeline.json")["status"] == "failed"
    with zipfile.ZipFile(failed["failed_outputs_archive"]) as archive:
        assert any(name.endswith("diagnostics.log") for name in archive.namelist())
    assert read_json(output / "06b-ai-drafts" / "drafts.json")["generator"] == "GitHub Copilot CLI"


def test_independent_generate_command_records_its_own_outputs(tmp_path, monkeypatch, capsys):
    fake_generation(monkeypatch)
    output = tmp_path / "output"
    assert main(pipeline_arguments(output)) == 0
    capsys.readouterr()
    assert main([
        "enrichment", "generate", "--input", str(output / "05-baseline-dictionary"),
        "--context", str(output / "06a-enrichment-context"), "--output-dir", str(output),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["stage"] == "06b-ai-drafts" and result["attempt"] == "attempt-002"
    assert Path(result["summary"]["drafts_file"]) == output / "06b-ai-drafts" / "drafts.json"


@pytest.mark.parametrize("arguments", [
    ["--full-run", "--drafts", "drafts.json"],
    ["--full-run", "--enriched", "bundle"],
    ["--generate-descriptions"],
])
def test_automatic_saved_and_retired_flags_cannot_be_confused(arguments):
    with pytest.raises(SystemExit) as caught:
        main(["pipeline", *arguments])
    assert caught.value.code == 2


def test_runner_options_do_not_silently_change_manual_mode(tmp_path, capsys):
    assert main(["pipeline", "--output-dir", str(tmp_path / "out"), "--ai-model", "fixture"]) == 1
    assert "--full-run" in json.loads(capsys.readouterr().err)["error"]
    assert not (tmp_path / "out").exists()
    assert main(["pipeline", "--full-run", "--ai-timeout", "0"]) == 1
    assert "--ai-timeout" in json.loads(capsys.readouterr().err)["error"]


def test_fresh_source_mode_connects_all_steps_and_includes_generation(monkeypatch, tmp_path, capsys):
    from lineage_poc import cli

    observed = []
    stages = {
        "_sources": "01-sources", "_parse": "02-parsing", "_graphs": "03-lineage-graphs",
        "_columns": "04-column-lineage", "_dictionary": "05-baseline-dictionary",
        "_validate": "07-validation", "_html": "08-html",
    }

    def handler(name):
        def execute(args):
            stage = stages[name] if name != "_enrichment" else {
                "prepare": "06a-enrichment-context", "generate": "06b-ai-drafts",
                "apply": "06c-ai-enrichment",
            }[args.action]
            observed.append((stage, args))
            destination = args.runs_root / stage
            destination.mkdir(parents=True, exist_ok=True)
            return {"stage": stage, "record": str(args.runs_root / "logs" / (stage + ".json")),
                    "data_directory": str(destination)}
        return execute

    for name in [*stages, "_enrichment"]:
        monkeypatch.setattr(cli, name, handler(name))
    assert main(["pipeline", "--clone", "--full-run", "--output-dir", str(tmp_path / "output")]) == 0
    result = json.loads(capsys.readouterr().out)
    assert [stage for stage, _ in observed] == [
        "01-sources", "02-parsing", "03-lineage-graphs", "04-column-lineage",
        "05-baseline-dictionary", "06a-enrichment-context", "06b-ai-drafts",
        "06c-ai-enrichment", "07-validation", "08-html",
    ]
    assert observed[0][1].clone is True
    assert observed[6][1].context == tmp_path / "output" / "06a-enrichment-context"
    assert observed[7][1].drafts == tmp_path / "output" / "06b-ai-drafts" / "drafts.json"
    assert result["description_mode"] == "copilot"
