import json
from datetime import datetime, timezone


def test_admin_summary_show_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import sys

    sys.modules.pop("app.app", None)
    mod = importlib.import_module("app.app")
    client = mod.app.test_client()

    now = datetime.now(timezone.utc)
    rec = {
        "user": "u",
        "mode": "normal",
        "endedAt": now.isoformat().replace("+00:00", "Z"),
        "answered": [
            {
                "id": "r001",
                "correct": False,
                "at": now.isoformat().replace("+00:00", "Z"),
            },
            {
                "id": "v051",
                "correct": True,
                "at": now.isoformat().replace("+00:00", "Z"),
            },
        ],
    }
    subject_dir = tmp_path / "english"
    subject_dir.mkdir(parents=True, exist_ok=True)
    with open(subject_dir / "results.ndjson", "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    res = client.get("/api/admin/summary", query_string={"show": "reorder"})
    assert res.status_code == 200
    data = res.get_json()
    assert all(q["type"] == "reorder" for q in data["questionStats"])
    assert all((q.get("level") or "").startswith("Lv") for q in data["questionStats"])
    assert all(r["unit"] == "present-simple" for r in data["recentAnswers"])
    assert all((r.get("level") or "").startswith("Lv") for r in data["recentAnswers"])
    assert all("stage" in r for r in data["recentAnswers"])
    assert [u["unit"] for u in data["byUnit"]] == ["present-simple"]

    res2 = client.get("/api/admin/summary", query_string={"show": "vocab-choice"})
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert all(q["type"] == "vocab-choice" for q in data2["questionStats"])
    assert all((q.get("level") or "").startswith("Lv") for q in data2["questionStats"])
    assert all(r["unit"] == "疑問詞" for r in data2["recentAnswers"])
    assert all((r.get("level") or "").startswith("Lv") for r in data2["recentAnswers"])
    assert all("stage" in r for r in data2["recentAnswers"])
    assert [u["unit"] for u in data2["byUnit"]] == ["疑問詞"]

    sys.modules.pop("app.app", None)


def test_admin_summary_sessions_include_type(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import sys

    sys.modules.pop("app.app", None)
    mod = importlib.import_module("app.app")
    client = mod.app.test_client()

    now = datetime.now(timezone.utc)
    rec_vocab = {
        "user": "alice",
        "setIndex": 1,
        "mode": "normal",
        "qType": "vocab",
        "seconds": 30,
        "endedAt": now.isoformat().replace("+00:00", "Z"),
        "answered": [
            {
                "id": "v001",
                "type": "vocab",
                "correct": True,
                "at": now.isoformat().replace("+00:00", "Z"),
            }
        ],
    }
    rec_reorder = {
        "user": "alice",
        "setIndex": 2,
        "mode": "normal",
        "seconds": 45,
        "endedAt": now.isoformat().replace("+00:00", "Z"),
        "answered": [
            {
                "id": "r001",
                "type": "reorder",
                "correct": False,
                "at": now.isoformat().replace("+00:00", "Z"),
            }
        ],
    }

    subject_dir = tmp_path / "english"
    subject_dir.mkdir(parents=True, exist_ok=True)
    with open(subject_dir / "results.ndjson", "w", encoding="utf-8") as f:
        f.write(json.dumps(rec_vocab) + "\n")
        f.write(json.dumps(rec_reorder) + "\n")

    res = client.get("/api/admin/summary")
    assert res.status_code == 200
    data = res.get_json()
    types_by_set = {
        sess.get("setIndex"): sess.get("qType") for sess in data.get("sessions", [])
    }
    assert types_by_set.get(1) == "vocab-choice"
    assert types_by_set.get(2) == "reorder"

    sys.modules.pop("app.app", None)


def test_admin_summary_includes_attempts_older_than_30_days(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import sys
    from datetime import timedelta

    sys.modules.pop("app.app", None)
    mod = importlib.import_module("app.app")
    client = mod.app.test_client()

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=45)
    rec = {
        "user": "alice",
        "mode": "normal",
        "endedAt": old.isoformat().replace("+00:00", "Z"),
        "answered": [
            {
                "id": "w201",
                "type": "rewrite",
                "correct": True,
                "at": old.isoformat().replace("+00:00", "Z"),
            }
        ],
    }

    subject_dir = tmp_path / "english"
    subject_dir.mkdir(parents=True, exist_ok=True)
    with open(subject_dir / "results.ndjson", "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    res = client.get(
        "/api/admin/summary",
        query_string={"user": "alice", "show": "rewrite"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert [item["id"] for item in data["recentAnswers"]] == ["w201"]
    stats_by_id = {item["id"]: item for item in data["questionStats"]}
    assert stats_by_id["w201"]["answered"] == 1
    assert stats_by_id["w201"]["correct"] == 1
    assert data["totals"]["answered"] == 1
    assert data["totals"]["correct"] == 1

    sys.modules.pop("app.app", None)
