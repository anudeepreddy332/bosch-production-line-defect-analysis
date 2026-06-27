"""Lazy re-exports: BoschPredictor/TwoStagePredictor pull in joblib and a fitted
FeaturePipeline, which lightweight consumers of this package (e.g. anything that only
needs decision_engine, like apps/api/main.py) should not be forced to import eagerly
just by importing the package.
"""
from typing import Any

__all__ = ["BoschPredictor", "TwoStagePredictor"]


def __getattr__(name: str) -> Any:
    if name == "BoschPredictor":
        from .predictor import BoschPredictor

        return BoschPredictor
    if name == "TwoStagePredictor":
        from .two_stage_predictor import TwoStagePredictor

        return TwoStagePredictor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
