import importlib
import json
import sys
from typing import Any, Dict


def init_app(
    tmp_path,
    monkeypatch,
    questions_payload: Dict[str, Any] | None = None,
    subject: str = "english",
):
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("DATA_DIR", str(runtime_root))
    for module in ("app.app", "app.user_state", "app.level_store"):
        sys.modules.pop(module, None)
    app_module = importlib.import_module("app.app")
    if questions_payload is not None:
        static_dir = tmp_path / "static"
        data_dir = static_dir / "data"
        normalized_subject = app_module.normalize_subject(subject)
        subject_dir = data_dir / normalized_subject
        subject_dir.mkdir(parents=True, exist_ok=True)
        with open(subject_dir / "questions.json", "w", encoding="utf-8") as fp:
            json.dump(questions_payload, fp, ensure_ascii=False)
        app_module.STATIC_DIR = str(static_dir)
        app_module.STATIC_DATA_DIR = str(data_dir)
    return app_module.app


def test_admin_reset_progress_clears_stage_history(tmp_path, monkeypatch):
    app = init_app(tmp_path, monkeypatch)
    client = app.test_client()

    runtime_dir = tmp_path / "runtime" / "english"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    stage_path = runtime_dir / "stages.json"
    with open(stage_path, "w", encoding="utf-8") as fp:
        json.dump({"alice": {"q1": {"stage": "C", "streak": 5}}}, fp)

    res = client.post(
        "/api/admin/reset-progress",
        json={"user": "alice", "id": "q1"},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload == {"ok": True, "stageRemoved": True}

    with open(stage_path, encoding="utf-8") as fp:
        store = json.load(fp)
    assert store == {}

    # No additional state files should be created by the reset operation.
    assert not (runtime_dir / "user_state.json").exists()
    assert not (runtime_dir / "levels.json").exists()


def test_admin_reset_progress_rebuilds_store(tmp_path, monkeypatch):
    app = init_app(tmp_path, monkeypatch)
    client = app.test_client()

    runtime_dir = tmp_path / "runtime" / "english"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    results_path = runtime_dir / "results.ndjson"

    session = {
        "user": "alice",
        "subject": "english",
        "receivedAt": "2024-01-01T00:00:00Z",
        "answered": [
            {"id": "q1", "correct": True, "at": "2024-01-01T00:00:00Z"},
        ],
    }
    with open(results_path, "w", encoding="utf-8") as fp:
        fp.write(json.dumps(session) + "\n")

    res = client.post(
        "/api/admin/reset-progress",
        json={"user": "alice", "id": "q1"},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload == {"ok": True, "stageRemoved": True}

    stage_path = runtime_dir / "stages.json"
    assert stage_path.exists()
    with open(stage_path, encoding="utf-8") as fp:
        store = json.load(fp)
    assert store == {}


def test_admin_question_level_updates_and_clears_override(tmp_path, monkeypatch):
    questions_payload = {
        "questions": [
            {"id": "q1", "jp": "JP", "en": "EN", "level": "Lv1"},
            {"id": "q2", "jp": "JP2", "en": "EN2", "level": "Lv2"},
        ]
    }
    app = init_app(tmp_path, monkeypatch, questions_payload)
    client = app.test_client()

    runtime_dir = tmp_path / "runtime" / "english"

    res = client.post(
        "/api/admin/question-level",
        json={"id": "q1", "level": "lv3"},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload == {
        "ok": True,
        "level": "Lv3",
        "effectiveLevel": "Lv3",
        "override": True,
        "changed": True,
    }

    levels_path = runtime_dir / "levels.json"
    with open(levels_path, encoding="utf-8") as fp:
        overrides = json.load(fp)
    assert overrides == {"q1": "Lv3"}

    questions_res = client.get("/data/english/questions.json")
    assert questions_res.status_code == 200
    questions = questions_res.get_json()
    assert questions["questions"][0]["level"] == "Lv3"

    res = client.post(
        "/api/admin/question-level",
        json={"id": "q1", "level": ""},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload == {
        "ok": True,
        "level": None,
        "effectiveLevel": "Lv1",
        "override": False,
        "changed": True,
    }

    assert not levels_path.exists()

    questions_res = client.get("/data/english/questions.json")
    assert questions_res.status_code == 200
    questions = questions_res.get_json()
    assert questions["questions"][0]["level"] == "Lv1"


def test_admin_question_level_rejects_invalid_input(tmp_path, monkeypatch):
    questions_payload = {"questions": [{"id": "q1", "level": "Lv1"}]}
    app = init_app(tmp_path, monkeypatch, questions_payload)
    client = app.test_client()

    res = client.post(
        "/api/admin/question-level",
        json={"id": "q1", "level": "hard"},
    )
    assert res.status_code == 400
    assert res.get_json()["ok"] is False

    res = client.post(
        "/api/admin/question-level",
        json={"id": "unknown", "level": "Lv2"},
    )
    assert res.status_code == 404
    assert res.get_json()["ok"] is False
