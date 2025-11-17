"""Server-side problem selection logic.

This module mirrors the client-side `buildOrderFromBank` logic so that the
backend can determine which questions to present for a given set. The code is
structured to be data-only (deck + stats in, order out) so it can be unit
tested without Flask.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

STAGE_PRIORITY: Tuple[str, ...] = ("A", "B", "C", "D", "E")
LEVEL_ORDER: Tuple[str, ...] = ("Lv1", "Lv2", "Lv3")
DEFAULT_LEVEL: str = LEVEL_ORDER[0]


def _to_non_negative_int(value: Any) -> int:
    try:
        num = int(float(value))
    except Exception:
        return 0
    return max(0, num)


def normalize_level(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    if text in LEVEL_ORDER:
        return text
    if text:
        for marker in ("1", "2", "3"):
            if marker in text:
                candidate = f"Lv{marker}"
                if candidate in LEVEL_ORDER:
                    return candidate
    return DEFAULT_LEVEL


def level_index(value: Any) -> int:
    normalized = normalize_level(value)
    try:
        return LEVEL_ORDER.index(normalized)
    except ValueError:
        return len(LEVEL_ORDER)


def normalize_unit(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def question_key(question: Mapping[str, Any]) -> str:
    if not isinstance(question, Mapping):
        return ""
    qid = question.get("id")
    if qid not in (None, ""):
        return f"id:{qid}"
    qtype = question.get("type") or ""
    en = question.get("en") or ""
    jp = question.get("jp") or ""
    return f"{qtype}:{en}__{jp}"


def _parse_iso_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value)
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def determine_stage_priority_quota(total_needed: Any, stage_f_count: Any) -> int:
    needed = _to_non_negative_int(total_needed)
    if needed == 0:
        return 0
    stage_f = _to_non_negative_int(stage_f_count)
    return max(0, needed - min(stage_f, needed))


def should_prioritize_stage_promotion(stage: Any, next_due: Any, now: datetime) -> bool:
    try:
        stage_key = str(stage).strip().upper()
    except Exception:
        stage_key = ""
    if stage_key in ("", "A", "F"):
        return False
    due = _parse_iso_date(next_due)
    if due is None:
        return False
    try:
        return due <= now
    except Exception:
        return False


@dataclass
class OrderEntry:
    idx: int
    bucket: Optional[str]
    streak: int
    id: Optional[str]
    key: str


@dataclass
class OrderResult:
    order: List[OrderEntry]
    fallback_extra_keys: List[str]


def _stage_rank(stage: str) -> int:
    normalized = (stage or "").strip().upper()
    try:
        return STAGE_PRIORITY.index(normalized)
    except ValueError:
        return len(STAGE_PRIORITY)


def _normalize_stat(value: Mapping[str, Any], *, default_stage: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"stage": default_stage, "streak": 0, "nextDueAt": None}
    return {
        "stage": value.get("stage") or default_stage,
        "streak": _to_non_negative_int(value.get("streak")),
        "nextDueAt": value.get("nextDueAt"),
    }


def _resolve_stat(
    stats: Mapping[str, Mapping[str, Any]],
    question: Mapping[str, Any],
    *,
    default_stage: str,
) -> Dict[str, Any]:
    qid = question.get("id")
    if qid not in (None, ""):
        stat = stats.get(str(qid))
        if stat:
            return _normalize_stat(stat, default_stage=default_stage)
    return {"stage": default_stage, "streak": 0, "nextDueAt": None}


def _filter_deck(
    deck: Sequence[Mapping[str, Any]],
    *,
    max_level_idx: int,
    unit_filter: str,
    mode: str,
    include_extras: bool,
    extras: Sequence[Mapping[str, Any]],
) -> List[Mapping[str, Any]]:
    if mode == "review":
        base = list(deck)
    else:
        base = [
            q
            for q in deck
            if level_index(q.get("level")) <= max_level_idx
            and (not unit_filter or normalize_unit(q.get("unit")) == unit_filter)
        ]

    if not include_extras or not extras:
        return base

    if mode == "review":
        return base + list(extras)

    if not unit_filter:
        return base + list(extras)

    filtered_extras = [
        q for q in extras if normalize_unit(q.get("unit")) == unit_filter
    ]
    return base + filtered_extras


def build_order(
    deck: Sequence[Mapping[str, Any]],
    stats: Mapping[str, Mapping[str, Any]],
    *,
    total_per_set: int,
    level_max: Any,
    mode: str = "normal",
    unit_filter: str = "",
    default_stage: str = "F",
    now: Optional[datetime] = None,
) -> OrderResult:
    desired = _to_non_negative_int(total_per_set)
    if desired == 0:
        return OrderResult(order=[], fallback_extra_keys=[])

    now_dt = now or datetime.utcnow()
    if now_dt.tzinfo is not None:
        now_dt = now_dt.astimezone(timezone.utc).replace(tzinfo=None)
    max_level_idx = level_index(level_max)
    effective_unit = unit_filter if mode == "normal" else ""

    base_deck = _filter_deck(
        deck,
        max_level_idx=max_level_idx,
        unit_filter=effective_unit,
        mode=mode,
        include_extras=False,
        extras=[],
    )

    seen_keys = set()
    for q in base_deck:
        seen_keys.add(question_key(q))

    promotable_base = 0
    for q in base_deck:
        stat = _resolve_stat(stats, q, default_stage=default_stage)
        if should_prioritize_stage_promotion(
            stat.get("stage"), stat.get("nextDueAt"), now_dt
        ):
            promotable_base += 1

    shortage = determine_stage_priority_quota(desired, promotable_base)

    fallback_extras: List[Mapping[str, Any]] = []
    if shortage > 0:
        candidates: List[Mapping[str, Any]] = []
        for q in deck:
            lvl_idx = level_index(q.get("level"))
            if lvl_idx <= max_level_idx:
                continue
            if effective_unit and normalize_unit(q.get("unit")) != effective_unit:
                continue
            key = question_key(q)
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            candidates.append(q)
        candidates.sort(
            key=lambda item: (
                level_index(item.get("level")),
                str(item.get("en") or ""),
                str(item.get("id") or ""),
            )
        )
        fallback_extras = candidates[:shortage]

    deck_with_extras = _filter_deck(
        deck,
        max_level_idx=max_level_idx,
        unit_filter=effective_unit,
        mode=mode,
        include_extras=True,
        extras=fallback_extras,
    )

    entries: List[Tuple[int, Mapping[str, Any], Dict[str, Any]]] = []
    for idx, q in enumerate(deck_with_extras):
        stat = _resolve_stat(stats, q, default_stage=default_stage)
        entries.append((idx, q, stat))

    promotable: List[Tuple[int, Mapping[str, Any], Dict[str, Any]]] = []
    higher_level: Dict[int, List[Tuple[int, Mapping[str, Any], Dict[str, Any]]]] = {}
    remaining: List[Tuple[int, Mapping[str, Any], Dict[str, Any]]] = []

    for idx, q, stat in entries:
        lvl_idx = level_index(q.get("level"))
        if should_prioritize_stage_promotion(
            stat.get("stage"), stat.get("nextDueAt"), now_dt
        ):
            promotable.append((idx, q, stat))
        elif lvl_idx > max_level_idx:
            higher_level.setdefault(lvl_idx, []).append((idx, q, stat))
        else:
            remaining.append((idx, q, stat))

    promotable.sort(
        key=lambda item: (
            _stage_rank(item[2].get("stage")),
            _parse_iso_date(item[2].get("nextDueAt")) or datetime.min,
            item[0],
        )
    )

    order: List[OrderEntry] = []
    chosen = set()

    for idx, q, stat in promotable:
        if len(order) >= desired:
            break
        if idx in chosen:
            continue
        order.append(
            OrderEntry(
                idx=idx,
                bucket=f"Stage {stat.get('stage')}",
                streak=_to_non_negative_int(stat.get("streak")),
                id=str(q.get("id")) if q.get("id") not in (None, "") else None,
                key=question_key(q),
            )
        )
        chosen.add(idx)

    if len(order) < desired and higher_level:
        for lvl_idx in sorted(higher_level.keys()):
            level_label = LEVEL_ORDER[lvl_idx] if lvl_idx < len(LEVEL_ORDER) else ""
            bucket_label = f"Lv優先 ({level_label})" if level_label else "Lv優先"
            items = higher_level.get(lvl_idx, [])
            items.sort(
                key=lambda item: (
                    _parse_iso_date(item[2].get("nextDueAt")) or datetime.max,
                    _stage_rank(item[2].get("stage")),
                    item[0],
                )
            )
            for idx, q, stat in items:
                if len(order) >= desired:
                    break
                if idx in chosen:
                    continue
                order.append(
                    OrderEntry(
                        idx=idx,
                        bucket=bucket_label,
                        streak=_to_non_negative_int(stat.get("streak")),
                        id=str(q.get("id")) if q.get("id") not in (None, "") else None,
                        key=question_key(q),
                    )
                )
                chosen.add(idx)
            if len(order) >= desired:
                break

    if len(order) < desired and remaining:
        remaining.sort(key=lambda item: item[0])
        for idx, q, stat in remaining:
            if len(order) >= desired:
                break
            if idx in chosen:
                continue
            order.append(
                OrderEntry(
                    idx=idx,
                    bucket=None,
                    streak=_to_non_negative_int(stat.get("streak")),
                    id=str(q.get("id")) if q.get("id") not in (None, "") else None,
                    key=question_key(q),
                )
            )
            chosen.add(idx)

    fallback_keys = [question_key(q) for q in fallback_extras if question_key(q)]
    return OrderResult(order=order[:desired], fallback_extra_keys=fallback_keys)
