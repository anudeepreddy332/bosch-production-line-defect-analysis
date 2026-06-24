# Full-Scale Training Plan (~1.18M rows)

**Status: PLAN ONLY. Nothing in this document has been executed.** No training, no data
preparation, and no other pipeline script was run to produce this plan — every command below was
verified by reading the actual script source (`scripts/prepare_data.py`,
`scripts/build_dataset_{baseline,g,h}.py`, `scripts/train_{baseline,dataset_g,dataset_h,
meta_model}.py`, `scripts/validate_model_payload.py`, `scripts/validate_system.py`) on this branch,
not guessed from memory or from other docs.

**Why this document exists:** `docs/evaluation_feature_quality_audit.md` found and
`3db7901` ("Fix feature methodology issues from evaluation_feature_quality_audit.md") fixed two
leakage bugs (`chunk_failure_rate` in Dataset G, `pair_cooccur_*`/`path_count` in Dataset H), but
the fix was verified **only on the 50,000-row dev sample**. The natural next step — rerunning the
full pipeline on the real ~1,183,747-row Bosch data — has not been done or approved. This document
is the copy-pasteable command sequence, artifact inventory, validation checklist, and risk
assessment for that step, so that whoever approves and runs it (a separate, explicitly-approved
compute step, not something to run opportunistically) does not have to reverse-engineer the script
dependency graph under time pressure.

**Update (2026-06-24): the dev-sample staleness gap below has been closed.** This section
originally documented that the tracked `outputs/training_summary.json` and `models/*.pkl` (dated
from commit `a62d631`) were stale relative to the post-`3db7901` code — `dataset_g`'s feature list
still listed `chunk_failure_rate` and `dataset_h`'s OOF MCC was the pre-fix, leak-inflated
0.13053326149364966. That gap was closed on `feature/dev-sample-refresh-post-methodology-fix`
(merged to `main`): the 50k dev-sample pipeline was rerun end-to-end against current code, and the
tracked `outputs/training_summary.json`, `models/*.pkl`, and `data/processed/PROVENANCE.json` now
reflect it (`dataset_g`'s feature list no longer contains `chunk_failure_rate`; `dataset_h` OOF MCC
is now `0.09725962897650973`; `meta_model` OOF MCC is now `0.03189334352773844`). See
`docs/reproducible_metrics_report.md` §1 for the current source-of-truth dev-sample numbers — do
not treat the 0.1305/0.0523 figures anywhere in this document as current; they are the historical
pre-fix values being referenced for comparison only. This full-scale plan's own command sequence
and risk assessment below were not affected by that refresh (they describe what a full-scale run
would do, which is unchanged) and remain unexecuted.

---

## 1. Regenerating full processed parquet from `data/raw/` (no sampling)

This is **not** the dev-sample sequence in `docs/reproducible_metrics_report.md` Section 3b. That
sequence passes `--sample-rows 50000 --sample-tag dev`, which explicitly caps every output parquet
to the first 50,000 rows. The sequence below omits `--sample-rows` entirely, which — per
`scripts/prepare_data.py`'s own argparse help text and the docstring of
`convert_csv_to_parquet_incremental` — means "the FULL CSV is converted — there is no implicit row
cap."

The full raw CSVs already exist locally at `data/raw/*.csv` (confirmed by `ls -la`, see Section 6),
so `--skip-unzip` is appropriate; there is no need to re-extract from a zip archive.

```bash
# Full data, no sampling, no truncation. --overwrite is REQUIRED because the local
# existing data/processed/*.parquet artifacts (untracked/gitignored, confirmed via
# `git ls-files data/processed/` -- only PROVENANCE.json is tracked there) are currently
# an explicit, current-code 50k dev sample (see data/processed/PROVENANCE.json:
# sample_tag="dev", status="sample", refreshed on feature/dev-sample-refresh-post-
# methodology-fix -- it is current relative to today's code, but it is still only
# 50,000 rows, not full data) -- without --overwrite, prepare_data.py will see each
# parquet already exists and SKIP it, silently leaving the 50k sample in place
# (convert_csv_to_parquet_incremental's "skipped_existing" path; see its docstring).
python scripts/prepare_data.py --skip-unzip --overwrite
```

Do **not** pass `--sample-rows` for this run. Do **not** omit `--overwrite` — omitting it is the
single most likely way this step silently produces nothing (every parquet already exists from the
50k dev sample, so all seven conversions would be skipped and `data/processed/PROVENANCE.json`
would record `"action": "skipped_existing"` for every file, with `full_data_status` very likely
landing on `"unverified"` rather than `"generated_full"` — see Section 5 for the exact check).

