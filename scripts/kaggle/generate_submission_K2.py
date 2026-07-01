"""K2 (KDR-003 SS5/SS6.6): generate outputs/kaggle/submission_K2.csv.

Imports the generic, reusable helpers from `scripts/generate_submission.py`
(payload validation, test-feature loading, ensembled predict_proba, sample-
submission cross-check) rather than duplicating them. Production -> Kaggle
import is permitted (KDR-003 SS6.6); this script never edits
`scripts/generate_submission.py`.

Reproduce:
  PYTHONPATH=. python scripts/kaggle/generate_submission_K2.py \\
    --model-path outputs/kaggle/models/k2_magic_model.pkl \\
    --test-features data/features/dataset_h_magic_test.parquet \\
    --output outputs/kaggle/submission_K2.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.generate_submission import (
    check_against_sample_submission,
    load_test_features,
    load_validated_payload,
    predict_proba_ensemble,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT / "outputs" / "kaggle" / "models" / "k2_magic_model.pkl"
DEFAULT_TEST_FEATURES = ROOT / "data" / "features" / "dataset_h_magic_test.parquet"
DEFAULT_OUTPUT = ROOT / "outputs" / "kaggle" / "submission_K2.csv"
DEFAULT_SAMPLE_SUBMISSION = ROOT / "data" / "processed" / "sample_submission.parquet"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the K2 magic-leakage Kaggle submission (KDR-003).")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--test-features", type=Path, default=DEFAULT_TEST_FEATURES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--id-col", default="Id")
    parser.add_argument("--sample-submission", type=Path, default=DEFAULT_SAMPLE_SUBMISSION)
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override the payload's stored decision threshold (default: use payload['threshold']).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        payload = load_validated_payload(args.model_path)
        threshold = args.threshold if args.threshold is not None else float(payload["threshold"])

        features = load_test_features(args.test_features, payload["feature_cols"], args.id_col)
        proba = predict_proba_ensemble(payload, features)
        response = (proba >= float(threshold)).astype(np.int8)

        submission = pd.DataFrame(
            {
                "Id": features[args.id_col].to_numpy(dtype=np.int64),
                "Response": response,
            }
        )

        check_against_sample_submission(submission["Id"], args.sample_submission)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        submission.to_csv(args.output, index=False)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"model_name={payload.get('model_name')!r}")
    print(f"threshold_used={float(threshold)}")
    print(f"output_path={args.output}")
    print(f"row_count={len(submission)}")
    print(f"positive_prediction_count={int(response.sum())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
