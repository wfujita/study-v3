import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REWRITE_DIR = ROOT / "app/static/data/english/questions/rewrite"
CHOICE_DIR = ROOT / "app/static/data/english/questions/vocab-choice-en-ja"

# The source request had a few obvious spelling typos. Keep the quiz data on
# standard English spellings while preserving coverage for the requested batch.
REQUESTED_BATCH = {
    "school": "学校",
    "after": "〜の後で／〜の後",
    "brass band": "吹奏楽部（ブラスバンド）",
    "new": "新しい",
    "yes": "はい",
    "come": "来る",
    "Mr.": "〜さん（男性の敬称）",
    "here's": "ここに〜があります／これが〜です（= here is）",
    "no": "いいえ",
    "interested": "興味がある",
    "of": "〜の",
    "anime": "アニメ",
    "an": "1つの（母音で始まる語の前の a）",
    "instrument": "楽器",
    "little": "小さい／少し（の）",
    "usually": "ふだんは／たいてい",
    "practice": "練習する／練習",
    "on": "〜に（曜日・日付）／〜の上に",
    "Monday": "月曜日",
    "Wednesday": "水曜日",
    "Friday": "金曜日",
    "listen": "聞く",
    "radio": "ラジオ",
    "read": "読む",
}


def load_all(directory: Path):
    questions = []
    for path in sorted(directory.glob("*.json")):
        questions.extend(json.loads(path.read_text(encoding="utf-8")))
    return questions


def test_requested_batch_exists_as_ja_en_spelling_questions():
    questions = {item["en"]: item for item in load_all(REWRITE_DIR)}

    for en, jp in REQUESTED_BATCH.items():
        item = questions[en]
        assert item["source"] == jp
        assert item["task"] == "和⇒英"
        assert en in item["answers"]


def test_requested_batch_exists_as_en_ja_choice_questions():
    questions = {item["en"]: item for item in load_all(CHOICE_DIR)}

    for en, jp in REQUESTED_BATCH.items():
        item = questions[en]
        assert item["jp"] == jp
        correct_choices = [
            choice["text"] for choice in item["choices"] if choice.get("correct")
        ]
        assert correct_choices == [jp]