`--chunksize` defaults to 50,000 CSV rows per `pd.read_csv` chunk; there is no reason to change it
for this run, but it is a tunable (`--chunksize <int>`) if memory pressure during conversion is a
concern (see Section 6).

**What this writes:** `data/processed/train_numeric.parquet`, `train_date.parquet`,
`train_categorical.parquet`, `test_numeric.parquet`, `test_date.parquet`,
`test_categorical.parquet`, `sample_submission.parquet`, and `data/processed/PROVENANCE.json`
(overwritten with this run's manifest — see Section 5 for what it must say).

---

## 2. Rebuilding the feature datasets

**`meta_dataset.parquet` is not a standalone build step.** Unlike `dataset_baseline.parquet`,
`dataset_g.parquet`, and `dataset_h.parquet` — each produced by its own
`scripts/build_dataset_*.py` — `meta_dataset.parquet` is constructed *inside*
`scripts/train_meta_model.py` (lines 47–76: it merges the three base models'
`oof_predictions_*.parquet` files plus `chunk_id`/`chunk_size` from `dataset_baseline.parquet`,
adds `mean_prediction`/`std_prediction`/`max_prediction`/`agreement_count`, then writes
`data/features/meta_dataset.parquet` *before* training the meta-model on it). There is no
`scripts/build_dataset_meta.py` and there should not be one — running `train_meta_model.py` is the
only way to produce `meta_dataset.parquet`, and it requires `outputs/training_summary.json` to
already contain `best_threshold` for `baseline`, `dataset_g`, and `dataset_h` (used to compute
`agreement_count`; see `_get_threshold` in `scripts/train_meta_model.py`).

This creates a hard dependency chain: the three base **build** scripts must run before the three
base **train** scripts (Section 3), and `train_meta_model.py` must run last. Within Section 2, the
three build scripts below can run in this order (g and h both depend on baseline's output, but are
independent of each other):

```bash
# 1. dataset_baseline + path_metadata (everything else depends on these two outputs)
python scripts/build_dataset_baseline.py
# reads:  data/processed/train_numeric.parquet, data/processed/train_date.parquet
# writes: data/features/dataset_baseline.parquet, data/features/path_metadata.parquet

# 2. dataset_g (OOF-safe target-rate features)
python scripts/build_dataset_g.py --n-splits 5
# reads:  data/features/dataset_baseline.parquet, data/features/path_metadata.parquet
# writes: data/features/dataset_g.parquet

# 3. dataset_h (path-transition / station-pair risk features, fold-restricted per the
#    evaluation_feature_quality_audit.md leakage fix)
python scripts/build_dataset_h.py --n-splits 5
# reads:  data/features/dataset_baseline.parquet, data/features/path_metadata.parquet
# writes: data/features/dataset_h.parquet
```

`--n-splits` defaults to 5 in both scripts; pass it explicitly above only for clarity/auditability —
changing it from 5 would also require changing it consistently in the corresponding
`ChunkCVConfig` expectations used by `verify_persisted_fold_assignment` at train time (Section 3),
since that function recomputes the split with its own default `config=None` → `ChunkCVConfig()`
(also `n_splits=5`) and asserts it matches the persisted `cv_fold` column exactly.

`build_dataset_baseline.py` also accepts `--batch-size` (default 20,000) and `--chunk-size-rows`
(default 10,000, this is the CV group size — see `CLAUDE.md` "Chunk-aware, leakage-safe CV"). Leave
both at their defaults unless there is a specific reason to change the CV group granularity; changing
`--chunk-size-rows` changes what `chunk_id` means everywhere downstream.

`meta_dataset.parquet` is produced as a side effect of Section 3's last step
(`train_meta_model.py`), not here — see Section 3.

---

## 3. Training: exact dependency order

Verified by reading all four `train_*.py` scripts directly. The order is **not interchangeable**:
`train_meta_model.py` reads the OOF prediction parquet files written by the other three, plus reads
`outputs/training_summary.json` for each base model's `best_threshold` (written by
`update_training_summary` inside each base `train_*.py` call). Running `train_meta_model.py` before
all three base trainers have completed will raise `FileNotFoundError` (it explicitly checks for all
four required inputs and lists which are missing).

