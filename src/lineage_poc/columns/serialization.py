"""Legacy column-inventory bytes consumed by SHA-bound dictionaries and AI context."""

import json
from pathlib import Path
from typing import Any


def write_inventory(path: Path, value: Any) -> None:
    """Retain ASCII escaping, insertion order, indentation and native newlines."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
