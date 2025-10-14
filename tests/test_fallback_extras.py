import json
import subprocess
from pathlib import Path


def run_node(code: str) -> str:
    result = subprocess.run(
        ["node", "-e", code],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    return result.stdout.strip()


def test_append_fallback_extras_limits_shortage():
    script = (
        Path(__file__).resolve().parent.parent / "app" / "static" / "fallback_extras.js"
    )
    assert script.exists(), "fallback_extras.js should exist"
    node_code = """
    const mod = require('./app/static/fallback_extras.js');
    const extras = [];
    const prioritized = ['p1','p2','p3','p4'];
    const others = ['o1','o2'];
    mod.appendFallbackExtras(extras, prioritized, others, 7, 5);
    process.stdout.write(JSON.stringify(extras));
    """
    output = run_node(node_code)
    assert json.loads(output) == ["p1", "p2"]


def test_append_fallback_extras_respects_existing_capacity():
    node_code = """
    const mod = require('./app/static/fallback_extras.js');
    const extras = ['keep'];
    const prioritized = ['p1','p2'];
    const others = ['o1','o2'];
    mod.appendFallbackExtras(extras, prioritized, others, 7, 5);
    process.stdout.write(JSON.stringify(extras));
    """
    output = run_node(node_code)
    assert json.loads(output) == ["keep", "p1"]


def test_append_fallback_extras_handles_no_capacity():
    node_code = """
    const mod = require('./app/static/fallback_extras.js');
    const extras = [];
    mod.appendFallbackExtras(extras, ['p1'], ['o1'], 5, 6);
    process.stdout.write(JSON.stringify(extras));
    """
    output = run_node(node_code)
    assert json.loads(output) == []
