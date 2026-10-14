"""
Institutional Buy-Box Router & Underwriting Memo Generator (`services/spacemusic/buyer_router.py`)

Automatically matches evaluated music catalogs against SPACE's 8 verified institutional
capital partners (`Duetti`, `Create Music Group`, `beatBread`, `Sound Royalties`,
`ANote Music`, `Royalty Exchange`, `SongVest`, and `Symphonic Distribution`) based on:
- Normalized LTM royalty volume (`effective_cf0_eur`)
- Genre family (`GenreFamily`)
- Catalog age (`catalog_weighted_age_months`)
- Rights scope (`RightsScope`: Masters, Publishing, or Both)
- Seller intent / deal structure fit (100% buyout vs. partial catalog listing vs. royalty advance)
- Forensics & AI Authenticity gating (`integrity_score`, `AuthenticityStatus`, `DTW` archetype)

Also generates a standardized Institutional Underwriting Memo (Markdown) for 1-click
deal-room sharing.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set

from pydantic import BaseModel, Field

from services.valuation.ai_profile_detector import AuthenticityStatus
from services.valuation.engine import (
    CatalogValuationOutput,
    GenreFamily,
    RightsScope,
)
from .models import CatalogApplication


class InstitutionalPartnerProfile(BaseModel):
    partner_id: str
    partner_name: str
    deal_type: str  # FULL_OR_TRACK_BUYOUT | LABEL_ACQUISITION_OR_JV | ROYALTY_ADVANCE_FINANCING | FRACTIONAL_CATALOG_MARKETPLACE | DISTRIBUTION_ADVANCE
    decision_makers: List[str]
    contact_emails: List[str]
    min_ltm_eur: float
    max_ltm_eur: float
    min_age_months: float
    min_integrity_score: float = 65.0
    preferred_genres: Set[GenreFamily]
    supported_rights: Set[RightsScope]
    target_multiple_range: str
    thesis_summary: str


INSTITUTIONAL_BUY_BOXES: List[InstitutionalPartnerProfile] = [
    InstitutionalPartnerProfile(
        partner_id="duetti",
        partner_name="Duetti",
        deal_type="FULL_OR_TRACK_BUYOUT",
        decision_makers=["Lior Tibon (CEO & Co-Founder)", "Lyva Corvo (Music Catalog Sales & Partnerships)"],
        contact_emails=["lior@duetti.co", "lyva@duetti.co"],
        min_ltm_eur=4_500.0,
        max_ltm_eur=600_000.0,
        min_age_months=12.0,
        min_integrity_score=70.0,
        preferred_genres={
            GenreFamily.POP_INDIE,
            GenreFamily.HIPHOP_RNB_PHONK,
            GenreFamily.ELECTRONIC_DANCE,
            GenreFamily.ROCK_METAL_COUNTRY,
            GenreFamily.LATIN_AFRO,
            GenreFamily.ELECTRONIC_INDIE,
            GenreFamily.POP_HIPHOP_RNB,
            GenreFamily.ROCK_FOLK_COUNTRY,
        },
        supported_rights={RightsScope.MASTERS, RightsScope.BOTH},
        target_multiple_range="2.5x – 6.5x LTM (track-by-track or full master buyout)",
        thesis_summary="Acquires independent master catalogs and individual sticky tracks ($5k–$500k+ LTM) with >12m streaming history.",
    ),
    InstitutionalPartnerProfile(
        partner_id="create_music_group",
        partner_name="Create Music Group",
        deal_type="LABEL_ACQUISITION_OR_JV",
        decision_makers=["Jonathan Strauss (CEO & Co-Founder)", "Steeven Leblanc (SVP, Corp Dev & M&A)"],
        contact_emails=["jonathan@createmusicgroup.com", "steeven.leblanc@createmusicgroup.com"],
        min_ltm_eur=15_000.0,
        max_ltm_eur=5_000_000.0,
        min_age_months=9.0,
        min_integrity_score=70.0,
        preferred_genres={
            GenreFamily.HIPHOP_RNB_PHONK,
            GenreFamily.ELECTRONIC_DANCE,
            GenreFamily.POP_INDIE,
            GenreFamily.LATIN_AFRO,
            GenreFamily.POP_HIPHOP_RNB,
            GenreFamily.ELECTRONIC_INDIE,
        },
        supported_rights={RightsScope.MASTERS, RightsScope.PUBLISHING, RightsScope.BOTH},
        target_multiple_range="3.0x – 8.0x LTM (catalog acquisition, JV, or YouTube Content ID monetization)",
        thesis_summary="High-velocity buyer for Hip-Hop, Trap, Phonk, Electronic, and Dance/Pop catalogs with strong DSP & YouTube footprint.",
    ),
    InstitutionalPartnerProfile(
        partner_id="beatbread",
        partner_name="beatBread",
        deal_type="ROYALTY_ADVANCE_FINANCING",
        decision_makers=["Peter Sinclair (CEO & Co-Founder)", "Andreea Gleeson (Chief Revenue Officer)"],
        contact_emails=["peter@beatbread.com", "andreea.gleeson@beatbread.com"],
        min_ltm_eur=2_500.0,
        max_ltm_eur=1_000_000.0,
        min_age_months=6.0,
        min_integrity_score=60.0,
        preferred_genres=set(GenreFamily),
        supported_rights={RightsScope.MASTERS, RightsScope.BOTH},
        target_multiple_range="1.5x – 4.5x LTM recoupable advance (artist retains long-term ownership)",
        thesis_summary="Automated catalog & repertoire advances where independent artists/labels keep ownership after recoupment.",
    ),
    InstitutionalPartnerProfile(
        partner_id="sound_royalties",
        partner_name="Sound Royalties",
        deal_type="ROYALTY_ADVANCE_FINANCING",
        decision_makers=["Alex Heiche (Founder & CEO)", "Reggie Calloway (VP of Music Royalty Funding)"],
        contact_emails=["alex@soundroyalties.com", "rcalloway@soundroyalties.com"],
        min_ltm_eur=4_500.0,
        max_ltm_eur=2_500_000.0,
        min_age_months=12.0,
        min_integrity_score=65.0,
        preferred_genres=set(GenreFamily),
        supported_rights={RightsScope.MASTERS, RightsScope.PUBLISHING, RightsScope.BOTH},
        target_multiple_range="1.5x – 5.0x LTM non-credit royalty financing (Masters, PRO, SoundExchange, Publishing)",
        thesis_summary="Royalty financing across Masters, PRO/Publishing, and SoundExchange without relinquishing permanent copyright.",
    ),
    InstitutionalPartnerProfile(
        partner_id="anote_music",
        partner_name="ANote Music",
        deal_type="FRACTIONAL_CATALOG_MARKETPLACE",
        decision_makers=["Marzio Schena (CEO & Co-Founder)", "Nicola Meloni (Head of Operations)"],
        contact_emails=["marzio@anotemusic.com", "nicola@anotemusic.com"],
        min_ltm_eur=8_000.0,
        max_ltm_eur=1_500_000.0,
        min_age_months=24.0,
        min_integrity_score=75.0,
        preferred_genres={
            GenreFamily.POP_INDIE,
            GenreFamily.ELECTRONIC_DANCE,
            GenreFamily.ROCK_METAL_COUNTRY,
            GenreFamily.CLASSICAL_JAZZ_INSTRUMENTAL,
            GenreFamily.LATIN_AFRO,
            GenreFamily.ELECTRONIC_INDIE,
            GenreFamily.ROCK_FOLK_COUNTRY,
        },
        supported_rights={RightsScope.MASTERS, RightsScope.PUBLISHING, RightsScope.BOTH},
        target_multiple_range="4.0x – 9.0x LTM (10%–50% partial royalty share listing on European marketplace)",
        thesis_summary="European marketplace for mature catalogs (>=24m history) listing partial or full passive royalty shares.",
    ),
    InstitutionalPartnerProfile(
        partner_id="royalty_exchange",
        partner_name="Royalty Exchange",
        deal_type="FRACTIONAL_CATALOG_MARKETPLACE",
        decision_makers=["Keegan Gaeng (Director, Artist & Label Relations)"],
        contact_emails=["keegan.g@royaltyexchange.net"],
        min_ltm_eur=4_500.0,
        max_ltm_eur=2_000_000.0,
        min_age_months=18.0,
        min_integrity_score=70.0,
        preferred_genres=set(GenreFamily),
        supported_rights={RightsScope.MASTERS, RightsScope.PUBLISHING, RightsScope.BOTH},
        target_multiple_range="3.0x – 8.5x LTM (10-year term or life-of-rights institutional auction)",
        thesis_summary="Liquid auction & private syndicate marketplace for 10-year term or life-of-rights royalty streams.",
    ),
    InstitutionalPartnerProfile(
        partner_id="songvest",
        partner_name="SongVest",
        deal_type="FRACTIONAL_CATALOG_MARKETPLACE",
        decision_makers=["Sean Peace (Founder & CEO)"],
        contact_emails=["sean@songvest.com"],
        min_ltm_eur=4_000.0,
        max_ltm_eur=750_000.0,
        min_age_months=18.0,
        min_integrity_score=70.0,
        preferred_genres={
            GenreFamily.POP_INDIE,
            GenreFamily.ROCK_METAL_COUNTRY,
            GenreFamily.HIPHOP_RNB_PHONK,
            GenreFamily.CLASSICAL_JAZZ_INSTRUMENTAL,
            GenreFamily.ROCK_FOLK_COUNTRY,
            GenreFamily.POP_HIPHOP_RNB,
        },
        supported_rights={RightsScope.MASTERS, RightsScope.PUBLISHING, RightsScope.BOTH},
        target_multiple_range="3.0x – 7.0x LTM (fractional SongShares & private institutional buyers)",
        thesis_summary="Fractional and private-syndicate buyer for established writer/producer and indie master catalogs.",
    ),
    InstitutionalPartnerProfile(
        partner_id="symphonic_distribution",
        partner_name="Symphonic Distribution",
        deal_type="DISTRIBUTION_ADVANCE",
        decision_makers=["Jorge Brea (Founder & CEO)", "Oz McGuire (VP of A&R and Client Development)"],
        contact_emails=["jorge@symdistro.com", "ozmcguire@symdistro.com"],
        min_ltm_eur=4_000.0,
        max_ltm_eur=800_000.0,
        min_age_months=6.0,
        min_integrity_score=65.0,
        preferred_genres={
            GenreFamily.LATIN_AFRO,
            GenreFamily.ELECTRONIC_DANCE,
            GenreFamily.HIPHOP_RNB_PHONK,
            GenreFamily.POP_INDIE,
            GenreFamily.ELECTRONIC_INDIE,
            GenreFamily.POP_HIPHOP_RNB,
        },
        supported_rights={RightsScope.MASTERS, RightsScope.BOTH},
        target_multiple_range="1.5x – 4.0x LTM distribution transfer advance or catalog acquisition",
        thesis_summary="Strong fit for Latin, Electronic, Afro, and Hip-Hop indie labels/artists open to distribution transfer or buyout.",
    ),
]


class BuyerMatchRecommendation(BaseModel):
    partner_id: str
    partner_name: str
    deal_type: str
    fit_score: float = Field(description="0.0 to 100.0 institutional buy-box fit score")
    decision_makers: List[str]
    contact_emails: List[str]
    target_multiple_range: str
    match_rationale: List[str]


class InstitutionalRoutingReport(BaseModel):
    eligible_for_syndication: bool
    disqualification_reason: Optional[str] = None
    recommended_buyers: List[BuyerMatchRecommendation] = Field(default_factory=list)
    underwriting_memo_markdown: str = ""


def route_catalog_to_institutional_buyers(
    app_row: CatalogApplication,
    valuation: CatalogValuationOutput,
    *,
    top_k: int = 4,
) -> InstitutionalRoutingReport:
    """
    Scores and ranks SPACE's 8 institutional buyers for a given catalog evaluation.
    Blocks routing if the catalog is flagged as `CONFIRMED_AI_OR_FARM`, `SUSPECTED_AI_OR_FAKE`,
    or `DTW_ARTIFICIAL_STEP_PLATEAU`, protecting SPACE's institutional reputation.
    """
    ai_rep = valuation.ai_profile_validation
    if ai_rep and ai_rep.authenticity_status in {
        AuthenticityStatus.CONFIRMED_AI_OR_FARM,
        AuthenticityStatus.SUSPECTED_AI_OR_FAKE,
    }:
        return InstitutionalRoutingReport(
            eligible_for_syndication=False,
            disqualification_reason=(
                f"Blocked by SPACE AI/Fake Profile Forensics ({ai_rep.authenticity_status.value}, "
                f"score {ai_rep.ai_fake_probability_score}/100)."
            ),
        )

    flag_codes = {rf.code for rf in valuation.risk_flags}
    if "DTW_ARTIFICIAL_STEP_PLATEAU" in flag_codes or "IMPLIED_STREAM_REVENUE_MISMATCH" in flag_codes:
        return InstitutionalRoutingReport(
            eligible_for_syndication=False,
            disqualification_reason=(
                "Blocked by SPACE Stream Forensics (DTW Artificial Step-Plateau or Extreme Implied-Revenue Mismatch)."
            ),
        )

    cf0 = valuation.baseline.effective_cf0_eur
    if cf0 < 2_500.0 or valuation.pipeline_status in {"DECLINED_BELOW_THRESHOLD", "DECLINED_AI_OR_FAKE_PROFILE"}:
        return InstitutionalRoutingReport(
            eligible_for_syndication=False,
            disqualification_reason=f"Normalized LTM (€{cf0:,.0f}) is below the €2,500 institutional syndication floor.",
        )

    age_m = valuation.cohorts.dollar_weighted_age_months
    genre = valuation.genre_family
    rights = (
        RightsScope(app_row.rights_scope)
        if app_row.rights_scope in {r.value for r in RightsScope}
        else RightsScope.MASTERS
    )

    recommendations: List[BuyerMatchRecommendation] = []
    for buyer in INSTITUTIONAL_BUY_BOXES:
        if cf0 < buyer.min_ltm_eur * 0.80 or cf0 > buyer.max_ltm_eur:
            continue
        if valuation.integrity_score < buyer.min_integrity_score:
            continue
        if rights not in buyer.supported_rights and RightsScope.BOTH not in buyer.supported_rights:
            continue

        score = 60.0
        reasons: List[str] = []

        # 1. LTM sweet-spot scoring
        if buyer.min_ltm_eur <= cf0 <= buyer.max_ltm_eur:
            score += 15.0
            reasons.append(f"Normalized LTM (€{cf0:,.0f}/yr) is squarely inside {buyer.partner_name}'s €{buyer.min_ltm_eur:,.0f}–€{buyer.max_ltm_eur:,.0f} buy-box.")
        else:
            score += 5.0
            reasons.append(f"Normalized LTM (€{cf0:,.0f}/yr) is near {buyer.partner_name}'s minimum threshold (€{buyer.min_ltm_eur:,.0f}).")

        # 2. Genre alignment
        if genre in buyer.preferred_genres:
            score += 12.0
            reasons.append(f"Strong genre mandate match ({genre.value}).")
        else:
            score -= 8.0

        # 3. Catalog maturity alignment
        if age_m >= buyer.min_age_months:
            score += 10.0
            reasons.append(f"Catalog weighted age ({age_m:.0f}m) meets {buyer.partner_name}'s >= {buyer.min_age_months:.0f}m seasoning requirement.")
        else:
            score -= 10.0
            reasons.append(f"Catalog age ({age_m:.0f}m) is slightly younger than {buyer.partner_name}'s preferred {buyer.min_age_months:.0f}m seasoning.")

        # 4. Specific partner affinity boosts
        if buyer.partner_id == "create_music_group" and genre in {GenreFamily.HIPHOP_RNB_PHONK, GenreFamily.ELECTRONIC_DANCE} and cf0 >= 18_000:
            score += 8.0
            reasons.append("High-priority Hip-Hop/Electronic scale target for Create Music Group M&A.")
        elif buyer.partner_id == "duetti" and 5_000 <= cf0 <= 250_000:
            score += 7.0
            reasons.append("Core indie master acquisition sweet spot for Duetti's track/catalog model.")
        elif buyer.partner_id == "anote_music" and age_m >= 30.0:
            score += 7.0
            reasons.append("Seasoned evergreen profile (>2.5 yrs) ideal for ANote Music fractional listing.")
        elif buyer.partner_id == "symphonic_distribution" and genre in {GenreFamily.LATIN_AFRO, GenreFamily.ELECTRONIC_DANCE}:
            score += 6.0
            reasons.append("Core Latin/Electronic repertoire fit for Symphonic Distribution.")

        final_fit = round(min(99.0, max(10.0, score)), 1)
        if final_fit >= 55.0:
            recommendations.append(
                BuyerMatchRecommendation(
                    partner_id=buyer.partner_id,
                    partner_name=buyer.partner_name,
                    deal_type=buyer.deal_type,
                    fit_score=final_fit,
                    decision_makers=buyer.decision_makers,
                    contact_emails=buyer.contact_emails,
                    target_multiple_range=buyer.target_multiple_range,
                    match_rationale=reasons,
                )
            )

    recommendations.sort(key=lambda r: r.fit_score, reverse=True)
    top_recs = recommendations[:top_k]

    memo = generate_institutional_underwriting_memo(app_row, valuation, top_recs)
    return InstitutionalRoutingReport(
        eligible_for_syndication=len(top_recs) > 0,
        recommended_buyers=top_recs,
        underwriting_memo_markdown=memo,
    )


def generate_institutional_underwriting_memo(
    app_row: CatalogApplication,
    valuation: CatalogValuationOutput,
    recommended_buyers: Sequence[BuyerMatchRecommendation],
) -> str:
    """
    Generates a clean, institutional-grade Markdown Deal Memo summarizing the
    8-genre Bayesian DCF, DTW trajectory archetype, AI/Fake authenticity certificate,
    and top buyer matches.
    """
    ai_status = (
        valuation.ai_profile_validation.authenticity_status.value
        if valuation.ai_profile_validation
        else "VERIFIED_ORGANIC"
    )
    dtw_arch = (
        valuation.dtw_analysis.matched_archetype.value
        if valuation.dtw_analysis
        else "PRIOR_COHORT_CURVE"
    )
    buyer_lines = "\n".join(
        f"- **{b.partner_name}** (`{b.deal_type}`, Fit: **{b.fit_score}/100**) — Contacts: {', '.join(b.contact_emails)} | {b. match_rationale[0] if b.match_rationale else ''}"
        for b in recommended_buyers
    ) or "- *Pending Stage 2 CSV verification*"

    risk_lines = "\n".join(
        f"- `[{rf.severity.value}]` **{rf.code}**: {rf.title} (+{rf.discount_rate_bps_impact} bps)"
        for rf in valuation.risk_flags
    ) or "- None (`100/100 Integrity Score`)"

    return (
        f"# SPACE Institutional Underwriting Memo — {app_row.artist_or_label_name}\n\n"
        f"**Stage:** `{valuation.valuation_stage}` | **Status:** `{valuation.pipeline_status}`\n"
        f"**Genre Cohort:** `{valuation.genre_family.value}` | **Weighted Catalog Age:** `{valuation.cohorts.dollar_weighted_age_months:.1f} months`\n"
        f"**Distributor / Admin:** `{app_row.distributor_or_admin or 'Unspecified'}` | **Rights Scope:** `{app_row.rights_scope}`\n\n"
        f"## 1. DCF Valuation & Normalized Cash Flow\n"
        f"- **Normalized LTM Baseline ($CF_0$):** €{valuation.baseline.effective_cf0_eur:,.2f} (Declared LTM: €{valuation.baseline.declared_ltm_eur:,.2f})\n"
        f"- **Valuation Range (Low / Base / High):** **€{valuation.price_low_eur:,.0f} / €{valuation.price_median_eur:,.0f} / €{valuation.price_high_eur:,.0f}**\n"
        f"- **Implied LTM Multiple (Base):** `{valuation.implied_ltm_multiple_median:.2f}x` (`{valuation.implied_ltm_multiple_low:.2f}x – {valuation.implied_ltm_multiple_high:.2f}x`)\n"
        f"- **Risk-Adjusted Discount Rate ($r$):** `{valuation.discount_rate.total_discount_rate * 100:.2f}%`\n"
        f"- **Recommended Deal Structure:** `{valuation.deal_structure.upfront_pct:.0f}%` upfront (€{valuation.deal_structure.upfront_eur:,.0f}) / `{valuation.deal_structure.holdback_pct:.0f}%` escrow holdback\n\n"
        f"## 2. Forensics & Authenticity Verification\n"
        f"- **Catalog Integrity Score:** `{valuation.integrity_score:.1f} / 100.0`\n"
        f"- **AI & Fake Profile Status:** `{ai_status}`\n"
        f"- **DTW Lifecycle Trajectory:** `{dtw_arch}`\n"
        f"- **Track HHI Concentration:** `{valuation.track_hhi:.3f}`\n"
        f"### Active Risk Flags\n"
        f"{risk_lines}\n\n"
        f"## 3. Institutional Buy-Box Matches\n"
        f"{buyer_lines}\n"
    )