```bash
# 1. Baseline model
python scripts/train_baseline.py
# reads:  data/features/dataset_baseline.parquet
# writes: data/features/oof_predictions_baseline.parquet,
#         outputs/feature_importance_baseline.csv,
#         models/baseline_model.pkl,
#         outputs/training_summary.json (adds/overwrites the "baseline" key)

# 2. Dataset G model
python scripts/train_dataset_g.py
# reads:  data/features/dataset_g.parquet
# also calls verify_persisted_fold_assignment(df) first -- raises ValueError if the
# cv_fold column persisted by build_dataset_g.py does not exactly match the split
# train_lightgbm_oof recomputes internally (see src/training/cv.py).
# writes: data/features/oof_predictions_dataset_g.parquet,
#         outputs/feature_importance_dataset_g.csv,
#         models/dataset_g_model.pkl,
#         outputs/training_summary.json (adds/overwrites the "dataset_g" key)

# 3. Dataset H model
python scripts/train_dataset_h.py
# reads:  data/features/dataset_h.parquet
# also calls verify_persisted_fold_assignment(df) first, same guard as above.
# writes: data/features/oof_predictions_dataset_h.parquet,
#         outputs/feature_importance_dataset_h.csv,
#         models/dataset_h_model.pkl,
#         outputs/training_summary.json (adds/overwrites the "dataset_h" key)

# 4. Meta-model (MUST run last -- depends on all three OOF prediction files above)
python scripts/train_meta_model.py
# reads:  data/features/oof_predictions_baseline.parquet,
#         data/features/oof_predictions_dataset_g.parquet,
#         data/features/oof_predictions_dataset_h.parquet,
#         data/features/dataset_baseline.parquet (for chunk_id/chunk_size),
#         outputs/training_summary.json (for each base model's best_threshold)
# writes: data/features/meta_dataset.parquet  <-- built here, not by a build_dataset_*.py
#         data/features/oof_predictions_final.parquet,
#         outputs/feature_importance_meta_model.csv,
#         models/meta_model.pkl,
#         outputs/training_summary.json (adds/overwrites the "meta_model" key, plus
#           meta_dataset_path and base_thresholds fields inside that key)
```

Each `train_*.py` uses the LightGBM hyperparameters hardcoded in
`src/training/modeling.py::train_lightgbm_oof` (`n_estimators=700`, `learning_rate=0.03`,
`num_leaves=63`, `subsample=0.8`, `colsample_bytree=0.8`, `class_weight="balanced"`,
`early_stopping(stopping_rounds=100)`, 5-fold `make_chunk_aware_splits`) — these are not exposed as
CLI flags on any `train_*.py` script, so there is nothing to pass here; changing them means editing
`src/training/modeling.py`, which is out of scope for this plan.

---

## 4. Expected generated artifacts: tracked vs. gitignored

Verified directly against `.gitignore` and `git ls-files` / `git check-ignore` on this branch — not
assumed. "Tracked" means the file is already in the git index today (it would be modified in place
by a full-scale rerun, not newly added); "gitignored" means git will not see it as a change at all
unless force-added.

| Artifact | Path | Tracked today? | Gitignored? |
|---|---|---|---|
| Provenance manifest | `data/processed/PROVENANCE.json` | **Tracked** | No (explicitly un-ignored via `!data/processed/PROVENANCE.json`) |
| Processed: train numeric | `data/processed/train_numeric.parquet` | untracked | Yes (`data/processed/*`) |
| Processed: train date | `data/processed/train_date.parquet` | untracked | Yes |
| Processed: train categorical | `data/processed/train_categorical.parquet` | untracked | Yes |
| Processed: test numeric | `data/processed/test_numeric.parquet` | untracked | Yes |
| Processed: test date | `data/processed/test_date.parquet` | untracked | Yes |
| Processed: test categorical | `data/processed/test_categorical.parquet` | untracked | Yes |
| Processed: sample submission | `data/processed/sample_submission.parquet` | untracked | Yes |
| Feature: baseline | `data/features/dataset_baseline.parquet` | untracked | Yes (`data/features/*.parquet`) |
| Feature: path metadata | `data/features/path_metadata.parquet` | untracked | Yes |
| Feature: dataset G | `data/features/dataset_g.parquet` | untracked | Yes |
| Feature: dataset H | `data/features/dataset_h.parquet` | untracked | Yes |
| Feature: meta dataset | `data/features/meta_dataset.parquet` | untracked | Yes |
| OOF preds: baseline | `data/features/oof_predictions_baseline.parquet` | untracked | Yes |
| OOF preds: dataset G | `data/features/oof_predictions_dataset_g.parquet` | untracked | Yes |
| OOF preds: dataset H | `data/features/oof_predictions_dataset_h.parquet` | untracked | Yes |
| OOF preds: meta/final | `data/features/oof_predictions_final.parquet` | untracked | Yes |
| Model: baseline | `models/baseline_model.pkl` | **Tracked** (force-added; see `CLAUDE.md`) | Yes (`models/*.pkl`) but already in index |
| Model: dataset G | `models/dataset_g_model.pkl` | **Tracked** (force-added) | Yes, but already in index |
| Model: dataset H | `models/dataset_h_model.pkl` | **Tracked** (force-added) | Yes, but already in index |
| Model: meta | `models/meta_model.pkl` | **Tracked** (force-added) | Yes, but already in index |
| Training summary | `outputs/training_summary.json` | **Tracked** (force-added) | No (not matched by any `outputs/*` ignore rule — only `outputs/*.csv` and `outputs/*.parquet` are ignored) |
| Feature importance: baseline | `outputs/feature_importance_baseline.csv` | untracked | Yes (`outputs/*.csv`) |
| Feature importance: dataset G | `outputs/feature_importance_dataset_g.csv` | untracked | Yes |
| Feature importance: dataset H | `outputs/feature_importance_dataset_h.csv` | untracked | Yes |
| Feature importance: meta model | `outputs/feature_importance_meta_model.csv` | untracked | Yes |

