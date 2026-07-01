# Kaggle Decision Log — Bosch Production Line Performance (SECONDARY TRACK)

This is the **canonical scientific record of the Kaggle / leaderboard-optimization track**, and the
**only** place leaderboard-driven work is recorded. It is deliberately separate from the production
decision log (`decisions.md`) so the two optimization programs can never cross-contaminate. See
`decisions.md` DR-005 §4 and DR-007 §4 for the adoption of this two-track structure.

## What belongs here (and only here)

- Competition-specific feature engineering, including features the **production charter forbids**
  (record-adjacency / timing-to-neighbor / test-order / duplicate-concat magic — the leakage family
  that produces the public-LB ~0.50).
- Leaderboard scores (public/private), competition ensembling/blending, submission tuning.
- Any metric computed *with* a leakage-laden or competition-only feature.

## What must never happen

- **No metric or conclusion from this log may appear in `decisions.md` or inform any `DR`/`E`
  decision.** Production decisions are gated *only* by honest, leakage-free OOF/CV MCC.
- The public-LB ~0.50 is a **leakage ceiling**, never a production target.
- Kaggle code lives only under `src/kaggle/` + `scripts/kaggle/`; nothing outside may import it.

## Flow between tracks (asymmetric by design — DR-008)

Production is the source of scientific truth; this track is an optimization laboratory. Because the
Production protocol is *strictly stronger* (leakage-free, pre-registered, chunk-aware honest OOF):

- **Production → Kaggle is free.** This track may import the shared library and any clean Production
  feature, build on Production OOF predictions, and cite Production conclusions directly. No
  re-validation needed — anything that passed the stronger bar holds here.
- **Kaggle → Production is never direct.** A leaderboard score is a *lead*, not *evidence*. To reach
  Production a finding must pass the **re-derivation gateway**: a new `DR`/`E` is opened, the
  *mechanism* is re-implemented leakage-free, and it is re-validated from scratch on the Production
  harness. The Kaggle number is discarded; only the independently reproduced honest MCC counts. A
  finding that cannot be made leakage-free **stays here permanently**.
- **Ideas** may travel either way; what may not travel Kaggle→Production is the *credibility* a
  leaderboard score lends an idea — that must be re-earned under the Production protocol.

## Branching (DR-008)

`kaggle/K<N>-slug` branches cut from **`kaggle-main`** (a long-lived branch, created at the track
opening in `KDR-001`, seeded from `main` @ `13ab858` — a descendant of `baseline-v1`, so it carries
the full Production lineage — and kept current by forward-merging `main`). Results merge to
`kaggle-main`, **never** `main`. This lets the Kaggle track inherit Production advances while the
firewall to `main` stays absolute. See `git_workflow.md` for the full protocol.

## Conventions (mirror the production protocol, disjoint namespace)

- Decisions numbered `KDR-NNN`; experiments `K<N>`; branches `kaggle/K<N>-slug` cut from
  `kaggle-main` (per DR-008; not `baseline-v1`); result tags `K<N>-result`. Merges go to
  `kaggle-main`, **never** `main`.
- Shared, track-neutral infrastructure (data prep, chunk-aware CV harness, `src/training/`,
  `src/utils/`, clean feature contracts) is imported from the production codebase — *sharing
  infrastructure is allowed; sharing results/metrics is not*.

## Status

**Track 2 is OPEN as of `KDR-001` (2026-06-28).** `kaggle-main` exists (created from `main` @
`13ab858`); the firewall code-valve is verified empty. **No `K` experiment is authorized yet** —
`K1` will be pre-registered in `KDR-002` when the first leaderboard probe is designed. Production
work is unaffected: `main` lineage stays leakage-free, and nothing in this log may inform a
`DR`/`E`.

---

## KDR-001 — Open the Kaggle (Track 2) leaderboard-optimization track

- **Date:** 2026-06-28
- **Decision type:** Governance / track-opening (charter activation). **No `K` experiment is
  authorized by this entry** — it opens the track and fixes its rules; the first experiment (`K1`)
  is pre-registered in a later `KDR` when a concrete leaderboard probe is designed.
- **Trigger (why now):** Both preconditions are met. Track 1 (Production research) is frozen
  (`track1-frozen`, DR-001→DR-015) and Track 3 (label-free production inference) is frozen
  (`track3-frozen`, commit `f743da3`); the pre-Kaggle repository cleanup is merged to `main`
  (`13ab858`). A reproducible, leakage-free inference path exists end-to-end for `dataset_h`
  (`docs/dataset_h_submission_run.md`: 1,183,748 rows, Id-set verified, threshold 0.91). The
  firewall scaffolding (DR-005 §4, DR-007 §4, DR-008, `git_workflow.md`) is in place. Opening
  Track 2 no longer risks contaminating an in-flight Production program.
- **Objective:** Optimize the Bosch *private*-leaderboard MCC under competition rules — **including
  the feature families the Production charter forbids** (record-adjacency / timing-to-neighbor /
  test-order / duplicate-concat: the leakage family behind the public-LB ~0.50). Purpose is
  twofold: (1) produce a competitive leaderboard result as a portfolio artifact; (2) *quantify the
  leakage gap* — how far the competition-legal-but-non-deployable ceiling sits above the honest,
  deployable Production ceiling (~0.15–0.16 OOF MCC; `dataset_h`'s real LB 0.14389 public /
  0.16160 private already brackets it). The leaderboard number is a **lead, never evidence**
  (DR-008).
- **Success criteria (pre-registered):**
  - *Process (binding):* every `K<N>` is fully recorded — `KDR` pre-registration, `kaggle/K<N>-slug`
    branch off `kaggle-main`, `K<N>-result` tag, pending-ledger update, results merged to
    `kaggle-main` **only**. A submission must be reproducible from committed `kaggle-main` code +
    documented commands.
  - *Outcome (soft, non-binding):* improve materially over the `dataset_h` honest baseline's
    recorded LB (0.14389 / 0.16160) where competition-legal, and characterize the mechanism of any
    gain (leakage vs. genuine signal).
  - *Explicitly NOT a success metric anywhere it could contaminate:* no leaderboard/leaky number
    may enter `decisions.md`, gate any `DR`/`E`, or be cited as Production evidence. A `K` result
    that cannot survive the re-derivation gateway stays in Track 2 permanently.
- **Contamination rules (ratified — the operative firewall for Track 2):**
  1. **Quarantine:** all competition-only / leaky code lives only under `src/kaggle/` and
     `scripts/kaggle/`; no module outside `src/kaggle/` may import it.
  2. **Code valve:** before any merge to `main`,
     `grep -rn --include="*.py" "import.*kaggle" src/ scripts/` (excluding `src/kaggle/`) must be
     empty. **Verified empty at this entry.**
  3. **Branch wall:** `kaggle/*` and `kaggle-main` **never** merge to `main`; `main → kaggle-main`
     forward-merge is allowed (Production advances flow in), the reverse is forbidden.
  4. **Log routing:** all Track 2 records land here (`KDR`/`K`), never in `decisions.md`.
  5. **Re-derivation gateway:** the only Kaggle→Production path — open a fresh `DR`/`E`,
     re-implement the mechanism leakage-free, re-validate on the chunk-aware honest-OOF harness,
     **discard the Kaggle number**.
- **Firewall audit at opening (evidence collected):**
  - Code-valve grep: **empty** — no `*kaggle*` module is imported anywhere.
  - `scripts/generate_submission.py`: **no** leaky / leaderboard / competition-specific logic; its
    only first-party import is the generic `validate_model_payload.validate_payload`.
  - Production↔submission coupling: `scripts/run_production_inference.py` imports two **generic**
    inference helpers (`load_validated_payload`, `predict_proba_ensemble`) from
    `scripts/generate_submission.py`. These are track-neutral inference operations (load+validate a
    payload; average `predict_proba` over folds), not Kaggle logic — **permitted infrastructure
    sharing**, not a firewall breach.
  - **Finding (structural, non-blocking):** `generate_submission.py` is documented as "the Track 2
    script" yet is track-neutral and depended on by Production. To keep the firewall unambiguous
    once `src/kaggle/` exists, **extract `load_validated_payload` + `predict_proba_ensemble` into
    `src/inference/` before any Kaggle-specific submission code is added**, so Production depends
    only on `src/inference/` and Track 2's submission wrapper can evolve freely. Pre-registered as a
    prerequisite for the first `K` that touches submission code; not actioned here (governance-only
    entry).
