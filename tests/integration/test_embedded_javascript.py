"""Validate the final report's real JavaScript without browser-control privileges."""

import importlib.util
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from lineage_poc.execution import sha256_file, write_json
from lineage_poc.paths import OUTPUT_ROOT


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []
        self.current = None

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag == "script" and not values.get("src") and values.get("type", "") in {
            "", "text/javascript", "application/javascript",
        }:
            self.current = {"name": values.get("id", "inline"), "code": ""}

    def handle_data(self, value):
        if self.current is not None:
            self.current["code"] += value

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.entries.append(self.current)
            self.current = None


def node_runtime():
    available = shutil.which("node")
    if available:
        return Path(available)
    specification = importlib.util.find_spec("playwright")
    if specification and specification.origin:
        candidate = Path(specification.origin).parent / "driver" / "node.exe"
        if candidate.is_file():
            return candidate
    return None


def test_final_report_scripts_compile_and_include_real_payloads():
    node = node_runtime()
    if node is None:
        pytest.skip("JavaScript syntax validation requires Node or the optional browser extra.")
    path = OUTPUT_ROOT / "08-html" / "index.html"
    if not path.is_file():
        pytest.skip("Build the final HTML before checking its embedded scripts.")
    html = path.read_text(encoding="utf-8")
    match = re.search(
        r'<script[^>]*id="embedded-dictionary-document"[^>]*>(.*?)</script>',
        html, re.S,
    )
    assert match, "The final report must embed the dictionary, not reference another HTML."
    dictionary = json.loads(match[1])
    scripts = []
    for prefix, document in (("graph", html), ("dictionary", dictionary)):
        parsed = Scripts()
        parsed.feed(document)
        scripts.extend({"name": prefix + "/" + item["name"], "code": item["code"]}
                       for item in parsed.entries)
    assert len(scripts) >= 6
    for marker in ("__TABLE_DATA__", "__COLUMN_DATA__", "__ENTERPRISE_DATA__"):
        assert marker not in html
    program = """
const vm=require('vm'),fs=require('fs');
const scripts=JSON.parse(fs.readFileSync(0,'utf8'));
for(const item of scripts){
  try { new vm.Script(item.code,{filename:item.name}); }
  catch(error){
    console.error(JSON.stringify({status:'failed',file:item.name,error:error.message}));
    process.exit(1);
  }
}
console.log(JSON.stringify({status:'passed',scripts:scripts.length}));
"""
    result = subprocess.run(
        [str(node), "-e", program], input=json.dumps(scripts), text=True,
        encoding="utf-8", capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    write_json(OUTPUT_ROOT / "logs" / "javascript-checks.json", {
        **summary, "html": str(path), "html_sha256": sha256_file(path),
        "scope": "actual graph and embedded dictionary script syntax; not an interactive UI check",
    })
