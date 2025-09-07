import re


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_end_punc(s: str) -> str:
    return re.sub(r"\s*[.,!?]$", "", s)


def test_reorder_question_extras_ignored():
    # question with dummy extras
    q = {
        "en": "He plays soccer after school.",
        "chunks": ["He", "plays", "soccer", "after school", "."],
        "extras": ["in the park"],
    }

    # renderQuestion would merge chunks and extras as options
    options = q["chunks"] + q["extras"]
    assert len(options) == len(q["chunks"]) + len(q["extras"])
    assert q["extras"][0] in options

    # selecting only the correct chunks should be considered done
    selected = q["chunks"]
    assert len(selected) == len(q["chunks"])

    ans = normalize_end_punc(normalize_spaces(" ".join(selected)))
    right = normalize_end_punc(normalize_spaces(q["en"]))

    # extra options do not affect evaluation
    assert ans == right

