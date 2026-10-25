"""Local source links relative to an explicitly located generated report."""

import os
from pathlib import Path
from urllib.parse import quote


def local_href(target: Path, document: Path) -> str:
    target, document = Path(target).resolve(), Path(document).resolve()
    try:
        return quote(Path(os.path.relpath(target, document.parent)).as_posix(), safe="/._-~")
    except ValueError:
        return target.as_uri()
