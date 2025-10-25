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
    assert all(r["unit"] == "present-simple" for r in data["recentAnswers"])
    assert all("stage" in r for r in data["recentAnswers"])
    assert [u["unit"] for u in data["byUnit"]] == ["present-simple"]

    res2 = client.get("/api/admin/summary", query_string={"show": "vocab-choice"})
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert all(q["type"] == "vocab-choice" for q in data2["questionStats"])
    assert all(r["unit"] == "疑問詞" for r in data2["recentAnswers"])
    assert all("stage" in r for r in data2["recentAnswers"])
    assert [u["unit"] for u in data2["byUnit"]] == ["疑問詞"]

    sys.modules.pop("app.app", None)
