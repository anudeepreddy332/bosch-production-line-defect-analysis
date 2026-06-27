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

## Conventions (mirror the production protocol, disjoint namespace)

- Decisions numbered `KDR-NNN`; experiments `K<N>`; branches `kaggle/K<N>-slug` cut from
  `baseline-v1`; result tags `K<N>-result`. Merges go to `kaggle-main`, **never** `main`.
- Shared, track-neutral infrastructure (data prep, chunk-aware CV harness, `src/training/`,
  `src/utils/`, clean feature contracts) is imported from the production codebase — *sharing
  infrastructure is allowed; sharing results/metrics is not*.

## Status

**No Kaggle experiment has been run.** This file is a charter skeleton, created when the two-track
separation was formalized (DR-007). The first entry will be `KDR-001` when a leaderboard objective
is actually opened. Until then the project's active work is entirely on the Production track.

---

## Pending Kaggle experiment ledger

| ID | Pre-registered question | Status |
|---|---|---|
| (none) | — | Track scaffolded; no experiment authorized |
