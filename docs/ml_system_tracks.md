# ML System Tracks: Three-Track Architecture

This document is the canonical statement of the project's scope split. It **clarifies** the
existing two-flow framing in `system_design.md` and the two-track framing in `bosch_agent.md`
into three explicit tracks, and resolves an ambiguity neither of those docs addressed: the
Streamlit dashboard is not one thing, it must be (eventually) two separate views with different
data contracts. This document only records the target architecture and an audit of where current
docs/code already match or diverge from it. **No code was changed to produce this document.**

## Why three tracks, not two

`bosch_agent.md` and `system_design.md` both describe a two-way split: "training" vs
"production," with Kaggle either out of scope ("IGNORE FOR NOW" in `bosch_agent.md`) or absent
entirely (`system_design.md` never mentions Kaggle/submission). That framing collapses two
genuinely different consumers of the trained model into one "production" bucket:

- Scoring **Kaggle's unlabeled test set** to produce a leaderboard submission (a one-shot batch
  job with a fixed output contract: `Id,Response`).
- Scoring a **simulated live stream** of unlabeled batches for an internal decision/monitoring
  system (an ongoing job with state, drift checks, and a risk-score output, no CSV submission).

Both consume the same frozen, approved model and both operate on unlabeled data, but they have
different inputs, different outputs, and different success criteria. Treating them as one
"production" track is what previously let Kaggle submission go unbuilt while "production"
absorbed supervised-metric logic that belongs to offline evaluation (see the audit below).
Splitting them into Track 2 and Track 3 makes each one's contract checkable on its own.

---

## Track 1: Offline Training + Evaluation

- **Input:** labeled training data (`data/processed/train_*.parquet`, with `Response`).
- **Purpose:** EDA, feature engineering, model training, OOF/holdout validation, threshold
  tuning, MCC/precision/recall/accuracy, confusion matrix, feature importance, model approval.
- **Output:** an approved, frozen model artifact, its feature schema, a selected decision
  threshold, and a metrics report.
- **Maps to existing code:** `scripts/prepare_data.py` → `build_dataset_{baseline,g,h}.py` →
  `train_{baseline,dataset_g,dataset_h}.py` → `train_meta_model.py`, plus
  `src/evaluation/decision_system.py` and `docs/reproducible_metrics_report.md` for honest
  metrics reporting.
- **Dashboard view allowed:** Offline Evaluation / Decision Analysis (View B below) — and only
  this view.

## Track 2: Kaggle Submission

- **Input:** unlabeled Kaggle test files (`test_numeric.csv`, `test_categorical.csv`,
  `test_date.csv` / their parquet equivalents).
- **Purpose:** generate a competition submission.
- **Process:** load the Track 1 approved model artifact → apply the identical feature
  transformation used in training → predict probabilities → apply the selected threshold →
  write `submission.csv`.
- **Output:** `submission.csv` with exactly `Id` and `Response` columns, row count matching
  Kaggle's `sample_submission`.
- **Constraint:** no local supervised metrics — Kaggle test labels are hidden, so MCC/precision/
  recall cannot be computed locally for this track.
- **Current state: scripts/generate_submission.py exists, but cannot yet produce a real
  full-size submission.** It loads a Phase-2 model payload, applies it to an already
  feature-engineered unlabeled test table, and writes `Id,Response` — see
  `docs/kaggle_submission.md` for the full design and validation evidence. Two pre-existing gaps
  block an actual end-to-end run today: (1) no test-side feature-engineering script exists (only
  `train_*` has a `build_dataset_*.py`), so there is no engineered test parquet to point the
  script at; (2) the committed `models/*.pkl` are still bare `LGBMClassifier` objects (pre-Phase-2
  format), not the payload dict the script requires. Both are documented as known limitations in
  `docs/kaggle_submission.md`, not fixed in that change. `tasks.md` describes a related but
  distinct batch-inference spec that was also never built.

## Track 3: Production Inference Simulation

