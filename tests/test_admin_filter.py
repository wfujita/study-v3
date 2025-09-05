import json
from datetime import datetime, timezone


def test_admin_summary_show_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib, sys

    sys.modules.pop("app.app", None)
    mod = importlib.import_module("app.app")
    client = mod.app.test_client()

    now = datetime.now(timezone.utc)
    rec = {
        "user": "u",
        "mode": "normal",
        "endedAt": now.isoformat().replace("+00:00", "Z"),
        "answered": [
            {"id": "r001", "correct": False, "at": now.isoformat().replace("+00:00", "Z")},
            {"id": "v001", "correct": False, "at": now.isoformat().replace("+00:00", "Z")},
        ],
    }
    with open(tmp_path / "results.ndjson", "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    res = client.get("/api/admin/summary", query_string={"show": "vocab"})
    assert res.status_code == 200
    data = res.get_json()
    assert all(q["type"] == "vocab" for q in data["questionStats"])
    assert all(r["unit"] == "動詞-基本" for r in data["recentAnswers"])
    assert [u["unit"] for u in data["byUnit"]] == ["動詞-基本"]

    res2 = client.get("/api/admin/summary", query_string={"show": "reorder"})
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert all(q["type"] == "reorder" for q in data2["questionStats"])
    assert all(r["unit"] == "present-simple" for r in data2["recentAnswers"])
    assert [u["unit"] for u in data2["byUnit"]] == ["present-simple"]

    sys.modules.pop("app.app", None)
