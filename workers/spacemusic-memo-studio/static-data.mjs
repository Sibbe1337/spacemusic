// Auto-generated from services/valuation/tenet_institutional_model.py, buyer_router.py, and paid_memo_service.py
export const TENET_ZITRON_PACKAGE = {
  "deal_name": "Project Tenet \u2014 Michel Zitron & John Martin Catalog (50% Stake)",
  "is_synthetic_benchmark": true,
  "benchmark_scope": "case_specific_synthetic_fixture",
  "benchmark_provenance_note": "Synthetic case-specific reference fixture (Project Tenet / Caelis model); business plan baseline cash flows are bound to workbook_audit when reconstructed cash flows are provided.",
  "workbook_audit": {
    "writer_name": "Michel Zitron",
    "currency": "SEK",
    "seller_reported_gross_total_sek": 5567645.0,
    "seller_reported_net_79pct_sek": 4398439.55,
    "seller_reported_3yr_avg_sek": 1466146.52,
    "seller_applied_multiple": 12.0,
    "seller_implied_valuation_sek": 17593758.2,
    "reconstructed_2023_2025_gross_sek": 5050965.0,
    "excluded_2022_prior_period_sek": 516680.0,
    "missed_by_broken_sumif_sek": 0.0,
    "lod_double_deduction_avoided_sek": 75245.1,
    "reconstructed_pro_forma_net_3yr_sek": 3990262.35,
    "reconstructed_pro_forma_3yr_avg_sek": 1330087.45,
    "valuation_delta_at_seller_multiple_sek": -1632708.8,
    "reconstructed_annual_cashflows_sekk": {
      "2023": 4149.0,
      "2024": 5517.0,
      "2025": 4666.0
    },
    "is_synthetic_benchmark": true,
    "benchmark_scope": "case_specific_synthetic_fixture",
    "track_breakdowns": [
      {
        "canonical_title": "Don't You Worry Child",
        "stim_gross_sek": 2195329.0,
        "bmg_gross_sek": 2099180.0,
        "kobalt_gross_sek": 0.0,
        "prior_2022_excluded_sek": 448900.0,
        "total_2023_2025_gross_sek": 4294509.0,
        "prior_sold_share_pct": 21.0,
        "manual_passthrough_deduction_sek": 901846.89,
        "pro_forma_net_2023_2025_sek": 3392662.11,
        "pro_forma_annual_avg_sek": 1130887.37
      },
      {
        "canonical_title": "Save the World",
        "stim_gross_sek": 217074.0,
        "bmg_gross_sek": 352920.0,
        "kobalt_gross_sek": 0.0,
        "prior_2022_excluded_sek": 61320.0,
        "total_2023_2025_gross_sek": 569994.0,
        "prior_sold_share_pct": 21.0,
        "manual_passthrough_deduction_sek": 119698.74,
        "pro_forma_net_2023_2025_sek": 450295.26,
        "pro_forma_annual_avg_sek": 150098.42
      },
      {
        "canonical_title": "Reload (Free Love)",
        "stim_gross_sek": 71889.0,
        "bmg_gross_sek": 0.0,
        "kobalt_gross_sek": 82471.0,
        "prior_2022_excluded_sek": 3170.0,
        "total_2023_2025_gross_sek": 154360.0,
        "prior_sold_share_pct": 21.0,
        "manual_passthrough_deduction_sek": 32415.6,
        "pro_forma_net_2023_2025_sek": 121944.4,
        "pro_forma_annual_avg_sek": 40648.13
      },
      {
        "canonical_title": "Fade into Darkness",
        "stim_gross_sek": 20612.0,
        "bmg_gross_sek": 11490.0,
        "kobalt_gross_sek": 0.0,
        "prior_2022_excluded_sek": 3290.0,
        "total_2023_2025_gross_sek": 32102.0,
        "prior_sold_share_pct": 21.0,
        "manual_passthrough_deduction_sek": 6741.42,
        "pro_forma_net_2023_2025_sek": 25360.58,
        "pro_forma_annual_avg_sek": 8453.53
      },
      {
        "canonical_title": "Reload (instrumental)",
        "stim_gross_sek": 0.0,
        "bmg_gross_sek": 0.0,
        "kobalt_gross_sek": 0.0,
        "prior_2022_excluded_sek": 0.0,
        "total_2023_2025_gross_sek": 0.0,
        "prior_sold_share_pct": 21.0,
        "manual_passthrough_deduction_sek": 0.0,
        "pro_forma_net_2023_2025_sek": 0.0,
        "pro_forma_annual_avg_sek": 0.0
      }
    ],
    "audit_findings": [
      {
        "code": "OUT_OF_WINDOW_PRIOR_YEAR_INCLUSION",
        "sheet_name": "BMG Rights & Kobalt",
        "cell_reference": "BMG Rights!A6:C9 & Kobalt!A21:C24",
        "severity": "HIGH",
        "title": "Out-of-Window 2020/2022 Royalty Rows Included in 2023\u20132025 3-Year Sum",
        "description": "Seller's `Summering` SUMIF includes `12/2022` BMG distributions (448,900 SEK on DYWC + 61,320 SEK on Save the World + 3,290 SEK on Fade into Darkness = 513,510 SEK) plus 3,170 SEK from `II/2020` in Kobalt, inflating the 2023\u20132025 3-year sum by 516,680 SEK before dividing by 3 (`=B11/3`).",
        "financial_distortion_sek": 408177.2
      },
      {
        "code": "SUMIF_WILDCARD_OR_PUNCTUATION_MISMATCH",
        "sheet_name": "Summering",
        "cell_reference": "Summering!C6:E6",
        "severity": "MEDIUM",
        "title": "Inconsistent Track Title Punctuation (`Reload (Free Love)` vs `Reload /Free Love)`)",
        "description": "Track is spelled `Reload (Free Love)` in STIM but `Reload /Free Love)` (with a slash instead of opening parenthesis) in BMG Rights and Kobalt, requiring brittle `*Free Love*` wildcard workarounds and risking silent row drops in automated SUMIF templates.",
        "financial_distortion_sek": 0.0
      },
      {
        "code": "PRE_COLLECTION_ZERO_ROW_DILUTION",
        "sheet_name": "STIM",
        "cell_reference": "STIM!A6:C53",
        "severity": "MEDIUM",
        "title": "48 Pre-Collection Zero-Payout Rows (Feb\u2013Nov 2022) in STIM Ledger",
        "description": "Rows 6\u201353 in the STIM tab cover Excel serial dates 44614\u201344911 (Feb\u2013Dec 2022) with 0 SEK across all 48 entries, confirming STIM distributions in this ledger only began in Feb 2023 (serial 44973).",
        "financial_distortion_sek": 0.0
      },
      {
        "code": "NAIVE_BLANKET_OWNERSHIP_MULTIPLIER_VS_LOD",
        "sheet_name": "Summering",
        "cell_reference": "Summering!B11:E11",
        "severity": "HIGH",
        "title": "Blanket `=B10*0.79` Multiplier Ignores BMG Direct LOD Cutover (H2 2025)",
        "description": "Seller applies a flat `0.79` (79%) multiplier across STIM, BMG, and Kobalt totals. However, per the contractual perimeter, BMG began paying the 21% income buyer directly via Letter of Direction (LOD) from H2 2025 while STIM and Kobalt still pay 100% to Michel for manual pass-through. Applying `0.79` to post-LOD BMG statements double-deducts the 21% outside interest.",
        "financial_distortion_sek": 75245.1
      }
    ]
  },
  "business_plan": {
    "currency_unit": "SEKk",
    "years": [
      {
        "year": 2023,
        "is_historical": true,
        "streaming_sekk": 2350.0,
        "synch_sekk": 459.0,
        "live_sekk": 163.0,
        "radio_sekk": 545.0,
        "other_sekk": 632.0,
        "total_income_sekk": 4149.0,
        "yoy_growth_pct": null,
        "streaming_share_pct": 56.6
      },
      {
        "year": 2024,
        "is_historical": true,
        "streaming_sekk": 2616.0,
        "synch_sekk": 687.0,
        "live_sekk": 537.0,
        "radio_sekk": 737.0,
        "other_sekk": 940.0,
        "total_income_sekk": 5517.0,
        "yoy_growth_pct": 33.0,
        "streaming_share_pct": 47.4
      },
      {
        "year": 2025,
        "is_historical": true,
        "streaming_sekk": 2444.0,
        "synch_sekk": 244.0,
        "live_sekk": 543.0,
        "radio_sekk": 715.0,
        "other_sekk": 720.0,
        "total_income_sekk": 4666.0,
        "yoy_growth_pct": -15.4,
        "streaming_share_pct": 52.4
      },
      {
        "year": 2026,
        "is_historical": false,
        "streaming_sekk": 2705.5,
        "synch_sekk": 245.0,
        "live_sekk": 544.0,
        "radio_sekk": 723.0,
        "other_sekk": 779.0,
        "total_income_sekk": 4996.5,
        "yoy_growth_pct": 7.1,
        "streaming_share_pct": 54.1
      },
      {
        "year": 2027,
        "is_historical": false,
        "streaming_sekk": 2867.8,
        "synch_sekk": 249.9,
        "live_sekk": 554.9,
        "radio_sekk": 708.5,
        "other_sekk": 763.4,
        "total_income_sekk": 5144.6,
        "yoy_growth_pct": 3.0,
        "streaming_share_pct": 55.7
      },
      {
        "year": 2028,
        "is_historical": false,
        "streaming_sekk": 3031.3,
        "synch_sekk": 254.9,
        "live_sekk": 566.0,
        "radio_sekk": 694.4,
        "other_sekk": 748.2,
        "total_income_sekk": 5294.7,
        "yoy_growth_pct": 2.9,
        "streaming_share_pct": 57.3
      },
      {
        "year": 2029,
        "is_historical": false,
        "streaming_sekk": 3176.8,
        "synch_sekk": 260.0,
        "live_sekk": 577.3,
        "radio_sekk": 680.5,
        "other_sekk": 733.2,
        "total_income_sekk": 5427.8,
        "yoy_growth_pct": 2.5,
        "streaming_share_pct": 58.5
      },
      {
        "year": 2030,
        "is_historical": false,
        "streaming_sekk": 3303.9,
        "synch_sekk": 265.2,
        "live_sekk": 588.8,
        "radio_sekk": 666.9,
        "other_sekk": 718.5,
        "total_income_sekk": 5543.3,
        "yoy_growth_pct": 2.1,
        "streaming_share_pct": 59.6
      },
      {
        "year": 2031,
        "is_historical": false,
        "streaming_sekk": 3429.4,
        "synch_sekk": 270.5,
        "live_sekk": 600.6,
        "radio_sekk": 653.5,
        "other_sekk": 704.2,
        "total_income_sekk": 5658.2,
        "yoy_growth_pct": 2.1,
        "streaming_share_pct": 60.6
      }
    ],
    "cagr_23_25a_streaming_pct": 2.0,
    "cagr_23_25a_total_pct": 6.0,
    "cagr_26_31e_streaming_pct": 4.9,
    "cagr_26_31e_synch_pct": 2.0,
    "cagr_26_31e_live_pct": 2.0,
    "cagr_26_31e_radio_pct": -2.0,
    "cagr_26_31e_other_pct": -2.0,
    "cagr_26_31e_total_pct": 2.5,
    "normalized_synch_baseline_sekk": 245.0,
    "one_off_2024_synch_spike_sekk": 442.0
  },
  "market_alpha": {
    "track_title": "Don't You Worry Child",
    "catalog_revenue_share_pct": 71.6,
    "release_year": 2012,
    "weighted_vintage_year": 2012,
    "us_volume_index_2026": 250.0,
    "de_volume_index_2026": 245.0,
    "uk_volume_index_2026": 135.0,
    "us_market_relative_alpha_pct": 42.9,
    "de_market_relative_alpha_pct": 36.1,
    "uk_market_relative_alpha_pct": -12.9,
    "outperforming_tier1_markets": [
      "US",
      "DE"
    ],
    "discovery_mode_windows_detected": [
      "2023-Q1 to 2024-Aug (Confirmed Universal Discovery Mode)",
      "2026-Q1 to 2026-Q3 (Likely Discovery Mode Re-Activation)"
    ],
    "discovery_mode_estimated_uplift_pct": 18.5,
    "recommended_dd_actions": [
      "Request Spotify for Artists / Universal Music campaign log confirming which months `Don't You Worry Child` was enrolled in Spotify Discovery Mode.",
      "Stress-test 2026E streaming baseline (-10% to -15% volume sensitivity) in case Universal disables Discovery Mode on the master recording."
    ]
  },
  "evergreen_dcf": {
    "acquired_stake_pct": 50.0,
    "wacc_midpoint_pct": 9.0,
    "terminal_growth_midpoint_pct": 1.5,
    "annual_admin_expense_100pct_sekk": 200.0,
    "ppa_amortization_years": 10,
    "fair_value_50pct_sekm": 34.6,
    "fair_value_100pct_sekm": 69.2,
    "implied_2026e_multiple_midpoint": 13.8,
    "implied_l3y_avg_multiple_midpoint": 14.5,
    "wacc_vs_pgr_matrix": [
      {
        "row_value": 0.5,
        "col_value": 8.0,
        "enterprise_value_m": 36.9,
        "implied_2026e_multiple": 14.8
      },
      {
        "row_value": 0.5,
        "col_value": 8.5,
        "enterprise_value_m": 34.5,
        "implied_2026e_multiple": 13.8
      },
      {
        "row_value": 0.5,
        "col_value": 9.0,
        "enterprise_value_m": 32.4,
        "implied_2026e_multiple": 13.0
      },
      {
        "row_value": 0.5,
        "col_value": 9.5,
        "enterprise_value_m": 30.6,
        "implied_2026e_multiple": 12.2
      },
      {
        "row_value": 0.5,
        "col_value": 10.0,
        "enterprise_value_m": 28.9,
        "implied_2026e_multiple": 11.6
      },
      {
        "row_value": 1.0,
        "col_value": 8.0,
        "enterprise_value_m": 38.4,
        "implied_2026e_multiple": 15.4
      },
      {
        "row_value": 1.0,
        "col_value": 8.5,
        "enterprise_value_m": 35.7,
        "implied_2026e_multiple": 14.3
      },
      {
        "row_value": 1.0,
        "col_value": 9.0,
        "enterprise_value_m": 33.5,
        "implied_2026e_multiple": 13.4
      },
      {
        "row_value": 1.0,
        "col_value": 9.5,
        "enterprise_value_m": 31.4,
        "implied_2026e_multiple": 12.6
      },
      {
        "row_value": 1.0,
        "col_value": 10.0,
        "enterprise_value_m": 29.6,
        "implied_2026e_multiple": 11.8
      },
      {
        "row_value": 1.5,
        "col_value": 8.0,
        "enterprise_value_m": 40.0,
        "implied_2026e_multiple": 16.0
      },
      {
        "row_value": 1.5,
        "col_value": 8.5,
        "enterprise_value_m": 37.1,
        "implied_2026e_multiple": 14.8
      },
      {
        "row_value": 1.5,
        "col_value": 9.0,
        "enterprise_value_m": 34.6,
        "implied_2026e_multiple": 13.8
      },
      {
        "row_value": 1.5,
        "col_value": 9.5,
        "enterprise_value_m": 32.4,
        "implied_2026e_multiple": 13.0
      },
      {
        "row_value": 1.5,
        "col_value": 10.0,
        "enterprise_value_m": 30.5,
        "implied_2026e_multiple": 12.2
      },
      {
        "row_value": 2.0,
        "col_value": 8.0,
        "enterprise_value_m": 42.0,
        "implied_2026e_multiple": 16.8
      },
      {
        "row_value": 2.0,
        "col_value": 8.5,
        "enterprise_value_m": 38.7,
        "implied_2026e_multiple": 15.5
      },
      {
        "row_value": 2.0,
        "col_value": 9.0,
        "enterprise_value_m": 35.9,
        "implied_2026e_multiple": 14.4
      },
      {
        "row_value": 2.0,
        "col_value": 9.5,
        "enterprise_value_m": 33.5,
        "implied_2026e_multiple": 13.4
      },
      {
        "row_value": 2.0,
        "col_value": 10.0,
        "enterprise_value_m": 31.4,
        "implied_2026e_multiple": 12.6
      },
      {
        "row_value": 2.5,
        "col_value": 8.0,
        "enterprise_value_m": 44.2,
        "implied_2026e_multiple": 17.7
      },
      {
        "row_value": 2.5,
        "col_value": 8.5,
        "enterprise_value_m": 40.6,
        "implied_2026e_multiple": 16.2
      },
      {
        "row_value": 2.5,
        "col_value": 9.0,
        "enterprise_value_m": 37.5,
        "implied_2026e_multiple": 15.0
      },
      {
        "row_value": 2.5,
        "col_value": 9.5,
        "enterprise_value_m": 34.8,
        "implied_2026e_multiple": 13.9
      },
      {
        "row_value": 2.5,
        "col_value": 10.0,
        "enterprise_value_m": 32.5,
        "implied_2026e_multiple": 13.0
      }
    ],
    "growth_delta_vs_pgr_matrix": [
      {
        "row_value": 0.5,
        "col_value": -1.0,
        "enterprise_value_m": 30.1,
        "implied_2026e_multiple": 12.0
      },
      {
        "row_value": 0.5,
        "col_value": -0.5,
        "enterprise_value_m": 31.2,
        "implied_2026e_multiple": 12.5
      },
      {
        "row_value": 0.5,
        "col_value": 0.0,
        "enterprise_value_m": 32.4,
        "implied_2026e_multiple": 13.0
      },
      {
        "row_value": 0.5,
        "col_value": 0.5,
        "enterprise_value_m": 33.7,
        "implied_2026e_multiple": 13.5
      },
      {
        "row_value": 0.5,
        "col_value": 1.0,
        "enterprise_value_m": 35.0,
        "implied_2026e_multiple": 14.0
      },
      {
        "row_value": 1.0,
        "col_value": -1.0,
        "enterprise_value_m": 31.0,
        "implied_2026e_multiple": 12.4
      },
      {
        "row_value": 1.0,
        "col_value": -0.5,
        "enterprise_value_m": 32.2,
        "implied_2026e_multiple": 12.9
      },
      {
        "row_value": 1.0,
        "col_value": 0.0,
        "enterprise_value_m": 33.5,
        "implied_2026e_multiple": 13.4
      },
      {
        "row_value": 1.0,
        "col_value": 0.5,
        "enterprise_value_m": 34.8,
        "implied_2026e_multiple": 13.9
      },
      {
        "row_value": 1.0,
        "col_value": 1.0,
        "enterprise_value_m": 36.1,
        "implied_2026e_multiple": 14.4
      },
      {
        "row_value": 1.5,
        "col_value": -1.0,
        "enterprise_value_m": 32.0,
        "implied_2026e_multiple": 12.8
      },
      {
        "row_value": 1.5,
        "col_value": -0.5,
        "enterprise_value_m": 33.3,
        "implied_2026e_multiple": 13.3
      },
      {
        "row_value": 1.5,
        "col_value": 0.0,
        "enterprise_value_m": 34.6,
        "implied_2026e_multiple": 13.8
      },
      {
        "row_value": 1.5,
        "col_value": 0.5,
        "enterprise_value_m": 36.0,
        "implied_2026e_multiple": 14.4
      },
      {
        "row_value": 1.5,
        "col_value": 1.0,
        "enterprise_value_m": 37.4,
        "implied_2026e_multiple": 15.0
      },
      {
        "row_value": 2.0,
        "col_value": -1.0,
        "enterprise_value_m": 33.2,
        "implied_2026e_multiple": 13.3
      },
      {
        "row_value": 2.0,
        "col_value": -0.5,
        "enterprise_value_m": 34.6,
        "implied_2026e_multiple": 13.8
      },
      {
        "row_value": 2.0,
        "col_value": 0.0,
        "enterprise_value_m": 35.9,
        "implied_2026e_multiple": 14.4
      },
      {
        "row_value": 2.0,
        "col_value": 0.5,
        "enterprise_value_m": 37.4,
        "implied_2026e_multiple": 14.9
      },
      {
        "row_value": 2.0,
        "col_value": 1.0,
        "enterprise_value_m": 38.9,
        "implied_2026e_multiple": 15.5
      },
      {
        "row_value": 2.5,
        "col_value": -1.0,
        "enterprise_value_m": 34.6,
        "implied_2026e_multiple": 13.8
      },
      {
        "row_value": 2.5,
        "col_value": -0.5,
        "enterprise_value_m": 36.0,
        "implied_2026e_multiple": 14.4
      },
      {
        "row_value": 2.5,
        "col_value": 0.0,
        "enterprise_value_m": 37.5,
        "implied_2026e_multiple": 15.0
      },
      {
        "row_value": 2.5,
        "col_value": 0.5,
        "enterprise_value_m": 39.0,
        "implied_2026e_multiple": 15.6
      },
      {
        "row_value": 2.5,
        "col_value": 1.0,
        "enterprise_value_m": 40.6,
        "implied_2026e_multiple": 16.2
      }
    ]
  },
  "lbo_returns": {
    "ltv_pct": 40.0,
    "cost_of_debt_pct": 7.5,
    "cash_sweep_pct": 100.0,
    "transaction_fees_pct": 2.0,
    "default_hold_years": 5,
    "base_entry_multiple_2026e": 14.0,
    "standalone_exit_multiple": 14.0,
    "portfolio_rollup_exit_multiple": 16.0,
    "base_standalone_irr_pct": 10.0,
    "base_standalone_moic": 1.6,
    "portfolio_rollup_irr_pct": 13.3,
    "portfolio_rollup_moic": 1.9,
    "multiple_expansion_irr_uplift_bps": 330,
    "deleveraging_profile": [
      {
        "year_label": "Dec-26",
        "net_debt_to_ebitda": 5.6,
        "ending_net_debt_sekm": 13.99,
        "ebitda_50pct_sekm": 2.498
      },
      {
        "year_label": "Dec-27",
        "net_debt_to_ebitda": 4.8,
        "ending_net_debt_sekm": 12.34,
        "ebitda_50pct_sekm": 2.472
      },
      {
        "year_label": "Dec-28",
        "net_debt_to_ebitda": 4.0,
        "ending_net_debt_sekm": 10.52,
        "ebitda_50pct_sekm": 2.547
      },
      {
        "year_label": "Dec-29",
        "net_debt_to_ebitda": 3.1,
        "ending_net_debt_sekm": 8.53,
        "ebitda_50pct_sekm": 2.614
      },
      {
        "year_label": "Dec-30",
        "net_debt_to_ebitda": 2.3,
        "ending_net_debt_sekm": 6.36,
        "ebitda_50pct_sekm": 2.672
      },
      {
        "year_label": "Dec-31",
        "net_debt_to_ebitda": 1.4,
        "ending_net_debt_sekm": 4.0,
        "ebitda_50pct_sekm": 2.729
      }
    ],
    "entry_vs_exit_multiple_matrix": [
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "12.0x",
        "irr_pct": 11.5,
        "moic": 1.7
      },
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "13.0x",
        "irr_pct": 13.3,
        "moic": 1.9
      },
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "14.0x",
        "irr_pct": 15.1,
        "moic": 2.0
      },
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "15.0x",
        "irr_pct": 16.8,
        "moic": 2.2
      },
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "16.0x",
        "irr_pct": 18.3,
        "moic": 2.3
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "12.0x",
        "irr_pct": 8.8,
        "moic": 1.5
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "13.0x",
        "irr_pct": 10.7,
        "moic": 1.7
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "14.0x",
        "irr_pct": 12.5,
        "moic": 1.8
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "15.0x",
        "irr_pct": 14.1,
        "moic": 1.9
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "16.0x",
        "irr_pct": 15.7,
        "moic": 2.1
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "12.0x",
        "irr_pct": 6.2,
        "moic": 1.4
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "13.0x",
        "irr_pct": 8.2,
        "moic": 1.5
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "14.0x",
        "irr_pct": 10.0,
        "moic": 1.6
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "15.0x",
        "irr_pct": 11.7,
        "moic": 1.7
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "16.0x",
        "irr_pct": 13.3,
        "moic": 1.9
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "12.0x",
        "irr_pct": 3.8,
        "moic": 1.2
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "13.0x",
        "irr_pct": 5.8,
        "moic": 1.3
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "14.0x",
        "irr_pct": 7.6,
        "moic": 1.4
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "15.0x",
        "irr_pct": 9.4,
        "moic": 1.6
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "16.0x",
        "irr_pct": 11.0,
        "moic": 1.7
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "12.0x",
        "irr_pct": 1.5,
        "moic": 1.1
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "13.0x",
        "irr_pct": 3.5,
        "moic": 1.2
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "14.0x",
        "irr_pct": 5.4,
        "moic": 1.3
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "15.0x",
        "irr_pct": 7.1,
        "moic": 1.4
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "16.0x",
        "irr_pct": 8.8,
        "moic": 1.5
      }
    ],
    "entry_multiple_vs_exit_year_matrix": [
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "Dec-29",
        "irr_pct": 18.7,
        "moic": 1.7
      },
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "Dec-30",
        "irr_pct": 16.5,
        "moic": 1.8
      },
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "Dec-31",
        "irr_pct": 15.1,
        "moic": 2.0
      },
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "Dec-32",
        "irr_pct": 13.5,
        "moic": 2.1
      },
      {
        "entry_multiple_2026e": 12.0,
        "implied_purchase_price_sekm": 30.0,
        "col_key": "Dec-33",
        "irr_pct": 11.8,
        "moic": 2.2
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "Dec-29",
        "irr_pct": 14.1,
        "moic": 1.5
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "Dec-30",
        "irr_pct": 13.1,
        "moic": 1.6
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "Dec-31",
        "irr_pct": 12.5,
        "moic": 1.8
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "Dec-32",
        "irr_pct": 12.0,
        "moic": 2.0
      },
      {
        "entry_multiple_2026e": 13.0,
        "implied_purchase_price_sekm": 32.5,
        "col_key": "Dec-33",
        "irr_pct": 10.5,
        "moic": 2.0
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "Dec-29",
        "irr_pct": 9.8,
        "moic": 1.3
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "Dec-30",
        "irr_pct": 10.0,
        "moic": 1.5
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "Dec-31",
        "irr_pct": 10.0,
        "moic": 1.6
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "Dec-32",
        "irr_pct": 9.9,
        "moic": 1.8
      },
      {
        "entry_multiple_2026e": 14.0,
        "implied_purchase_price_sekm": 35.0,
        "col_key": "Dec-33",
        "irr_pct": 9.4,
        "moic": 1.9
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "Dec-29",
        "irr_pct": 5.8,
        "moic": 1.2
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "Dec-30",
        "irr_pct": 7.0,
        "moic": 1.3
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "Dec-31",
        "irr_pct": 7.6,
        "moic": 1.4
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "Dec-32",
        "irr_pct": 8.0,
        "moic": 1.6
      },
      {
        "entry_multiple_2026e": 15.0,
        "implied_purchase_price_sekm": 37.5,
        "col_key": "Dec-33",
        "irr_pct": 8.2,
        "moic": 1.7
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "Dec-29",
        "irr_pct": 2.1,
        "moic": 1.1
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "Dec-30",
        "irr_pct": 4.2,
        "moic": 1.2
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "Dec-31",
        "irr_pct": 5.4,
        "moic": 1.3
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "Dec-32",
        "irr_pct": 6.2,
        "moic": 1.4
      },
      {
        "entry_multiple_2026e": 16.0,
        "implied_purchase_price_sekm": 40.0,
        "col_key": "Dec-33",
        "irr_pct": 6.7,
        "moic": 1.6
      }
    ]
  },
  "football_field": [
    {
      "methodology": "Discounted Cash Flow",
      "assumptions_summary": "WACC: 8.5\u20139.5%; PGR: 1.0\u20132.0% (In-line with 3rd party valuation methodology)",
      "ev_low_sekm": 31.2,
      "ev_high_sekm": 38.7,
      "multiple_l3y_avg_low": 13.1,
      "multiple_l3y_avg_high": 16.2,
      "multiple_2026e_low": 12.5,
      "multiple_2026e_high": 15.5
    },
    {
      "methodology": "Precedent Transactions",
      "assumptions_summary": "L3Y avg. income: 12.0\u201314.0x (Non-controlling & similar scale songwriting catalogs)",
      "ev_low_sekm": 28.7,
      "ev_high_sekm": 33.5,
      "multiple_l3y_avg_low": 12.0,
      "multiple_l3y_avg_high": 14.0,
      "multiple_2026e_low": 11.5,
      "multiple_2026e_high": 13.4
    },
    {
      "methodology": "Leveraged Buy-Out (Standalone Exit)",
      "assumptions_summary": "Target IRR: 10\u201315%; Hold: 5 years; Exit multiple: 12.0x standalone",
      "ev_low_sekm": 27.2,
      "ev_high_sekm": 31.2,
      "multiple_l3y_avg_low": 11.4,
      "multiple_l3y_avg_high": 13.1,
      "multiple_2026e_low": 10.9,
      "multiple_2026e_high": 12.5
    },
    {
      "methodology": "Leveraged Buy-Out (Portfolio Roll-Up Exit)",
      "assumptions_summary": "Target IRR: 10\u201315%; Hold: 5 years; Exit multiple: 16.0x folded into scaled portfolio (Tenet/SPACE)",
      "ev_low_sekm": 33.5,
      "ev_high_sekm": 38.7,
      "multiple_l3y_avg_low": 14.0,
      "multiple_l3y_avg_high": 16.2,
      "multiple_2026e_low": 13.4,
      "multiple_2026e_high": 15.5
    }
  ],
  "collection_anomalies": [
    {
      "anomaly_id": "ANOMALY_I_UK_BMG_MECHANICALS",
      "title": "Anomaly I: UK Streaming Mechanicals Drop-Off (BMG-Specific)",
      "society_or_administrator": "BMG Rights Management Scandinavia AB",
      "territory": "United Kingdom (UK)",
      "rights_type": "Streaming Mechanicals",
      "estimated_annual_leakage_sek": 185000.0,
      "estimated_recoverable_arrears_sek": 370000.0,
      "root_cause_hypothesis": "UK streaming mechanicals on BMG-administered works (2008\u20132011 perimeter: `Don't You Worry Child`, `Save the World`, `Fade into Darkness`) dropped off sharply despite stable UK DSP consumption and uninterrupted STIM performance collections \u2014 indicating a BMG UK / MCPS / ICE registration or suspense-account routing break.",
      "remediation_action": "File formal ICE / MCPS / BMG UK work-registration audit and claim unallocated UK streaming mechanical suspense royalties from H2 2024\u20132026."
    },
    {
      "anomaly_id": "ANOMALY_II_US_LIVE_PERFORMANCE",
      "title": "Anomaly II: US Live Performance Income Materially Below Arena/Festival Touring Footprint",
      "society_or_administrator": "STIM -> ASCAP / BMI (US Reciprocal Collection)",
      "territory": "United States (US)",
      "rights_type": "Live Performance",
      "estimated_annual_leakage_sek": 240000.0,
      "estimated_recoverable_arrears_sek": 480000.0,
      "root_cause_hypothesis": "Both John Martin and Michel Zitron accounts show negligible US live performance income despite Swedish House Mafia, Ti\u00ebsto, and Martin Garrix headlining major US festivals (Ultra, EDC, Coachella) and arena dates performing `Don't You Worry Child`, `Save the World`, `Reload`, and `Red Lights`.",
      "remediation_action": "Submit setlist cue sheets and ISWC cross-registrations directly to ASCAP/BMI via STIM/publisher to trigger retroactive US live performance distributions."
    },
    {
      "anomaly_id": "ANOMALY_III_STIM_2023_FOREIGN_UNDERCOLLECTION",
      "title": "Historical Distortion: 2023 STIM Foreign Under-Collection (Explains ~80% of '23\u2013'24 Jump)",
      "society_or_administrator": "STIM (Foreign Reciprocal Societies)",
      "territory": "International / Ex-Sweden",
      "rights_type": "Performance & Streaming",
      "estimated_annual_leakage_sek": 0.0,
      "estimated_recoverable_arrears_sek": 0.0,
      "root_cause_hypothesis": "2023 total income (4.15m SEK) was artificially depressed because STIM under-collected in foreign territories during 2023. Remediation in early 2024 drove ~80% of the +33% headline revenue jump from 2023 to 2024 (5.52m SEK), meaning naive 2023\u20132025 CAGR (+6.1%) overstates organic growth while naive L3Y average (4.78m SEK) understates normalized run-rate.",
      "remediation_action": "Normalize 2023 baseline for STIM foreign catch-up when computing historical volatility and anchor valuation on 2026E normalized run-rate (5.00m SEK)."
    }
  ]
};

