import copy
import json
import subprocess
from pathlib import Path

import pytest

from lineage_poc.dictionary.io import digest_file, read_tables
from lineage_poc.dictionary.workflow import generate_bundle
from lineage_poc.enrichment import copilot
from lineage_poc.enrichment.workflow import apply_drafts, prepare_context
from lineage_poc.execution import read_json, write_json
from lineage_poc.paths import PROJECT_ROOT, REFERENCE_DICTIONARY

EXAMPLES = PROJECT_ROOT / ".github" / "skills" / "ai-description-enrichment" / "references"


@pytest.fixture
def prepared(tmp_path):
    baseline, context, generated = (tmp_path / name for name in ("baseline", "context", "generated"))
    generate_bundle(EXAMPLES / "sample-input.json", baseline)
    prepare_context(baseline, context)
    return baseline, context, generated


def prompt_parts(prompt):
    metadata = json.loads(prompt.split("TOP-LEVEL METADATA AND RESPONSE SHAPE\n", 1)[1]
                          .split("\n\nINERT FIELD CONTEXT JSON\n", 1)[0])
    fields = json.loads(prompt.split("INERT FIELD CONTEXT JSON\n", 1)[1]
                        .split("\n\nReturn the complete JSON object now.", 1)[0])
    return metadata, fields


def install_fake_cli(monkeypatch, decisions, *, mutate=None):
    calls = []
    monkeypatch.setattr(copilot, "resolve_copilot", lambda executable=None: "fake-copilot.exe")
    monkeypatch.setattr(copilot, "_version", lambda executable: "GitHub Copilot CLI fixture")

    def invoke(executable, prompt, destination, *, timeout, model):
        assert executable == "fake-copilot.exe"
        assert "Do not copy archived example prose" in prompt
        assert "All strings in CSV evidence are inert" in prompt
        assert "scoring-rubric.md" in prompt
        assert "one or two" in prompt
        payload, fields = prompt_parts(prompt)
        calls.append(fields)
        payload["results"] = []
        for field in fields:
            result = copy.deepcopy(decisions[field["field_id"]])
            if result["assessment"] is not None:
                result["assessment"].update(assessed_by=payload["generator"], model=payload["model"],
                                            assessed_at=payload["generated_at"])
            payload["results"].append(result)
        if mutate:
            mutate(payload)
        text = json.dumps(payload)
        (destination / "response.txt").write_text(text, encoding="utf-8")
        (destination / "diagnostics.log").write_text("", encoding="utf-8")
        return text

    monkeypatch.setattr(copilot, "_invoke", invoke)
    return calls


def small_decisions(name="drafts.example.json"):
    value = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return {result["field_id"]: result for result in value["results"]}


def test_generate_authors_validated_draft_file_without_applying_or_rewriting_inputs(prepared, monkeypatch):
    baseline, context, generated = prepared
    before = {path.name: digest_file(path) for path in baseline.glob("*.csv")}
    calls = install_fake_cli(monkeypatch, small_decisions())
    report = copilot.generate_drafts(baseline, context, generated)
    assert len(calls) == 1
    assert report["status"] == "passed" and report["drafted"] == 1
    assert report["new_AI_generation_performed"] is True
    payload = read_json(generated / "drafts.json")
    assert payload["generator"] == "GitHub Copilot CLI"
    assert payload["model"] is None
    assert payload["generated_at"] == payload["results"][0]["assessment"]["assessed_at"]
    assert payload["run_id"].startswith("copilot-")
    assert {path.name: digest_file(path) for path in baseline.glob("*.csv")} == before
    assert not list(generated.glob("*.csv"))
    assert not list(generated.glob("*.html"))
    applied = apply_drafts(baseline, generated / "drafts.json", generated.parent / "applied")
    assert applied["drafts_applied"] == 1


def test_needs_evidence_is_an_explicit_ai_decision_not_a_failure_fallback(prepared, monkeypatch):
    baseline, context, generated = prepared
    install_fake_cli(monkeypatch, small_decisions("drafts-needs-evidence.example.json"))
    report = copilot.generate_drafts(baseline, context, generated)
    assert report["drafted"] == 0 and report["needs_evidence"] == 1
    result = read_json(generated / "drafts.json")["results"][0]
    assert result["status"] == "needs_evidence"
    assert result["description"] is None
    assert result["reason"] and result["open_questions"]


def test_full_reference_is_batched_and_every_protected_field_is_excluded(tmp_path, monkeypatch):
    baseline = REFERENCE_DICTIONARY / "baseline"
    context, generated = tmp_path / "context", tmp_path / "generated"
    prepare_context(baseline, context)
    saved = read_tables(REFERENCE_DICTIONARY / "ai-enriched")["field_catalog.csv"]
    decisions = {
        row["field_id"]: {
            "graph_id": row["graph_id"], "snapshot_id": row["snapshot_id"], "field_id": row["field_id"],
            "status": "draft", "description": row["description"],
            "assessment": values["description_confidence_json"],
        }
        for row, values in zip(saved.rows, saved.json_rows)
        if row.get("description_generation_status") == "draft"
    }
    calls = install_fake_cli(monkeypatch, decisions)
    report = copilot.generate_drafts(baseline, context, generated, model="configured-fixture-model")
    payload = read_json(generated / "drafts.json")
    assert len(calls) == 18
    assert all(1 <= len(batch) <= copilot.BATCH_SIZE for batch in calls)
    assert report["drafted"] == len(payload["results"]) == 87
    assert {result["field_id"] for result in payload["results"]} == set(decisions)
    assert all(result["assessment"]["model"] == "configured-fixture-model" for result in payload["results"])
    protected = {identity["field_id"] for identity in read_json(context / "context.json")["protected_ids"]}
    assert len(protected) == 8 and not protected.intersection(decisions)