- **Experiment numbering & mechanics:** `K1, K2, …` (diagnostics `K<N>p`); branches
  `kaggle/K<N>-slug` cut from `kaggle-main`; result tags `K<N>-result`; merges to `kaggle-main`
  only. IDs are the join key across this log, branches, commits, and tags (mirrors the Production
  `E<N>` protocol in a disjoint namespace).
- **Decision:** **Track 2 is open.** `kaggle-main` created from `main` @ `13ab858`. No `K`
  experiment authorized yet.
- **Confidence:** High — a governance/charter decision, not an empirical claim; it ratifies and
  activates the already-adopted two-track contract (DR-005/007/008).
- **Next action:** Pre-register `K1` in `KDR-002` when the first concrete leaderboard probe is
  designed. Before any `K` that edits submission code, perform the `src/inference/` extraction
  noted above.

---

## KDR-002 — Pre-register K1: baseline reproduction from frozen production candidate

- **Date:** 2026-06-28
- **Decision type:** Experiment pre-registration. **Authorizes K1 only** — no further experiments
  are authorized by this entry.
- **Trigger:** Track 2 is open (KDR-001). `kaggle-main` is current at `b058e58` (carries KDR-001
  governance). The first step before any leaderboard probe is establishing a reproducible baseline
  so that every future `K<N>` has a concrete comparator. The `dataset_h` production submission is
  already verified end-to-end (`docs/dataset_h_submission_run.md`): 1,183,748 rows, threshold 0.91,
  2,993 positives, LB 0.14389 public / 0.16160 private. K1 re-runs that exact submission from the
  `kaggle/K1-baseline-reproduction` branch to confirm reproducibility, produce a committed artifact,
  and record the authoritative Track 2 starting point.
- **Hypothesis:** The frozen `dataset_h` production model (`models/dataset_h_model.pkl`, payload
  format Phase-2, threshold 0.91) running through the verified submission pipeline
  (`scripts/generate_submission.py`) will produce the same 2,993-positive output and, upon
  submission, reproduce the documented LB scores (public 0.14389 / private 0.16160) within
  floating-point noise. No new training, no feature changes, no threshold tuning — pure
  reproducibility check.
- **Pre-registered success / failure criteria:**
  - **Pass:** the generated `submission.csv` matches the documented run exactly (row count
    1,183,748; positive count 2,993; Id-set verified; no NaN; threshold applied = 0.91). LB
    submission is optional for the pre-registration step; if submitted, public LB should land at
    0.14389 ± 0.001.
  - **Fail / inconclusive:** any mismatch in row count, positive count, Id-set, or LB score
    outside tolerance. Failure triggers a root-cause investigation before K2 is opened; the
    baseline is not considered established until Pass.
  - **Not a criterion:** absolute LB rank, comparison to other public kernels, or any metric
    computed on production (unlabeled) data.
- **Contamination rules (inherited from KDR-001; recorded here for K1 scope):**
  1. All K1 artifacts (submission CSV, any diagnostic notebooks) live on
     `kaggle/K1-baseline-reproduction` — **never** committed to `main`.
  2. K1 uses only the production model and clean production features (`data/features/
     test_dataset_h.parquet`). No leaky feature families, no record-adjacency magic.
  3. Code valve remains empty: `grep -rn --include="*.py" "import.*kaggle" src/ scripts/`
     (ex-`src/kaggle/`) must stay empty — K1 adds no new imports.
  4. `src/kaggle/` and `scripts/kaggle/` do **not** need to be created for K1 (no competition-
     only code introduced); they are created at the first `K` that adds leaky or competition-only
     logic.
  5. No leaderboard number may enter `decisions.md` or gate any `DR`/`E`.
- **Expected artifacts:**
  - `outputs/submission_K1.csv` — the reproduced submission file (1,183,748 rows, 0/1 column).
  - `K1-result` tag on the commit that produces the final artifact.
  - This KDR-002 entry updated with Evidence / Outcome / Decision once the run completes.
  - Pending-ledger row for K1 updated to "Complete."
- **Reproducibility requirements:**
  - Branch: `kaggle/K1-baseline-reproduction` cut from `kaggle-main` @ `b058e58`.
  - Model: `models/dataset_h_model.pkl` (committed; Phase-2 payload, 5 fold models, threshold 0.91).
  - Test features: `data/features/test_dataset_h.parquet` (gitignored; regenerate with
    `PYTHONPATH=. python scripts/build_test_dataset_h.py` if absent).
  - Command:
    ```bash
    PYTHONPATH=. python scripts/generate_submission.py \
      --model-path models/dataset_h_model.pkl \
      --test-features data/features/test_dataset_h.parquet \
      --output outputs/submission_K1.csv
    ```
  - Seed: n/a (inference only; no training randomness in this experiment).
  - Data fingerprint: carried from Track 1 / Track 3 pipeline (`data_fingerprint` in
    `outputs/production_decision_summary.json`).
- **Decision:** **K1 is authorized.** Branch `kaggle/K1-baseline-reproduction` cut from
  `kaggle-main` @ `b058e58`. Proceed with the reproducibility run. Do NOT optimize, tune, or train
  in this experiment.
- **Confidence:** High — this is a reproducibility check of a fully verified pipeline, not an
  experimental probe.
- **Next action:** Run the submission command above; record evidence (row count, positive count,
  Id-set check, LB score if submitted); place `K1-result` tag; update this entry with
  Evidence/Outcome/Decision; update ledger. Then design K2 (first true leaderboard probe) in
  KDR-003.

---

### K1 Evidence (run 2026-06-28 on `kaggle/K1-baseline-reproduction`)

**Pre-run artifact fingerprints:**

| Artifact | Fingerprint |
|---|---|
| `models/dataset_h_model.pkl` | md5 `ef924414462ed554c7bd14b5b95cc1e7` |
| `models/dataset_h_model.pkl` payload `data_fingerprint` | `a5bb652f2b20aca6` |
| `models/dataset_h_model.pkl` payload `threshold` | `0.91` |
| `models/dataset_h_model.pkl` payload `n_folds` | `5` |
| `models/dataset_h_model.pkl` payload `oof_mcc` | `0.15337` |
| `data/features/test_dataset_h.parquet` | pandas-hash md5 `691357340332fc446eff09a3085145a4` |
| `data/features/test_dataset_h.parquet` shape | `(1183748, 17)` |
| `data/features/test_dataset_h.parquet` has `Response` | `False` (label-free confirmed) |

**Commands executed (in order):**

```bash
# Verify artifacts present
ls models/dataset_h_model.pkl data/features/test_dataset_h.parquet
md5sum models/dataset_h_model.pkl  # -> ef924414462ed554c7bd14b5b95cc1e7

# K1 run (pre-registered command)
PYTHONPATH=. python scripts/generate_submission.py \
  --model-path models/dataset_h_model.pkl \
  --test-features data/features/test_dataset_h.parquet \
  --output outputs/submission_K1.csv

# Determinism check (second run, independent)
PYTHONPATH=. python scripts/generate_submission.py \
  --model-path models/dataset_h_model.pkl \
  --test-features data/features/test_dataset_h.parquet \
  --output outputs/submission_K1_run2.csv
diff outputs/submission_K1.csv outputs/submission_K1_run2.csv  # -> BYTE-IDENTICAL
rm outputs/submission_K1_run2.csv  # cleanup
```

**Script output (both runs identical):**

```
model_name='dataset_h'
threshold_used=0.91
output_path=outputs/submission_K1.csv
row_count=1183748
positive_prediction_count=2993
```

**Output validation (`outputs/submission_K1.csv`):**