- **Input:** unlabeled incoming batches, simulated from test-data chunks.
- **Purpose:** mimic a Bosch factory scoring flow — i.e., simulate what would happen if the
  approved model scored a live, unlabeled stream.
- **Process:** load the frozen approved model → score each batch → append predictions/risk
  scores → compute batch statistics (counts, score distributions, throughput) → monitor
  drift/data quality → update the dashboard.
- **Output:** predictions, risk scores, batch stats, drift/data-quality summaries.
- **Constraint:** no MCC/precision/recall/accuracy/TP/FP/TN/FN/confusion matrix anywhere in this
  track's output, because by definition its input is unlabeled.
- **Current state: resolved for `dataset_h` via a SPLIT, not a rewrite-in-place.**
  `scripts/run_batch_simulation.py` (the script formerly positioned as this track, despite
  actually being Track 1 logic — see below) has been renamed to `scripts/run_offline_batch_eval.py`
  and re-labeled as what it actually is: a labeled OOF threshold/budget replay
  (`data/features/meta_dataset.parquet` **with `Response`**, `metrics_from_labels`/`simulate_batches`
  computing real `recall`/`precision`/`tp`/`fp`/`fn`/`tn`). It is no longer wired into
  `scripts/run_full_system.py`'s "production" stage and is no longer described as part of the
  "Production Pipeline" in `README.md`. It remains useful as a standalone Track 1 tool — a
  threshold/budget sweep replayed batch-by-batch — and its output
  (`outputs/batch_simulation_summary.json`, quoted in `docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md`
  §8) is now explicitly labeled there as Track 1 output, not production output.

  The genuinely label-free replacement is `scripts/run_production_inference.py` (new,
  `dataset_h`-only — the approved candidate model): it consumes
  `data/features/test_dataset_h.parquet` (built by `scripts/build_test_dataset_h.py`, the
  fingerprint-validated, `Response`-free feature contract), scores it with
  `models/dataset_h_model.pkl`, and emits exactly this track's spec — predictions/risk scores,
  batch stats, score distributions, `batch_id`/`cycle_id`/timestamp — with zero MCC/precision/
  recall/accuracy/confusion-matrix/TP/FP/TN/FN anywhere, by construction (grep-verified). It is
  now wired into `scripts/run_full_system.py`'s "production" stage in place of the old script.
  `batch_id`/`cycle_id` state-machine semantics follow `tasks.md`'s documented contract (batch_id
  resets per cycle, cycle_id increments on wraparound; a separate `run_seq` field is the
  lifetime-monotonic counter).

  **S3 upload of Track 3's partitioned output is now wired** (`src/utils/s3_utils.py`'s
  `upload_file_append_only`/`key_exists`, called from `scripts/run_production_inference.py`
  after the local parquet write, before state advances — upload-then-advance, failure-loud,
  never overwrites an existing key; `--no-s3` skips it for local-only runs). **Still not yet
  done** (separate follow-up, not this change): a dashboard Production Monitoring view (View A
  below) rendering Track 3's output; `scripts/run_drift_monitoring.py` is still Track-1-shaped
  (reads `meta_dataset.parquet` with `Response`) and was not touched by this change — it has the
  same mislabeling pattern this section used to describe, just not yet addressed for the
  monitoring script specifically.

---

## Dashboard: two views, not one

### View A — Production Monitoring View

- Uses unlabeled production-like batches.
- Shows: predictions, risk scores, batch counts, score distributions, data quality, drift,
  throughput, latest batch/cycle, top risky parts.
- **Must NOT show** MCC, precision, recall, accuracy, TP, FP, TN, FN, or a confusion matrix,
  because production/test batches are unlabeled.
