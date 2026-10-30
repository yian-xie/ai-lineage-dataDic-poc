"""Dictionary fixtures stay in the checkout, never the OS temporary directory."""
import json
import uuid
from pathlib import Path

import pytest

from lineage_poc.dictionary.io import remove_tree
from lineage_poc.dictionary.workflow import generate_bundle

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / '.github' / 'skills' / 'ai-description-enrichment' / 'references'


@pytest.fixture
def work():
    path = ROOT / 'tests' / 'dictionary' / ('.work-' + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        remove_tree(path)


@pytest.fixture(scope='session')
def small_bundle():
    path = ROOT / 'tests' / 'dictionary' / ('.fixture-' + uuid.uuid4().hex)
    try:
        generate_bundle(EXAMPLES / 'sample-input.json', path)
        yield path
    finally:
        remove_tree(path)


@pytest.fixture
def drafts():
    return json.loads((EXAMPLES / 'drafts.example.json').read_bytes())


@pytest.fixture
def needs_drafts():
    return json.loads((EXAMPLES / 'drafts-needs-evidence.example.json').read_bytes())


@pytest.fixture(scope='session')
def reference():
    return ROOT / 'tests' / 'fixtures' / 'reference' / 'dictionary'
