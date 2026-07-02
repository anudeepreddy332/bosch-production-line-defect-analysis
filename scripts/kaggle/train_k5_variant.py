"""K5 (KDR-006 v2 SS4): train the two duplicate-group attribution variants.

Reuses K5's built dataset (`data/features/dataset_h_dup_train.parquet`, unchanged) and the same
Production training utilities as K2/K3/K4 (`train_lightgbm_oof`/`build_model_payload`) -- same
LightGBM hyperparameters, no change logged. Only the *feature set* differs, exactly mirroring K3's
two-variant attribution design:

  --variant identity_free : DATASET_H_FEATURE_COLS + POSITION_ONLY_MAGIC_COLS + DUPLICATE_FEATURE_COLS (51)
      Label-free by construction (no Response reference anywhere in DUPLICATE_FEATURE_COLS). Its
      OOF MCC is NOT contaminated -- an honest internal metric, the primary metric per KDR-006 v2 SS5.
  --variant identity_label : DATASET_H_FEATURE_COLS + POSITION_ONLY_MAGIC_COLS + DUPLICATE_LABEL_COLS (42)
      Label-touching (identity-conditioned train-neighbor Response lookup). Its OOF MCC IS
      contaminated by the same chunk-aware-CV blind spot as K2's full model / K3-B -- flag it,
      never compare to an honest MCC. Only the LB validly measures this variant.

Outputs (gitignored): outputs/kaggle/models/k5_{variant}_model.pkl

Reproduce:
  PYTHONPATH=. python scripts/kaggle/train_k5_variant.py --variant identity_free
  PYTHONPATH=. python scripts/kaggle/train_k5_variant.py --variant identity_label
"""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd

from src.features.dataset_h_pipeline import DATASET_H_FEATURE_COLS
from src.kaggle.duplicate_features import DUPLICATE_FEATURE_COLS, DUPLICATE_LABEL_COLS
from src.kaggle.magic_features import POSITION_ONLY_MAGIC_COLS
from src.logger import setup_logger
from src.training.modeling import build_model_payload, train_lightgbm_oof

logger = setup_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = ROOT / "data" / "features"
OUTPUTS_DIR = ROOT / "outputs" / "kaggle"
MODEL_DIR = OUTPUTS_DIR / "models"

_BASE_COLS = [*DATASET_H_FEATURE_COLS, *POSITION_ONLY_MAGIC_COLS]

VARIANT_EXTRA_COLS = {
    "identity_free": DUPLICATE_FEATURE_COLS,
    "identity_label": DUPLICATE_LABEL_COLS,
}
VARIANT_CONTAMINATED = {
    "identity_free": False,
    "identity_label": True,
}

# K3-A's own honest OOF, for the marginal-gain comparison KDR-006 asks for.
K3A_OOF_MCC = 0.31761


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a K5 duplicate-group attribution variant (KDR-006 v2).")
    parser.add_argument("--variant", required=True, choices=sorted(VARIANT_EXTRA_COLS))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variant = args.variant
    extra_cols = VARIANT_EXTRA_COLS[variant]
    feature_cols = [*_BASE_COLS, *extra_cols]

    dataset_path = FEATURES_DIR / "dataset_h_dup_train.parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Missing {dataset_path}. Run scripts/kaggle/build_duplicate_dataset.py first.")

    df = pd.read_parquet(dataset_path)
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"{dataset_path} is missing required columns for variant={variant}: {missing}")

    model_name = f"k5_{variant}"
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

    delta = payload["oof_mcc"] - K3A_OOF_MCC
    logger.info(f"Saved K5 {variant} model payload ({len(fold_models)} fold models) to {model_path}")
    print(f"variant={variant}")
    print(f"feature_count={len(feature_cols)} (16 dataset_h + 18 position_only magic + {len(extra_cols)} duplicate)")
    print(f"model_path={model_path}")
    print(f"data_fingerprint={payload['data_fingerprint']}")
    print(f"threshold={payload['threshold']}")
    if VARIANT_CONTAMINATED[variant]:
        print(
            "CONTAMINATED oof_mcc=%.5f (identity-conditioned train-neighbor Response leaks across "
            "folds -- KDR-006 v2 SS5, not a valid ranking metric, LB is the only valid measurement)"
            % payload["oof_mcc"]
        )
    else:
        print(
            "HONEST oof_mcc=%.5f (label-free; vs K3-A honest oof_mcc=%.5f, delta=%+.5f)"
            % (payload["oof_mcc"], K3A_OOF_MCC, delta)
        )


if __name__ == "__main__":
    main()
