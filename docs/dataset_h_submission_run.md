# dataset_h Kaggle Submission Run

Record of a real, end-to-end run of the dataset_h train-serve contract
(`feature/dataset-h-train-serve-contract`, merged to `main` at `5bdfac8`, tagged
`phase-dataset-h-train-serve-contract`) producing an actual Kaggle-shaped
`submission.csv` from the full-scale (~1.18M-row) unlabeled Bosch test set.

**This submission was not sent to Kaggle.** This document records that the
artifact was built and validated locally; submitting it to the competition is a
separate, explicit action for a human to take.

## Model used

`models/dataset_h_model.pkl` — the approved candidate model (best single base
model at full scale; OOF MCC 0.1534, ahead of `dataset_g` at 0.1366 and the
3-model `meta_model` stack at 0.1494). `data_fingerprint=a5bb652f2b20aca6`,
matching `data/features/dataset_h_lookup.json`'s embedded fingerprint exactly —
confirmed by `scripts/validate_model_payload.py` before generating anything.

## Threshold used

`0.91` — the payload's own stored `threshold` (`payload["threshold"]`), not
overridden via `--threshold`.

## Exact commands run

```bash
# 1. Confirm dataset_h inference is runnable from current repo state
PYTHONPATH=. python scripts/validate_model_payload.py
# -> exit 0; dataset_h section: "PASS: lookup present and data_fingerprint
#    matches (a5bb652f2b20aca6) -- dataset_h inference is runnable."

# 2. Build the unlabeled test feature table (Track 2/3 shared contract)
PYTHONPATH=. python scripts/build_test_dataset_h.py
# -> Lookup<->model fingerprint check passed (a5bb652f2b20aca6)
# -> Saved unlabeled dataset_h test features:
#    data/features/test_dataset_h.parquet rows=1183748 cols=17

# 3. Generate the submission
PYTHONPATH=. python scripts/generate_submission.py \
  --model-path models/dataset_h_model.pkl \
  --test-features data/features/test_dataset_h.parquet \
  --output outputs/dataset_h_submission.csv
# -> model_name='dataset_h'
# -> threshold_used=0.91
# -> output_path=outputs/dataset_h_submission.csv
# -> row_count=1183748
# -> positive_prediction_count=2993
```

## Positive prediction count

**2,993** out of 1,183,748 rows (positive rate 0.2528%) flagged `Response=1` at
threshold 0.91.

## Validation checks passed

All checked independently with pandas against the actual output file, not just
the script's printed summary:

| Check | Result |
|---|---|
| Row count == 1,183,748 | **True** |
| Columns exactly `[Id, Response]` | **True** |
| Id set matches `data/processed/sample_submission.parquet` exactly | **True** |
| `Response` is binary `{0, 1}` | **True** (dtype `int64`) |
| No supervised metric (MCC/precision/recall/accuracy/confusion/TP/FP/TN/FN) computed anywhere in the generation path | **True** (grep over `scripts/generate_submission.py`, `scripts/build_test_dataset_h.py`, `src/features/dataset_h_pipeline.py` returns zero matches) |

This is consistent with `CLAUDE.md`'s hard rule: test/production data is
unlabeled, and MCC/precision/recall are only ever valid against labeled
train/OOF data.

## Output artifact path

`outputs/dataset_h_submission.csv` (gitignored via `outputs/*.csv` — generated,
not committed; regenerate with the three commands above). 11.3 MB,
`Id,Response` header, 1,183,748 data rows.

## Reproducing this run

Both `data/features/dataset_h_lookup.json` and `data/features/test_dataset_h.parquet`
are gitignored (regenerable, not committed). To reproduce from a clean clone with
`main` already checked out:

```bash
# Requires data/raw/*.csv (the original Bosch CSVs) to already be present.
PYTHONPATH=. python scripts/prepare_data.py --skip-unzip --overwrite
PYTHONPATH=. python scripts/build_dataset_baseline.py
PYTHONPATH=. python scripts/build_dataset_h.py
PYTHONPATH=. python scripts/build_test_dataset_h.py
PYTHONPATH=. python scripts/generate_submission.py \
  --model-path models/dataset_h_model.pkl \
  --test-features data/features/test_dataset_h.parquet \
  --output outputs/dataset_h_submission.csv
```

`models/dataset_h_model.pkl` itself is tracked in git, so it does not need to be
retrained to reproduce this exact submission — only the gitignored intermediate
artifacts (`dataset_h_lookup.json`, `test_dataset_h.parquet`) need regenerating.
