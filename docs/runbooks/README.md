# Runbooks Index

Practical, command-level guides for running, operating, and deploying this project. These
runbooks describe **what the code actually does today**, verified by running it — not the
aspirational spec in `tasks.md`/`system_design.md`. Where the code falls short of that spec, the
gap is called out explicitly rather than glossed over.

For the architectural source of truth (the three-track split, the two dashboard views, and a
full audit of where docs/code previously diverged from that split), see
[`docs/ml_system_tracks.md`](../ml_system_tracks.md). These runbooks are operational companions
to that document, not a replacement for it.

## Runbooks

| Runbook | Covers |
|---|---|
| [`local_setup.md`](local_setup.md) | Python/conda environment, required local files, `.env` variables, sanity checks |
| [`track1_offline_evaluation.md`](track1_offline_evaluation.md) | Labeled OOF evaluation, threshold/cost tuning, why supervised metrics are allowed here |
| [`track2_kaggle_submission.md`](track2_kaggle_submission.md) | Generating a Kaggle `submission.csv` from the approved `dataset_h` model |
| [`track3_production_inference.md`](track3_production_inference.md) | Label-free batch inference, `batch_id`/`cycle_id`/`run_seq` state, S3 append-only upload |
| [`dashboard.md`](dashboard.md) | Running Streamlit locally, View A (Production Monitoring) vs View B (Offline Evaluation) |
| [`docker.md`](docker.md) | Current Dockerfiles/compose, what works, what's not wired up yet |
| [`aws_s3.md`](aws_s3.md) | Bucket/env vars, Track 3 key layout, append-only contract, credential guidance |
| [`ec2_deployment.md`](ec2_deployment.md) | Deploying to an EC2 instance — explicitly marked verified vs. planned |
| [`troubleshooting.md`](troubleshooting.md) | Symptom → cause → fix for the most common failures |

## Project tracks (summary)

This repo has three distinct tracks that consume the same trained models differently. Full detail
and audit history: [`docs/ml_system_tracks.md`](../ml_system_tracks.md).

1. **Track 1 — Offline Training + Evaluation.** Labeled data in, approved model + metrics out.
   Supervised metrics (MCC, precision, recall, confusion matrix) are computed here and **only**
   here. This is what the existing Streamlit dashboard pages (all except "Production Monitoring
   (Track 3)") show — labeled OOF data, not live scores.
2. **Track 2 — Kaggle Submission.** Unlabeled Kaggle test data in, `Id,Response` `submission.csv`
   out. Verified working end-to-end **for `dataset_h` only** — see
   [`track2_kaggle_submission.md`](track2_kaggle_submission.md) for the exact command and why the
   other three models (`baseline`, `dataset_g`, `meta_model`) are still blocked.
3. **Track 3 — Production Inference Simulation.** Unlabeled batches in, label-free risk
   scores/decisions out, scored against `dataset_h`. Append-only, partitioned local + S3 output,
   resumable batch-by-batch state. Rendered in the Streamlit dashboard's "Production Monitoring
   (Track 3)" page.

## Recommended reading order

1. [`local_setup.md`](local_setup.md) — get the environment and artifacts in place first.
2. [`track1_offline_evaluation.md`](track1_offline_evaluation.md) — the most "finished" track;
   good for orienting yourself in the codebase.
3. [`track3_production_inference.md`](track3_production_inference.md) — the production-facing
   track this project is actually built around.
4. [`aws_s3.md`](aws_s3.md) — once you need Track 3's S3 output or the dashboard's Production
   Monitoring view.
5. [`dashboard.md`](dashboard.md) — view both tracks' output in one place.
6. [`track2_kaggle_submission.md`](track2_kaggle_submission.md) — only if you need a Kaggle
   submission.
7. [`docker.md`](docker.md) and [`ec2_deployment.md`](ec2_deployment.md) — only when you need to
   run this somewhere other than your own machine; both documents are explicit about what is
   verified vs. still a known gap.
8. [`troubleshooting.md`](troubleshooting.md) — keep this open while doing any of the above.

## Current known limitations (read before deploying)

- **Docker is not S3-ready.** `Dockerfile.dashboard` does not install `boto3` or `python-dotenv`,
  but `apps/streamlit_dashboard/app.py` imports `boto3` unconditionally at module load — the
  dashboard container will fail to start as currently built. `docker-compose.yml` also does not
  pass any AWS credentials/region into either container. See [`docker.md`](docker.md).
- **The dashboard hardcodes its S3 bucket and region** (`apps/streamlit_dashboard/app.py`),
  separately from the `AWS_BUCKET_NAME`/`AWS_REGION` env vars `src/utils/s3_utils.py` reads from
  `.env`. Two sources of truth for the same configuration. See [`aws_s3.md`](aws_s3.md).
- **Drift monitoring is still Track-1-shaped.** `scripts/run_drift_monitoring.py` reads
  `data/features/meta_dataset.parquet` (labeled) and a historical, non-reproducible blend file
  (`oof_predictions_context_meta_v2_blend.parquet` — see `data/README.md`), not Track 3's
  unlabeled S3 output. It is not yet part of the label-free production path and is not rendered in
  the dashboard's Production Monitoring view.
- **Kaggle submission only works for `dataset_h`.** `baseline`, `dataset_g`, and `meta_model` have
  no test-side feature-engineering script, so `scripts/generate_submission.py` cannot be run
  against them yet. See [`track2_kaggle_submission.md`](track2_kaggle_submission.md).
- **EC2 deployment is a documented plan, not a verified procedure** — no EC2 instance was actually
  provisioned/tested while writing [`ec2_deployment.md`](ec2_deployment.md). Treat every command
  in it as "should work based on the verified local/Docker behavior," not "has been run on EC2."
