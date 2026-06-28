# Production Readiness Audit — Bosch Production Line Performance

> **HISTORICAL ARTIFACT — SUPERSEDED.** This audit was performed at commit `b96cd0d` (2026-06-24),
> before Track 3 was built and frozen. All findings from §1's Executive Summary have since been
> resolved: the World A/B gap is documented, the label-free production path is complete and
> validated (`validate_system.py` → `overall_pass: True`, tag `track3-frozen` at `f743da3`),
> and the Kaggle submission path works end-to-end for `dataset_h` (see
> `docs/dataset_h_submission_run.md`). This document is retained as a historical record of the
> pre-Track-3 state, not as a description of the current repository.

**Auditor role:** Senior production ML systems architect / auditor
**Audit date:** 2026-06-24
**Branch audited:** `feature/production-readiness-audit` (forked from `main` @ `b96cd0d`)
**Scope:** Read-only audit. No source code was modified. This is the only artifact produced.
**Method:** Claims were validated against actual code, committed artifacts, parquet schemas/row counts, output JSON/CSV, and the real Kaggle Bosch Production Line Performance challenge setup.

> **Note on agent spec file:** `bosch_agent.md` **exists** and was read, so the fallback to `agent.md` does not apply. Worth flagging for reproducibility: `.gitignore` ignores `agent.md`, `system_design.md`, `execution_rules.md`, and `tasks.md`, and `bosch_agent.md` is currently **untracked**. The governing spec/context documents for this project are therefore **not under version control**. That is itself a reproducibility/documentation gap (see §9.9).

---

## 1. Executive Summary — Verdict

**Kaggle competition readiness: NOT READY.** There is no code path that produces a Kaggle submission. Nothing reads the unlabeled test set, runs inference, thresholds to binary `Response`, and writes a submission CSV. The "Kaggle solution" claim is unsupported by any executable artifact.

**Production ML readiness: NOT PRODUCTION-READY.** The "production" layer is supervised evaluation on labeled, training-derived out-of-fold (OOF) predictions, relabeled as a "production stream." It computes recall/precision on data that has labels — directly contradicting the project's own stated rule that production must not compute supervised metrics. Monitoring is a random split of a single dataset against itself (drift is structurally impossible to detect). There is no working raw→features→prediction inference path for the persisted models.

**The single most important finding:** the repository contains **two disjoint and mutually inconsistent worlds**:

- **World A — the reproducible committed pipeline.** Operates on a **50,000-row truncation** of the dataset (271 positives). The committed models are trained on it. The meta-model's OOF MCC is **0.052** — effectively no signal, and *worse* than its best base model (dataset_h @ 0.131).
- **World B — the frozen "headline" artifacts.** `production_decision_summary.json`, the case study, and the README quote metrics (MCC ~0.30, recall 0.45–0.63) derived from a **1,183,747-row** prediction file (`oof_predictions_context_meta_v2_blend.parquet`, 6,879 positives). **No committed training script produces that file**, and the CSVs the decision summary was built from **no longer exist**. World B is a black box that cannot be reproduced from this repository.

The published results describe World B. The code you can actually run produces World A. They are not the same system, and the gap is not disclosed anywhere in the repo. **Until that is resolved, the reported numbers cannot be trusted as representing the committed code.**

| Dimension | Status |
|---|---|
| Reproducible end-to-end run | ❌ Decision/sim/monitoring source data missing or inconsistent |
| Headline metrics reproducible | ❌ Produced by a model/run absent from the repo |
| Kaggle submission path | ❌ Does not exist |
| Working inference on raw/test data | ❌ No path; persisted models incompatible with inference classes |
| Train/production preprocessing parity | ❌ Cannot verify; no shared transform is exercised |
| Drift monitoring meaningfulness | ❌ Self-vs-self random split |
| Supervised-metric-free production | ❌ "Production" simulation computes recall/precision on labels |
| Model versioning/persistence | ❌ Persists only the last CV fold's estimator |
| Tests / CI | ❌ None |
| Security (credentials) | ⚠️ `.env` gitignored, but bucket hardcoded; creds handling fragile |

---

## 2. Kaggle Readiness vs Production Readiness (kept strictly separate)

### 2.1 Kaggle competition readiness

The real challenge (validated against the actual Bosch Production Line Performance competition):

