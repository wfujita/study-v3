import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class StageConfig:
    sequence: Tuple[str, ...]
    default_stage: str
    reset_stage: str
    rules: Dict[str, Dict[str, Any]]


DEFAULT_STAGE_RULES: Dict[str, Dict[str, Any]] = {
    "F": {"next": "E", "gap_days": None, "min_streak": 3},
    "E": {"next": "D", "gap_days": 2},
    "D": {"next": "C", "gap_days": 3},
    "C": {"next": "B", "gap_days": 7},
    "B": {"next": "A", "gap_days": 14},
    "A": {},
}

MATH_STAGE_RULES: Dict[str, Dict[str, Any]] = {
    "E": {"next": "D", "gap_days": None},
    "D": {"next": "C", "gap_days": 3},
    "C": {"next": "B", "gap_days": 7},
    "B": {"next": "A", "gap_days": 30},
    "A": {},
}

DEFAULT_STAGE_CONFIG = StageConfig(
    sequence=("F", "E", "D", "C", "B", "A"),
    default_stage="F",
    reset_stage="F",
    rules=DEFAULT_STAGE_RULES,
)

MATH_STAGE_CONFIG = StageConfig(
    sequence=("E", "D", "C", "B", "A"),
    default_stage="E",
    reset_stage="E",
    rules=MATH_STAGE_RULES,
)

_STAGE_CONFIGS: Dict[str, StageConfig] = {
    "math": MATH_STAGE_CONFIG,
}

STAGE_SEQUENCE = DEFAULT_STAGE_CONFIG.sequence


def _normalize_subject(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in ("-", "_"))
    return cleaned


def get_stage_config(subject: Optional[str] = None) -> StageConfig:
    key = _normalize_subject(subject)
    return _STAGE_CONFIGS.get(key, DEFAULT_STAGE_CONFIG)


def _config_from_record(record: Dict[str, Any]) -> StageConfig:
    subject = record.get("subject")
    config = get_stage_config(subject)
    if config is DEFAULT_STAGE_CONFIG:
        mode = (record.get("mode") or "").strip().lower()
        if mode == "math-drill":
            return MATH_STAGE_CONFIG
    return config


def _default_question_state(config: StageConfig) -> Dict[str, Any]:
    return {
        "stage": config.default_stage,
        "streak": 0,
        "answered": 0,
        "correct": 0,
        "lastCorrectAt": None,
        "lastWrongAt": None,
        "lastAttemptAt": None,
        "nextDueAt": None,
        "updatedAt": None,
    }


def _normalize_user(user: str) -> str:
    value = (user or "").strip()
    return value or "guest"


def _normalize_qid(qid: Any) -> Optional[str]:
    if qid in (None, ""):
        return None
    return str(qid)


def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _compute_next_due(
    stage: str, reference: Optional[datetime], config: StageConfig
) -> Optional[str]:
    rules = config.rules.get(stage, {})
    gap_days = rules.get("gap_days")
    if not reference or gap_days in (None, 0):
        return None
    try:
        delta = timedelta(days=float(gap_days))
    except Exception:
        return None
    return _to_iso(reference + delta)


def _apply_correct(
    state: Dict[str, Any], attempt_dt: datetime, config: StageConfig
) -> None:
    prev_last_correct = _parse_iso(state.get("lastCorrectAt"))
    state["streak"] = int(state.get("streak") or 0) + 1

    stage = state.get("stage") or config.default_stage
    if stage == "F" and config is not DEFAULT_STAGE_CONFIG:
        stage = config.default_stage
    stage_rules = config.rules.get(stage, {})

    if stage == "F" and config is DEFAULT_STAGE_CONFIG:
        min_streak = stage_rules.get("min_streak") or 0
        if state["streak"] >= min_streak and min_streak > 0:
            stage = stage_rules.get("next", stage)
    else:
        gap_days_req = stage_rules.get("gap_days")
        next_stage = stage_rules.get("next")
        if next_stage:
            if gap_days_req is None:
                stage = next_stage
            elif prev_last_correct is None:
                try:
                    if float(gap_days_req) <= 0:
                        stage = next_stage
                except Exception:
                    pass
            else:
                gap = (attempt_dt - prev_last_correct).total_seconds() / 86400.0
                try:
                    if gap >= float(gap_days_req):
                        stage = next_stage
                except Exception:
                    pass

    if stage not in config.sequence and stage != "F":
        stage = config.default_stage

    state["stage"] = stage
    state["lastCorrectAt"] = _to_iso(attempt_dt)
    state["nextDueAt"] = _compute_next_due(state["stage"], attempt_dt, config)


def _apply_wrong(state: Dict[str, Any], attempt_dt: datetime, config: StageConfig) -> None:
    state["stage"] = config.reset_stage
    state["streak"] = 0
    state["lastWrongAt"] = _to_iso(attempt_dt)
    state["nextDueAt"] = None


