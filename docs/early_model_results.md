# Early model on synthetic data

Reproducible artefact for the optional Round 1 model submission.
It uses **synthetic data only**; no real student data is present.

```bash
python3 scripts/run_early_model.py
```

## What it demonstrates

1. Rasch/1PL recovery of student ability and item difficulty.
2. A dropout baseline trained on an earlier cohort, calibrated on a second,
   and evaluated on a later cohort (time-like split, not a random split).
3. Calibration and top-decile precision, not just AUC.

## Results

| Metric | Value |
|---|---:|
| Seed | 20260401 |
| Rasch theta correlation | 0.922 |
| Rasch b correlation | 0.9945 |
| Rasch theta RMSE | 0.3952 |
| Rasch b RMSE | 0.1047 |
| Rasch iterations | 271 |
| Dropout AUC | 0.7436 |
| Dropout PR-AUC | 0.209 |
| Dropout Brier | 0.0783 |
| Dropout precision@10% | 0.2375 |

| Calibration bin | n | Mean predicted | Observed |
|---|---:|---:|---:|
| 0.0-0.2 | 760 | 0.0791 | 0.0829 |
| 0.2-0.4 | 40 | 0.2481 | 0.25 |

## Caveat

These are synthetic-data results. The dropout labels contain a designed signal and measurement noise. They validate the pipeline and time-split evaluation, not real-world effectiveness.
