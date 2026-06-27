# Bosch Research Git Protocol

Lightweight-but-strict Git workflow for the experimental research phase. Optimized for
reproducibility, scientific traceability, easy rollback, minimal overhead, and clean portfolio
presentation. Companion to `docs/research/decisions.md` (the canonical decision log).

## The whole thing in six lines

1. `main` = what we currently believe (always reproducible). Tags + log = everything we tried.
2. One experiment = one branch (`exp/E1-…`) = one tag (`E1-result`) = one PR = one DR entry.
3. Branch every experiment from the immutable `baseline-v1` tag, never from another experiment.
4. Prefix branch/commit/PR with the experiment ID; `git log --grep E1` rebuilds the experiment.
5. Positive/kept result → merge. Null/dead-end → abandon, but tag + document so it stays reproducible.
6. The `decisions.md` update lands on `main` regardless of whether the experiment's code does.

## Branch strategy

- **`main`** — stable, always-green, always-reproducible; current model lineage + full decisions.md.
  Protected by convention (no direct experiment commits).
- **`baseline-vN`** — immutable **tag** (not a branch): the single anchor experiments diff against.
- **`exp/<ID>-<slug>`** — one short-lived branch per experiment, cut from `baseline-vN`. All
  iterations stay as commits on this one branch. No experiment branches off another experiment
  unless it builds on a *merged* predecessor (then branch from `main`, note the dependency in the
  DR entry).

## Naming convention

| Thing | Pattern | Example |
|---|---|---|
| Baseline anchor | `baseline-vN` (tag) | `baseline-v1` |
| Experiment branch | `exp/<ID>-<kebab-slug>` | `exp/E1-additive-sensor-probe` |
| Conditional/diagnostic (`'` → `p`) | `exp/<IDp>-<slug>` | `exp/E1p-sensors-alone` |
| Result anchor | `<ID>-result` (tag) | `E1-result`, `E2-result` |

IDs come from `decisions.md` and are the **join key** across log, branches, commits, tags, PRs.

## Commit convention

`<ID> <type>: <summary>` — types: `exp` (change under test), `eval` (run + metrics),
`docs` (record), `chore`/`fix` (harness). One variable changed per experiment.

The **evidence commit** body must record: metric result; the pre-registered pass/fail bar **and the
verdict against it**; random seed(s); **data fingerprint** (reuse existing `data_fingerprint`);
exact reproduce command. Trailer: `Refs DR-NNN / E1` + repo `Co-Authored-By`.

## Pull request convention

One PR per experiment branch → `main`. Title: `[E1] <probe name> — <one-line outcome>`.
Fixed body template:
- DR link + experiment ID
- Hypothesis + pre-registered success/failure criteria (copied before results, never edited after)
- Evidence (metric table: OOF MCC, per-fold MCC, head-to-head vs comparator)
- Outcome (pass / fail / inconclusive, stated against the bar)
- Decision (merge or abandon, why)
- Reproducibility (seed, data fingerprint, command)

Three consistent records: commit = atomic proof, PR = narrative, decisions.md = canonical interpretation.

## Merge policy

- **Merge** a kept artifact: result passes its bar and advances the model/contract, **or** any
  reusable harness/tooling (merge tooling even on a negative scientific result).
- Prefer a **merge commit** for experiments (keeps internal commits as a contained, grep-able unit);
  squash is fine for pure plumbing.
- `main` stays green + reproducible post-merge; the experiment's decisions.md update is in the merge.

## Abandon vs merge

