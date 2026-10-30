import re
from urllib.parse import unquote

import yaml

from lineage_poc.paths import PROJECT_ROOT


def active_documents():
    for relative in ("README.md",):
        yield PROJECT_ROOT / relative
    yield from (PROJECT_ROOT / ".github" / "skills").rglob("*.md")


def test_current_documentation_links_resolve():
    failures = []
    for path in active_documents():
        text = path.read_text(encoding="utf-8")
        for value in re.findall(r"\[[^\]\n]+\]\((<[^>\n]+>|[^)\n]+)\)", text):
            target = value.strip("<>")
            if "://" in target or target.startswith("#") or target.startswith("mailto:"):
                continue
            target = unquote(target.split("#", 1)[0])
            if not (path.parent / target).resolve().exists():
                failures.append(f"{path.relative_to(PROJECT_ROOT)} -> {target}")
    assert not failures, "\n".join(failures)


def test_discoverable_skills_have_matching_valid_frontmatter():
    paths = list((PROJECT_ROOT / ".github" / "skills").glob("*/SKILL.md"))
    assert len(paths) == 3
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), path
        frontmatter = yaml.safe_load(text.split("---", 2)[1])
        assert frontmatter["name"] == path.parent.name
        assert isinstance(frontmatter["description"], str)
        assert 10 <= len(frontmatter["description"]) <= 1024
        assert len(text.splitlines()) <= 500


def test_full_workflow_skill_runs_in_chat_and_supports_resume_and_targeted_reruns():
    skill = (PROJECT_ROOT / ".github" / "skills" / "lineage-workflow" / "SKILL.md").read_text(
        encoding="utf-8",
    )
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "current VS Code Copilot Chat agent" in skill
    assert "user-invocable: true" in skill
    assert "Resume by default" in skill
    assert 'steps 1 and 2 are completed; start at step 3' in skill
    assert "accepted_data" in skill and 'inventory(Path(item["path"]))' in skill
    assert "rerun steps 4 through 7" in skill
    assert "Do not stop after context preparation" in skill
    assert "enrichment record" in skill
    assert "pipeline --clone --full-run" not in skill + readme
    assert "enrichment generate" not in skill + readme
