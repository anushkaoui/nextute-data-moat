import hashlib
import json
import math
import secrets
import sys
import uuid
from datetime import date, datetime, timedelta

import numpy as np
import psycopg

from .core import DATABASE_URL
from psycopg.rows import dict_row
from .synth import AS_OF

TENANT_SQL = "select set_config('app.institute_id', %s, true)"


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def fit_rasch(si, ii, y, n_s, n_i, iters=200, prior_b=2.0, damping=0.5, tol=1e-6):
    theta = np.zeros(n_s)
    b = np.zeros(n_i)
    prev_ll = -np.inf
    for it in range(iters):
        p = sigmoid(theta[si] - b[ii])
        g = y - p
        h = p * (1 - p)
        d_theta = (np.bincount(si, weights=g, minlength=n_s) - theta) / (
            np.bincount(si, weights=h, minlength=n_s) + 1.0)
        theta += damping * d_theta
        p = sigmoid(theta[si] - b[ii])
        g = y - p
        h = p * (1 - p)
        d_b = -(np.bincount(ii, weights=g, minlength=n_i) + b / prior_b**2) / (
            np.bincount(ii, weights=h, minlength=n_i) + 1.0 / prior_b**2)
        b += damping * d_b
        if it % 5 == 0:
            p = sigmoid(theta[si] - b[ii])
            eps = 1e-9
            cur = float(np.sum(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
            if abs(cur - prev_ll) < tol * abs(cur) and it > 20:
                prev_ll = cur
                break
            prev_ll = cur
    mu = float(np.mean(theta))
    theta = theta - mu
    b = b - mu
    p = sigmoid(theta[si] - b[ii])
    h = p * (1 - p)
    se_theta = 1.0 / np.sqrt(np.bincount(si, weights=h, minlength=n_s) + 1.0)
    se_b = 1.0 / np.sqrt(np.bincount(ii, weights=h, minlength=n_i) + 1.0 / prior_b**2)
    eps = 1e-9
    ll = float(np.sum(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
    return {
        "theta": theta, "b": b, "se_theta": se_theta, "se_b": se_b,
        "iterations": it + 1, "log_likelihood": ll,
    }


def topic_mastery(theta_g, b, y, w, kappa=8.0):
    est = theta_g
    for _ in range(30):
        p = sigmoid(est - b)
        grad = float(np.sum(w * (y - p)) + kappa * (theta_g - est))
        info = float(np.sum(w * p * (1 - p)) + kappa)
        step = grad / max(info, 1e-9)
        est += step
        if abs(step) < 1e-5:
            break
    return est, 1.0 / math.sqrt(max(info, 1e-9))


def fit_logistic(X, y, l2=1e-2, epochs=900, lr=0.25):
    n, d = X.shape
    w = np.zeros(d)
    b = float(np.log(max(y.mean(), 1e-4) / max(1 - y.mean(), 1e-4)))
    for _ in range(epochs):
        p = sigmoid(X @ w + b)
        grad_w = X.T @ (p - y) / n + l2 * w
        grad_b = float(np.mean(p - y))
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def predict(X, w, b):
    return sigmoid(X @ w + b)


def fit_platt(scores, y, l2=0.05):
    a, c = 1.0, 0.0
    for _ in range(300):
        p = sigmoid(a * scores + c)
        g = p - y
        h = p * (1 - p)
        a -= float(np.sum(g * scores) + l2 * a) / float(np.sum(h * scores * scores) + l2 + 1e-6)
        c -= float(np.sum(g)) / float(np.sum(h) + 1e-6)
    return float(np.clip(a, -8, 8)), float(np.clip(c, -20, 20))


def auc_score(y, s):
    y = np.asarray(y)
    s = np.asarray(s)
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def average_precision(y, s):
    y = np.asarray(y)
    order = np.argsort(-np.asarray(s))
    y = y[order]
    if y.sum() == 0:
        return float("nan")
    tp = np.cumsum(y)
    precision = tp / np.arange(1, len(y) + 1)
    return float(np.sum(precision * y) / y.sum())


def brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def percentile_10(y, s):
    k = max(1, int(round(0.1 * len(s))))
    order = np.argsort(-np.asarray(s))
    return float(np.asarray(y)[order[:k]].mean())


def split_indices(y, seed=7):
    rng = np.random.default_rng(seed)
    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]
    rng.shuffle(pos)
    rng.shuffle(neg)
    n_pos, n_neg = len(pos), len(neg)
    a = pos[: int(0.6 * n_pos)].tolist() + neg[: int(0.6 * n_neg)].tolist()
    b = pos[int(0.6 * n_pos): int(0.8 * n_pos)].tolist() + neg[int(0.6 * n_neg): int(0.8 * n_neg)].tolist()
    c = pos[int(0.8 * n_pos):].tolist() + neg[int(0.8 * n_neg):].tolist()
    return sorted(a), sorted(b), sorted(c)


def standardize(train, other):
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0)
    sd = np.where(sd < 1e-6, 1.0, sd)
    def apply(X):
        X = np.where(np.isnan(X), mu, X)
        return (X - mu) / sd
    return apply(train), apply(other), mu, sd


RISK_FEATURES = [
    "att_rate_28d", "att_rate_prev28d", "att_trend", "days_since_present",
    "tests_last3", "score_last", "score_delta", "mastery_mean", "mastery_min",
    "fee_overdue_k", "n_attendance",
]

RISK_LABELS = {
    "att_rate_28d": "attendance rate over the last 28 days",
    "att_rate_prev28d": "attendance rate in the previous 28 days",
    "att_trend": "change in attendance versus the previous month",
    "days_since_present": "days since last attended class",
    "tests_last3": "tests attended out of the last three",
    "score_last": "most recent mock score",
    "score_delta": "change in mock score",
    "mastery_mean": "average topic mastery",
    "mastery_min": "weakest topic mastery",
    "fee_overdue_k": "overdue fees (thousand rupees)",
    "n_attendance": "attendance records available",
}


def pct_ranks(values):
    n = len(values)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(n)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return 100.0 * (ranks + 0.5) / n


def build_risk_features(conn, as_of):
    students = {r["id"]: r for r in conn.execute(
        "select id, status, exit_date from student where deleted_at is null"
    ).fetchall()}
    att = conn.execute(
        "select ar.student_id, s.session_date, ar.status from attendance_record ar "
        "join attendance_session s on s.institute_id = ar.institute_id and s.id = ar.session_id "
        "where s.session_date <= %s", (as_of,),
    ).fetchall()
    by_student = {}
    for r in att:
        by_student.setdefault(r["student_id"], []).append((r["session_date"], r["status"]))
    scores = conn.execute(
        "select r.student_id, t.test_date, sum(r.marks_awarded) as marks, count(*) as n "
        "from response r join test t on t.institute_id = r.institute_id and t.id = r.test_id "
        "group by r.student_id, t.test_date"
    ).fetchall()
    by_test = {}
    for r in scores:
        pct = 100.0 * float(r["marks"]) / (4.0 * int(r["n"]))
        by_test.setdefault(r["student_id"], []).append((r["test_date"], pct))
    for k in by_test:
        by_test[k].sort()
    mastery = {}
    for r in conn.execute(
        "select student_id, avg(mastery_prob) as mean_m, min(mastery_prob) as min_m "
        "from mastery_snapshot where as_of = (select max(as_of) from mastery_snapshot) "
        "group by student_id"
    ).fetchall():
        mastery[r["student_id"]] = (float(r["mean_m"]), float(r["min_m"]))
    overdue = {}
    for r in conn.execute(
        "select fp.student_id, coalesce(sum(fi.amount_due - fi.amount_paid), 0) as due "
        "from fee_instalment fi join fee_plan fp on fp.institute_id = fi.institute_id and fp.id = fi.fee_plan_id "
        "where fi.due_date <= %s and fi.status <> 'paid' group by fp.student_id", (as_of,),
    ).fetchall():
        overdue[r["student_id"]] = float(r["due"])

    rows, labels, ids = [], [], []
    d28 = as_of - timedelta(days=28)
    d56 = as_of - timedelta(days=56)
    for sid, st in students.items():
        if st["exit_date"] is not None and st["exit_date"] <= as_of:
            continue
        recs = by_student.get(sid, [])
        recent = [x for x in recs if x[0] > d28]
        prev = [x for x in recs if d56 < x[0] <= d28]
        def rate(rs):
            if not rs:
                return np.nan
            return np.mean([1.0 if s[1] in ("present", "late") else 0.0 for s in rs])
        r28, rprev = rate(recent), rate(prev)
        present_dates = [x[0] for x in recs if x[1] in ("present", "late")]
        days_since = (as_of - max(present_dates)).days if present_dates else 60
        tests = by_test.get(sid, [])
        tests_last3 = min(3, sum(1 for t in tests if t[0] > as_of - timedelta(days=100)))
        last = tests[-1][1] if tests else np.nan
        prev_score = tests[-2][1] if len(tests) > 1 else np.nan
        m_mean, m_min = mastery.get(sid, (np.nan, np.nan))
        label_student = students[sid]
        withdrew = (
            label_student["status"] == "withdrawn"
            and label_student["exit_date"] is not None
            and as_of < label_student["exit_date"] <= as_of + timedelta(days=28)
        )
        rows.append([
            r28, rprev, (r28 - rprev) if not (np.isnan(r28) or np.isnan(rprev)) else np.nan,
            min(days_since, 60), tests_last3, last,
            (last - prev_score) if not (np.isnan(last) or np.isnan(prev_score)) else np.nan,
            m_mean, m_min, overdue.get(sid, 0.0) / 1000.0, len(recs),
        ])
        labels.append(1 if withdrew else 0)
        ids.append(sid)
    return np.array(rows, dtype=float), np.array(labels, dtype=int), ids


def run_for_institute(conn, institute_id, as_of=AS_OF, run_tag=None, report_count=15):
    conn.execute(TENANT_SQL, (str(institute_id),))
    conn.execute("delete from report where institute_id=%s", (institute_id,))
    conn.execute("delete from item_difficulty where institute_id=%s", (institute_id,))
    conn.execute("delete from mastery_snapshot where institute_id=%s", (institute_id,))
    conn.execute("delete from risk_snapshot where institute_id=%s", (institute_id,))
    conn.execute("delete from prediction_snapshot where institute_id=%s", (institute_id,))
    conn.execute("delete from model_version where institute_id=%s", (institute_id,))
    tag = run_tag or datetime.now().strftime("%Y%m%d%H%M%S")
    version = f"v{as_of.strftime('%Y%m%d')}-{tag}"

    resp = conn.execute(
        "select r.student_id, r.test_item_id, ti.item_id, i.topic_id, t.test_date, r.is_correct "
        "from response r join test_item ti on ti.institute_id = r.institute_id and ti.id = r.test_item_id "
        "join item i on i.institute_id = ti.institute_id and i.id = ti.item_id "
        "join test t on t.institute_id = r.institute_id and t.id = r.test_id "
        "where r.is_correct is not null and r.attempt_no = 1"
    ).fetchall()
    if not resp:
        return {"status": "no_data"}
    student_ids = sorted({r["student_id"] for r in resp})
    item_ids = sorted({r["item_id"] for r in resp})
    s_index = {v: i for i, v in enumerate(student_ids)}
    i_index = {v: i for i, v in enumerate(item_ids)}
    si = np.array([s_index[r["student_id"]] for r in resp])
    ii = np.array([i_index[r["item_id"]] for r in resp])
    y = np.array([1.0 if r["is_correct"] else 0.0 for r in resp])
    topic_of = {}
    for r in resp:
        topic_of[r["item_id"]] = r["topic_id"]
    fit = fit_rasch(si, ii, y, len(student_ids), len(item_ids))
    theta = fit["theta"]
    b = fit["b"]

    mv = conn.execute(
        "insert into model_version (institute_id, kind, version, trained_at, data_window, metrics, status) "
        "values (%s,'rasch',%s,now(),daterange(%s,%s,'[]'),%s,'active') returning id",
        (institute_id, version, date(2026, 4, 1), as_of + timedelta(days=1),
         psycopg.types.json.Jsonb({
             "n_students": len(student_ids), "n_items": len(item_ids), "n_responses": len(resp),
             "iterations": fit["iterations"], "log_likelihood": fit["log_likelihood"],
             "theta_sd": float(np.std(theta)), "b_mean": float(np.mean(b)),
             "b_sd": float(np.std(b)), "equating": "concurrent calibration, 10 common anchor items per test",
         })),
    ).fetchone()["id"]

    item_rows = []
    for item_id, idx in i_index.items():
        n_item = int(np.sum(ii == idx))
        status = "calibrated" if n_item >= 30 else "provisional"
        item_rows.append((institute_id, item_id, as_of, mv, float(b[idx]), float(fit["se_b"][idx]), n_item, status))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into item_difficulty (institute_id, item_id, as_of, model_version_id, difficulty, "
            "std_error, response_count, status) values (%s,%s,%s,%s,%s,%s,%s,%s) "
            "on conflict (institute_id, item_id, as_of, model_version_id) do nothing",
            item_rows,
        )

    resp_by_student_topic = {}
    for r, row_idx in zip(resp, range(len(resp))):
        key = (r["student_id"], r["topic_id"])
        resp_by_student_topic.setdefault(key, []).append(
            (float(y[row_idx]), float(r["test_date"].toordinal()), r["item_id"])
        )
    item_index = {v: i for i, v in enumerate(item_ids)}
    mastery_rows = []
    as_of_ord = as_of.toordinal()
    for (sid, topic_id), recs in resp_by_student_topic.items():
        ys = np.array([r[0] for r in recs])
        idxs = np.array([item_index[r[2]] for r in recs])
        days = np.array([as_of_ord - r[1] for r in recs])
        w = np.power(0.5, days / 120.0)
        est, unc = topic_mastery(theta[s_index[sid]], b[idxs], ys, w)
        bbar = float(np.mean(b[idxs]))
        mastery = sigmoid(est - bbar)
        mastery_rows.append((
            institute_id, sid, topic_id, as_of, mv, float(est), float(mastery), len(recs),
            float(unc), datetime.combine(date.fromordinal(int(max(r[1] for r in recs))), datetime.min.time()),
        ))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into mastery_snapshot (institute_id, student_id, topic_id, as_of, model_version_id, "
            "ability, mastery_prob, evidence_count, uncertainty, last_response_at) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing",
            mastery_rows,
        )

    risk_metrics = run_risk(conn, institute_id, as_of, mv, tag)
    perf_metrics = run_performance(conn, institute_id, as_of, mv, tag, student_ids, theta)
    rule_metrics = run_rule_risks(conn, institute_id, as_of, tag)
    reports = seed_reports(conn, institute_id, as_of, report_count)
    summary = {
        "institute_id": str(institute_id),
        "model_version": version,
        "rasch": {"students": len(student_ids), "items": len(item_ids), "responses": len(resp),
                  "theta_sd": float(np.std(theta)), "b_sd": float(np.std(b))},
        "mastery_rows": len(mastery_rows),
        "risk": risk_metrics,
        "performance": perf_metrics,
        "rule_risks": rule_metrics,
        "reports": reports,
    }
    return summary


def run_risk(conn, institute_id, as_of, model_version_id, tag):
    X, y, ids = build_risk_features(conn, as_of)
    if len(y) == 0 or y.sum() < 5:
        return {"status": "insufficient_labels", "n": int(len(y)), "positives": int(y.sum())}
    train, calib, test = split_indices(y)
    Xtr_raw, Xall_raw = X[train], X
    Xtr, Xall, mu, sd = standardize(Xtr_raw, Xall_raw)
    Xcal, Xtest = Xall[calib], Xall[test]
    w, b0 = fit_logistic(Xtr, y[train])
    raw_cal = Xcal @ w + b0
    a, c = fit_platt(raw_cal, y[calib])
    raw_test = Xtest @ w + b0
    p_test = sigmoid(a * raw_test + c)
    metrics = {
        "n": int(len(y)), "positives": int(y.sum()), "base_rate": float(y.mean()),
        "auc": auc_score(y[test], p_test), "pr_auc": average_precision(y[test], p_test),
        "brier": brier(y[test], p_test), "precision_at_10pct": percentile_10(y[test], p_test),
        "recall_at_10pct": None, "platt": {"a": float(a), "c": float(c)},
        "coefficients": {k: float(v) for k, v in zip(RISK_FEATURES, w)},
        "standardization": {"mean": [float(v) for v in mu], "sd": [float(v) for v in sd]},
        "intercept": float(b0), "horizon_days": 28,
        "split": {"train": len(train), "calib": len(calib), "test": len(test)},
    }
    k = max(1, int(round(0.1 * len(test))))
    order = np.argsort(-p_test)[:k]
    metrics["recall_at_10pct"] = float(y[test][order].sum() / max(y[test].sum(), 1))
    mv = conn.execute(
        "insert into model_version (institute_id, kind, version, trained_at, metrics, status) "
        "values (%s,'risk_disengagement',%s,now(),%s,'active') returning id",
        (institute_id, f"risk-{tag}", psycopg.types.json.Jsonb(metrics)),
    ).fetchone()["id"]

    p_all = sigmoid(a * (Xall @ w + b0) + c)
    feat_rows = []
    for i, sid in enumerate(ids):
        contrib = {k: float(w[j] * Xall[i, j]) for j, k in enumerate(RISK_FEATURES)}
        top = sorted(contrib.items(), key=lambda kv: -kv[1])[:3]
        reasons = []
        for key, val in top:
            if val <= 0:
                continue
            raw = X[i, RISK_FEATURES.index(key)]
            if key == "att_rate_28d":
                txt = f"attendance {raw * 100:.0f}% in the last 28 days"
            elif key == "att_trend":
                txt = f"attendance fell {abs(raw) * 100:.0f} points versus the previous month"
            elif key == "days_since_present":
                txt = f"no class attended for {raw:.0f} days"
            elif key == "tests_last3":
                txt = f"attended {raw:.0f} of the last 3 tests"
            elif key == "score_delta":
                txt = f"mock score fell {abs(raw):.0f} points"
            elif key == "score_last":
                txt = f"recent mock score {raw:.0f}%"
            elif key == "fee_overdue_k":
                txt = f"₹{raw * 1000:.0f} fees overdue"
            elif key == "mastery_min":
                txt = f"weakest topic mastery {raw * 100:.0f}%"
            elif key == "mastery_mean":
                txt = f"average topic mastery {raw * 100:.0f}%"
            else:
                txt = RISK_LABELS.get(key, key)
            reasons.append({"feature": key, "text": txt, "contribution": round(val, 3)})
        score = float(p_all[i])
        band = "high" if score >= 0.40 else ("medium" if score >= 0.18 else "low")
        suff = "ok" if X[i, RISK_FEATURES.index("n_attendance")] >= 10 else "low"
        feat_rows.append((
            institute_id, sid, "disengagement", as_of, 28, score, band,
            psycopg.types.json.Jsonb(reasons),
            psycopg.types.json.Jsonb({k: (None if np.isnan(v) else round(float(v), 4))
                                      for k, v in zip(RISK_FEATURES, X[i])}),
            suff, mv,
        ))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into risk_snapshot (institute_id, student_id, target, as_of, horizon_days, score, band, "
            "reasons, features, data_sufficiency, model_version_id) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing",
            feat_rows,
        )
    metrics["snapshots"] = len(feat_rows)
    metrics["bands"] = {b: sum(1 for r in feat_rows if r[6] == b) for b in ("high", "medium", "low")}
    conn.execute(
        "update model_version set metrics = %s where id = %s",
        (psycopg.types.json.Jsonb(metrics), mv),
    )
    return metrics


def run_performance(conn, institute_id, as_of, mv, tag, student_ids, theta):
    rows = conn.execute(
        "select r.student_id, t.test_date, sum(r.marks_awarded) as marks, count(*) as n "
        "from response r join test t on t.institute_id = r.institute_id and t.id = r.test_id "
        "group by r.student_id, t.test_date"
    ).fetchall()
    scores = {}
    for r in rows:
        scores.setdefault(r["student_id"], []).append(
            (r["test_date"], 100.0 * float(r["marks"]) / (4.0 * int(r["n"])))
        )
    for k in scores:
        scores[k].sort()
    s_index = {v: i for i, v in enumerate(student_ids)}
    feat, target, ids = [], [], []
    for sid, vals in scores.items():
        if len(vals) < 2 or sid not in s_index:
            continue
        hist = vals[:-1]
        prev = hist[-1][1]
        mean2 = float(np.mean([v[1] for v in hist[-2:]]))
        feat.append([prev, mean2, float(theta[s_index[sid]])])
        target.append(vals[-1][1])
        ids.append(sid)
    X = np.array(feat)
    y = np.array(target)
    if len(y) < 30:
        return {"status": "insufficient_data", "n": int(len(y))}
    rng = np.random.default_rng(11)
    perm = rng.permutation(len(y))
    n1, n2 = int(0.6 * len(y)), int(0.8 * len(y))
    tr, ca, te = perm[:n1], perm[n1:n2], perm[n2:]
    A = np.column_stack([np.ones(len(tr)), X[tr]])
    coef, *_ = np.linalg.lstsq(A, y[tr], rcond=None)
    def pred(Xs):
        return np.clip(np.column_stack([np.ones(len(Xs)), Xs]) @ coef, 0, 100)
    abs_cal = np.abs(y[ca] - pred(X[ca]))
    q80 = float(np.quantile(abs_cal, 0.8, method="higher"))
    p_test = pred(X[te])
    lo, hi = np.clip(p_test - q80, 0, 100), np.clip(p_test + q80, 0, 100)
    coverage = float(np.mean((y[te] >= lo) & (y[te] <= hi)))
    mae = float(np.mean(np.abs(y[te] - p_test)))
    metrics = {"n": int(len(y)), "mae": mae, "coverage_80": coverage,
               "coefficients": [float(v) for v in coef], "q80_abs": q80,
               "split": {"train": len(tr), "calib": len(ca), "test": len(te)}}
    pmv = conn.execute(
        "insert into model_version (institute_id, kind, version, trained_at, metrics, status) "
        "values (%s,'performance_percentile',%s,now(),%s,'active') returning id",
        (institute_id, f"perf-{tag}", psycopg.types.json.Jsonb(metrics)),
    ).fetchone()["id"]
    snap_rows = []
    allpred = pred(X)
    for i, sid in enumerate(ids):
        point = float(allpred[i])
        snap_rows.append((
            institute_id, sid, "internal_percentile", as_of, point,
            float(np.clip(point - q80, 0, 100)), float(np.clip(point + q80, 0, 100)),
            coverage, psycopg.types.json.Jsonb({
                "basis": "last mock, two-mock mean and Rasch ability",
                "note": "internal cohort percentile only; not a JEE/NEET rank",
            }),
            "ok" if len(scores[sid]) >= 2 else "low", pmv,
        ))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into prediction_snapshot (institute_id, student_id, kind, as_of, point, lower_bound, "
            "upper_bound, coverage, basis, data_sufficiency, model_version_id) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing",
            snap_rows,
        )
    metrics["snapshots"] = len(snap_rows)
    conn.execute("update model_version set metrics=%s where id=%s",
                 (psycopg.types.json.Jsonb(metrics), pmv))
    return metrics


def seed_reports(conn, institute_id, as_of, count):
    from .reports import generate_report
    rows = conn.execute(
        "select id from student where status = 'active' order by id limit %s", (count,)
    ).fetchall()
    made = 0
    for r in rows:
        for lang in ("en", "hi"):
            if generate_report(conn, r["id"], lang, as_of):
                made += 1
    return made


def run_rule_risks(conn, institute_id, as_of, tag):
    active = conn.execute(
        "select id from student where deleted_at is null and (exit_date is null or exit_date > %s)",
        (as_of,),
    ).fetchall()
    overdue = {}
    for r in conn.execute(
        "select fp.student_id, coalesce(sum(case when fi.due_date <= %s then fi.amount_due - fi.amount_paid else 0 end),0) as due, "
        "count(*) filter (where fi.paid_date is not null and fi.paid_date > fi.due_date + fi.grace_days) as late "
        "from fee_instalment fi join fee_plan fp on fp.institute_id = fi.institute_id and fp.id = fi.fee_plan_id "
        "group by fp.student_id", (as_of,),
    ).fetchall():
        overdue[r["student_id"]] = (float(r["due"]), int(r["late"]))
    perf = {r["student_id"]: r for r in conn.execute(
        "select distinct on (student_id) student_id, lower_bound from prediction_snapshot "
        "where kind='internal_percentile' order by student_id, as_of desc"
    ).fetchall()}
    mastery = {r["student_id"]: float(r["m"]) for r in conn.execute(
        "select student_id, min(mastery_prob) as m from mastery_snapshot "
        "where as_of = (select max(as_of) from mastery_snapshot) group by student_id"
    ).fetchall()}
    fee_mv = conn.execute(
        "insert into model_version (institute_id, kind, version, trained_at, metrics, status) "
        "values (%s,'risk_fee_default',%s,now(),%s,'active') returning id",
        (institute_id, f"fee-rule-{tag}", psycopg.types.json.Jsonb({
            "method": "rule_v1", "note": "transparent score; trained model needs 12+ months of default history"})),
    ).fetchone()["id"]
    fb_mv = conn.execute(
        "insert into model_version (institute_id, kind, version, trained_at, metrics, status) "
        "values (%s,'risk_falling_behind',%s,now(),%s,'active') returning id",
        (institute_id, f"fb-rule-{tag}", psycopg.types.json.Jsonb({
            "method": "rule_v1", "note": "uses the 80% percentile band lower bound and weakest topic mastery"})),
    ).fetchone()["id"]
    fee_rows, fb_rows = [], []
    for r in active:
        sid = r["id"]
        due, late = overdue.get(sid, (0.0, 0))
        fee_score = min(1.0, 0.7 * min(due / 45000.0, 1.0) + 0.3 * min(late / 5.0, 1.0))
        fee_reasons = []
        if due > 0:
            fee_reasons.append(f"₹{due:,.0f} overdue as of {as_of.isoformat()}")
        if late:
            fee_reasons.append(f"{late} instalment(s) paid after the grace period")
        if not fee_reasons:
            fee_reasons.append("no overdue instalments")
        fee_rows.append((
            institute_id, sid, "fee_default", as_of, 30, fee_score,
            "high" if fee_score >= 0.6 else ("medium" if fee_score >= 0.3 else "low"),
            psycopg.types.json.Jsonb([{"feature": "fees", "text": t, "contribution": None} for t in fee_reasons]),
            psycopg.types.json.Jsonb({"overdue": due, "late_instalments": late}),
            "ok" if sid in overdue else "low", fee_mv,
        ))
        if sid in perf and sid in mastery:
            low = float(perf[sid]["lower_bound"] or 0)
            weak = mastery[sid]
            score = min(1.0, 0.6 * max(0.0, (45 - low) / 45.0) + 0.4 * (1 - weak))
            reasons = [
                {"feature": "band", "text": f"80% internal percentile band starts at {low:.0f}", "contribution": None},
                {"feature": "mastery", "text": f"weakest topic mastery {weak * 100:.0f}%", "contribution": None},
            ]
            fb_rows.append((
                institute_id, sid, "falling_behind", as_of, 30, score,
                "high" if score >= 0.65 else ("medium" if score >= 0.4 else "low"),
                psycopg.types.json.Jsonb(reasons),
                psycopg.types.json.Jsonb({"band_lower": low, "weakest_mastery": weak}),
                "ok" if len(mastery) else "low", fb_mv,
            ))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into risk_snapshot (institute_id, student_id, target, as_of, horizon_days, score, band, "
            "reasons, features, data_sufficiency, model_version_id) values "
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing",
            fee_rows + fb_rows,
        )
    return {"fee_default": len(fee_rows), "falling_behind": len(fb_rows)}


def run_all(as_of=AS_OF, report_count=15):
    conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
    try:
        institutes = conn.execute("select id, name from list_institutes()").fetchall()
        out = []
        for inst in institutes:
            with conn.transaction():
                conn.execute(TENANT_SQL, (str(inst["id"]),))
                summary = run_for_institute(conn, inst["id"], as_of=as_of, report_count=report_count)
                summary["institute"] = inst["name"]
                out.append(summary)
                print(json.dumps(summary, indent=2, default=str))
        return out
    finally:
        conn.close()


if __name__ == "__main__":
    run_all()