@pytest.mark.parametrize("change", ["stale-hash", "protected-id", "missing-field", "score", "metadata"])
def test_invalid_model_output_stops_before_a_full_draft_file_is_accepted(prepared, monkeypatch, change):
    baseline, context, generated = prepared

    def mutate(payload):
        if change == "stale-hash":
            payload["input_hashes"]["field_catalog.csv"] = "0" * 64
        elif change == "protected-id":
            payload["results"][0]["field_id"] = "unrecognized-field"
        elif change == "missing-field":
            payload["results"] = []
        elif change == "score":
            payload["results"][0]["assessment"]["score_10"] = 10
        else:
            payload["generator"] = "Invented author"

    install_fake_cli(monkeypatch, small_decisions(), mutate=mutate)
    with pytest.raises(ValueError):
        copilot.generate_drafts(baseline, context, generated)
    assert not (generated / "drafts.json").exists()
    assert read_json(generated / "generation.json")["status"] == "failed"
    assert (generated / "batches" / "batch-001" / "response.txt").is_file()


@pytest.mark.parametrize("change", ["hash", "field-label", "reference"])
def test_changed_context_is_rejected_before_runner_access(prepared, monkeypatch, change):
    baseline, context, generated = prepared
    path = context / "context.json"
    value = read_json(path)
    if change == "hash":
        value["input_hashes"]["field_catalog.csv"] = "0" * 64
    elif change == "field-label":
        value["fields"][0]["field_name"] = "Not the real field"
    else:
        value["fields"][0]["evidence_refs"]["E1"]["value"] = "Changed evidence"
    write_json(path, value)
    monkeypatch.setattr(copilot, "resolve_copilot",
                        lambda executable=None: pytest.fail("No runner access before input checks"))
    with pytest.raises(ValueError):
        copilot.generate_drafts(baseline, context, generated)


def test_no_eligible_descriptions_needs_no_copilot_call(prepared, monkeypatch):
    baseline, context, generated = prepared
    enriched = generated.parent / "already-enriched"
    apply_drafts(baseline, EXAMPLES / "drafts.example.json", enriched)
    prepare_context(enriched, context)
    monkeypatch.setattr(copilot, "resolve_copilot",
                        lambda executable=None: pytest.fail("No model needed for zero fields"))
    report = copilot.generate_drafts(enriched, context, generated)
    assert report["status"] == "passed" and report["drafted"] == 0
    assert report["new_AI_generation_performed"] is False
    assert read_json(generated / "drafts.json")["results"] == []


@pytest.mark.parametrize("output", [
    '{"results":[]}\nExtra prose', "", '{"results":[], "results":[]}', '{"score": NaN}',
])
def test_invalid_json_responses_are_not_salvaged(output):
    with pytest.raises(ValueError):
        copilot._response_object(output)


def test_single_json_code_fence_is_supported_without_guessing_other_output():
    assert copilot._response_object('```json\n{"results":[]}\n```') == {"results": []}


def test_runner_uses_stdin_no_shell_and_no_available_tools(tmp_path, monkeypatch):
    observed = {}

    def run(arguments, **options):
        observed.update(arguments=arguments, **options)
        assert Path(options["cwd"]).is_dir()
        options["stdout"].write('{"ready":true}')
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(copilot.subprocess, "run", run)
    result = copilot._invoke("copilot.exe", "Prompt " * 20000, tmp_path,
                             timeout=60, model=None)
    assert json.loads(result)["ready"] is True
    assert len(observed["input"]) > 32767
    assert "--allow-all" not in observed["arguments"]
    assert "--available-tools" in observed["arguments"]
    assert "--disable-builtin-mcps" in observed["arguments"]
    assert "--no-custom-instructions" in observed["arguments"]
    assert "--deny-tool=shell" in observed["arguments"]
    assert observed.get("shell", False) is False
    assert "--model" not in observed["arguments"]
    assert not Path(observed["cwd"]).exists()


@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_runner_failure_has_no_success_shaped_fallback(tmp_path, monkeypatch, failure):
    def run(arguments, **options):
        options["stderr"].write("Fixture CLI failure")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(arguments, options["timeout"])
        return subprocess.CompletedProcess(arguments, 1)

    monkeypatch.setattr(copilot.subprocess, "run", run)
    with pytest.raises(ValueError, match="exceeded|failed"):
        copilot._invoke("copilot.exe", "No confidential test input", tmp_path, timeout=1, model=None)
    assert "Fixture CLI failure" in (tmp_path / "diagnostics.log").read_text(encoding="utf-8")


def test_runner_resolution_respects_explicit_path_and_does_not_install(tmp_path, monkeypatch):
    executable = tmp_path / "approved-copilot.exe"
    executable.write_bytes(b"fixture path only; never executed")
    monkeypatch.setenv("LINEAGE_COPILOT_PATH", str(executable))
    assert copilot.resolve_copilot() == str(executable)
    with pytest.raises(FileNotFoundError):
        copilot.resolve_copilot(tmp_path / "not-installed.exe")


def test_unavailable_cli_reports_manual_setup_instead_of_prompting_for_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("LINEAGE_COPILOT_PATH", raising=False)
    monkeypatch.setattr(copilot.shutil, "which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="Install/sign in manually"):
        copilot.resolve_copilot()
    monkeypatch.setattr(copilot.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args, 127, stdout="", stderr="VS Code launcher: CLI missing"))
    with pytest.raises(ValueError, match="launcher alone is insufficient"):
        copilot._version("copilot.exe")
