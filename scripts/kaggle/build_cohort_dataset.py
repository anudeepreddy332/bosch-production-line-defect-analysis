"""K4 (KDR-005 SS4): build the label-free timing-cohort feature dataset.

Reads the already-built K2 magic dataset (`data/features/dataset_h_magic_{train,test}.parquet`,
unchanged -- built by `scripts/kaggle/build_magic_dataset.py`) and adds the new quarantined
cohort feature block from `src.kaggle.cohort_features` additively. No date-matrix reread, no
`train_resp_*`/`Response` lookup anywhere in the new block.

Outputs (gitignored, `data/features/*.parquet`):
  - data/features/dataset_h_cohort_train.parquet  (Id, Response, DATASET_H_FEATURE_COLS, POSITION_ONLY_MAGIC_COLS, COHORT_FEATURE_COLS)
  - data/features/dataset_h_cohort_test.parquet   (Id, DATASET_H_FEATURE_COLS, POSITION_ONLY_MAGIC_COLS, COHORT_FEATURE_COLS)

Reproduce: PYTHONPATH=. python scripts/kaggle/build_cohort_dataset.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.features.dataset_h_pipeline import DATASET_H_FEATURE_COLS
from src.kaggle.cohort_features import COHORT_FEATURE_COLS, compute_cohort_features
from src.kaggle.magic_features import POSITION_ONLY_MAGIC_COLS

ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = ROOT / "data" / "features"

TRAIN_IN = FEATURES_DIR / "dataset_h_magic_train.parquet"
TEST_IN = FEATURES_DIR / "dataset_h_magic_test.parquet"
TRAIN_OUT = FEATURES_DIR / "dataset_h_cohort_train.parquet"
TEST_OUT = FEATURES_DIR / "dataset_h_cohort_test.parquet"

KEEP_COLS = [*DATASET_H_FEATURE_COLS, *POSITION_ONLY_MAGIC_COLS]


def main() -> None:
    if not TRAIN_IN.exists():
        raise FileNotFoundError(f"Missing {TRAIN_IN}. Run scripts/kaggle/build_magic_dataset.py first.")
    if not TEST_IN.exists():
        raise FileNotFoundError(f"Missing {TEST_IN}. Run scripts/kaggle/build_magic_dataset.py first.")

    train_df = pd.read_parquet(TRAIN_IN)
    test_df = pd.read_parquet(TEST_IN)

    print(f"train rows={len(train_df)} test rows={len(test_df)}")

    cohort = compute_cohort_features(train_df, test_df)
    missing_cohort_cols = [c for c in COHORT_FEATURE_COLS if c not in cohort.columns]
    if missing_cohort_cols:
        raise RuntimeError(f"compute_cohort_features did not produce expected columns: {missing_cohort_cols}")

    train_out = train_df[["Id", "Response", *KEEP_COLS]].merge(
        cohort[["Id", *COHORT_FEATURE_COLS]], on="Id", how="left", validate="one_to_one"
    )
    test_out = test_df[["Id", *KEEP_COLS]].merge(
        cohort[["Id", *COHORT_FEATURE_COLS]], on="Id", how="left", validate="one_to_one"
    )

    assert len(train_out) == len(train_df), "train row count changed during cohort merge"
    assert len(test_out) == len(test_df), "test row count changed during cohort merge"

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    train_out.to_parquet(TRAIN_OUT, index=False)
    test_out.to_parquet(TEST_OUT, index=False)

    print(f"wrote {TRAIN_OUT} rows={len(train_out)} cols={len(train_out.columns)}")
    print(f"wrote {TEST_OUT} rows={len(test_out)} cols={len(test_out.columns)}")
    print(f"cohort_feature_cols={len(COHORT_FEATURE_COLS)}")


if __name__ == "__main__":
    main()