- **Current state: exists for Track 3's predictions/risk-score output.**
  `apps/streamlit_dashboard/app.py`'s new "Production Monitoring (Track 3)" page lists and
  concatenates every `predictions/cycle=*/batch=*/predictions.parquet` object in S3, runtime-
  asserts the result has no `Response` column, and renders only label-free panels (total
  predictions, latest cycle/batch/run_seq, flagged/auto-reject/manual-inspect counts, a risk-score
  histogram, batch growth/cumulative-predictions, and a top-100-by-risk-score table) — no
  supervised metric anywhere on the page. **Still open:** drift/data-quality rendering — a `grep`
  for `drift`/`evidently` in that file still returns zero matches, even though
  `scripts/run_drift_monitoring.py` already produces `outputs/monitoring/evidently_summary.json` +
  `.html`; that output is generated but still never rendered in the dashboard.

### View B — Offline Evaluation / Decision Analysis View (this is what exists today)

- Uses labeled training validation / OOF data only.
- May show threshold sliders and how MCC, precision, recall, accuracy, TP, FP, TN, FN,
  confusion matrix, inspection budget, and cost trade-offs change.
- This is allowed because it is not production inference — it is a model-evaluation and
  decision-policy analysis tool.
- **Current state: still every other page in the dashboard**, mostly not labeled as such.
  Every section in `apps/streamlit_dashboard/app.py` (Threshold Explorer, Inspection Budget
  Simulator, Recall at Fixed Precision, Cost Simulator, Model Insights, Failure Analysis) loads
  `meta_dataset.parquet` joined to `oof_predictions_final.parquet` — both labeled, both
  Track-1-derived. The data source is correctly labeled data (so the *math* is legitimate
  View-B work), but:
  - The loader function is named `load_scoring_data()` and its result is assigned to a variable
    named `live_df` throughout (e.g. `apps/streamlit_dashboard/app.py:274,427,475,497`) —
    `live_df` is a misleading name for labeled OOF data.
  - These pages still aren't individually labeled "Offline Evaluation" or "Decision Analysis" in
    the UI; a one-line top-of-page caption now states that every page except "Production
    Monitoring (Track 3)" uses labeled OOF data, but the per-page naming/labeling cleanup below is
    still open.

**Per the user's explicit instruction for the original change: do not refactor the dashboard
beyond what's needed to add View A.** Remaining work: (1) fully relabel existing sections as the
Offline Evaluation / Decision Analysis view (today there's only the one top-level caption), (2)
rename `live_df` to something like `oof_eval_df`, (3) **done** — a new, separate Production
Monitoring (Track 3) page now exists, backed by Track 3's real label-free S3 output, (4) wire the
existing Evidently HTML/JSON into that new view. Only (3) is done; (1), (2), (4) remain open.

---

## Current state vs. target state (summary table)

| Track / View | Target | Current state |
|---|---|---|
| Track 1: Offline Training + Evaluation | Labeled data in, approved model + metrics out | **Exists**, with the World A/B reproducibility caveats already documented in `docs/reproducible_metrics_report.md` |
| Track 2: Kaggle Submission | Unlabeled Kaggle test in, `submission.csv` out | **Script exists** (`scripts/generate_submission.py`), but blocked end-to-end by two pre-existing gaps: no engineered test feature table, and committed models are pre-Phase-2 bare estimators — see `docs/kaggle_submission.md` |
| Track 3: Production Inference Simulation | Unlabeled simulated batches in, label-free predictions/drift out | **Exists for `dataset_h`**: `scripts/run_production_inference.py` is genuinely label-free (verified: no `Response`, no supervised metrics) and wired into `scripts/run_full_system.py`'s "production" stage. The old mislabeled script is now `scripts/run_offline_batch_eval.py`, honestly Track 1. S3 upload of Track 3's partitioned output is wired (append-only, upload-then-advance), and Dashboard View A (next row) now renders it. Still open: drift in the dashboard |
| Dashboard View A: Production Monitoring | Label-free batch/drift/data-quality view | **Exists for predictions/risk-scores** in `apps/streamlit_dashboard/app.py`'s "Production Monitoring (Track 3)" page (label-free, verified no `Response`/no supervised metrics). Still open: drift/data-quality rendering (Evidently output exists but isn't wired into this view) |
| Dashboard View B: Offline Evaluation / Decision Analysis | Labeled OOF data, supervised metrics, threshold/cost tuning | **Exists and is correct on data**, but unlabeled as such and uses misleading naming (`live_df`) |

