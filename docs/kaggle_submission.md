# Kaggle Submission (Track 2)

This is the implementation note for Track 2 in `docs/ml_system_tracks.md`. It explains what
`scripts/generate_submission.py` does, what it deliberately does not do, and what is still
missing in this repo before it can produce a real, full-size Kaggle submission.

## What the script does

`scripts/generate_submission.py`:
1. Loads a model artifact with `joblib.load(--model-path)` and validates it has the Phase-2
   payload shape (`{"models", "feature_cols", "threshold", ...}`) using the exact same
   `validate_payload` function as `scripts/validate_model_payload.py` (imported, not
   duplicated). Refuses to proceed — with a clear error — if the file is a bare estimator
   (the pre-Phase-2 format) or otherwise structurally invalid.
2. Loads `--test-features`, a parquet file that must already contain an `Id` column plus every
   column listed in the payload's `feature_cols`. Fails fast, listing the missing columns by
   name, if any are absent.
3. Generates probabilities by averaging `predict_proba` across every CV-fold model in
   `payload["models"]` (the same average-over-folds ensembling `BoschPredictor` uses).
4. Applies `payload["threshold"]` unless `--threshold` is passed to override it.
5. Writes `Id,Response` to `--output` (default `outputs/submission.csv`, which is already
   gitignored — see `.gitignore` `outputs/*.csv` — so a generated submission is never
   accidentally committed).
6. Prints `model_name`, `threshold_used`, `output_path`, `row_count`, and
   `positive_prediction_count`. Prints a warning (not an error) if `--test-features` row count or
   Id set doesn't match `--sample-submission` (default
   `data/processed/sample_submission.parquet`).

**It never reads or scores against labels.** If `--test-features` happens to contain a
`Response` column, the script prints a warning that it is being ignored and never touches it
again — no MCC, precision, recall, accuracy, or confusion matrix is computed anywhere in this
script, by construction (it has no code path that reads a label column for scoring purposes).

## What the script does NOT do

- **No feature engineering.** It does not run `core_pipeline.build_core_features` or any
  equivalent transform — `--test-features` must already be in the exact shape the model was
  trained on.
- **No model selection logic.** You choose which payload (`baseline_model.pkl`,
  `dataset_g_model.pkl`, `dataset_h_model.pkl`, or `meta_model.pkl`) and which matching feature
  table to pass.
- **No retraining, no threshold search.** It only applies an already-selected threshold.

## Current status: `dataset_h` works end-to-end; other models do not

> **Updated 2026-06-28 (pre-Kaggle cleanup).** Both blockers described in the original writing
> of this document are resolved specifically for `dataset_h`. See `docs/dataset_h_submission_run.md`
> for the full verified run record.

- `scripts/build_test_dataset_h.py` exists and produces `data/features/test_dataset_h.parquet`
  (1,183,748 rows, no `Response`, all `feature_cols` verified against the payload).
- `models/dataset_h_model.pkl` is a valid Phase-2 payload dict (`models`, `feature_cols`,
  `threshold`, `data_fingerprint`, ...) — fingerprint-matched to `data/features/dataset_h_lookup.json`
  via `scripts/validate_model_payload.py`.
- A full-size submission was generated and locally validated (2,993 positives at threshold 0.91,
  row count and Id set match `data/processed/sample_submission.parquet`). Not yet submitted to
  Kaggle — that is a deliberate, separate action.

The other three models (`baseline`, `dataset_g`, `meta_model`) still have no test-side feature-
engineering script. Running `generate_submission.py` against them will fail at the feature-columns
check with a clear error. This is the documented current gap, not a bug.

To produce a submission for `dataset_h` (ready now):

```bash
PYTHONPATH=. python scripts/build_test_dataset_h.py
PYTHONPATH=. python scripts/generate_submission.py \
  --model-path models/dataset_h_model.pkl \
  --test-features data/features/test_dataset_h.parquet \
  --output outputs/submission.csv
```

To produce a submission for the other models (future work):
1. Build a test-side feature table for the target model (no `build_test_dataset_baseline.py`,
   `build_test_dataset_g.py`, or test-side meta-feature builder exists yet).
2. For `dataset_g`/`dataset_h`/`meta_model`, the OOF-safe lookup tables (chunk/path failure rates)
   must already be persisted from the full-scale training run — they cannot be recomputed on test
   data without leaking.
3. Run this script with `--model-path` and `--test-features` matching the target model.

## Usage

```bash
PYTHONPATH=. python scripts/generate_submission.py \
  --model-path models/meta_model.pkl \
  --test-features <path to an engineered, unlabeled test parquet with Id + meta feature_cols> \
  --output outputs/submission.csv
```

(`PYTHONPATH=.` matches the convention every other `scripts/*.py` in this repo already requires
for its `from src...` / `from scripts...` imports to resolve — see e.g.
`scripts/validate_model_payload.py`.)

Optional: `--threshold 0.4` to override the payload's stored threshold; `--id-col` if the Id
column is named differently; `--sample-submission <path>` to check against a different reference
file.

## Validation performed for this change

See the commit/PR for full output. Summary:
- `py_compile` on `scripts/generate_submission.py` — passes.
- `scripts/validate_model_payload.py` — passes its self-test; confirms (as documented above)
  that all four committed `models/*.pkl` are still bare estimators.
- Smoke test with a tiny synthetic payload (built via the same `train_lightgbm_oof` +
  `build_model_payload` used in production training, dumped to a temp file) and a tiny synthetic
  unlabeled feature parquet — produces a correctly shaped `Id,Response` CSV with binary int
  predictions.
- Negative test: pointing `--model-path` at the real, committed `models/baseline_model.pkl`
  (bare estimator) prints a single `ERROR: ... bare LGBMClassifier, not the Phase-2 payload
  dict ...` line to stdout, exits 1, prints no Python traceback, and creates no output file.
  `main()`'s CLI entrypoint catches `FileNotFoundError`/`ValueError`/`KeyError` — the failure
  modes this script defines on purpose — for exactly this reason; any other exception type is
  an unanticipated bug and still surfaces with its full traceback.
- Negative test: pointing `--test-features` at a parquet missing required `feature_cols` fails
  the same way — one `ERROR:` line, exit 1, no traceback, naming the missing columns.
- `grep` over `scripts/generate_submission.py` for `mcc|precision|recall|accuracy|confusion|
  \btp\b|\bfp\b|\btn\b|\bfn\b` (case-insensitive) returns no matches outside this sentence —
  confirming no supervised-metric computation was introduced.