| Check | Pre-registered criterion | Result | Pass? |
|---|---|---|---|
| Row count | 1,183,748 | 1,183,748 | ✅ |
| Positive count | 2,993 | 2,993 | ✅ |
| Id set matches `sample_submission.parquet` | exact set equality | True (1,183,748 unique, no extras/missing) | ✅ |
| Id range | 1 – 2,367,494 | 1 – 2,367,494 | ✅ |
| Id monotone sorted | yes | yes | ✅ |
| NaN count | 0 | 0 | ✅ |
| Columns | `[Id, Response]` | `[Id, Response]` | ✅ |
| Response values | binary `{0, 1}` | `{0, 1}` (int64) | ✅ |
| Threshold applied | 0.91 | 0.91 (from payload; not overridden) | ✅ |
| No supervised metric computed | grep returns empty | verified (label-free path) | ✅ |

**Output file hashes:**

| Hash | Value |
|---|---|
| md5 | `e83b769be914976972a209c5ca278602` |
| sha256 | `44bebfa864f24c4cb5029f42eb384a507e3771b7782a08d8bb0b12e794df29db` |
| size | 11,281,556 bytes |

**Determinism:** Two independent runs produce byte-identical output (md5
`e83b769be914976972a209c5ca278602` on both). The pipeline is deterministic at
inference time (no training randomness; LightGBM predict is deterministic given
fixed model + input).

**Comparison to documented prior run (`docs/dataset_h_submission_run.md`):**
The prior run produced `outputs/dataset_h_submission.csv` (gitignored, no longer
on disk; no hash was recorded at run time). All documented numerical results
match exactly: 1,183,748 rows, 2,993 positives, threshold 0.91, Id-set verified
against `sample_submission.parquet`. Byte-identity with the original file cannot
be proven (hash was not recorded then), but numerical identity on every
pre-registered criterion is confirmed. The pipeline is deterministic, so any
future run on the same model and features will reproduce the same output.

**Contamination check:**
- `grep -rn --include="*.py" "import.*kaggle" src/ scripts/` → empty. Firewall intact.
- K1 touched only `docs/research/kaggle_decisions.md` and `docs/ml_system_tracks.md` (docs
  only). No `src/`, `scripts/`, `apps/` files changed. No `decisions.md` entry added.

### K1 Outcome

**PASS.** All pre-registered success criteria met. The frozen `dataset_h` model at threshold
0.91 reproduces the documented Track 2 baseline exactly and deterministically.

### K1 Decision

**Complete.** `outputs/submission_K1.csv` is the authoritative K1 artifact (gitignored, not
committed; reproducible on demand from committed model + pre-registered command). Tag
`K1-result` placed at the tip of `kaggle/K1-baseline-reproduction`. The Track 2
baseline is established: public LB target 0.14389 / private LB 0.16160 (from documented prior
run; K1 confirms the artifact that produced those scores is reproducible). Every future `K<N>`
compares against this baseline. Design K2 in `KDR-003`.

---

## KDR-003 — Pre-register K2: quantify the leakage gap via record-adjacency "magic" features

- **Date:** 2026-06-28
- **Decision type:** Experiment pre-registration with candidate ranking (Opus). **Authorizes K2
  only.** No `K3+` is authorized. This entry selects the single highest-information-gain Kaggle
  experiment given the K1 honest baseline and the frozen Production findings (RP1, RP2), and fixes
  K2's hypothesis, evidence bar, contamination safeguards, and git plan **before any code is
  written**. It is a design entry — no code, no branch, no model in this commit.

### §1 — Trigger and the decision K2 actually faces

K1 established the **honest Track-2 baseline**: public LB **0.14389** / private **0.16160**
(`dataset_h`, clean leakage-free features only). KDR-001 set Track 2's dual objective: (1) a
competitive leaderboard artifact, and (2) **quantify the leakage gap** — how far the
competition-legal-but-non-deployable ceiling sits above the honest, deployable ceiling. The
Bosch competition's public top scores sit near **~0.50 MCC**; the project has always treated this
as a *leakage ceiling*, never a modeling target (charter; DR-001). The open question Track 2 must
answer first is therefore: **what mechanism produces the ~0.16 → ~0.50 gap, and how large is it
when measured cleanly?**

### §2 — Imported priors from the frozen Production track (Production → Kaggle idea flow, DR-008)

These are *ideas/conclusions*, not borrowed evidence — admissible as priors under the asymmetric
flow rule. They sharply constrain which Kaggle experiments are worth running:

- **The honest signal is nearly exhausted.** RP1 (DR-010) froze representation work: sensor
  measurements add **no durable** signal over routing. RP2 (DR-009→DR-015) measured the honest
  deployable ceiling as a *regime distribution* — **AUC ≈ 0.55 (flat), MCC mean ≈ 0.12, range
  0.06–0.18**. The model's threshold-free ranking is barely above chance once leakage is removed.
- **Capacity is not binding** (DR-001): LightGBM on 1.18M×16 is far from saturation; **stacking
  made it worse** (meta_model 0.1494 < dataset_h 0.1534). HPO / model swaps are low-EV honestly.
- **Split-gain importance is inadmissible** (H_splitgain 0.90): never rank features by split-gain.

**Consequence:** the *honest* feature/model space is a near-dead-end for the leaderboard — pursuing
it would "rediscover already-rejected ideas." The entire remaining LB headroom must live in the
**leakage families the Production charter forbids** — which is exactly what Track 2 exists to probe.

### §3 — Candidate K2 experiments (each scored on the requested axes)

**Candidate A — Record-adjacency / temporal-neighbor "magic" leakage features (RECOMMENDED).**
- *Hypothesis:* the ~0.16→~0.50 gap is dominated by **record-adjacency leakage** — failures cluster
  among parts that are adjacent in dataset/station-time orderings ("bad batches"), so features
  derived from neighboring records under multiple sort orders (Id deltas, station-time deltas to
  prev/next part, and neighbor `Response` for train rows) carry massive non-deployable signal.
- *Why it should improve LB:* this is the documented mechanism behind the Bosch public-LB ~0.50;
  it is the canonical "magic." It violates the Production charter (record-adjacency / timing-to-
  neighbor / test-order / duplicate-concat) — i.e., it is Kaggle-only by construction.
- *Expected information gain:* **highest.** It *eliminates an entire hypothesis class* — "honest
  feature/model work can close the gap" — by directly measuring how much of the gap a single
  leakage family explains. Outcome is decisive in either direction (large jump → gap located and
  quantified; small jump → the famous mechanism is *not* the driver here, a major surprise that
  redirects the whole track).
- *Expected leaderboard impact:* large (community precedent: from ~0.2 honest to ~0.45–0.50 with
  magic). Treated as a **lead, never evidence** (DR-008); never enters `decisions.md`.
- *Implementation complexity:* **medium.** Build magic features over train+test concatenated in a
  new quarantined module; retrain; generate a Kaggle submission. No new modeling theory.
