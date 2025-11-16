import datetime as dt

from app import order_builder


def _build_stats(mapper):
    default = {"stage": "F", "streak": 0, "nextDueAt": None}
    return {k: {**default, **v} for k, v in mapper.items()}


def test_promotable_items_are_prioritized():
    deck = [
        {"id": "1", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en1", "jp": "jp1"},
        {"id": "2", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en2", "jp": "jp2"},
        {"id": "3", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en3", "jp": "jp3"},
        {"id": "4", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en4", "jp": "jp4"},
        {"id": "5", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en5", "jp": "jp5"},
    ]
    stats = _build_stats(
        {
            "1": {"stage": "D", "streak": 2, "nextDueAt": "2000-01-01T00:00:00.000Z"},
            "2": {"stage": "B", "streak": 1, "nextDueAt": "2000-01-01T00:00:00.000Z"},
            "3": {"stage": "C", "streak": 4, "nextDueAt": "2099-01-01T00:00:00.000Z"},
            "4": {"stage": "F", "streak": 0, "nextDueAt": None},
            "5": {"stage": "E", "streak": 3, "nextDueAt": "2000-01-01T00:00:00.000Z"},
        }
    )

    result = order_builder.build_order(
        deck,
        stats,
        total_per_set=3,
        level_max="Lv1",
        mode="normal",
        unit_filter="",
        default_stage="F",
        now=dt.datetime(2000, 1, 2, tzinfo=dt.timezone.utc),
    )

    ids_with_buckets = [(entry.id, entry.bucket) for entry in result.order]
    assert ids_with_buckets == [
        ("2", "Stage B"),
        ("1", "Stage D"),
        ("5", "Stage E"),
    ]


def test_higher_levels_fill_shortage():
    deck = [
        {"id": "base1", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en-base1", "jp": "jp-base1"},
        {"id": "base2", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en-base2", "jp": "jp-base2"},
        {"id": "high1", "type": "vocab-choice", "level": "Lv2", "unit": "U1", "en": "en-high1", "jp": "jp-high1"},
        {"id": "high2", "type": "vocab-choice", "level": "Lv3", "unit": "U1", "en": "en-high2", "jp": "jp-high2"},
    ]
    stats = _build_stats(
        {
            "base1": {"stage": "F", "streak": 0, "nextDueAt": None},
            "base2": {"stage": "F", "streak": 0, "nextDueAt": None},
            "high1": {"stage": "C", "streak": 1, "nextDueAt": None},
            "high2": {"stage": "D", "streak": 1, "nextDueAt": None},
        }
    )

    result = order_builder.build_order(
        deck,
        stats,
        total_per_set=2,
        level_max="Lv1",
        mode="normal",
        unit_filter="",
        default_stage="F",
        now=dt.datetime(2000, 1, 2, tzinfo=dt.timezone.utc),
    )

    ids_with_buckets = [(entry.id, entry.bucket) for entry in result.order]
    assert ids_with_buckets == [
        ("high1", "Lv優先 (Lv2)"),
        ("high2", "Lv優先 (Lv3)"),
    ]


def test_shortage_then_fill_with_remaining_questions():
    deck = [
        {"id": "base1", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en-base1", "jp": "jp-base1"},
        {"id": "base2", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en-base2", "jp": "jp-base2"},
        {"id": "due1", "type": "vocab-choice", "level": "Lv1", "unit": "U1", "en": "en-due1", "jp": "jp-due1"},
    ]
    stats = _build_stats(
        {
            "base1": {"stage": "F", "streak": 0, "nextDueAt": None},
            "base2": {"stage": "F", "streak": 0, "nextDueAt": None},
            "due1": {"stage": "B", "streak": 2, "nextDueAt": "2000-01-01T00:00:00.000Z"},
        }
    )

    result = order_builder.build_order(
        deck,
        stats,
        total_per_set=2,
        level_max="Lv1",
        mode="normal",
        unit_filter="",
        default_stage="F",
        now=dt.datetime(2000, 1, 2, tzinfo=dt.timezone.utc),
    )

    ids_with_buckets = [(entry.id, entry.bucket) for entry in result.order]
    assert ids_with_buckets == [
        ("due1", "Stage B"),
        ("base1", None),
    ]
    streaks = [entry.streak for entry in result.order]
    assert streaks == [2, 0]

