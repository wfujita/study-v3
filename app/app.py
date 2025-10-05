from flask import Flask, request, send_from_directory, jsonify
from datetime import datetime, timezone, timedelta
import os
import json

import app.stage_tracker as stage_tracker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
STATIC_DATA_DIR = os.path.join(STATIC_DIR, "data")
RUNTIME_DATA_DIR = os.getenv(
    "DATA_DIR", os.path.join(os.path.dirname(BASE_DIR), "data")
)  # 既定: リポジトリ直下 ./data
DEFAULT_SUBJECT = "english"

app = Flask(__name__, static_folder="static", static_url_path="")


# ===== ヘルパー =====
def normalize_subject(value):
    value = (value or "").strip().lower()
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_"))
    return cleaned or DEFAULT_SUBJECT


def subject_static_dir(subject: str) -> str:
    return os.path.join(STATIC_DATA_DIR, normalize_subject(subject))


def subject_runtime_dir(subject: str) -> str:
    return os.path.join(RUNTIME_DATA_DIR, normalize_subject(subject))


# ===== 静的ページ =====
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/admin")
def admin_page():
    return send_from_directory("static", "admin.html")


# 出題ファイル（フロントは /data/<subject>/questions.json を参照）
@app.get("/data/<subject>/questions.json")
def get_subject_questions(subject):
    directory = subject_static_dir(subject)
    path = os.path.join(directory, "questions.json")
    if not os.path.exists(path):
        return jsonify({"error": "subject not found"}), 404
    return send_from_directory(directory, "questions.json")


@app.get("/data/questions.json")
def get_questions():
    # 後方互換用: 既定教科の問題を返す
    return get_subject_questions(DEFAULT_SUBJECT)


