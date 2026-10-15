"""
Tests for the Caelis / Tenet Institutional Valuation & Publishing Forensics Model
(`services/valuation/tenet_institutional_model.py`).
"""

from __future__ import annotations

import pytest

from services.valuation.tenet_institutional_model import (
    build_tenet_institutional_valuation_package,
)


def test_default_tenet_zitron_package_and_synthetic_benchmark_metadata():
    pkg = build_tenet_institutional_valuation_package()
    assert pkg.is_synthetic_benchmark is True
    assert pkg.benchmark_scope == "case_specific_synthetic_fixture"
    assert pkg.workbook_audit.is_synthetic_benchmark is True
    assert pkg.workbook_audit.benchmark_scope == "case_specific_synthetic_fixture"
    assert pkg.workbook_audit.reconstructed_pro_forma_3yr_avg_sek == pytest.approx(1330087.45, rel=1e-4)
    assert pkg.workbook_audit.reconstructed_annual_cashflows_sekk[2023] == pytest.approx(4149.0, rel=1e-3)
    assert pkg.workbook_audit.reconstructed_annual_cashflows_sekk[2024] == pytest.approx(5517.0, rel=1e-3)
    assert pkg.workbook_audit.reconstructed_annual_cashflows_sekk[2025] == pytest.approx(4666.0, rel=1e-3)
    assert pkg.evergreen_dcf.fair_value_100pct_sekm > 0
    assert len(pkg.football_field) >= 4


def test_tenet_package_binds_custom_reconstructed_workbook_cashflows():
    default_pkg = build_tenet_institutional_valuation_package()
    custom_audit = default_pkg.workbook_audit.model_copy(
        update={
            "reconstructed_pro_forma_3yr_avg_sek": 100_000.0,
            "reconstructed_annual_cashflows_sekk": {2023: 100.0, 2024: 100.0, 2025: 100.0},
        }
    )
    custom_pkg = build_tenet_institutional_valuation_package(workbook_audit=custom_audit)

    assert custom_pkg.is_synthetic_benchmark is True
    assert custom_pkg.benchmark_scope == "case_specific_synthetic_fixture"
    years_by_num = {yr.year: yr for yr in custom_pkg.business_plan.years}
    assert years_by_num[2023].total_income_sekk == pytest.approx(100.0, rel=1e-2)
    assert years_by_num[2024].total_income_sekk == pytest.approx(100.0, rel=1e-2)
    assert years_by_num[2025].total_income_sekk == pytest.approx(100.0, rel=1e-2)
    assert custom_pkg.evergreen_dcf.fair_value_100pct_sekm < default_pkg.evergreen_dcf.fair_value_100pct_sekm * 0.15
