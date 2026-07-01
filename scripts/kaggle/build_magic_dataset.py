"""K2 (KDR-003 SS5): build the record-adjacency magic feature dataset.

Reads the frozen, leakage-free `dataset_h` train/test feature tables (Production
artifacts, read-only -- this script never modifies them) and adds the quarantined
magic feature block from `src.kaggle.magic_features` additively. `dataset_h`'s 16
clean feature columns are reused as-is (imported from `src.features.dataset_h_pipeline`,
a Production module -- Prod -> Kaggle import is permitted, KDR-003 SS6.6).

Outputs (gitignored, `data/features/*.parquet`):
  - data/features/dataset_h_magic_train.parquet  (Id, Response, DATASET_H_FEATURE_COLS [incl. chunk_id], MAGIC_FEATURE_COLS)
  - data/features/dataset_h_magic_test.parquet   (Id, DATASET_H_FEATURE_COLS, MAGIC_FEATURE_COLS)

Reproduce: PYTHONPATH=. python scripts/kaggle/build_magic_dataset.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.features.dataset_h_pipeline import DATASET_H_FEATURE_COLS
from src.kaggle.magic_features import MAGIC_FEATURE_COLS, compute_magic_features

ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = ROOT / "data" / "features"

TRAIN_IN = FEATURES_DIR / "dataset_h.parquet"
TEST_IN = FEATURES_DIR / "test_dataset_h.parquet"
TRAIN_OUT = FEATURES_DIR / "dataset_h_magic_train.parquet"
TEST_OUT = FEATURES_DIR / "dataset_h_magic_test.parquet"


def main() -> None:
    if not TRAIN_IN.exists():
        raise FileNotFoundError(f"Missing {TRAIN_IN}. Run scripts/build_dataset_h.py first.")
    if not TEST_IN.exists():
        raise FileNotFoundError(f"Missing {TEST_IN}. Run scripts/build_test_dataset_h.py first.")

    train_df = pd.read_parquet(TRAIN_IN)
    test_df = pd.read_parquet(TEST_IN)

    print(f"train rows={len(train_df)} test rows={len(test_df)}")

    magic = compute_magic_features(train_df, test_df)
    missing_magic_cols = [c for c in MAGIC_FEATURE_COLS if c not in magic.columns]
    if missing_magic_cols:
        raise RuntimeError(f"compute_magic_features did not produce expected columns: {missing_magic_cols}")

    train_out = train_df[["Id", "Response", *DATASET_H_FEATURE_COLS]].merge(
        magic[["Id", *MAGIC_FEATURE_COLS]], on="Id", how="left", validate="one_to_one"
    )
    test_out = test_df[["Id", *DATASET_H_FEATURE_COLS]].merge(
        magic[["Id", *MAGIC_FEATURE_COLS]], on="Id", how="left", validate="one_to_one"
    )

    assert len(train_out) == len(train_df), "train row count changed during magic merge"
    assert len(test_out) == len(test_df), "test row count changed during magic merge"

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    train_out.to_parquet(TRAIN_OUT, index=False)
    test_out.to_parquet(TEST_OUT, index=False)

    print(f"wrote {TRAIN_OUT} rows={len(train_out)} cols={len(train_out.columns)}")
    print(f"wrote {TEST_OUT} rows={len(test_out)} cols={len(test_out.columns)}")
    print(f"magic_feature_cols={len(MAGIC_FEATURE_COLS)}")


if __name__ == "__main__":
    main()
