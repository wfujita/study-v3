import json
import os
from typing import Any, Dict, List

from .stage_tracker import _normalize_user as normalize_user  # type: ignore


def _state_file_path(runtime_dir: str) -> str:
    return os.path.join(runtime_dir, "user_state.json")


def _load_state(runtime_dir: str) -> Dict[str, Any]:
    path = _state_file_path(runtime_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save_state(runtime_dir: str, state: Dict[str, Any]) -> None:
    path = _state_file_path(runtime_dir)
    os.makedirs(runtime_dir, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp_path, path)


def _ensure_user_bucket(state: Dict[str, Any], user: str) -> Dict[str, Any]:
    key = normalize_user(user)
    bucket = state.get(key)
    if not isinstance(bucket, dict):
        bucket = {}
        state[key] = bucket
    return bucket


def get_history(runtime_dir: str, user: str) -> List[Dict[str, Any]]:
    state = _load_state(runtime_dir)
    bucket = _ensure_user_bucket(state, user)
    history = bucket.get("history")
    if isinstance(history, list):
        return history
    return []


def append_history(
    runtime_dir: str, user: str, session: Dict[str, Any], limit: int = 100
) -> None:
    state = _load_state(runtime_dir)
    bucket = _ensure_user_bucket(state, user)
    history = bucket.get("history")
    if not isinstance(history, list):
        history = []
    history.insert(0, session)
    if limit > 0:
        del history[limit:]
    bucket["history"] = history
    _save_state(runtime_dir, state)