---

## Misleading-language audit

Searched the repo for `MCC`, `precision`, `recall`, `accuracy`, `confusion matrix`, `TP`, `FP`,
`TN`, `FN`, `Response` in docs and dashboard-related code, and classified every occurrence in a
production/dashboard-adjacent context into one of three buckets:

- **Valid** — offline-evaluation language, correctly scoped (Track 1, or explicit Kaggle-leaderboard discussion).
- **Invalid** — misleading production language: a "production"/"batch simulation"/"live" framing
  applied to what is actually labeled-data evaluation, without disclosing that.
- **Code-level issue** — the doc language is reporting actual code behavior accurately, and the
  *code* is what needs to change (not just the words).

| Location | Language | Classification |
|---|---|---|
| `execution_rules.md:38-43`, `tasks.md:17-22`, `bosch_agent.md:38-39` | "Test data is UNLABELED → NEVER compute MCC/precision/recall" | **Valid** — this is the rule statement itself |
| `system_design.md:48,55` | "Training Flow... MCC/precision/recall" / "Production flow MUST NOT compute MCC/precision/recall" | **Valid** — correct rule, but file is silent on Track 2 and the two dashboard views (updated in this change, see below) |
| `docs/reproducible_metrics_report.md` (all MCC/recall mentions) | OOF MCC per model, World A vs World B reproducibility | **Valid** — explicitly scoped to Track 1, already the most precise doc in the repo on this topic |
| `docs/architecture.md:1,10` | Diagram titled "Production Architecture" containing `Batch Logs\nrecall/precision/flagged` | **Invalid** — recall/precision attributed to a diagram titled "Production," with no disclosure that the underlying batches are labeled OOF data, not live unlabeled data |
| `README.md:34-39` ("🔵 Production Pipeline") | Lists "Batch simulation (streaming-like behavior)" under Production | **Invalid** — `run_batch_simulation.py` is Track 1 logic (see Track 3 section above); calling it "production" is the same mislabeling baked into a top-level doc |
| `README.md:81-84` ("📊 Key Results") | "Best MCC: ~0.317", "Recall @ 10% inspection: ~0.63", "Fully production-safe pipeline" | **Invalid** — already flagged as World-B/unverified for *reproducibility*, but the disclaimer never addresses that these are labeled-data evaluation numbers being presented under a doc titled "Production ML System"; "Fully production-safe pipeline" is an unsupported claim given Track 3's current state |
| `README.md:122-128` ("📈 Dashboard Features") | "Recall vs precision trade-offs" etc., listed without a view label | **Invalid** — these are View B (Offline Evaluation) features, listed under a README that frames the dashboard as part of the "Production Pipeline" with no A/B split |
| `docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md` §7 "Measured Operating Points" | Recall/Precision/TP/FP/FN/TN from `production_decision_summary.json` | **Valid math, invalid placement** — the numbers are legitimately computed on labeled data (View B work), but the section sits inside a document framed entirely as a "production decision system" case study with no Track/View label on the section itself |
| `docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md` §8 "Simulation Results" | "Mean recall across simulated batches: 0.6320" | **Invalid** + **code-level issue** — this is the doc faithfully reporting what `run_batch_simulation.py` actually does (supervised metrics on labeled "simulated" batches); the doc language is accurate to the code, but the code is the Track 3 violation described above |
| `docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md` §12 "Production Readiness Status" | "Achieved: Reproducible end-to-end runner..." | **Invalid** — overstates readiness; contradicts the doc's own top World-B disclaimer and `docs/reproducible_metrics_report.md` |
| `apps/streamlit_dashboard/app.py` (`load_scoring_data`, `live_df` everywhere) | Function/variable naming implies live/production data | **Code-level issue** — the data loaded (`meta_dataset.parquet` + `oof_predictions_final.parquet`) is labeled OOF data; naming it `live_df` is misleading at the code level, not just in docs |
| `CLAUDE.md` ("Production / decision pipeline" section) | "...must never compute MCC/precision/recall against unlabeled data" / later: "The dashboard and decision-system code already enforce this split" | **Partially invalid** — the first clause is technically true (the data `run_batch_simulation.py` touches is labeled, not unlabeled, so it isn't violating *that* literal sentence), but the second clause ("already enforce this split") overstates the current state: there is no separate label-free Production Monitoring view, and `run_batch_simulation.py` is presented elsewhere (README, case study) as production behavior while running Track 1 logic. Flagged here for visibility; **not edited in this change** since it's the user's own active instructions file — worth a follow-up edit once Track 3/View A actually exist. |

---

## Known code-level issues to fix later (not fixed in this change)

These are implied by the audit above and by `docs/production_readiness_audit.md` — listed for
follow-up, not actioned here:

1. **RESOLVED** (option (a): relabeled, plus a real Track 3 was also built — option (b) for a
   new script, not a rewrite of the old one). `run_batch_simulation.py` is now
   `scripts/run_offline_batch_eval.py`, honestly Track 1. `scripts/run_production_inference.py`
   is the new, genuinely label-free Track 3 (dataset_h only). See the Track 3 section above.
2. **Partially resolved.** `apps/streamlit_dashboard/app.py` now has a Production Monitoring
   (Track 3) view (View A), label-free and backed by real S3 output. **Still open:** no rendering
   of the existing Evidently drift output in either view; the View B pages' naming (`live_df`,
   `load_scoring_data`) still implies live data when the source is labeled OOF data (only a single
   top-of-page caption distinguishes the views so far).
