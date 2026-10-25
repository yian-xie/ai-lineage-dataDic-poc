import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_repository_skill_frontmatter_and_references():
    skills = ROOT / '.github' / 'skills'
    for name in ('ultracs-data-dictionary-v3', 'ai-description-enrichment'):
        directory = skills / name
        text = (directory / 'SKILL.md').read_text(encoding='utf-8')
        assert text.startswith('---\n')
        frontmatter = yaml.safe_load(text.split('---', 2)[1])
        assert frontmatter['name'] == name
        assert 0 < len(frontmatter['description']) <= 1024
        assert frontmatter['user-invocable'] is True
        assert not list(directory.rglob('*.py'))
        for document in directory.rglob('*.md'):
            body = document.read_text(encoding='utf-8')
            for target in re.findall(r'\]\((\.[^)]+)\)', body):
                assert (document.parent / target).exists(), (document, target)
        assert '03-output' not in text and 'sys.path' not in text
