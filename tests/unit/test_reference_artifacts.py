import hashlib
import subprocess

from lineage_poc.execution import read_json
from lineage_poc.paths import INPUT_ROOT, REFERENCE_ROOT


def test_original_reference_artifacts_are_byte_identical():
    manifest = read_json(REFERENCE_ROOT / "manifest.json")
    assert manifest["source_repository_commits"] is None
    assert hashlib.sha256((INPUT_ROOT / "column_lineage.json").read_bytes()).hexdigest() == manifest["input"]["sha256"]
    for name, expected in manifest["artifacts"].items():
        assert hashlib.sha256((REFERENCE_ROOT / name).read_bytes()).hexdigest() == expected["sha256"], name


def test_git_does_not_rewrite_hash_bound_fixture_bytes():
    from lineage_poc.paths import PROJECT_ROOT

    result = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "check-attr", "text", "--",
         str(INPUT_ROOT / "column_lineage.json")],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip().endswith(": text: unset")