- **Target:** `Response` (binary), extreme imbalance (~0.58% positive). Confirmed in data: full blend file has 6,879 / 1,183,747 = **0.5811%**.
- **Metric:** Matthews Correlation Coefficient (MCC) on hidden test labels.
- **Test set:** **unlabeled** (confirmed: `data/processed/test_numeric.parquet` has **no `Response` column**; train does).
- **Submission:** CSV of `Id, Response` with **binary 0/1** predictions (the competitor must pick the threshold; Kaggle scores MCC on hidden labels). `sample_submission` schema confirmed: `['Id', 'Response']`.
- **Known leaderboard reality:** top solutions (~0.5+ MCC) leaned heavily on leakage-adjacent "magic" features (record-proximity / Id-ordering / station-path timing patterns computed across the combined train+test set). The project's decision to avoid those is *defensible for production* but means a non-leaky model will score far lower — and the repo never actually generates *any* submission to test this.

**What's missing for Kaggle:**
1. No submission generation script anywhere (`grep` of `scripts/` shows none; `tasks.md` specifies a `scripts/run_batch_inference.py` that was never built).
2. No inference over the unlabeled test parquet/CSV.
3. No threshold-application-to-test step producing 0/1 labels.
4. The persisted models cannot be loaded by the inference classes (see §6.4), so even a hand-written submission script would need new glue code.
5. Processed test data is truncated to 50k rows (real test is ~1.18M), and `sample_submission.parquet` is likewise 50k — a real submission would be rejected by Kaggle for wrong row count.

**Kaggle verdict: not started in any runnable sense.** The trained meta-model's OOF MCC of 0.052 (World A) would translate to a near-bottom leaderboard score; the ~0.30 World-B number is from a model not in the repo.

### 2.2 Production ML readiness

A production predictive-maintenance system needs: a stable raw→features→score contract identical in train and serve; model/threshold versioning; inference on **unlabeled** live data; label-free monitoring (input + prediction drift, data-quality, volume); guardrails; observability; reproducibility; and tests. **Almost none of these are met** (detailed in §5–§9). The "production simulation" is not a production simulation — it is offline supervised scoring of labeled OOF data.

---

## 3. What Currently Works

Credit where due — these components are real and reasonably built **in isolation**:

1. **Leakage-aware CV machinery (`src/training/cv.py`).** `make_chunk_aware_splits` uses `StratifiedGroupKFold` grouped by `chunk_id` and `validate_chunk_aware_splits` actively raises on chunk overlap across folds. This is the strongest engineering in the repo and is genuinely good practice.
2. **OOF-safe target-rate feature construction (`build_dataset_g.py`, `build_dataset_h.py`).** Failure-rate features (chunk/signature/path/transition/station) are computed fold-by-fold from training-fold statistics only, with `pd.merge_asof` for the rolling rate. The *intent and mechanics* of avoiding target leakage are correct.
3. **Memory-safe ingestion (`prepare_data.py`).** Chunked CSV→Parquet with dtype downcasting, safe unzip with path-traversal guard, incremental Parquet writer. Solid.
4. **Decision-engine math (`src/inference/decision_engine.py`).** `apply_threshold` / `apply_topk_budget` / `apply_hybrid` are clean, deterministic (mergesort tie-break), and correct for the policy they implement.
5. **Dashboard compute trick.** The cumulative-sum + `np.searchsorted` threshold/budget sweep in the Streamlit app is efficient and numerically sound.
6. **FastAPI decision service (`apps/api/main.py`).** A thin, well-typed policy endpoint. It scores *pre-computed* scores, not raw parts — but as a policy calculator it works.

**Important caveat:** "works in isolation" ≠ "works as a system." These pieces do not connect into one reproducible, label-free, test-capable pipeline.

---

## 4. Critical Gaps (ranked)

1. **Two disjoint worlds; headline metrics not reproducible.** Committed code → 50k rows, meta OOF MCC 0.052. Headline artifacts → 1.18M rows from `oof_predictions_context_meta_v2_blend` whose training script is absent and whose decision-table source CSVs are missing. (Evidence §6.1, §7.)
2. **No Kaggle submission path and no working test-set inference.** (Evidence §2.1, §6.4.)
3. **"Production simulation" computes supervised metrics on labeled OOF data** — violates the project's own constraint and is not a production simulation. (Evidence §5.2.)
4. **Drift monitoring is self-vs-self.** A random 70/30 split of *one* 50k dataset; `drift_share = 0.0` is guaranteed, not measured. It never compares train vs incoming test. (Evidence §5.3.)
5. **Model persistence saves only the last CV fold's estimator** (`random_state=46` = `42 + fold 4`), not an ensemble and not a model refit on full data. (Evidence §6.2.)
6. **Persisted models are incompatible with the inference classes.** `BoschPredictor.load`/`TwoStagePredictor` expect a payload dict `{"models", "feature_cols", "threshold"}`; the pickles are bare `LGBMClassifier` objects. (Evidence §6.4.)
7. **Trained on a 50k truncation with only 271 positives** → ~54 positives per fold → unstable thresholds (meta fold thresholds: 0.03, 0.95, 0.98, 0.34, 0.04) and near-zero MCC. The "model" is fitting noise. (Evidence §7.2.)
8. **Stacking is regressive.** Meta OOF MCC (0.052) < best base (dataset_h 0.131). The ensemble destroys signal rather than adding it. (Evidence §7.3.)
9. **`validate_system.py` would fail on the current tree** — it reads `outputs/production_decision_table.csv`, which does not exist (only `feature_importance_*.csv` are present). The "validation" has not been run against the committed state.
10. **No tests, no CI, no schema/version pinning of artifacts.** (Evidence §9.8.)