A git-status diff after this full run will therefore show, at most: **modifications** to the six
already-tracked files (`data/processed/PROVENANCE.json`, `outputs/training_summary.json`, and the
four `models/*.pkl` — these already exist in the index from the 50k-sample run, so a full-scale
rerun overwrites them in place rather than adding new paths) and **zero new tracked paths** for
everything else (all newly-written parquet and CSV files match an existing `.gitignore` rule and
will not appear in `git status` as untracked unless someone runs `git add -f`).

This confirms the `CLAUDE.md` note verbatim: `models/*.pkl` and `outputs/training_summary.json`
**are** currently tracked despite matching gitignore patterns, because they were force-added in an
earlier, deliberate decision — don't "fix" this by deleting them or by adding a `.gitignore`
exception; just be aware that a full-scale run **modifies tracked files** and that diff needs human
review before commit (see Section 7).

---

## 5. Required validation after a full run

Run every check below before treating a full-scale run as trustworthy. None of these require
re-running the pipeline if it already completed; they only read the artifacts it produced.

**1. `data/processed/PROVENANCE.json` shows full-data status, not `is_full_data: false`.**

```bash
python3 -c "import json; p = json.load(open('data/processed/PROVENANCE.json')); print(p['status'], p['is_full_data'], p['requested_sample_rows'])"
```
Expected: `status == "full_data"`, `is_full_data == True`, `requested_sample_rows is None`. Per
`write_provenance()` in `scripts/prepare_data.py`, `status` is `"full_data"` **only if every file**
has `full_data_status == "generated_full"` — i.e. every one of the 7 parquet files was actually
(re)converted this run with no `--sample-rows` cap, not skipped because it already existed. If any
file shows `"unverified"` (most likely cause: `--overwrite` was omitted and the stale 50k sample was
left in place — see Section 1), `status` will be `"unknown"` and `is_full_data` will be `null`. Do
not proceed past this check if that happens; rerun Section 1 with `--overwrite`.

**2. Row counts match the row count of each file's own source CSV — train and test are NOT
assumed to be equal.**

`docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md` ("Total rows: **1,183,747**"),
`docs/production_readiness_audit.md`, `data/README.md`, and `docs/reproducible_metrics_report.md`
all cite **1,183,747 rows** for the full Bosch *train* set (6,879 positives, 0.5811% failure rate,
from the World-B blend file's metadata). Measured directly this session via `wc -l data/raw/*.csv`
(see Section 6 for the full output), train and test are **close but not identical**: the three
`train_*.csv` files each have 1,183,748 lines (1,183,747 data rows after the header), while the
three `test_*.csv` files (plus `sample_submission.csv`) each have 1,183,749 lines (**1,183,748**
data rows after the header) — test has exactly **one more row than train**, not the same count.
Do not assume or assert that test row count equals train row count; validate each side against its
own raw CSV independently. Check directly:

```bash
python3 -c "
import pyarrow.parquet as pq
for name in ['train_numeric','train_date','train_categorical','test_numeric','test_date','test_categorical','sample_submission']:
    p = pq.ParquetFile(f'data/processed/{name}.parquet')
    print(name, p.metadata.num_rows)
"
```
Expected: every `train_*` and `test_*` file reports the same row count as its corresponding raw CSV
(do not hardcode 1,183,747 as a pass/fail gate for `test_*` — Kaggle's actual test row count may
differ slightly from train; the real check is "matches the row count of the source CSV," which you
can confirm via `wc -l data/raw/<file>.csv` minus 1 for the header).

**3. Test data has no `Response` column.**

```bash
python3 -c "
import pyarrow.parquet as pq
for name in ['test_numeric','test_date','test_categorical']:
    cols = pq.ParquetFile(f'data/processed/{name}.parquet').schema.names
    print(name, 'Response' in cols)
"
```
Expected: `False` for all three. This was already true for the 50k dev sample (confirmed in
`docs/evaluation_feature_quality_audit.md` Section 1) and must remain true after a full regenerate
since `prepare_data.py` does not add or drop columns — but verify directly rather than assuming the
full run preserved this, since this is the exact invariant this repo's hard rules
(`CLAUDE.md` "Production = inference only") depend on.

**4. Model payloads validate.**

```bash
python scripts/validate_model_payload.py
```
This always runs a self-test against a tiny synthetic dataset first (no dependency on real data),
then does a best-effort load of whatever is in `models/*.pkl`. After the full run, expect: all four
`models/*.pkl` load via `joblib.load`, each is a dict with the required keys (`models`,
`feature_cols`, `threshold`, `model_name`, `oof_mcc`, `fold_metrics`, `created_at_utc`,
`training_rows`, `data_fingerprint`), `training_rows` reflects the full-scale row count (not
50,000), and `oof_mcc` is a float in `[-1, 1]`. Exit code must be 0. Note the script's documented
gap: it does **not** exercise `BoschPredictor.load()` end-to-end (that needs
`selected_features_top150.txt` / `train_selected.parquet` artifacts this repo does not have) — that
gap is unrelated to and unaffected by full-scale training, see the script's own module docstring.

**5. `outputs/training_summary.json` contains full-scale OOF MCC for all four models.**

```bash
python3 -c "
import json
s = json.load(open('outputs/training_summary.json'))
for name, m in s['models'].items():
    print(name, 'rows=', m['rows'], 'oof_mcc=', m['oof_mcc'], 'best_threshold=', m['best_threshold'])
"
```
Expected: `rows` for `baseline`/`dataset_g`/`dataset_h` reflects the full train row count (not
50,000), and `rows` for `meta_model` matches it too (meta_dataset is built from the same Ids).
Sanity-check that `dataset_g`'s `features` list does **not** contain `chunk_failure_rate` (it was
removed by `3db7901`; its presence in a full-scale run would mean stale code or a stale file was
used — the currently tracked `training_summary.json` on `main` already passes this check at
dev-sample scale after the refresh described in this document's opening note, so a full-scale run
regressing on this specific point would indicate something went wrong in that run, not a
pre-existing repo issue).

**6. `feature_importance_*.csv` files regenerate for all four models.**

```bash
ls -la outputs/feature_importance_baseline.csv outputs/feature_importance_dataset_g.csv outputs/feature_importance_dataset_h.csv outputs/feature_importance_meta_model.csv
```
Expected: all four exist with a fresh mtime from this run (these are gitignored per Section 4, so
`git status` will not show them — check the filesystem directly, not git). Spot-check that each
CSV's `feature` column matches the corresponding `train_*.py`'s `FEATURE_COLS` / `META_FEATURES`
list and has no NaN `importance` values.

**7. Explicit `dataset_h` vs. `meta_model` comparison.**

This is the highest-value check, since it directly re-decides a finding from
`docs/reproducible_metrics_report.md` §1 (current source of truth) and
`docs/evaluation_feature_quality_audit.md` (historical pre-fix diagnosis): at 50k-row scale,
post-fix, `dataset_h` (OOF MCC 0.0973) beats the 3-model `meta_model` stack (OOF MCC 0.0319) by an
even wider margin than the pre-fix numbers showed (`dataset_h` 0.1305 vs. `meta_model` 0.0523), i.e.
**stacking hurt, and post-fix it hurts proportionally more** — attributed in the audit to too few
positives (271 total, ~54/fold) for the meta-learner to find real signal in
`agreement_count`/`mean_prediction`/etc. beyond noise. At full scale there are ~23.7x
more rows and (extrapolating proportionally) on the order of ~6,400 positives, which may be enough
for the stack to actually add value. Re-run this comparison, don't assume the answer transfers:

```bash
python3 -c "
import json
s = json.load(open('outputs/training_summary.json'))
h = s['models']['dataset_h']['oof_mcc']
meta = s['models']['meta_model']['oof_mcc']
print(f'dataset_h OOF MCC: {h:.5f}')
print(f'meta_model OOF MCC: {meta:.5f}')
print('stacking HELPS' if meta > h else 'stacking HURTS (same direction as 50k sample)')
"
```
Record the result in an updated metrics report (Section 7) before anyone treats `meta_model` as the
production-recommended model at full scale.

---

## 6. Compute / storage risk assessment

All numbers below are measured directly on this machine/branch (commands shown), not invented.

### Runtime estimate

**No timing instrumentation exists in this repo for the current scripts** (no `time.time()` deltas
are logged in any `train_*.py`; `prepare_data.py` does log per-file elapsed seconds for CSV→Parquet
conversion, but only after the fact in its own run, and no full-scale run has ever been logged). This
estimate is therefore order-of-magnitude reasoning from row-count scaling, not a measured baseline:

