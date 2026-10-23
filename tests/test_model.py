import numpy as np

from app.analytics import fit_rasch, sigmoid, topic_mastery


def test_rasch_recovers_ability_ordering():
    rng = np.random.default_rng(42)
    n_s, n_i = 80, 40
    true_theta = rng.normal(0, 1, n_s)
    true_b = rng.normal(0, 0.8, n_i)
    si, ii = np.meshgrid(np.arange(n_s), np.arange(n_i), indexing="ij")
    si, ii = si.ravel(), ii.ravel()
    y = (rng.random(si.size) < sigmoid(true_theta[si] - true_b[ii])).astype(float)
    out = fit_rasch(si, ii, y, n_s, n_i)
    assert np.corrcoef(out["theta"], true_theta)[0, 1] > 0.85
    assert np.corrcoef(out["b"], true_b)[0, 1] > 0.8
    assert out["iterations"] < 200


def test_mastery_is_bounded_and_evidence_sensitive():
    theta = 0.0
    b = np.array([-1.0, 0.0, 1.0])
    y = np.array([1.0, 1.0, 0.0])
    w = np.array([2.0, 2.0, 2.0])
    est, se = topic_mastery(theta, b, y, w)
    assert est > 0
    assert 0 < se < 1