---

## 5. Evidence-Backed Critique of Architecture

### 5.1 The "training ≠ production" separation is asserted, not implemented
`system_design.md` and `execution_rules.md` insist production must be inference-only and must never compute MCC/precision/recall. The actual production scripts do the opposite:

- `scripts/run_batch_simulation.py` loads `meta_dataset.parquet` **with `Response`**, joins OOF predictions, and computes `recall/precision/tp/fp/fn/tn` per batch (`src/inference/decision_engine.py::metrics_from_labels`). Output `batch_simulation_summary.json` reports `recall_mean: 0.603`, `precision_mean: 0.066`. **These are supervised metrics on labeled data.**
- This is offline model evaluation wearing a "streaming production" costume. A real production stream (the unlabeled test set) is never touched.

### 5.2 The data the "production" layer consumes is not production data
`run_batch_simulation.py::load_best_pred` reads `oof_predictions_context_meta_v2_blend.parquet` (1.18M) and `oof_predictions_meta_v3_dataset_h_blend.parquet` (**missing**), then `meta.merge(pred, how="left")` on the 50k `meta_dataset`. Net effect: it scores the first 50k Ids using World-B predictions and grades them against labels. It picks the "best" source by computing a proxy MCC **on labels** at threshold 0.74. Every step assumes labels exist — the exact opposite of production.

### 5.3 Monitoring cannot detect drift by construction
`scripts/run_drift_monitoring.py::build_reference_current` takes ONE dataframe (`meta_dataset` ⋈ blend), does `df.sample(frac=1.0, random_state=42)`, and splits 70/30. Reference and current are **random halves of the same distribution**, so Evidently reports `drifted_columns_count: 0`, `drift_share: 0.0` deterministically (confirmed in `evidently_summary.json`: 35,000 ref / 15,000 cur, 4 columns, 0 drift). Only 4 columns are monitored (`Response`, `dataset_g_pred`, `dataset_h_pred`, `pred`) — and monitoring drift on the **label column** in a random split is meaningless. Real drift monitoring must compare the **training feature distribution** against **incoming test/live feature distributions**; this never happens.

### 5.4 The decision summary is a frozen artifact with a vanished source
`scripts/build_decision_summary.py` short-circuits: "if `production_decision_summary.json` exists, load it." It does exist (committed), so the decision system **never regenerates**. If forced to regenerate, `src/evaluation/decision_system.py::load_tables` requires `max_recall_threshold_sweep.csv`, `inspection_budget_results.csv`, `production_threshold_sweep.csv` — **none of which exist** in `outputs/`. Furthermore the committed summary's `dataset_rows: 1183747` contradicts the current `meta_dataset.parquet` (50,000 rows), so even a successful regen would normalize costs against the wrong denominator. The headline operating points are unreproducible.

### 5.5 S3 storage design does not match the stated design
`system_design.md` mandates partitioned, append-only paths (`predictions/cycle=…/batch=…`). The implemented `src/utils/s3_utils.py::upload_file` is an unconditional `s3.upload_file` to a fixed key — i.e., **overwrite-in-place**, the single thing the design forbids. `run_full_system.py` overwrites three fixed JSON keys each run. There is no partitioning, no append, no versioning, no cycle/batch state in the wired code (the `batch_simulation_state.json`/`batch_stream_log.csv` sliding-mode artifacts are local-only and gitignored).

---

## 6. Model, Persistence & Inference Audit

### 6.1 The two-worlds evidence (definitive)
| Artifact | Rows | Positives | Failure rate | MCC | Reproducible by committed code? |
|---|---:|---:|---:|---:|---|
| `meta_dataset.parquet` (committed; what models trained on) | 50,000 | 271 | 0.542% | meta OOF **0.052** | ✅ yes |
| `dataset_{baseline,g,h}.parquet`, all OOF files | 50,000 | — | — | base ≤ 0.131 | ✅ yes |
| `oof_predictions_context_meta_v2_blend.parquet` (drives dashboard/sim/decision narrative) | **1,183,747** | 6,879 | 0.581% | ~0.30 (implied) | ❌ **no training script** |
| `production_decision_summary.json` (README/case-study numbers) | 1,183,747 | 6,879 | — | up to **0.301** | ❌ source CSVs missing |
| `evidently_summary.json` | 50,000 (35k/15k) | — | — | n/a | ⚠️ runs, but meaningless |