3. **Partially resolved.** `docs/architecture.md`'s "Production Architecture" diagram now has a
   text note distinguishing the label-dependent path from Track 3, but the diagram itself hasn't
   been redrawn with a Track 3 node.
4. **Partially resolved.** `README.md`'s "Production Pipeline" section and
   `docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md` §8 now correctly attribute the labeled
   Track-1-sourced numbers and point to the new Track 3 script; the dashboard split itself
   (item 2) is now partially resolved too, but the per-page View B relabel/rename is still open.
5. Track 2 (Kaggle submission) now has `scripts/generate_submission.py`, but needs (a) a
   test-side feature-engineering script analogous to `build_dataset_{baseline,g,h}.py`, (b)
   persisted OOF-safe rate-lookup tables so `dataset_g`/`dataset_h`/`meta_model` features can be
   computed on test rows without leaking, and (c) a real training run to regenerate `models/*.pkl`
   in the Phase-2 payload format. See `docs/kaggle_submission.md`.
6. `CLAUDE.md`'s claim that "the dashboard and decision-system code already enforce this split"
   should be revisited once 1–2 are addressed, since it currently overstates the present state.

Items 1 and 2 have since been addressed (in part or fully) in follow-up changes described above;
3–6 remain open, per explicit scope limits on each of those changes.

---

## Relationship to other docs

- `system_design.md` — updated alongside this doc to point here and to stop being silent on
  Track 2 and the dashboard A/B split (see its diff). Note: `system_design.md` is listed in
  `.gitignore`, so this edit is local-only and will not appear in `git diff`/the eventual commit
  for this branch unless force-added.
- `bosch_agent.md` — its "two tracks, Kaggle ignored for now" framing is superseded by this doc's
  three-track framing. Not edited in this change (untracked file, not in scope of this task).
- `docs/reproducible_metrics_report.md` — remains the source of truth for which Track 1 metrics
  are actually reproducible (World A vs World B); unaffected by this change.
- `docs/production_readiness_audit.md` — merged onto `main` alongside this doc (both were
  consolidated from their respective feature branches in the same documentation-consolidation
  pass). It independently identified most of the same Track 3 / dashboard mislabeling issues
  documented here, from a read-only audit of the repo at commit `b96cd0d`.
