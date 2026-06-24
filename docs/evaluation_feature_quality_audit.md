# Evaluation & Feature-Quality Audit

**Status note (2026-06-24):** the leakage bugs this audit found (`chunk_failure_rate` in
`dataset_g`, fold-unrestricted `pair_cooccur_*`/`path_count` in `dataset_h`) were fixed in
`3db7901`, and the fix has since been verified against a fresh 50k dev-sample rerun on
`feature/dev-sample-refresh-post-methodology-fix`. The OOF MCC numbers quoted throughout this
document (§3, e.g. `dataset_h`=0.1305, `meta_model`=0.0523) are the **pre-fix** numbers that
motivated the fix — they are intentionally left unchanged below as the historical record of what
was found. For the current, post-fix numbers, see `docs/reproducible_metrics_report.md` §1
(`dataset_h`=0.0973, `meta_model`=0.0319).

**Scope:** read-only inspection of the currently committed, reproducible artifacts (data, features,
models, metrics). No training was run to produce this report — every number below is read directly
from committed parquet/JSON/CSV files or from re-running the existing, already-saved CV split logic
in `src/training/cv.py` for verification. This document does not change any code.

**Why this exists:** before generating Kaggle test features or attempting a real submission (Track 2),
we need an honest answer to "is the current model and feature set actually good, and is the CV
methodology actually leakage-safe?" — not an assumption. `docs/production_readiness_audit.md` and
`docs/reproducible_metrics_report.md` already raised parts of this; this report re-verifies their
claims against the data directly and adds a feature-level leakage audit that hadn't been done before
(see §6).

---

## 1. Current data scope: dev sample, not full-scale

**Evidence — `data/processed/PROVENANCE.json`:**
```json
{
  "sample_rows": 50000,
  "sample_tag": "stale-partial-committed-dev-sample",
  "is_full_data": false
}
```

**Evidence — direct parquet metadata (`pyarrow.parquet.ParquetFile`), this session:**

| File | Rows | Columns | Has `Response` |
|---|---:|---:|---|
| `train_numeric.parquet` | 50,000 | 970 | Yes |
| `train_date.parquet` | 50,000 | 1,157 | No |
| `train_categorical.parquet` | 50,000 | 2,141 | No |
| `test_numeric.parquet` | 50,000 | 969 | **No** |
| `test_date.parquet` | 50,000 | 1,157 | No |
| `test_categorical.parquet` | 50,000 | 2,141 | No |
| `sample_submission.parquet` | 50,000 | 2 (`Id`, `Response`) | placeholder only |

**Conclusion:** the committed data is a **50,000-row dev sample** of the real ~1.18M-row Bosch
dataset (confirmed `Id` range in `train_numeric` is `4..100147`, a contiguous low-Id slice, not a
random sample of the full range). Test data correctly has **no** `Response` column — schema-honest
for "unlabeled." `sample_submission.parquet`'s `Response` column is 100% zero — a Kaggle placeholder
format, not real labels. **Full-scale data exists** in `data/raw/*.csv` but has not been processed or
trained on in this repo snapshot (`docs/raw/*.csv` are the full ~2.1–2.9 GB files per `data/README.md`).

**Positive count / failure rate — `train_numeric.parquet["Response"]` value_counts (read directly):**
```
0    49729
1      271
```
271 / 50,000 = **0.542%** failure rate. This matches `PROVENANCE.json`, `data/README.md`, and
`docs/reproducible_metrics_report.md` exactly — internally consistent.

---

## 2. Feature dataset inspection

Directly read via `pandas.read_parquet(...).shape` / `.dtypes` / `.isna().sum()` this session:

| Dataset | Shape | Feature count (model `feature_cols`) | Missing values | `Response` prevalence | `cv_fold` balance |
|---|---|---:|---|---|---|
| `dataset_baseline.parquet` | (50000, 10) | 8 | `start_time`: 25 NaN, rest 0 | 271/50000 (0.542%) | n/a (no `cv_fold` column) |
| `dataset_g.parquet` | (50000, 17) | 13 | `start_time`: 25 NaN, rest 0 | 271/50000 (0.542%) | exactly 10,000/fold × 5 |
| `dataset_h.parquet` | (50000, 19) | 16 | `start_time`: 25 NaN, rest 0 | 271/50000 (0.542%) | exactly 10,000/fold × 5 |
| `meta_dataset.parquet` | (50000, 11) | 7 (`META_FEATURES`) | none | 271/50000 (0.542%) | n/a (re-split at train time) |

