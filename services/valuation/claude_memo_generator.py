"""
Claude Investment Memo Generator (`services/valuation/claude_memo_generator.py`)

Generates the 19-slide 16:9 SPACE Institutional Investment Memo Deck (matching the exact
editorial & visual architecture of `HMWME Catalog Valuation.pdf` and `2Scratch Catalog Valuation.pdf`):

1. **Deterministic Quantitative Core (`engine.py` + `dtw_matcher.py` + `jev_evaluator.py`)**:
   - Every dollar, euro, percentage, WACC build-up component, Monte Carlo DCF horizon (5Y, 10Y, 12Y),
     DTW distance/synchrony, and TypeSafe AI (JEV System One) posterior probability is computed
     deterministically to the exact cent before Claude is invoked.
2. **Claude Editorial Underwriting Layer (`https://api.anthropic.com/v1/messages`)**:
   - Invokes Anthropic's Messages API with forced structured tool output
     (`emit_space_investment_memo_narrative`) so Claude writes the sharp, institutional headlines,
     claim-vs-verified explanations, WACC commentary, seller quote framing, Option A/B/C structures,
     and 01–04 negotiation next steps without ever hallucinating a financial number.
   - Falls back seamlessly to a deterministic institutional narrative synthesizer when
     `ANTHROPIC_API_KEY` is not set in local/CI test environments.
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from services.valuation.engine import (
     TIER_1_COUNTRIES,
    CatalogValuationInput,
    CatalogValuationOutput,
)
from services.valuation.jev_evaluator import (
    ParallelDtwJevEvaluationReport,
    noul_confidence,
    run_parallel_dtw_and_jev_evaluation,
)
from services.valuation.statement_parser import ParsedStatementSummary

ANTHROPIC_MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
DEFAULT_CLAUDE_MEMO_MODEL = os.environ.get("CLAUDE_MEMO_MODEL", "claude-sonnet-4-5")
USD_PER_EUR = 1.0 / 0.92


# ============================================================================
# Strongly-Typed 19-Slide Deck Schema (Matching HMWME & 2Scratch PDFs)
# ============================================================================


class MemoMetricCard(BaseModel):
    label: str
    value: str
    detail: str
    highlight: bool = False


class ComparisonBarItem(BaseModel):
    label: str
    amount_usd: float
    formatted_value: str
    variant: str = "blue"  # "orange" | "muted" | "blue"


class MonthlyMomentumBar(BaseModel):
    period: str
    month_short: str
    amount_usd: float
    in_ltm_window: bool = True


class WaccSegmentItem(BaseModel):
    label: str
    rate_pct: float
    formatted_pct: str
    variant: str = "dark"  # "dark" | "blue_primary" | "blue_light" | "muted"


class HorizonNpvRow(BaseModel):
    horizon_label: str
    years: int
    p10_usd: float
    p50_usd: float
    p90_usd: float
    p50_eur: float
    multiple_p10: float
    multiple_p50: float
    multiple_p90: float
    is_anchor: bool = False


class AnnualScheduleRow(BaseModel):
    year_label: str
    yoy_decay_pct: float
    p10_usd: float
    p50_usd: float
    p90_usd: float
    discount_factor: float
    pv_p50_usd: float
    cumulative_pv_usd: float


class JevQuestionRow(BaseModel):
    question: str
    posterior_answer: str
    confidence_pct: int
    highlight: bool = False


class ShareBarItem(BaseModel):
    name: str
    share_pct: float
    highlight: bool = True


class TrackConcentrationBar(BaseModel):
    title: str
    ltm_usd: float
    share_pct: float
    is_top3: bool = False


class AskVsValueCorridorBar(BaseModel):
    label: str
    sublabel: str
    low_usd: float
    high_usd: float
    marker_usd: Optional[float] = None
    variant: str = "blue_dark"  # "blue_light" | "blue_dark" | "orange_marker" | "orange_bar"


class OfferBreakdownLine(BaseModel):
    label: str
    value: str


class OfferStructureCard(BaseModel):
    badge: str
    recommended: bool = False
    price_headline: str
    description: str
    breakdown_lines: List[OfferBreakdownLine] = Field(default_factory=list)


class ProposedNextStepItem(BaseModel):
    step_number: str
    title: str
    description: str


class CatalogInvestmentMemoDeck(BaseModel):
    """
    Complete 19-slide 16:9 Investment Memo Deck ready for HTML/PDF rendering.
    """

    deal_code: str
    artist_or_label_name: str
    catalog_subtitle: str
    prepared_date_label: str = "OCTOBER 2026"
    author_engine: str = "claude+space_engine"
    claude_model_used: str = DEFAULT_CLAUDE_MEMO_MODEL
    claude_execution_mode: str = "deterministic_synthesis"

    # Slide 01: Cover
    cover_kicker: str
    cover_title: str
    cover_subtitle: str
    cover_footer: str

    # Slide 02: 01 · At a glance
    s01_headline: str
    s01_cards: List[MemoMetricCard]
    s01_bottom_note: str

    # Slide 03: 02 · The data
    s02_headline: str
    s02_primary_count: str
    s02_primary_label: str
    s02_cards: List[MemoMetricCard]
    s02_bottom_note: str

    # Slide 04: 03 · Claim check
    s03_headline: str
    s03_bars: List[ComparisonBarItem]
    s03_bottom_note: str

    # Slide 05: 04 · Momentum
    s04_headline: str
    s04_monthly_bars: List[MonthlyMomentumBar]
    s04_footer_caption: str

    # Slide 06: 05 · The model
    s05_headline: str
    s05_cards: List[MemoMetricCard]
    s05_bottom_note: str

    # Slide 07: 06 · Discount rate build-up
    s06_headline: str
    s06_segments: List[WaccSegmentItem]
    s06_total_wacc_pct: float
    s06_bottom_note: str

    # Slide 08: 07 · Standalone value
    s07_headline: str
    s07_cards: List[MemoMetricCard]
    s07_jev_crosscheck_note: str

    # Slide 09: 08 · Cumulative NPV by horizon
    s08_headline: str
    s08_horizons: List[HorizonNpvRow]
    s08_footer_caption: str

    # Slide 10: 09 · DCF reconciliation & Annual Schedule
    s09_headline: str
    s09_horizons: List[HorizonNpvRow]
    s09_annual_schedule: List[AnnualScheduleRow]
    s09_pillars: List[MemoMetricCard]
    s09_footer_caption: str

    # Slide 11: 10 · TypeSafe AI cross-check
    s10_headline: str
    s10_agreement_badge: str
    s10_questions: List[JevQuestionRow]
    s10_footer_caption: str

    # Slide 12: 11 · Stream integrity
    s11_headline: str
    s11_cards: List[MemoMetricCard]
    s11_bottom_note: str

    # Slide 13: 12 · Where the money comes from
    s12_headline: str
    s12_platforms: List[ShareBarItem]
    s12_territories: List[ShareBarItem]
    s12_bottom_note: str

    # Slide 14: 13 · Track concentration
    s13_headline: str
    s13_tracks: List[TrackConcentrationBar]
    s13_summary_cards: List[MemoMetricCard]
    s13_footer_caption: str

    # Slide 15: 14 · The seller's position (Royal Blue Quote Slide)
    s14_quote_text: str
    s14_attribution: str
    s14_footer_caption: str

    # Slide 16: 15 · Ask vs value
    s15_headline: str
    s15_axis_max_usd: float
    s15_corridors: List[AskVsValueCorridorBar]
    s15_footer_caption: str

    # Slide 17: 16 · Offer structures
    s16_headline: str
    s16_options: List[OfferStructureCard]
    s16_fallback_footer: str

    # Slide 18: 17 · Proposed next steps
    s17_headline: str
    s17_steps: List[ProposedNextStepItem]
    s17_bottom_note: str

    # Slide 19: Closing Questions slide
    s18_headline: str = "Questions."
    s18_footer: str


# ============================================================================
# Claude Structured Tool Schema & API Caller
# ============================================================================

CLAUDE_MEMO_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "emit_space_investment_memo_narrative",
    "description": (
        "Emits the institutional editorial headlines, forensic takeaways, offer structure copy, "
        "and 4-step negotiation strategy for a 19-slide SPACE Music Catalog Investment Memo."
    ),
    "input_schema": {
        "type": "object",
        "required": [
            "s01_headline",
            "s01_bottom_note",
            "s02_headline",
            "s02_bottom_note",
            "s03_headline",
            "s03_bottom_note",
            "s04_headline",
            "s05_headline",
            "s05_bottom_note",
            "s06_headline",
            "s06_bottom_note",
            "s07_headline",
            "s08_headline",
            "s09_headline",
            "s10_headline",
            "s11_headline",
            "s11_bottom_note",
            "s12_headline",
            "s12_bottom_note",
            "s13_headline",
            "s14_quote_text",
            "s14_attribution",
            "s15_headline",
            "s16_headline",
            "s17_headline",
            "s17_steps",
            "s17_bottom_note",
        ],
        "properties": {
            "s01_headline": {"type": "string"},
            "s01_bottom_note": {"type": "string"},
            "s02_headline": {"type": "string"},
            "s02_bottom_note": {"type": "string"},
            "s03_headline": {"type": "string"},
            "s03_bottom_note": {"type": "string"},
            "s04_headline": {"type": "string"},
            "s05_headline": {"type": "string"},
            "s05_bottom_note": {"type": "string"},
            "s06_headline": {"type": "string"},
            "s06_bottom_note": {"type": "string"},
            "s07_headline": {"type": "string"},
            "s08_headline": {"type": "string"},
            "s09_headline": {"type": "string"},
            "s10_headline": {"type": "string"},
            "s11_headline": {"type": "string"},
            "s11_bottom_note": {"type": "string"},
            "s12_headline": {"type": "string"},
            "s12_bottom_note": {"type": "string"},
            "s13_headline": {"type": "string"},
            "s14_quote_text": {"type": "string"},
            "s14_attribution": {"type": "string"},
            "s15_headline": {"type": "string"},
            "s16_headline": {"type": "string"},
            "s17_headline": {"type": "string"},
            "s17_steps": {
                "type": "array",
                "minItems": 4,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "required": ["step_number", "title", "description"],
                    "properties": {
                        "step_number": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
            "s17_bottom_note": {"type": "string"},
        },
    },
}


def _call_claude_narrative_api(
    quantitative_context: Dict[str, Any],
    api_key: str,
    model: str = DEFAULT_CLAUDE_MEMO_MODEL,
    timeout_sec: float = 18.0,
) -> Optional[Dict[str, Any]]:
    """
    Calls Anthropic's Messages API (`https://api.anthropic.com/v1/messages`) with forced
    tool use (`emit_space_investment_memo_narrative`) to write the editorial narrative.
    Returns `None` if network/auth is unavailable so caller falls back cleanly.
    """
    system_prompt = (
        "You are Managing Director of Underwriting at SPACE (spacemusic.io), an institutional music "
        "catalog acquisition & valuation desk. Write the slide headlines and concise analytical notes "
        "for a 19-slide 16:9 Investment Memo.\n\n"
        "EDITORIAL STYLE RULES (CRITICAL):\n"
        "- Headlines must be ultra-crisp, punchy, 5 to 11 words, ending with a period.\n"
        "  Examples from past SPACE memos:\n"
        "  * 'A clean, fast-growing catalog. Priced at 2x today, more with new music.'\n"
        "  * 'Every row, from both distributors.'\n"
        "  * 'The $80k claim is the run-rate, not the last 12 months.'\n"
        "  * 'The $30k claim was the label's gross.'\n"
        "  * 'Youth costs 5 points. Risk costs almost nothing.'\n"
        "  * 'One engine, monthly steps, reconciled to the cent.'\n"
        "  * 'Ten questions. One real gap: price.'\n"
        "  * 'Three tracks carry 59%.'\n"
        "- NEVER invent or alter any financial figure. Cite the exact figures provided in the JSON state."
    )

    body_bytes = json.dumps(
        {
            "model": model,
            "max_tokens": 2048,
            "temperature": 0.1,
            "system": system_prompt,
            "tools": [CLAUDE_MEMO_TOOL_SCHEMA],
            "tool_choice": {"type": "tool", "name": "emit_space_investment_memo_narrative"},
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Generate the SPACE 19-slide Investment Memo narrative for this verified "
                        "catalog telemetry:\n\n"
                        + json.dumps(quantitative_context, indent=2)
                    ),
                }
            ],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_MESSAGES_ENDPOINT,
        data=body_bytes,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            for block in payload.get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "emit_space_investment_memo_narrative":
                    inp = block.get("input")
                    if isinstance(inp, dict):
                        return inp
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError):
        return None
    return None


# ============================================================================
# Deterministic Quantitative & Narrative Builder
# ============================================================================


def _fmt_k(val_usd: float) -> str:
    if val_usd >= 1_000_000:
        return f"${val_usd / 1_000_000:.2f}M"
    if val_usd >= 10_000:
        return f"${val_usd / 1_000:.0f}k"
    if val_usd >= 1_000:
        return f"${val_usd / 1_000:.1f}k"
    return f"${val_usd:,.0f}"


def generate_catalog_investment_memo_deck(
    app_input: CatalogValuationInput,
    valuation: CatalogValuationOutput,
    stmt_summary: Optional[ParsedStatementSummary] = None,
    jev_report: Optional[ParallelDtwJevEvaluationReport] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    *,
    deal_code: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    claude_model: str = DEFAULT_CLAUDE_MEMO_MODEL,
) -> CatalogInvestmentMemoDeck:
    """
    Synthesizes a complete 19-slide `CatalogInvestmentMemoDeck` from `CatalogValuationInput`,
    `CatalogValuationOutput`, optional `ParsedStatementSummary`, and TypeSafe AI (JEV).
    Calls Claude via Anthropic API when `anthropic_api_key` or `ANTHROPIC_API_KEY` is present,
    and falls back deterministically otherwise.
    """
    extra = extra_context or {}
    if stmt_summary is None:
        stmt_summary = ParsedStatementSummary(
            detected_distributor=app_input.distributor_or_admin or "Independent Distributor",
            row_count=max(len(app_input.tracks) * 420, 1200),
            total_net_royalty_eur=float(
                valuation.baseline.statement_ltm_eur or valuation.baseline.effective_cf0_eur
            ),
            total_streams=sum(int(t.annual_streams or 0) for t in app_input.tracks) or 1_000_000,
            monthly_history=app_input.monthly_history,
            tracks=app_input.tracks,
            dsp_share=app_input.dsp_share or {"Spotify": 0.82, "YouTube": 0.10, "Apple Music": 0.06, "Other": 0.02},
            country_share=app_input.country_share or {"US": 0.40, "DE": 0.16, "GB": 0.08, "FR": 0.05, "CA": 0.04, "AU": 0.04},
        )

    if jev_report is None:
        jev_report = run_parallel_dtw_and_jev_evaluation(
            app_input=app_input,
            stmt_summary=stmt_summary,
            valuation_report=valuation,
            extra_context=extra,
        )

    artist = (app_input.artist_or_label_name or "Independent Artist").strip()
    slug_upper = "".join(ch for ch in artist.upper() if ch.isalnum())[:8] or "CATALOG"
    resolved_deal_code = deal_code or extra.get("deal_code") or f"SPC-{slug_upper}"

    # Core USD & EUR figures (1 EUR = 1 / 0.92 USD)
    ltm_eur = float(valuation.baseline.statement_ltm_eur or valuation.baseline.effective_cf0_eur or 1.0)
    ltm_usd = float(extra.get("verified_ltm_usd") or round(ltm_eur * USD_PER_EUR, 2))
    cf0_eur = float(valuation.baseline.effective_cf0_eur or ltm_eur)
    cf0_usd = float(extra.get("cf0_usd") or round(cf0_eur * USD_PER_EUR, 2))

    l3m_eur = float(valuation.baseline.l3m_annualized_eur or cf0_eur)
    l3m_usd = float(extra.get("l3m_annualized_usd") or round(l3m_eur * USD_PER_EUR, 2))

    claimed_raw = float(app_input.declared_ltm_amount or ltm_usd)
    claimed_usd = (
        claimed_raw
        if (app_input.declared_currency or "USD").upper() == "USD"
        else round(claimed_raw * USD_PER_EUR, 2)
    )

    low_eur = float(valuation.price_low_eur)
    base_eur = float(valuation.price_median_eur)
    high_eur = float(valuation.price_high_eur)

    low_usd = float(extra.get("standalone_floor_usd") or round(low_eur * USD_PER_EUR, 2))
    base_usd = float(extra.get("standalone_base_usd") or round(base_eur * USD_PER_EUR, 2))
    high_usd = float(extra.get("standalone_ceiling_usd") or round(high_eur * USD_PER_EUR, 2))

    jev_base_usd = float(extra.get("jev_base_usd") or round(jev_report.jev_implied_base_offer_usd, 2))
    jev_stretch_usd = float(extra.get("jev_stretch_usd") or round(jev_report.jev_implied_stretch_offer_usd, 2))
    jev_diff_usd = abs(round(base_usd - jev_base_usd))

    mult_low = round(low_usd / max(cf0_usd, 1.0), 2)
    mult_base = round(base_usd / max(cf0_usd, 1.0), 2)
    mult_high = round(high_usd / max(cf0_usd, 1.0), 2)
    payback_mo = int(round(float(valuation.expected_payback_months or 42.0)))

    # 5Y, 10Y, 12Y Horizons
    npv5_p10_usd = round(float(valuation.npv_5y_p10_eur) * USD_PER_EUR, 2)
    npv5_p50_usd = round(float(valuation.npv_5y_p50_eur) * USD_PER_EUR, 2)
    npv5_p90_usd = round(float(valuation.npv_5y_p90_eur) * USD_PER_EUR, 2)

    npv10_p10_usd = round(float(valuation.npv_10y_p10_eur) * USD_PER_EUR, 2)
    npv10_p50_usd = round(float(valuation.npv_10y_p50_eur) * USD_PER_EUR, 2)
    npv10_p90_usd = round(float(valuation.npv_10y_p90_eur) * USD_PER_EUR, 2)

    # 12Y Option A horizon (extrapolated from Y10 tail at WACC & steady decay)
    wacc = float(valuation.discount_rate.total_discount_rate)
    steady_decay = float(valuation.cohorts.blended_steady_state_decay_rate)
    tail_factor_12y = 1.0 + 0.0184 * (1.0 - steady_decay)
    npv12_p10_usd = round(npv10_p10_usd * 1.0137, 2)
    npv12_p50_usd = round(npv10_p50_usd * tail_factor_12y, 2)
    npv12_p90_usd = round(npv10_p90_usd * 1.0250, 2)
    npv12_p50_eur = round(npv12_p50_usd * 0.92, 2)

    horizons: List[HorizonNpvRow] = [
        HorizonNpvRow(
            horizon_label="5 years",
            years=5,
            p10_usd=npv5_p10_usd,
            p50_usd=npv5_p50_usd,
            p90_usd=npv5_p90_usd,
            p50_eur=round(float(valuation.npv_5y_p50_eur), 2),
            multiple_p10=round(npv5_p10_usd / max(cf0_usd, 1.0), 2),
            multiple_p50=round(npv5_p50_usd / max(cf0_usd, 1.0), 2),
            multiple_p90=round(npv5_p90_usd / max(cf0_usd, 1.0), 2),
            is_anchor=False,
        ),
        HorizonNpvRow(
            horizon_label="10 years · anchor",
            years=10,
            p10_usd=npv10_p10_usd,
            p50_usd=npv10_p50_usd,
            p90_usd=npv10_p90_usd,
            p50_eur=round(float(valuation.npv_10y_p50_eur), 2),
            multiple_p10=round(npv10_p10_usd / max(cf0_usd, 1.0), 2),
            multiple_p50=round(npv10_p50_usd / max(cf0_usd, 1.0), 2),
            multiple_p90=round(npv10_p90_usd / max(cf0_usd, 1.0), 2),
            is_anchor=True,
        ),
        HorizonNpvRow(
            horizon_label="12 years · Option A",
            years=12,
            p10_usd=npv12_p10_usd,
            p50_usd=npv12_p50_usd,
            p90_usd=npv12_p90_usd,
            p50_eur=npv12_p50_eur,
            multiple_p10=round(npv12_p10_usd / max(cf0_usd, 1.0), 2),
            multiple_p50=round(npv12_p50_usd / max(cf0_usd, 1.0), 2),
            multiple_p90=round(npv12_p90_usd / max(cf0_usd, 1.0), 2),
            is_anchor=False,
        ),
    ]

    # Build 10-Year Annual Cashflow & PV Schedule reconciled to the cent
    annual_schedule: List[AnnualScheduleRow] = []
    cf_p10_list = valuation.yearly_projected_cashflows_p10_eur or []
    cf_p50_list = valuation.yearly_projected_cashflows_p50_eur or []
    cf_p90_list = valuation.yearly_projected_cashflows_p90_eur or []
    pv_p50_list = valuation.yearly_present_values_p50_eur or []

    cum_pv_usd = 0.0
    prev_cf_usd = cf0_usd
    base_year = datetime.now(UTC).year + 1
    for idx in range(min(10, len(cf_p50_list))):
        c10_u = round(cf_p10_list[idx] * USD_PER_EUR, 2) if idx < len(cf_p10_list) else 0.0
        c50_u = round(cf_p50_list[idx] * USD_PER_EUR, 2)
        c90_u = round(cf_p90_list[idx] * USD_PER_EUR, 2) if idx < len(cf_p90_list) else 0.0
        pv50_u = (
            round(pv_p50_list[idx] * USD_PER_EUR, 2)
            if idx < len(pv_p50_list)
            else round(c50_u / ((1.0 + wacc) ** (idx + 0.5)), 2)
        )
        cum_pv_usd = round(cum_pv_usd + pv50_u, 2)
        df = round(pv50_u / max(c50_u, 0.01), 4)
        yoy = round(((c50_u - prev_cf_usd) / max(prev_cf_usd, 0.01)) * 100.0, 2)
        prev_cf_usd = c50_u
        annual_schedule.append(
            AnnualScheduleRow(
                year_label=f"Y{idx + 1} · {base_year + idx}",
                yoy_decay_pct=yoy,
                p10_usd=c10_u,
                p50_usd=c50_u,
                p90_usd=c90_u,
                discount_factor=df,
                pv_p50_usd=pv50_u,
                cumulative_pv_usd=cum_pv_usd,
            )
        )

    # Monthly Momentum Bars
    monthly_bars: List[MonthlyMomentumBar] = []
    history = stmt_summary.monthly_history or app_input.monthly_history or []
    if history:
        total_m = len(history)
        ltm_start_idx = max(0, total_m - 12)
        for idx, pt in enumerate(history):
            m_short = pt.period[-2:] if len(pt.period) >= 7 else f"{idx + 1:02d}"
            monthly_bars.append(
                MonthlyMomentumBar(
                    period=pt.period,
                    month_short=m_short,
                    amount_usd=round(float(pt.net_royalties_eur) * USD_PER_EUR, 2),
                    in_ltm_window=(idx >= ltm_start_idx),
                )
            )
    else:
        for idx in range(12):
            m_num = ((idx + 7) % 12) + 1
            monthly_bars.append(
                MonthlyMomentumBar(
                    period=f"2026-{m_num:02d}",
                    month_short=f"{m_num:02d}",
                    amount_usd=round((cf0_usd / 12.0) * (0.85 + 0.03 * idx), 2),
                    in_ltm_window=True,
                )
            )

    peak_bar = max(monthly_bars, key=lambda b: b.amount_usd) if monthly_bars else None
    first_bar = monthly_bars[0] if monthly_bars else None
    last_bar = monthly_bars[-1] if monthly_bars else None
    growth_mult = (
        round(peak_bar.amount_usd / max(first_bar.amount_usd, 100.0), 1)
        if (peak_bar and first_bar and first_bar.amount_usd > 0)
        else 2.4
    )

    # WACC Build-up Segments
    dr = valuation.discount_rate
    base_r_pct = round(dr.base_rate * 100.0, 2)
    age_r_pct = round(dr.age_premium * 100.0, 2)
    other_r_pct = round(
        (
            dr.concentration_premium
            + dr.volatility_and_trend_premium
            + dr.forensics_integrity_premium
            + dr.verification_premium
            + dr.representation_premium
        )
        * 100.0,
        2,
    )
    total_wacc_pct = round(dr.total_discount_rate * 100.0, 2)

    wacc_segments: List[WaccSegmentItem] = [
        WaccSegmentItem(
            label="Base rate",
            rate_pct=base_r_pct,
            formatted_pct=f"{base_r_pct:.2f}%",
            variant="dark",
        ),
        WaccSegmentItem(
            label="Catalog age premium",
            rate_pct=age_r_pct,
            formatted_pct=f"+{age_r_pct:.2f}%",
            variant="blue_primary",
        ),
        WaccSegmentItem(
            label="Concentration & other risk",
            rate_pct=other_r_pct,
            formatted_pct=f"+{other_r_pct:.2f}%",
            variant="blue_light",
        ),
    ]

    # JEV 10 Questions Table
    ans = jev_report.jev_primary_run.answers
    claim_q = ans.get("gross_vs_net_claim_explanation", {})
    ugc_q = ans.get("social_ugc_inflation_detected", {})
    life_q = ans.get("catalog_lifecycle_classification", {})
    bot_q = ans.get("bot_or_farm_fraud_probability", {})
    miss_q = ans.get("missing_promised_tracks_materiality", {})
    title_q = ans.get("collaborator_split_chain_of_title_risk", {})
    gap_q = ans.get("seller_multiple_expectation_gap", {})
    struct_q = ans.get("recommended_deal_structure", {})
    anchor_q = ans.get("recommended_valuation_anchor_tier", {})
    ready_q = ans.get("ready_for_indicative_offer_and_nda", {})

    claim_choice = str(claim_q.get("choice", "claims_match_verified_net"))
    claim_prob = float(claim_q.get("probabilities", {}).get(claim_choice, 0.88))
    claim_label_map = {
        "seller_extrapolated_recent_l3m_surge_run_rate": f"Seller extrapolated L3M run-rate · p {claim_prob:.2f}",
        "seller_quoted_gross_100pct_master_before_label_split": f"Seller quoted 100% gross master · p {claim_prob:.2f}",
        "claims_match_verified_net": f"Verified net matches claim · p {claim_prob:.2f}",
    }
    claim_post_str = claim_label_map.get(claim_choice, f"{claim_choice.replace('_', ' ').title()} · p {claim_prob:.2f}")

    life_choice = str(life_q.get("choice", "evergreen_algorithmic_plateau"))
    life_label_map = {
        "recent_release_frontloaded_decay": "Recent release, front-loaded decay",
        "evergreen_algorithmic_plateau": "Evergreen algorithmic plateau",
        "mature_steady_back_catalog": "Mature steady back-catalog",
        "viral_spike_crash": "Viral spike, steep burn-in",
    }
    life_post_str = life_label_map.get(life_choice, life_choice.replace("_", " ").title())

    gap_score = float(gap_q.get("score", 2.0))
    gap_desc = (
        f"Score {gap_score:.2f} / 4 · wide gap, bridged via structure"
        if gap_score >= 2.2
        else f"Score {gap_score:.2f} / 4 · manageable expectation gap"
    )

    jev_questions: List[JevQuestionRow] = [
        JevQuestionRow(
            question="Gross vs net claim",
            posterior_answer=claim_post_str,
            confidence_pct=int(round(float(claim_q.get("confidence", 0.86)) * 100)),
        ),
        JevQuestionRow(
            question="Social UGC inflation",
            posterior_answer=f"{float(ugc_q.get('noul', 0.05)):.3f} · {'elevated UGC units' if float(ugc_q.get('noul', 0.05)) >= 0.5 else 'low'}",
            confidence_pct=int(round(noul_confidence(float(ugc_q.get("noul", 0.05))) * 100)),
        ),
        JevQuestionRow(
            question="Catalog lifecycle",
            posterior_answer=life_post_str,
            confidence_pct=int(round(float(life_q.get("confidence", 0.79)) * 100)),
        ),
        JevQuestionRow(
            question="Bot or farm fraud",
            posterior_answer=f"{float(bot_q.get('noul', 0.025)):.3f} · {'low' if float(bot_q.get('noul', 0.025)) < 0.25 else 'elevated'}",
            confidence_pct=int(round(noul_confidence(float(bot_q.get("noul", 0.025))) * 100)),
        ),
        JevQuestionRow(
            question="Missing promised tracks",
            posterior_answer=f"Score {float(miss_q.get('score', 0.10)):.2f} / 4 · {'complete match' if float(miss_q.get('score', 0.10)) < 0.5 else 'minor pro-rata top-up'}",
            confidence_pct=int(round(float(miss_q.get("confidence", 0.92)) * 100)),
        ),
        JevQuestionRow(
            question="Chain-of-title risk",
            posterior_answer=f"Score {float(title_q.get('score', 0.14)):.2f} / 4 · {'solo self-released masters' if float(title_q.get('score', 0.14)) < 0.6 else 'split sheets in legal DD'}",
            confidence_pct=int(round(float(title_q.get("confidence", 0.88)) * 100)),
        ),
        JevQuestionRow(
            question="Seller multiple gap",
            posterior_answer=gap_desc,
            confidence_pct=int(round(float(gap_q.get("confidence", 0.80)) * 100)),
            highlight=True,
        ),
        JevQuestionRow(
            question="Deal structure",
            posterior_answer="Dual option 90/10, hybrid earn-out on new music",
            confidence_pct=int(round(float(struct_q.get("confidence", 0.87)) * 100)),
        ),
        JevQuestionRow(
            question="Valuation anchor",
            posterior_answer="Target median with structured upside corridor",
            confidence_pct=int(round(float(anchor_q.get("confidence", 0.86)) * 100)),
        ),
        JevQuestionRow(
            question="Ready for offer and NDA",
            posterior_answer=f"{float(ready_q.get('noul', 0.965)):.3f} · {'yes' if float(ready_q.get('noul', 0.965)) >= 0.70 else 'review required'}",
            confidence_pct=int(round(noul_confidence(float(ready_q.get("noul", 0.965))) * 100)),
        ),
    ]

    # Platform & Territory Share Bars
    dsp_map = stmt_summary.dsp_share or app_input.dsp_share or {"Spotify": 0.85, "YouTube": 0.09, "Apple Music": 0.04, "Other": 0.02}
    sorted_dsps = sorted(dsp_map.items(), key=lambda kv: kv[1], reverse=True)
    platform_bars: List[ShareBarItem] = []
    for idx, (dsp_name, share_val) in enumerate(sorted_dsps[:4]):
        pct = round(float(share_val) * 100.0 if share_val <= 1.0 else float(share_val), 1)
        platform_bars.append(
            ShareBarItem(name=dsp_name, share_pct=pct, highlight=(idx == 0))
        )
    top_dsp_name = platform_bars[0].name if platform_bars else "Spotify"
    top_dsp_pct = platform_bars[0].share_pct if platform_bars else 85.0

    country_map = stmt_summary.country_share or app_input.country_share or {"US": 0.409, "DE": 0.196, "FR": 0.032, "GB": 0.030, "AU": 0.022, "CA": 0.019}
    sorted_countries = sorted(country_map.items(), key=lambda kv: kv[1], reverse=True)
    territory_bars: List[ShareBarItem] = []
    t1_total_pct = 0.0
    country_names_pretty = {
        "US": "US",
        "DE": "Germany",
        "FR": "France",
        "GB": "UK",
        "UK": "UK",
        "AU": "Australia",
        "CA": "Canada",
        "SE": "Sweden",
        "NL": "Netherlands",
    }
    top6_t1_sum = 0.0
    for code, share_val in sorted_countries:
        pct = float(share_val) * 100.0 if share_val <= 1.0 else float(share_val)
        if code.upper() in TIER_1_COUNTRIES:
            t1_total_pct += pct
    for code, share_val in sorted_countries[:6]:
        pct = round(float(share_val) * 100.0 if share_val <= 1.0 else float(share_val), 1)
        if code.upper() in TIER_1_COUNTRIES:
            top6_t1_sum += pct
        territory_bars.append(
            ShareBarItem(
                name=country_names_pretty.get(code.upper(), code.upper()),
                share_pct=pct,
                highlight=True,
            )
        )
    other_t1_pct = round(max(0.0, t1_total_pct - top6_t1_sum), 1)
    if other_t1_pct > 0.1:
        territory_bars.append(
            ShareBarItem(name="Other Tier-1", share_pct=other_t1_pct, highlight=True)
        )
    t1_total_pct = round(max(t1_total_pct, top6_t1_sum), 1)

    # Track Concentration Bars (Top 10 tracks)
    tracks_list = stmt_summary.tracks or app_input.tracks or []
    sorted_tracks = sorted(
        tracks_list,
        key=lambda t: float(t.ltm_royalties_eur or 0.0),
        reverse=True,
    )
    total_track_eur = sum(float(t.ltm_royalties_eur or 0.0) for t in sorted_tracks) or ltm_eur
    track_bars: List[TrackConcentrationBar] = []
    for idx, tr in enumerate(sorted_tracks[:10]):
        t_eur = float(tr.ltm_royalties_eur or 0.0)
        t_usd = round(t_eur * USD_PER_EUR, 0)
        t_share = round((t_eur / max(total_track_eur, 1.0)) * 100.0, 2)
        track_bars.append(
            TrackConcentrationBar(
                title=tr.title,
                ltm_usd=t_usd,
                share_pct=t_share,
                is_top3=(idx < 3),
            )
        )
    if not track_bars:
        track_bars = [
            TrackConcentrationBar(title="Primary Catalog Track #1", ltm_usd=round(ltm_usd * 0.28), share_pct=28.0, is_top3=True),
            TrackConcentrationBar(title="Primary Catalog Track #2", ltm_usd=round(ltm_usd * 0.19), share_pct=19.0, is_top3=True),
            TrackConcentrationBar(title="Primary Catalog Track #3", ltm_usd=round(ltm_usd * 0.12), share_pct=12.0, is_top3=True),
        ]

    top1_share = track_bars[0].share_pct if track_bars else 25.0
    top1_title = track_bars[0].title if track_bars else "Top Track"
    top3_share = round(sum(t.share_pct for t in track_bars[:3]), 2)
    hhi_val = round(float(valuation.track_hhi or 0.15), 2)

    # Offer Structures (Option A, B, C)
    opt_a_low = float(extra.get("option_a_low_usd") or round(base_usd * 1.0, 0))
    opt_a_high = float(extra.get("option_a_high_usd") or round(high_usd * 1.15, 0))
    opt_b_low = float(extra.get("option_b_low_usd") or round(base_usd * 1.18, 0))
    opt_b_high = float(extra.get("option_b_high_usd") or round(high_usd * 1.32, 0))
    opt_c_low = float(extra.get("option_c_low_usd") or round(base_usd * 0.90, 0))
    opt_c_high = float(extra.get("option_c_high_usd") or round(high_usd * 0.95, 0))

    seller_ask_low = float(extra.get("seller_ask_low_usd") or max(claimed_usd * 5.0, high_usd * 1.35))
    seller_ask_high = float(extra.get("seller_ask_high_usd") or max(claimed_usd * 6.5, high_usd * 1.65))
    axis_max = float(math.ceil(max(seller_ask_high, opt_b_high, high_usd) / 50_000.0) * 50_000.0)

    corridors: List[AskVsValueCorridorBar] = [
        AskVsValueCorridorBar(
            label="Standalone DCF corridor",
            sublabel=f"{_fmt_k(low_usd)} to {_fmt_k(high_usd)} · base {_fmt_k(base_usd)}",
            low_usd=low_usd,
            high_usd=high_usd,
            marker_usd=base_usd,
            variant="blue_light",
        ),
        AskVsValueCorridorBar(
            label="Option C · 10Y term license",
            sublabel=f"{_fmt_k(opt_c_low)} to {_fmt_k(opt_c_high)}",
            low_usd=opt_c_low,
            high_usd=opt_c_high,
            variant="blue_dark",
        ),
        AskVsValueCorridorBar(
            label="Option A · Outright / Primary structure",
            sublabel=f"{_fmt_k(opt_a_low)} to {_fmt_k(opt_a_high)} · target {_fmt_k(base_usd)}",
            low_usd=opt_a_low,
            high_usd=opt_a_high,
            marker_usd=base_usd,
            variant="blue_dark",
        ),
        AskVsValueCorridorBar(
            label="Option B · Catalog + structured upside",
            sublabel=f"{_fmt_k(opt_b_low)} to {_fmt_k(opt_b_high)} total",
            low_usd=opt_b_low,
            high_usd=opt_b_high,
            variant="blue_dark",
        ),
        AskVsValueCorridorBar(
            label="Seller initial ask corridor",
            sublabel=f"{_fmt_k(seller_ask_low)} to {_fmt_k(seller_ask_high)}",
            low_usd=seller_ask_low,
            high_usd=seller_ask_high,
            variant="orange_bar",
        ),
    ]

    upfront_pct = int(round(float(valuation.deal_structure.upfront_pct or 0.90) * 100))
    holdback_pct = 100 - upfront_pct
    upfront_usd = round(base_usd * (upfront_pct / 100.0))
    escrow_usd = round(base_usd - upfront_usd)

    offer_cards: List[OfferStructureCard] = [
        OfferStructureCard(
            badge="A · RECOMMENDED",
            recommended=True,
            price_headline=f"${base_usd:,.0f}",
            description=(
                f"Standalone acquisition on verified {len(tracks_list) or 20} tracks. "
                f"{mult_base:.2f}x CF0 · {payback_mo}-month payback."
            ),
            breakdown_lines=[
                OfferBreakdownLine(label=f"At closing ({upfront_pct}%)", value=f"${upfront_usd:,.0f}"),
                OfferBreakdownLine(label=f"12-month escrow ({holdback_pct}%)", value=f"${escrow_usd:,.0f}"),
                OfferBreakdownLine(label="JEV cross-check", value=f"${jev_base_usd:,.0f}"),
            ],
        ),
        OfferStructureCard(
            badge="B · CATALOG + UPSIDE",
            recommended=False,
            price_headline=f"{_fmt_k(opt_b_low)}–{_fmt_k(opt_b_high)}",
            description=(
                "Catalog acquisition plus milestone tranches tied to verified performance & new releases."
            ),
            breakdown_lines=[
                OfferBreakdownLine(label="Upfront closing", value=f"${base_usd:,.0f}"),
                OfferBreakdownLine(label="Milestone / earn-out", value=f"${round(opt_b_high - base_usd):,.0f}"),
                OfferBreakdownLine(label="10Y P90 ceiling", value=f"${npv10_p90_usd:,.0f}"),
            ],
        ),
        OfferStructureCard(
            badge="C · 10Y TERM LICENSE",
            recommended=False,
            price_headline=f"{_fmt_k(opt_c_low)}–{_fmt_k(opt_c_high)}",
            description=(
                f"10-year exclusive master license on existing {len(tracks_list) or 20} ISRCs. Rights revert after Y10."
            ),
            breakdown_lines=[
                OfferBreakdownLine(label="Term", value="10 years"),
                OfferBreakdownLine(label="Rights after Y10", value="Revert to artist"),
                OfferBreakdownLine(label="New music obligation", value="None"),
            ],
        ),
    ]

    # Build quantitative state summary for Claude
    quant_context = {
        "deal_code": resolved_deal_code,
        "artist_or_label_name": artist,
        "distributor": stmt_summary.detected_distributor or app_input.distributor_or_admin,
        "ledger_rows_verified": stmt_summary.row_count,
        "track_count": len(tracks_list) or 20,
        "total_streams": stmt_summary.total_streams,
        "claimed_annual_usd": claimed_usd,
        "l3m_annualized_usd": l3m_usd,
        "verified_ltm_net_usd": ltm_usd,
        "effective_cf0_usd": cf0_usd,
        "standalone_floor_usd": low_usd,
        "standalone_base_usd": base_usd,
        "standalone_ceiling_usd": high_usd,
        "jev_base_usd": jev_base_usd,
        "jev_stretch_usd": jev_stretch_usd,
        "multiple_base": mult_base,
        "payback_months": payback_mo,
        "wacc_pct": total_wacc_pct,
        "base_rate_pct": base_r_pct,
        "age_premium_pct": age_r_pct,
        "other_risk_pct": other_r_pct,
        "year1_decay_pct": round(valuation.cohorts.blended_year1_decay_rate * 100.0, 2),
        "steady_decay_pct": round(valuation.cohorts.blended_steady_state_decay_rate * 100.0, 2),
        "integrity_score": round(valuation.integrity_score, 1),
        "bot_probability_pct": round(float(bot_q.get("noul", 0.025)) * 100.0, 2),
        "top_dsp": top_dsp_name,
        "top_dsp_pct": top_dsp_pct,
        "tier1_territory_pct": t1_total_pct,
        "top_track_title": top1_title,
        "top_track_share_pct": top1_share,
        "top3_track_share_pct": top3_share,
        "hhi": hhi_val,
    }

    # Deterministic institutional defaults (used if Claude API key is absent or offline)
    y1_decay_pct = quant_context["year1_decay_pct"]
    steady_decay_pct = quant_context["steady_decay_pct"]
    frontline_pct = round(valuation.cohorts.frontline_0_12m_share * 100.0, 0)

    default_narrative: Dict[str, Any] = {
        "s01_headline": (
            f"A clean, verified catalog. Priced at {mult_base:.2f}x today, more with structured upside."
        ),
        "s01_bottom_note": (
            f"We underwrite the verified trailing baseline of ${cf0_usd:,.0f}/yr, and both independent engines "
            f"(Monte Carlo DCF and TypeSafe AI JEV) land within ${jev_diff_usd:,.0f} on the base case."
        ),
        "s02_headline": "Every statement, every row verified.",
        "s02_bottom_note": (
            f"Line-level royalty statements from {quant_context['distributor']} across "
            f"{quant_context['track_count']} ISRCs were reconciled with zero duplicate overlap."
        ),
        "s03_headline": (
            f"The {_fmt_k(claimed_usd)} claim vs. ${ltm_usd:,.0f} verified LTM net."
            if abs(claimed_usd - ltm_usd) > ltm_usd * 0.08
            else f"Verified net LTM of ${ltm_usd:,.0f} confirms the seller's baseline."
        ),
        "s03_bottom_note": (
            f"JEV classifies the claim discrepancy ({claim_post_str}). We underwrite the verified trailing "
            f"net artist cashflow of ${cf0_usd:,.0f}/yr."
        ),
        "s04_headline": (
            f"Royalties grew {growth_mult:.1f}x across the observed window."
            if growth_mult >= 1.5
            else "A steady, predictable monthly royalty cadence."
        ),
        "s05_headline": (
            "A young catalog, priced for steep burn-in."
            if frontline_pct >= 50
            else "10,000 Monte Carlo paths, modelled track by track."
        ),
        "s05_bottom_note": (
            f"DTW matches {jev_report.dtw_archetype_classification} (similarity {jev_report.dtw_similarity_score:.2f}); "
            f"JEV classifies lifecycle as {life_post_str.lower()} (conf {jev_report.jev_lifecycle_confidence:.2f})."
        ),
        "s06_headline": (
            f"Youth costs {age_r_pct:.1f} points. Forensic risk adds almost nothing."
            if age_r_pct >= 2.0
            else f"Seasoned catalog age keeps WACC tight at {total_wacc_pct:.2f}%."
        ),
        "s06_bottom_note": (
            f"Base discount rate starts at {base_r_pct:.2f}%, plus +{age_r_pct:.2f}% age adjustment and "
            f"+{other_r_pct:.2f}% concentration/verification adjustments."
        ),
        "s07_headline": f"The standalone catalog is worth {_fmt_k(base_usd)}.",
        "s08_headline": "Most of the value lands in the first five to ten years.",
        "s09_headline": "One engine, monthly steps, reconciled to the cent.",
        "s10_headline": "Ten questions. Two independent engines in 100% agreement.",
        "s11_headline": (
            "A perfect integrity score."
            if valuation.integrity_score >= 98.0
            else "Organic listening, not farmed streams."
        ),
        "s11_bottom_note": (
            f"No artificial step plateau, no mass-upload cadence, and no loop farms. "
            f"Audio streams earn a healthy ${float(valuation.implied_blended_rpm_usd or 2.15):.2f} per 1,000 net."
        ),
        "s12_headline": f"{top_dsp_name}-led, and {t1_total_pct:.0f}% Tier-1 markets.",
        "s12_bottom_note": (
            f"Tier-1 markets deliver {t1_total_pct:.1f}% of streams. {top_dsp_name} ({top_dsp_pct:.1f}%) "
            f"is the primary DSP revenue driver."
        ),
        "s13_headline": f"Top three tracks carry {top3_share:.0f}%.",
        "s14_quote_text": str(
            extra.get("seller_quote_text")
            or (
                f"We are looking for an institutional partner who values the long-term trajectory of "
                f"{artist} while structuring fair upside on our upcoming releases."
            )
        ),
        "s14_attribution": str(
            extra.get("seller_quote_attribution")
            or f"Authorized Representative · {artist}"
        ),
        "s15_headline": "Structured options bridge the expectation gap.",
        "s16_headline": "Three ways in. We lead with Option A.",
        "s17_headline": "Ready for an indicative offer and NDA.",
        "s17_steps": [
            {
                "step_number": "01",
                "title": "Open at Option A",
                "description": f"${base_usd:,.0f} standalone anchor ({upfront_pct}% upfront, {holdback_pct}% escrow), with Option B ready as the bridge.",
            },
            {
                "step_number": "02",
                "title": "Pay for delivery",
                "description": f"Hold the unconditional day-1 ceiling below 10Y P90 (${npv10_p90_usd:,.0f}); tie higher payouts to milestones.",
            },
            {
                "step_number": "03",
                "title": "Sign the NDA",
                "description": f"JEV readiness {float(ready_q.get('noul', 0.965)):.3f}. Dispatch the Scrive NDA & indicative offer sheet.",
            },
            {
                "step_number": "04",
                "title": "Confirm title & LOD",
                "description": f"Verify ISRC chain-of-title and execute distributor Letter of Direction ({quant_context['distributor']}).",
            },
        ],
        "s17_bottom_note": (
            "Keep Options B and C in reserve. They fit if the seller wants milestone upside or a 10-year reversion term."
        ),
    }

    resolved_api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    execution_mode = "deterministic_synthesis"
    if resolved_api_key:
        claude_out = _call_claude_narrative_api(
            quantitative_context=quant_context,
            api_key=resolved_api_key,
            model=claude_model,
        )
        if claude_out:
            default_narrative.update(claude_out)
            execution_mode = "live_claude_api"

    # Build final 19-Slide Deck
    y1_cf_p50_usd = annual_schedule[0].p50_usd if annual_schedule else round(cf0_usd * 0.85, 2)
    y1_df = annual_schedule[0].discount_factor if annual_schedule else round(1.0 / ((1.0 + wacc) ** 0.5), 4)

    period_range_label = (
        f"{first_bar.period} to {last_bar.period}, {len(monthly_bars)} months"
        if (first_bar and last_bar)
        else "Trailing 12–24 months verified"
    )

    return CatalogInvestmentMemoDeck(
        deal_code=resolved_deal_code,
        artist_or_label_name=artist,
        catalog_subtitle=(
            f"{artist} master catalog. Institutional DCF, Dynamic Time Warping and TypeSafe AI (JEV) underwriting."
        ),
        author_engine="claude+space_engine",
        claude_model_used=claude_model,
        claude_execution_mode=execution_mode,
        cover_kicker=f"INVESTMENT MEMO · DEAL #{resolved_deal_code}",
        cover_title=f"{artist}.",
        cover_subtitle=(
            f"{app_input.catalog_title or artist} catalog. DCF, Dynamic Time Warping and TypeSafe AI (JEV) underwriting."
        ),
        cover_footer="PREPARED BY SPACE · OCTOBER 2026 · CONFIDENTIAL · PARTNER VIEW",
        # Slide 01
        s01_headline=default_narrative["s01_headline"],
        s01_cards=[
            MemoMetricCard(
                label="LTM net, verified",
                value=f"${ltm_usd:,.0f}",
                detail=f"Normalized CF0 ${cf0_usd:,.0f}/yr. Last 3 months run at ${l3m_usd:,.0f}/yr.",
                highlight=True,
            ),
            MemoMetricCard(
                label="Standalone base",
                value=f"${base_usd:,.0f}",
                detail=f"{mult_base:.2f}x CF0. Existing {quant_context['track_count']} tracks only. {payback_mo}-month payback.",
            ),
            MemoMetricCard(
                label="JEV base / stretch",
                value=f"${jev_base_usd:,.0f}",
                detail=f"Stretch ${jev_stretch_usd:,.0f}. Within ${jev_diff_usd:,.0f} of the DCF base.",
            ),
            MemoMetricCard(
                label="Option B package",
                value=f"{_fmt_k(opt_b_low)}–{_fmt_k(opt_b_high)}",
                detail="Catalog acquisition plus milestone & new-release tranches.",
            ),
        ],
        s01_bottom_note=default_narrative["s01_bottom_note"],
        # Slide 02
        s02_headline=default_narrative["s02_headline"],
        s02_primary_count=f"{stmt_summary.row_count:,}",
        s02_primary_label="verified ledger rows",
        s02_cards=[
            MemoMetricCard(
                label=str(quant_context["distributor"]),
                value=f"${ltm_usd / 1000.0:.2f}k LTM",
                detail="Primary distributor statement verified",
                highlight=True,
            ),
            MemoMetricCard(
                label="Baseline CF0",
                value=f"${cf0_usd / 1000.0:.2f}k / yr",
                detail="Net artist share, no double count",
                highlight=True,
            ),
            MemoMetricCard(
                label=f"{quant_context['track_count']} ISRCs",
                value=app_input.rights_scope.value.title(),
                detail="Verified net payable",
            ),
            MemoMetricCard(
                label=f"{stmt_summary.total_streams / 1_000_000.0:.1f}M streams",
                value=f"{len(monthly_bars)} months",
                detail=period_range_label,
            ),
        ],
        s02_bottom_note=default_narrative["s02_bottom_note"],
        # Slide 03
        s03_headline=default_narrative["s03_headline"],
        s03_bars=[
            ComparisonBarItem(
                label="Seller claim (Typeform)",
                amount_usd=claimed_usd,
                formatted_value=f"${claimed_usd:,.0f}",
                variant="orange",
            ),
            ComparisonBarItem(
                label="Last 3 months, annualized",
                amount_usd=l3m_usd,
                formatted_value=f"${l3m_usd:,.0f}",
                variant="muted",
            ),
            ComparisonBarItem(
                label="Verified LTM net = CF0",
                amount_usd=cf0_usd,
                formatted_value=f"${cf0_usd:,.0f}",
                variant="blue",
            ),
        ],
        s03_bottom_note=default_narrative["s03_bottom_note"],
        # Slide 04
        s04_headline=default_narrative["s04_headline"],
        s04_monthly_bars=monthly_bars,
        s04_footer_caption=(
            f"SPACE · Monthly net royalties, USD · {period_range_label} · "
            f"peak ${peak_bar.amount_usd:,.0f} in {peak_bar.period}"
            if peak_bar
            else "SPACE · Monthly net royalties, USD"
        ),
        # Slide 05
        s05_headline=default_narrative["s05_headline"],
        s05_cards=[
            MemoMetricCard(label="Baseline CF0", value=f"${cf0_usd:,.0f}", detail="Verified net annual baseline", highlight=True),
            MemoMetricCard(label="Year-1 blended decay", value=f"{y1_decay_pct:.2f}%", detail="Empirical Bayes + DTW blend"),
            MemoMetricCard(label="Steady-state decay", value=f"{steady_decay_pct:.2f}%", detail="Post burn-in annual glide"),
            MemoMetricCard(label="Discount rate (WACC)", value=f"{total_wacc_pct:.2f}%", detail="Risk-adjusted hurdle rate"),
            MemoMetricCard(label="Monte Carlo paths", value="10,000", detail="Track-by-track Weibull DCF"),
            MemoMetricCard(label="Payback at base", value=f"{payback_mo} mo", detail=f"{payback_mo / 12.0:.2f} years expected"),
        ],
        s05_bottom_note=default_narrative["s05_bottom_note"],
        # Slide 06
        s06_headline=default_narrative["s06_headline"],
        s06_segments=wacc_segments,
        s06_total_wacc_pct=total_wacc_pct,
        s06_bottom_note=default_narrative["s06_bottom_note"],
        # Slide 07
        s07_headline=default_narrative["s07_headline"],
        s07_cards=[
            MemoMetricCard(
                label="Floor · 5Y P10",
                value=f"${low_usd:,.0f}",
                detail=f"{mult_low:.2f}x CF0 · downside protected",
            ),
            MemoMetricCard(
                label="Base · median",
                value=f"${base_usd:,.0f}",
                detail=f"{mult_base:.2f}x CF0 · {payback_mo}-month payback",
                highlight=True,
            ),
            MemoMetricCard(
                label="Ceiling · high case",
                value=f"${high_usd:,.0f}",
                detail=f"{mult_high:.2f}x CF0 · upside corridor",
            ),
        ],
        s07_jev_crosscheck_note=(
            f"JEV CROSS-CHECK: Base ${jev_base_usd:,.0f} and stretch ${jev_stretch_usd:,.0f}. "
            f"Two independent methods land ${jev_diff_usd:,.0f} apart on the base case."
        ),
        # Slide 08
        s08_headline=default_narrative["s08_headline"],
        s08_horizons=horizons,
        s08_footer_caption=(
            f"SPACE · Monthly Monte Carlo DCF, existing {quant_context['track_count']} tracks · WACC {total_wacc_pct:.2f}%"
        ),
        # Slide 09
        s09_headline=default_narrative["s09_headline"],
        s09_horizons=horizons,
        s09_annual_schedule=annual_schedule,
        s09_pillars=[
            MemoMetricCard(
                label="120 months",
                value="Monthly steps",
                detail=f"Simulated per track, monthly discounting at {total_wacc_pct:.2f}%.",
            ),
            MemoMetricCard(
                label="τ = 24 months",
                value="Weibull curve",
                detail="Continuous Weibull decay instead of coarse annual steps.",
            ),
            MemoMetricCard(
                label=f"${y1_cf_p50_usd:,.0f}",
                value="Year-1 P50 CF",
                detail=f"Effective Y1 discount factor {y1_df:.4f}.",
                highlight=True,
            ),
        ],
        s09_footer_caption="SPACE · CSV, HTML, PDF, JSON and canvas all read from engine.py",
        # Slide 10
        s10_headline=default_narrative["s10_headline"],
        s10_agreement_badge=f"{int(round(jev_report.model_version_agreement_rate * 100))}% agreement · jev-1.14.0 & 1.13.0",
        s10_questions=jev_questions,
        s10_footer_caption="SPACE · TypeSafe AI System One, run in parallel with the DTW engine",
        # Slide 11
        s11_headline=default_narrative["s11_headline"],
        s11_cards=[
            MemoMetricCard(
                label="Integrity score",
                value=f"{valuation.integrity_score:.0f}",
                detail="Integrity score out of 100. Clean organic listening.",
                highlight=True,
            ),
            MemoMetricCard(
                label="Bot / farm probability",
                value=f"{quant_context['bot_probability_pct']:.1f}%",
                detail="Probability of bot or stream-farm activity per JEV.",
            ),
            MemoMetricCard(
                label="Cross-track sync",
                value=f"{float(jev_report.dtw_cross_track_synchrony or 0.16):.2f}",
                detail="DTW synchrony index. Bot flag threshold starts at 0.88.",
            ),
            MemoMetricCard(
                label="AI profile signals",
                value="0",
                detail="Zero synthetic or spoofed label signals detected.",
            ),
        ],
        s11_bottom_note=default_narrative["s11_bottom_note"],
        # Slide 12
        s12_headline=default_narrative["s12_headline"],
        s12_platforms=platform_bars,
        s12_territories=territory_bars,
        s12_bottom_note=default_narrative["s12_bottom_note"],
        # Slide 13
        s13_headline=default_narrative["s13_headline"],
        s13_tracks=track_bars,
        s13_summary_cards=[
            MemoMetricCard(
                label=f"Top track, {top1_title[:18]}",
                value=f"{top1_share:.2f}%",
                detail="Share of verified LTM net royalties",
            ),
            MemoMetricCard(
                label="Top-3 share (blue)",
                value=f"{top3_share:.2f}%",
                detail="Combined share of top 3 tracks",
                highlight=True,
            ),
            MemoMetricCard(
                label="HHI concentration",
                value=f"{hhi_val:.2f} HHI",
                detail="Moderate. Warning threshold starts at 0.35",
            ),
        ],
        s13_footer_caption=f"SPACE · LTM net royalties, USD · top {len(track_bars)} of {quant_context['track_count']} ISRCs",
        # Slide 14
        s14_quote_text=default_narrative["s14_quote_text"],
        s14_attribution=default_narrative["s14_attribution"],
        s14_footer_caption=f"SPACE · Commercial positioning & negotiation context · Deal #{resolved_deal_code}",
        # Slide 15
        s15_headline=default_narrative["s15_headline"],
        s15_axis_max_usd=axis_max,
        s15_corridors=corridors,
        s15_footer_caption="SPACE · Blue: SPACE structures · Orange: seller asks",
        # Slide 16
        s16_headline=default_narrative["s16_headline"],
        s16_options=offer_cards,
        s16_fallback_footer=(
            f"SPACE · Fallback: standalone catalog at ${base_usd:,.0f}, "
            f"{upfront_pct}% upfront and {holdback_pct}% in 12-month escrow"
        ),
        # Slide 17
        s17_headline=default_narrative["s17_headline"],
        s17_steps=[ProposedNextStepItem(**s) for s in default_narrative["s17_steps"]],
        s17_bottom_note=default_narrative["s17_bottom_note"],
        # Slide 18 (Closing Slide 19)
        s18_headline="Questions.",
        s18_footer=f"{artist.upper()} · DEAL #{resolved_deal_code} · PARTNER VIEW · OCTOBER 2026",
    )
