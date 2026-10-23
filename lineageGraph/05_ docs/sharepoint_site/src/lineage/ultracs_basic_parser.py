import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class UltracsBasicProgram:
    name: str = ""
    source: str = ""
    open_files: List[str] = field(default_factory=list)
    read_targets: List[str] = field(default_factory=list)
    write_targets: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    assignments: List[str] = field(default_factory=list)

    def has_statement(self, keyword: str) -> bool:
        return any(keyword.upper() in operation.upper() for operation in self.operations)

    def to_dict(self):
        return {
            "name": self.name,
            "open_files": self.open_files,
            "read_targets": self.read_targets,
            "write_targets": self.write_targets,
            "operations": self.operations,
            "assignments": self.assignments,
        }


def parse_ultracs_record(record: str, separator: str = "|") -> List[str]:
    """Split a pipe-delimited Ultracs record into a list of field values."""
    if record is None:
        return []
    return record.split(separator)


def parse_ultracs_basic(source: str) -> UltracsBasicProgram:
    """Parse the legacy Ultracs BASIC job format used in this repo.

    This is intentionally lightweight but captures the main structure:
    - program name from comment lines
    - file opens
    - SELECT / READNEXT / READ / WRITESEQ operations
    - assignments and variable usage for lineage mapping
    """
    program = UltracsBasicProgram(source=source)
    cleaned_lines: List[str] = []

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("*") and line != "*":
            comment_value = line[1:].strip()
            if not program.name and re.fullmatch(r"[A-Z][A-Z0-9_.-]*", comment_value):
                program.name = comment_value
            continue

        line = re.split(r";\s*\*", line, maxsplit=1)[0].strip()

        if not line:
            continue

        cleaned_lines.append(line)

    for line in cleaned_lines:
        normalized = line.strip()

        open_match = re.search(r"OPEN\s+'([^']+)'\s+TO\s+(\w+)", normalized, flags=re.IGNORECASE)
        if open_match:
            file_name = open_match.group(1).strip()
            target_name = open_match.group(2).strip()
            if file_name not in program.open_files:
                program.open_files.append(file_name)
            program.operations.append(f"OPEN {file_name} TO {target_name}")
            continue

        if re.search(r"\bOPENSEQ\s+.+\s+TO\s+\w+", normalized, flags=re.IGNORECASE):
            program.operations.append(normalized)
            continue

        if re.match(r"SELECT\s+.+", normalized, flags=re.IGNORECASE):
            program.operations.append(normalized)
            continue

        if re.search(r"READNEXT\s+\w+", normalized, flags=re.IGNORECASE):
            program.operations.append(normalized)
            continue

        if re.search(r"\bEXECUTE\b", normalized, flags=re.IGNORECASE):
            program.operations.append(normalized)
            continue

        if re.search(r"\bREAD(?:V)?\s+.*\s+FROM\s+\w+", normalized, flags=re.IGNORECASE):
            program.operations.append(normalized)
            file_target_match = re.search(r"FROM\s+(\w+)", normalized, flags=re.IGNORECASE)
            if file_target_match:
                read_target = file_target_match.group(1)
                if read_target not in program.read_targets:
                    program.read_targets.append(read_target)
            continue

        if re.search(r"WRITESEQ\s+.*\s+ON\s+\w+", normalized, flags=re.IGNORECASE):
            program.operations.append(normalized)
            target_match = re.search(r"ON\s+(\w+)", normalized, flags=re.IGNORECASE)
            if target_match:
                write_target = target_match.group(1)
                if write_target not in program.write_targets:
                    program.write_targets.append(write_target)
            continue

        if re.search(r"WRITE\s+.*\s+ON\s+\w+", normalized, flags=re.IGNORECASE):
            program.operations.append(normalized)
            target_match = re.search(r"ON\s+(\w+)", normalized, flags=re.IGNORECASE)
            if target_match:
                write_target = target_match.group(1)
                if write_target not in program.write_targets:
                    program.write_targets.append(write_target)
            continue

        if re.search(r"\w+\s*=\s*.*", normalized):
            if not normalized.startswith(("IF ", "FOR ", "NEXT ", "END ", "RETURN", "STOP", "GOTO", "GO ", "EXECUTE ", "CALL ")):
                program.assignments.append(normalized)

    if not program.name:
        # fallback: infer from file name if available
        program.name = "UNKNOWN_BASIC_PROGRAM"

    return program


def parse_ultracs_basic_file(file_path: str | Path) -> UltracsBasicProgram:
    path = Path(file_path)
    program = parse_ultracs_basic(path.read_text(encoding="utf-8", errors="ignore"))
    if program.name == "UNKNOWN_BASIC_PROGRAM":
        program.name = path.name
    return program
