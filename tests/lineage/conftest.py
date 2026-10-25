"""Four-repository integration checks; only tenant landing is optional."""

import pytest

from lineage_poc.parsers.snapshot import REQUIRED_REPOSITORIES
from lineage_poc.paths import source_root


@pytest.fixture(scope="session", autouse=True)
def required_repositories():
    root = source_root()
    missing = [name for name in REQUIRED_REPOSITORIES if not (root / name).is_dir()]
    if missing:
        pytest.fail(f"Required lineage integration repositories are missing at {root}: {', '.join(missing)}")
    return root
