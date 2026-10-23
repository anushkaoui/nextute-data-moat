"""Reproducible early-model demonstration on synthetic data.

This is the optional Round 1 artefact: Rasch/1PL recovery and a
time-split dropout baseline. It deliberately uses only numpy so it runs
in a minimal environment.

Usage:
    python3 scripts/run_early_model.py

Outputs:
    docs/early_model_results.json
    docs/early_model_results.md
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SEED = 20260401


# ---------------------------------------------------------------- utilities
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def auc_score(y, s):
    y = np.asarray(y)
    s = np.asarray(s)
    pos = y == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
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


def top_k(y, s, frac=0.10):
    k = max(1, int(round(frac * len(s))))
    order = np.argsort(-np.asarray(s))[:k]
    return float(np.asarray(y)[order].mean()), float(np.asarray(s)[order].mean())


def calibration_table(y, p, bins=5):
    y = np.asarray(y)
    p = np.asarray(p)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.sum() == 0:
            continue
        out.append({
            "bin": f"{lo:.1f}-{hi:.1f}",
            "n": int(m.sum()),
            "mean_predicted": round(float(p[m].mean()), 4),
            "observed_rate": round(float(y[m].mean()), 4),
        })
    return out


# ---------------------------------------------------------------- Rasch
def fit_rasch(si, ii, y, n_s, n_i, iters=300, prior_b=2.0, damping=0.5):
    theta = np.zeros(n_s)
    b = np.zeros(n_i)
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
        d_b = -(np.bincount(ii, weights=g, minlength=n_i) + b / prior_b ** 2) / (
            np.bincount(ii, weights=h, minlength=n_i) + 1.0 / prior_b ** 2)
        b += damping * d_b

        if it > 20 and it % 10 == 0:
            p = sigmoid(theta[si] - b[ii])
            ll = float(np.sum(y * np.log(p + 1e-9) + (1 - y) * np.log(1 - p + 1e-9)))
            if it > 20 and abs(ll - getattr(fit_rasch, "_prev", -np.inf)) < 1e-7:
                break
            fit_rasch._prev = ll

    mu = float(theta.mean())
    theta -= mu
    b -= mu
    p = sigmoid(theta[si] - b[ii])
    h = p * (1 - p)
    se_theta = 1.0 / np.sqrt(np.bincount(si, weights=h, minlength=n_s) + 1.0)
    return theta, b, se_theta, it + 1


def rasch_experiment(rng):
    n_students = 1_200
    n_items = 60
    per_student = 35

    theta_true = rng.normal(0.0, 1.0, n_students)
    b_true = rng.normal(0.0, 1.0, n_items)

    si, ii, yy = [], [], []
    for s in range(n_students):
        items = rng.choice(n_items, size=per_student, replace=False)
        p = sigmoid(theta_true[s] - b_true[items])
        resp = (rng.random(per_student) < p).astype(float)
        si.extend([s] * per_student)
        ii.extend(items.tolist())
        yy.extend(resp.tolist())

    si = np.asarray(si)
    ii = np.asarray(ii)
    yy = np.asarray(yy)
    theta_hat, b_hat, se_theta, iters = fit_rasch(si, ii, yy, n_students, n_items)

    return {
        "n_students": n_students,
        "n_items": n_items,
        "n_responses": int(len(yy)),
        "theta_correlation": round(float(np.corrcoef(theta_true, theta_hat)[0, 1]), 4),
        "b_correlation": round(float(np.corrcoef(b_true, b_hat)[0, 1]), 4),
        "theta_rmse": round(float(np.sqrt(np.mean((theta_true - theta_hat) ** 2))), 4),
        "b_rmse": round(float(np.sqrt(np.mean((b_true - b_hat) ** 2))), 4),
        "mean_se_theta": round(float(se_theta.mean()), 4),
        "iterations": int(iters),
    }


# ---------------------------------------------------------------- dropout
FEATURE_NAMES = [
    "att_rate_28d",
    "att_rate_prev28d",
    "att_trend",
    "days_since_present",
    "tests_last3",
    "score_last",
    "score_delta",
    "mastery_mean",
    "fee_overdue_k",
]


def make_cohort(rng, n, intercept, cohort_id):
    theta = rng.normal(0.0, 1.0, n)
    att = np.clip(rng.normal(0.78, 0.13, n), 0.15, 1.0)
    trend = rng.normal(-0.01, 0.09, n)
    att_prev = np.clip(att - trend + rng.normal(0.0, 0.04, n), 0.1, 1.0)
    score = 50.0 + 11.0 * theta + rng.normal(0.0, 8.0, n)
    score_delta = -18.0 * trend + rng.normal(0.0, 7.0, n)
    days_since = np.clip(rng.exponential(8.0, n) + (1.0 - att) * 18.0, 0, 60)
    tests = rng.binomial(3, np.clip(att + 0.05, 0.05, 0.98))
    mastery = sigmoid(0.9 * theta + rng.normal(0.0, 0.28, n))
    overdue = rng.binomial(1, np.clip(0.05 + 0.18 * (1.0 - att), 0.0, 0.6))
    overdue_k = overdue * rng.uniform(2.0, 18.0, n)

    logit = (
        intercept
        - 4.2 * att
        - 1.1 * (att_prev - att)
        - 0.035 * score_delta
        + 0.028 * days_since
        - 0.35 * tests
        + 0.85 * overdue
        - 0.9 * mastery
        + 0.18 * rng.normal(0.0, 1.0, n)
    )
    p = sigmoid(logit)
    y = (rng.random(n) < p).astype(int)

    X = np.column_stack([att, att_prev, att, 1.0 - att_prev, days_since,
                         tests, score, score_delta, mastery, overdue_k])
    # remove the redundant first feature so columns match FEATURE_NAMES
    X = np.column_stack([att, att_prev, att_prev - att, days_since,
                         tests, score, score_delta, mastery, overdue_k])

    # measurement noise and missingness
    X[:, 0] = np.clip(X[:, 0] + rng.normal(0.0, 0.025, n), 0, 1)
    X[:, 1] = np.clip(X[:, 1] + rng.normal(0.0, 0.025, n), 0, 1)
    X[:, 3] = np.clip(X[:, 3] + rng.normal(0.0, 2.0, n), 0, 90)
    X[:, 6] = X[:, 6] + rng.normal(0.0, 2.0, n)
    mask = rng.random(X.shape) < 0.05
    X[mask] = np.nan

    return X, y, cohort_id


def fit_logistic(X, y, l2=0.05, epochs=1500, lr=0.20):
    n, d = X.shape
    w = np.zeros(d)
    b = math.log(max(y.mean(), 1e-4) / max(1.0 - y.mean(), 1e-4))
    for _ in range(epochs):
        p = sigmoid(X @ w + b)
        w -= lr * (X.T @ (p - y) / n + l2 * w)
        b -= lr * float(np.mean(p - y))
    return w, b


def fit_platt(scores, y, l2=0.05):
    a, c = 1.0, 0.0
    for _ in range(500):
        p = sigmoid(a * scores + c)
        g = p - y
        h = p * (1 - p)
        a -= float(np.sum(g * scores) + l2 * a) / float(np.sum(h * scores * scores) + l2 + 1e-6)
        c -= float(np.sum(g)) / float(np.sum(h) + 1e-6)
    return float(a), float(c)


def standardize(train, others):
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0)
    sd = np.where(sd < 1e-8, 1.0, sd)

    def apply(X):
        X = np.where(np.isnan(X), mu, X)
        return (X - mu) / sd

    return apply(train), [apply(x) for x in others], mu, sd


def dropout_experiment(rng):
    # Time-like cohorts: train on earliest, calibrate on middle, test on latest.
    X1, y1, _ = make_cohort(rng, 800, 1.55, 1)
    X2, y2, _ = make_cohort(rng, 800, 1.45, 2)
    X3, y3, _ = make_cohort(rng, 800, 1.60, 3)

    Xtr, (Xcal, Xte), mu, sd = standardize(X1, [X2, X3])
    w, b = fit_logistic(Xtr, y1)
    raw_cal = sigmoid(Xcal @ w + b)
    raw_te = sigmoid(Xte @ w + b)
    a, c = fit_platt(np.log(np.clip(raw_cal, 1e-6, 1 - 1e-6) /
                            np.clip(1 - raw_cal, 1e-6, 1)), y2)
    cal_te = sigmoid(a * np.log(np.clip(raw_te, 1e-6, 1 - 1e-6) /
                                np.clip(1 - raw_te, 1e-6, 1)) + c)

    precision10, _ = top_k(y3, cal_te, 0.10)
    return {
        "train_n": int(len(y1)),
        "calibration_n": int(len(y2)),
        "test_n": int(len(y3)),
        "train_base_rate": round(float(y1.mean()), 4),
        "calibration_base_rate": round(float(y2.mean()), 4),
        "test_base_rate": round(float(y3.mean()), 4),
        "auc": round(auc_score(y3, cal_te), 4),
        "pr_auc": round(average_precision(y3, cal_te), 4),
        "brier": round(brier(y3, cal_te), 4),
        "precision_at_10pct": round(precision10, 4),
        "platt_a": round(a, 4),
        "platt_c": round(c, 4),
        "calibration": calibration_table(y3, cal_te),
        "feature_weights": {k: round(float(v), 4) for k, v in zip(FEATURE_NAMES, w)},
    }


def main():
    rng = np.random.default_rng(SEED)
    rasch = rasch_experiment(rng)
    dropout = dropout_experiment(rng)

    results = {
        "seed": SEED,
        "data": "synthetic; no real student data",
        "caveat": (
            "These are synthetic-data results. The dropout labels contain a designed "
            "signal and measurement noise. They validate the pipeline and time-split "
            "evaluation, not real-world effectiveness."
        ),
        "rasch": rasch,
        "dropout": dropout,
    }

    DOCS.mkdir(exist_ok=True)
    (DOCS / "early_model_results.json").write_text(json.dumps(results, indent=2))

    rows = [
        "| Metric | Value |",
        "|---|---:|",
        f"| Seed | {SEED} |",
        f"| Rasch theta correlation | {rasch['theta_correlation']} |",
        f"| Rasch b correlation | {rasch['b_correlation']} |",
        f"| Rasch theta RMSE | {rasch['theta_rmse']} |",
        f"| Rasch b RMSE | {rasch['b_rmse']} |",
        f"| Rasch iterations | {rasch['iterations']} |",
        f"| Dropout AUC | {dropout['auc']} |",
        f"| Dropout PR-AUC | {dropout['pr_auc']} |",
        f"| Dropout Brier | {dropout['brier']} |",
        f"| Dropout precision@10% | {dropout['precision_at_10pct']} |",
    ]
    cal_rows = ["", "| Calibration bin | n | Mean predicted | Observed |", "|---|---:|---:|---:|"]
    for r in dropout["calibration"]:
        cal_rows.append(
            f"| {r['bin']} | {r['n']} | {r['mean_predicted']} | {r['observed_rate']} |"
        )

    md = "\n".join([
        "# Early model on synthetic data",
        "",
        "Reproducible artefact for the optional Round 1 model submission.",
        "It uses **synthetic data only**; no real student data is present.",
        "",
        "```bash",
        "python3 scripts/run_early_model.py",
        "```",
        "",
        "## What it demonstrates",
        "",
        "1. Rasch/1PL recovery of student ability and item difficulty.",
        "2. A dropout baseline trained on an earlier cohort, calibrated on a second,",
        "   and evaluated on a later cohort (time-like split, not a random split).",
        "3. Calibration and top-decile precision, not just AUC.",
        "",
        "## Results",
        "",
        *rows,
        *cal_rows,
        "",
        "## Caveat",
        "",
        results["caveat"],
        "",
    ])
    (DOCS / "early_model_results.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
