import json
import importlib
import sys


def test_math_accuracy_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    sys.modules.pop("app.app", None)
    mod = importlib.import_module("app.app")
    client = mod.app.test_client()

    math_dir = tmp_path / "math"
    math_dir.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "user": "alice",
            "mode": "math-drill",
            "answered": [
                {"id": "m1", "prompt": "1+1", "correct": True},
                {"id": "m2", "prompt": "5-2", "correct": False},
            ],
        },
        {
            "user": "bob",
            "mode": "math-drill",
            "answered": [
                {"id": "m1", "prompt": "1+1", "correct": False},
                {"id": "m3", "prompt": "3×3", "correct": True},
            ],
        },
        {
            "user": "alice",
            "mode": "review",
            "answered": [
                {"id": "m1", "prompt": "1+1", "correct": False},
            ],
        },
    ]

    with open(math_dir / "results.ndjson", "w", encoding="utf-8") as fp:
        for record in records:
            fp.write(json.dumps(record) + "\n")

    res = client.get("/api/math/accuracy")
    assert res.status_code == 200
    data = res.get_json()

    assert data["totals"] == {
        "answered": 4,
        "correct": 2,
        "accuracy": 50.0,
    }

    assert data["byUser"] == [
        {"user": "alice", "answered": 2, "correct": 1, "accuracy": 50.0},
        {"user": "bob", "answered": 2, "correct": 1, "accuracy": 50.0},
    ]

    assert data["byQuestion"] == [
        {"id": "m1", "prompt": "1+1", "answered": 2, "correct": 1, "accuracy": 50.0},
        {"id": "m2", "prompt": "5-2", "answered": 1, "correct": 0, "accuracy": 0.0},
        {"id": "m3", "prompt": "3×3", "answered": 1, "correct": 1, "accuracy": 100.0},
    ]

    # user filter
    res = client.get("/api/math/accuracy", query_string={"user": "alice"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["totals"] == {
        "answered": 2,
        "correct": 1,
        "accuracy": 50.0,
    }
    assert data["byUser"] == [
        {"user": "alice", "answered": 2, "correct": 1, "accuracy": 50.0},
    ]
    assert data["byQuestion"] == [
        {"id": "m1", "prompt": "1+1", "answered": 1, "correct": 1, "accuracy": 100.0},
        {"id": "m2", "prompt": "5-2", "answered": 1, "correct": 0, "accuracy": 0.0},
    ]

    sys.modules.pop("app.app", None)