All four datasets are Id-aligned and label-consistent (same 271 positives throughout — no row drift
between feature-engineering stages). The 25 `start_time` NaNs are a real Bosch data quirk (some parts
have no recorded timestamp on any station) and are handled by `core_pipeline._fill_start_time`
(imputed to `min - 1.0`, i.e. sorted before all real timestamps) — not a bug introduced by this
pipeline.

Dtypes are appropriately downcast throughout (`float32`/`int32`/`int8`/`int16`), consistent with the
project's stated memory-safety goals — no obvious dtype problems.

---

## 3. Model metrics — read from `outputs/training_summary.json`

| Model | OOF MCC | Best threshold (global) | Fold thresholds | Fold threshold range | Fold threshold std |
|---|---:|---:|---|---:|---:|
| `baseline` | **0.0157** | 0.51 | 0.10, 0.07, 0.01, 0.47, 0.06 | 0.46 | 0.167 |
| `dataset_g` | **0.0459** | 0.32 | 0.02, 0.02, 0.34, 0.70, 0.62 | 0.68 | 0.287 |
| `dataset_h` | **0.1305** | 0.16 | 0.16, 0.26, 0.16, 0.23, 0.44 | 0.28 | 0.103 |
| `meta_model` | **0.0523** | 0.16 | 0.03, 0.95, 0.98, 0.34, 0.04 | **0.95** | **0.421** |

**Stacking effect: the meta-model is worse than its best base model.** `dataset_h` alone (OOF MCC
0.1305) outperforms the 3-model stack (`meta_model`, OOF MCC 0.0523) by more than 2×. Stacking is
**actively hurting** on this sample, not helping.

**Fold-level threshold stability: poor across the board, worst for the meta-model.** Every model's
per-fold best threshold swings by more than its own global threshold value, but the meta-model is
the extreme case — fold thresholds range from 0.03 to 0.98 (essentially the entire [0,1] interval),
with the highest standard deviation (0.421) of any model. A threshold that jumps from 0.03 to 0.98
between folds on the same model is not describing a stable decision boundary; it's describing noise
in a ~54-positives-per-fold regime (271 positives ÷ 5 folds). `dataset_h` is comparatively the most
stable (range 0.28, std 0.103) — consistent with it also having the best OOF MCC.

**Conclusion: current model quality is NOT trustworthy as a representative result.** This matches
`docs/reproducible_metrics_report.md`'s own conclusion, re-verified here directly against
`training_summary.json` rather than taken on faith.

---

## 4. Feature importance — read from `outputs/feature_importance_*.csv`

### High-signal features
- `dataset_h`'s engineered risk features carry real, non-trivial importance:
  `transition_fail_rate_mean` (1496.8), `transition_fail_rate_std` (1485.6), `station_risk_mean`
  (1422.4), `pair_cooccur_std` (1276.6), `path_count` (1266.4), `pair_cooccur_mean` (1136.0),
  `transition_fail_rate_max` (823.2) — these are why `dataset_h` is the best base model.
- `dataset_g`'s `signature_failure_rate` (1795.2) and `duration_x_path_failure_rate` (1668.0) are
  meaningfully used; `rolling_fail_rate_w10000` (138.8) is weak but non-zero.