The committed 50k Ids (range 4..100,147) are a **100% subset** of the full blend (range 4..2,367,495) — i.e., the committed processed data is simply the **first ~50k Ids** of the real dataset. Someone trained the real model on the full data (World B), then the repo was left holding a 50k truncation plus the full-data prediction file, with no script tying them together.

**Confirmed by the authors' own note.** `data/README.md` (present on `origin/training-pipeline`) states: *"Original Bosch raw files and intermediate feature/model artifacts were removed for GitHub packaging size and cleanliness."* It keeps `meta_dataset.parquet` and `oof_predictions_context_meta_v2_blend.parquet` as packaged "demo" inputs. So **World B is unreproducible by deliberate decision, not accident** — the model and intermediate artifacts that generated the blend were intentionally deleted. A full-history search (`git log --all -S "context_meta_v2"`) finds the string only in **consumer** code (dashboard, `run_batch_simulation.py`, `run_drift_monitoring.py`); **no producer/training script exists on any branch.** The committed training scripts emit `oof_predictions_final.parquet`, never the blend.

### 6.2 Persistence saves the wrong object
`src/training/modeling.py` sets `final_model = model` **inside** the fold loop, so after training it holds only the **last fold's** estimator (trained on 4/5 of 50k = 40k rows). `train_baseline.py` etc. then `joblib.dump(model)`. Confirmed at load time: every `models/*.pkl` is a single `LGBMClassifier` with `random_state=46` (= `42 + 4`). There is **no fold ensemble** and **no full-data refit**. The OOF MCC reported in `training_summary.json` describes the 5-fold OOF procedure, but the *saved* model is just one fold — its real generalization is unmeasured.

### 6.3 No model versioning / registry / lineage
Models are overwritten in place at fixed paths. No version hash, no training-data fingerprint, no schema snapshot, no metric tag stored *with* the artifact. `BoschPredictor` computes a SHA of the file at load, but nothing persists which data/threshold/feature-list produced it. There is no way to answer "which model+threshold is in production and what was it trained on."

### 6.4 Inference classes cannot load the persisted models
`src/inference/predictor.py::BoschPredictor.load` does `pickle.load` then `model_payload["models"]`, `["feature_cols"]`, `["threshold"]`, and also needs a fitted `FeaturePipeline` plus artifacts (`selected_features_top150.txt`, `selected_categorical_top100.txt`, `train_selected.parquet`) that **do not exist** in this repo. The committed pickles are bare classifiers with none of those keys. `TwoStagePredictor` additionally references `data/models/model_batch_focused_v1.pkl` (absent). **The entire raw-data inference subsystem is dead code relative to the committed artifacts** — it has never been exercised against them and cannot be without new glue + missing files.

### 6.5 `FeaturePipeline` is unused by anything wired up
`src/features/pipeline.py` (a large, ambitious Phase-5 feature contract) is imported only by the dead inference classes. The *training* pipeline builds features through a completely different path (`core_pipeline.py` + the `build_dataset_*` scripts). So there are **two unrelated feature-engineering implementations**, and the one with the careful train/serve contract is the one nothing runs. Train/serve preprocessing parity is therefore **not just unverified — it is architecturally impossible to claim**, because training and the (notional) serving path use different code.

---

## 7. Metrics & Evaluation Critique

### 7.1 Headline numbers do not describe the committed model
README: "Best MCC ~0.317." Case study: balance point MCC 0.30, min-cost recall 0.4505. These come from `production_decision_summary.json` / the 1.18M blend — **World B**. The committed, reproducible meta-model scores **MCC 0.052** (World A). Quoting World-B numbers as the project's results, while shipping World-A code, is misleading.

### 7.2 The committed model is fitting noise
With 271 positives over 50k rows (~54 per fold), per-fold "best thresholds" for the meta-model are **0.03, 0.95, 0.98, 0.34, 0.04** — i.e., MCC is so flat/noisy that the argmax jumps across the entire range. A stable model on real signal does not do this. The single global `best_threshold` (0.16) is not trustworthy and would not transfer to the full distribution.

### 7.3 Stacking is regressive
Base OOF MCC: baseline 0.016, dataset_g 0.046, dataset_h **0.131**. Meta (stacked) OOF MCC: **0.052**. The meta-model is *worse than simply using dataset_h alone*. This is a red flag that the stack is overfitting the tiny positive set and/or that `agreement_count` (importance 256 vs ~8,600 for the raw preds) and the mean/std/max features are adding variance, not signal. On the committed data, the ensemble is a net negative.

