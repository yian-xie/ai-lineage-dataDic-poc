"""Inventory output extract files written by Ultracs BASIC programs."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, OUTPUT_ROOT, source_root as default_source_root

import re
from collections import defaultdict
from pathlib import Path
from .links import local_href

ROOT = REPOSITORY_ROOT
REPO = default_source_root() / "kb-ultracs-datawarehouse"
OUTPUT = OUTPUT_ROOT / "lineage" / "extract_file_inventory.md"
EXCLUDED_SUFFIXES = {
    ".sample", ".pack", ".rev", ".idx", ".yml", ".yaml", ".md", ".xml",
    ".py", ".ps1", ".xlsx", ".xls", ".param", ".json",
}
STATEMENT_PATTERN = re.compile(
    r"^\s*(?:\d+\s*:\s*)?(?:OPEN|OPENSEQ|SELECT|READNEXT|READV?|WRITESEQ|WRITE|WRITEV|"
    r"EXECUTE|PERFORM|CALL|DISPLAY|IF|FOR|GOSUB|RETURN|STOP|GO|CONVERT|DELETE|"
    r"CLOSESEQ|READSEQ)\b",
    re.IGNORECASE,
)
PROGRAM_IO_PATTERN = re.compile(
    r"^\s*(?:\d+\s*:\s*)?(?:OPEN|OPENSEQ|SELECT|READNEXT|READV?|WRITESEQ|EXECUTE|PERFORM|CALL)\b",
    re.IGNORECASE | re.MULTILINE,
)
OPEN_PATTERN = re.compile(r"\b(OPENSEQ|OPEN)\s+(.+?)\s+TO\s+([A-Z][A-Z0-9_.]*)\b", re.IGNORECASE)
WRITE_PATTERN = re.compile(r"\b(WRITESEQ|WRITEV|WRITE)\b", re.IGNORECASE)
CALL_PATTERN = re.compile(r"\b(EXECUTE|PERFORM)\s+(?:\"([^\"]*)\"|'([^']*)'|([A-Z][A-Z0-9_.-]*))", re.IGNORECASE)
QUOTED_PATTERN = re.compile(r"'([^']*)'|\"([^\"]*)\"")


def mask_quoted_text(text: str) -> str:
    chars = list(text)
    quote = None
    for index, char in enumerate(chars):
        if quote is None and char in ("'", '"'):
            quote = char
            chars[index] = " "
        elif quote is not None:
            if char == quote:
                quote = None
            chars[index] = " "
    return "".join(chars)


def strip_comment(line: str) -> str:
    if line.lstrip().startswith("*"):
        return ""
    return re.split(r";\s*\*", line, maxsplit=1)[0].strip()


def split_statements(line: str) -> list[str]:
    statements = []
    current = []
    quote = None
    for char in line:
        if char in ("'", '"'):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        if char == ";" and quote is None:
            statements.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        statements.append("".join(current).strip())
    return [statement for statement in statements if statement]


def source_statements(text: str) -> list[str]:
    statements = []
    for line in text.splitlines():
        cleaned = strip_comment(line)
        if cleaned:
            statements.extend(split_statements(cleaned))
    return statements


def quoted_values(expression: str) -> list[str]:
    return [single if single else double for single, double in QUOTED_PATTERN.findall(expression)]


def first_argument(expression: str) -> str:
    quote = None
    for index, char in enumerate(expression):
        if char in ("'", '"'):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        elif char == "," and quote is None:
            return expression[:index].strip()
    return expression.strip()


def open_resource(operation: str, expression: str) -> str:
    values = quoted_values(expression)
    if operation.upper() == "OPEN":
        return values[0] if values else f"DYNAMIC({expression.strip()})"
    if len(values) >= 2:
        resource = f"{values[0]}/{values[1]}"
        last_quote = max(expression.rfind("'"), expression.rfind('"'))
        suffix = expression[last_quote + 1 :].strip()
        if suffix.startswith(":"):
            resource += "{" + suffix[1:].strip() + "}"
        return resource
    if values:
        return values[0]
    return f"DYNAMIC({expression.strip()})"


def file_record_id(tail: str) -> str:
    tail = re.split(r"\bELSE\b", tail, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if not tail.startswith(","):
        return ""
    return first_argument(tail[1:]).strip()


def explicit_path_expression(record_id: str) -> str:
    values = quoted_values(record_id)
    if len(values) >= 2:
        return f"{values[0]}/{values[1]}"
    if values:
        suffix = record_id[record_id.rfind(values[0]) + len(values[0]) + 1 :].strip()
        if suffix.startswith(":"):
            return values[0] + "{" + suffix[1:].strip() + "}"
        return values[0]
    return f"DYNAMIC({record_id})" if record_id else ""


def format_for_program(text: str, writer_statements: list[str]) -> tuple[str, str]:
    statements = source_statements(text)
    code = "\n".join(statements)
    separator_assignments = re.findall(
        r"\b(SEP|PIPE|DELIM|SEPARATOR)\s*=\s*(['\"])(.*?)\2",
        code,
        re.IGNORECASE,
    )
    separator_by_name = {name.upper(): value for name, _, value in separator_assignments}

    payload_vars = set()
    for statement in writer_statements:
        masked = mask_quoted_text(statement)
        match = WRITE_PATTERN.search(masked)
        if not match:
            continue
        payload = masked[match.end() :].strip()
        payload = re.split(r"\b(?:ON|TO)\b", payload, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        variable = re.match(r"([A-Z][A-Z0-9_.]*)\b", payload, re.IGNORECASE)
        if variable:
            payload_vars.add(variable.group(1).upper())

    payload_assignments = []
    for variable in payload_vars:
        payload_assignments.extend(
            statement
            for statement in statements
            if re.match(r"\s*" + re.escape(variable) + r"\s*=", mask_quoted_text(statement), re.IGNORECASE)
        )

    for statement in payload_assignments:
        for sep_name, sep_value in separator_by_name.items():
            if sep_value and re.search(r":" + re.escape(sep_name) + r"\b", mask_quoted_text(statement), re.IGNORECASE):
                if sep_value == "|":
                    return "Pipe-delimited", f"{sep_name} is assigned '|'; this written payload uses :{sep_name}:"
                if sep_value == ",":
                    return "Comma-delimited", f"{sep_name} is assigned ',' and this written payload uses :{sep_name}:"
                if sep_value in {"\\t", "\t"}:
                    return "Tab-delimited", f"{sep_name} is assigned a tab and this written payload uses :{sep_name}:"

    if any(re.search(r"\b(?:FIELD_DELIM|FILE_DELIM|PIPE)\s*=\s*['\"]\|['\"]", statement, re.IGNORECASE) for statement in payload_assignments):
        return "Pipe-delimited", "pipe delimiter assignment is present in the written payload construction"

    width_hint = any(re.search(r"\b(?:L#|R#)\s*\d+|\[\s*\d+\s*,\s*\d+\s*\]", statement, re.IGNORECASE) for statement in payload_assignments)
    if width_hint:
        return "Fixed-width candidate", "fixed-width substring/formatting syntax is present in the written payload"

    return "Other / format not determined", "no delimiter or fixed-width evidence tied to this output"


def discover_programs(source_root: Path | None = None) -> list[tuple[Path, str]]:
    repo = Path(source_root) / "kb-ultracs-datawarehouse" if source_root is not None else REPO
    programs = []
    for path in sorted(repo.rglob("*")):
        if not path.is_file() or ".git" in path.relative_to(repo).parts:
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        statements = source_statements(text)
        active = [statement for statement in statements if STATEMENT_PATTERN.search(statement)]
        if len(active) >= 5 and PROGRAM_IO_PATTERN.search(text):
            programs.append((path, text))
    return programs


def output_inventory(path: Path, text: str) -> list[tuple[str, str, str]]:
    statements = source_statements(text)
    aliases: dict[str, tuple[str, str]] = {}
    outputs: dict[str, dict] = {}
    selected_file = None

    def add_output(resource: str, writer: str, statement: str) -> None:
        entry = outputs.setdefault(resource, {"writers": set(), "evidence": []})
        entry["writers"].add(writer)
        if statement not in entry["evidence"]:
            entry["evidence"].append(statement)

    for statement in statements:
        masked = mask_quoted_text(statement)
        match = OPEN_PATTERN.search(masked)
        if not match:
            continue
        original_match = OPEN_PATTERN.search(statement, match.start())
        if not original_match:
            continue
        operation, expression, handle = original_match.groups()
        resource = open_resource(operation, expression)
        aliases[handle.upper()] = (resource, operation.upper())

    for statement in statements:
        masked = mask_quoted_text(statement)
        if re.search(r"\bSELECT\s+", masked, re.IGNORECASE):
            match = re.search(r"\bSELECT\s+([A-Z][A-Z0-9_.]*)", masked, re.IGNORECASE)
            if match:
                selected_file = aliases.get(match.group(1).upper(), (match.group(1), "OPEN"))[0]

        match = WRITE_PATTERN.search(masked)
        if match:
            operation = match.group(1).upper()
            target_match = re.search(r"\b(?:ON|TO)\s+([A-Z][A-Z0-9_.]*)", masked[match.end():], re.IGNORECASE)
            if not target_match:
                continue
            handle = target_match.group(1)
            target_start = match.end() + target_match.start()
            target_end = match.end() + target_match.end()
            resource, open_operation = aliases.get(handle.upper(), (handle, ""))
            tail = file_record_id(statement[target_end:])

            if handle.upper().startswith("KBDOSOUTPUT"):
                if tail:
                    output_file = explicit_path_expression(tail)
                    add_output(f"{handle}/{output_file}", operation, statement)
                elif open_operation == "OPENSEQ":
                    add_output(resource, operation, statement)
                continue

            if open_operation == "OPENSEQ":
                add_output(resource, operation, statement)
                continue

        if re.search(r"\bREADNEXT\b", masked, re.IGNORECASE) and selected_file:
            continue

    writer_statements_by_output: dict[str, list[str]] = defaultdict(list)
    for output, details in outputs.items():
        writer_statements_by_output[output].extend(details["evidence"])

    if not outputs:
        return []

    result = []
    for output, details in sorted(outputs.items(), key=lambda item: item[0].casefold()):
        source_writers = details["evidence"]
        format_name, format_evidence = format_for_program(text, source_writers)
        row_format = f"{format_name} ({format_evidence})"
        result.append((output, row_format, "; ".join(sorted(details["writers"]))))
    return result


def generate_report(source_root: Path | None = None, document: Path = OUTPUT) -> str:
    programs = discover_programs(source_root=source_root)
    rows = []
    for path, text in programs:
        source = f"[{path.name}]({local_href(path, document)})"
        for output_path, format_name, writers in output_inventory(path, text):
            rows.append(
                f"| {source} | {output_path.replace('|', '\\|')} | {format_name.replace('|', '\\|')} | {writers.replace('|', '\\|')} |"
            )

    return "\n".join([
        "# Ultracs BASIC Extract File Inventory",
        "",
        f"Scanned **{len(programs)} BASIC/BASIC-like programs** using the content-signature rule documented in [repo_profile_ultracs.md](repo_profile_ultracs.md). This table lists detected output files written through `KBDOSOUTPUT*` or sequential paths opened with `OPENSEQ`; ordinary writes to MultiValue business files are excluded.",
        "",
        "Format is reported as pipe-delimited only when source shows a pipe separator used in output-record assembly. Fixed-width is a candidate only where width-formatting syntax is found; otherwise the format is marked not determined. Dynamic path expressions are preserved as written.",
        "",
        "| source_program | output_file_or_path | format | write_form |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ])


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generate_report(), encoding="utf-8")
    print(f"Generated {OUTPUT}")
