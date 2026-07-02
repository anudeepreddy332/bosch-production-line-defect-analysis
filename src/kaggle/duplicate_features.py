"""K5 (KDR-006 v2 SS4): duplicate-group / feature-identity leakage features.

Three deterministic keys per row, computed over the train+test concatenation from Production's
**raw** parquets (`data/processed/{train,test}_{date,numeric}.parquet`, read-only, never written
to):

  - `key_date`:    md5 (truncated to a 64-bit int) over the canonical bytes of the full raw
                   date-row (all 1156 date columns, fixed sorted-name order, NaN-mask bits ‖
                   NaN->0.0 float64 values). "Same batch" signature.
  - `key_numeric`: same construction over the 968 raw numeric columns (excludes `Id`/`Response`).
                   "Clone part" signature.
  - `key_nanpat`:  md5 (truncated) of the numeric NaN-mask bits alone, no values. Route/path proxy
                   -- falls out of the numeric pass at zero marginal cost.

**Hard rule: no raw date or numeric value ever leaves this module as a feature.** Only the three
int64 keys and features derived from them (group size/position, cross-key agreement, and
`key_date`-only Id-chains) are exposed. This is what keeps K5 a duplicate/identity probe rather
than deep raw-numeric modeling (explicitly out of scope, KDR-006 SS4a).

Two column sets, mirroring K3's clean label-free/label-touching split:

  - `DUPLICATE_FEATURE_COLS` (17, Variant A): group size/rank/rank_frac/is_dup per key (12),
    `dup_key_agreement` (1), `key_date`-only Id-chain same/len/pos (4). Label-free by construction
    -- no `Response` reference anywhere in this block. Honest OOF.
  - `DUPLICATE_LABEL_COLS` (8, Variant B): per-key leave-one-out train-fail count/fraction (6),
    `key_date`-chain neighbor `Response` (2). Label-touching -- contaminated OOF by construction
    (same chunk-aware-CV blind spot as K2's `train_resp_*` / K3-B), flagged, LB-only.

Reproduce the key-hashing pass (slow step, ~1-2 min per raw file):
  PYTHONPATH=. python scripts/kaggle/build_duplicate_dataset.py
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

_KEY_NAMES: tuple[str, ...] = ("date", "numeric", "nanpat")
_GROUP_STAT_SUFFIXES: tuple[str, ...] = ("group_size", "group_rank", "group_rank_frac", "is_dup")
_BATCH_SIZE = 20_000

DUPLICATE_FEATURE_COLS: list[str] = (
    [f"dup_{k}_{s}" for k in _KEY_NAMES for s in _GROUP_STAT_SUFFIXES]
    + ["dup_key_agreement"]
    + ["dup_chain_same_prev", "dup_chain_same_next", "dup_chain_len", "dup_chain_pos"]
)
assert len(DUPLICATE_FEATURE_COLS) == 17

DUPLICATE_LABEL_COLS: list[str] = (
    [f"dup_{k}_train_fail_cnt_loo" for k in _KEY_NAMES]
    + [f"dup_{k}_train_frac_loo" for k in _KEY_NAMES]
    + ["dup_chain_resp_prev", "dup_chain_resp_next"]
)
assert len(DUPLICATE_LABEL_COLS) == 8


def _md5_int64(*byte_chunks: bytes) -> int:
    h = hashlib.md5()
    for chunk in byte_chunks:
        h.update(chunk)
    return int(np.frombuffer(h.digest()[:8], dtype="<i8")[0])


def _canonical_mask_and_values(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """NaN-mask bits (packed) and NaN->0.0 float64 values, per row -- the shared canonicalization
    used by every key in this module (KDR-006 v2 SS4: hashes-and-masks-only, sorted column order)."""
    mask = np.isnan(arr)
    vals = np.where(mask, 0.0, arr)
    mask_bytes = np.packbits(mask, axis=1)
    return mask_bytes, vals


def _hash_date_rows(path: Path) -> pd.DataFrame:
    pf = pq.ParquetFile(path)
    cols = sorted(c for c in pf.schema_arrow.names if c != "Id")
    ids_out: list[np.ndarray] = []
    keys_out: list[np.ndarray] = []
    for batch in pf.iter_batches(batch_size=_BATCH_SIZE, columns=["Id", *cols]):
        pdf = batch.to_pandas()
        ids = pdf["Id"].to_numpy(dtype=np.int64)
        arr = pdf[cols].to_numpy(dtype=np.float64)
        mask_bytes, vals = _canonical_mask_and_values(arr)
        n = arr.shape[0]
        keys = np.empty(n, dtype=np.int64)
        for i in range(n):
            keys[i] = _md5_int64(mask_bytes[i].tobytes(), vals[i].tobytes())
        ids_out.append(ids)
        keys_out.append(keys)
    return pd.DataFrame({"Id": np.concatenate(ids_out), "key_date": np.concatenate(keys_out)})


def _hash_numeric_rows(path: Path) -> pd.DataFrame:
    pf = pq.ParquetFile(path)
    cols = sorted(c for c in pf.schema_arrow.names if c not in ("Id", "Response"))
    ids_out: list[np.ndarray] = []
    key_num_out: list[np.ndarray] = []
    key_nan_out: list[np.ndarray] = []
    for batch in pf.iter_batches(batch_size=_BATCH_SIZE, columns=["Id", *cols]):
        pdf = batch.to_pandas()
        ids = pdf["Id"].to_numpy(dtype=np.int64)
        arr = pdf[cols].to_numpy(dtype=np.float64)
        mask_bytes, vals = _canonical_mask_and_values(arr)
        n = arr.shape[0]
        key_num = np.empty(n, dtype=np.int64)
        key_nan = np.empty(n, dtype=np.int64)
        for i in range(n):
            mb = mask_bytes[i].tobytes()
            key_num[i] = _md5_int64(mb, vals[i].tobytes())
            key_nan[i] = _md5_int64(mb)
        ids_out.append(ids)
        key_num_out.append(key_num)
        key_nan_out.append(key_nan)
    return pd.DataFrame(
        {
            "Id": np.concatenate(ids_out),
            "key_numeric": np.concatenate(key_num_out),
            "key_nanpat": np.concatenate(key_nan_out),
        }
    )


def compute_duplicate_keys(
    train_date_path: Path,
    test_date_path: Path,
    train_numeric_path: Path,
    test_numeric_path: Path,
) -> pd.DataFrame:
    """Stream-hash the four raw parquets (read-only) into `key_date`/`key_numeric`/`key_nanpat`.

    Returns Id + the three int64 keys, covering every Id in train+test, in the train-then-test
    concatenation order (train sorted by Id, then test sorted by Id -- same convention as
    `magic_features._concat_train_test`).
    """
    train_date_keys = _hash_date_rows(train_date_path)
    test_date_keys = _hash_date_rows(test_date_path)
    train_num_keys = _hash_numeric_rows(train_numeric_path)
    test_num_keys = _hash_numeric_rows(test_numeric_path)

    train_keys = train_date_keys.merge(train_num_keys, on="Id", validate="one_to_one")
    test_keys = test_date_keys.merge(test_num_keys, on="Id", validate="one_to_one")

    train_keys = train_keys.sort_values("Id", kind="mergesort").reset_index(drop=True)
    test_keys = test_keys.sort_values("Id", kind="mergesort").reset_index(drop=True)

    return pd.concat([train_keys, test_keys], ignore_index=True, sort=False)


def _group_stats(key: np.ndarray, ids: np.ndarray, prefix: str) -> dict[str, np.ndarray]:
    df = pd.DataFrame({"key": key, "Id": ids})
    group_size = df.groupby("key")["Id"].transform("size").to_numpy(dtype=np.int64)
    group_rank = df.groupby("key")["Id"].rank(method="first").to_numpy(dtype=np.int64)
    group_rank_frac = group_rank / group_size
    is_dup = (group_size >= 2).astype(np.int64)
    return {
        f"dup_{prefix}_group_size": group_size,
        f"dup_{prefix}_group_rank": group_rank,
        f"dup_{prefix}_group_rank_frac": group_rank_frac,
        f"dup_{prefix}_is_dup": is_dup,
    }


def _chain_features(key_date_sorted: np.ndarray) -> dict[str, np.ndarray]:
    """Id-adjacency chain structure on `key_date` only (KDR-006 v2 SS4 -- numeric chains excluded
    as creep). `key_date_sorted` must already be in the combined Id-ascending order."""
    n = len(key_date_sorted)
    same_prev = np.zeros(n, dtype=np.int8)
    same_next = np.zeros(n, dtype=np.int8)
    if n > 1:
        eq = (key_date_sorted[1:] == key_date_sorted[:-1]).astype(np.int8)
        same_prev[1:] = eq
        same_next[:-1] = eq

    is_new_run = np.empty(n, dtype=bool)
    is_new_run[0] = True
    if n > 1:
        is_new_run[1:] = key_date_sorted[1:] != key_date_sorted[:-1]
    run_id = np.cumsum(is_new_run) - 1
    run_counts = np.bincount(run_id)
    chain_len = run_counts[run_id]
    run_start = np.zeros(len(run_counts), dtype=np.int64)
    if len(run_counts) > 1:
        run_start[1:] = np.cumsum(run_counts)[:-1]
    chain_pos = np.arange(n) - run_start[run_id] + 1

    return {
        "dup_chain_same_prev": same_prev,
        "dup_chain_same_next": same_next,
        "dup_chain_len": chain_len.astype(np.int64),
        "dup_chain_pos": chain_pos.astype(np.int64),
    }


def _chain_response(
    key_date_sorted: np.ndarray, is_train_sorted: np.ndarray, response_sorted: np.ndarray
) -> dict[str, np.ndarray]:
    n = len(key_date_sorted)
    resp_prev = np.full(n, np.nan)
    resp_next = np.full(n, np.nan)
    if n > 1:
        same = key_date_sorted[1:] == key_date_sorted[:-1]
        prev_is_train = is_train_sorted[:-1] & same
        next_is_train = is_train_sorted[1:] & same
        resp_prev[1:] = np.where(prev_is_train, response_sorted[:-1], np.nan)
        resp_next[:-1] = np.where(next_is_train, response_sorted[1:], np.nan)
    return {"dup_chain_resp_prev": resp_prev, "dup_chain_resp_next": resp_next}


def _train_fail_loo(
    key: np.ndarray, is_train: np.ndarray, response: np.ndarray, prefix: str
) -> dict[str, np.ndarray]:
    """Leave-one-out train-fail count/fraction within each key's group: a train row excludes
    itself; a test row uses every train member in its group. NaN when no other train member
    exists in the group (KDR-006 v2 SS4)."""
    train_response = np.where(is_train, response, 0.0)
    train_flag = is_train.astype(np.float64)
    df = pd.DataFrame({"key": key, "train_response": train_response, "train_flag": train_flag})
    group_fail_sum = df.groupby("key")["train_response"].transform("sum").to_numpy()
    group_train_count = df.groupby("key")["train_flag"].transform("sum").to_numpy()

    loo_cnt = np.where(is_train, group_fail_sum - response, group_fail_sum)
    loo_train_count = np.where(is_train, group_train_count - 1, group_train_count)

    with np.errstate(invalid="ignore", divide="ignore"):
        loo_frac = np.where(loo_train_count > 0, loo_cnt / loo_train_count, np.nan)
    loo_cnt = np.where(loo_train_count > 0, loo_cnt, np.nan)

    return {
        f"dup_{prefix}_train_fail_cnt_loo": loo_cnt,
        f"dup_{prefix}_train_frac_loo": loo_frac,
    }


def compute_duplicate_features(keys_df: pd.DataFrame, is_train: np.ndarray, response: np.ndarray) -> pd.DataFrame:
    """Build the 25 duplicate/identity feature columns (`DUPLICATE_FEATURE_COLS` +
    `DUPLICATE_LABEL_COLS`) from `keys_df` (Id + the three int64 keys, from
    `compute_duplicate_keys`, in its train-then-test concatenation order).

    `is_train`/`response` must be aligned with `keys_df`'s row order: `response` is the row's
    `Response` for train rows (0/1) and is unused (any float) for test rows.
    """
    ids = keys_df["Id"].to_numpy(dtype=np.int64)

    group_blocks: dict[str, np.ndarray] = {}
    for prefix, col in (("date", "key_date"), ("numeric", "key_numeric"), ("nanpat", "key_nanpat")):
        group_blocks.update(_group_stats(keys_df[col].to_numpy(), ids, prefix))

    dup_key_agreement = (
        group_blocks["dup_date_is_dup"] + group_blocks["dup_numeric_is_dup"] + group_blocks["dup_nanpat_is_dup"]
    )

    label_blocks: dict[str, np.ndarray] = {}
    for prefix, col in (("date", "key_date"), ("numeric", "key_numeric"), ("nanpat", "key_nanpat")):
        label_blocks.update(_train_fail_loo(keys_df[col].to_numpy(), is_train, response, prefix))

    # Chain features need the *global* Id-ascending order (magic_features' "adj_id" order),
    # distinct from keys_df's train-then-test concatenation order.
    order = np.argsort(ids, kind="mergesort")
    inverse_order = np.empty_like(order)
    inverse_order[order] = np.arange(len(order))

    key_date_sorted = keys_df["key_date"].to_numpy()[order]
    is_train_sorted = is_train[order]
    response_sorted = response[order]

    chain_feats_sorted = _chain_features(key_date_sorted)
    chain_resp_sorted = _chain_response(key_date_sorted, is_train_sorted, response_sorted)

    chain_feats = {name: values[inverse_order] for name, values in chain_feats_sorted.items()}
    chain_resp = {name: values[inverse_order] for name, values in chain_resp_sorted.items()}

    out = pd.DataFrame(
        {
            "Id": ids,
            **group_blocks,
            "dup_key_agreement": dup_key_agreement,
            **chain_feats,
            **label_blocks,
            **chain_resp,
        }
    )
    return out


def check_degenerate_groups(keys_df: pd.DataFrame) -> dict[str, float]:
    """KDR-006 v2 SS5 guard 2: largest `key_date`/`key_numeric` group must be <=1% of all rows;
    `key_nanpat` must show >=50 distinct groups. Returns a report dict; raises if violated."""
    n_total = len(keys_df)
    report: dict[str, float] = {}

    for prefix, col in (("date", "key_date"), ("numeric", "key_numeric")):
        sizes = keys_df[col].value_counts()
        top_share = float(sizes.iloc[0]) / n_total
        report[f"{prefix}_top_group_share"] = top_share
        report[f"{prefix}_n_distinct_groups"] = float(len(sizes))
        if top_share > 0.01:
            raise RuntimeError(
                f"Degenerate grouping guard failed for key_{prefix}: top group is "
                f"{top_share:.4%} of all rows (limit 1%) -- likely a hashing/canonicalization bug."
            )

    nanpat_sizes = keys_df["key_nanpat"].value_counts()
    nanpat_n_groups = len(nanpat_sizes)
    nanpat_top_share = float(nanpat_sizes.iloc[0]) / n_total
    report["nanpat_n_distinct_groups"] = float(nanpat_n_groups)
    report["nanpat_top_group_share"] = nanpat_top_share
    if nanpat_n_groups < 50:
        raise RuntimeError(
            f"Degenerate grouping guard failed for key_nanpat: only {nanpat_n_groups} distinct "
            f"groups (limit >=50) -- likely a hashing bug."
        )

    return report


def extract_canonical_bytes(path: Path, id_col_values: set[int], mode: str) -> dict[int, bytes]:
    """KDR-006 v2 SS5 guard 3 helper: re-stream `path` and retain the canonical
    (mask-bytes || value-bytes) for a small target set of Ids, for a collision sanity check.
    `mode` is "date" (all non-Id cols) or "numeric" (all cols except Id/Response)."""
    pf = pq.ParquetFile(path)
    if mode == "date":
        cols = sorted(c for c in pf.schema_arrow.names if c != "Id")
    elif mode == "numeric":
        cols = sorted(c for c in pf.schema_arrow.names if c not in ("Id", "Response"))
    else:
        raise ValueError(f"unknown mode {mode!r}")

    found: dict[int, bytes] = {}
    remaining = set(id_col_values)
    for batch in pf.iter_batches(batch_size=_BATCH_SIZE, columns=["Id", *cols]):
        if not remaining:
            break
        pdf = batch.to_pandas()
        ids = pdf["Id"].to_numpy(dtype=np.int64)
        hit_mask = np.isin(ids, list(remaining))
        if not hit_mask.any():
            continue
        arr = pdf[cols].to_numpy(dtype=np.float64)
        mask_bytes, vals = _canonical_mask_and_values(arr)
        for i in np.nonzero(hit_mask)[0]:
            row_id = int(ids[i])
            found[row_id] = mask_bytes[i].tobytes() + vals[i].tobytes()
            remaining.discard(row_id)
    return found