export const INSTITUTIONAL_BUYERS = [
  {
    "partner_id": "duetti",
    "partner_name": "Duetti",
    "deal_type": "FULL_OR_TRACK_BUYOUT",
    "decision_makers": [
      "Lior Tibon (CEO & Co-Founder)",
      "Lyva Corvo (Music Catalog Sales & Partnerships)"
    ],
    "contact_emails": [
      "lior@duetti.co",
      "lyva@duetti.co"
    ],
    "min_ltm_eur": 4500.0,
    "max_ltm_eur": 600000.0,
    "min_age_months": 12.0,
    "min_integrity_score": 70.0,
    "preferred_genres": [
      "rock_folk_country",
      "latin_afro",
      "rock_metal_country",
      "electronic_dance",
      "pop_indie",
      "hiphop_rnb_phonk",
      "pop_hiphop_rnb",
      "electronic_indie"
    ],
    "supported_rights": [
      "masters",
      "both"
    ],
    "target_multiple_range": "2.5x \u2013 6.5x LTM (track-by-track or full master buyout)",
    "thesis_summary": "Acquires independent master catalogs and individual sticky tracks ($5k\u2013$500k+ LTM) with >12m streaming history."
  },
  {
    "partner_id": "create_music_group",
    "partner_name": "Create Music Group",
    "deal_type": "LABEL_ACQUISITION_OR_JV",
    "decision_makers": [
      "Jonathan Strauss (CEO & Co-Founder)",
      "Steeven Leblanc (SVP, Corp Dev & M&A)"
    ],
    "contact_emails": [
      "jonathan@createmusicgroup.com",
      "steeven.leblanc@createmusicgroup.com"
    ],
    "min_ltm_eur": 15000.0,
    "max_ltm_eur": 5000000.0,
    "min_age_months": 9.0,
    "min_integrity_score": 70.0,
    "preferred_genres": [
      "latin_afro",
      "electronic_dance",
      "pop_indie",
      "hiphop_rnb_phonk",
      "pop_hiphop_rnb",
      "electronic_indie"
    ],
    "supported_rights": [
      "publishing",
      "masters",
      "both"
    ],
    "target_multiple_range": "3.0x \u2013 8.0x LTM (catalog acquisition, JV, or YouTube Content ID monetization)",
    "thesis_summary": "High-velocity buyer for Hip-Hop, Trap, Phonk, Electronic, and Dance/Pop catalogs with strong DSP & YouTube footprint."
  },
  {
    "partner_id": "beatbread",
    "partner_name": "beatBread",
    "deal_type": "ROYALTY_ADVANCE_FINANCING",
    "decision_makers": [
      "Peter Sinclair (CEO & Co-Founder)",
      "Andreea Gleeson (Chief Revenue Officer)"
    ],
    "contact_emails": [
      "peter@beatbread.com",
      "andreea.gleeson@beatbread.com"
    ],
    "min_ltm_eur": 2500.0,
    "max_ltm_eur": 1000000.0,
    "min_age_months": 6.0,
    "min_integrity_score": 60.0,
    "preferred_genres": [
      "rock_folk_country",
      "latin_afro",
      "lofi_chill",
      "rock_metal_country",
      "electronic_dance",
      "classical_jazz_instrumental",
      "pop_indie",
      "hiphop_rnb_phonk",
      "pop_hiphop_rnb",
      "electronic_indie",
      "ambient_functional"
    ],
    "supported_rights": [
      "masters",
      "both"
    ],
    "target_multiple_range": "1.5x \u2013 4.5x LTM recoupable advance (artist retains long-term ownership)",
    "thesis_summary": "Automated catalog & repertoire advances where independent artists/labels keep ownership after recoupment."
  },
  {
    "partner_id": "sound_royalties",
    "partner_name": "Sound Royalties",
    "deal_type": "ROYALTY_ADVANCE_FINANCING",
    "decision_makers": [
      "Alex Heiche (Founder & CEO)",
      "Reggie Calloway (VP of Music Royalty Funding)"
    ],
    "contact_emails": [
      "alex@soundroyalties.com",
      "rcalloway@soundroyalties.com"
    ],
    "min_ltm_eur": 4500.0,
    "max_ltm_eur": 2500000.0,
    "min_age_months": 12.0,
    "min_integrity_score": 65.0,
    "preferred_genres": [
      "rock_folk_country",
      "latin_afro",
      "lofi_chill",
      "rock_metal_country",
      "electronic_dance",
      "classical_jazz_instrumental",
      "pop_indie",
      "hiphop_rnb_phonk",
      "pop_hiphop_rnb",
      "electronic_indie",
      "ambient_functional"
    ],
    "supported_rights": [
      "publishing",
      "masters",
      "both"
    ],
    "target_multiple_range": "1.5x \u2013 5.0x LTM non-credit royalty financing (Masters, PRO, SoundExchange, Publishing)",
    "thesis_summary": "Royalty financing across Masters, PRO/Publishing, and SoundExchange without relinquishing permanent copyright."
  },
  {
    "partner_id": "anote_music",
    "partner_name": "ANote Music",
    "deal_type": "FRACTIONAL_CATALOG_MARKETPLACE",
    "decision_makers": [
      "Marzio Schena (CEO & Co-Founder)",
      "Nicola Meloni (Head of Operations)"
    ],
    "contact_emails": [
      "marzio@anotemusic.com",
      "nicola@anotemusic.com"
    ],
    "min_ltm_eur": 8000.0,
    "max_ltm_eur": 1500000.0,
    "min_age_months": 24.0,
    "min_integrity_score": 75.0,
    "preferred_genres": [
      "rock_folk_country",
      "latin_afro",
      "rock_metal_country",
      "electronic_dance",
      "classical_jazz_instrumental",
      "pop_indie",
      "electronic_indie"
    ],
    "supported_rights": [
      "publishing",
      "masters",
      "both"
    ],
    "target_multiple_range": "4.0x \u2013 9.0x LTM (10%\u201350% partial royalty share listing on European marketplace)",
    "thesis_summary": "European marketplace for mature catalogs (>=24m history) listing partial or full passive royalty shares."
  },
  {
    "partner_id": "royalty_exchange",
    "partner_name": "Royalty Exchange",
    "deal_type": "FRACTIONAL_CATALOG_MARKETPLACE",
    "decision_makers": [
      "Keegan Gaeng (Director, Artist & Label Relations)"
    ],
    "contact_emails": [
      "keegan.g@royaltyexchange.net"
    ],
    "min_ltm_eur": 4500.0,
    "max_ltm_eur": 2000000.0,
    "min_age_months": 18.0,
    "min_integrity_score": 70.0,
    "preferred_genres": [
      "rock_folk_country",
      "latin_afro",
      "lofi_chill",
      "rock_metal_country",
      "electronic_dance",
      "classical_jazz_instrumental",
      "pop_indie",
      "hiphop_rnb_phonk",
      "pop_hiphop_rnb",
      "electronic_indie",
      "ambient_functional"
    ],
    "supported_rights": [
      "publishing",
      "masters",
      "both"
    ],
    "target_multiple_range": "3.0x \u2013 8.5x LTM (10-year term or life-of-rights institutional auction)",
    "thesis_summary": "Liquid auction & private syndicate marketplace for 10-year term or life-of-rights royalty streams."
  },
  {
    "partner_id": "songvest",
    "partner_name": "SongVest",
    "deal_type": "FRACTIONAL_CATALOG_MARKETPLACE",
    "decision_makers": [
      "Sean Peace (Founder & CEO)"
    ],
    "contact_emails": [
      "sean@songvest.com"
    ],
    "min_ltm_eur": 4000.0,
    "max_ltm_eur": 750000.0,
    "min_age_months": 18.0,
    "min_integrity_score": 70.0,
    "preferred_genres": [
      "rock_folk_country",
      "rock_metal_country",
      "classical_jazz_instrumental",
      "pop_indie",
      "pop_hiphop_rnb",
      "hiphop_rnb_phonk"
    ],
    "supported_rights": [
      "publishing",
      "masters",
      "both"
    ],
    "target_multiple_range": "3.0x \u2013 7.0x LTM (fractional SongShares & private institutional buyers)",
    "thesis_summary": "Fractional and private-syndicate buyer for established writer/producer and indie master catalogs."
  },
  {
    "partner_id": "symphonic_distribution",
    "partner_name": "Symphonic Distribution",
    "deal_type": "DISTRIBUTION_ADVANCE",
    "decision_makers": [
      "Jorge Brea (Founder & CEO)",
      "Oz McGuire (VP of A&R and Client Development)"
    ],
    "contact_emails": [
      "jorge@symdistro.com",
      "ozmcguire@symdistro.com"
    ],
    "min_ltm_eur": 4000.0,
    "max_ltm_eur": 800000.0,
    "min_age_months": 6.0,
    "min_integrity_score": 65.0,
    "preferred_genres": [
      "latin_afro",
      "electronic_dance",
      "pop_indie",
      "hiphop_rnb_phonk",
      "pop_hiphop_rnb",
      "electronic_indie"
    ],
    "supported_rights": [
      "masters",
      "both"
    ],
    "target_multiple_range": "1.5x \u2013 4.0x LTM distribution transfer advance or catalog acquisition",
    "thesis_summary": "Strong fit for Latin, Electronic, Afro, and Hip-Hop indie labels/artists open to distribution transfer or buyout."
  },
  {
    "partner_id": "sagos_distro_solid_gold",
    "partner_name": "Sagos Distro / Solid Gold Global",
    "deal_type": "FULL_OR_TRACK_BUYOUT",
    "decision_makers": [
      "Partnerships & Acquisitions Team (Solid Gold Global Labs / Sagos Distro)"
    ],
    "contact_emails": [
      "info@sagosdistro.com",
      "info@solidgoldglobal.co.site"
    ],
    "min_ltm_eur": 2500.0,
    "max_ltm_eur": 500000.0,
    "min_age_months": 6.0,
    "min_integrity_score": 65.0,
    "preferred_genres": [
      "hiphop_rnb_phonk",
      "pop_hiphop_rnb",
      "latin_afro",
      "pop_indie"
    ],
    "supported_rights": [
      "publishing",
      "masters",
      "both"
    ],
    "target_multiple_range": "2.5x \u2013 6.0x LTM (full or partial rights acquisition + international distribution expansion)",
    "thesis_summary": "Acquires independent artist, producer, and label catalogs with strong focus on African, Caribbean, Hip-Hop/R&B, and Gospel repertoires."
  }
];

