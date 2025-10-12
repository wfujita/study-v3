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
    subject_dir = tmp_path / "english"
    subject_dir.mkdir(parents=True, exist_ok=True)
    path = subject_dir / "results.ndjson"
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")

    res = client.get("/api/stats", query_string={"user": "alice", "id": "q1"})
    assert res.status_code == 200
    data = res.get_json()
    assert data == {
        "answered": 3,
        "correct": 2,
        "streak": 2,
        "lastWrongAt": (now - timedelta(days=40)).isoformat().replace("+00:00", "Z"),
        "lastCorrectAt": now.isoformat().replace("+00:00", "Z"),
        "stage": "F",
        "nextDueAt": None,
    }
    sys.modules.pop("app.app", None)


def test_stats_bulk_endpoint_returns_payloads_in_order(tmp_path, monkeypatch):
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
                {
                    "id": "q2",
                    "correct": False,
                    "at": now.isoformat().replace("+00:00", "Z"),
                },
            ],
        }
    ]

    subject_dir = tmp_path / "english"
    subject_dir.mkdir(parents=True, exist_ok=True)
    path = subject_dir / "results.ndjson"
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")

    res = client.post(
        "/api/stats/bulk",
        json={"user": "alice", "subject": "english", "ids": ["q1", "q2", "missing"]},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert isinstance(payload, dict)
    results = payload.get("results")
    assert isinstance(results, list)
    assert [item.get("id") for item in results] == ["q1", "q2", "missing"]
    first, second, third = results
    assert first["correct"] == 1
    assert first["answered"] == 1
    assert first["stage"] == "F"
    assert second["answered"] == 1
    assert second["correct"] == 0
    assert second["stage"] == "F"
    assert third["answered"] == 0
    assert third["correct"] == 0
    assert third["stage"] == "F"

    sys.modules.pop("app.app", None)


def test_stage_progression_updates_on_result_post(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import sys

    sys.modules.pop("app.app", None)
    mod = importlib.import_module("app.app")
    flask_app = mod.app
    client = flask_app.test_client()

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def iso(dt):
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    session_one = {
        "user": "alice",
        "mode": "normal",
        "endedAt": iso(base + timedelta(minutes=2)),
        "answered": [
            {"id": "q1", "correct": True, "at": iso(base)},
            {"id": "q1", "correct": True, "at": iso(base + timedelta(minutes=1))},
            {"id": "q1", "correct": True, "at": iso(base + timedelta(minutes=2))},
        ],
    }

    res = client.post("/api/results", json=session_one)
    assert res.status_code == 201

    stage_path = tmp_path / "english" / "stages.json"
    with open(stage_path, encoding="utf-8") as fp:
        store = json.load(fp)
    state = store["alice"]["q1"]
    assert state["stage"] == "E"
    assert state["streak"] == 3
    assert state["answered"] == 3
    assert state["correct"] == 3
    expected_last_correct = iso(base + timedelta(minutes=2))
    assert state["lastCorrectAt"] == expected_last_correct
    assert state["nextDueAt"] == iso(base + timedelta(minutes=2) + timedelta(days=2))

    session_two = {
        "user": "alice",
        "mode": "normal",
        "endedAt": iso(base + timedelta(days=4)),
        "answered": [
            {"id": "q1", "correct": True, "at": iso(base + timedelta(days=4))},
        ],
    }

    res = client.post("/api/results", json=session_two)
    assert res.status_code == 201

    with open(stage_path, encoding="utf-8") as fp:
        store = json.load(fp)
    state = store["alice"]["q1"]
    assert state["stage"] == "D"
    assert state["streak"] == 4
    assert state["correct"] == 4
    assert state["nextDueAt"] == iso(base + timedelta(days=4) + timedelta(days=3))

    session_three = {
        "user": "alice",
        "mode": "normal",
        "endedAt": iso(base + timedelta(days=5)),
        "answered": [
            {"id": "q1", "correct": False, "at": iso(base + timedelta(days=5))},
        ],
    }

    res = client.post("/api/results", json=session_three)
    assert res.status_code == 201

    with open(stage_path, encoding="utf-8") as fp:
        store = json.load(fp)
    state = store["alice"]["q1"]
    assert state["stage"] == "F"
    assert state["streak"] == 0
    assert state["answered"] == 5
    assert state["correct"] == 4
    assert state["lastWrongAt"] == iso(base + timedelta(days=5))
    assert state["lastCorrectAt"] == iso(base + timedelta(days=4))
    assert state["nextDueAt"] is None

    stats = client.get("/api/stats", query_string={"user": "alice", "id": "q1"})
    assert stats.status_code == 200
    payload = stats.get_json()
    assert payload == {
        "answered": 5,
        "correct": 4,
        "streak": 0,
        "lastWrongAt": iso(base + timedelta(days=5)),
        "lastCorrectAt": iso(base + timedelta(days=4)),
        "stage": "F",
        "nextDueAt": None,
    }
    sys.modules.pop("app.app", None)
