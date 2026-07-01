"""K2 (KDR-003 SS5): record-adjacency / temporal-neighbor "magic" leakage features.

These features are leakage **by construction**: they use row identity/ordering
(`Id`, `start_time`) across the train+test concatenation, including the `Response`
of neighboring TRAIN records looked up by test rows. This is exactly the mechanism
the Production charter forbids (record-adjacency / timing-to-neighbor / test-order
features) -- legal only inside this quarantine (`src/kaggle/`), never importable by
Production code.

Three sort orders are built over the concatenated train+test frame, each a fully
deterministic total order (KDR-003 reproducibility requirement -- no ambiguous ties):
  - `sort_id`:      sort by `Id` alone. `Id` is unique across train+test, so this is
                    already a total order.
  - `sort_time`:    sort by `start_time` alone, ties broken by the fixed input row
                    order (train rows by `Id`, then test rows by `Id` -- see
                    `_concat_train_test`), via a stable ("mergesort") sort.
  - `sort_time_id`: sort by the explicit compound key `(start_time, Id)` -- a
                    different, self-contained tie-break than `sort_time`.

For each order, per row: `Id`/`start_time` deltas to the immediately adjacent record
(prev/next), a same-neighbor tie flag, and the `Response` of the nearest preceding /
following TRAIN record in that order (`train_resp_prev` / `train_resp_next`; NaN if
none exists, e.g. before the first / after the last train record in the order).

Optional duplicate/concat-group aggregates (KDR-003 SS5 candidate extension) are
**omitted** in this K2 pass -- not required by the pre-registration and not free
enough to include without a second design pass; the resulting gap estimate is
still a valid measurement of the adjacency family alone.

NaN `start_time` (~0.05% of rows) is placed deterministically last within each sort
via a `+inf` sentinel key, never left to pandas' NaN-sort behavior.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SORT_ORDERS: tuple[str, ...] = ("adj_id", "adj_time", "adj_time_id")

_SUFFIXES: tuple[str, ...] = (
    "id_prev_diff",
    "id_next_diff",
    "time_prev_diff",
    "time_next_diff",
    "same_prev",
    "same_next",
    "train_resp_prev",
    "train_resp_next",
)

MAGIC_FEATURE_COLS: list[str] = [f"{prefix}_{suffix}" for prefix in SORT_ORDERS for suffix in _SUFFIXES]

# K3 (KDR-004 SS4): the two column subsets used to attribute K2's LB gain between record
# proximity (label-free) and neighbor-label lookup (label-touching, contaminated OOF by
# construction). Named here once so no training/eval script re-derives the split.
TRAIN_RESP_MAGIC_COLS: list[str] = [c for c in MAGIC_FEATURE_COLS if "train_resp" in c]
POSITION_ONLY_MAGIC_COLS: list[str] = [c for c in MAGIC_FEATURE_COLS if "train_resp" not in c]


def _concat_train_test(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    train = train_df[["Id", "start_time", "Response"]].copy()
    train["is_train"] = True
    train = train.sort_values("Id", kind="mergesort").reset_index(drop=True)

    test = test_df[["Id", "start_time"]].copy()
    test["Response"] = np.nan
    test["is_train"] = False
    test = test.sort_values("Id", kind="mergesort").reset_index(drop=True)

    combined = pd.concat([train, test], ignore_index=True, sort=False)
    # Deterministic NaN placement: +inf sorts NaN start_time last in every order below.
    combined["start_time_key"] = combined["start_time"].fillna(np.inf).astype(np.float64)
    return combined


def _adjacency_deltas(id_arr: np.ndarray, time_arr: np.ndarray, tie_key: np.ndarray) -> dict[str, np.ndarray]:
    n = len(id_arr)
    id_prev_diff = np.full(n, np.nan)
    id_next_diff = np.full(n, np.nan)
    time_prev_diff = np.full(n, np.nan)
    time_next_diff = np.full(n, np.nan)
    same_prev = np.zeros(n, dtype=np.int8)
    same_next = np.zeros(n, dtype=np.int8)

    if n > 1:
        id_prev_diff[1:] = id_arr[1:] - id_arr[:-1]
        id_next_diff[:-1] = id_arr[1:] - id_arr[:-1]
        time_prev_diff[1:] = time_arr[1:] - time_arr[:-1]
        time_next_diff[:-1] = time_arr[1:] - time_arr[:-1]
        ties = (tie_key[1:] == tie_key[:-1]).astype(np.int8)
        same_prev[1:] = ties
        same_next[:-1] = ties

    return {
        "id_prev_diff": id_prev_diff,
        "id_next_diff": id_next_diff,
        "time_prev_diff": time_prev_diff,
        "time_next_diff": time_next_diff,
        "same_prev": same_prev,
        "same_next": same_next,
    }


def _train_neighbor_response(is_train: np.ndarray, response: np.ndarray) -> dict[str, np.ndarray]:
    """Nearest strictly-prior / strictly-following TRAIN record's Response.

    `shift(1)` before `ffill()` excludes the row's own position, so a train row
    never sees its own label -- only the nearest *other* train record's label.
    """
    masked = np.where(is_train, response, np.nan).astype(np.float64)
    prev = pd.Series(masked).shift(1).ffill().to_numpy()
    next_ = pd.Series(masked[::-1]).shift(1).ffill().to_numpy()[::-1]
    return {"train_resp_prev": prev, "train_resp_next": next_}


def _order_block(combined: pd.DataFrame, sort_cols: list[str], tie_col: str, prefix: str) -> pd.DataFrame:
    ordered = combined.sort_values(sort_cols, kind="mergesort")

    feats = _adjacency_deltas(
        id_arr=ordered["Id"].to_numpy(dtype=np.int64),
        time_arr=ordered["start_time"].to_numpy(dtype=np.float64),
        tie_key=ordered[tie_col].to_numpy(),
    )
    feats.update(
        _train_neighbor_response(
            is_train=ordered["is_train"].to_numpy(),
            response=ordered["Response"].to_numpy(dtype=np.float64),
        )
    )

    block = pd.DataFrame({f"{prefix}_{name}": values for name, values in feats.items()})
    block["Id"] = ordered["Id"].to_numpy()
    return block.set_index("Id")


def compute_magic_features(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    """Build record-adjacency magic features over train+test concatenated.

    `train_df` must have `Id`, `start_time`, `Response`; `test_df` must have `Id`,
    `start_time` (no `Response`). Returns a DataFrame with an `Id` column plus
    `MAGIC_FEATURE_COLS`, covering every Id in both inputs -- merge back onto the
    train/test feature tables on `Id`.
    """
    combined = _concat_train_test(train_df, test_df)

    blocks = [
        _order_block(combined, sort_cols=["Id"], tie_col="Id", prefix="adj_id"),
        _order_block(combined, sort_cols=["start_time_key"], tie_col="start_time_key", prefix="adj_time"),
        _order_block(
            combined, sort_cols=["start_time_key", "Id"], tie_col="start_time_key", prefix="adj_time_id"
        ),
    ]

    magic = pd.concat(blocks, axis=1)
    return magic.reset_index()
