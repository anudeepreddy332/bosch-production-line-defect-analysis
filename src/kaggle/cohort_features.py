"""K4 (KDR-005 SS4): label-free timing-cohort geometry features.

Extends the record-order-proximity family K2/K3 already established, using only the
`start_time` (min date) and `max_date` (= `start_time + duration`) columns already
present in `data/features/dataset_h_magic_{train,test}.parquet` (built at K2). No
per-station `train_date.parquet` reread, no `Response`/`train_resp_*` lookup anywhere
in this module -- every feature here is label-free by construction.

Two kinds of features, computed over the train+test concatenation (same total-order
conventions as `magic_features.py`: deterministic sort via `mergesort`, `+inf` sentinel
for NaN `start_time`/`max_date` placement, `Id` tie-break):

  - **Cohort size/position** (`mindate_*`, `maxdate_*` prefixes): rows sharing the exact
    same rounded timestamp (0.01 precision, the data's native granularity) form a
    "cohort" -- how many rows share it, and this row's rank within that cohort.
    Rows with a NaN timestamp (~0.05% of rows) are given a deterministic singleton
    cohort of their own (`cohort_size=1`) rather than being grouped together, since
    grouping them would assert a false adjacency that doesn't exist in the raw data.
  - **Max-date order adjacency + extended min-date lag**: `magic_features.py` covers
    the `Id`, `start_time`, and `(start_time, Id)` sort orders at k=1 lag only. This
    module adds the one new sort order those didn't cover (`(max_date, Id)`, prev/next
    id/time deltas + same-neighbor flags) and extends the `(start_time, Id)` order to
    k=2/k=3 backward lag, testing whether cohort *extent* beyond the immediate
    neighbor carries signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.kaggle.magic_features import _adjacency_deltas

_COHORT_STAT_SUFFIXES: tuple[str, ...] = ("cohort_size", "cohort_pos", "cohort_pos_frac", "is_singleton")
_MAXDATE_ADJ_SUFFIXES: tuple[str, ...] = (
    "prev_id_diff",
    "next_id_diff",
    "prev_time_diff",
    "next_time_diff",
    "same_prev",
    "same_next",
)
_MINDATE_LAG_K: tuple[int, ...] = (2, 3)

COHORT_FEATURE_COLS: list[str] = (
    [f"mindate_{s}" for s in _COHORT_STAT_SUFFIXES]
    + [f"maxdate_{s}" for s in _COHORT_STAT_SUFFIXES]
    + [f"maxdate_{s}" for s in _MAXDATE_ADJ_SUFFIXES]
    + [f"mindate_id_diff_k{k}" for k in _MINDATE_LAG_K]
    + [f"mindate_time_diff_k{k}" for k in _MINDATE_LAG_K]
)


def _concat_train_test(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    train = train_df[["Id", "start_time", "duration"]].copy()
    train = train.sort_values("Id", kind="mergesort").reset_index(drop=True)

    test = test_df[["Id", "start_time", "duration"]].copy()
    test = test.sort_values("Id", kind="mergesort").reset_index(drop=True)

    combined = pd.concat([train, test], ignore_index=True, sort=False)
    combined["max_date"] = combined["start_time"] + combined["duration"]
    # Deterministic NaN placement: +inf sorts NaN last in every order below.
    combined["start_time_key"] = combined["start_time"].fillna(np.inf).astype(np.float64)
    combined["max_date_key"] = combined["max_date"].fillna(np.inf).astype(np.float64)
    return combined


def _cohort_stats(round_key: np.ndarray, ids: np.ndarray, prefix: str) -> dict[str, np.ndarray]:
    """Cohort size/position for rows sharing the same rounded timestamp.

    NaN-timestamp rows get a deterministic singleton cohort (`cohort_size=1`) --
    grouping them together (as a shared "NaN cohort") would assert a false adjacency.
    """
    nan_mask = np.isnan(round_key)
    df = pd.DataFrame({"key": round_key, "Id": ids})
    cohort_size = df.groupby("key")["Id"].transform("size").to_numpy(dtype=np.float64)
    cohort_pos = df.groupby("key")["Id"].rank(method="first").to_numpy(dtype=np.float64)

    cohort_size = np.where(nan_mask, 1.0, cohort_size)
    cohort_pos = np.where(nan_mask, 1.0, cohort_pos)

    cohort_pos_frac = cohort_pos / cohort_size
    is_singleton = (cohort_size == 1).astype(np.int8)

    return {
        f"{prefix}_cohort_size": cohort_size.astype(np.int64),
        f"{prefix}_cohort_pos": cohort_pos.astype(np.int64),
        f"{prefix}_cohort_pos_frac": cohort_pos_frac.astype(np.float64),
        f"{prefix}_is_singleton": is_singleton,
    }


def _mindate_extended_lag(ordered: pd.DataFrame) -> dict[str, np.ndarray]:
    """Backward k=2/k=3 lag in the (start_time, Id) order (K2/K3 only built k=1)."""
    id_arr = ordered["Id"].to_numpy(dtype=np.int64)
    time_arr = ordered["start_time"].to_numpy(dtype=np.float64)
    n = len(id_arr)

    feats: dict[str, np.ndarray] = {}
    for k in _MINDATE_LAG_K:
        id_diff = np.full(n, np.nan)
        time_diff = np.full(n, np.nan)
        if n > k:
            id_diff[k:] = id_arr[k:] - id_arr[:-k]
            time_diff[k:] = time_arr[k:] - time_arr[:-k]
        feats[f"id_diff_k{k}"] = id_diff
        feats[f"time_diff_k{k}"] = time_diff
    return feats


def compute_cohort_features(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    """Build label-free timing-cohort features over train+test concatenated.

    `train_df`/`test_df` must each have `Id`, `start_time`, `duration` (already present
    in `dataset_h_magic_{train,test}.parquet`). Returns a DataFrame with an `Id` column
    plus `COHORT_FEATURE_COLS`, covering every Id in both inputs -- merge back onto the
    train/test feature tables on `Id`.
    """
    combined = _concat_train_test(train_df, test_df)

    mindate_ordered = combined.sort_values(["start_time_key", "Id"], kind="mergesort").reset_index(drop=True)
    maxdate_ordered = combined.sort_values(["max_date_key", "Id"], kind="mergesort").reset_index(drop=True)

    mindate_cohort = _cohort_stats(
        round_key=np.round(combined["start_time"].to_numpy(dtype=np.float64), 2),
        ids=combined["Id"].to_numpy(dtype=np.int64),
        prefix="mindate",
    )
    maxdate_cohort = _cohort_stats(
        round_key=np.round(combined["max_date"].to_numpy(dtype=np.float64), 2),
        ids=combined["Id"].to_numpy(dtype=np.int64),
        prefix="maxdate",
    )

    maxdate_adj_raw = _adjacency_deltas(
        id_arr=maxdate_ordered["Id"].to_numpy(dtype=np.int64),
        time_arr=maxdate_ordered["max_date"].to_numpy(dtype=np.float64),
        tie_key=maxdate_ordered["max_date_key"].to_numpy(),
    )
    # _adjacency_deltas returns id_prev_diff/id_next_diff/time_prev_diff/time_next_diff/same_prev/same_next;
    # rename to this module's maxdate_prev_id_diff / maxdate_next_id_diff convention.
    _rename = {
        "id_prev_diff": "prev_id_diff",
        "id_next_diff": "next_id_diff",
        "time_prev_diff": "prev_time_diff",
        "time_next_diff": "next_time_diff",
        "same_prev": "same_prev",
        "same_next": "same_next",
    }
    maxdate_adj = {f"maxdate_{_rename[name]}": values for name, values in maxdate_adj_raw.items()}
    maxdate_adj_block = pd.DataFrame(maxdate_adj)
    maxdate_adj_block["Id"] = maxdate_ordered["Id"].to_numpy()
    maxdate_adj_block = maxdate_adj_block.set_index("Id")

    mindate_lag_raw = _mindate_extended_lag(mindate_ordered)
    mindate_lag = {f"mindate_{name}": values for name, values in mindate_lag_raw.items()}
    mindate_lag_block = pd.DataFrame(mindate_lag)
    mindate_lag_block["Id"] = mindate_ordered["Id"].to_numpy()
    mindate_lag_block = mindate_lag_block.set_index("Id")

    cohort_block = pd.DataFrame({**mindate_cohort, **maxdate_cohort})
    cohort_block["Id"] = combined["Id"].to_numpy()
    cohort_block = cohort_block.set_index("Id")

    result = cohort_block.join(maxdate_adj_block, how="left").join(mindate_lag_block, how="left")
    return result.reset_index()
