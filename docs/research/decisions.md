# Research Decision Log — Bosch Production Line Performance

This is the **canonical scientific record** of the modeling work on this project. It is **not**
session memory (that lives in `docs/agent_memory/`). It is the permanent, append-mostly log of
every hypothesis, experiment, and decision, written so that a reader can reconstruct the complete
scientific story of the project from beginning to end.

## How to use this log

- **One entry per research decision**, newest appended at the end, numbered `DR-NNN`.
- Entries are **pre-registered where possible**: the hypothesis, evidence bar, and decision rule
  (success/failure criteria) are recorded **before** results are seen, to prevent post-hoc
  rationalization. Results and outcomes are filled in afterward, never silently rewriting the
  pre-registered rule.
- Every entry carries these fields:
  - **Date**
  - **Research Question**
  - **Hypothesis**
  - **Prior Reasoning**
  - **Alternatives Considered**
  - **Experiment Designed**
  - **Evidence Collected**
  - **Outcome**
  - **Decision**
  - **Confidence Level** (Low / Medium / High, with justification)
  - **Next Action**
- Confidence is about *our belief in the conclusion*, not about whether an experiment ran.
- Negative results are first-class. A null is recorded as an **upper bound on the effect**, never
  as proof of absence, unless the design genuinely supports a disproof.

## Standing scientific constraints (carried from project charter)

- **Leakage discipline is absolute.** No record-adjacency / timing-to-neighbor / test-order
  features (`mean_timediff_till_next_*`, duplicate/concat magic) enter any model whose metric we
  report as honest. The public-leaderboard ~0.50 is a leakage ceiling, not a modeling target.
- **MCC on labeled OOF/CV only.** Never compute supervised metrics on unlabeled production data.
- **Chunk-aware, group-safe CV** is the default evaluation harness; no `chunk_id` may leak across
  train/validation.

---

## DR-001 — Foundational diagnosis: is the model representation-limited or information-limited?

- **Date:** 2026-06-27
- **Research Question:** Where is future modeling effort highest-return — i.e., what is actually
  limiting model performance today, now that the architecture/infrastructure is complete?
- **Hypothesis:** The current model is **representation-limited rather than model-limited**: there
  is failure-relevant, leakage-safe information in the per-part measurement data that the current
  global-mean compression (`feature_mean`, a single scalar over the ~970-dim numeric sensor block)
  fails to preserve.
- **Prior Reasoning:** Ablation across the model ladder shows discriminative power is concentrated
  almost entirely in target-encoded routing features, not raw measurements. The raw sensor
  representation is collapsed to one scalar, which is architecturally guaranteed to wash out any
  localized (single-sensor / single-station) anomaly. High split-gain importance of the sensor
  aggregates is a known imbalanced-learning artifact (gain fits the bulk distribution) and is
  contradicted by their near-zero standalone MCC — the "split-gain trap."
- **Alternatives Considered:**
  - *Information-limited* (the honest non-leaky ceiling is genuinely ~0.15–0.16). Plausible; the
    massive jump came only from routing/target encoding, and the leaderboard gap is leakage.
  - *Model-capacity-limited* — rejected: LightGBM on 1.18M rows × 16 features is far from
    saturation, and stacking made it worse (see evidence).
  - *Thresholding/calibration-limited* — rejected as a *metric* bottleneck: best-threshold sweep
    already absorbs calibration into reported MCC; it is an operational, not ranking, concern.
  - *CV-methodology-limited* — rejected: the CV is correctly conservative; if anything it is a
    strength.
  - *Temporal non-stationarity* — retained as a secondary, cross-cutting limiter (see evidence:
    fold-MCC spread exceeds feature gains).
- **Experiment Designed:** None at this stage — this entry forms the hypothesis. A minimal
  experimental program to test it is designed in DR-002.
- **Evidence Collected** (from `outputs/training_summary.json`, full-scale ~1.18M-row run):
  | Model | Features added | OOF MCC | Δ |
  |---|---|---|---|
  | baseline | sensor aggregates only | 0.0225 | — |
  | dataset_g | + target-rate routing features | 0.1366 | +0.1141 |
  | dataset_h | + transition / station-pair co-occurrence | 0.1534 | +0.0168 |
  | meta_model | stack of the three | 0.1494 | −0.0040 |
  - Kaggle (dataset_h): public 0.14389, private 0.16160 — brackets OOF MCC, consistent with a
    non-leaky baseline.
  - dataset_h feature importance: sensor aggregates rank *above* routing features by split-gain,
    while contributing ~0 standalone MCC (the split-gain trap).
  - Per-fold MCC (dataset_g): 0.117–0.164 — a spread (~0.05) larger than the entire g→h gain
    (0.017), indicating temporal non-stationarity.
