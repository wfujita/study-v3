import json
import subprocess
from pathlib import Path


def run_node(script: str) -> str:
    res = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    )
    return res.stdout.strip()


def test_reorder_punctuation_judgement():
    index = Path("app/static/index.html").read_text(encoding="utf-8").splitlines()
    lines = {}
    for line in index:
        s = line.strip()
        if s.startswith("const NBSP"):  # NBSP constant
            lines["NBSP"] = s
        elif s.startswith("const normalizeSpaces"):
            lines["normalizeSpaces"] = s
        elif s.startswith("const normalizeEndPunc"):
            lines["normalizeEndPunc"] = s
    script = f"""
{lines['NBSP']}
{lines['normalizeSpaces']}
{lines['normalizeEndPunc']}
function grade(ans, right, keep) {{
  ans = normalizeEndPunc(normalizeSpaces(ans), keep);
  ans = ans? ans.charAt(0).toUpperCase()+ans.slice(1) : ans;
  right = normalizeEndPunc(normalizeSpaces(right), keep);
  return ans === right;
}}
console.log(JSON.stringify([
  grade('Hello world', 'Hello world.', true),
  grade('Hello world.', 'Hello world.', true),
  grade('Hello world .', 'Hello world.', true),
  grade('Hello world', 'Hello world.', false)
]));
"""
    out = run_node(script)
    result = json.loads(out)
    assert result == [False, True, True, True]
