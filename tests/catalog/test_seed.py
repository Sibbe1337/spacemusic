import json
from pathlib import Path

from libs.catalog.models import CatalogPassport


def test_synthetic_soundscape_fixture_is_valid_catalog_passport():
    path = Path(__file__).parents[2] / "fixtures" / "synthetic_soundscape_catalog.json"
    passport = CatalogPassport.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert len(passport.tracks) == 3
    assert len(passport.revenue_history) == 12
    assert all(period.verified for period in passport.revenue_history)
    assert passport.anti_fraud_status == "CLEAR"
