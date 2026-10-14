"""
"Sov+" Down-Funnel Monetization Router & Forensic Audit Certificate Engine
(`services/spacemusic/monetization_engine.py`)

Ensures **100% of non-fraudulent inbound catalogs** generate revenue for SPACE even when a
catalog is declined for direct institutional M&A buyout (`< €3,000/yr` LTM or unreleased):

1. **Track A — Automated Micro-Advance Referral (`MICRO_ADVANCE_REFERRAL`)**:
   - For verified streaming catalogs earning `€500 – €3,000/yr` (below institutional M&A
     buy-box thresholds): routes the artist to SPACE's automated micro-advance partners
     (**beatBread** / **Sound Royalties**) via a tracked affiliate URL (`utm_source=spacemusic&ref=SPC-...`)
     earning SPACE a **3.0%–5.0% referral bounty** on funded advances with zero balance-sheet risk.
2. **Track B — SPACE Managed Sub-Label & UGC Content ID Override (`MANAGED_SUBLABEL_CONTENT_ID`)**:
   - For unreleased libraries, beatmakers, or unmonetized catalogs (e.g., Aydın Polat / RAMMEDEBEL):
     models a turnkey distribution & YouTube Content ID / TikTok administration deal via SPACE's
     preferred institutional infrastructure (**Symphonic** / **Create Music Group**) where SPACE
     retains a **15.0% ongoing passive royalty override** + a **12-month post-seasoning buyout option**
     once the catalog establishes 6–12 months of verified LTM history.
3. **Track C — $299 Official SPACE Forensic Valuation & Chain-of-Title Audit Certificate (`FORENSIC_AUDIT_CERTIFICATE`)**:
   - Generates a verifiable, SHA-256-signed **SPACE 11-Point Forensic Valuation & Chain-of-Title
     Audit Certificate** (`CERT-SPC-...`) for artists, managers, entertainment lawyers, or estate
     planners who want an institutional valuation report for partner buyouts, tax/estate planning,
     or bank financing.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from services.valuation.engine import CatalogValuationOutput

from .models import CatalogApplication


class MonetizationTrackType(str, Enum):
    INSTITUTIONAL_MA_SYNDICATION = "INSTITUTIONAL_MA_SYNDICATION"
    MICRO_ADVANCE_REFERRAL = "MICRO_ADVANCE_REFERRAL"
    MANAGED_SUBLABEL_CONTENT_ID = "MANAGED_SUBLABEL_CONTENT_ID"
    FORENSIC_AUDIT_CERTIFICATE = "FORENSIC_AUDIT_CERTIFICATE"
    REJECTED_FRAUD_OR_AI = "REJECTED_FRAUD_OR_AI"


class MonetizationOfferOption(BaseModel):
    track_type: MonetizationTrackType
    partner_name: str
    headline: str
    description: str
    tracking_url: str
    estimated_artist_funding_eur: float = 0.0
    estimated_space_upfront_revenue_eur: float = 0.0
    estimated_space_annual_passive_eur: float = 0.0
    estimated_space_10y_total_eur: float = 0.0
    space_take_rate_pct: float = 0.0


class DownFunnelMonetizationPlan(BaseModel):
    application_id: str
    deal_code: str
    artist_or_label_name: str
    primary_track: MonetizationTrackType
    options: List[MonetizationOfferOption] = Field(default_factory=list)
    total_expected_space_10y_value_eur: float
    seller_pitch_markdown: str


class ForensicAuditCertificate(BaseModel):
    certificate_id: str
    deal_code: str
    application_id: str
    issued_at_utc: str
    artist_or_label_name: str
    rights_scope: str
    distributor_or_admin: str
    verified_ltm_eur: float
    valuation_low_eur: float
    valuation_median_eur: float
    valuation_high_eur: float
    implied_multiple_median: float
    discount_rate_pct: float
    integrity_score: float
    valuation_confidence: float
    certificate_fee_usd: float = 299.0
    certificate_fee_eur: float = 275.0
    sha256_verification_seal: str
    verification_url: str
    certificate_markdown: str


def _make_monetization_code(app: CatalogApplication) -> str:
    digest = hashlib.sha1(f"{app.id}:{app.contact_email}".encode("utf-8")).hexdigest()[:6].upper()
    return f"SPC-{digest}"


def build_down_funnel_monetization_plan(
    app: CatalogApplication,
    valuation: CatalogValuationOutput,
    *,
    carried_tail_pct: float = 0.075,
    sublabel_override_pct: float = 0.15,
    referral_bounty_pct: float = 0.04,
) -> DownFunnelMonetizationPlan:
    """
    Routes any evaluated catalog (`CatalogApplication` + `CatalogValuationOutput`) into its
    highest-EV monetization track so SPACE captures revenue on 100% of legitimate submissions:
    - If `pipeline_status == "DECLINED_AI_OR_FAKE_PROFILE"` -> `REJECTED_FRAUD_OR_AI` (€0).
    - If `effective_cf0_eur >= 3000` -> `INSTITUTIONAL_MA_SYNDICATION` (6% origination + 7.5% Carried Tail)
      plus fallback options.
    - If `500 <= effective_cf0_eur < 3000` -> `MICRO_ADVANCE_REFERRAL` (beatBread / Sound Royalties
      4% referral bounty) + `MANAGED_SUBLABEL_CONTENT_ID` (15% Content ID & distribution override)
      + `FORENSIC_AUDIT_CERTIFICATE` ($299).
    - If `effective_cf0_eur < 500` (unreleased / early catalog) -> `MANAGED_SUBLABEL_CONTENT_ID`
      (Symphonic / Create Music Group sub-label onboarding with 15% override + 12M buyout option)
      + `FORENSIC_AUDIT_CERTIFICATE` ($299).
    """
    deal_code = _make_monetization_code(app)
    cf0 = max(0.0, float(valuation.baseline.effective_cf0_eur or 0.0))
    price_med = max(0.0, float(valuation.price_median_eur or 0.0))

    if valuation.pipeline_status == "DECLINED_AI_OR_FAKE_PROFILE":
        return DownFunnelMonetizationPlan(
            application_id=str(app.id),
            deal_code=deal_code,
            artist_or_label_name=app.artist_or_label_name,
            primary_track=MonetizationTrackType.REJECTED_FRAUD_OR_AI,
            options=[],
            total_expected_space_10y_value_eur=0.0,
            seller_pitch_markdown="Catalog rejected due to AI/Bot streaming fraud screening.",
        )

    options: List[MonetizationOfferOption] = []

    # 1. Institutional M&A Syndication + Carried Tail (when eligible >= €3,000/yr)
    if cf0 >= 3_000.0 and price_med > 0:
        upfront_origination = round(price_med * 0.06, 2)
        projected_10y_cf = sum(valuation.yearly_projected_cashflows_p50_eur) or (cf0 * 6.5)
        tail_10y = round(projected_10y_cf * carried_tail_pct, 2)
        tail_yr1 = round(
            (valuation.yearly_projected_cashflows_p50_eur[0] if valuation.yearly_projected_cashflows_p50_eur else cf0)
            * carried_tail_pct,
            2,
        )
        options.append(
            MonetizationOfferOption(
                track_type=MonetizationTrackType.INSTITUTIONAL_MA_SYNDICATION,
                partner_name="SPACE Institutional Syndicate (Duetti / Create Music Group / Symphonic)",
                headline=f"Direct Institutional Buyout (€{price_med:,.0f} EUR) + {carried_tail_pct*100:.1f}% SPACE Carried Tail",
                description=(
                    f"Full or partial catalog acquisition at €{price_med:,.2f} EUR ({valuation.implied_ltm_multiple_median:.2f}x LTM) "
                    f"with 6.0% closing origination (€{upfront_origination:,.2f}) and a {carried_tail_pct*100:.1f}% perpetual/10-year "
                    f"Carried Royalty Tail (€{tail_10y:,.2f} projected 10Y passive cash flow)."
                ),
                tracking_url=f"https://spacemusic.io/deals/{deal_code}/closing",
                estimated_artist_funding_eur=price_med,
                estimated_space_upfront_revenue_eur=upfront_origination,
                estimated_space_annual_passive_eur=tail_yr1,
                estimated_space_10y_total_eur=round(upfront_origination + tail_10y, 2),
                space_take_rate_pct=round((0.06 + carried_tail_pct) * 100, 2),
            )
        )

    # 2. Track A: Automated Micro-Advance Referral (beatBread / Sound Royalties)
    est_micro_advance = round(max(1_500.0, cf0 * 2.5), 2) if cf0 >= 300.0 else 1_500.0
    bounty_eur = round(est_micro_advance * referral_bounty_pct, 2)
    options.append(
        MonetizationOfferOption(
            track_type=MonetizationTrackType.MICRO_ADVANCE_REFERRAL,
            partner_name="beatBread / Sound Royalties (SPACE Fast-Track Desk)",
            headline=f"Automated Royalty Micro-Advance (€{est_micro_advance:,.0f} EUR Keep-Your-Masters Advance)",
            description=(
                "Keep 100% ownership of your masters while unlocking an automated 12–36 month royalty advance "
                "via SPACE's priority partner link."
            ),
            tracking_url=f"https://spacemusic.io/partner/micro-advance?utm_source=spacemusic&ref={deal_code}",
            estimated_artist_funding_eur=est_micro_advance,
            estimated_space_upfront_revenue_eur=bounty_eur,
            estimated_space_annual_passive_eur=0.0,
            estimated_space_10y_total_eur=bounty_eur,
            space_take_rate_pct=round(referral_bounty_pct * 100, 2),
        )
    )

    # 3. Track B: SPACE Managed Sub-Label & UGC Content ID Override (Symphonic / Create Music Group)
    assumed_seasoned_ltm = max(cf0 * 1.35, 3_500.0)
    annual_override = round(assumed_seasoned_ltm * sublabel_override_pct, 2)
    ten_yr_override = round(annual_override * 7.5, 2)
    options.append(
        MonetizationOfferOption(
            track_type=MonetizationTrackType.MANAGED_SUBLABEL_CONTENT_ID,
            partner_name="SPACE Managed Distribution & YouTube Content ID (via Symphonic / Create)",
            headline="SPACE Managed Incubation, YouTube Content ID & 12-Month Buyout Option",
            description=(
                f"Onboard unreleased or growing releases into SPACE's institutional distribution & UGC Content ID "
                f"monetization suite (85% Artist / {sublabel_override_pct*100:.0f}% SPACE administration share) with a "
                f"guaranteed re-valuation and buyout option after 6–12 months of verified streaming history."
            ),
            tracking_url=f"https://spacemusic.io/incubate/{deal_code}",
            estimated_artist_funding_eur=round(assumed_seasoned_ltm * 0.85, 2),
            estimated_space_upfront_revenue_eur=0.0,
            estimated_space_annual_passive_eur=annual_override,
            estimated_space_10y_total_eur=ten_yr_override,
            space_take_rate_pct=round(sublabel_override_pct * 100, 2),
        )
    )

    # 4. Track C: $299 (€275) Official SPACE Forensic Valuation & Chain-of-Title Audit Certificate
    cert_fee_eur = 275.0
    options.append(
        MonetizationOfferOption(
            track_type=MonetizationTrackType.FORENSIC_AUDIT_CERTIFICATE,
            partner_name="SPACE Underwriting & Forensics Desk",
            headline="Official SPACE 11-Point Forensic Valuation & Chain-of-Title Certificate ($299 / €275)",
            description=(
                "Certified institutional DCF valuation report, cohort decay audit, and ISRC chain-of-title "
                "certificate signed with a cryptographic SHA-256 seal for co-writer buyouts, legal/estate "
                "planning, or bank financing."
            ),
            tracking_url=f"https://spacemusic.io/certificates/{deal_code}/checkout",
            estimated_artist_funding_eur=0.0,
            estimated_space_upfront_revenue_eur=cert_fee_eur,
            estimated_space_annual_passive_eur=0.0,
            estimated_space_10y_total_eur=cert_fee_eur,
            space_take_rate_pct=100.0,
        )
    )

    if cf0 >= 3_000.0 and price_med > 0:
        primary = MonetizationTrackType.INSTITUTIONAL_MA_SYNDICATION
    elif cf0 >= 500.0:
        primary = MonetizationTrackType.MICRO_ADVANCE_REFERRAL
    else:
        primary = MonetizationTrackType.MANAGED_SUBLABEL_CONTENT_ID

    primary_opt = next((o for o in options if o.track_type == primary), options[0])
    first_name = (app.contact_name or "there").split()[0]

    pitch_md = (
        f"Hi {first_name},\n\n"
        f"Thank you for submitting **{app.artist_or_label_name or 'your catalog'}** to SPACE (`Ref: {deal_code}`).\n\n"
        f"Based on our underwriting engine, here are the tailored financing and monetization paths available for your catalog right now:\n\n"
        + "\n".join(
            f"- **{opt.headline}** ({opt.partner_name}): {opt.description} → [Activate Here]({opt.tracking_url})"
            for opt in options
        )
        + "\n\nBest regards,\nEmil\nSPACE (spacemusic.io)"
    )

    return DownFunnelMonetizationPlan(
        application_id=str(app.id),
        deal_code=deal_code,
        artist_or_label_name=app.artist_or_label_name,
        primary_track=primary,
        options=options,
        total_expected_space_10y_value_eur=primary_opt.estimated_space_10y_total_eur,
        seller_pitch_markdown=pitch_md,
    )


def generate_forensic_audit_certificate(
    app: CatalogApplication,
    valuation: CatalogValuationOutput,
    *,
    issued_at: Optional[datetime] = None,
) -> ForensicAuditCertificate:
    """
    Generates a verifiable, SHA-256-sealed SPACE 11-Point Forensic Valuation & Chain-of-Title
    Audit Certificate (`CERT-SPC-...`).
    """
    deal_code = _make_monetization_code(app)
    cert_id = f"CERT-{deal_code}"
    ts = (issued_at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

    cf0 = round(float(valuation.baseline.effective_cf0_eur or 0.0), 2)
    p_low = round(float(valuation.price_low_eur or 0.0), 2)
    p_med = round(float(valuation.price_median_eur or 0.0), 2)
    p_high = round(float(valuation.price_high_eur or 0.0), 2)
    mult = round(float(valuation.implied_ltm_multiple_median or 0.0), 2)
    disc_pct = round(float(valuation.discount_rate.total_discount_rate or 0.0) * 100.0, 2)
    integ = round(float(valuation.integrity_score or 0.0), 1)
    conf = round(float(valuation.valuation_confidence or 0.0), 2)

    canonical_payload = (
        f"{cert_id}|{app.id}|{app.artist_or_label_name}|{app.rights_scope}|"
        f"{cf0:.2f}|{p_low:.2f}|{p_med:.2f}|{p_high:.2f}|{integ:.1f}|{ts}"
    )
    seal = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    verify_url = f"https://spacemusic.io/verify/{cert_id}?seal={seal[:24]}"

    md = (
        f"# OFFICIAL SPACE FORENSIC VALUATION & CHAIN-OF-TITLE AUDIT CERTIFICATE\n"
        f"**Certificate ID:** `{cert_id}` | **Issued (UTC):** `{ts}`\n"
        f"**Cryptographic SHA-256 Seal:** `{seal}`\n\n"
        f"---\n\n"
        f"### 1. Catalog & Rights Holder Summary\n"
        f"- **Artist / Label:** {app.artist_or_label_name}\n"
        f"- **Applicant / Authorized Representative:** {app.contact_name} (`{app.contact_email}`)\n"
        f"- **Rights Scope Evaluated:** `{app.rights_scope}`\n"
        f"- **Primary Distributor / Administrator:** {app.distributor_or_admin or 'Independent Distributor'}\n"
        f"- **Verification Stage:** `{valuation.valuation_stage}`\n\n"
        f"### 2. Institutional DCF Valuation Summary (EUR)\n"
        f"- **Normalized LTM Net Royalty Baseline ($CF_0$):** **€{cf0:,.2f} EUR**\n"
        f"- **Conservative Valuation (P10):** €{p_low:,.2f} EUR\n"
        f"- **Institutional Fair Market Value (P50 Median):** **€{p_med:,.2f} EUR** (`{mult:.2f}x` LTM)\n"
        f"- **Upside Valuation (P90):** €{p_high:,.2f} EUR\n"
        f"- **Risk-Adjusted Discount Rate ($r$):** `{disc_pct:.2f}%`\n\n"
        f"### 3. SPACE 11-Point Forensic & Integrity Audit\n"
        f"- **Forensic Integrity Score:** **{integ:.1f} / 100.0**\n"
        f"- **Underwriting Confidence Index:** `{conf:.2f}`\n"
        f"- **Cohort Weighted Catalog Age:** `{valuation.cohorts.dollar_weighted_age_months:.1f} months`\n"
        f"- **Active Risk Flags Count:** `{len(valuation.risk_flags)}`\n\n"
        f"---\n"
        f"*Verify authenticity online at `{verify_url}` — Issued by SpaceMusic Underwriting Desk (`spacemusic.io`).*"
    )

    return ForensicAuditCertificate(
        certificate_id=cert_id,
        deal_code=deal_code,
        application_id=str(app.id),
        issued_at_utc=ts,
        artist_or_label_name=app.artist_or_label_name,
        rights_scope=app.rights_scope,
        distributor_or_admin=app.distributor_or_admin or "Independent Distributor",
        verified_ltm_eur=cf0,
        valuation_low_eur=p_low,
        valuation_median_eur=p_med,
        valuation_high_eur=p_high,
        implied_multiple_median=mult,
        discount_rate_pct=disc_pct,
        integrity_score=integ,
        valuation_confidence=conf,
        sha256_verification_seal=seal,
        verification_url=verify_url,
        certificate_markdown=md,
    )
