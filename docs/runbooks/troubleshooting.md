# Troubleshooting

Symptom → cause → fix, for the most common failures across this project. Cross-references point
to the runbook with full detail.

## `FileNotFoundError: data/features/test_dataset_h.parquet does not exist`

**Where:** `scripts/run_production_inference.py`, `scripts/generate_submission.py` (Track 2/3).

**Cause:** the unlabeled `dataset_h` feature contract hasn't been built yet (it's gitignored if
regenerated, though it's committed in this repo snapshot — if it's missing, something deleted or
never restored it).

**Fix:**
```bash
python scripts/build_test_dataset_h.py
```
This depends on `data/processed/test_numeric.parquet`/`test_date.parquet` and
`data/features/dataset_h_lookup.json` already existing. See
[`track2_kaggle_submission.md`](track2_kaggle_submission.md) and
[`track3_production_inference.md`](track3_production_inference.md).

## `FileNotFoundError: Model payload not found: models/dataset_h_model.pkl` (or similar)

**Where:** any script calling `load_validated_payload`/`joblib.load` on a `models/*.pkl`.

**Cause:** `models/*.pkl` files are intentionally committed (force-added past `.gitignore`) — if
missing, the checkout is incomplete, or you're on a branch/commit that predates them.

**Fix:** confirm you're on a branch with the models committed (`git log -- models/`); if you
intentionally deleted them to retrain, re-run the matching `scripts/train_*.py` (see top-level
`CLAUDE.md`). Verify with:
```bash
PYTHONPATH=. python scripts/validate_model_payload.py
```

## `ValueError: ... unexpectedly has a Response column` (Track 3 input)

**Where:** `scripts/run_production_inference.py`'s defensive guard.

**Cause:** `data/features/test_dataset_h.parquet` (or whatever `--features-path` points at) has a
`Response` column — either it was built incorrectly, or you accidentally pointed Track 3 at a
**labeled** parquet (e.g. `meta_dataset.parquet`) instead of the unlabeled test feature table.

**Fix:** rebuild with `scripts/build_test_dataset_h.py`, which never emits `Response` by
construction, and double check `--features-path` if you overrode the default. This guard is
intentional and correct behavior — do not work around it by stripping the column from a labeled
file; that would defeat the purpose of the check. See
[`track3_production_inference.md`](track3_production_inference.md) "label-free contract."

## `FileExistsError: S3 key '...' already exists`

**Where:** `src/utils/s3_utils.upload_file_append_only()`, called from
`scripts/run_production_inference.py`.

**Cause:** either (a) you're re-running with a state file that's behind where S3 actually is
(someone else advanced S3 but not your local state), or (b) a prior run uploaded successfully but
crashed before finishing local finalization.

**Fix:** read the full error message — it tells you to inspect/delete the stray S3 key or a
leftover local `.tmp` file. Full walkthrough: [`aws_s3.md`](aws_s3.md) "manual recovery notes."
In the much more common case (the upload itself just failed transiently), simply **re-running the
same command** is the fix — state was never advanced, so the retry targets the same batch
automatically.

## `FileExistsError: outputs/production/dataset_h/cycle=.../batch=.../predictions.parquet already exists`

**Where:** the **local** append-only guard in `run_one_batch()`, before any S3 interaction.

**Cause:** you're pointing at a state file whose `pointer`/`cycle_id`/`batch_id` don't match what's
already on disk at `--output-dir` — usually from mixing custom `--state-path`/`--output-dir`
combinations across test runs.

**Fix:** use matching, dedicated `--state-path`/`--output-dir`/`--stats-log-path` for any test run
that isn't meant to touch the real production state (see the "custom batch size / paths" example
in [`track3_production_inference.md`](track3_production_inference.md)). For the real production
state, this error means something is genuinely inconsistent — inspect both the state file and the
output directory before deleting anything.

## AWS credentials failure (`NoCredentialsError`, `ClientError ... 403`, `InvalidAccessKeyId`)

**Where:** any boto3 call — `src/utils/s3_utils.py` (Track 3, `run_full_system.py`) or
`apps/streamlit_dashboard/app.py` (dashboard).

**Cause and fix depend on which client:**
- **`s3_utils.py`** reads `AWS_ACCESS_KEY`/`AWS_SECRET_KEY`/`AWS_REGION`/`AWS_BUCKET_NAME` from
  `.env` via `python-dotenv`. Confirm `.env` exists, is in the working directory the script is run
  from, and has correct (non-expired, non-typo'd) values. See [`local_setup.md`](local_setup.md)
  §3.
- **`app.py` (dashboard)** uses boto3's **default credential chain** instead — it does not read
  `.env` at all. Confirm `~/.aws/credentials` is set up, or `AWS_ACCESS_KEY_ID`/
  `AWS_SECRET_ACCESS_KEY`/`AWS_DEFAULT_REGION` are exported in the shell the Streamlit process
  runs in (note: these are *different env var names* than `s3_utils.py` uses — a `.env` correctly
  set up for `s3_utils.py` will not, by itself, fix the dashboard). See
  [`aws_s3.md`](aws_s3.md)'s "required bucket / env vars" section for the full asymmetry.

## Dashboard's "Production Monitoring (Track 3)" page is empty

**Symptom:** clean warning, not a crash:
> No production batches found yet under s3://.../predictions/cycle=*/batch=*/predictions.parquet.

**Cause, in order of likelihood:**
1. You only ran `scripts/run_production_inference.py --no-s3` so far — local-only batches never
   reach S3, and this page only reads S3.
2. You ran it without `--no-s3` but credentials/bucket/region are misconfigured for the
   **dashboard's** client specifically (see the AWS-credentials entry above — this is a common
   trap because `s3_utils.py`'s `.env` setup being correct does not guarantee the dashboard's
   separate credential path is also correct).
3. The 60-second cache is stale — click **"🔄 Refresh from S3"** on the page.

**Fix:** run at least one batch without `--no-s3`, confirm it landed in S3 (`aws s3 ls` or the
boto3 snippet in [`aws_s3.md`](aws_s3.md)), fix dashboard credentials if needed, then refresh.

## Docker dashboard container missing `boto3`

**Symptom:**
```
ModuleNotFoundError: No module named 'boto3'
```
immediately on `docker-compose up` for the `dashboard` service.

**Cause:** `Dockerfile.dashboard`'s `pip install` list doesn't include `boto3` (or
`python-dotenv`), but `apps/streamlit_dashboard/app.py` imports `boto3` unconditionally.

**Fix:** this is a known, documented, **not yet fixed** gap — see [`docker.md`](docker.md) "what
must be fixed before calling Docker production-ready." There is no workaround short of editing
`Dockerfile.dashboard` and rebuilding the image.

## Streamlit `S3 Load Failed: ...` (View B pages)

**Where:** `load_scoring_data()`'s `try/except` around `load_parquet_from_s3` calls for
`meta_dataset.parquet`/`oof_predictions_final.parquet`.

**Cause:** same credential/bucket-region issue as the dashboard credentials entry above, or those
two files genuinely don't exist at the hardcoded bucket/key the dashboard expects.

**Fix:** confirm the objects exist at the expected keys (`data/features/meta_dataset.parquet`,
`data/features/oof_predictions_final.parquet`) in the bucket `app.py` hardcodes
(`AWS_BUCKET`/`AWS_REGION` constants near the top of the file), and that your active AWS
credentials (default chain, not `.env`) can read them.
