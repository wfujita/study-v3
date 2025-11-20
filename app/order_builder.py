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
    # A/Fは昇格チェックから外し、最終ランク（Aランク）も通常の出題枠に残す。
    # これにより、Aランクの問題も出力対象から除外されずに提示できる。
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
    unit_filter: str,
    mode: str,
) -> List[Mapping[str, Any]]:
    if mode == "review":
        base = list(deck)
    else:
        base = [
            q
            for q in deck
            if not unit_filter or normalize_unit(q.get("unit")) == unit_filter
        ]
    return base


def build_order(
    deck: Sequence[Mapping[str, Any]],
    stats: Mapping[str, Mapping[str, Any]],
    *,
    total_per_set: int,
    mode: str = "normal",
    unit_filter: str = "",
    default_stage: str = "F",
    now: Optional[datetime] = None,
) -> OrderResult:
    # 1. 希望する出題数が0なら即終了。
    desired = _to_non_negative_int(total_per_set)
    if desired == 0:
        return OrderResult(order=[])

    # 2. 現在時刻とユニット絞り込みの準備。
    now_dt = now or datetime.utcnow()
    if now_dt.tzinfo is not None:
        now_dt = now_dt.astimezone(timezone.utc).replace(tzinfo=None)
    effective_unit = unit_filter if mode == "normal" else ""

    # 3. モードに応じてデッキを絞り込み、ステータスを解決。
    deck_with_extras = _filter_deck(
        deck,
        unit_filter=effective_unit,
        mode=mode,
    )

    entries: List[Tuple[int, Mapping[str, Any], Dict[str, Any]]] = []
    for idx, q in enumerate(deck_with_extras):
        stat = _resolve_stat(stats, q, default_stage=default_stage)
        entries.append((idx, q, stat))

    # 4. 昇格優先（期限到来かつA/F以外）とそれ以外に振り分ける。
    promotable: List[Tuple[int, Mapping[str, Any], Dict[str, Any]]] = []
    remaining: List[Tuple[int, Mapping[str, Any], Dict[str, Any]]] = []

    for idx, q, stat in entries:
        if should_prioritize_stage_promotion(
            stat.get("stage"), stat.get("nextDueAt"), now_dt
        ):
            promotable.append((idx, q, stat))
        else:
            remaining.append((idx, q, stat))

    # 5. 昇格候補はステージ順位→次回出題時刻→元の並び順で優先。
    promotable.sort(
        key=lambda item: (
            _stage_rank(item[2].get("stage")),
            _parse_iso_date(item[2].get("nextDueAt")) or datetime.min,
            item[0],
        )
    )

    order: List[OrderEntry] = []
    chosen = set()

    # 6. 昇格候補から枠が埋まるまで採用し、ステージ名をbucketに残す。
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

    # 7. まだ足りない分は残りを元の並び順で補充。
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

    return OrderResult(order=order[:desired])
