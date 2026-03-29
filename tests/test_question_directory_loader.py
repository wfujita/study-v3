import importlib
import json
from pathlib import Path


def _client():
    mod = importlib.import_module("app.app")
    return mod.app.test_client()


def test_directory_based_questions_are_loaded():
    base = Path("app/static/data/english/questions")
    expected_questions = sum(
        len(json.loads(p.read_text(encoding="utf-8")))
        for p in (base / "reorder").glob("*.json")
    )
    expected_vocab_choice = sum(
        len(json.loads(p.read_text(encoding="utf-8")))
        for p in (base / "vocab-choice-en-ja").glob("*.json")
    )
    expected_rewrite = sum(
        len(json.loads(p.read_text(encoding="utf-8")))
        for p in (base / "rewrite").glob("*.json")
    )

    res = _client().get("/data/english/questions.json")
    assert res.status_code == 200
    payload = res.get_json()

    assert isinstance(payload.get("questions"), list)
    assert isinstance(payload.get("vocabChoice"), list)
    assert isinstance(payload.get("rewrite"), list)

    assert len(payload["questions"]) == expected_questions
    assert len(payload["vocabChoice"]) == expected_vocab_choice
    assert len(payload["rewrite"]) == expected_rewrite


def test_directory_layout_exists():
    base = Path("app/static/data/english/questions")
    assert (base / "reorder").is_dir()
    assert (base / "vocab-choice-en-ja").is_dir()
    assert (base / "rewrite").is_dir()

    assert list((base / "reorder").glob("*.json"))
    assert list((base / "vocab-choice-en-ja").glob("*.json"))
    assert list((base / "rewrite").glob("*.json"))

    meta = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    assert isinstance(meta, dict)
