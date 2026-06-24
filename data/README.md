# Data Notes

This repository's committed data artifacts span two disjoint, inconsistent
"worlds." See `docs/reproducible_metrics_report.md` for the full explanation and
exact regeneration commands. Summary:

## (a) World A — committed 50k dev-sample artifacts (reproducible)

- `data/processed/*.parquet` (`train_*`, `test_*`, `sample_submission.parquet`)
  and `data/features/{dataset_baseline,dataset_g,dataset_h,meta_dataset,
  oof_predictions_baseline,oof_predictions_dataset_g,oof_predictions_dataset_h,
  oof_predictions_final,path_metadata}.parquet` are a **50,000-row-per-file
  slice** of the full Bosch CSVs, with **271 positive rows (0.542% failure
  rate)**.
- Provenance for this slice is recorded in `data/processed/PROVENANCE.json`.
  As committed, that file documents that this 50k slice is a **stale/partial
  artifact** predating the explicit `--sample-rows` flag (see
  `scripts/prepare_data.py`) — it was not produced by an intentional, labeled
  sampling run, just inferred from the files as they exist today.
- This sample IS reproducible going forward: regenerate it explicitly with
  `python scripts/prepare_data.py --sample-rows 50000 --sample-tag dev --overwrite`
  followed by the `build_dataset_*` and `train_*` scripts (see
  `docs/reproducible_metrics_report.md` Section 3b for the exact sequence).
- The committed models in `outputs/` were trained on this 50k sample. Honest
  OOF MCC values are in `outputs/training_summary.json` and tabulated in
  `docs/reproducible_metrics_report.md`.

## (b) World B — historical demo blend file (NOT reproducible)

- `data/features/oof_predictions_context_meta_v2_blend.parquet` (and its backup
  copy `_backup_oof_predictions_context_meta_v2_blend.parquet`) contain
  **1,183,747 rows with 6,879 positives (0.5811% failure rate)** — i.e. full
  Kaggle-scale data, NOT the 50k sample above.
- These files are kept ONLY as a **historical demo input** for
  `scripts/run_batch_simulation.py` and `scripts/run_drift_monitoring.py`. They
  are NOT backed by any reproducible generator in this repository.
- The original raw data, intermediate feature tables, and trained model
  artifacts that produced this blend file were **deliberately deleted** for
  GitHub packaging size and cleanliness, before this provenance practice was
  introduced. A full git-history search across all branches found **no
  training script that produces this file** — it cannot currently be
  regenerated from committed code.
- Any metric quoted from this file (in `README.md` or
  `docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md`) is historical and unverified.
  Treat it as a record of a past experiment, not a property of the current
  codebase.

## (c) Regenerating full-scale data from `data/raw/`

The full, un-truncated Bosch CSVs are present in `data/raw/` (`train_numeric.csv`,
`train_date.csv`, `train_categorical.csv`, `test_*.csv`, each ~2.1–2.9 GB). Full
regeneration is possible but heavy (hours of runtime, large intermediate files).
To produce full-scale processed parquet (no sampling, no truncation):

```bash
python scripts/prepare_data.py --zip-path <path-or-omit-with-skip-unzip> --overwrite
python scripts/build_dataset_baseline.py
python scripts/build_dataset_g.py
python scripts/build_dataset_h.py
python scripts/train_baseline.py
python scripts/train_dataset_g.py
python scripts/train_dataset_h.py
python scripts/train_meta_model.py
```

`scripts/prepare_data.py` defaults to processing the FULL CSVs with no row cap;
a sample is only produced if `--sample-rows` is passed explicitly. See
`docs/reproducible_metrics_report.md` for full details, caveats, and the exact
dev-sample command sequence.