- *Scientific value:* **high** — it is the empirical measurement of the leakage gap that is the
  stated reason Track 2 exists, and the portfolio artifact ("here is exactly how big the leakage
  is, isolated and quarantined") is more valuable than a bare leaderboard number.
- *Contamination risk:* **high in principle, controlled in practice** — this is the first
  experiment that creates `src/kaggle/` + `scripts/kaggle/`; the firewall (§6) is designed for
  exactly this. The risk is structural and pre-mitigated, not accidental.
- *Rollback:* branch-local; `kaggle/K2-*` never merges to `main`; abandon = keep `K2-result` tag +
  the `kaggle-main` merge; no production artifact is touched.

**Candidate B — Honest feature/model improvement (more sensor aggregations, deeper routing, XGBoost, HPO, blending).**
- *Hypothesis:* non-leaky engineering materially raises the LB.
- *Expected info gain:* **low** — RP1/RP2 already answer this (AUC ~0.55, sensors add nothing
  durable, stacking hurts, capacity not binding). Running it would re-derive a known negative.
- *Expected LB impact:* low (~±0.01). *Complexity:* medium. *Scientific value:* low (duplicates
  Production findings). *Contamination risk:* low. *Rollback:* trivial. **Reject** — forbidden by
  the user's "do not rediscover already-rejected ideas" and dominated on EIG.

**Candidate C — Model swap / hyperparameter optimization (XGBoost + Optuna).**
- *Hypothesis:* a different learner / tuned params lifts the LB. *Info gain:* **lowest**
  (capacity-not-binding is settled, DR-001). *LB impact:* ~noise. *Reject* — pre-answered.

**Candidate D — Other leakage sub-families in isolation (duplicate/concat-only, or test-order-only).**
- *Hypothesis:* a *different* leakage family (not adjacency) is the dominant driver. *Info gain:*
  medium but **dominated by A** — A tests the canonical, highest-prior mechanism first; D is the
  natural *follow-up* to attribute any residual gap A leaves. *Defer to K3+.*

**Candidate E — Blend the honest K1 model with a leaky model.**
- *Premature:* requires a leaky model to exist first (that is K2-A). *Defer.*

### §4 — Ranking (by expected information gain, per the user's stated priority)

| Rank | Candidate | EIG | LB impact | Complexity | Verdict |
|---|---|---|---|---|---|
| **1** | **A — record-adjacency magic leakage** | **Highest** | Large | Medium | **CHOSEN** — eliminates the "honest work closes the gap" class; quantifies the leakage gap (KDR-001 goal); stands up the firewall. |
| 2 | D — other leakage families in isolation | Medium | Med–Large | Medium | Defer to K3 — attributes residual gap *after* A locates the dominant one. |
| 3 | E — honest+leaky blend | Med (gated) | Large | Low | Defer — needs A's leaky model first. |
| 4 | B — honest feature/model work | Low | ~±0.01 | Medium | Reject — pre-answered by RP1/RP2. |
| 5 | C — model swap / HPO | Lowest | ~noise | Low–Med | Reject — capacity not binding (DR-001). |

A is the unique candidate whose result **changes what we fund next** *and* directly delivers
KDR-001's leakage-gap quantification. It dominates on information gain per unit effort.

### §5 — K2 pre-registration (the chosen experiment)

- **Experiment ID:** `K2`. **Branch:** `kaggle/K2-magic-leakage-probe` cut from `kaggle-main`
  (DR-008). **Result tag:** `K2-result`. **Log:** this file only — never `decisions.md`.
- **Research question:** How much of the Bosch leakage gap (honest LB 0.14389 → public ceiling
  ~0.50) is recovered by record-adjacency / temporal-neighbor magic features added to the
  `dataset_h` feature set, and what is the mechanism's contribution profile?
- **Hypotheses (with entering priors):**
  - **H_adjacency_dominant (0.75):** adjacency magic recovers a *large* share of the gap (public
    LB rises materially above 0.144, plausibly toward 0.30–0.50).
  - **H_adjacency_minor (0.20):** adjacency contributes only modestly; the gap lives mostly in
    another leakage family (→ K3 tests D).
  - **H_no_gap (0.05):** little movement — a major surprise that would reframe the whole track.
- **Feature specification (committed before results):** a quarantined `src/kaggle/magic_features.py`
  builds, over **train+test concatenated**, the canonical adjacency family:
  1. Multi-sort-order neighbor position features: sort by `Id`; by station start-time; by
     (`start_time`, `Id`). For each order: `*_prev_diff`, `*_next_diff` (Id and time deltas to the
     immediately adjacent record), and same-neighbor indicator flags.
  2. Train-neighbor `Response` features (the strong leak): for each sort order, the `Response` of
     the previous/next **train** record (test rows look up their train neighbors). These are
     explicitly leakage and **legal only inside `src/kaggle/`**.
  3. Optional duplicate/concat aggregates (group size / position within identical-feature groups)
     if cheap — recorded if added, omitted otherwise.
  No Production feature is modified; `dataset_h`'s 16 clean features are reused as-is and the magic
  block is added additively. The exact final column list is logged in the K2 Evidence block.
- **Success / pass criteria (Track-2 process is binding; outcome is a measurement, not a gate):**
  - *Process (BINDING):* K2 is fully recorded — this pre-registration, `kaggle/K2-*` off
    `kaggle-main`, `K2-result` tag, results merged to `kaggle-main` **only**, submission
    reproducible from committed `kaggle-main` code + documented commands. The firewall §6 checks
    pass. **Missing any one → K2 not done.**
  - *Outcome (SOFT, non-binding):* the experiment *succeeds as a measurement* iff it produces a
    quantified leakage-gap estimate with a stated mechanism attribution and a confident
    classification into one of the three hypotheses — **in any direction**. We are buying the
    number, not a particular number.
- **Failure / warning criteria:**
  - *Methodology failure (redesign, no conclusion):* the magic features cannot be built leak-clean
    *with respect to the firewall* (i.e. any magic logic leaks outside `src/kaggle/`), OR the
    submission is not reproducible, OR the train-neighbor-`Response` construction accidentally makes
    the internal CV degenerate in a way that prevents *any* honest internal sanity read. In that
    case K2 reports "unresolved — rebuild" and draws no gap estimate.
  - *Warning (record, do not over-claim):* internal CV MCC computed **with** magic features is
    itself contaminated (train-neighbor `Response` leaks across folds) and is **not** a valid
    ranking metric — only the **held-out Kaggle LB** legitimately measures the magic's value. K2
    must flag any internal MCC as contaminated and lean on the LB (or a strictly group-blocked
    internal holdout) for the gap estimate.
- **Required evidence / success metrics:**
  - The **public (and, if revealed, private) Kaggle LB score** of the magic submission, vs K1's
    0.14389 / 0.16160 — the definitive gap quantifier. *(Submitting to Kaggle is an outward action
    requiring explicit user go-ahead — pre-registered here, executed by a human, exactly as K1's
    submission was treated.)*
  - A **leakage-gap decomposition**: LB(magic) − LB(K1 honest) = the measured gap recovered by
    adjacency; plus, if feasible, an ablation (position-only vs +train-neighbor-`Response`) to
    attribute the gap within the family.
  - Submission artifact (`outputs/kaggle/submission_K2.csv`, gitignored), its row/Id-set
    validation against `sample_submission`, and md5.
  - The committed magic-feature code under `src/kaggle/` + the K2 submission script under
    `scripts/kaggle/`, with the exact reproduce command.
- **Reproducibility requirements:** branch `kaggle/K2-magic-leakage-probe` @ its `kaggle-main`
  base; deterministic feature build (fixed sort tie-breakers — sort keys must be total orders, no
  ambiguous ties); same LightGBM hyperparameters as `dataset_h` unless a change is itself logged;
  documented `PYTHONPATH=. python scripts/kaggle/...` command; data fingerprints recorded.

### §6 — Contamination safeguards (the operative firewall for the FIRST leaky experiment)

K2 is the experiment KDR-001's firewall was built for. All of the following are **binding**:

1. **Quarantine (creates the namespaces):** all magic / record-adjacency / train-neighbor-`Response`
   logic lives **only** in `src/kaggle/` (created at K2) and its entry points in `scripts/kaggle/`
   (created at K2). No module in `src/` or `scripts/` outside those two trees may import them.
2. **Code valve — and a required refinement K2 surfaces.** Before any merge to `main`,
   `grep -rn --include="*.py" "import.*kaggle" src/ scripts/` **excluding both `src/kaggle/` AND
   `scripts/kaggle/`** must be empty. *(KDR-001/DR-008 wrote the exclusion as `src/kaggle/` only;
   once `scripts/kaggle/` exists, its internal `from src.kaggle...` imports would be false
   positives. The valve must exclude both quarantine trees. This refinement is part of K2's
   deliverable and should be mirrored into `git_workflow.md` §code-valve when K2 lands.)* The valve
   continues to verify the **one true invariant: no Production code imports Kaggle code.**
3. **Branch wall:** `kaggle/K2-*` and `kaggle-main` **never** merge to `main`. `main → kaggle-main`
   forward-merge is allowed; the reverse is forbidden. K2 results merge to `kaggle-main` only.
4. **Log routing:** every K2 number lands here (`KDR`/`K`). **No K2 metric — LB or internal — may
   appear in `decisions.md` or gate any `DR`/`E`.** The leakage gap is a *finding about leakage*,
   not a Production result.
5. **Metric-provenance honesty:** any internal CV/MCC computed with magic features is flagged
   contaminated and is never reported as an honest ranking metric (only the LB / group-blocked
   holdout measures the magic).
6. **Submission output** goes under `outputs/kaggle/` (add to `.gitignore` if not already covered);
   the production decision system, `run_production_inference.py`, and all Track-3 artifacts are
   untouched. The KDR-001 `src/inference/` extraction prerequisite is **not triggered by K2**: K2
   adds *new* code under `scripts/kaggle/` and may freely **import** the generic helpers from
   `scripts/generate_submission.py` (Production → Kaggle import is permitted); it does **not edit**
   `generate_submission.py`. If a later K needs to *modify* that script, the extraction must be done
   first as a separate **Production-side chore on `main`** (not on a `kaggle/*` branch).

### §7 — Git strategy

- **Branch:** `kaggle/K2-magic-leakage-probe`, cut from `kaggle-main` **after** K1 is merged into
  `kaggle-main` and KDR-003 is on `kaggle-main` (so K2 inherits both the K1 baseline record and its
  own charter).
- **Commits:** `K2 exp:` (magic features), `K2 eval:` (submission + LB), `K2 docs:` (Evidence
  block). IDs are the join key (`git log --grep "K2"`).
- **Merge:** `kaggle/K2-magic-leakage-probe` → **`kaggle-main` only** (a `--no-ff` merge keeps the
  K2 commits contained and grep-able). **Never `main`.**
- **Tag:** `K2-result` (annotated) at the final K2 commit, recording the measured LB and gap.
- **Abandon path:** even if the magic underwhelms, K2 merges to `kaggle-main` (it is a kept
  measurement, not a dead end) with the `K2-result` tag and this log's Evidence block.

### §8 — Documentation updates required AFTER K2 is implemented

- `docs/research/kaggle_decisions.md` — fill KDR-003's K2 **Evidence / Outcome / Decision**
  (LB scores, gap decomposition, final feature list, md5, hypothesis classification); update the
  ledger (K2 → Complete; add K3 pending KDR-004).
- `docs/research/git_workflow.md` — apply the §6.2 code-valve refinement (exclude `scripts/kaggle/`
  too) once the quarantine trees exist.
- `docs/agent_memory/claude_state.md` — Track 2 state → K2 complete; record the measured leakage
  gap and the firewall-now-active note.
- `.gitignore` — ensure `outputs/kaggle/` (submission artifacts) is ignored.
- **Not touched:** `decisions.md` (no Production decision changes), README / case-study / Track-3
  docs (K2 changes no architecture and no Production behavior), `CLAUDE.md`.

### §9 — Decision, confidence, next action

- **Decision:** **Authorize K2** = record-adjacency magic-leakage probe, exactly as pre-registered
  in §5–§7, pending user go-ahead. Defer D/E/B/C. K2 is the first experiment to create `src/kaggle/`
  + `scripts/kaggle/` and activate the firewall in practice.
- **Confidence:** **High** that K2 is the highest-EIG Kaggle experiment and that it eliminates the
  "honest work closes the gap" class; **High** that the adjacency family is the dominant leakage
  mechanism (community precedent); **Medium** on the exact magnitude of the recovered gap (that is
  the number K2 buys).
- **Next action:** On go-ahead, cut `kaggle/K2-magic-leakage-probe` from `kaggle-main`, build the
  quarantined magic features, train, and (with explicit authorization for the outward submission)
  measure the LB. Record evidence here, tag `K2-result`, merge to `kaggle-main` only. Then design
  K3 (leakage-family attribution, candidate D) in `KDR-004` if a residual gap remains.

### K2 Implementation status (2026-07-01) — build/train/submission complete; LB measured 2026-07-02

Process record of the build/train/submission steps (see K2 Evidence — Kaggle LB below for the
measured LB scores and the formal Outcome/Decision).

- **Branch:** `kaggle/K2-magic-leakage-probe`, cut from `kaggle-main` @ `c1aa2ba` (KDR-003 ratified
  and committed onto `kaggle-main` first, as required by §7).
- **Quarantine created** exactly as pre-registered (§6.1): `src/kaggle/magic_features.py`,
  `scripts/kaggle/{build_magic_dataset,train_magic_model,generate_submission_K2}.py`, each with
  `__init__.py`. `outputs/kaggle/` added to `.gitignore` **before** any artifact was generated.
- **Feature spec implemented (§5 item 1–2):** 3 deterministic total-order sorts —
  `adj_id` (by `Id`, already unique), `adj_time` (by `start_time`, ties broken by stable sort over
  fixed train-then-test-by-`Id` concatenation order), `adj_time_id` (explicit compound key
  `(start_time, Id)`, a different tie-break than `adj_time`). Each order contributes 8 columns
  (`id_prev_diff`, `id_next_diff`, `time_prev_diff`, `time_next_diff`, `same_prev`, `same_next`,
  `train_resp_prev`, `train_resp_next`) → 24 `MAGIC_FEATURE_COLS` total. `train_resp_*` is the
  nearest strictly-prior/-following **train** record's `Response` in that order (own label always
  excluded). NaN `start_time` (~0.05% of rows) placed deterministically last via a `+inf` sort key.
  **Item 3 (optional duplicate/concat aggregates) omitted** — not required by §5, deferred rather
  than rushed.
