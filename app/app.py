from flask import Flask, request, send_from_directory, jsonify
from datetime import datetime, timezone, timedelta
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
STATIC_DATA_DIR = os.path.join(STATIC_DIR, "data")
RUNTIME_DATA_DIR = os.getenv(
    "DATA_DIR", os.path.join(os.path.dirname(BASE_DIR), "data")
)  # 既定: リポジトリ直下 ./data

app = Flask(__name__, static_folder="static", static_url_path="")


# ===== 静的ページ =====
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/admin")
def admin_page():
    return send_from_directory("static", "admin.html")


# 出題ファイル（フロントは /data/questions.json を参照）
@app.get("/data/questions.json")
def get_questions():
    # ← 移動後は static/data/ から配信
    return send_from_directory(STATIC_DATA_DIR, "questions.json")


# ===== 受信（結果保存） =====
@app.post("/api/results")
def save_results():
    rec = request.get_json(force=True, silent=True) or {}
    rec["receivedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    os.makedirs(RUNTIME_DATA_DIR, exist_ok=True)
    path = os.path.join(RUNTIME_DATA_DIR, "results.ndjson")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return jsonify({"ok": True}), 201


# ====== 管理ダッシュボード用ユーティリティ ======
def load_questions_map():
    """
    static/data/questions.json を読み、id -> {jp,en,unit,type} にまとめる。
    並べ替え（questions）と単語（vocab）の両方をサポート。
    """
    qmap = {}
    path = os.path.join(STATIC_DATA_DIR, "questions.json")
    if not os.path.exists(path):
        return qmap
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception:
        return qmap

    for q in data.get("questions") or []:
        qid = q.get("id")
        if qid:
            qmap[qid] = {
                "id": qid,
                "jp": q.get("jp"),
                "en": q.get("en"),
                "unit": q.get("unit"),
                "type": "reorder",
            }
    for v in data.get("vocab") or []:
        qid = v.get("id")
        if qid:
            qmap[qid] = {
                "id": qid,
                "jp": v.get("jp"),
                "en": v.get("en"),
                "unit": v.get("unit"),
                "type": "vocab",
            }
    return qmap


def iter_results():
    """保存済みの results.ndjson を配列で返す（1行=1セッション）。"""
    path = os.path.join(RUNTIME_DATA_DIR, "results.ndjson")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


# ====== /admin 用 API ======
@app.get("/api/admin/users")
def admin_users():
    res = iter_results()
    users = {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for r in res:
        mode = r.get("mode") or "normal"
        session_at = r.get("endedAt") or r.get("receivedAt")
        try:
            session_dt = (
                datetime.fromisoformat(session_at.replace("Z", "+00:00"))
                if session_at
                else None
            )
        except Exception:
            session_dt = None
        if mode == "review" or not session_dt or session_dt < cutoff:
            continue

        u = r.get("user") or "guest"
        users.setdefault(
            u,
            {
                "user": u,
                "sessions": 0,
                "lastAt": None,
                "answered": 0,
                "correct": 0,
            },
        )
        users[u]["sessions"] += 1
        last = session_at or ""
        users[u]["lastAt"] = max(users[u]["lastAt"] or "", last)
        ans = r.get("answered") or []
        users[u]["answered"] += (
            len(ans) if isinstance(ans, list) else (r.get("total") or 0)
        )
        users[u]["correct"] += r.get("correct") or sum(
            1 for a in ans if a.get("correct")
        )
    out = sorted(users.values(), key=lambda x: (x["lastAt"] or ""), reverse=True)
    return jsonify(out)


@app.get("/api/admin/summary")
def admin_summary():
    user = request.args.get("user")  # "__all__" で全体
    unit = request.args.get("unit") or ""
    qtext = (request.args.get("q") or "").lower()
    mode = request.args.get("mode") or "normal"

    qmap = load_questions_map()
    res = iter_results()

    def match_user(r):
        return (user in (None, "", "__all__")) or (r.get("user", "guest") == user)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    answered_all = []
    sessions = []
    for r in res:
        if not match_user(r):
            continue
        if mode == "review":
            ans = r.get("reviewed") or []
        else:
            ans = [
                a
                for a in (r.get("answered") or [])
                if (a.get("mode") or r.get("mode") or "normal") != "review"
            ]
        if not isinstance(ans, list):
            ans = []
        for a in ans:
            at_str = a.get("at") or r.get("endedAt") or r.get("receivedAt")
            try:
                at_dt = (
                    datetime.fromisoformat(at_str.replace("Z", "+00:00"))
                    if at_str
                    else None
                )
            except Exception:
                at_dt = None
            if not at_dt or at_dt < cutoff:
                continue
            qid = a.get("id")
            qm = qmap.get(qid, {})
            item = {
                "user": r.get("user", "guest"),
                "id": qid,
                "unit": (a.get("unit") or qm.get("unit") or ""),
                "jp": qm.get("jp"),
                "en": qm.get("en"),
                "type": (a.get("type") or qm.get("type") or ""),
                "correct": bool(a.get("correct")),
                "userAnswer": a.get("userAnswer"),
                "at": at_str,
            }
            if unit and item["unit"] != unit:
                continue
            if qtext:
                hay = " ".join(
                    str(x or "")
                    for x in [item["id"], item["jp"], item["en"], item["userAnswer"]]
                ).lower()
                if qtext not in hay:
                    continue
            answered_all.append(item)
        session_at = r.get("endedAt") or r.get("receivedAt")
        try:
            session_dt = (
                datetime.fromisoformat(session_at.replace("Z", "+00:00"))
                if session_at
                else None
            )
        except Exception:
            session_dt = None
        if session_dt and session_dt >= cutoff and ans:
            sessions.append(
                {
                    "user": r.get("user", "guest"),
                    "endedAt": r.get("endedAt"),
                    "total": len(ans),
                    "correct": sum(1 for a in ans if a.get("correct")),
                    "accuracy": (
                        (sum(1 for a in ans if a.get("correct")) / len(ans) * 100)
                        if len(ans)
                        else 0
                    ),
                    "mode": mode,
                    "qType": r.get("qType"),
                    "setIndex": r.get("setIndex"),
                    "seconds": r.get("seconds", 0),
                }
            )

    totals = {
        "sessions": len(sessions),
        "answered": len(answered_all),
        "correct": sum(1 for a in answered_all if a["correct"]),
    }

    by_unit = {}
    for a in answered_all:
        u = a.get("unit") or ""
        d = by_unit.setdefault(u, {"unit": u, "answered": 0, "correct": 0, "wrong": 0})
        d["answered"] += 1
        if a["correct"]:
            d["correct"] += 1
        else:
            d["wrong"] += 1
    by_unit_arr = sorted(by_unit.values(), key=lambda x: (-x["answered"], x["unit"]))

    by_q = {}
    for a in answered_all:
        qid = a.get("id") or "(no-id)"
        d = by_q.setdefault(
            qid,
            {
                "id": qid,
                "unit": a.get("unit"),
                "jp": a.get("jp"),
                "en": a.get("en"),
                "answered": 0,
                "correct": 0,
                "wrong": 0,
                "lastAt": None,
            },
        )
        d["answered"] += 1
        if a["correct"]:
            d["correct"] += 1
        else:
            d["wrong"] += 1
        d["lastAt"] = max(d["lastAt"] or "", a.get("at") or "")
    top_missed = sorted(
        by_q.values(), key=lambda x: (x["wrong"], x["answered"]), reverse=True
    )

    recent = sorted(answered_all, key=lambda x: x.get("at") or "", reverse=True)[:100]

    question_stats = sorted(by_q.values(), key=lambda x: (x["id"] or ""))

    return jsonify(
        {
            "totals": totals,
            "byUnit": by_unit_arr,
            "topMissed": top_missed,
            "recentAnswers": recent,
            "questionStats": question_stats,
            "sessions": sorted(
                sessions, key=lambda x: x["endedAt"] or "", reverse=True
            )[:100],
        }
    )


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
def devtools_stub():
    return jsonify({}), 200


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))  # 既定8000（80はroot権限が必要）
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(host=host, port=port, debug=debug)