export const STUDIO_HTML = "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>SPACE Institutional Catalog Valuation Memo Studio | Claude + Autumn Billing + DTW DCF</title>\n<meta name=\"description\" content=\"Generate a 19-slide 16:9 institutional music catalog valuation memo powered by SPACE 10,000-path Monte Carlo DCF, Dynamic Time Warping (DTW) decay matching, and TypeSafe AI (JEV) forensics.\">\n<meta name=\"robots\" content=\"index, follow\">\n<link rel=\"canonical\" href=\"https://spacemusic.io/valuation-memo/\">\n<style>\n  * { box-sizing: border-box; }\n  body {\n    margin: 0;\n    background: #0D0E11;\n    color: #F5F6F8;\n    font-family: \"Inter\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;\n  }\n  .topbar {\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    padding: 20px 48px;\n    border-bottom: 1px solid #1E2330;\n  }\n  .brand { font-size: 18px; font-weight: 800; letter-spacing: 0.18em; }\n  .badge {\n    font-family: monospace;\n    font-size: 11px;\n    color: #84B1FF;\n    background: rgba(132, 177, 255, 0.12);\n    border: 1px solid rgba(132, 177, 255, 0.3);\n    padding: 5px 12px;\n    border-radius: 999px;\n  }\n  .container {\n    max-width: 1180px;\n    margin: 36px auto;\n    padding: 0 24px;\n    display: grid;\n    grid-template-columns: 440px 1fr;\n    gap: 32px;\n  }\n  .panel {\n    background: #141720;\n    border: 1px solid #252A3A;\n    border-radius: 10px;\n    padding: 26px;\n  }\n  h1 { font-size: 26px; margin: 0 0 8px; letter-spacing: -0.02em; }\n  p.lead { font-size: 13.5px; color: #9BA3B8; line-height: 1.5; margin: 0 0 20px; }\n  label { display: block; font-size: 12px; color: #B4BCCF; margin: 12px 0 5px; font-weight: 500; }\n  input, select, textarea {\n    width: 100%;\n    padding: 10px 12px;\n    background: #0D0E11;\n    border: 1px solid #2A3145;\n    border-radius: 6px;\n    color: #FFFFFF;\n    font-size: 13px;\n  }\n  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }\n  .btn-primary {\n    margin-top: 18px;\n    width: 100%;\n    padding: 13px;\n    background: #2356C8;\n    color: #FFFFFF;\n    border: none;\n    border-radius: 6px;\n    font-weight: 700;\n    font-size: 14px;\n    cursor: pointer;\n  }\n  .btn-primary:hover { background: #2D64DF; }\n  .preview-frame {\n    width: 100%;\n    height: 640px;\n    border: 1px solid #252A3A;\n    border-radius: 8px;\n    background: #090A0D;\n  }\n  .action-bar {\n    display: none;\n    margin-bottom: 16px;\n    padding: 14px 18px;\n    background: #171D2B;\n    border: 1px solid #84B1FF;\n    border-radius: 8px;\n    justify-content: space-between;\n    align-items: center;\n  }\n  .action-links a {\n    display: inline-block;\n    margin-left: 10px;\n    padding: 9px 16px;\n    border-radius: 6px;\n    font-size: 13px;\n    font-weight: 700;\n    text-decoration: none;\n  }\n  .btn-pdf { background: #84B1FF; color: #0D0E11; }\n  .btn-stripe { background: #F99441; color: #0D0E11; }\n  .plans-grid {\n    display: grid;\n    grid-template-columns: repeat(3, 1fr);\n    gap: 12px;\n    margin-bottom: 16px;\n  }\n  .plan-card {\n    background: #141720;\n    border: 1px solid #252A3A;\n    border-radius: 8px;\n    padding: 14px;\n    font-size: 12px;\n  }\n  .plan-card strong { font-size: 13px; color: #84B1FF; display: block; margin-bottom: 4px; }\n  .plan-price { font-size: 16px; font-weight: 800; color: #FFFFFF; margin: 6px 0; }\n</style>\n</head>\n<body>\n  <div class=\"topbar\">\n    <div class=\"brand\">SPACE</div>\n    <div class=\"badge\">CLAUDE + AUTUMN BILLING \u00b7 19-SLIDE 16:9 INVESTMENT MEMO</div>\n  </div>\n  <div class=\"container\">\n    <div class=\"panel\">\n      <h1>Generate Catalog Investment Memo</h1>\n      <p class=\"lead\">\n        Run our 10,000-path Monte Carlo DCF, Dynamic Time Warping (DTW), and TypeSafe AI (JEV)\n        forensics engine. Preview Slides 01\u201302 free, or unlock the full 19-slide 16:9 PDF via Autumn + Stripe ($299 single memo or $499/mo Desk Pass).\n      </p>\n      <form id=\"memoForm\">\n        <div class=\"row-2\">\n          <div>\n            <label>Artist or Label Name</label>\n            <input type=\"text\" id=\"artist_name\" value=\"HMWME\" required>\n          </div>\n          <div>\n            <label>Catalog Title</label>\n            <input type=\"text\" id=\"catalog_title\" value=\"The Family of One\">\n          </div>\n        </div>\n        <div class=\"row-2\">\n          <div>\n            <label>Customer Email / Autumn ID</label>\n            <input type=\"email\" id=\"contact_email\" placeholder=\"mgmt@hmwme.com\">\n          </div>\n          <div>\n            <label>Primary Distributor</label>\n            <input type=\"text\" id=\"distributor\" value=\"DistroKid + Amuse\">\n          </div>\n        </div>\n        <div class=\"row-2\">\n          <div>\n            <label>Claimed / Trailing LTM ($ USD)</label>\n            <input type=\"number\" id=\"ltm_amount\" value=\"80000\" step=\"100\">\n          </div>\n          <div>\n            <label>Customer Session Token (Optional)</label>\n            <input type=\"text\" id=\"customer_token\" placeholder=\"ctok_... (for existing Desk Pass)\">\n          </div>\n        </div>\n        <label>Paste Raw Distributor CSV / TSV Rows (Optional \u2014 upgrades to Stage 2 Verified)</label>\n        <textarea id=\"raw_csv\" rows=\"4\" placeholder=\"reporting_month,title,isrc,store,country,quantity,net_royalty_usd...\"></textarea>\n        <label>Autumn Plan (`billing.attach` / `balances.check`)</label>\n        <select id=\"plan_tier\">\n          <option value=\"SINGLE_MEMO_299\">single_memo_299 \u2014 Single 19-Slide Memo PDF ($299 / \u20ac275)</option>\n          <option value=\"DESK_PASS_499\">desk_pass_499 \u2014 Label / Manager Desk Pass (10 Memos/mo \u00b7 $499/mo)</option>\n        </select>\n        <button type=\"submit\" class=\"btn-primary\">Run Engine &amp; Build 19-Slide Memo</button>\n      </form>\n    </div>\n    <div>\n      <div id=\"autumnPlansGrid\" class=\"plans-grid\"></div>\n      <div id=\"actionBar\" class=\"action-bar\">\n        <div id=\"statusSummary\" style=\"font-size: 13px;\"></div>\n        <div class=\"action-links\" id=\"actionLinks\"></div>\n      </div>\n      <iframe id=\"deckIframe\" class=\"preview-frame\" title=\"SPACE 19-Slide Investment Memo Preview\"></iframe>\n    </div>\n  </div>\n<script>\nconst MEMO_API_BASE = (window.location.hostname === \"localhost\" || window.location.hostname === \"127.0.0.1\") ? \"\" : \"https://spacemusic-memo-studio.samplehubkupp.workers.dev\";\nfunction absMemoUrl(u) {\n  if (!u) return u;\n  return (u.startsWith(\"/\") && MEMO_API_BASE) ? (MEMO_API_BASE + u) : u;\n}\nasync function loadAutumnCatalogPlans() {\n  var emailVal = document.getElementById(\"contact_email\").value || \"\";\n  var qs = emailVal ? \"?customer_id=\" + encodeURIComponent(emailVal) : \"\";\n  var res = await fetch(MEMO_API_BASE + \"/catalog-review/paid-memo/autumn/plans\" + qs);\n  if (!res.ok) return;\n  var data = await res.json();\n  var grid = document.getElementById(\"autumnPlansGrid\");\n  if (!grid || !data.plans) return;\n  grid.innerHTML = data.plans.map(function(p) {\n    var priceStr = p.amount_usd != null ? (\"$\" + p.amount_usd + (p.interval === \"month\" ? \"/mo\" : \" one-off\")) : \"Free (auto-enabled)\";\n    var itemsStr = (p.items || []).map(function(i) { return i.primary_text || (i.included + \" \" + i.feature_id); }).join(\" \u00b7 \");\n    return '<div class=\"plan-card\"><strong>' + p.name + ' (' + p.plan_id + ')</strong><div class=\"plan-price\">' + priceStr + '</div><div style=\"color:#9BA3B8\">' + itemsStr + '</div></div>';\n  }).join(\"\");\n}\nloadAutumnCatalogPlans();\n(async function checkCheckoutReturnParams() {\n  var params = new URLSearchParams(window.location.search);\n  var orderId = params.get(\"order_id\");\n  var returnToken = params.get(\"return_token\");\n  var sessionId = params.get(\"session_id\") || \"\";\n  if (orderId && returnToken) {\n    var retRes = await fetch(MEMO_API_BASE + \"/catalog-review/paid-memo/return?order_id=\" + encodeURIComponent(orderId) + \"&session_id=\" + encodeURIComponent(sessionId) + \"&return_token=\" + encodeURIComponent(returnToken));\n    if (retRes.ok) {\n      var retData = await retRes.json();\n      var bar = document.getElementById(\"actionBar\");\n      var links = document.getElementById(\"actionLinks\");\n      bar.style.display = \"flex\";\n      document.getElementById(\"statusSummary\").innerHTML = \"<strong>\" + retData.order_id + \"</strong> \u00b7 Payment Status: <strong>PAID</strong>\";\n      document.getElementById(\"deckIframe\").src = absMemoUrl(retData.unlocked_html_url);\n      links.innerHTML = '<a class=\"btn-pdf\" href=\"' + absMemoUrl(retData.unlocked_pdf_url) + '\">Download 19-Slide PDF</a>';\n    }\n  }\n})();\ndocument.getElementById(\"memoForm\").addEventListener(\"submit\", async function(e) {\n  e.preventDefault();\n  var payload = {\n    artist_or_label_name: document.getElementById(\"artist_name\").value,\n    catalog_title: document.getElementById(\"catalog_title\").value,\n    contact_email: document.getElementById(\"contact_email\").value || null,\n    declared_ltm_amount: parseFloat(document.getElementById(\"ltm_amount\").value || \"50000\"),\n    distributor: document.getElementById(\"distributor\").value,\n    raw_statement_csv: document.getElementById(\"raw_csv\").value || null,\n    plan_tier: document.getElementById(\"plan_tier\").value,\n    customer_token: document.getElementById(\"customer_token\").value || null\n  };\n  var res = await fetch(MEMO_API_BASE + \"/catalog-review/paid-memo/checkout\", {\n    method: \"POST\",\n    headers: { \"Content-Type\": \"application/json\" },\n    body: JSON.stringify(payload)\n  });\n  if (!res.ok) return;\n  var data = await res.json();\n  var bar = document.getElementById(\"actionBar\");\n  var links = document.getElementById(\"actionLinks\");\n  bar.style.display = \"flex\";\n  document.getElementById(\"statusSummary\").innerHTML =\n    \"<strong>\" + data.deal_code + \"</strong> \u00b7 Standalone Base: <strong>\" + data.teaser_standalone_base_usd +\n    \"</strong> \u00b7 WACC: \" + data.teaser_wacc_pct + \"% \u00b7 Autumn Credits Remaining: <strong>\" + data.autumn_credits_remaining + \"</strong>\";\n  if (data.payment_status === \"PAID\" && data.unlocked_pdf_url) {\n    document.getElementById(\"deckIframe\").src = absMemoUrl(data.unlocked_html_url);\n    links.innerHTML = '<a class=\"btn-pdf\" href=\"' + absMemoUrl(data.unlocked_pdf_url) + '\">Download 19-Slide PDF</a>';\n  } else {\n    document.getElementById(\"deckIframe\").src = absMemoUrl(data.locked_preview_url);\n    links.innerHTML = '<a class=\"btn-stripe\" href=\"' + absMemoUrl(data.checkout_url) + '\" target=\"_blank\">Unlock All 19 Slides ($' + data.amount_usd + ')</a>';\n  }\n});\n</script>\n</body>\n</html>\n";
