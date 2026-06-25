# Dashboard

## Running Streamlit locally

```bash
streamlit run apps/streamlit_dashboard/app.py
```

Opens at `http://localhost:8501`. The dashboard requires S3 access for **every** page (both
views load data from S3, not local disk) — see "What S3 data this dashboard expects" below before
running it.

## View A: Production Monitoring (Track 3)

The sidebar page **"Production Monitoring (Track 3)"**. Label-free by contract: it lists every
`predictions/cycle=*/batch=*/predictions.parquet` object in S3, concatenates them, and
runtime-raises if the result ever contains a `Response` column — this view refuses to render data
that could be labeled. It shows only:

- Total predictions, latest cycle/batch/run_seq, latest `scored_at_utc`
- Flagged / auto-reject / manual-inspect counts
- A risk-score histogram
- Batch growth (rows per batch + cumulative predictions over `run_seq`)
- Top 100 risky parts by `risk_score`

**No MCC, precision, recall, accuracy, or confusion matrix anywhere on this page** — there is no
ground truth to compute them against.

This page is genuinely new and was the explicit "View A" gap documented in
[`docs/ml_system_tracks.md`](../ml_system_tracks.md) as "not yet built" — it now exists, see that
document's current state notes for full detail.

## View B: Offline Evaluation (labeled OOF data)

Every other sidebar page (Overview, Threshold Explorer, Inspection Budget Simulator, Recall at
Fixed Precision, Cost Simulator, Model Insights, Failure Analysis). These load
`data/features/meta_dataset.parquet` joined to `oof_predictions_final.parquet` from S3 — both
**labeled** Track 1 data — and compute real MCC/precision/recall/confusion-matrix figures. This is
legitimate offline model-evaluation work, not a production-inference view; see
[`track1_offline_evaluation.md`](track1_offline_evaluation.md) for why supervised metrics are
allowed here.

A one-line caption at the top of every page now states that everything except "Production
Monitoring (Track 3)" uses labeled OOF data. The underlying code in these pages
(`load_scoring_data()`, the `live_df` variable name throughout) still implies "live" data more
than it should — a known, deliberately-deferred naming cleanup, not a correctness issue (the
*data* loaded is correctly labeled OOF data; only the *names* are misleading).

## What S3 data View A expects

```
predictions/cycle={cycle_id}/batch={batch_id}/predictions.parquet
```

written by `scripts/run_production_inference.py` — see
[`track3_production_inference.md`](track3_production_inference.md). If this prefix is empty (no
batches scored yet), the page shows a clean warning, not a crash:

> No production batches found yet under s3://.../predictions/cycle=\*/batch=\*/predictions.parquet.
> Run scripts/run_production_inference.py to generate the first batch.

## How to refresh the cache

Both the production-batch loader and View B's loaders use `@st.cache_data`. View A's cache has a
60-second TTL (`ttl=60`) and a manual **"🔄 Refresh from S3"** button on the page that clears the
cache and reruns immediately — use this after running a new `run_production_inference.py` batch if
you don't want to wait up to 60 seconds. View B's caches have no TTL (the underlying OOF/meta
parquet files don't change during a session) — restart the Streamlit process to pick up changes
there.

## Current limitations

- **No drift/data-quality rendering.** `scripts/run_drift_monitoring.py` already produces
  `outputs/monitoring/evidently_summary.json` + `.html`, but neither view renders it. A `grep` for
  `drift`/`evidently` in `apps/streamlit_dashboard/app.py` returns zero matches.
- **Bucket/region are hardcoded** in `apps/streamlit_dashboard/app.py`
  (`AWS_BUCKET`/`AWS_REGION` module-level constants), separate from the `.env`-driven
  `AWS_BUCKET_NAME`/`AWS_REGION` that `src/utils/s3_utils.py` uses. Two sources of truth — see
  [`aws_s3.md`](aws_s3.md).
- **Authentication uses boto3's default credential chain** (`boto3.client("s3",
  region_name=AWS_REGION)`, no explicit keys) rather than the `.env` `AWS_ACCESS_KEY`/
  `AWS_SECRET_KEY` pair `s3_utils.py` reads. Locally this usually works if you have `~/.aws/credentials`
  or exported `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars (note the *different* env var
  names boto3's default chain expects vs. this repo's `.env` names) — but it means `.env` alone is
  not sufficient for the dashboard the way it is for `scripts/run_production_inference.py`.
- **Not verified inside Docker** — see [`docker.md`](docker.md); the dashboard container is
  missing `boto3`/`python-dotenv` as currently built and will not start.
- View B naming cleanup (`live_df` → something like `oof_eval_df`, per-page "Offline Evaluation"
  labels) is still open — only the single top-of-page caption exists today.

## Troubleshooting common S3/dashboard failures

See [`troubleshooting.md`](troubleshooting.md) for the full table. Quick pointers:

- **`S3 Load Failed: ...` on any View B page** → credentials issue for the default boto3 chain, or
  the hardcoded bucket/region don't match where `meta_dataset.parquet`/`oof_predictions_final.parquet`
  actually live. Check `aws configure list` or your exported `AWS_ACCESS_KEY_ID`/
  `AWS_SECRET_ACCESS_KEY`/`AWS_DEFAULT_REGION`.
- **Production Monitoring page shows the empty-state warning even though you ran batches** →
  confirm you didn't use `--no-s3` when running `scripts/run_production_inference.py` (local-only
  batches never reach S3, so View A can't see them); click "🔄 Refresh from S3" in case the
  60-second cache is stale.
- **`ModuleNotFoundError: No module named 'boto3'`** → see [`local_setup.md`](local_setup.md) §1;
  `boto3` is not in `requirements.txt`/`environment.yml`, install it manually.
