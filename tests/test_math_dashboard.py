import importlib
import json
import sys


def create_record(
    user,
    prompt,
    correct,
    *,
    difficulty="normal",
    ended_at="2024-01-01T00:00:00Z",
    response=None,
    accepted=None,
    question_id="q1"
):
    answered = {
        "id": question_id,
        "prompt": prompt,
        "correct": correct,
    }
    if response is not None:
        answered["response"] = response
    if accepted is not None:
        answered["acceptedAnswers"] = accepted
    return {
        "user": user,
        "mode": "math-drill",
        "difficulty": difficulty,
        "endedAt": ended_at,
        "answered": [answered],
        "correct": 1 if correct else 0,
    }


def test_math_dashboard_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    sys.modules.pop("app.app", None)
    mod = importlib.import_module("app.app")
    client = mod.app.test_client()

    math_dir = tmp_path / "math"
    math_dir.mkdir(parents=True, exist_ok=True)

    records = [
        create_record(
            "alice",
            "濃度を求める問題",
            True,
            difficulty="normal",
            ended_at="2024-01-01T10:00:00Z",
            response={"salt8": "500", "salt15": "200"},
            accepted=[{"salt8": ["500"], "salt15": ["200"]}],
            question_id="mix-1",
        ),
        create_record(
            "alice",
            "濃度を求める問題",
            False,
            difficulty="hard",
            ended_at="2024-01-02T11:00:00Z",
            response={"salt8": "400", "salt15": "300"},
            question_id="mix-1",
        ),
        create_record(
            "bob",
            "池を一周する問題",
            True,
            difficulty="hard",
            ended_at="2024-01-03T09:30:00Z",
            response={"speedA": "100", "speedB": "50"},
            accepted=[{"speedA": ["100"], "speedB": ["50"]}],
            question_id="speed-1",
        ),
        {
            "user": "charlie",
            "mode": "review",
            "answered": [{"id": "ignore", "prompt": "復習", "correct": True}],
        },
        {
            "user": "delta",
            "mode": "normal",
            "answered": [{"id": "ignore", "prompt": "通常", "correct": True}],
        },
    ]

    with open(math_dir / "results.ndjson", "w", encoding="utf-8") as fp:
        for record in records:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    res = client.get("/api/math/dashboard")
    assert res.status_code == 200
    data = res.get_json()

    assert data["totals"]["answered"] == 3
    assert data["totals"]["correct"] == 2
    assert round(data["totals"]["accuracy"], 2) == 66.67

    assert data["filters"] == {"user": "__all__", "difficulty": "all", "query": ""}

    user_summaries = data["userSummaries"]
    assert len(user_summaries) == 2
    assert user_summaries[0]["user"] == "alice"
    assert user_summaries[0]["answered"] == 2
    assert user_summaries[0]["correct"] == 1
    assert user_summaries[1]["user"] == "bob"
    assert user_summaries[1]["answered"] == 1
    assert user_summaries[1]["correct"] == 1

    difficulty_stats = {item["difficulty"]: item for item in data["difficultyStats"]}
    assert difficulty_stats["normal"]["answered"] == 1
    assert difficulty_stats["normal"]["correct"] == 1
    assert difficulty_stats["hard"]["answered"] == 2
    assert difficulty_stats["hard"]["correct"] == 1

    question_stats = {item["id"]: item for item in data["questionStats"]}
    assert question_stats["mix-1"]["answered"] == 2
    assert question_stats["mix-1"]["correct"] == 1
    assert question_stats["mix-1"]["wrong"] == 1
    assert question_stats["mix-1"]["lastAnsweredAt"] == "2024-01-02T11:00:00Z"
    assert question_stats["speed-1"]["answered"] == 1
    assert question_stats["speed-1"]["correct"] == 1
    assert question_stats["speed-1"]["difficulty"] == "hard"

    recent = data["recentAttempts"]
    assert [item["questionId"] for item in recent] == ["speed-1", "mix-1", "mix-1"]
    assert "speedA: 100" in recent[0]["responseText"]
    assert "salt8: 500" in recent[-1]["acceptedText"]

    assert data["lastUpdated"] == "2024-01-03T09:30:00Z"

    res_user = client.get("/api/math/dashboard", query_string={"user": "alice"})
    assert res_user.status_code == 200
    data_user = res_user.get_json()
    assert data_user["totals"]["answered"] == 2
    assert data_user["totals"]["correct"] == 1

    res_diff = client.get("/api/math/dashboard", query_string={"difficulty": "hard"})
    assert res_diff.status_code == 200
    data_diff = res_diff.get_json()
    assert data_diff["totals"]["answered"] == 2
    assert data_diff["totals"]["correct"] == 1

    res_query = client.get("/api/math/dashboard", query_string={"q": "池"})
    assert res_query.status_code == 200
    data_query = res_query.get_json()
    assert data_query["totals"]["answered"] == 1
    assert data_query["recentAttempts"][0]["questionId"] == "speed-1"

    sys.modules.pop("app.app", None)