- Across baseline/g/h, the lean structural features (`feature_mean`, `density_ratio`,
  `records_last_1hr`, `duration`, `records_last_24hr`, `start_time`) dominate raw importance —
  consistently the top 5–6 features in every model. They carry signal but evidently not enough on
  their own (`baseline`'s OOF MCC of 0.0157 uses only these).
- In the meta-model, `dataset_g_pred` (8597.4) and `baseline_pred` (8404.0) get *higher* importance
  than `dataset_h_pred` (7485.6) despite `dataset_h` being the best individual model by OOF MCC — a
  sign the meta-model's importance ranking doesn't track which base model is actually most
  predictive, consistent with it overfitting noise rather than learning a sound combination.

### Weak / dead features
- **`chunk_size` is exactly 0.0 importance in every single model** (`baseline`, `dataset_g`,
  `dataset_h`) — never once used in any split, in any fold, in any model.
- **`chunk_failure_rate` (dataset_g) is exactly 0.0 importance — and this is structurally
  guaranteed, not incidental.** Verified directly: `df["chunk_failure_rate"].nunique() == 1` across
  all 50,000 rows (every row has the exact same value, `0.00542`, the dataset's global failure
  rate). Root cause, confirmed by reading `scripts/build_dataset_g.py`: `chunk_failure_rate` is
  computed by grouping `Response` by `chunk_id` **within the training fold only**, then `.map()`-ed
  onto the validation fold. But `chunk_id` is also the **CV group column** — `make_chunk_aware_splits`
  guarantees train and validation folds never share a `chunk_id`. So for every validation row, the
  `.map()` lookup can never find a match (its own `chunk_id` was never in the training fold's
  groupby), and it always falls back to `global_mean`. **`chunk_failure_rate` is mathematically
  incapable of carrying signal under chunk-grouped CV** — not a leakage risk, the opposite: a
  feature whose construction is structurally incompatible with the CV scheme that protects it.
  Recommendation: drop it, or compute chunk-level rate encoding only if CV grouping is changed to
  not group by the same key (not recommended, since chunk-grouping is what keeps everything else
  leakage-safe).
- `chunk_id` itself has near-zero importance everywhere (81.6 / 70.8 / 35.4 out of importance sums
  in the thousands) — consistent with the existing audit's observation that it's a sequential
  row-order proxy, weak as a feature, and a latent fragility if the Id/time ordering ever shifts.
- `agreement_count` in the meta-model (256.8) is an order of magnitude below the other 6 meta
  features — weak relative to the raw predictions and their summary stats.

### Suspicious / leakage-prone features — see §6 for the full audit. Flagged here:
`pair_cooccur_mean/max/std` (dataset_h) and `path_count` (used in dataset_h) are computed from
**global** signature-frequency counts spanning the full dataset (train + validation rows together),
not restricted to the training fold the way every other target-rate feature in dataset_g/h is. They
do not leak the label directly, but they do leak structural/frequency information about each row's
own fold membership into its own feature value.

---

## 5. CV methodology validation

**Chunk/group-aware split — confirmed enforced in code, not just intended.**
`src/training/cv.py::make_chunk_aware_splits` builds folds via `StratifiedGroupKFold` (falling back
to `GroupKFold`), grouped by `chunk_id`, and **unconditionally calls
`validate_chunk_aware_splits(splits, groups=groups)` before returning** (`cv.py:78`). That function
raises `ValueError` immediately if any `chunk_id` appears in both a train and validation fold, or if
any validation `chunk_id` is reused across folds (`cv.py:17-41`). Every one of `train_baseline.py`,
`train_dataset_g.py`, `train_dataset_h.py`, `train_meta_model.py` (via `train_lightgbm_oof`), and
`build_dataset_g.py`/`build_dataset_h.py` (for their own fold loops) calls this same function. Since
`outputs/training_summary.json` shows all four models completed training with real fold metrics, the
validation necessarily passed for the committed run — **chunk-level leakage across folds is
code-enforced, not just assumed.**

**Persisted vs. recomputed fold assignment — verified consistent, but fragile.**
`build_dataset_g.py`/`build_dataset_h.py` compute their own fold split to build OOF-safe target-rate
features, and save the resulting assignment as a `cv_fold` column in the output parquet. But
`train_dataset_g.py`/`train_dataset_h.py` (via `train_lightgbm_oof`) **do not read that column** —
they independently call `make_chunk_aware_splits` again with the same default config
(`n_splits=5, random_state=42, shuffle=True`) and implicitly rely on getting the identical partition
back. Verified empirically this session — re-running `make_chunk_aware_splits` on the saved
`dataset_g.parquet`/`dataset_h.parquet` and comparing to the persisted `cv_fold` column:
```
dataset_g: persisted cv_fold == independently recomputed fold assignment? True
dataset_h: persisted cv_fold == independently recomputed fold assignment? True
```
Currently consistent, but this is an **implicit contract enforced by nothing** — no assertion
anywhere checks that the two computations agree. If sklearn's `StratifiedGroupKFold` internals ever
change, or the row order between the two read paths ever drifts, the OOF-safe features and the
model's own CV split would silently diverge — features built as "training-fold-only" could end up
described differently than what the model actually validates on, without raising an error.
**Recommendation:** either have `train_dataset_{g,h}.py` read the persisted `cv_fold` column
directly instead of recomputing, or add an assertion that the recomputed split matches it.

**Is `chunk_failure_rate` (and the other dataset_g/h target-rate features) OOF-safe?**
- `chunk_failure_rate`, `signature_failure_rate`/`path_failure_rate`,
  `duration_x_path_failure_rate`, `rolling_fail_rate_w10000` (dataset_g) and
  `transition_fail_rate_{mean,max,std}`, `station_risk_mean` (dataset_h): **yes, OOF-safe.** Each is
  computed inside the fold loop using `tr = df.iloc[train_idx]` only (`build_dataset_g.py:88-107`,
  `build_dataset_h.py:110-163`), then mapped onto the validation fold. (`chunk_failure_rate` is
  OOF-safe by this definition but dead per §4 above — OOF-safety and usefulness are different axes.)
- `pair_cooccur_mean/max/std` (dataset_h): **not fold-restricted** — see §6.
- `path_count` (used as a dataset_h feature): **not fold-restricted** — see §6.
- The `global_mean` fallback constant used throughout dataset_g/h (`build_dataset_g.py:77`,
  `build_dataset_h.py:96`) is computed on the **full** 50k dataset (`df["Response"].mean()`) before
  any fold split, and used as the imputation default for unseen categories. This is a theoretical,
  low-severity leak (the fallback constant for a validation row's missing category is influenced by
  that row's own label, diluted across 50,000 rows) — common practice, but worth naming explicitly
  rather than silently assuming zero leakage.

---

## 6. Leakage-risk inventory (new finding from this audit)

| Feature(s) | Model(s) | Computed from | Fold-restricted? | Risk |
|---|---|---|---|---|
| `chunk_failure_rate` | dataset_g | `tr.groupby("chunk_id")` | Yes | **None** (dead, not leaky — see §4) |
| `signature_failure_rate`, `path_failure_rate`, `duration_x_path_failure_rate` | dataset_g | `tr.groupby("path_signature")` | Yes | None — correct OOF target encoding |
| `rolling_fail_rate_w10000` | dataset_g | training-fold rows only, `.shift(1)` before merge_asof | Yes | None — causal, OOF-safe |
| `transition_fail_rate_{mean,max,std}`, `station_risk_mean` | dataset_h | `tr.groupby("path_signature")` | Yes | None — correct OOF target encoding |
| **`pair_cooccur_mean/max/std`** | dataset_h | `signature_freq = df["path_signature"].value_counts()` (`build_dataset_h.py:84`) — **`df` is the full 50k frame, computed before the fold loop** | **No** | **Structural/non-target leak.** A validation row's own presence (and its fold-mates') contributes to the frequency count baked into its own feature value. Does not leak `Response` directly, so unlikely to meaningfully inflate OOF MCC, but is methodologically inconsistent with every other target-rate feature in the same script. |
| **`path_count`** | dataset_h (feature), also computed for all datasets | `path_counts = merged["path_signature"].value_counts()` in `build_dataset_baseline.py` (full train frame, no fold split at all — baseline dataset has no CV awareness by design) | **No** | Same structural leak as `pair_cooccur_*`, and has *substantive* importance (1266.4) in dataset_h — the dataset_h feature most worth re-auditing if this is fixed. |
| `global_mean` fallback | dataset_g, dataset_h | `df["Response"].mean()` on full 50k frame, used only as an imputation default | No | Low severity, common practice, named here for completeness. |
| `chunk_id`, `chunk_size` | all | Sequential index over Id-sorted rows | n/a (not target-derived) | Not a leakage risk; a stability/generalization risk if Id ordering doesn't hold on new data (near-zero importance already, see §4). |

**Net assessment:** the headline leakage protection this project advertises (chunk-grouped CV,
validated by `validate_chunk_aware_splits`) is real and does work for the features it was designed
to protect. The newly-identified gap is narrower: two features in `dataset_h`
(`pair_cooccur_*`, `path_count`) bypass that protection entirely because they're computed before
and outside the fold loop, on the full dataset. This is a real methodology inconsistency worth
fixing, but it is a much smaller and more specific issue than "leakage is unaddressed" — most of the
target-rate feature engineering in this repo is genuinely careful.

---

## 7. Should the meta-model be kept, fixed, or dropped?

**Recommendation: fix or drop, do not ship as-is.** Evidence:
- OOF MCC 0.0523 vs. best base model (`dataset_h`) at 0.1305 — stacking subtracts more than half the
  signal of the best input.
- Fold-level threshold range of 0.95 (0.03 to 0.98) is not describing a learnable decision boundary;
  it's noise from ~54 positives per fold being further compressed into a 7-feature meta-space.
  `META_FEATURES` includes 3 raw predictions plus 4 derived summary stats
  (`mean/std/max_prediction`, `agreement_count`) of those same 3 predictions — likely
  multicollinear, adding variance without new information at this sample size.
- Feature importance in the meta-model ranks `dataset_g_pred` above `dataset_h_pred` despite
  `dataset_h` being the stronger base model by OOF MCC — the meta-model isn't learning "trust the
  best base model more," it's fitting fold-specific noise.

**If kept:** retrain on full-scale data first (271 positives is too few to evaluate stacking value at
all — variance dominates), and consider dropping the derived summary-stat features
(`mean/std/max_prediction`, `agreement_count`) in favor of the 3 raw predictions alone, or simplifying
to a 2-input stack of just `dataset_h_pred` + `dataset_g_pred` (the two strongest base models).
**If dropped:** serve `dataset_h`'s predictions directly — it is both the best-performing and most
threshold-stable model in this audit.

---

## 8. Do current results justify moving to Kaggle test inference?

**No — not without re-running on full-scale data first.** Three independent reasons converge on the
same answer:
1. **Sample size.** 271 positives split 5 ways (~54/fold) cannot support a trustworthy MCC estimate
   or threshold selection — confirmed directly by the fold-threshold instability in §3, not assumed.
2. **Stacking is regressive on this sample** (§3, §7) — shipping the meta-model would ship a model
   that is worse than the simpler `dataset_h` alone, and we don't yet know if that holds at full
   scale.
3. **Track 2 is blocked on independent infrastructure gaps anyway** (`docs/kaggle_submission.md`):
   no test-side feature-engineering script exists, and committed `models/*.pkl` are still
   pre-Phase-2 bare estimators. Generating Kaggle test features now would be feature work spent
   feeding a model we already have direct evidence not to trust.

---

## 9. Recommended next actions before a real Kaggle submission

In order:
1. **Fix the two non-fold-restricted features first** (`pair_cooccur_*`, `path_count` in
   `dataset_h`) — cheap, scoped, and removes the one confirmed methodology inconsistency in an
   otherwise careful OOF-safety design.
2. **Run a full-scale data prep + training pass** (`docs/reproducible_metrics_report.md` §3a) to get
   an honest full-data OOF MCC per model and re-check whether `dataset_h`'s lead and the meta-model's
   regression both hold at ~1.18M rows / ~6,879 positives. Do not run this without explicit approval
   (training is heavy; this report does not request it, only recommends it as the next gate).
3. **Re-decide the meta-model** using full-scale OOF MCC, per §7's criteria (keep only if it beats
   the best base model; otherwise simplify or drop).
