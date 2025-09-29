import json
import re
import subprocess
from pathlib import Path


def run_node(script: str) -> str:
    res = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    )
    return res.stdout.strip()


def test_full_width_digits_are_normalized():
    index = Path("app/static/index.html").read_text(encoding="utf-8").splitlines()
    lines = {}
    for line in index:
        s = line.strip()
        if s.startswith("const NBSP"):
            lines["NBSP"] = s
        elif s.startswith("const normalizeDigits"):
            lines["normalizeDigits"] = s
        elif s.startswith("const normalizeSpaces"):
            lines["normalizeSpaces"] = s
        elif s.startswith("const normalizeEndPunc"):
            lines["normalizeEndPunc"] = s
        elif s.startswith("const normalizeWord"):
            lines["normalizeWord"] = s

    script = f"""
{lines['NBSP']}
{lines['normalizeDigits']}
{lines['normalizeSpaces']}
{lines['normalizeEndPunc']}
{lines['normalizeWord']}
function gradeReorder(ans, right, keep) {{
  const normalizedAns = normalizeEndPunc(normalizeSpaces(ans), keep);
  const normalizedAnswers = [normalizeEndPunc(normalizeSpaces(right), keep)];
  const normalizedAnsLower = typeof normalizedAns === 'string' ? normalizedAns.toLowerCase() : normalizedAns;
  const normalizedAnswersLower = normalizedAnswers.map(a=>typeof a === 'string' ? a.toLowerCase() : a);
  return normalizedAnswersLower.includes(normalizedAnsLower);
}}
function gradeVocab(ans, right) {{
  const normalizedAns = normalizeWord(ans);
  const normalizedAnswers = [normalizeWord(right)];
  return normalizedAnswers.includes(normalizedAns);
}}
console.log(JSON.stringify([
  gradeReorder('１２３', '123', true),
  gradeReorder('123', '１２３', true),
  gradeVocab('１２３', '123'),
  gradeVocab('123', '１２３')
]));
"""

    out = run_node(script)
    result = json.loads(out)
    assert result == [True, True, True, True]


def extract_function(source: str, name: str) -> str:
    pattern = rf"function {name}\([^)]*\)\s*\{{[\s\S]*?\}}"
    match = re.search(pattern, source)
    if not match:
        raise AssertionError(f"Function {name} not found")
    return match.group(0)


def test_math_mode_full_width_digits_are_normalized():
    math_html = Path("app/static/math.html").read_text(encoding="utf-8")
    normalize_digits_line = None
    for line in math_html.splitlines():
        stripped = line.strip()
        if stripped.startswith("const normalizeDigits"):
            normalize_digits_line = stripped
            break
    assert normalize_digits_line is not None

    normalize_fn = extract_function(math_html, "normalize")
    compare_scalar_fn = extract_function(math_html, "compareScalar")

    script = f"""
{normalize_digits_line}
{normalize_fn}
{compare_scalar_fn}
console.log(JSON.stringify([
  compareScalar('123', '１２３'),
  compareScalar('１２３', '123'),
  normalize('１２３')
]));
"""

    out = run_node(script)
    result = json.loads(out)
    assert result == [True, True, "123"]
