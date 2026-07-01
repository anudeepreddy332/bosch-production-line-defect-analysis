"""K4 (KDR-005 SS4): train the label-free timing-cohort model.

Reuses K3's winning feature set (`DATASET_H_FEATURE_COLS` + `POSITION_ONLY_MAGIC_COLS`, K3-A's
34 features, public LB 0.31791 / private 0.33161) plus the 18 new cohort features from
`src.kaggle.cohort_features`, read from `data/features/dataset_h_cohort_train.parquet` (built by
`scripts/kaggle/build_cohort_dataset.py`). Same Production training utilities as K2/K3
(`train_lightgbm_oof`/`build_model_payload`) -- same LightGBM hyperparameters, no change logged.

Label-free by construction: no `Response`/`train_resp_*` column is read anywhere in
`cohort_features.py`. K4 is a single variant (marginal-gain test against the K3-A baseline), not
an A/B attribution split like K3.

Outputs (gitignored): outputs/kaggle/models/k4_cohort_model.pkl

Reproduce:
  PYTHONPATH=. python scripts/kaggle/train_k4_cohort.py
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from src.features.dataset_h_pipeline import DATASET_H_FEATURE_COLS
from src.kaggle.cohort_features import COHORT_FEATURE_COLS
from src.kaggle.magic_features import POSITION_ONLY_MAGIC_COLS
from src.logger import setup_logger
from src.training.modeling import build_model_payload, train_lightgbm_oof

logger = setup_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = ROOT / "data" / "features"
OUTPUTS_DIR = ROOT / "outputs" / "kaggle"
MODEL_DIR = OUTPUTS_DIR / "models"

MODEL_NAME = "k4_cohort"
FEATURE_COLS = [*DATASET_H_FEATURE_COLS, *POSITION_ONLY_MAGIC_COLS, *COHORT_FEATURE_COLS]

# K3-A's own honest OOF, for the marginal-gain comparison KDR-005 asks for.
K3A_OOF_MCC = 0.31761


def main() -> None:
    dataset_path = FEATURES_DIR / "dataset_h_cohort_train.parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Missing {dataset_path}. Run scripts/kaggle/build_cohort_dataset.py first.")

    df = pd.read_parquet(dataset_path)
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        raise RuntimeError(f"{dataset_path} is missing required columns: {missing}")

    result, fold_models = train_lightgbm_oof(
        df=df,
        feature_cols=FEATURE_COLS,
        model_name=MODEL_NAME,
        output_oof_path=OUTPUTS_DIR / f"oof_predictions_{MODEL_NAME}.parquet",
        output_importance_path=OUTPUTS_DIR / f"feature_importance_{MODEL_NAME}.csv",
    )
    payload = build_model_payload(result, fold_models)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / f"{MODEL_NAME}_model.pkl"
    joblib.dump(payload, model_path)

    delta = payload["oof_mcc"] - K3A_OOF_MCC
    logger.info(f"Saved K4 cohort model payload ({len(fold_models)} fold models) to {model_path}")
    print(f"feature_count={len(FEATURE_COLS)} (16 dataset_h + 18 position_only magic + 18 cohort)")
    print(f"model_path={model_path}")
    print(f"data_fingerprint={payload['data_fingerprint']}")
    print(f"threshold={payload['threshold']}")
    print(f"HONEST oof_mcc={payload['oof_mcc']:.5f} (label-free; vs K3-A honest oof_mcc={K3A_OOF_MCC:.5f}, delta={delta:+.5f})")


if __name__ == "__main__":
    main()
