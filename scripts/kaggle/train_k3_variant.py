"""K3 (KDR-004 SS4): train the two adjacency-attribution variants.

Reuses K2's already-built dataset (`data/features/dataset_h_magic_train.parquet`,
unchanged) and the same Production training utilities as K2 (Prod -> Kaggle
import permitted, KDR-003 SS6.6) -- same LightGBM hyperparameters, no change
logged. Only the *feature set* differs, via the column subsets in
`src.kaggle.magic_features`:

  --variant position_only : DATASET_H_FEATURE_COLS + POSITION_ONLY_MAGIC_COLS (18)
      Label-free by construction. Its OOF MCC is NOT contaminated -- an honest
      internal metric, and its OOF-derived threshold is a valid, honest
      recalibration (K2's own threshold was contaminated-OOF-derived).
  --variant label_only : DATASET_H_FEATURE_COLS + TRAIN_RESP_MAGIC_COLS (6)
      Label-touching (train-neighbor Response lookup). Its OOF MCC IS
      contaminated by the same mechanism as K2's full model (KDR-003 SS5
      warning) -- flag it, never compare to an honest MCC. Only the LB
      validly measures this variant.

Outputs (gitignored): outputs/kaggle/models/k3_{variant}_model.pkl

Reproduce:
  PYTHONPATH=. python scripts/kaggle/train_k3_variant.py --variant position_only
  PYTHONPATH=. python scripts/kaggle/train_k3_variant.py --variant label_only
"""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd

from src.features.dataset_h_pipeline import DATASET_H_FEATURE_COLS
from src.kaggle.magic_features import POSITION_ONLY_MAGIC_COLS, TRAIN_RESP_MAGIC_COLS
from src.logger import setup_logger
from src.training.modeling import build_model_payload, train_lightgbm_oof

logger = setup_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = ROOT / "data" / "features"
OUTPUTS_DIR = ROOT / "outputs" / "kaggle"
MODEL_DIR = OUTPUTS_DIR / "models"

VARIANT_MAGIC_COLS = {
    "position_only": POSITION_ONLY_MAGIC_COLS,
    "label_only": TRAIN_RESP_MAGIC_COLS,
}
VARIANT_CONTAMINATED = {
    "position_only": False,
    "label_only": True,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a K3 adjacency-attribution variant (KDR-004).")
    parser.add_argument("--variant", required=True, choices=sorted(VARIANT_MAGIC_COLS))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variant = args.variant
    magic_cols = VARIANT_MAGIC_COLS[variant]
    feature_cols = [*DATASET_H_FEATURE_COLS, *magic_cols]

    dataset_path = FEATURES_DIR / "dataset_h_magic_train.parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Missing {dataset_path}. Run scripts/kaggle/build_magic_dataset.py first.")

    df = pd.read_parquet(dataset_path)
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"{dataset_path} is missing required columns for variant={variant}: {missing}")

    model_name = f"k3_{variant}"
    result, fold_models = train_lightgbm_oof(
        df=df,
        feature_cols=feature_cols,
        model_name=model_name,
        output_oof_path=OUTPUTS_DIR / f"oof_predictions_{model_name}.parquet",
        output_importance_path=OUTPUTS_DIR / f"feature_importance_{model_name}.csv",
    )
    payload = build_model_payload(result, fold_models)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / f"{model_name}_model.pkl"
    joblib.dump(payload, model_path)

    logger.info(f"Saved K3 {variant} model payload ({len(fold_models)} fold models) to {model_path}")
    print(f"variant={variant}")
    print(f"feature_count={len(feature_cols)} (16 dataset_h + {len(magic_cols)} magic)")
    print(f"model_path={model_path}")
    print(f"data_fingerprint={payload['data_fingerprint']}")
    print(f"threshold={payload['threshold']}")
    if VARIANT_CONTAMINATED[variant]:
        print(
            "CONTAMINATED oof_mcc=%.5f (train-neighbor Response leaks across folds -- KDR-004 SS5, "
            "not a valid ranking metric, LB is the only valid measurement)" % payload["oof_mcc"]
        )
    else:
        print(
            "HONEST oof_mcc=%.5f (label-free features only -- valid internal metric, "
            "vs dataset_h honest oof_mcc=0.15337)" % payload["oof_mcc"]
        )


if __name__ == "__main__":
    main()
