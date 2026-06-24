from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np
import pandas as pd

DATASET_H_FEATURE_COLS = [
    "start_time",
    "duration",
    "feature_mean",
    "records_last_1hr",
    "records_last_24hr",
    "density_ratio",
    "chunk_id",
    "chunk_size",
    "transition_fail_rate_mean",
    "transition_fail_rate_max",
    "transition_fail_rate_std",
    "station_risk_mean",
    "path_count",
    "pair_cooccur_mean",
    "pair_cooccur_max",
    "pair_cooccur_std",
]


def parse_signature(signature: str) -> tuple[str, ...]:
    if pd.isna(signature) or signature == "__none__":
        return tuple()
    return tuple(token for token in str(signature).split("|") if token)


def transitions_from_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if len(tokens) < 2:
        return tuple()
    return tuple(f"{tokens[i]}>{tokens[i + 1]}" for i in range(len(tokens) - 1))


def pairs_from_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if len(tokens) < 2:
        return tuple()
    return tuple(f"{a}&{b}" for a, b in combinations(tokens, 2))


def _mean_max_std(values: list[float], default_mean: float) -> tuple[float, float, float]:
    if not values:
        return float(default_mean), float(default_mean), 0.0
    arr = np.array(values, dtype=np.float32)
    return float(arr.mean()), float(arr.max()), float(arr.std())


def compute_dataset_h_lookup_artifacts(train_df: pd.DataFrame) -> dict:
    """Fit dataset_h's train-derived rate/count lookups from labeled train data only.

    ``train_df`` must have ``Response`` and ``path_signature`` columns (e.g. the
    ``dataset_baseline.parquet`` + ``path_metadata.parquet`` merge already built by
    ``scripts/build_dataset_baseline.py``). Unlike the per-fold statistics computed inside
    ``scripts/build_dataset_h.py`` (which are intentionally restricted to each fold's
    training rows to keep OOF predictions leakage-free), this fits on the FULL train set --
    correct here because the consumer is genuinely unseen test/incoming data that was never
    part of these statistics, not a held-out fold of the same rows used to fit them.
    """
    sig_str = train_df["path_signature"].fillna("__none__").astype(str)
    global_mean = float(train_df["Response"].mean())

    unique_signatures = sig_str.unique()
    sig_tokens = {sig: parse_signature(sig) for sig in unique_signatures}
    sig_pairs = {sig: pairs_from_tokens(tokens) for sig, tokens in sig_tokens.items()}

    sig_freq = sig_str.value_counts()

    pair_count: defaultdict[str, int] = defaultdict(int)
    for sig, freq in sig_freq.items():
        for pair in sig_pairs.get(sig, tuple()):
            pair_count[pair] += int(freq)

    sig_stats = pd.DataFrame({"sig": sig_str, "Response": train_df["Response"]}).groupby("sig")["Response"].agg(
        ["sum", "count"]
    )

    station_sum: defaultdict[str, float] = defaultdict(float)
    station_cnt: defaultdict[str, int] = defaultdict(int)
    trans_sum: defaultdict[str, float] = defaultdict(float)
    trans_cnt: defaultdict[str, int] = defaultdict(int)

    for sig, row in sig_stats.iterrows():
        y_sum = float(row["sum"])
        y_cnt = int(row["count"])
        tokens = sig_tokens.get(sig, tuple())

        for station in tokens:
            station_sum[station] += y_sum
            station_cnt[station] += y_cnt

        for trans in transitions_from_tokens(tokens):
            trans_sum[trans] += y_sum
            trans_cnt[trans] += y_cnt

    station_rate = {k: station_sum[k] / station_cnt[k] for k in station_sum if station_cnt[k] > 0}
    trans_rate = {k: trans_sum[k] / trans_cnt[k] for k in trans_sum if trans_cnt[k] > 0}

    return {
        "global_mean": global_mean,
        "station_rate": station_rate,
        "trans_rate": trans_rate,
        "path_count_train": {str(k): int(v) for k, v in sig_freq.items()},
        "pair_count_train": {str(k): int(v) for k, v in pair_count.items()},
    }


def apply_dataset_h_lookup(df: pd.DataFrame, lookup: dict) -> pd.DataFrame:
    """Apply persisted train-derived lookups to unlabeled rows with a ``path_signature`` column.

    ``df`` must already have the 8 baseline core columns (start_time, duration, feature_mean,
    records_last_1hr, records_last_24hr, density_ratio, chunk_id, chunk_size) plus
    ``path_signature`` -- all computable directly from raw unlabeled numeric/date columns with
    no train dependency (see ``scripts/build_dataset_baseline.py``). No ``Response`` column is
    read or required. Tokens/signatures unseen in train fall back exactly as the per-fold
    validation-side code in ``scripts/build_dataset_h.py`` does: path_count -> 1, rate features ->
    ``global_mean``, pair co-occurrence -> 0.0.
    """
    global_mean = float(lookup["global_mean"])
    station_rate: dict[str, float] = lookup["station_rate"]
    trans_rate: dict[str, float] = lookup["trans_rate"]
    path_count_train: dict[str, int] = lookup["path_count_train"]
    pair_count_train: dict[str, int] = lookup["pair_count_train"]

    sig_str = df["path_signature"].fillna("__none__").astype(str)
    unique_sigs = sig_str.unique()

    sig_features: dict[str, tuple[float, float, float, float, int, float, float, float]] = {}
    for sig in unique_sigs:
        tokens = parse_signature(sig)
        transitions = transitions_from_tokens(tokens)
        pairs = pairs_from_tokens(tokens)

        trans_values = [float(trans_rate.get(t, global_mean)) for t in transitions]
        station_values = [float(station_rate.get(s, global_mean)) for s in tokens]
        pair_values = [float(pair_count_train[p]) for p in pairs if p in pair_count_train]

        tr_mean, tr_max, tr_std = _mean_max_std(trans_values, default_mean=global_mean)
        st_mean, _, _ = _mean_max_std(station_values, default_mean=global_mean)
        pc_mean, pc_max, pc_std = _mean_max_std(pair_values, default_mean=0.0)
        path_count = int(path_count_train.get(sig, 1))

        sig_features[sig] = (tr_mean, tr_max, tr_std, st_mean, path_count, pc_mean, pc_max, pc_std)

    out = df.copy()
    out["transition_fail_rate_mean"] = sig_str.map(lambda s: sig_features[s][0]).astype(np.float32)
    out["transition_fail_rate_max"] = sig_str.map(lambda s: sig_features[s][1]).astype(np.float32)
    out["transition_fail_rate_std"] = sig_str.map(lambda s: sig_features[s][2]).astype(np.float32)
    out["station_risk_mean"] = sig_str.map(lambda s: sig_features[s][3]).astype(np.float32)
    out["path_count"] = sig_str.map(lambda s: sig_features[s][4]).astype(np.int32)
    out["pair_cooccur_mean"] = sig_str.map(lambda s: sig_features[s][5]).astype(np.float32)
    out["pair_cooccur_max"] = sig_str.map(lambda s: sig_features[s][6]).astype(np.float32)
    out["pair_cooccur_std"] = sig_str.map(lambda s: sig_features[s][7]).astype(np.float32)
    return out