# ===== 受信（結果保存） =====
@app.post("/api/results")
def save_results():
    rec = request.get_json(force=True, silent=True) or {}
    subject = normalize_subject(rec.get("subject"))
    rec["subject"] = subject
    rec["receivedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    target_dir = subject_runtime_dir(subject)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, "results.ndjson")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    try:
        stage_tracker.update_store_from_session(target_dir, rec)
    except Exception:
        app.logger.exception("failed to update stage cache for subject=%s", subject)

    return jsonify({"ok": True}), 201


# ====== 管理ダッシュボード用ユーティリティ ======
def load_questions_map(subject: str = DEFAULT_SUBJECT):
    """
    static/data/questions.json を読み、id -> {jp,en,unit,type} にまとめる。
    並べ替え（questions）と単語（vocab）の両方をサポート。
    """
    qmap = {}
    path = os.path.join(subject_static_dir(subject), "questions.json")
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


def iter_results(subject: str = DEFAULT_SUBJECT):
    """保存済みの results.ndjson を配列で返す（1行=1セッション）。"""
    path = os.path.join(subject_runtime_dir(subject), "results.ndjson")
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


def _accuracy_pct(correct: int, answered: int) -> float:
    if not answered:
        return 0.0
    try:
        return float(correct) / float(answered) * 100.0
    except Exception:
        return 0.0


def _is_math_record(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    mode = record.get("mode") or ""
    if mode.lower() != "math-drill":
        return False
    answered = record.get("answered")
    return isinstance(answered, list) and bool(answered)


@app.get("/api/math/accuracy")
def math_accuracy():
    """数学演習モードの正答率を返す。"""

    subject = normalize_subject(request.args.get("subject") or "math")
    user_filter = (request.args.get("user") or "").strip()

    results = iter_results(subject)

    totals_answered = 0
    totals_correct = 0
    by_user = {}
    by_question = {}

    for record in results:
        if not _is_math_record(record):
            continue
        user = record.get("user") or "guest"
        if user_filter and user != user_filter:
            continue
        answered_list = record.get("answered") or []
        for ans in answered_list:
            if not isinstance(ans, dict):
                continue
            totals_answered += 1
            is_correct = bool(ans.get("correct"))
            if is_correct:
                totals_correct += 1

            user_summary = by_user.setdefault(
                user, {"user": user, "answered": 0, "correct": 0}
            )
            user_summary["answered"] += 1
            if is_correct:
                user_summary["correct"] += 1

            qid_raw = ans.get("id")
            prompt = ans.get("prompt") or ""
            qid = str(qid_raw) if qid_raw not in (None, "") else None
            question_key = (qid or "", prompt)
            question_summary = by_question.setdefault(
                question_key,
                {
                    "id": qid,
                    "prompt": prompt,
                    "answered": 0,
                    "correct": 0,
                },
            )
            question_summary["answered"] += 1
            if is_correct:
                question_summary["correct"] += 1

    totals = {
        "answered": totals_answered,
        "correct": totals_correct,
        "accuracy": _accuracy_pct(totals_correct, totals_answered),
    }

    by_user_arr = []
    for summary in by_user.values():
        summary["accuracy"] = _accuracy_pct(
            summary.get("correct", 0), summary.get("answered", 0)
        )
        by_user_arr.append(summary)
    by_user_arr.sort(key=lambda x: x.get("user") or "")

    by_question_arr = []
    for summary in by_question.values():
        summary["accuracy"] = _accuracy_pct(
            summary.get("correct", 0), summary.get("answered", 0)
        )
        by_question_arr.append(summary)
    by_question_arr.sort(key=lambda x: (x.get("id") or "", x.get("prompt") or ""))

    payload = {
        "subject": subject,
        "totals": totals,
        "byUser": by_user_arr,
        "byQuestion": by_question_arr,
    }

    if user_filter:
        payload["userFilter"] = user_filter

    return jsonify(payload)


@app.get("/api/stats")
def question_stat():
    user = request.args.get("user") or ""
    qid = request.args.get("id") or ""
    subject = normalize_subject(request.args.get("subject"))
    if not user or not qid:
        return jsonify({"answered": 0, "correct": 0, "streak": 0, "stage": "F"})

    runtime_dir = subject_runtime_dir(subject)
    store = stage_tracker.load_store(runtime_dir)
    state = stage_tracker.get_question_state(store, user, qid)
    cached_results = None

    if state is None:
        cached_results = iter_results(subject)
        if cached_results:
            store = stage_tracker.rebuild_store(runtime_dir, cached_results)
            state = stage_tracker.get_question_state(store, user, qid)

    if state is not None:
        payload = {
            "answered": int(state.get("answered") or 0),
            "correct": int(state.get("correct") or 0),
            "streak": int(state.get("streak") or 0),
            "lastWrongAt": state.get("lastWrongAt"),
            "lastCorrectAt": state.get("lastCorrectAt"),
            "stage": state.get("stage") or "F",
            "nextDueAt": state.get("nextDueAt"),
        }
        return jsonify(payload)

    results = cached_results if cached_results is not None else iter_results(subject)

    def parse_iso(dt_str):
        if not dt_str:
            return None
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    attempts = []
    last_wrong_at = None
    last_wrong_dt = None
    last_correct_at = None
    last_correct_dt = None

    for r in results:
        if r.get("user") != user:
            continue
        ans = r.get("answered") or []
        for a in ans:
            if (a.get("mode") or r.get("mode") or "normal") == "review":
                continue
            if str(a.get("id") or "") != qid:
                continue
            at = a.get("at") or r.get("endedAt") or r.get("receivedAt") or ""
            is_correct = bool(a.get("correct"))
            attempts.append({"correct": is_correct, "at": at})

            at_dt = parse_iso(at)
            if not at_dt:
                continue
            if is_correct:
                if not last_correct_dt or at_dt > last_correct_dt:
                    last_correct_dt = at_dt
                    last_correct_at = at
            else:
                if not last_wrong_dt or at_dt > last_wrong_dt:
                    last_wrong_dt = at_dt
                    last_wrong_at = at

    attempts.sort(key=lambda x: x["at"] or "")
    total = len(attempts)
    correct = sum(1 for a in attempts if a["correct"])
    streak = 0
    for a in reversed(attempts):
        if a["correct"]:
            streak += 1
        else:
            break

    return jsonify(
        {
            "answered": total,
            "correct": correct,
            "streak": streak,
            "lastWrongAt": last_wrong_at,
            "lastCorrectAt": last_correct_at,
            "stage": "F",
            "nextDueAt": None,
        }
    )


# ====== /admin 用 API ======
@app.get("/api/admin/users")
def admin_users():
    subject = normalize_subject(request.args.get("subject"))
    res = iter_results(subject)
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
    qtype = request.args.get("show") or "all"
    subject = normalize_subject(request.args.get("subject"))

    qmap = load_questions_map(subject)
    res = iter_results(subject)

    runtime_dir = subject_runtime_dir(subject)
    stage_store = stage_tracker.load_store(runtime_dir)
    if not stage_store and res:
        stage_store = stage_tracker.rebuild_store(runtime_dir, res)

    def match_user(r):
        return (user in (None, "", "__all__")) or (r.get("user", "guest") == user)

    def parse_iso(dt_str):
        if not dt_str:
            return None
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    answered_all = []
    sessions = []
    attempts_by_q = {}

    review_sessions = {}
    for r in res:
        mode_r = r.get("mode") or "normal"
        if mode_r != "review":
            continue
        ended_str = r.get("endedAt") or r.get("receivedAt")
        ended_dt = parse_iso(ended_str)
        if not ended_dt:
            continue
        key = (r.get("user", "guest"), r.get("setIndex"))
        if key[1] is None:
            continue
        review_sessions.setdefault(key, []).append(ended_dt)

    for arr in review_sessions.values():
        arr.sort()
    for r in res:
        if not match_user(r):
            continue
        if mode == "review":
            ans_all = r.get("reviewed") or []
        else:
            ans_all = [
                a
                for a in (r.get("answered") or [])
                if (a.get("mode") or r.get("mode") or "normal") != "review"
            ]
        if not isinstance(ans_all, list):
            ans_all = []
        ans = ans_all

        # 表示タイプ（単語/並べ替え）で絞り込み
        if qtype in ("vocab", "reorder"):
            filtered = []
            for a in ans_all:
                qm = qmap.get(a.get("id")) or {}
                atype = a.get("type") or qm.get("type") or ""
                if atype == qtype:
                    filtered.append(a)
            ans = filtered
        else:
            ans = ans_all

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
            attempts_by_q.setdefault(qid or "(no-id)", []).append(
                (at_str or "", bool(a.get("correct")))
            )
        session_at = r.get("endedAt") or r.get("receivedAt")
        session_dt = parse_iso(session_at)
        started_dt = None
        started_iso = None
        if session_dt is not None:
            seconds_val = r.get("seconds")
            if seconds_val is not None:
                try:
                    started_dt = session_dt - timedelta(seconds=float(seconds_val))
                except Exception:
                    started_dt = None
            if started_dt is None:
                earliest = None
                for a in ans_all:
                    at_dt = parse_iso(a.get("at"))
                    if at_dt and (earliest is None or at_dt < earliest):
                        earliest = at_dt
                started_dt = earliest
            if started_dt:
                started_iso = (
                    started_dt.astimezone(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )

        if session_dt and session_dt >= cutoff and ans:
            review_done = False
            if (r.get("mode") or "normal") != "review":
                key = (r.get("user", "guest"), r.get("setIndex"))
                for rev_dt in review_sessions.get(key, []):
                    if rev_dt >= session_dt:
                        review_done = True
                        break
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
                    "startedAt": started_iso,
                    "reviewDone": review_done,
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

    streaks = {}
    for qid, arr in attempts_by_q.items():
        arr.sort(key=lambda x: x[0])
        streak = 0
        for _, ok in reversed(arr):
            if ok:
                streak += 1
            else:
                break
        streaks[qid] = streak

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
                "type": a.get("type"),
                "answered": 0,
                "correct": 0,
                "wrong": 0,
                "lastAt": None,
                "streak": 0,
            },
        )
        d["answered"] += 1
        if a["correct"]:
            d["correct"] += 1
        else:
            d["wrong"] += 1
        d["lastAt"] = max(d["lastAt"] or "", a.get("at") or "")
        d["streak"] = streaks.get(qid, 0)
    top_missed = sorted(
        by_q.values(), key=lambda x: (x["wrong"], x["answered"]), reverse=True
    )

    recent = sorted(answered_all, key=lambda x: x.get("at") or "", reverse=True)[:100]

    question_stats = sorted(by_q.values(), key=lambda x: (x["id"] or ""))

    stage_buckets = {}
    selected_user = user not in (None, "", "__all__")

    if selected_user:
        normalized_user = (user or "").strip() or "guest"
        for item in question_stats:
            state = stage_tracker.get_question_state(stage_store, normalized_user, item.get("id"))
            if state:
                item["stage"] = state.get("stage")
                item["nextDueAt"] = state.get("nextDueAt")
            else:
                item["stage"] = None
                item["nextDueAt"] = None

        user_bucket = {}
        if isinstance(stage_store, dict):
            user_bucket = stage_store.get(normalized_user) or {}
            if not isinstance(user_bucket, dict):
                user_bucket = {}

        for stage_name in stage_tracker.STAGE_SEQUENCE:
            bucket_items = []
            for qid, state in user_bucket.items():
                if not isinstance(state, dict):
                    continue
                state_stage = state.get("stage") or ""
                if state_stage != stage_name:
                    continue
                meta = qmap.get(qid) or {}
                bucket_items.append(
                    {
                        "id": qid,
                        "stage": state_stage,
                        "nextDueAt": state.get("nextDueAt"),
                        "jp": meta.get("jp"),
                        "en": meta.get("en"),
                        "unit": meta.get("unit"),
                        "type": meta.get("type"),
                    }
                )

            def next_due_sort_key(item):
                due = item.get("nextDueAt")
                if not due:
                    return (1, "")
                return (0, due)

            bucket_items.sort(key=next_due_sort_key)
            stage_buckets[stage_name] = bucket_items
    else:
        for item in question_stats:
            item["stage"] = None
            item["nextDueAt"] = None

    return jsonify(
        {
            "totals": totals,
            "byUnit": by_unit_arr,
            "topMissed": top_missed,
            "recentAnswers": recent,
            "questionStats": question_stats,
            "stageBuckets": stage_buckets,
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
