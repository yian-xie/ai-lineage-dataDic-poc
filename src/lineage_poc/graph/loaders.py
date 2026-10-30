from pathlib import Path
from typing import List


def read_text_lines(file_path: str | Path) -> List[str]:
    """Read a text file and return the raw lines as a list."""
    return Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()


def parse_pipe_delimited_line(line: str) -> List[str]:
    """Split a pipe-delimited record. This is intentionally simple and suited to a POC."""
    return line.split("|")
