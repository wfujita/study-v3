import importlib
import json
import sys


def init_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    sys.modules.pop("app.app", None)
    app_module = importlib.import_module("app.app")
    return app_module.app


def test_admin_reset_progress_resets_stage_and_sets_level(tmp_path, monkeypatch):
    app = init_app(tmp_path, monkeypatch)
    client = app.test_client()

    runtime_dir = tmp_path / "english"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    stage_path = runtime_dir / "stages.json"
    with open(stage_path, "w", encoding="utf-8") as fp:
        json.dump({"alice": {"q1": {"stage": "C", "streak": 5}}}, fp)

    res = client.post(
        "/api/admin/reset-progress",
        json={"user": "alice", "id": "q1", "level": "lv2"},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload == {
        "ok": True,
        "stageRemoved": True,
        "level": "Lv2",
        "levelChanged": True,
    }

    with open(stage_path, encoding="utf-8") as fp:
        store = json.load(fp)
    assert "alice" not in store or "q1" not in store.get("alice", {})

    state_path = runtime_dir / "user_state.json"
    with open(state_path, encoding="utf-8") as fp:
        state = json.load(fp)
    overrides = state.get("alice", {}).get("levelOverrides", {})
    assert overrides.get("q1") == "Lv2"

    sys.modules.pop("app.app", None)
    sys.modules.pop("app.user_state", None)


def test_admin_reset_progress_rejects_invalid_level(tmp_path, monkeypatch):
    app = init_app(tmp_path, monkeypatch)
    client = app.test_client()

    runtime_dir = tmp_path / "english"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    stage_path = runtime_dir / "stages.json"
    with open(stage_path, "w", encoding="utf-8") as fp:
        json.dump({"alice": {"q1": {"stage": "B"}}}, fp)

    res = client.post(
        "/api/admin/reset-progress",
        json={"user": "alice", "id": "q1", "level": "hard"},
    )
    assert res.status_code == 400
    payload = res.get_json()
    assert payload.get("ok") is False

    with open(stage_path, encoding="utf-8") as fp:
        store = json.load(fp)
    assert store.get("alice", {}).get("q1") == {"stage": "B"}

    state_path = runtime_dir / "user_state.json"
    assert not state_path.exists()

    sys.modules.pop("app.app", None)
    sys.modules.pop("app.user_state", None)


def test_admin_reset_progress_removes_level_override(tmp_path, monkeypatch):
    app = init_app(tmp_path, monkeypatch)
    client = app.test_client()

    runtime_dir = tmp_path / "english"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    stage_path = runtime_dir / "stages.json"
    with open(stage_path, "w", encoding="utf-8") as fp:
        json.dump({"alice": {"q1": {"stage": "F"}}}, fp)

    user_state = importlib.import_module("app.user_state")
    user_state.set_level_override(str(runtime_dir), "alice", "q1", "Lv3")

    res = client.post(
        "/api/admin/reset-progress",
        json={"user": "alice", "id": "q1", "level": ""},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload == {
        "ok": True,
        "stageRemoved": True,
        "level": None,
        "levelChanged": True,
    }

    state_path = runtime_dir / "user_state.json"
    with open(state_path, encoding="utf-8") as fp:
        state = json.load(fp)
    overrides = state.get("alice", {}).get("levelOverrides", {})
    assert "q1" not in overrides

    sys.modules.pop("app.app", None)
    sys.modules.pop("app.user_state", None)
