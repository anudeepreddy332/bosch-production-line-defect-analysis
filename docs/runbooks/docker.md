# Docker

## Current files and services

| File | Builds | Exposes | Installs (pip, inside the image) |
|---|---|---|---|
| `Dockerfile.api` | `bosch_api` container | `8000` | `fastapi`, `uvicorn[standard]`, `pandas`, `numpy`, `pyarrow`, `pydantic` |
| `Dockerfile.dashboard` | `bosch_dashboard` container | `8501` | `streamlit`, `plotly`, `pandas`, `numpy`, `pyarrow` |
| `docker-compose.yml` | both, with `dashboard` depending on `api` | `8000`, `8501` | — |

Both containers mount the full repo (`./:/app`) plus `./data` and `./outputs` as volumes, and set
`PYTHONPATH=/app` / `BOSCH_PROJECT_ROOT=/app`.

## How to build/run with docker compose today

```bash
docker-compose up --build
```

This **will start the API container successfully** — `apps/api/main.py` has no S3/boto3
dependency; it only reads `outputs/max_recall_system_summary.json` (or falls back to defaults)
and serves `/health`, `/predict`, `/batch_predict`.

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

## Known current gaps — read before relying on the dashboard container

**This was not verified to work, and based on reading the Dockerfile and `app.py`, it should not
currently work.** Do not claim otherwise.

1. **`Dockerfile.dashboard` does not install `boto3` or `python-dotenv`**, but
   `apps/streamlit_dashboard/app.py` does `import boto3` unconditionally at module load (line 10).
   Every page in the dashboard — both View A and View B — needs S3 access, so this import runs
   before any page-specific code does. Expected failure on container start:
   ```
   ModuleNotFoundError: No module named 'boto3'
   ```
2. **`docker-compose.yml` passes no AWS credentials or region into either container.** Even after
   fixing (1), `apps/streamlit_dashboard/app.py` authenticates via boto3's default credential
   chain (`boto3.client("s3", region_name=AWS_REGION)` with no explicit keys) — inside a
   container with no `~/.aws/credentials` mounted and no `AWS_ACCESS_KEY_ID`/
   `AWS_SECRET_ACCESS_KEY`/`AWS_DEFAULT_REGION` environment variables set, this will fail with a
   `NoCredentialsError` or similar at the first S3 call.
3. **The repo's own `.env` (read by `src/utils/s3_utils.py`) is not consumed by the dashboard
   container's S3 client.** Even though `./:/app` is mounted (so `.env` is visible on disk inside
   the container), `app.py` never calls `load_dotenv()` — it isn't wired to read it. Mounting the
   repo is not sufficient by itself.
4. **Bucket/region are hardcoded in `app.py`**, not parameterized via Docker build args or env
   vars at all — see [`aws_s3.md`](aws_s3.md).

Net effect: as currently built, `docker-compose up` for the `dashboard` service is expected to
crash immediately on the `import boto3` line, before it gets far enough to hit gaps (2)-(4). Those
are listed because they'll surface next, in order, once (1) is fixed.

## What must be fixed before calling Docker production-ready

In order:

1. Add `boto3` and `python-dotenv` to `Dockerfile.dashboard`'s pip install list (matching what
   `requirements.txt`/`environment.yml` are also missing — see
   [`local_setup.md`](local_setup.md) §1; this is the same root gap, just also needs fixing
   inside the image separately since Dockerfiles don't read `requirements.txt` today).
2. Decide on one credential mechanism for the dashboard container and wire it into
   `docker-compose.yml`: either
   - pass `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_DEFAULT_REGION` as environment
     variables in the `dashboard` service's `environment:` block (mirroring what's already done
     for `PYTHONPATH`/`BOSCH_PROJECT_ROOT`), or
   - mount `~/.aws:/root/.aws:ro` as a volume, or
   - (for an EC2 deployment specifically) rely on an IAM instance role and add no credentials at
     all — see [`ec2_deployment.md`](ec2_deployment.md) and [`aws_s3.md`](aws_s3.md) for why this
     is the preferred option outside local dev.
3. Either make `app.py` call `load_dotenv()` and read the same `AWS_BUCKET_NAME`/`AWS_REGION`
   names `src/utils/s3_utils.py` already uses, or accept that the dashboard intentionally uses a
   different mechanism and document the bucket/region as build args / compose environment
   variables instead of hardcoded constants. Either fix consolidates the two-sources-of-truth
   problem flagged in [`aws_s3.md`](aws_s3.md); this runbook does not prescribe which.
4. Re-verify by actually running `docker-compose up --build` and opening
   `http://localhost:8501` after each fix, not just by reading the Dockerfile.

This runbook intentionally does not implement these fixes — per this project's pattern of small,
scoped changes, that's separate follow-up work, not a documentation task.