- **Datasets built** (`scripts/kaggle/build_magic_dataset.py`, gitignored parquet):
  `data/features/dataset_h_magic_train.parquet` (1,183,747 rows × 42 cols: `Id`, `Response`, 16
  clean `DATASET_H_FEATURE_COLS`, 24 magic cols) and `dataset_h_magic_test.parquet` (1,183,748 rows
  × 41 cols, same minus `Response`). Row counts match `dataset_h`/`test_dataset_h` exactly (additive
  merge, no row loss).
- **Model trained** (`scripts/kaggle/train_magic_model.py`, reusing `train_lightgbm_oof` +
  `build_model_payload` from `src.training.modeling` unchanged — same LightGBM hyperparameters as
  `dataset_h`, no change logged): `outputs/kaggle/models/k2_magic_model.pkl`, 5 fold models,
  `data_fingerprint=3dc7fb742ce24ecf`, `threshold=0.98`.
  - **CONTAMINATED `oof_mcc=0.37530`** (full 40-feature set, includes `train_resp_*`) — per §5
    warning, this is **not a valid ranking metric** (label leaks across CV folds via the
    train-neighbor lookup) and must never be compared to `dataset_h`'s honest `oof_mcc=0.15337`.
  - **Ablation (§5 required evidence, "if feasible" — performed):** retrained with the 18
    position-only magic columns (`train_resp_*` excluded). These carry **no label information**, so
    this OOF MCC **is a valid, uncontaminated internal comparison**:
    `oof_mcc=0.31761` vs. `dataset_h` honest `oof_mcc=0.15337` — position/adjacency-delta features
    *alone* (no explicit neighbor-label lookup) already recover roughly half the movement toward the
    full-magic contaminated figure. This is genuine internal evidence that fine-grained record
    position carries information beyond `dataset_h`'s existing chunk/order aggregates, independent
    of the label-leak mechanism. The full gap to the ~0.50 public-LB ceiling is only measurable via
    the LB (label-leak contribution + any remaining LB-only effects, e.g. test-set-only ordering).
