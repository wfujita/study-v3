"""Utilities for storing per-question level overrides at the subject scope."""

from __future__ import annotations

import json
import os
from typing import Dict, Optional

from .stage_tracker import _normalize_qid


def _levels_file_path(runtime_dir: str) -> str:
    return os.path.join(runtime_dir, "levels.json")


def load_levels(runtime_dir: str) -> Dict[str, str]:
    path = _levels_file_path(runtime_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: Dict[str, str] = {}
    for key, value in data.items():
        qid = _normalize_qid(key)
        if qid is None:
            continue
        if isinstance(value, str) and value:
            out[qid] = value
    return out


def _save_levels(runtime_dir: str, overrides: Dict[str, str]) -> None:
    path = _levels_file_path(runtime_dir)
    if overrides:
        os.makedirs(runtime_dir, exist_ok=True)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as fp:
            json.dump(overrides, fp, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp_path, path)
    else:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def set_level(runtime_dir: str, qid: str, level: Optional[str]) -> bool:
    """Update or remove the override for ``qid``.

    Returns ``True`` if the stored data was modified."""

    normalized_qid = _normalize_qid(qid)
    if normalized_qid is None:
        return False

    overrides = load_levels(runtime_dir)

    changed = False
    if level is None or level == "":
        if normalized_qid in overrides:
            overrides.pop(normalized_qid, None)
            changed = True
    else:
        if overrides.get(normalized_qid) != level:
            overrides[normalized_qid] = level
            changed = True

    if changed:
        _save_levels(runtime_dir, overrides)

    return changed


def get_level(runtime_dir: str, qid: str) -> Optional[str]:
    overrides = load_levels(runtime_dir)
    normalized_qid = _normalize_qid(qid)
    if normalized_qid is None:
        return None
    return overrides.get(normalized_qid)
