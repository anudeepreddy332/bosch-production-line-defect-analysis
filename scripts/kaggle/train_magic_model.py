"""K2 (KDR-003 SS5): train the record-adjacency magic-leakage model.

Reuses Production's training utilities as-is (Prod -> Kaggle import permitted,
KDR-003 SS6.6) -- same LightGBM hyperparameters as `dataset_h` (no change logged),
same chunk-aware CV machinery. The *feature set* is the only thing that differs:
`DATASET_H_FEATURE_COLS` (16, clean) + `MAGIC_FEATURE_COLS` (24, leaky by
construction, KDR-003 SS5).

KDR-003 SS5 warning (binding): the OOF MCC this script reports is CONTAMINATED --
`train_resp_prev`/`train_resp_next` leak a neighboring TRAIN row's Response across
CV folds (Bosch's `Id`/`start_time` ordering is shared across the whole train set,
not just train-vs-test). It must never be reported as an honest ranking metric or
compared to `dataset_h`'s OOF MCC (0.15337) as if the two were on the same footing.
Only the held-out Kaggle LB score is a valid measurement of the magic's value.

Output (gitignored): outputs/kaggle/models/k2_magic_model.pkl

Reproduce: PYTHONPATH=. python scripts/kaggle/train_magic_model.py
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from src.features.dataset_h_pipeline import DATASET_H_FEATURE_COLS
from src.kaggle.magic_features import MAGIC_FEATURE_COLS
from src.logger import setup_logger
from src.training.modeling import build_model_payload, train_lightgbm_oof

logger = setup_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = ROOT / "data" / "features"
OUTPUTS_DIR = ROOT / "outputs" / "kaggle"
MODEL_DIR = OUTPUTS_DIR / "models"

FEATURE_COLS = [*DATASET_H_FEATURE_COLS, *MAGIC_FEATURE_COLS]


def main() -> None:
    dataset_path = FEATURES_DIR / "dataset_h_magic_train.parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Missing {dataset_path}. Run scripts/kaggle/build_magic_dataset.py first.")

    df = pd.read_parquet(dataset_path)

    result, fold_models = train_lightgbm_oof(
        df=df,
        feature_cols=FEATURE_COLS,
        model_name="k2_magic",
        output_oof_path=OUTPUTS_DIR / "oof_predictions_k2_magic.parquet",
        output_importance_path=OUTPUTS_DIR / "feature_importance_k2_magic.csv",
    )
    payload = build_model_payload(result, fold_models)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "k2_magic_model.pkl"
    joblib.dump(payload, model_path)

    logger.info(f"Saved K2 magic model payload ({len(fold_models)} fold models) to {model_path}")
    print(f"model_path={model_path}")
    print(f"data_fingerprint={payload['data_fingerprint']}")
    print(f"threshold={payload['threshold']}")
    print("CONTAMINATED oof_mcc=%.5f (train-neighbor Response leaks across folds -- KDR-003 SS5 warning, "
          "not a valid ranking metric, never compare to dataset_h oof_mcc=0.15337)" % payload["oof_mcc"])


if __name__ == "__main__":
    main()
