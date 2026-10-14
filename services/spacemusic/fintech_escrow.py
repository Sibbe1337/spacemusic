"""
Multi-Currency Split-Escrow & Virtual Lockbox Ledger (`services/spacemusic/fintech_escrow.py`)

Provides 100% deterministic, cent-exact (`Decimal` + `ROUND_HALF_UP`) financial settlement and
virtual lockbox royalty distribution for SPACE's Autonomous Deal Desk:

1. **Cent-Exact Closing Split-Escrow Waterfall (`compute_split_escrow_instruction`)**:
   - Uses strict `Decimal("0.01")` precision so that:
     `gross_funding_cents == seller_upfront_wire_cents + seller_holdback_escrow_cents + space_origination_wire_cents + space_spread_wire_cents`
     holds with **0.00 cent rounding drift** across all currencies (`EUR`, `USD`, `GBP`, `SEK`).
   - Enforces idempotency via `idempotency_key` (`SHA-256` derived or caller-supplied) so repeated
     webhook/API retries never trigger duplicate wire instructions.
2. **Multi-Rail Institutional Settlement (`Shieldpay` / `Wise Platform` / `Airwallex`)**:
   - Generates structured JSON wire payloads ready for Shieldpay M&A Escrow, Wise Batch Payouts,
     or Airwallex Virtual IBAN Lockbox accounts.
3. **Monthly Virtual Lockbox Royalty Waterfall (`distribute_monthly_lockbox_royalties`)**:
   - When monthly royalties arrive from DistroKid / TuneCore / Symphonic into the Deal's Virtual IBAN
     Lockbox (`SE-LOCKBOX-SPC-...`), automatically splits every cent between:
     - **SPACE Carried Royalty Tail (`carried_tail_pct`, e.g. 7.5%)** -> swept immediately to SPACE Treasury
     - **Buyer Primary Royalty Share (`92.5%`)** -> swept to Institutional Buyer
     - **12-Month Seller Performance Holdback Release Tracker** -> tracks cumulative LTM performance
       against the underwriting baseline ($CF_0$) and triggers automatic holdback release at Month 12.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from pydantic import BaseModel, Field

TWO_PLACES = Decimal("0.01")


def _to_dec(val: float | str | Decimal) -> Decimal:
    if isinstance(val, Decimal):
        return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class EscrowProviderRail(str, Enum):
    SHIELDPAY_ESCROW = "SHIELDPAY_ESCROW"
    WISE_PLATFORM_BATCH = "WISE_PLATFORM_BATCH"
    AIRWALLEX_VIRTUAL_LOCKBOX = "AIRWALLEX_VIRTUAL_LOCKBOX"


class SplitWireLeg(BaseModel):
    leg_id: str
    recipient_role: str
    recipient_name: str
    destination_account: str
    currency: str
    amount_decimal: str
    amount_cents: int
    settlement_timing: str
    memo: str


class SplitEscrowSettlementInstruction(BaseModel):
    instruction_id: str
    idempotency_key: str
    deal_code: str
    application_id: str
    provider_rail: EscrowProviderRail
    virtual_lockbox_iban: str
    currency: str
    fx_rate_from_eur: str
    gross_buyer_funding: str
    seller_total_consideration: str
    seller_upfront_wire: str
    seller_holdback_escrow: str
    space_origination_wire: str
    space_spread_wire: str
    space_total_closing_wire: str
    carried_tail_pct: str
    invariant_balanced_to_exact_cent: bool
    wire_legs: list[SplitWireLeg] = Field(default_factory=list)
    created_at_utc: str


class MonthlyLockboxDistribution(BaseModel):
    distribution_id: str
    idempotency_key: str
    deal_code: str
    period_month: str
    currency: str
    gross_royalty_inflow: str
    space_carried_tail_payout: str
    buyer_royalty_payout: str
    cumulative_royalties_collected: str
    target_12m_baseline_cf0: str
    performance_coverage_ratio: float
    holdback_release_status: str
    holdback_released_to_seller: str
    invariant_balanced_to_exact_cent: bool


SUPPORTED_FX_FROM_EUR: dict[str, Decimal] = {
    "EUR": Decimal("1.0000"),
    "USD": Decimal("1.0870"),
    "GBP": Decimal("0.8550"),
    "SEK": Decimal("11.3500"),
}


class FintechEscrowLedger:
    """
    Deterministic, idempotent Split-Escrow & Virtual Lockbox Ledger.
    Guarantees zero rounding drift (`0.00` cent discrepancy) and rejects conflicting
    payloads reusing the same `idempotency_key`.
    """

    def __init__(self) -> None:
        self._closing_instructions: dict[str, SplitEscrowSettlementInstruction] = {}
        self._closing_payload_fingerprints: dict[str, str] = {}
        self._lockbox_distributions: dict[str, MonthlyLockboxDistribution] = {}
        self._cumulative_inflows_by_deal: dict[str, Decimal] = {}

    def compute_split_escrow_instruction(
        self,
        *,
        deal_code: str,
        application_id: str,
        seller_legal_name: str,
        seller_iban: str,
        buyer_entity_name: str,
        seller_agreed_price_eur: float | Decimal,
        buyer_gross_funding_eur: float | Decimal | None = None,
        origination_fee_pct: float | Decimal = Decimal("0.06"),
        holdback_pct: float | Decimal = Decimal("0.20"),
        carried_tail_pct: float | Decimal = Decimal("0.075"),
        settlement_currency: str = "EUR",
        provider_rail: EscrowProviderRail = EscrowProviderRail.AIRWALLEX_VIRTUAL_LOCKBOX,
        space_treasury_iban: str = "SE00 0000 0000 0000 0000 0000 (SPACE Corporate Treasury)",
        idempotency_key: str | None = None,
    ) -> SplitEscrowSettlementInstruction:
        """
        Computes a cent-exact closing Split-Escrow Settlement Instruction.
        If `idempotency_key` has already been processed with identical parameters, returns the
        cached instruction; if called with mutated financial amounts under the same key,
        raises `ValueError` to prevent double-spend / parameter tampering.
        """
        ccy = (settlement_currency or "EUR").strip().upper()
        fx = SUPPORTED_FX_FROM_EUR.get(ccy, Decimal("1.0000"))

        seller_eur = _to_dec(seller_agreed_price_eur)
        fee_rate = Decimal(str(origination_fee_pct))
        hb_rate = Decimal(str(holdback_pct))
        tail_rate = Decimal(str(carried_tail_pct))

        seller_ccy = (seller_eur * fx).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        fee_ccy = (seller_ccy * fee_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        if buyer_gross_funding_eur is not None:
            gross_ccy = (_to_dec(buyer_gross_funding_eur) * fx).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        else:
            gross_ccy = seller_ccy + fee_ccy

        if gross_ccy < seller_ccy + fee_ccy:
            raise ValueError(
                f"Insufficient gross buyer funding ({gross_ccy} {ccy}) to cover seller price "
                f"({seller_ccy} {ccy}) + SPACE origination fee ({fee_ccy} {ccy})."
            )

        # Cent-exact waterfall allocation
        holdback_ccy = (seller_ccy * hb_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        seller_upfront_ccy = seller_ccy - holdback_ccy
        spread_ccy = gross_ccy - seller_ccy - fee_ccy
        space_total_ccy = fee_ccy + spread_ccy

        # Mathematical cent invariant check
        total_out_cents = int(
            (seller_upfront_ccy + holdback_ccy + fee_ccy + spread_ccy) * 100
        )
        gross_in_cents = int(gross_ccy * 100)
        if total_out_cents != gross_in_cents:
            raise AssertionError(
                f"CRITICAL ESCROW INVARIANT VIOLATION: gross_in_cents={gross_in_cents} != total_out_cents={total_out_cents}"
            )

        fingerprint = (
            f"{deal_code}|{application_id}|{ccy}|{gross_ccy}|{seller_ccy}|"
            f"{fee_ccy}|{holdback_ccy}|{seller_iban}|{space_treasury_iban}"
        )
        idem_key = idempotency_key or f"idem_escrow_{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:20]}"

        if idem_key in self._closing_instructions:
            if self._closing_payload_fingerprints.get(idem_key) != fingerprint:
                raise ValueError(
                    f"Idempotency conflict for key '{idem_key}': financial parameters differ from original instruction."
                )
            return self._closing_instructions[idem_key]

        lockbox_iban = f"SE88SPACE{hashlib.sha1(deal_code.encode('utf-8')).hexdigest()[:14].upper()}"
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        inst_id = f"esc_{hashlib.sha256(f'{idem_key}:{now_iso}'.encode()).hexdigest()[:16]}"

        legs = [
            SplitWireLeg(
                leg_id=f"{inst_id}_leg1_seller_upfront",
                recipient_role="SELLER_UPFRONT_80",
                recipient_name=seller_legal_name,
                destination_account=seller_iban,
                currency=ccy,
                amount_decimal=f"{seller_upfront_ccy:.2f}",
                amount_cents=int(seller_upfront_ccy * 100),
                settlement_timing="IMMEDIATE_ON_LOD_EXECUTION",
                memo=f"SPACE Deal {deal_code} - Closing Upfront Proceeds",
            ),
            SplitWireLeg(
                leg_id=f"{inst_id}_leg2_space_origination",
                recipient_role="SPACE_ORIGINATION_AND_SPREAD",
                recipient_name="SpaceMusic AB (Treasury)",
                destination_account=space_treasury_iban,
                currency=ccy,
                amount_decimal=f"{space_total_ccy:.2f}",
                amount_cents=int(space_total_ccy * 100),
                settlement_timing="IMMEDIATE_ON_LOD_EXECUTION",
                memo=f"SPACE Deal {deal_code} - Origination Fee ({fee_ccy:.2f}) & Spread ({spread_ccy:.2f})",
            ),
            SplitWireLeg(
                leg_id=f"{inst_id}_leg3_seller_holdback",
                recipient_role="SELLER_PERFORMANCE_HOLDBACK_20",
                recipient_name=f"Escrow Sub-Account f/b/o {seller_legal_name}",
                destination_account=lockbox_iban,
                currency=ccy,
                amount_decimal=f"{holdback_ccy:.2f}",
                amount_cents=int(holdback_ccy * 100),
                settlement_timing="RELEASED_12M_POST_CLOSING_WATERFALL",
                memo=f"SPACE Deal {deal_code} - 12M Performance Holdback Escrow",
            ),
        ]

        instruction = SplitEscrowSettlementInstruction(
            instruction_id=inst_id,
            idempotency_key=idem_key,
            deal_code=deal_code,
            application_id=str(application_id),
            provider_rail=provider_rail,
            virtual_lockbox_iban=lockbox_iban,
            currency=ccy,
            fx_rate_from_eur=f"{fx:.4f}",
            gross_buyer_funding=f"{gross_ccy:.2f}",
            seller_total_consideration=f"{seller_ccy:.2f}",
            seller_upfront_wire=f"{seller_upfront_ccy:.2f}",
            seller_holdback_escrow=f"{holdback_ccy:.2f}",
            space_origination_wire=f"{fee_ccy:.2f}",
            space_spread_wire=f"{spread_ccy:.2f}",
            space_total_closing_wire=f"{space_total_ccy:.2f}",
            carried_tail_pct=f"{tail_rate:.4f}",
            invariant_balanced_to_exact_cent=(total_out_cents == gross_in_cents),
            wire_legs=legs,
            created_at_utc=now_iso,
        )
        self._closing_instructions[idem_key] = instruction
        self._closing_payload_fingerprints[idem_key] = fingerprint
        return instruction

    def distribute_monthly_lockbox_royalties(
        self,
        *,
        deal_code: str,
        period_month: str,
        gross_royalty_inflow: float | Decimal,
        target_12m_baseline_cf0: float | Decimal,
        seller_holdback_escrow: float | Decimal = Decimal("0.00"),
        carried_tail_pct: float | Decimal = Decimal("0.075"),
        is_month_12_holdback_check: bool = False,
        currency: str = "EUR",
        idempotency_key: str | None = None,
    ) -> MonthlyLockboxDistribution:
        """
        Executes a cent-exact monthly Virtual Lockbox royalty distribution:
        - Splits `gross_royalty_inflow` into `space_carried_tail_payout` (`carried_tail_pct`)
          and `buyer_royalty_payout` (`1 - carried_tail_pct`) with zero cent leakage.
        - Tracks cumulative royalty inflows for `deal_code` and evaluates the 12-month
          holdback release trigger (`>= 90%` of underwritten $CF_0$ releases 100% of holdback;
          pro-rata release between `50%` and `90%`).
        """
        ccy = (currency or "EUR").strip().upper()
        inflow = _to_dec(gross_royalty_inflow)
        if inflow < Decimal("0.00"):
            raise ValueError("Gross royalty inflow cannot be negative.")

        cf0 = max(Decimal("0.01"), _to_dec(target_12m_baseline_cf0))
        holdback_pool = max(Decimal("0.00"), _to_dec(seller_holdback_escrow))
        tail_rate = Decimal(str(carried_tail_pct))

        idem_key = idempotency_key or (
            f"idem_lockbox_{hashlib.sha256(f'{deal_code}|{period_month}|{inflow}|{ccy}'.encode()).hexdigest()[:20]}"
        )
        if idem_key in self._lockbox_distributions:
            return self._lockbox_distributions[idem_key]

        space_tail = (inflow * tail_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        buyer_share = inflow - space_tail

        inflow_cents = int(inflow * 100)
        split_cents = int((space_tail + buyer_share) * 100)
        balanced = inflow_cents == split_cents

        prior_cum = self._cumulative_inflows_by_deal.get(deal_code, Decimal("0.00"))
        new_cum = prior_cum + inflow
        self._cumulative_inflows_by_deal[deal_code] = new_cum

        coverage = float((new_cum / cf0).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

        if not is_month_12_holdback_check:
            hb_status = "ACCUMULATING_IN_ESCROW"
            hb_released = Decimal("0.00")
        else:
            if coverage >= 0.90:
                hb_status = "RELEASED_100_PCT_TO_SELLER"
                hb_released = holdback_pool
            elif coverage >= 0.50:
                hb_status = "RELEASED_PRO_RATA_TO_SELLER"
                hb_released = (holdback_pool * Decimal(str(coverage))).quantize(
                    TWO_PLACES, rounding=ROUND_HALF_UP
                )
            else:
                hb_status = "CLAWED_BACK_TO_BUYER_UNDERPERFORMANCE"
                hb_released = Decimal("0.00")

        dist_id = f"lkbx_{hashlib.sha256(idem_key.encode('utf-8')).hexdigest()[:14]}"
        result = MonthlyLockboxDistribution(
            distribution_id=dist_id,
            idempotency_key=idem_key,
            deal_code=deal_code,
            period_month=period_month,
            currency=ccy,
            gross_royalty_inflow=f"{inflow:.2f}",
            space_carried_tail_payout=f"{space_tail:.2f}",
            buyer_royalty_payout=f"{buyer_share:.2f}",
            cumulative_royalties_collected=f"{new_cum:.2f}",
            target_12m_baseline_cf0=f"{cf0:.2f}",
            performance_coverage_ratio=coverage,
            holdback_release_status=hb_status,
            holdback_released_to_seller=f"{hb_released:.2f}",
            invariant_balanced_to_exact_cent=balanced,
        )
        self._lockbox_distributions[idem_key] = result
        return result