- **Row-count multiplier**: 1,183,747 / 50,000 ≈ **23.7x**.
- **`prepare_data.py` (CSV→Parquet)**: this step is I/O- and pandas-chunking-bound, scaling
  roughly linearly with row count (each of the 7 CSVs is read once in 50k-row chunks regardless of
  total size). At 50k rows this step is fast (well under a minute per file based on file sizes); at
  full scale, reading and dtype-optimizing ~15 GB of CSV (`du -sh data/raw` = **15G**, see below)
  chunk-by-chunk is reasonably estimated at **20–60 minutes total** across all 7 files on typical
  laptop-class disk I/O, dominated by `train_date.parquet`/`test_date.parquet`'s ~1,157 columns.
- **`build_dataset_*.py`**: `build_dataset_baseline.py` does two full passes over `train_numeric`/
  `train_date` in 20,000-row batches (linear in rows and in the ~970–1,157 column count it touches);
  `build_dataset_g.py`/`build_dataset_h.py` do an additional 5-fold loop with groupby/map operations
  over signature/transition/pair dictionaries — `build_dataset_h.py`'s `pairs_from_tokens` is
  `O(k^2)` per row in path length `k` (number of stations visited), and Python-level dict
  accumulation (`defaultdict`) does not vectorize, so it is the slowest of the three build scripts
  per row. Reasoned estimate: **30–90 minutes total** across all three, scaling slightly worse than
  linear because of the per-fold dictionary work in `build_dataset_h.py`.
- **`train_*.py`**: LightGBm with `n_estimators=700`, `num_leaves=63`, 5-fold CV, `early_stopping`
  at 100 rounds, `n_jobs=-1`. Per-tree fit cost in gradient boosting scales roughly with
  `rows x features x leaves` per tree; at 50k rows with 8–16 features this is fast (seconds to low
  minutes per fold judging from the small model file sizes in Section 4 below). At ~1.18M rows
  (23.7x), expect **substantially more than 23.7x** wall-clock for the tree-building scripts because
  histogram-based split finding cost grows with both row count and the number of unique values per
  feature (more rows -> more distinct values for continuous features like `start_time`,
  `feature_mean`, the OOF-safe rate features). A reasoned order-of-magnitude estimate is
  **1–4 hours per base model** (`train_baseline.py`, `train_dataset_g.py`, `train_dataset_h.py`),
  and a faster **15–45 minutes** for `train_meta_model.py` since it only has 7 scalar meta-features
  regardless of base row count. **Total training estimate: roughly 4–13 hours**, before accounting
  for early-stopping possibly cutting individual folds short or `class_weight="balanced"` increasing
  gradient computation cost on the full imbalanced set.
- **Grand total reasoned estimate: on the order of half a day to a full day of wall-clock time**
  for Sections 1–3 combined on a single machine with no GPU. This is consistent with
  `docs/reproducible_metrics_report.md`'s framing ("a long-running, heavy job — do not run it
  casually") and `data/README.md`'s ("hours of runtime, large intermediate files"). Treat this as a
  planning-level estimate, not a committed SLA — actual time depends heavily on disk speed, core
  count, and how much of the ~15 GB of CSV can be page-cached.

### Memory risk

