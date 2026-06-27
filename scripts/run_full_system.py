from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str]) -> bool:
    print(f"[START] {name}")
    try:
        result = subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        print(f"[OK] {name}")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[FAIL] {name}")
        if exc.stdout:
            print(exc.stdout)
        if exc.stderr:
            print(exc.stderr)
        return False


if __name__ == "__main__":
    steps = [
        ("Build Decision System", [sys.executable, "scripts/build_decision_summary.py"]),
        # Track 3, label-free: scores data/features/test_dataset_h.parquet (must already
        # exist -- build via scripts/build_test_dataset_h.py -- this pipeline does not
        # regenerate it, same as it does not regenerate meta_dataset.parquet for the step
        # below). Replaces the old labeled Track 1 replay here; that script
        # (scripts/run_offline_batch_eval.py) is still available standalone for offline
        # evaluation, it's just no longer part of the "production" stage.
        ("Run Production Inference (Track 3, label-free)", [sys.executable, "scripts/run_production_inference.py"]),
        ("Run Drift Monitoring", [sys.executable, "scripts/run_drift_monitoring.py"]),
    ]

    failed = []
    for name, cmd in steps:
        if not run_step(name, cmd):
            failed.append(name)

    print("=" * 72)
    if failed:
        print("System run completed with failures:")
        for name in failed:
            print(f" - {name}")
        sys.exit(1)

    print("System run completed successfully.")
    print("Generated outputs:")
    print(" - outputs/production_decision_summary.json")
    print(" - outputs/production/dataset_h/cycle={n}/batch={n}/predictions.parquet (this run's batch)")
    print(" - outputs/production/dataset_h/dataset_h_batch_stats_log.csv")
    print(" - outputs/monitoring/evidently_summary.json")

from src.utils.s3_utils import upload_file

print("\n[START] Uploading to S3")

upload_file("outputs/production_decision_summary.json", "outputs/production_decision_summary.json")
upload_file("outputs/monitoring/evidently_summary.json", "outputs/monitoring/evidently_summary.json")
# NOTE: Track 3's per-batch outputs (outputs/production/dataset_h/cycle=*/batch=*/
# predictions.parquet) are intentionally NOT uploaded here yet -- they are append-only,
# partitioned, per-batch files (one new path per run), not a single static file this
# loop's hardcoded upload_file() calls can target. Wiring S3 upload for them (mirroring
# the local cycle={n}/batch={n} partition into the S3 key, per tasks.md TASK 4) is a
# separate follow-up, not done in this change.

print("[OK] Upload to S3 complete")