def _apply_attempt(
    state: Dict[str, Any],
    attempt_dt: Optional[datetime],
    is_correct: bool,
    config: StageConfig,
) -> bool:
    if not attempt_dt:
        return False
    before = state.copy()

    state["answered"] = int(state.get("answered") or 0) + 1
    if is_correct:
        state["correct"] = int(state.get("correct") or 0) + 1
        _apply_correct(state, attempt_dt, config)
    else:
        _apply_wrong(state, attempt_dt, config)
    state["lastAttemptAt"] = _to_iso(attempt_dt)
    state["updatedAt"] = state["lastAttemptAt"]

    return state != before


def _stage_file_path(runtime_dir: str) -> str:
    return os.path.join(runtime_dir, "stages.json")


def load_store(runtime_dir: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    path = _stage_file_path(runtime_dir)
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


def save_store(runtime_dir: str, store: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
    path = _stage_file_path(runtime_dir)
    os.makedirs(runtime_dir, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fp:
        json.dump(store, fp, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp_path, path)


def _ensure_state(
    store: Dict[str, Any], user: str, qid: str, config: StageConfig
) -> Dict[str, Any]:
    user_key = _normalize_user(user)
    qid_key = _normalize_qid(qid)
    if qid_key is None:
        raise ValueError("question id is required")
    user_bucket = store.setdefault(user_key, {})
    state = user_bucket.get(qid_key)
    if not isinstance(state, dict):
        state = _default_question_state(config)
        user_bucket[qid_key] = state
    return state


def _iter_session_attempts(
    record: Dict[str, Any],
) -> Iterable[Tuple[datetime, Dict[str, Any]]]:
    mode = (record.get("mode") or "normal").lower()
    if mode == "review":
        return []
    answered = record.get("answered") or []
    if not isinstance(answered, list):
        return []

    attempts: List[Tuple[datetime, Dict[str, Any]]] = []
    fallback_time = record.get("endedAt") or record.get("receivedAt")
    for item in answered:
        if not isinstance(item, dict):
            continue
        attempt_mode = (item.get("mode") or mode).lower()
        if attempt_mode == "review":
            continue
        qid = _normalize_qid(item.get("id"))
        if qid is None:
            continue
        at_str = item.get("at") or fallback_time
        dt = _parse_iso(at_str)
        if not dt:
            continue
        attempts.append((dt, item))
    attempts.sort(key=lambda x: x[0])
    return attempts


def apply_session(store: Dict[str, Any], record: Dict[str, Any]) -> bool:
    user = _normalize_user(record.get("user"))
    changed = False
    config = _config_from_record(record)
    for attempt_dt, payload in _iter_session_attempts(record):
        qid = _normalize_qid(payload.get("id"))
        if qid is None:
            continue
        try:
            state = _ensure_state(store, user, qid, config)
        except ValueError:
            continue
        ok = bool(payload.get("correct"))
        changed |= _apply_attempt(state, attempt_dt, ok, config)
    return changed


def update_store_from_session(runtime_dir: str, record: Dict[str, Any]) -> None:
    store = load_store(runtime_dir)
    changed = apply_session(store, record)
    if changed:
        save_store(runtime_dir, store)


def rebuild_store(
    runtime_dir: str, records: Iterable[Dict[str, Any]]
) -> Dict[str, Any]:
    ordered: List[Tuple[datetime, Dict[str, Any]]] = []
    for rec in records:
        fallback = rec.get("endedAt") or rec.get("receivedAt")
        dt = _parse_iso(fallback)
        if not dt:
            dt = datetime.now(timezone.utc)
        ordered.append((dt, rec))
    ordered.sort(key=lambda x: x[0])

    store: Dict[str, Any] = {}
    for _, rec in ordered:
        apply_session(store, rec)
    save_store(runtime_dir, store)
    return store


def get_question_state(
    store: Dict[str, Any], user: str, qid: str
) -> Optional[Dict[str, Any]]:
    user_key = _normalize_user(user)
    qid_key = _normalize_qid(qid)
    if qid_key is None:
        return None
    user_bucket = store.get(user_key)
    if not isinstance(user_bucket, dict):
        return None
    state = user_bucket.get(qid_key)
    if not isinstance(state, dict):
        return None
    return state


def get_question_states(
    store: Dict[str, Any], user: str, qids: Iterable[Any]
) -> Dict[str, Dict[str, Any]]:
    """Return a mapping of question id -> state for the provided ids."""

    user_key = _normalize_user(user)
    user_bucket = store.get(user_key)
    if not isinstance(user_bucket, dict):
        return {}

    states: Dict[str, Dict[str, Any]] = {}
    for raw_qid in qids:
        qid_key = _normalize_qid(raw_qid)
        if qid_key is None:
            continue
        state = user_bucket.get(qid_key)
        if isinstance(state, dict):
            states[qid_key] = state
    return states
