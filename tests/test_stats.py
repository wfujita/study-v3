import json
from datetime import datetime, timedelta, timezone


def test_stats_endpoint_excludes_review_and_counts_all(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import sys

    sys.modules.pop("app.app", None)
    mod = importlib.import_module("app.app")
    flask_app = mod.app
    client = flask_app.test_client()
    now = datetime.now(timezone.utc)
    recs = [
        {
            "user": "alice",
            "mode": "normal",
            "endedAt": now.isoformat().replace("+00:00", "Z"),
            "answered": [
                {
                    "id": "q1",
                    "correct": True,
                    "at": now.isoformat().replace("+00:00", "Z"),
                },
            ],
        },
        {
            "user": "alice",
            "mode": "normal",
            "endedAt": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "answered": [
                {
                    "id": "q1",
                    "correct": True,
                    "at": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                },
            ],
        },
        {
            "user": "alice",
            "mode": "review",
            "endedAt": now.isoformat().replace("+00:00", "Z"),
            "reviewed": [
                {
                    "id": "q1",
                    "correct": True,
                    "mode": "review",
                    "at": now.isoformat().replace("+00:00", "Z"),
                }
            ],
        },
        {
            "user": "alice",
            "mode": "normal",
            "endedAt": (now - timedelta(days=40)).isoformat().replace("+00:00", "Z"),
            "answered": [
                {
                    "id": "q1",
                    "correct": False,
                    "at": (now - timedelta(days=40)).isoformat().replace("+00:00", "Z"),
                }
            ],
        },
    ]
    path = tmp_path / "results.ndjson"
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    res = client.get("/api/stats", query_string={"user": "alice", "id": "q1"})
    assert res.status_code == 200
    data = res.get_json()
    assert data == {"answered": 3, "correct": 2, "streak": 2}
    sys.modules.pop("app.app", None)