- **Submission generated** (`scripts/kaggle/generate_submission_K2.py`, importing — never editing —
  `scripts/generate_submission.py`'s `load_validated_payload` / `load_test_features` /
  `predict_proba_ensemble` / `check_against_sample_submission`): `outputs/kaggle/submission_K2.csv`.

  | Field | Value |
  |---|---|
  | Row count | 1,183,748 (matches `sample_submission` row count and full `Id` set) |
  | Positive predictions | 1,324 |
  | Threshold used | 0.98 (payload default; derived from the contaminated OOF — flagged, not re-tuned) |
  | md5 | `f63e286cea15ea3394cd9da2f14b511f` |
  | Determinism | Submission-generation step verified byte-identical across two independent runs against the same frozen `k2_magic_model.pkl` (same md5) — same bar as K1's determinism check. Full pipeline retrain-determinism not separately verified (LightGBM multi-threaded histogram building is not guaranteed bit-identical across reruns even with a fixed seed); this does not affect the reported artifact, which is generated from one fixed, saved model payload. |

- **Firewall verified:** `grep -rn --include="*.py" "import.*kaggle" src/ scripts/` excluding both
  `src/kaggle/` and `scripts/kaggle/` → **empty**. No Track 1 or Track 3 `src`/`scripts` file
  modified (diff against `kaggle-main` base `c1aa2ba` touches only `.gitignore` plus the two new
  quarantine trees). `docs/research/git_workflow.md` §code-valve updated to exclude both quarantine
  trees, as pre-registered in §6.2.
### K2 Evidence — Kaggle LB (submitted 2026-07-02, manual submission by user)

`outputs/kaggle/submission_K2.csv` (md5 `f63e286cea15ea3394cd9da2f14b511f`, verified unchanged
immediately before submission) was submitted to the `bosch-production-line-performance` Kaggle
competition via the website (the `kaggle` CLI's newer releases all depend on a `kagglesdk` package
whose last several published PyPI wheels, checked 0.1.28–0.1.32, are missing their own
`competitions/legacy` submodule — an upstream packaging defect, not a local misconfiguration; the
older CLI generations that don't need `kagglesdk` don't support this Kaggle account's `KGAT_`-format
API token. User submitted manually and reported the scores below).

| Metric | K1 (honest baseline) | K2 (record-adjacency magic) | Δ (K2 − K1) |
|---|---|---|---|
| Public LB | 0.14389 | **0.31699** | **+0.17310** |
| Private LB | 0.16160 | **0.32702** | **+0.16542** |

**Gap recovered:** using the documented public-LB leakage ceiling (~0.50, DR-001/KDR-003 §1) as the
top of the honest→leaky gap, K2 recovers `(0.31699 − 0.14389) / (0.50 − 0.14389) ≈ 48.6%` of the
total documented gap on the public split. Private LB moves in the same direction and by a similar
magnitude (+0.165), consistent with K1's own public/private relationship (private slightly higher
than public in both K1 and K2) — no sign of public-LB overfitting from the magic features.

**Internal-vs-external calibration note:** the held-out public LB (0.317) sits close to this
session's **uncontaminated** position-only ablation OOF MCC (0.31761, no `train_resp_*`), not the
**contaminated** full-magic OOF MCC (0.37530, includes the explicit train-neighbor-`Response`
lookup). One data point is not a general law, but it suggests the internal CV's label-leak
component may over-estimate what the explicit `train_resp_*` lookup is worth out-of-sample relative
to the pure position/ordering signal — a candidate line item for K3's attribution work, not a
conclusion drawn here.

### K2 Outcome

**Measurement obtained, as a soft/non-binding buy per §5.** K2 produces a decisive, large movement
(+0.173 public, +0.165 private — more than double K1's honest score) that lands squarely inside the
pre-registered "plausibly toward 0.30–0.50" range for `H_adjacency_dominant`, while leaving roughly
half of the total documented leakage ceiling gap (~51%) still unexplained by the adjacency family
alone.

### K2 Hypothesis classification (against §5 priors)

| Hypothesis | Prior | Result | Verdict |
|---|---|---|---|
| **H_adjacency_dominant** | 0.75 | Public LB 0.317, recovering ~49% of the total gap — a large, decisive rise, within the pre-registered 0.30–0.50 band | **CONFIRMED** |
| H_adjacency_minor | 0.20 | Would have predicted only modest movement; the actual +0.173 public / +0.165 private movement is far larger than "modest" | **Rejected** |
| H_no_gap | 0.05 | Would have predicted little movement; directly falsified by the observed gap | **Rejected** |

Record-adjacency leakage is confirmed as a **major** driver of the honest→leaky LB gap — this
eliminates the "honest work alone can close the gap" hypothesis class, exactly as §3/§4 intended.
It does **not**, however, fully close the gap to the ~0.50 ceiling on its own: roughly half the
documented gap remains unattributed. This residual is the natural target for K3 (candidate D — other
leakage sub-families in isolation, deferred at §3/§4), not evidence against K2's own hypothesis.

### K2 Decision

**Complete.** `outputs/kaggle/submission_K2.csv` is the authoritative K2 artifact (gitignored, not
committed; reproducible on demand from committed quarantine code + pre-registered commands). Tag
`K2-result` placed at the tip of `kaggle/K2-magic-leakage-probe`, merged to `kaggle-main` only. The
Track 2 leakage-gap quantification KDR-001 set out to obtain is delivered: record-adjacency magic
recovers ~49% of the honest→leaky gap. Design K3 (leakage-family attribution of the residual gap,
candidate D) in `KDR-004` if pursued.

---

## KDR-004 — Pre-register K3: attribute K2's gain between record-proximity and neighbor-label leakage

- **Date:** 2026-07-02
- **Decision type:** Experiment pre-registration (Opus, post-K2 planning review). **Authorizes K3
  only.** No `K4+` is authorized. This entry decomposes K2's own +0.173 public / +0.165 private LB
  gain before any new leakage family is probed — a design entry, no code/branch/model in this
  commit.

### §1 — Trigger

K2's real public LB (**0.31699**) landed almost exactly on this session's **uncontaminated**
position-only ablation OOF MCC (**0.31761**, no `train_resp_*` columns) — not the **contaminated**
full-magic OOF MCC (**0.37530**, which includes the explicit train-neighbor-`Response` lookup). This
is a striking coincidence that directly bears on Track 2's stated objective (KDR-001: quantify the
leakage gap by mechanism): **we do not yet know whether K2's real LB gain came from record
*proximity* (label-free, e.g. `id_prev_diff`/`time_prev_diff`/`same_neighbor`) or from the neighbor
*label* lookup (`train_resp_prev`/`train_resp_next`), or both.** K2's own KDR-003 §5 warning already
flagged the label-touching OOF as contaminated (not a valid ranking metric); K3 resolves this on the
only trustworthy signal — the held-out LB — before committing engineering effort to the next,
much larger candidate family (full per-station timing-cohort reconstruction).

### §2 — Imported priors (K1, K2, RP1, RP2 — no re-derivation)

- **K1:** honest baseline, public 0.14389 / private 0.16160.
- **K2:** full magic (24 cols: 18 position + 6 `train_resp`), public 0.31699 / private 0.32702.
  Internal OOF: contaminated full-magic 0.37530; uncontaminated position-only ablation 0.31761.
- **RP1/RP2 (imported ideas only, DR-008):** honest representation/model space is exhausted (AUC
  ~0.55 flat, sensors add nothing durable, stacking hurts, capacity not binding) — this is why Track
  2 exists at all, and why K3 stays inside the already-open leakage-attribution question rather than
  re-deriving a settled honest-space negative.
- **New finding this session (governance-relevant):** internal CV is demonstrably untrustworthy for
  any label-touching leaky feature — the `train_resp_*` block added +0.058 phantom OOF MCC
  (0.318→0.375) that did not survive out-of-sample (real LB 0.317). Every future family estimate
  must be confirmed on the LB, not the OOF, until proven otherwise.

### §3 — Hypotheses (entering priors, fixed before results)

- **H_position_dominant (0.60):** position-only LB ≈ 0.30–0.32 (label-leak contributes ~0 out-of-
  sample; the OOF↔LB coincidence was not a coincidence).
- **H_label_contributes (0.30):** position-only LB materially below K2's 0.317 (e.g. ≤0.29) **and**
  label-only LB clearly above the K1 honest baseline (both components independently generalize).
