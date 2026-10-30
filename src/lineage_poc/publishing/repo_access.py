"""Generate a table-level I/O and program-call inventory for Ultracs BASIC files."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, OUTPUT_ROOT, source_root as default_source_root

import re
from pathlib import Path
from .links import local_href

ROOT = REPOSITORY_ROOT
REPO = default_source_root() / "kb-ultracs-datawarehouse"
OUTPUT = OUTPUT_ROOT / "lineage" / "table_level_reads_writes.md"
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
READ_PATTERN = re.compile(r"\b(READSEQ|READV?|READ)\b.*?\bFROM\s+([A-Z][A-Z0-9_.]*)", re.IGNORECASE)
WRITE_PATTERN = re.compile(r"\b(WRITESEQ|WRITEV|WRITE)\b.*?\b(ON|TO)\s+([A-Z][A-Z0-9_.]*)", re.IGNORECASE)
SELECT_PATTERN = re.compile(r"\bSELECT\s+([A-Z][A-Z0-9_.]*)", re.IGNORECASE)
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
    for raw_line in text.splitlines():
        cleaned = strip_comment(raw_line)
        if cleaned:
            statements.extend(split_statements(cleaned))
    return statements


def quote_parts(expression: str) -> list[str]:
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


def resource_from_open(operation: str, expression: str) -> str:
    parts = quote_parts(expression)
    operation = operation.upper()
    if operation == "OPEN":
        return parts[0] if parts else f"DYNAMIC({expression.strip()})"
    if len(parts) >= 2:
        resource = f"{parts[0]}/{parts[1]}"
        last_quote = max(expression.rfind("'"), expression.rfind('"'))
        suffix = expression[last_quote + 1 :].strip()
        if suffix.startswith(":"):
            resource += "{" + suffix[1:].strip() + "}"
        return resource
    if parts:
        return parts[0]
    return f"DYNAMIC({expression.strip()})"


def display_resource(resource: str, operation: str) -> str:
    return f"{resource} [{operation}]"


def resolve_handle(handle: str, aliases: dict[str, str]) -> str:
    return aliases.get(handle.upper(), handle)


def keyed_output_resource(resource: str, statement: str, marker_end: int, operation: str) -> str:
    if not resource.upper().startswith("KBDOSOUTPUT") or operation.upper() not in {"WRITE", "WRITEV", "READ", "READV"}:
        return resource
    tail = re.split(r"\bELSE\b", statement[marker_end:], maxsplit=1, flags=re.IGNORECASE)[0].lstrip()
    if not tail.startswith(","):
        return resource
    key = first_argument(tail[1:]).strip()
    if not key:
        return resource
    return f"{resource} (record {key})"


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
        if len([s for s in statements if STATEMENT_PATTERN.search(s)]) < 5:
            continue
        if not PROGRAM_IO_PATTERN.search(text):
            continue
        programs.append((path, text))
    return programs


def analyze_program(path: Path, text: str, known_programs: set[str]) -> tuple[list[str], list[str], list[str], list[str]]:
    statements = source_statements(text)
    aliases: dict[str, str] = {}
    opens: list[str] = []
    reads: list[str] = []
    writes: list[str] = []
    calls: list[str] = []
    selected_resource = None

    for statement in statements:
        masked = mask_quoted_text(statement)
        open_match = OPEN_PATTERN.search(masked)
        if not open_match:
            continue
        open_match = OPEN_PATTERN.search(statement, open_match.start())
        if not open_match:
            continue
        operation, expression, handle = open_match.groups()
        resource = resource_from_open(operation, expression)
        aliases[handle.upper()] = resource
        opens.append(display_resource(resource, operation.upper()))

    for statement in statements:
        masked = mask_quoted_text(statement)
        open_match = OPEN_PATTERN.search(masked)
        if open_match:
            continue

        select_match = SELECT_PATTERN.search(masked)
        if select_match:
            selected_resource = resolve_handle(select_match.group(1), aliases)
            reads.append(selected_resource)
            continue

        if re.search(r"\bREADNEXT\b", masked, re.IGNORECASE):
            if selected_resource:
                reads.append(selected_resource)
            continue

        read_match = READ_PATTERN.search(masked)
        if read_match:
            operation, handle = read_match.groups()
            resource = resolve_handle(handle, aliases)
            marker = re.search(r"\bFROM\s+" + re.escape(handle) + r"\b", masked, re.IGNORECASE)
            if marker:
                resource = keyed_output_resource(resource, statement, marker.end(), operation)
            reads.append(resource)
            continue

        write_match = WRITE_PATTERN.search(masked)
        if write_match:
            operation, _, handle = write_match.groups()
            resource = resolve_handle(handle, aliases)
            marker = re.search(r"\b(?:ON|TO)\s+" + re.escape(handle) + r"\b", masked, re.IGNORECASE)
            if marker:
                resource = keyed_output_resource(resource, statement, marker.end(), operation)
            writes.append(resource)
            continue

        call_start = re.search(r"\b(?:EXECUTE|PERFORM)\b", masked, re.IGNORECASE)
        call_match = CALL_PATTERN.search(statement, call_start.start()) if call_start else None
        if call_match:
            _, double, single, bare = call_match.groups()
            command = (double or single or bare or "").strip()
            phantom = re.match(r"PHANTOM\s+(.+)$", command, re.IGNORECASE)
            if phantom:
                command = phantom.group(1).strip()
            run_sbp = re.match(r"RUN\s+SBP\s+([A-Z0-9_.-]+)", command, re.IGNORECASE)
            if run_sbp:
                target = run_sbp.group(1)
                suffix = "" if target.casefold() in known_programs else " (not present in repository inventory)"
                calls.append(target + suffix)
                continue
            target = command.split()[0] if command else ""
            if target.casefold() in known_programs:
                calls.append(target)

    return list(dict.fromkeys(opens)), list(dict.fromkeys(reads)), list(dict.fromkeys(writes)), list(dict.fromkeys(calls))


def cell(values: list[str]) -> str:
    if not values:
        return "-"
    return "; ".join(value.replace("|", "\\|") for value in values)


def generate_report(source_root: Path | None = None, document: Path = OUTPUT) -> str:
    programs = discover_programs(source_root=source_root)
    known = {path.name.casefold() for path, _ in programs}
    rows = []
    for path, text in programs:
        opens, reads, writes, calls = analyze_program(path, text, known)
        source = f"[{path.name}]({local_href(path, document)})"
        rows.append(f"| {source} | {cell(opens)} | {cell(reads)} | {cell(writes)} | {cell(calls)} |")

    content = [
        "# Ultracs BASIC File Access and Program Dependencies",
        "",
        f"This inventory contains **{len(programs)} BASIC/BASIC-like files** identified by the same content-signature rule as [repo_profile_ultracs.md](repo_profile_ultracs.md): at least five active BASIC statements and at least one file I/O, selection, or execution statement, excluding `.git` and known non-program fixture/config formats.",
        "",
        "Repository items are mostly extensionless; the first column links to the actual repository item name (not a `.b` suffix). Each row is one source program.",
        "",
        "- `opens` lists literal files and sequential output resources from `OPEN` and `OPENSEQ`; dynamic expressions are shown as `DYNAMIC(...)`.",
        "- `reads_from` includes explicit `READ`, `READV`, `READSEQ`, and the file selected by `SELECT`/`READNEXT`.",
        "- `writes_to` includes explicit `WRITE`, `WRITEV`, `WRITESEQ` targets. Writes to `KBDOSOUTPUT*` with a literal/dynamic record id include that record id.",
        "- `calls_program` includes `EXECUTE`/`PERFORM` targets matching a BASIC file in this inventory, plus `RUN SBP` targets; shell/TCL/list commands are not listed as program calls.",
        "- This is lexical source inventory. Dynamic file names or commands are preserved as expressions; no runtime values are inferred.",
        "",
        "| source_program | opens | reads_from | writes_to | calls_program |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ]
    return "\n".join(content)


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generate_report(), encoding="utf-8")
    print(f"Generated {OUTPUT}")
