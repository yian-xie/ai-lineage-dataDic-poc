"""Independently runnable dictionary CSV generation; never builds HTML."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from .generate import _generate, require
from .io import CSV_FILES


def generate_bundle(input_path: Path, output_dir: Path, graph_id: str | None = None) -> dict:
    input_path, output_dir = Path(input_path), Path(output_dir)
    require(input_path.resolve() not in {output_dir.resolve() / name for name in CSV_FILES},
            'CSV output must not replace its input JSON file')
    graph_id = input_path.stem if graph_id is None else graph_id
    require(isinstance(graph_id, str) and bool(graph_id.strip()), 'graph_id must not be empty')
    return _generate(SimpleNamespace(input=input_path, output=output_dir), graph_id)


if __name__ == '__main__':
    from .generate import main
    main()