- **H_position_optimistic (0.10):** position-only LB is materially below its own OOF (0.318) —
  i.e. even the label-free position features are CV-optimistic (chunk-aware CV under-blocks
  record-order leakage). A governance-relevant surprise: would mean *any* record-order feature,
  leaky-labeled or not, needs a stronger internal safeguard than chunk grouping provides.

### §4 — Feature/model specification (no new feature family — reuse K2's columns exactly)

Both variants reuse the **already-computed** `MAGIC_FEATURE_COLS` from `src.kaggle.magic_features`
(K2, unchanged) merged onto `dataset_h`'s 16 clean features (also unchanged) — no new sort order, no
new column, no re-run of `compute_magic_features`. The existing `data/features/dataset_h_magic_{train,test}.parquet`
(built at K2) already contain every column either variant needs; K3 does not rebuild them.

- **Variant A — position-only:** `DATASET_H_FEATURE_COLS` (16) + the 18 position/delta/tie-flag
  magic columns, **excluding** all 6 `*_train_resp_*` columns. Label-free by construction.
- **Variant B — label-only:** `DATASET_H_FEATURE_COLS` (16) + only the 6 `*_train_resp_*` columns
  (nearest train-neighbor `Response`, prev/next, across all 3 sort orders). Label-touching — its
  internal OOF is contaminated by construction (same mechanism as K2's full model) and must be
  flagged, never compared to an honest MCC.
- **Hyperparameters:** identical LightGBM config as `dataset_h`/K2 (`train_lightgbm_oof` reused
  unchanged) — no hyperparameter change is logged, so none is made.
- **Threshold:** each variant's own OOF-derived `best_threshold` (from `search_best_mcc_threshold`,
  already run inside `train_lightgbm_oof`) is used as-is. For Variant A this is an **honest**
  threshold (uncontaminated OOF) — a incidental repair of K2's own contaminated-0.98 operating
  point. For Variant B the threshold is contaminated, exactly as flagged for K2's full model.

### §5 — Success / pass / failure criteria

- **Process (BINDING):** K3 fully recorded — this pre-registration, `kaggle/K3-adjacency-attribution`
  off `kaggle-main`, `K3-result` tag, results merged to `kaggle-main` **only**, both submissions
  reproducible from committed quarantine code + documented commands. Firewall (§6) checks pass.
- **Outcome (SOFT, non-binding):** a confident classification into exactly one of §3's hypotheses,
  using the two real LB scores plus the existing K1/K2 reference points. We are buying the
  attribution, not a particular direction.
- **Failure/warning:** Variant B's internal OOF MCC is contaminated (train-neighbor `Response`
  leaks across folds, same mechanism as K2) — must be flagged and never used as a ranking metric;
  only the LB legitimately measures it. If a submission is not reproducible or the firewall is
  breached, K3 reports "unresolved — rebuild" and draws no attribution.

### §6 — Contamination safeguards

Same quarantine as K2 — no new trees. `src/kaggle/magic_features.py` may gain small additive
constants (e.g. named column-subset lists) to avoid duplicating the position/label-only filter
logic across scripts; this is a refactor-for-reuse, not a new feature family, and does not change
any existing K2 column's computation. New training entry point(s) under `scripts/kaggle/` for the
two variants; the existing `scripts/kaggle/generate_submission_K2.py` is reused **unchanged** for
both variants' submissions (it is already generic over `--model-path`/`--test-features`/`--output`
and reads the feature list from the payload, not a hardcoded column list) — no new submission script
required. Code valve (`grep -rn --include="*.py" "import.*kaggle" src/ scripts/` excluding both
`src/kaggle/` and `scripts/kaggle/`) must remain empty before merge. No Track 1/3 file touched. No
`decisions.md` entry. No leaderboard number outside `kaggle_decisions.md`.

### §7 — Git strategy

- **Branch:** `kaggle/K3-adjacency-attribution`, cut from `kaggle-main` **after** this KDR-004 is
  ratified and committed onto `kaggle-main` (K1/K2 precedent).
- **Commits:** `K3 exp:` (variant training code + reuse), `K3 eval:` (submissions + validation),
  `K3 docs:` (Evidence/Outcome/Decision, once the LB scores are in).
- **Merge:** `kaggle/K3-adjacency-attribution` → **`kaggle-main` only**, `--no-ff`. Never `main`.
- **Tag:** `K3-result` (annotated), placed **only after** both LB scores are recorded (K1/K2
  precedent — no tag before outcome evidence exists).

### §8 — Documentation updates required after K3 evidence lands

- `docs/research/kaggle_decisions.md` — fill KDR-004 Evidence/Outcome/Decision + hypothesis
  classification + ledger update (K3 → Complete; K4 pending KDR-005).
- `docs/agent_memory/claude_state.md` — Track 2 state, K3 record, next-step pointer to K4.
- `docs/research/git_workflow.md` — only if a genuinely new rule emerges (none anticipated: same
  quarantine, same code valve, same branch/merge/tag pattern as K2).
