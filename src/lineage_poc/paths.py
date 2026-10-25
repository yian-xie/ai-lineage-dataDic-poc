"""Shared locations for source checkouts, required test fixtures, and step outputs."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "reference"
REFERENCE_LINEAGE = REFERENCE_ROOT / "lineage"
REFERENCE_DICTIONARY = REFERENCE_ROOT / "dictionary"
INPUT_ROOT = REFERENCE_ROOT / "inputs"
OUTPUT_ROOT = PROJECT_ROOT / "output"
SKILL_ROOT = PROJECT_ROOT / ".github" / "skills"


def source_root() -> Path:
    configured = os.environ.get("LINEAGE_SOURCE_ROOT")
    return Path(configured).expanduser().resolve() if configured else PROJECT_ROOT.parent / "source-repos"