| Outcome | Code → main? | Preserved as |
|---|---|---|
| Passes bar, kept artifact | Merge | merge commit + `E*-result` tag + DR entry + merged PR |
| Fails / inconclusive, no reusable artifact | Abandon (don't merge) | `E*-result` tag + DR entry + closed-unmerged PR |
| Negative result but reusable harness | Merge harness only | tag + DR entry + PR documenting both |

Principle: `main` carries the lineage of *what we believe*; tags + decisions.md carry the full
history of *what we tried*. Dead ends are tagged + documented, never deleted — always one
`git checkout E*-result` from a full rerun.

## How failed experiments are recorded (four places, none touching main's code lineage)

1. **decisions.md** — DR Evidence/Outcome/Decision filled; null framed as an **upper bound**, never
   proof of zero.
2. **Tag `E*-result`** — immutable pointer surviving branch deletion.
3. **Closed (unmerged) PR** — GitHub keeps narrative + diff permanently.
4. **Small commit on `main`** updating decisions.md + the pending-experiment ledger (the *record*
   lands on main even though the *code* does not).

## decisions.md ↔ Git, and ID ↔ history

```
DR-NNN ──designs──▶ E1, E2, E1p           (why / what / decision rule)
  └─ E1 ──is──▶ branch exp/E1-...          (how / when; commits prefixed "E1 …")
        ├──tagged──▶ E1-result             (immutable where)
        ├──PR──▶ [E1] ...                   (narrative)
        └──feeds back──▶ DR-NNN Evidence/Outcome/Decision
```

`git log --grep "E1"` and the DR entry retrieve the same experiment from either direction.

## Definition of "experiment done" (the only checklist)

① results committed with seed + data fingerprint + reproduce command; ② `E*-result` tag placed;
③ PR filled with the template; ④ decisions.md DR entry updated; ⑤ merge-or-abandon decision
recorded. Missing any one → not done.

## Baseline

Experiments require a single immutable anchor. The stable research baseline is the tag
**`baseline-v1`**, placed on `main` at the production-system merge commit (PR #1 merged 2026-06-27).
All experiment branches are cut from `baseline-v1`. See DR-003 for the adoption decision.

## Two tracks, one repo (added DR-005)

The repo runs two non-overlapping programs. Disjoint ID prefixes are both the join key and the
contamination firewall.

| | Production (primary) | Kaggle (secondary) |
|---|---|---|
| Canonical log | `decisions.md` | `kaggle_decisions.md` |
| Decision IDs | `DR-NNN` | `KDR-NNN` |
| Experiment IDs | `E<N>` (diagnostics `E<N>p`) | `K<N>` |
| Branch | `exp/E<N>-slug` | `kaggle/K<N>-slug` |
| Result tag | `E<N>-result` | `K<N>-result` |
| Cut from | `baseline-v1` | `kaggle-main` (seeded from `baseline-v1`, forward-merged from `main`) |
| Long-lived line | `main` | `kaggle-main` (lazy; created at `K1`) |
| Merges to | `main` (if kept) | `kaggle-main` only — **never `main`** |
| Cross-merge | `main` → `kaggle-main` **allowed** | `kaggle-main` → `main` **forbidden** (only the §re-derivation gateway crosses) |
| Quarantined code | n/a | `src/kaggle/`, `scripts/kaggle/` (no outside module may import these) |

> **Revision (DR-008):** Kaggle branches now cut from `kaggle-main` (not `baseline-v1` as DR-005
> provisionally stated), so the Kaggle track inherits Production advances by forward-merging `main`.
> The reverse merge is forbidden; Production-bound Kaggle ideas use the re-derivation gateway below.

**Hard rules.** `main` is production lineage and stays leakage-free forever — no `kaggle/*` branch
ever merges into it. No leaderboard score or leakage-laden metric appears in `decisions.md` or
gates any `E`/`DR`. Shared infrastructure (data prep, CV harness, `src/training/`, clean feature
contracts) is imported by both tracks; competition-only/leaky feature logic lives only in
`src/kaggle/`. `git log --grep "E"` returns only production work; `--grep "K"` only Kaggle. See
DR-005 §4 and DR-007 §4 for the full contract.

### Contamination checklist (run before any merge to `main`)

A change may merge to `main` only if **all** are true. Any "no" → it is Kaggle work, route it to
`kaggle/K*` / `kaggle-main` instead.

1. **Feature provenance:** every feature is computable from a single part's own raw record at
   scoring time — no record-adjacency, timing-to-neighbor, test-order, or duplicate/concat features
   (the `LEAKY_FEATURE_PREFIXES` family). 
2. **Metric provenance:** every reported MCC/threshold was computed on labeled OOF/CV data with the
   chunk-aware group-safe harness — never on unlabeled production data, never with a leaky feature.
3. **No import of `src/kaggle/`** anywhere in the changed code outside `src/kaggle/` itself.
4. **No leaderboard number** appears in `decisions.md` or in any `DR`/`E` rationale.
5. **Log routing:** the change's scientific record lands in `decisions.md` (`DR`/`E`), not
   `kaggle_decisions.md`.

If a single experiment produces both an honest production result and a leaky leaderboard variant,
they are **two experiments** (`E*` and `K*`) on **two branches**, recorded in **two logs** — never
one commit.

### The evidence valve and re-derivation gateway (DR-008)

Production's protocol is strictly stronger than Kaggle's, so value flows asymmetrically:

| What crosses | Prod → Kaggle | Kaggle → Prod |
|---|---|---|
| Ideas / hypotheses | free | free, but only as a **fresh pre-registered `DR`/`E`** (zero borrowed priors) |
| Code (import) | free | forbidden (`src/kaggle/` is import-inward-only) |
| Evidence / metrics | free | **forbidden** (never in `decisions.md`, never gates a `DR`/`E`) |
| Features | free | only via the **re-derivation gateway** |

**Re-derivation gateway** (the *only* inbound Kaggle→Production path): open a new `E<M>` with fresh
`DR` pre-registration → re-implement the mechanism leakage-free (if impossible, it stays Kaggle-only
forever) → re-validate on the chunk-aware honest-OOF harness → **discard the Kaggle number**, keep
only the reproduced Production MCC → merge after the contamination checklist. A Kaggle result that
cannot survive this gateway is, by definition, not a Production result.

**Code valve enforcement:** before any merge to `main`,
`grep -r "import.*kaggle" src/ scripts/ --include=*.py` (excluding `src/kaggle/`) must be empty.
Wire into CI when `K1` opens.