### 7.4 Threshold selection methodology
On the *training* side thresholds are chosen on OOF predictions (acceptable, no test leakage). But: (a) the saved model is one fold, so the OOF threshold doesn't match the saved estimator; (b) the production/decision thresholds in World B were chosen on the full labeled OOF set — fine for analysis, but there is **no held-out confirmation** and no application of any threshold to the unlabeled test set. There is no temporal/holdout validation despite the data being explicitly time-ordered (`start_time`).

### 7.5 `chunk_id` as a model feature
`chunk_id` is a sequential integer derived from sorting by `start_time` (`core_pipeline.py`) — effectively a row-order/time proxy and an identifier. It is used as a *model feature* in baseline/g/h. Importance is near-zero (35.4 in dataset_h; `chunk_size` is literally 0.0), so it's not actively harmful, but feeding identifiers/positional indices to the model is poor practice and a latent leakage/instability risk if the ID distribution shifts.

---

## 8. Data & Feature Engineering Audit

### 8.1 Processed data is a silent 50k truncation
Raw CSVs are full size (train_numeric.csv 2.1 GB), but every `data/processed/*.parquet` is **exactly 50,000 rows** (train_numeric 970 cols incl. Response; test_numeric 969, no Response — schema-consistent with real Bosch). Nothing documents that processed data is truncated. Anyone re-running training on the committed processed files silently trains on 4% of the data with 271 positives. This is the root cause of the broken World-A metrics.

### 8.2 Feature signal
- dataset_h's engineered risk features carry real importance (`transition_fail_rate_mean` 1,497, `station_risk_mean` 1,422, `pair_cooccur_*`), and dataset_h is the only base model with non-trivial MCC (0.131) — so the path/transition features *do* carry signal even on 50k.
- The lean baseline block is weak (MCC 0.016); `density_ratio`, `records_last_*` dominate but don't separate classes at this sample size.
- `chunk_size` importance 0.0 → dead feature on this data. `chunk_id`, `pair_cooccur_max` near-dead.
- **No EDA artifacts exist.** No notebooks, no plots, no missingness/sparsity analysis, no feature-distribution or class-separation analysis is committed. The workflow's "EDA → identify high-signal features → drop noisy features" step is absent; feature lists are hardcoded.

### 8.3 Train/test schema consistency (the one genuinely good data fact)
Train vs test numeric column counts differ by exactly one (`Response`), and categorical/date counts match (2141/1157). The underlying raw data is the real Bosch data and is schema-consistent. The problem is not the raw schema — it's that no pipeline converts the *test* schema into the *model's* feature contract.

### 8.4 Are the processed parquet files trustworthy?
For the 50k rows present: yes, they're internally consistent (Ids align across feature files; failure rate ~0.54% matches expectation for a small slice). For representing the project's claims: **no** — they are a non-representative truncation, and the artifacts that back the claims (World B) are not regenerable from them.

---

## 9. Security, Reliability, Observability, Monitoring & Guardrails

### 9.1 Security
- ✅ `.env` is gitignored; credentials are read via `python-dotenv`.
- ⚠️ The S3 bucket name is **hardcoded** in `apps/streamlit_dashboard/app.py` (`bosch-ml-production-anudeep-193116635897-ap-south-2-an`) and in `tasks.md` — bucket identity (incl. account-id-looking string) is in source.
- ⚠️ `s3_utils.py` relies on `AWS_ACCESS_KEY`/`AWS_SECRET_KEY` env vars (long-lived keys) rather than IAM roles/instance profiles; the dashboard uses default credential chain (`boto3.client("s3", region_name=...)`) — **two different auth mechanisms** for the same bucket.
- ⚠️ No input validation/auth on the FastAPI service; no rate limiting; no payload-size bounds beyond Pydantic `min_length=1`.

### 9.2 Reliability
- `upload_file` swallows exceptions and prints ✅/❌ — failures don't propagate, so `run_full_system.py` can report success while uploads silently fail.
- No retries, no idempotency keys, no transactional/append semantics on S3 (overwrites).
- No schema validation on load; a malformed parquet would crash mid-run with no recovery.