- `docs/ml_system_tracks.md` — currently stale since before K1 shipped (still shows 20%/"K1 in
  progress"); reconcile opportunistically with this KDR's commit, not required for K3 itself.
- **Not touched:** `decisions.md` (no Production/research decision changes), README, case study,
  Track 1/3 docs, `CLAUDE.md`.

### §9 — Decision, confidence, next action

- **Decision:** **Authorize K3** = adjacency attribution (Variant A position-only, Variant B
  label-only), exactly as specified in §4–§7, pending user go-ahead for the two outward LB
  submissions. This is the highest information-gain-per-effort action on the Track 2 board (reuses
  committed K2 code and data; no new feature engineering) and gates the design of the next, much
  more expensive candidate (full per-station timing-cohort reconstruction, proposed as K4/KDR-005).
- **Confidence:** **High** that this is the correct next experiment given K2's real LB result;
  **Medium** on which hypothesis wins (0.60/0.30/0.10 prior split) — that is the number K3 buys.
- **Next action:** On go-ahead, cut `kaggle/K3-adjacency-attribution`, train both variants from the
  existing `dataset_h_magic_{train,test}.parquet`, generate two submissions via the existing
  `generate_submission_K2.py`, validate, and (with explicit authorization for the outward
  submissions) measure both LB scores. Record evidence here, tag `K3-result`, merge to
  `kaggle-main` only. Design K4 (timing-cohort, KDR-005) informed by K3's verdict.

### K3 Implementation status (2026-07-01) — build/train/submission complete

**Status update only** (superseded by the Evidence/Outcome/Decision sections below, added
2026-07-02 once both Kaggle LB scores were measured).

- **Branch:** `kaggle/K3-adjacency-attribution`, cut from `kaggle-main` @ `c17955a` (KDR-004
  ratified and committed first, per §7).
- **No new feature family, no dataset rebuild:** both variants read the existing
  `data/features/dataset_h_magic_{train,test}.parquet` built at K2. Added only
  `POSITION_ONLY_MAGIC_COLS` (18) / `TRAIN_RESP_MAGIC_COLS` (6) constants to
  `src/kaggle/magic_features.py` (named split, zero recomputation) and one new training entry
  point, `scripts/kaggle/train_k3_variant.py --variant {position_only,label_only}`, reusing
  `train_lightgbm_oof`/`build_model_payload` from `src.training.modeling` unchanged (same LightGBM
  hyperparameters as `dataset_h`/K2, no change logged).
- **Submissions generated via the existing `scripts/kaggle/generate_submission_K2.py`, unmodified**
  — it is already generic over `--model-path`/`--test-features`/`--output` and reads the feature
  list from the payload, so both variants reused it with zero new submission code.

| Field | Variant A — position_only | Variant B — label_only |
|---|---|---|
| Feature count | 34 (16 `dataset_h` + 18 position/delta/tie-flag) | 22 (16 `dataset_h` + 6 `train_resp_*`) |
| Model | `outputs/kaggle/models/k3_position_only_model.pkl`, fingerprint `e02a1d4e1106fbaa` | `outputs/kaggle/models/k3_label_only_model.pkl`, fingerprint `1c98082a35397fd5` |
| OOF MCC | **HONEST** `0.31761` (label-free; matches the K2-session ablation exactly — reproducible) | **CONTAMINATED** `0.21171` (train-neighbor `Response` leaks across folds; flagged, not comparable to an honest MCC) |
| Threshold | `0.98` (honest — first trustworthy re-tuned threshold in the K2/K3 leaky line) | `0.95` (contaminated-OOF-derived, same caveat as K2) |
| Submission | `outputs/kaggle/submission_K3_position_only.csv` — rows 1,183,748, positives 1,278, md5 `94d74fbd994b49bd66f89ff9cef88894` | `outputs/kaggle/submission_K3_label_only.csv` — rows 1,183,748, positives 1,470, md5 `a34fb58b0c3cecdaa3a4286ad17c6c2d` |
| Id-set vs `sample_submission` | exact match, 0 NaN, schema `[Id, Response]` int64/int64, `Response ∈ {0,1}` | exact match, 0 NaN, schema `[Id, Response]` int64/int64, `Response ∈ {0,1}` |
| Determinism | 2 independent submission-generation runs against the same frozen model → byte-identical (same md5) | 2 independent submission-generation runs against the same frozen model → byte-identical (same md5) |

- **Firewall verified:** `grep -rn --include="*.py" "import.*kaggle" src/ scripts/` excluding both
  `src/kaggle/` and `scripts/kaggle/` → **empty**. Diff against `kaggle-main` base `c17955a` touches
  only `src/kaggle/magic_features.py` (additive constants) and the new
  `scripts/kaggle/train_k3_variant.py` — no Track 1/3 file modified.
- **Interim observation (not the K3 verdict):** Variant B's contaminated OOF (0.21171) is *lower*
  than Variant A's honest OOF (0.31761) even with label leakage folded in — the 6 `train_resp_*`
  columns alone carry less internal signal than the 18 position/delta columns. Consistent with, but
  not proof of, `H_position_dominant`; the real test is the LB.

### K3 Evidence — Kaggle LB (submitted 2026-07-02, manual submission by user)

`outputs/kaggle/submission_K3_position_only.csv` (md5 `94d74fbd994b49bd66f89ff9cef88894`) and
`outputs/kaggle/submission_K3_label_only.csv` (md5 `a34fb58b0c3cecdaa3a4286ad17c6c2d`) — both
verified unchanged immediately before submission — were submitted to the
`bosch-production-line-performance` Kaggle competition via the website (same `kagglesdk` CLI
packaging defect as K2; user submitted manually and reported the scores below).

| Metric | K1 (honest) | K2 (full magic) | K3-A (position-only) | K3-B (label-only) |
|---|---|---|---|---|
| Public LB | 0.14389 | 0.31699 | **0.31791** | **0.10065** |
| Private LB | 0.16160 | 0.32702 | **0.33161** | **0.10530** |

**K3-A (position-only) slightly *exceeds* K2's full-magic score on both splits** (+0.00092 public,
+0.00459 private) despite dropping the 6 `train_resp_*` columns entirely. **K3-B (label-only) falls
*below* even the K1 honest baseline** on both splits (−0.04324 public, −0.05630 private) — the
`train_resp_*` columns alone are actively harmful to a lean model, not merely unhelpful.

**Internal-vs-external calibration resolved:** K3-A's honest OOF MCC (0.31761) matches its real LB
(0.31791 public / 0.33161 private) to within 0.0003–0.014 — the label-free position/ordering
features generalize almost exactly as the internal CV predicted. This confirms the K2-evidence note's
suspicion: the internal CV's apparent gain from `train_resp_*` (contaminated OOF 0.37530 vs honest
0.31761, a +0.058 phantom) was **entirely a chunk-aware-CV blind spot**, not real out-of-sample
signal — real LB shows the label-touching columns *subtract* value once out of sample.

### K3 Outcome

**Measurement obtained, as a soft/non-binding buy per §5.** The two-variant split isolates the two
candidate mechanisms cleanly: record-proximity (position/delta/tie-flag columns) explains the entire
observable K2 gain and then some; neighbor-label lookup (`train_resp_*`) explains none of it and is
actively harmful when it is the only magic signal present.

### K3 Hypothesis classification (against §3 priors)

| Hypothesis | Prior | Result | Verdict |
|---|---|---|---|
| **H_position_dominant** | 0.60 | Position-only public LB 0.31791 ≈ K2's 0.31699 (slightly exceeds it); private LB 0.33161 > K2's 0.32702 | **CONFIRMED** |
| H_label_contributes | 0.30 | Would require position-only LB materially below 0.317 **and** label-only LB clearly above K1's 0.14389. Neither holds: position-only ≈/exceeds K2, and label-only (0.10065/0.10530) is *below* K1 | **REJECTED** |
| H_position_optimistic | 0.10 | Would require position-only LB materially below its own OOF (0.31761). Actual public LB (0.31791) sits within 0.0003 of OOF, private (0.33161) exceeds it | **REJECTED** |

Record proximity is confirmed as the **entire** source of K2's real LB gain; neighbor-label lookup
contributes **zero** out-of-sample and actively **subtracts** value when isolated. Chunk-aware CV's
under-blocking of record-order leakage (the H_position_optimistic concern) did **not** materialize —
label-free record-order OOF is trustworthy. This eliminates neighbor-label leakage as a research
direction entirely and repairs confidence in OOF-as-primary-metric for any future label-free
record-order feature (directly informs K4/KDR-005's design).

### K3 Decision

**Complete.** `outputs/kaggle/submission_K3_position_only.csv` and
`outputs/kaggle/submission_K3_label_only.csv` are the authoritative K3 artifacts (gitignored, not
committed; reproducible on demand from committed quarantine code + pre-registered commands). Tag
`K3-result` placed at the tip of `kaggle/K3-adjacency-attribution`, merged to `kaggle-main` only.
KDR-004's attribution question is resolved: K2's gain is **100% record-proximity, 0% neighbor-label**.
Design K4 (label-free timing-cohort features, informed by this verdict — neighbor-label work is
retired) in `KDR-005`.

---

## Pending Kaggle experiment ledger

| ID | Pre-registered question | Status |
|---|---|---|
| KDR-001 | Open Track 2; fix objective, success criteria, contamination rules, `K`-numbering | **Decided — track open (2026-06-28)** |
| KDR-002 | Pre-register K1: baseline reproduction from frozen production candidate | **Decided — K1 authorized (2026-06-28)** |
| K1 | Reproduce `dataset_h` submission end-to-end; establish authoritative Track 2 baseline | **Complete** — PASS (2026-06-28); tag `K1-result`; md5 `e83b769be914976972a209c5ca278602` |
| KDR-003 | Pre-register K2: quantify the leakage gap via record-adjacency magic features | **Decided — K2 authorized (2026-06-28)** |
| K2 | How much of the leakage gap (0.144 → ~0.50) do record-adjacency magic features recover? | **Complete** — public LB 0.31699 / private LB 0.32702 (~49% of gap recovered); `H_adjacency_dominant` confirmed; tag `K2-result` (2026-07-02) |
| KDR-004 | Pre-register K3: attribute K2's gain between record-proximity and neighbor-label leakage | **Decided — K3 authorized (2026-07-02)** |
| K3 | Does K2's gain come from record proximity (Variant A) or neighbor-label lookup (Variant B), or both? | **Complete** — position-only public 0.31791/private 0.33161 (exceeds K2); label-only public 0.10065/private 0.10530 (below K1); `H_position_dominant` confirmed, `H_label_contributes`/`H_position_optimistic` rejected; tag `K3-result` (2026-07-02) |
| KDR-005 | Pre-register K4: label-free timing-cohort features (record-proximity-adjacent, no neighbor-label) | Pending — see KDR-005 below |
| K4 | Do label-free timing-cohort features (min/max-date group geometry) add over K3-A's 34-feature baseline? | Pending — pre-register in `KDR-005` before branching |
