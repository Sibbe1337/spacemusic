"""Versioned model interface for analytics consumers.

Commercial valuation is implemented in ``libs.catalog.valuation``. This module
only provides a small, explicit interface for consumers that need a model object;
it does not load arbitrary pickle files.
"""

from __future__ import annotations

from typing import Any, Mapping

from .feature_pipeline import process_data_for_features


class EvidenceFeatureModel:
    """Stable feature model used when a caller needs a model-like interface."""

    def __init__(self, name: str, version: str = "evidence-features-v1") -> None:
        self.name = name
        self.version = version

    def predict(self, input_data: Mapping[str, Any]) -> dict[str, Any]:
        return {"version": self.version, "features": process_data_for_features(input_data)}


def load_model(model_name: str, *, version: str = "evidence-features-v1") -> EvidenceFeatureModel:
    """Load the explicit built-in evidence feature model."""
    return EvidenceFeatureModel(model_name, version)
