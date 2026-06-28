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

## Pending Kaggle experiment ledger

| ID | Pre-registered question | Status |
|---|---|---|
| KDR-001 | Open Track 2; fix objective, success criteria, contamination rules, `K`-numbering | **Decided — track open (2026-06-28)** |
| K1 | (to be designed) | Pending — pre-register in `KDR-002` before any Kaggle code |