4. **Then, and only then**, resume Track 2 work: build the test-side feature-engineering script and
   persist the rate-lookup tables, per `docs/kaggle_submission.md`'s existing "Known limitation"
   section.
5. Independently, the model-persistence gap (`models/*.pkl` are bare estimators, pre-Phase-2 format)
   needs the same full training run to resolve, so steps 2 and this naturally happen together.

---

## 10. Explicit statement on full-scale model quality

**Full-scale model quality is UNKNOWN.** Every metric in this report — OOF MCC, fold threshold
stability, feature importance, the stacking comparison — is computed on the committed 50,000-row
dev sample (271 positives), not the full ~1.18M-row dataset. No full-scale training run exists in
this repo's history (`docs/reproducible_metrics_report.md` §2–3 already establishes this; this audit
does not change that). The widely-quoted "World B" numbers (`README.md`, `docs/CASE_STUDY_BOSCH_
PRODUCTION_SYSTEM.md`: MCC ~0.30–0.317) are **not validated by this audit and are not assumed valid**
— they come from a file with no reproducing training script anywhere in this repo's git history (see
`docs/production_readiness_audit.md` §6.1 and `data/README.md`). Until a full-scale run is executed
and its `outputs/training_summary.json` reviewed, **no claim about this project's real-world model
quality should be treated as established** — only the dev-sample numbers in this report and in
`docs/reproducible_metrics_report.md` are currently reproducible and verified.