- The three processed `*_date.parquet`/`*_categorical.parquet` files have **1,157** and **2,141**
  columns respectively (measured directly via `pyarrow.parquet.ParquetFile(...).schema.names` on the
  current 50k files — column count does not change with row count, only row count does). At full
  scale, `pd.read_csv(..., chunksize=...)` in `prepare_data.py` keeps memory bounded to one chunk at
  a time (chunk size defaults to 50,000 rows x up to 2,141 columns ≈ the same per-chunk memory
  footprint as today's *entire* 50k dev sample for `train_categorical.csv` — i.e. each chunk alone is
  comparable in size to today's whole file). `psutil`-based memory logging is already wired into
  `prepare_data.py` (`_memory_gb()`, logged every 10 chunks) — watch this output during the real run
  rather than guessing.
- `build_dataset_baseline.py` reads `train_numeric.parquet`/`train_date.parquet` in
  20,000-row batches (`--batch-size`, bounded), but then does `pd.read_parquet(tmp_numeric)` and
  `pd.read_parquet(tmp_date)` **in full** before merging (lines 173–176) — this loads the *entire*
  numeric-core and date-core intermediate tables into memory at once. At full scale these intermediates
  are small (3 columns: `Id`/`Response`/`feature_mean` for numeric-core; 4 columns for date-core), so
  this is low risk even at 1.18M rows, but it is a full in-memory join, not a streamed one — note it
  as a risk if the machine has less than ~8 GB free RAM.
  Similarly, `build_dataset_g.py`/`build_dataset_h.py` call `pd.read_parquet(baseline_path)` and
  `pd.read_parquet(path_meta_path)` in full (these are already the small, ~8–10 column outputs of
  `build_dataset_baseline.py`, not the wide raw parquet, so this is the lower-risk read).
- **No chunked/streaming reads exist in any `train_*.py`** — `pd.read_parquet(dataset_path)` loads
  the full feature dataset into memory before training. At full scale this means holding ~1.18M rows
  x (8–16 feature columns, all float32/int16/int32) in memory simultaneously, which is on the order
  of tens of MB — not a real risk by itself. The bigger unknown is LightGBM's own internal histogram
  memory during `model.fit(...)`, which scales with rows x bins x trees-in-flight; this repo has no
  prior full-scale run to cite a measured peak from.
- **Recommendation:** run with active memory monitoring (the existing `_memory_gb()` pattern, or
  `top`/`Activity Monitor` alongside), and budget for needing noticeably more free RAM than the dev
  sample required — this repo gives no hard number because no full-scale run has been logged in
  `data/processed/PROVENANCE.json` or anywhere else.

### Disk usage risk

Measured directly on this machine, this session. Row counts via `wc -l data/raw/*.csv`
(line count includes the header, so subtract 1 for data rows): `train_numeric.csv`,
`train_date.csv`, `train_categorical.csv` each report 1,183,748 lines (1,183,747 data rows);
`test_numeric.csv`, `test_date.csv`, `test_categorical.csv`, `sample_submission.csv` each report
1,183,749 lines (1,183,748 data rows) — confirming test has one more row than train, per the
Section 5 check 2 note above.

```
data/raw                15G   (train_numeric.csv 2.0G, train_date.csv 2.7G, train_categorical.csv 2.5G,
                                test_numeric.csv 2.0G, test_date.csv 2.7G, test_categorical.csv 2.5G,
                                sample_submission.csv 11M)
data/processed          100M  (50k-row parquet, current)
data/features            31M  (50k-row feature parquet, current, includes the 2 World-B blend files)
models                   13M  (current 4 pkl files)
outputs                 3.8M  (current JSON/CSV)
```

Extrapolating `data/processed` and `data/features` by the 23.7x row multiplier (parquet size scales
close to linearly with row count for fixed column count and similar value distributions):

| Artifact group | Current (50k) | Extrapolated full-scale (~1.18M, x23.7) |
|---|---:|---:|
| `data/processed/*.parquet` (7 files) | 100 MB | **~2.3 GB** |
| `data/features/*.parquet` (9 files, excluding World-B blend) | 31 MB total incl. blend files; ~13 MB for the 9 reproducible files | **~250 MB** |
| `models/*.pkl` (4 files) | 13 MB | **not linear — see below** |

**`models/*.pkl` will NOT scale 23.7x.** Tree count is fixed by `n_estimators=700` regardless of row
count; tree *size* (number of leaf splits actually used, up to `num_leaves=63` per tree) is bounded
per-tree but more rows means more trees are likely to reach their full leaf budget more consistently
across all 5 folds x 700 estimators, so expect model files to grow somewhat (more consistently
full trees, more distinct split thresholds stored) but by a **small multiple (rough guess: 1.5–4x)**,
not 23.7x. Current sizes: `baseline_model.pkl` 3.3 MB, `dataset_g_model.pkl` 2.8 MB,
`dataset_h_model.pkl` 2.1 MB, `meta_model.pkl` 4.5 MB (12.7 MB total) — even a generous 4x growth
estimate puts the four files around **~50 MB total**, not a disk concern by itself.

**The actual disk risk is headroom, not the artifact sizes themselves**: this machine currently
reports (`df -h .`) **19 GiB free out of 460 GiB (96% full)**. The ~2.3 GB processed +
~250 MB features + ~50 MB models = **~2.6 GB** of new/changed artifacts fits within 19 GiB free, but
leaves little margin alongside whatever else is competing for that disk during a multi-hour run
(OS swap, temp files, log growth from `psutil`-logged chunks at "every 10 chunks" cadence over
~24x more chunks than today). **Recommend freeing disk space before running this plan, independent
of the artifact sizes computed above** — 19 GiB free with 96% disk utilization is the binding
constraint, not the ~2.6 GB this pipeline is expected to add.

### Model file size risk

Already covered above: extrapolated `models/*.pkl` total is a rough **~20–50 MB** for all four
files combined (versus 12.7 MB today), a low risk in absolute terms. The CLAUDE.md-documented
decision to force-track these `.pkl` files in git despite `.gitignore` means this growth **will**
show up as a real diff size in any commit that includes a full-scale rerun — flag this for the
human reviewer in Section 7 below, it is not free to commit even at ~50 MB.

---

## 7. Rollback guidance

**Do not commit generated parquet/model artifacts from a full-scale run without explicit review and
approval.** Specifically, using the tracked/gitignored inventory from Section 4:

- `data/processed/*.parquet`, `data/features/*.parquet` (all 9 reproducible files), and
  `outputs/feature_importance_*.csv` are **gitignored** — running the full pipeline will not stage
  them for commit by default. Leave them untracked. If anyone is tempted to `git add -f` these for
  "convenience," don't — they are large (Section 6) and exactly the kind of generated artifact this
  repo's `.gitignore` was written to exclude.
- `data/processed/PROVENANCE.json`, `outputs/training_summary.json`, and the four `models/*.pkl`
  files (`models/baseline_model.pkl`, `models/dataset_g_model.pkl`, `models/dataset_h_model.pkl`,
  `models/meta_model.pkl`) — **six files total** — **are already tracked** in git from the
  50k-sample run. A full-scale run will **modify these six files in place** — this is a real diff
  that `git status`/`git diff` will show automatically, with no `git add -f` needed. **This is
  exactly the diff that needs human review before any commit**: confirm `outputs/training_summary.json`'s
  new OOF MCC values look sane (Section 5, checks 5 and 7) and that the four `.pkl` files actually
  changed `training_rows` to the full-scale count (not still 50,000, which would indicate the run
  silently used stale/cached inputs) before approving the commit.
- If a full-scale run produces results that look wrong (sanity checks in Section 5 fail, runtime
  blew up, disk filled up mid-run), the safe rollback is: do not commit. The six currently-tracked
  files (`outputs/training_summary.json`, `models/*.pkl` x4, `data/processed/PROVENANCE.json`) are
  unchanged in git's index until an explicit `git add` + commit happens — a failed or rejected run
  can simply be discarded by leaving the working tree dirty and not committing. **Any destructive
  cleanup command — `git checkout -- <path>` to revert a tracked file, or `rm` to delete generated
  parquet/CSV files (e.g. `rm data/processed/*.parquet data/features/*.parquet
  outputs/feature_importance_*.csv`) — must be explicitly reviewed and approved by a human before
  execution.** Neither command should be run automatically as part of "cleaning up" a rejected run;
  present the specific command and its target paths for approval first. The untracked generated
  parquet/CSV files carry zero git impact if simply left in place (they were never staged), so
  deletion is a convenience, not a requirement, and should not be treated as an automatic next step.
- **Documentation/metrics commits are different from artifact commits.** An updated, human-reviewed
  markdown report (e.g. a new "full-scale results" section added to
  `docs/reproducible_metrics_report.md`, or a new dedicated doc) that *quotes* numbers read out of
  the post-run `outputs/training_summary.json` is safe and appropriate to commit after review — it
  is small, human-readable, and does not carry the large-binary-diff risk of the `.pkl`/parquet
  files themselves. Prefer committing "here is what `outputs/training_summary.json` said after the
  full run, reviewed on `<date>`" prose over re-committing the raw JSON/pkl diff without comment.

---

## 8. Decision gate

**Do not proceed to building test-feature-engineering scripts** (the Kaggle Track 2 work documented
as blocked in `docs/kaggle_submission.md` / `docs/ml_system_tracks.md` — currently blocked partly
because "no engineered test feature table" exists, i.e. nothing produces a `--test-features` parquet
for `scripts/generate_submission.py` to score) **until**:

1. The full-scale training run described in Sections 1–3 above has actually been executed (not just
   planned), with explicit sign-off — this is, per this task's own constraints, a separate,
   explicitly-approved compute step, not something to run opportunistically.
2. All validation checks in Section 5 pass, in particular check 1 (`PROVENANCE.json` confirms
   `is_full_data: true` / `status: "full_data"`, not a stale or mixed sample state) and check 4
   (`scripts/validate_model_payload.py` exits 0 against the new `models/*.pkl`).
3. The full-scale `dataset_h`-vs-`meta_model` comparison (Section 5, check 7) has been re-run and
   the result — whether stacking helps or still hurts at ~1.18M rows — has been explicitly recorded
   and used to decide which model (a single base model or the meta-model) is the one Track 2's
   submission generator and any future production decision path should actually be pointed at. The
   50k-sample finding ("stacking hurts," attributed to too few positives) is a hypothesis about why,
   not a proven mechanism — full scale could go either way and must be checked, not assumed to
   replicate.

Until all three conditions above are met, any Kaggle submission, production decision-summary
refresh, or case-study update that implies a full-scale model evaluation happened is **getting
ahead of the evidence** — exactly the "two worlds" problem this repo's own
`docs/reproducible_metrics_report.md` and `docs/production_readiness_audit.md` were written to stop
recurring.
