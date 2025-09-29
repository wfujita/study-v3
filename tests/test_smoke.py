import os
import json
import importlib


def test_routes_and_post(tmp_path, monkeypatch):
    # data ディレクトリは存在させておく（CIでも安全）
    os.makedirs("data", exist_ok=True)

    # app.app から Flask インスタンス 'app' を取り出す想定
    mod = importlib.import_module("app.app")
    flask_app = getattr(mod, "app", None)
    assert (
        flask_app is not None
    ), "app.app は Flask インスタンス 'app' を公開してください"

    client = flask_app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/admin").status_code == 200
    assert client.get("/math.html").status_code == 200

    payload = {"_smoke": True}
    r = client.post("/api/results", json=payload)
    assert r.status_code in (200, 201, 204)

    path = os.path.join("data", "results.ndjson")
    assert os.path.exists(path)
    with open(path, "rb") as f:
        last = f.readlines()[-1]
    json.loads(last)  # NDJSON でパースできること

    math_res = client.get("/data/math_questions.json")
    assert math_res.status_code == 200
    math_payload = json.loads(math_res.data)
    assert isinstance(math_payload.get("questions"), list)
    field_questions = [
        q for q in math_payload["questions"] if isinstance(q.get("fields"), list)
    ]
    assert field_questions, "fields を持つ問題が少なくとも1問あること"
    for q in field_questions:
        answers = q.get("answers") or []
        assert answers, "fields を持つ問題は少なくとも1つの answers を持つこと"
        assert all(
            isinstance(ans, dict) for ans in answers
        ), "fields を持つ問題の answers はオブジェクト形式に統一されていること"
