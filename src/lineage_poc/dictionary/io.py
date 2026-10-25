"""Strict CSV/JSON IO and destination-local, rollback-safe file replacement."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import stat
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .legacy_projection import js, reject_nonfinite, unique_object

CSV_FILES = ('asset_registry.csv', 'field_catalog.csv', 'data_dictionary.csv')
ID_COLUMNS = dict(zip(CSV_FILES, ('asset_id', 'field_id', 'dictionary_entry_id')))
CELL_LIMIT = 32767


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_json(value: str):
    def finite_number(token):
        number = float(token)
        require(math.isfinite(number), 'Nonfinite JSON number cannot be preserved: ' + token)
        return number
    return json.loads(value, object_pairs_hook=unique_object, parse_constant=reject_nonfinite,
                      parse_float=finite_number)


def equal(left, right) -> bool:
    return js(left) == js(right)


def pointer(value, path: str):
    require(isinstance(path, str) and (not path or path.startswith('/')),
            'Invalid JSON pointer: ' + repr(path))
    for token in path.split('/')[1:]:
        require(not re.search(r'~(?![01])', token), 'Invalid JSON pointer escape: ' + path)
        token = token.replace('~1', '/').replace('~0', '~')
        try:
            if isinstance(value, list):
                require(bool(re.fullmatch(r'0|[1-9]\d*', token)), 'Invalid JSON array index: ' + path)
                value = value[int(token)]
            else:
                require(isinstance(value, dict), 'JSON pointer traverses a scalar: ' + path)
                value = value[token]
        except (KeyError, IndexError) as error:
            raise ValueError('JSON pointer does not resolve: ' + path) from error
    return value


def scoped(row, identity):
    return row['graph_id'], row['snapshot_id'], row[identity]


def _check_quotes(text: str, filename: str):
    state, index = 'start', 0
    while index < len(text):
        char = text[index]
        if state == 'quoted':
            if char == '"':
                if index + 1 < len(text) and text[index + 1] == '"':
                    index += 1
                else:
                    state = 'closed'
        elif char in ',\r\n':
            state = 'start'
        elif char == '"':
            require(state == 'start', filename + ': unexpected CSV quote')
            state = 'quoted'
        else:
            require(state != 'closed', filename + ': text after a closing CSV quote')
            state = 'plain'
        index += 1
    require(state != 'quoted', filename + ': unclosed CSV quote')


@dataclass
class Table:
    name: str
    headers: list[str]
    rows: list[dict[str, str]]
    json_rows: list[dict] = field(default_factory=list)
    sha256: str = ''
    maximum_cell_characters: int = 0

    def index(self):
        identity = ID_COLUMNS[self.name]
        return {scoped(row, identity): (row, values)
                for row, values in zip(self.rows, self.json_rows)}


def read_table(path: Path) -> Table:
    blob = path.read_bytes()
    text = blob.decode('utf-8-sig')
    _check_quotes(text, path.name)
    try:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        headers = next(reader)
        require(headers and all(header.strip() for header in headers),
                path.name + ': empty CSV header')
        require(len(headers) == len(set(headers)), path.name + ': duplicate CSV headers')
        rows, parsed, maximum = [], [], 0
        for number, cells in enumerate(reader, 2):
            require(len(cells) == len(headers), f'{path.name} record {number}: header/cell width mismatch')
            maximum = max(maximum, *(len(value) for value in cells))
            require(maximum <= CELL_LIMIT,
                    f'{path.name} record {number}: decoded cell exceeds Excel {CELL_LIMIT}-character limit; no truncation is supported')
            row = dict(zip(headers, cells))
            values = {}
            for column, value in row.items():
                if column.endswith('_json') or column == 'process_relationship_ids':
                    try:
                        # Original registry contracts serialize absent optional JSON
                        # values as blank cells. Newly added assessments require null.
                        legacy_blank = (value == '' and path.name != 'data_dictionary.csv'
                                        and column != 'description_confidence_json')
                        values[column] = None if legacy_blank else parse_json(value)
                    except (ValueError, TypeError) as error:
                        raise ValueError(f'{path.name} record {number}: invalid JSON in {column}: {error}') from error
            rows.append(row)
            parsed.append(values)
    except (StopIteration, csv.Error) as error:
        raise ValueError(path.name + ': invalid or empty CSV: ' + str(error)) from error
    require(rows, path.name + ': no data records')
    return Table(path.name, headers, rows, parsed, hashlib.sha256(blob).hexdigest(), maximum)


def read_tables(directory: Path):
    return {name: read_table(directory / name) for name in CSV_FILES}


def write_table(path: Path, headers: list[str], rows: list[dict[str, str]]):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator='\r\n')
        writer.writeheader()
        for row in rows:
            require(set(row) == set(headers), path.name + ': row/header columns disagree')
            writer.writerow(row)


@contextmanager
def staging_directory(destination: Path, prefix: str):
    destination.mkdir(parents=True, exist_ok=True)
    require(not destination.is_symlink(), 'Output directory must not be a symlink')
    staging = destination / ('.' + prefix + '-' + uuid.uuid4().hex)
    staging.mkdir()
    try:
        yield staging
    finally:
        remove_tree(staging)


def remove_tree(directory: Path):
    """Allow short-lived Windows indexing handles to release our own files."""
    def writable(function, path, error):
        if not isinstance(error[1], PermissionError):
            raise error[1]
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        function(path)

    for attempt in range(8):
        try:
            if directory.exists():
                shutil.rmtree(directory, onerror=writable)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05 * (attempt + 1))


def commit_outputs(staged: Path, destination: Path, filenames):
    """Replace only named files; retain the previous bundle if replacement fails."""
    backup = destination / ('.backup-' + uuid.uuid4().hex)
    backup.mkdir()
    keep_backup = False
    try:
        previous, replaced = {}, []
        for name in filenames:
            target = destination / name
            require(not target.is_symlink() and (not target.exists() or target.is_file()),
                    'Output target must be a regular file: ' + str(target))
            previous[name] = target.exists()
            if previous[name]:
                shutil.copy2(target, backup / name)
        try:
            for name in filenames:
                (staged / name).replace(destination / name)
                replaced.append(name)
        except BaseException as error:
            failures = []
            for name in reversed(replaced):
                try:
                    if previous[name]:
                        shutil.copy2(backup / name, staged / name)
                        (staged / name).replace(destination / name)
                    else:
                        (destination / name).unlink(missing_ok=True)
                except OSError as recovery_error:
                    failures.append(str(recovery_error))
            if failures:
                keep_backup = True
                raise OSError('Output restoration was interrupted; previous files are retained at '
                              + str(backup) + '. ' + '; '.join(failures)) from error
            raise
    finally:
        if not keep_backup:
            remove_tree(backup)


def atomic_write(path: Path, contents: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.is_symlink() and (not path.exists() or path.is_file()),
            'Output target must be a regular file: ' + str(path))
    staging = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        with staging.open('xb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)