- **Outcome:** "Representation-limited" adopted as the **leading** hypothesis; "information-limited"
  retained as the primary competing hypothesis. The two are distinguishable by experiment.
- **Decision:** Do **not** fund more stacking (proven negative), HPO/model swaps (capacity not
  binding), additional routing-feature variants (diminishing returns), or leaderboard chasing
  (leakage). Design the smallest experimental program that discriminates representation-limited
  from information-limited.
- **Confidence Level:** **Medium.** The ablation strongly implicates representation, but split-gain
  importance is consistent with *both* the representation and information-limited stories; only a
  direct experiment resolves it.
- **Next Action:** Design the minimal uncertainty-reduction program → DR-002.

---

## DR-002 — Minimal experimental program to test the representation-limited hypothesis

- **Date:** 2026-06-27
- **Research Question:** What is the smallest sequence of experiments that either supports or
  falsifies "representation-limited," maximizing information gained per unit of scarce engineering
  effort — and answering the *decision* the project actually faces: *fund a representation-
  engineering phase for the production model, yes or no?*
- **Hypothesis (program-level):** A leakage-safe, information-preserving representation of the
  per-part measurement data will add durable MCC on top of the production model (`dataset_h`). If
  true → representation-limited and worth funding. If false → at/near the honest ceiling.
- **Prior Reasoning:** The decision hinges on two conditions that are jointly necessary and
  sufficient: the sensor signal must be **additive** to routing (not redundant), and it must
  **survive temporal generalization** (not an in-sample artifact). A third question — does the
  sensor data carry *any* standalone signal — is merely *explanatory*: it diagnoses *why* a
  negative occurs but does not, by itself, change the funding decision.
- **Alternatives Considered (and why this design beats them):**
  - *Original ordering (signal-presence → additivity → durability, three sequential gates).*
    Superseded. It ordered by mechanistic logic, not decision-relevance. Its first gate
    (sensors-alone) is neither necessary nor sufficient for the funding decision, and its most
    likely failure mode (redundancy with routing) would cost two experiments to reach "no."
  - *Prescribing the raw sensor matrix as the first probe.* **Rejected** — smuggles an
    implementation into the hypothesis, conflates information-preservation with model-learnability,
    and makes a null uninterpretable (no-signal vs. bad-exposure). The first experiment must fix an
    *evidence bar and comparator*, not an encoding.
  - *Collapsing additivity + durability into a single temporal-split test.* **Rejected** — temporal
    splits at 0.58% positives are noisy, and a direct temporal null cannot separate "no additive
    signal" from "additive but non-durable signal." Two stages preserve diagnostic resolution at
    low marginal cost.
- **Experiment Designed — pre-registered program:**
  - **E1 (GATE) — Additive-value probe.** Does a leakage-safe, *information-preserving* sensor
    representation improve OOF MCC over `dataset_h` (0.1534) on the existing chunk-aware CV harness?
    - *Implementation-agnostic by construction:* Opus fixes the comparator (`dataset_h`) and the
      evidence bar; the implementer selects the representation by an explicit information-
      preservation criterion (retaining the most localized/structural information — including
      missingness/activity, not only numeric values — at low cost) and must report what it was and
      why, so a null can be scoped as an upper bound.
    - *Success:* combined OOF MCC exceeds 0.1534 by **> 2× the cross-fold MCC standard deviation**
      (noise-anchored, not a magic number).
    - *Failure:* combined OOF MCC within one fold-σ of 0.1534, or below — recorded as
      *"recoverable additive signal bounded below [noise] under the probed information ceiling,"*
      not as proof of zero.
    - *Bounded escalation:* at most one alternative representation family permitted on a null, and
      only with an a-priori reason to suspect under-exposure.
  - **E2 (GATE) — Temporal durability.** Re-evaluate the E1 configuration under a purely temporal /
    forward-chaining (out-of-time) split.
    - *Success:* the additive gain retains **≥ ~70–80%** of its in-CV magnitude and the
      combined-beats-routing ordering holds out-of-time.
    - *Failure:* gain collapses into noise out-of-time, or sign-flips.
  - **E1′ (CONDITIONAL DIAGNOSTIC, not a gate) — Sensors-alone vs. collapsed baseline.** Run only
    if E1 fails *and* understanding "no signal" vs. "redundant signal" would change whether we ever
    revisit representation work. Explanatory, off the critical path.
