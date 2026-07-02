"""K5 (KDR-006 v2 SS4): build the duplicate-group / feature-identity dataset.

Reads Production's raw `{train,test}_{date,numeric}.parquet` **read-only** (never written to) to
hash each row into `key_date`/`key_numeric`/`key_nanpat` (`src.kaggle.duplicate_features`), runs
the KDR-006 v2 SS5 process guards (degenerate-grouping cap, hash-collision sanity check), then
additively merges the 25 duplicate/identity feature columns onto K3-A's winning feature set
(`DATASET_H_FEATURE_COLS` + `POSITION_ONLY_MAGIC_COLS`, read from the already-built
`dataset_h_magic_{train,test}.parquet`).

Outputs (gitignored, `data/features/*.parquet`):
  - data/features/dataset_h_dup_train.parquet  (Id, Response, DATASET_H_FEATURE_COLS, POSITION_ONLY_MAGIC_COLS, DUPLICATE_FEATURE_COLS, DUPLICATE_LABEL_COLS)
  - data/features/dataset_h_dup_test.parquet   (Id, DATASET_H_FEATURE_COLS, POSITION_ONLY_MAGIC_COLS, DUPLICATE_FEATURE_COLS, DUPLICATE_LABEL_COLS)

Reproduce (slow step, ~1-2 min for the raw-parquet hashing pass):
  PYTHONPATH=. python scripts/kaggle/build_duplicate_dataset.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.features.dataset_h_pipeline import DATASET_H_FEATURE_COLS
from src.kaggle.duplicate_features import (
    DUPLICATE_FEATURE_COLS,
    DUPLICATE_LABEL_COLS,
    check_degenerate_groups,
    compute_duplicate_features,
    compute_duplicate_keys,
    extract_canonical_bytes,
)
from src.kaggle.magic_features import POSITION_ONLY_MAGIC_COLS

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT / "data" / "processed"
FEATURES_DIR = ROOT / "data" / "features"

TRAIN_DATE_RAW = PROCESSED_DIR / "train_date.parquet"
TEST_DATE_RAW = PROCESSED_DIR / "test_date.parquet"
TRAIN_NUMERIC_RAW = PROCESSED_DIR / "train_numeric.parquet"
TEST_NUMERIC_RAW = PROCESSED_DIR / "test_numeric.parquet"

TRAIN_BASE_IN = FEATURES_DIR / "dataset_h_magic_train.parquet"
TEST_BASE_IN = FEATURES_DIR / "dataset_h_magic_test.parquet"
TRAIN_OUT = FEATURES_DIR / "dataset_h_dup_train.parquet"
TEST_OUT = FEATURES_DIR / "dataset_h_dup_test.parquet"

KEEP_COLS = [*DATASET_H_FEATURE_COLS, *POSITION_ONLY_MAGIC_COLS]

_COLLISION_SAMPLE_GROUPS = 5


def _run_collision_guard(keys_df: pd.DataFrame, n_train: int) -> None:
    """KDR-006 v2 SS5 guard 3: for the largest few key_date/key_numeric groups, re-read the
    canonical bytes of two members directly from the raw parquet and verify they are byte-equal
    (guards against a hash-construction bug silently merging non-duplicate rows)."""
    train_ids = set(keys_df["Id"].to_numpy()[:n_train].tolist())

    for prefix, col, mode in (("date", "key_date", "date"), ("numeric", "key_numeric", "numeric")):
        sizes = keys_df[col].value_counts()
        dup_keys = sizes[sizes >= 2].sort_values(ascending=False)
        if len(dup_keys) == 0:
            print(f"collision guard key_{prefix}: no duplicate groups found, nothing to verify")
            continue
        checked = 0
        for key_val in dup_keys.index[:_COLLISION_SAMPLE_GROUPS]:
            members = keys_df.loc[keys_df[col] == key_val, "Id"].to_numpy()[:2]
            a, b = int(members[0]), int(members[1])
            targets_train = {i for i in (a, b) if i in train_ids}
            targets_test = {i for i in (a, b) if i not in train_ids}
            found: dict[int, bytes] = {}
            if targets_train:
                path = TRAIN_DATE_RAW if mode == "date" else TRAIN_NUMERIC_RAW
                found.update(extract_canonical_bytes(path, targets_train, mode))
            if targets_test:
                path = TEST_DATE_RAW if mode == "date" else TEST_NUMERIC_RAW
                found.update(extract_canonical_bytes(path, targets_test, mode))
            if found.get(a) != found.get(b):
                raise RuntimeError(
                    f"Collision sanity guard failed for key_{prefix}: Ids {a} and {b} share a "
                    f"hash but their canonical bytes differ -- true hash collision or bug."
                )
            checked += 1
        print(f"collision guard key_{prefix}: verified {checked} group(s) byte-equal (top {len(dup_keys)} sizes: "
              f"{dup_keys.head(_COLLISION_SAMPLE_GROUPS).tolist()})")


def main() -> None:
    for p in (TRAIN_DATE_RAW, TEST_DATE_RAW, TRAIN_NUMERIC_RAW, TEST_NUMERIC_RAW, TRAIN_BASE_IN, TEST_BASE_IN):
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}.")

    train_base = pd.read_parquet(TRAIN_BASE_IN)
    test_base = pd.read_parquet(TEST_BASE_IN)
    print(f"train rows={len(train_base)} test rows={len(test_base)}")

    print("hashing raw date/numeric matrices (read-only) ...")
    keys_df = compute_duplicate_keys(TRAIN_DATE_RAW, TEST_DATE_RAW, TRAIN_NUMERIC_RAW, TEST_NUMERIC_RAW)
    assert len(keys_df) == len(train_base) + len(test_base), "key row count mismatch"

    print("checking degenerate-grouping guard (KDR-006 v2 SS5 guard 2) ...")
    report = check_degenerate_groups(keys_df)
    for k, v in report.items():
        print(f"  {k}: {v}")

    print("checking hash-collision sanity guard (KDR-006 v2 SS5 guard 3) ...")
    _run_collision_guard(keys_df, n_train=len(train_base))

    is_train = np.concatenate([np.ones(len(train_base), dtype=bool), np.zeros(len(test_base), dtype=bool)])
    response_map = train_base.set_index("Id")["Response"]
    response = keys_df["Id"].map(response_map).fillna(0.0).to_numpy(dtype=np.float64)

    print("computing duplicate features ...")
    dup = compute_duplicate_features(keys_df, is_train, response)
    missing = [c for c in [*DUPLICATE_FEATURE_COLS, *DUPLICATE_LABEL_COLS] if c not in dup.columns]
    if missing:
        raise RuntimeError(f"compute_duplicate_features did not produce expected columns: {missing}")

    train_out = train_base[["Id", "Response", *KEEP_COLS]].merge(
        dup[["Id", *DUPLICATE_FEATURE_COLS, *DUPLICATE_LABEL_COLS]], on="Id", how="left", validate="one_to_one"
    )
    test_out = test_base[["Id", *KEEP_COLS]].merge(
        dup[["Id", *DUPLICATE_FEATURE_COLS, *DUPLICATE_LABEL_COLS]], on="Id", how="left", validate="one_to_one"
    )

    assert len(train_out) == len(train_base), "train row count changed during dup merge"
    assert len(test_out) == len(test_base), "test row count changed during dup merge"

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    train_out.to_parquet(TRAIN_OUT, index=False)
    test_out.to_parquet(TEST_OUT, index=False)

    print(f"wrote {TRAIN_OUT} rows={len(train_out)} cols={len(train_out.columns)}")
    print(f"wrote {TEST_OUT} rows={len(test_out)} cols={len(test_out.columns)}")
    print(f"duplicate_feature_cols={len(DUPLICATE_FEATURE_COLS)} duplicate_label_cols={len(DUPLICATE_LABEL_COLS)}")


if __name__ == "__main__":
    main()
