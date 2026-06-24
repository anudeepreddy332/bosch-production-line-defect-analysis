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
- **Current state: code exists but does not satisfy the constraint.** `scripts/run_batch_simulation.py`
  is the script positioned as this track (it's literally named "batch simulation" and is wired
  into `scripts/run_full_system.py`'s "production" stage and described as part of the
  "Production Pipeline" in `README.md`). In its current form it reads
  `data/features/meta_dataset.parquet` **with the `Response` column** and calls
  `src/inference/decision_engine.py::metrics_from_labels` / `simulate_batches`, which compute
  `recall`, `precision`, `tp`, `fp`, `fn`, `tn` per batch — all supervised metrics on labeled
  data. That output is then surfaced as `outputs/batch_simulation_summary.json` and quoted in
  `docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md` §8 ("Simulation Results... Mean recall across
  simulated batches"). **This is Track 1 work (offline evaluation on labeled OOF data) wearing a
  Track 3 label.** It is functionally identical to running a threshold/budget sweep — useful, and
  fine to keep — but it must be re-labeled as Offline Evaluation output, not Production Inference
  Simulation output, until it is rewritten to consume genuinely unlabeled batches and stop
  computing labeled metrics. See "Known code-level issues" below; not fixed in this change.

---

## Dashboard: two views, not one

### View A — Production Monitoring View (target state — not yet built)

- Uses unlabeled production-like batches.
- Shows: predictions, risk scores, batch counts, score distributions, data quality, drift,
  throughput, latest batch/cycle, top risky parts.
- **Must NOT show** MCC, precision, recall, accuracy, TP, FP, TN, FN, or a confusion matrix,
  because production/test batches are unlabeled.
- **Current state: does not exist.** `apps/streamlit_dashboard/app.py` has no section that loads
  unlabeled batches, and no drift/data-quality section at all — a `grep` for `drift`/`evidently`
  in that file returns zero matches, even though `scripts/run_drift_monitoring.py` already
  produces `outputs/monitoring/evidently_summary.json` + `.html`. The Evidently output is
  generated but never rendered in the dashboard.

### View B — Offline Evaluation / Decision Analysis View (this is what exists today)

- Uses labeled training validation / OOF data only.
- May show threshold sliders and how MCC, precision, recall, accuracy, TP, FP, TN, FN,
  confusion matrix, inspection budget, and cost trade-offs change.
- This is allowed because it is not production inference — it is a model-evaluation and
  decision-policy analysis tool.
- **Current state: this is the entirety of the existing dashboard**, just not labeled as such.
  Every section in `apps/streamlit_dashboard/app.py` (Threshold Explorer, Inspection Budget
  Simulator, Recall at Fixed Precision, Cost Simulator, Model Insights, Failure Analysis) loads
  `meta_dataset.parquet` joined to `oof_predictions_final.parquet` — both labeled, both
  Track-1-derived. The data source is correctly labeled data (so the *math* is legitimate
  View-B work), but:
  - The loader function is named `load_scoring_data()` and its result is assigned to a variable
    named `live_df` throughout (e.g. `apps/streamlit_dashboard/app.py:274,427,475,497`) —
    `live_df` is a misleading name for labeled OOF data.
  - Nothing in the UI is labeled "Offline Evaluation" or "Decision Analysis" — a user opening the
    dashboard cannot tell from the UI that they are looking at labeled validation data rather
    than live production scores.

**Per the user's explicit instruction for this change: do not refactor the dashboard now.** The
work needed is: (1) relabel existing sections as the Offline Evaluation / Decision Analysis view,
(2) rename `live_df` to something like `oof_eval_df`, (3) add a new, separate Production
Monitoring view backed by unlabeled batch output once Track 3 actually produces label-free output,
(4) wire the existing Evidently HTML/JSON into that new view. None of this is done in this change.

---

## Current state vs. target state (summary table)

| Track / View | Target | Current state |
|---|---|---|
| Track 1: Offline Training + Evaluation | Labeled data in, approved model + metrics out | **Exists**, with the World A/B reproducibility caveats already documented in `docs/reproducible_metrics_report.md` |
| Track 2: Kaggle Submission | Unlabeled Kaggle test in, `submission.csv` out | **Script exists** (`scripts/generate_submission.py`), but blocked end-to-end by two pre-existing gaps: no engineered test feature table, and committed models are pre-Phase-2 bare estimators — see `docs/kaggle_submission.md` |
| Track 3: Production Inference Simulation | Unlabeled simulated batches in, label-free predictions/drift out | **Mislabeled**: `run_batch_simulation.py` exists but runs Track 1 logic (supervised metrics on labeled `Response`) under a Track 3 name |
| Dashboard View A: Production Monitoring | Label-free batch/drift/data-quality view | **Does not exist** in `apps/streamlit_dashboard/app.py` |
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

1. `run_batch_simulation.py` / `src/inference/decision_engine.py::metrics_from_labels` compute
   supervised metrics on labeled data inside what's billed as the production/batch-simulation
   path. Needs to either (a) be relabeled as Track 1 / Offline Evaluation tooling, or (b) be
   rewritten to take genuinely unlabeled batches and drop the labeled-metric computation entirely
   so it actually satisfies Track 3.
2. `apps/streamlit_dashboard/app.py` has no Production Monitoring view (View A) and no rendering
   of the existing Evidently drift output; its single view's naming (`live_df`,
   `load_scoring_data`) implies live data when the source is labeled OOF data.
3. `docs/architecture.md`'s "Production Architecture" diagram needs a node-level note (or a
   second diagram) distinguishing the label-dependent decision-analytics path from a genuinely
   label-free production path.
4. `README.md` and `docs/CASE_STUDY_BOSCH_PRODUCTION_SYSTEM.md` need their "Production
   Pipeline"/"production decision system" framing split so that View-B/Track-1-sourced numbers
   are clearly attributed, separately from any future genuinely label-free Track 3 output.
5. Track 2 (Kaggle submission) now has `scripts/generate_submission.py`, but needs (a) a
   test-side feature-engineering script analogous to `build_dataset_{baseline,g,h}.py`, (b)
   persisted OOF-safe rate-lookup tables so `dataset_g`/`dataset_h`/`meta_model` features can be
   computed on test rows without leaking, and (c) a real training run to regenerate `models/*.pkl`
   in the Phase-2 payload format. See `docs/kaggle_submission.md`.
6. `CLAUDE.md`'s claim that "the dashboard and decision-system code already enforce this split"
   should be revisited once 1–2 are addressed, since it currently overstates the present state.

None of these are implemented or refactored as part of this change, per explicit instruction.

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