- **Evidence Collected:** None yet — this entry is a **design/pre-registration**. No experiment has
  run.
- **Outcome:** Program defined and pre-registered. The reorder-by-decision-relevance is proposed
  for user ratification; it strictly dominates the original three-gate ordering in expected
  experiments-to-decision while testing the same underlying questions.
- **Decision:** On user go-ahead, run **E1 (additive-value probe)** first. Hold E2 until E1 passes.
  Hold E1′ unless E1 fails and the diagnostic is decision-relevant. Every result returns to Opus
  for interpretation against the decision tree before the next experiment is authorized — no
  experiment is pre-approved on the assumption its predecessor passes.
- **Confidence Level:** **High** in the *design* (the two gates are necessary and sufficient for
  the funding decision); **N/A** for results (unrun). Confidence in the *hypothesis itself* remains
  Medium per DR-001.
- **Next Action:** Await user ratification of (a) the reordered program and (b) whether an E1
  failure is an acceptable stop signal or must escalate to a second representation family. Then
  authorize E1.

---

## DR-003 — Adopt the research Git protocol and establish the stable baseline

- **Date:** 2026-06-27
- **Research Question:** How should Git history be run during the experimental phase so it becomes a
  scientific record — reproducible, traceable, easy to roll back — without overhead that makes us
  abandon the process?
- **Hypothesis:** A lightweight branch-per-experiment protocol with ID-keyed branches/commits/tags/
  PRs, anchored to one immutable baseline tag, is sufficient for full scientific traceability while
  staying simple enough to actually follow.
- **Prior Reasoning:** Experiments must diff against a single immutable anchor or reproducibility and
  clean diffs are lost. Null results are first-class and must be preserved without polluting `main`.
  The join between the decision log and Git must be bidirectional and trivial (grep-able IDs).
- **Alternatives Considered:**
  - *Merge everything, including dead ends, to main* — rejected: pollutes the lineage and harms
    portfolio readability. Replaced by "main = what we believe; tags + log = what we tried."
  - *Abandon failed experiments without preserving them* — rejected: destroys reproducibility and
    the scientific record of negatives. Replaced by tag + closed-PR + DR-entry preservation.
  - *Branch experiments off the open production PR / feature branch* — rejected: a mutable baseline
    shifts under the experiment. Replaced by a frozen `baseline-v1` tag on `main`.
  - *GitFlow / heavier multi-branch models* — rejected as over-engineering for a solo research phase.
- **Experiment Designed:** N/A (process decision). Protocol written to `docs/research/git_workflow.md`.
- **Evidence Collected:** N/A.
- **Outcome:** Protocol adopted. Baseline decision: establish `baseline-v1` as the stable research
  anchor **before** E1, by merging PR #1 into `main` and tagging the merge commit `baseline-v1`;
  cut `exp/E1-additive-sensor-probe` from that tag. A lighter fallback (tag the feature-branch tip
  `bef707f` as `baseline-v1` without merging) is documented but not recommended.
- **Decision:** Use the protocol for all remaining experimental work. Treat "establish `baseline-v1`"
  as a hard precondition for E1.
- **Confidence Level:** **High** — the protocol is minimal and the baseline reasoning is structural.
- **Next Action:** User to (a) approve merging PR #1 + tagging `baseline-v1` (outward action, needs
  explicit go-ahead), then (b) authorize E1 cut from `baseline-v1`.

---

## Pending experiment ledger

| ID | Role | Pre-registered question | Status |
|---|---|---|---|
| E1 | Gate | Additive sensor signal over dataset_h, in-CV? | Designed, not run |
| E2 | Gate | Does the E1 additive gain survive out-of-time? | Blocked on E1 pass |
| E1′ | Conditional diagnostic | Sensors-alone vs. collapsed baseline (why a null?) | Blocked on E1 fail + relevance |