### 9.3 Observability
- Logging is local file + stdout (`src/logger.py`), per-process, timestamped filenames. No structured logs, no metrics export, no tracing, no run IDs, no centralized sink. No health/readiness beyond `/health` returning `{"status":"ok"}` (which doesn't check model/artifact availability).

### 9.4 Monitoring (see also §5.3)
- Self-vs-self drift; label column monitored; only 4 columns; thresholds fixed; no input-feature drift vs training; no data-quality checks (nulls, ranges, cardinality, volume); no alerting. **Monitoring is non-functional as a production signal.**

### 9.5 Guardrails
- None. No prediction sanity bounds, no "model expects N features / got M" gate at serve time (the dead `BoschPredictor` has schema checks, but it's not wired), no fallback policy, no canary, no kill-switch.

### 9.6 Reproducibility
- Headline results not reproducible (§5.4, §6.1). Random seeds are set in training; good. But: processed data truncated and undocumented; decision source CSVs missing; the World-B model training script absent; governing spec docs gitignored; no environment lockfile with hashes (only loose ranges in `requirements.txt`/`environment.yml`); `evidently>=0.7.21,<0.8` is pinned tightly enough that the report-dict parsing in `drift_detection.py` is brittle to Evidently internals.

### 9.7 Deployment readiness
- Dockerfiles install dependencies ad-hoc via `pip install <list>` instead of `requirements.txt` — the API image installs **no model/inference deps for raw scoring** (just fastapi/pandas/etc.), consistent with it being a policy calculator only. `docker-compose` mounts local `./data` and `./outputs`, so containers depend on host artifacts — not a portable deployment. No LightGBM in either image (fine, since neither serves the model). No CI build/test.

### 9.8 CI / Testing
- **Zero tests.** No `tests/`, no pytest/conftest/pyproject config. `validate_system.py` is the only check and it **fails on the current tree** (missing `production_decision_table.csv`). No GitHub Actions / pre-commit.

### 9.9 Documentation
- README and case study overstate maturity and quote World-B metrics without disclosing they aren't reproducible. Architecture doc describes a flow (`data/features` + `outputs` → decision → sim/monitoring → dashboard) that doesn't match the wired S3 loads and frozen artifacts. Spec docs are gitignored.

---

## 10. Do the Results Back the Claims?

**No.**

- "Best MCC ~0.317 / 0.30" — from a model **not in the repo**; the committed model scores **0.052**.
- "Recall @ 10% inspection ~0.63", "min-cost recall 0.4505" — from `production_decision_summary.json` whose source CSVs are **gone** and whose row count (1.18M) contradicts the committed data (50k).
- "Fully production-safe pipeline" / "leakage-safe" — the leakage-aware *CV* is real, but the *production* layer computes supervised metrics on labels, monitoring is self-vs-self, and no label-free inference path exists.
- "Batch simulation (streaming-like)" — it's offline supervised scoring of 50k labeled OOF rows.
- "Drift detection (Evidently)" — runs, but on a random split of one dataset; detects nothing by construction.

The claims describe an aspirational system (World B + the design docs). The repository delivers World A + disconnected scaffolding.

---

## 11. Does the Current Plan Make Sense for the Actual Kaggle Challenge?

**Partially, in intent; no, in execution.**

- Correct understanding: target `Response`, MCC metric, extreme imbalance, unlabeled test, chunk/group-aware CV to avoid leakage. ✅
- Correct, defensible *philosophy*: avoid the leaderboard's leakage "magic features" in favor of deployable signal. ✅ (but it must then be honest that MCC will be lower).
- Broken execution: no submission, no test inference, model trained on 4% of data, saved model = one fold, stacking that *reduces* MCC, and a "production" story that is really relabeled offline evaluation. ❌

The plan conflates two products (a Kaggle submission and a production system) and ships neither end-to-end. They share feature engineering and a trained model, but **diverge at the output**: Kaggle needs `Id,Response` on unlabeled test; production needs label-free scoring + monitoring on a live stream. The repo builds the shared middle and skips both ends.

---

## 12. Remediation Roadmap

### 12.1 Immediate (correctness & honesty — days)
1. **Disclose the two-worlds problem.** Update README/case study to state which metrics are reproducible and which came from an absent run. Stop quoting World-B numbers as the committed result.
2. **Reproduce or remove World B.** Either commit the training script that produced `oof_predictions_context_meta_v2_blend.parquet` (and the decision source CSVs), or delete the frozen artifacts and re-derive everything from the committed pipeline on full data.
3. **Regenerate processed data on the FULL dataset** (or document the 50k slice as a dev sample and keep production artifacts separate). With full data + ~6,879 positives, re-evaluate MCC honestly.
4. **Fix model persistence** to save what you actually intend to serve: either the full fold ensemble (`{"models", "feature_cols", "threshold"}` payload that `BoschPredictor` expects) or a single model refit on all training data. Make `train_*.py` and `BoschPredictor` agree on the format.
5. **Make `build_decision_summary.py` regenerate** instead of short-circuiting on a stale JSON; ensure the source CSVs are produced by a committed step.
6. **Fix `run_full_system.py` upload** to fail loudly (don't swallow S3 exceptions).

### 12.2 Short-term (make each product real — 1–3 weeks)
7. **Build the Kaggle submission path:** unlabeled `test_*` → same feature transform as train → ensemble score → apply OOF-selected threshold → `submission.csv` (`Id,Response`, full ~1.18M rows). Validate row count against `sample_submission`.
8. **Build a real label-free inference path** that consumes the test/live stream, reuses the *exact* training feature code (one implementation, not two), and writes **scores only** (no recall/precision). Retire or rewrite `run_batch_simulation.py` so it does not compute supervised metrics on "production" data.
9. **Fix monitoring:** reference = training feature distribution; current = incoming (test/live) feature distribution. Monitor input features + prediction score distribution + data quality + volume. Drop the label column from drift.
10. **Reconcile train/serve preprocessing into one module** and add a contract test that the same raw row produces identical features in both paths.
11. **Add a smoke-test CI** that runs the full pipeline on the 50k dev sample end-to-end and runs `validate_system.py` (after fixing it to match committed outputs).

### 12.3 Production hardening (3–6 weeks)
12. Model registry / versioning: persist model + data fingerprint + feature list + threshold + metrics together; tag what's "in production."
13. Guardrails at serve time: feature-count/schema gates, score-range checks, fallback policy, canary.
14. S3 redesign to the **append-only partitioned** scheme the design already specifies; IAM roles over long-lived keys; single auth mechanism.
15. Structured logging + run IDs + metrics export + meaningful `/health` (checks artifacts/model load).
16. Real unit tests for CV leakage, OOF-safety of target features, decision-engine math, and feature parity.
17. Dependency lockfile with hashes; Dockerfiles install from it; pin Evidently and add a parsing contract test.

### 12.4 Long-term architecture (quarter+)
18. Decide the product boundary explicitly: a Kaggle track and a production track that share a feature library but have separate, tested entry/exit points.
19. Temporal/holdout validation (data is time-ordered) in addition to group CV.
20. Automated retraining triggered by *real* drift signals; model approval gate before promotion.
21. Backtesting harness for decision policies against historical labeled data, kept strictly separate from the label-free production scorer.

---

## 13. Sub-Agent Execution Plan

> Spawn only on explicit user request. Each agent is read-first, proposes changes, and respects the constraints in `bosch_agent.md`/`execution_rules.md` (minimal scoped diffs; no supervised metrics on unlabeled data; append-only S3; user does git). Agents must run in dependency order — **A and B before the rest.**

### Agent A — Architecture Planning
- **Objective:** Define the explicit two-track architecture (Kaggle vs production), resolve the two-worlds inconsistency, and specify a single shared feature library.
- **Inspect:** `src/features/*`, `scripts/build_dataset_*`, `src/inference/*`, `run_full_system.py`, `system_design.md`, this audit.
- **Deliverables:** Target architecture doc; decision on World-B (reproduce vs discard); interface spec for the shared feature module and the model payload format.
- **Dependencies:** none (first).
- **Acceptance:** A written, reviewed design where every claimed metric maps to a reproducible step, and train/serve share one feature implementation.

### Agent B — Evaluation & Validation
- **Objective:** Establish trustworthy, leakage-free evaluation and reconcile reported vs reproducible metrics.
- **Inspect:** `src/training/cv.py`, `src/training/modeling.py`, `training_summary.json`, all OOF parquets, `production_decision_summary.json`.
- **Deliverables:** Re-run on full data; honest MCC report; threshold-selection methodology with held-out/temporal confirmation; explanation+fix for the regressive stack; corrected README/case-study numbers.
- **Dependencies:** A.
- **Acceptance:** Single source of truth for metrics; meta-model ≥ best base model OR a documented decision to drop stacking; thresholds stable across folds.

### Agent C — Pipeline / Workflow Implementation
- **Objective:** Make the end-to-end runs real: full-data processing, fixed persistence, Kaggle submission, and a label-free production scorer.
- **Inspect:** `prepare_data.py`, `train_*.py`, `build_decision_summary.py`, `run_batch_simulation.py`, `s3_utils.py`, `run_full_system.py`.
- **Deliverables:** Full-data ingestion; ensemble/refit persistence matching `BoschPredictor`; `scripts/generate_submission.py` (Id,Response over full test); rewritten production scorer that emits scores only; append-only partitioned S3 writes; non-swallowing error handling.
- **Dependencies:** A, B.
- **Acceptance:** Cold-clone reproduces all artifacts and metrics; a valid full-size `submission.csv` is produced; production scorer computes zero supervised metrics; `validate_system.py` passes.

### Agent D — Feature Engineering & EDA
- **Objective:** Add the missing EDA/analysis layer and verify feature signal/parity at full scale.
- **Inspect:** `data/processed/*`, `build_dataset_{baseline,g,h}.py`, `core_pipeline.py`, `pipeline.py`, feature-importance CSVs.
- **Deliverables:** EDA notebook/report (missingness, sparsity, class separation, leakage checks, station-path analysis); high-/low-signal feature shortlist; drop dead features (`chunk_size`, etc.); confirm OOF-safety of target-rate features at full scale.
- **Dependencies:** A (feature-library interface); runs alongside C.
- **Acceptance:** Committed EDA artifacts; documented feature selection rationale; no target leakage demonstrated via tests.

### Agent E — Monitoring / Observability
- **Objective:** Replace self-vs-self drift with real train-vs-incoming monitoring; add observability.
- **Inspect:** `src/monitoring/drift_detection.py`, `run_drift_monitoring.py`, `evidently_summary.json`, dashboard.
- **Deliverables:** Reference=train features / current=incoming features drift; input + prediction + data-quality + volume monitoring (label-free); structured logging + run IDs + metrics; meaningful `/health`; alert thresholds.
- **Dependencies:** A, C (needs the real scorer output).
- **Acceptance:** Drift demonstrably fires on a synthetically shifted test slice; no supervised metrics in any production monitor; dashboard reflects label-free production state.

### Agent F — Security / Reliability
- **Objective:** Harden credentials, storage, serving, and CI.
- **Inspect:** `s3_utils.py`, dashboard S3 config, `apps/api/main.py`, Dockerfiles, `docker-compose.yml`, `.gitignore`, `.env` handling.
- **Deliverables:** IAM-role/single-auth design; remove hardcoded bucket to config/env; API auth + payload bounds; retries/idempotency; dependency lockfile with hashes; smoke-test CI; guardrails (schema gate, score bounds, fallback).
- **Dependencies:** A, C.
- **Acceptance:** No secrets/bucket identity in source; CI runs pipeline + tests green; serve-time guardrails enforced; S3 writes append-only.

---

## 14. Final Prioritized Checklist — Before Calling This Production-Grade

**Blockers (must fix):**
- [ ] Resolve the two-worlds inconsistency: every reported metric reproducible from committed code.
- [ ] Train on the full dataset; report honest MCC; stop quoting absent-run numbers.
- [ ] Persist the model you actually serve (ensemble or full-data refit), in a format the inference code loads.
- [ ] One shared train/serve feature implementation, with a parity test.
- [ ] A working label-free inference path on the unlabeled test/live stream (scores only).
- [ ] Kaggle: full-size `submission.csv` (`Id,Response`) generated and row-count-validated.
- [ ] Remove supervised metrics from the "production"/streaming path.
- [ ] Real drift monitoring (train vs incoming, input features), not self-vs-self.
- [ ] `validate_system.py` passes against committed artifacts; add smoke-test CI.

**High priority:**
- [ ] Fix the regressive stack (meta ≥ best base) or drop it, with evidence.
- [ ] Stable threshold selection with held-out/temporal confirmation.
- [ ] Append-only partitioned S3; non-swallowing upload errors; single auth mechanism (IAM roles).
- [ ] Model registry: version + data fingerprint + feature list + threshold + metrics.
- [ ] Commit EDA/feature-analysis artifacts; drop dead features.

**Hardening:**
- [ ] Serve-time guardrails (schema gate, score bounds, fallback, canary).
- [ ] Structured logging, run IDs, metrics export, meaningful `/health`.
- [ ] Dependency lockfile w/ hashes; Dockerfiles build from it; pin + test Evidently parsing.
- [ ] Unit tests: CV leakage, OOF-safety, decision math, feature parity.
- [ ] Put governing spec docs under version control.

---

## 15. Unknowns / Evidence Not Available
- **S3 bucket contents are unverified** (no credentials in audit env). The dashboard loads `oof_predictions_final.parquet` from S3; locally that's the 50k World-A file, but the S3 copy may be the 1.18M World-B file. The local/S3 divergence is a real risk but its current state is **unknown**.
- ~~The provenance of `oof_predictions_context_meta_v2_blend.parquet` is unknown~~ — **RESOLVED during audit.** Full-history search and a branch diff confirm no producer script exists on any branch, and `data/README.md` states the generating artifacts were deliberately deleted for packaging. World B must be rebuilt from scratch (or recovered from wherever the original full run lives, outside this repo). What's unknown is whether the original full-data training code/artifacts still exist **anywhere** off-repo.
- **Why processed data is exactly 50k** (deliberate dev sample vs interrupted conversion) is unknown; either way it is undocumented.
