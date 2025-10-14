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


def test_determine_stage_priority_quota_cases():
    script = (
        Path(__file__).resolve().parent.parent / "app" / "static" / "stage_priority.js"
    )
    assert script.exists(), "stage_priority.js should exist"
    node_code = """
    const mod = require('./app/static/stage_priority.js');
    const fn = mod.determineStagePriorityQuota;
    const cases = [
      { total: 7, stageF: 5 },
      { total: 7, stageF: 10 },
      { total: 7, stageF: 0 },
      { total: 5, stageF: 2 },
    ];
    const results = cases.map(c => fn(c.total, c.stageF));
    process.stdout.write(JSON.stringify(results));
    """
    output = run_node(node_code)
    assert json.loads(output) == [2, 0, 7, 3]


def test_index_uses_priority_quota():
    html = (
        Path(__file__).resolve().parent.parent / "app" / "static" / "index.html"
    ).read_text(encoding="utf-8")
    assert "determineStagePriorityQuota(n, stageFPool.length)" in html


def test_stage_promotion_helper_respects_due_dates():
    script = (
        Path(__file__).resolve().parent.parent / "app" / "static" / "stage_priority.js"
    )
    assert script.exists(), "stage_priority.js should exist"
    node_code = """
    const mod = require('./app/static/stage_priority.js');
    const fn = mod.shouldPrioritizeStagePromotion;
    const now = Date.UTC(2024, 0, 10, 12, 0, 0);
    const results = [
      fn('E', null, now),
      fn('E', undefined, now),
      fn('E', '2024-01-09T00:00:00Z', now),
      fn('d', new Date(now - 3600000), now),
      fn('B', '2099-01-01T00:00:00Z', now),
      fn('A', new Date(now - 1000), now),
    ];
    process.stdout.write(JSON.stringify(results));
    """
    output = run_node(node_code)
    assert json.loads(output) == [False, False, True, True, False, False]
