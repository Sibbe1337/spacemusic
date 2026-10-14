"""
Typeform Adapter (`xzx5SBJb` - SPACE catalog review) & Automated Reply Draft Generator
(`services/spacemusic/typeform_adapter.py`)
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from services.valuation.engine import (
    CatalogValuationInput,
    CatalogValuationOutput,
    RightsScope,
    RoyaltyBasis,
    is_distributor_name,
)
from .models import CatalogApplication, ReplyDraft


# Exact field IDs from Typeform `xzx5SBJb` ("SPACE catalog review")
TYPEFORM_FIELD_IDS = {
    "ZynDs8tkxlJF": "inquiry_route",
    "cIEzRJe4jZWW": "contact_name",
    "oY3yxQa3CAD3": "contact_email",
    "kvxzy30bsRuE": "artist_or_label_name",
    "v8zF9mHvsniN": "listen_url",
    "OqKtPOGC9Hdg": "rights_scope",
    "W8Bb4Ax6Xgl9": "owner_authorized",
    "5i9TtGJ1Upta": "knows_ltm_royalties",
    "CKyv4Tu2q2qS": "declared_ltm_amount",
    "DN8Au6nFTIIa": "declared_currency",
    "xI8yrwFcihKF": "royalty_basis",
    "dMwecIGMIyrp": "distributor_or_admin",
    "jVSpoJtOlUJ6": "rights_notes",
    "yxNKmEUYo0jp": "organization_name",
    "vCGtrW7Qm1CA": "organization_website",
    "zmUSKFsE4iRz": "partnership_topic",
    "vMbAcO69sEXP": "referral_source",
    "ZUo7UF5L5nP0": "newsletter_opt_in",
}


def extract_spotify_artist_id(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    m = re.search(r"open\.spotify\.com/(?:intl-[a-z]{2}/)?artist/([A-Za-z0-9]{22})", url)
    if m:
        return m.group(1)
    m_uri = re.search(r"spotify:artist:([A-Za-z0-9]{22})", url)
    if m_uri:
        return m_uri.group(1)
    return None


def _extract_answer_value(ans: Dict[str, Any]) -> Any:
    ans_type = ans.get("type", "")
    if ans_type == "choice":
        return ans.get("choice", {}).get("label") or ans.get("choice", {}).get("other")
    if ans_type == "choices":
        labels = ans.get("choices", {}).get("labels", [])
        return ", ".join(labels)
    if ans_type in {"text", "email", "url"}:
        return ans.get(ans_type)
    if ans_type == "number":
        return ans.get("number")
    if ans_type == "boolean":
        return ans.get("boolean")
    # Fallback
    for k in ("text", "email", "url", "number", "boolean"):
        if k in ans:
            return ans[k]
    return None


def _parse_numeric_amount(raw: Any) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(",", "").replace(" ", "")
    # Handle "5.6k" or "12k"
    m_k = re.search(r"(\d+(?:\.\d+)?)\s*[kK]", s)
    if m_k:
        return float(m_k.group(1)) * 1000.0
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else 0.0


def _map_inquiry_route(label: Optional[str]) -> str:
    if not label:
        return "own_catalog"
    s = label.lower()
    if "represent" in s:
        return "represented_catalog"
    if "partnership" in s or "another inquiry" in s:
        return "partnership"
    return "own_catalog"


def _map_rights_scope(label: Optional[str]) -> RightsScope:
    if not label:
        return RightsScope.MASTERS
    s = label.lower()
    if "both" in s:
        return RightsScope.BOTH
    if "publishing" in s:
        return RightsScope.PUBLISHING
    if "master" in s:
        return RightsScope.MASTERS
    return RightsScope.UNKNOWN


def _map_royalty_basis(label: Optional[str]) -> RoyaltyBasis:
    if not label:
        return RoyaltyBasis.NET_PAYABLE
    s = label.lower()
    if "before" in s:
        return RoyaltyBasis.GROSS_BEFORE_DEDUCTIONS
    if "not sure" in s or "unsure" in s:
        return RoyaltyBasis.UNSURE
    return RoyaltyBasis.NET_PAYABLE


def parse_typeform_webhook_payload(payload: Dict[str, Any]) -> CatalogApplication:
    """
    Parses a Typeform `form_response` webhook payload for form `xzx5SBJb`
    (or a flat JSON dict in the same schema) into a `CatalogApplication` instance.
    """
    form_response = payload.get("form_response", payload)
    response_id = form_response.get("token") or payload.get("event_id")
    form_id = form_response.get("form_id", "xzx5SBJb")

    extracted: Dict[str, Any] = {}
    answers = form_response.get("answers", [])
    for ans in answers:
        field_id = ans.get("field", {}).get("id") or ans.get("field", {}).get("ref")
        canonical_key = TYPEFORM_FIELD_IDS.get(field_id)
        if canonical_key:
            extracted[canonical_key] = _extract_answer_value(ans)

    # Also allow direct flat dictionary fields if submitted via internal API
    for canonical_key in TYPEFORM_FIELD_IDS.values():
        if canonical_key not in extracted and canonical_key in payload:
            extracted[canonical_key] = payload[canonical_key]

    route = _map_inquiry_route(extracted.get("inquiry_route"))
    rights = _map_rights_scope(extracted.get("rights_scope"))
    basis = _map_royalty_basis(extracted.get("royalty_basis"))

    auth_raw = str(extracted.get("owner_authorized", "Yes")).lower()
    owner_authorized = "still need" not in auth_raw and "no" not in auth_raw

    knows_raw = str(extracted.get("knows_ltm_royalties", "I can provide")).lower()
    knows_ltm = "need to check" not in knows_raw

    ltm_amount = _parse_numeric_amount(extracted.get("declared_ltm_amount"))
    currency = (str(extracted.get("declared_currency") or "USD").strip().upper()[:3]) or "USD"
    listen_url = extracted.get("listen_url")
    spotify_id = extract_spotify_artist_id(listen_url)

    opt_in_raw = str(extracted.get("newsletter_opt_in", "No")).lower()
    newsletter_opt_in = opt_in_raw in {"yes", "true", "1"}

    return CatalogApplication(
        typeform_response_id=response_id,
        typeform_form_id=form_id,
        inquiry_route=route,
        contact_name=str(extracted.get("contact_name") or "").strip(),
        contact_email=str(extracted.get("contact_email") or "").strip(),
        artist_or_label_name=str(extracted.get("artist_or_label_name") or "").strip(),
        listen_url=listen_url,
        spotify_artist_id=spotify_id,
        rights_scope=rights.value,
        owner_authorized=owner_authorized,
        knows_ltm_royalties=knows_ltm,
        declared_ltm_amount=ltm_amount,
        declared_currency=currency,
        royalty_basis=basis.value,
        distributor_or_admin=extracted.get("distributor_or_admin"),
        rights_notes=extracted.get("rights_notes"),
        organization_name=extracted.get("organization_name"),
        organization_website=extracted.get("organization_website"),
        partnership_topic=extracted.get("partnership_topic"),
        referral_source=extracted.get("referral_source"),
        newsletter_opt_in=newsletter_opt_in,
    )


def application_to_valuation_input(app_row: CatalogApplication) -> CatalogValuationInput:
    # Check if rights_notes mentions partial ownership percentage (e.g. "50%")
    ownership_pct = 100.0
    if app_row.rights_notes:
        m_pct = re.search(r"(\d{1,3})\s*%", app_row.rights_notes)
        if m_pct:
            val = float(m_pct.group(1))
            if 1.0 <= val <= 100.0:
                ownership_pct = val

    return CatalogValuationInput(
        catalog_title=f"{app_row.artist_or_label_name or app_row.contact_name} Catalog",
        artist_or_label_name=app_row.artist_or_label_name,
        applicant_name=app_row.contact_name,
        applicant_email=app_row.contact_email,
        representation_type=app_row.inquiry_route,
        owner_authorized=app_row.owner_authorized,
        listen_url=app_row.listen_url,
        spotify_artist_id=app_row.spotify_artist_id,
        rights_scope=RightsScope(app_row.rights_scope)
        if app_row.rights_scope in {r.value for r in RightsScope}
        else RightsScope.MASTERS,
        royalty_basis=RoyaltyBasis(app_row.royalty_basis)
        if app_row.royalty_basis in {b.value for b in RoyaltyBasis}
        else RoyaltyBasis.NET_PAYABLE,
        distributor_or_admin=app_row.distributor_or_admin,
        ownership_share_pct=ownership_pct,
        declared_ltm_amount=app_row.declared_ltm_amount,
        declared_currency=app_row.declared_currency,
        statements_verified=app_row.statements_verified,
        notes=app_row.rights_notes,
    )


def generate_reply_draft(
    app_row: CatalogApplication,
    valuation: CatalogValuationOutput,
) -> ReplyDraft:
    first_name = (app_row.contact_name or "there").split()[0]
    dist_name = app_row.distributor_or_admin or "your distributor"

    if app_row.inquiry_route == "partnership":
        subject = f"SPACE Partnership Inquiry — {app_row.organization_name or first_name}"
        body = (
            f"Hi {first_name},\n\n"
            "Thank you for reaching out to SPACE regarding a potential partnership.\n\n"
            "We reviewed your note and would love to learn more about how we can work together "
            "on catalog deal flow or valuation infrastructure. Let us know a few times that work "
            "for a brief introductory call this week.\n\n"
            "Best regards,\n"
            "Emil\n"
            "SPACE (spacemusic.io)"
        )
        return ReplyDraft(
            recipient_email=app_row.contact_email,
            recipient_name=app_row.contact_name,
            subject=subject,
            body=body,
            template_type="PARTNERSHIP",
        )

    if valuation.pipeline_status == "MISSING_INFO":
        questions = []
        if not app_row.artist_or_label_name or is_distributor_name(app_row.artist_or_label_name):
            questions.append(
                f"1. **Artist or label name & link:** Which artist or label name are the releases under "
                f"(it looks like '{app_row.artist_or_label_name}' was entered as the distributor), and could you share a public Spotify link?"
            )
        elif not app_row.listen_url:
            questions.append(
                f"1. **Streaming link:** Could you share a direct Spotify link to the artist profile or releases for **{app_row.artist_or_label_name}**?"
            )
        if app_row.declared_ltm_amount <= 0:
            questions.append(
                "2. **Last 12 months royalties:** Approximately how much did the catalog earn in net royalties over the last 12 months (and in which currency), or could you attach your recent royalty statements?"
            )
        if app_row.inquiry_route == "represented_catalog" and not app_row.owner_authorized:
            questions.append(
                "3. **Owner authorization:** Please confirm once the underlying rights owner has authorized sharing statements for a formal review."
            )
        questions_block = "\n".join(questions)
        subject = "Your SPACE catalog review"
        body = (
            f"Hi {first_name},\n\n"
            "Thank you for submitting your catalog to SPACE. We'd be glad to take a look.\n\n"
            "To complete our initial review, could you reply with a few quick details?\n\n"
            f"{questions_block}\n\n"
            "Once we have this, we will come back to you with our assessment.\n\n"
            "Best regards,\n"
            "Emil\n"
            "SPACE (spacemusic.io)"
        )
        return ReplyDraft(
            recipient_email=app_row.contact_email,
            recipient_name=app_row.contact_name,
            subject=subject,
            body=body,
            template_type="MISSING_INFO",
        )

    if valuation.pipeline_status == "DECLINED_BELOW_THRESHOLD":
        subject = f"Your SPACE catalog review — {app_row.artist_or_label_name}"
        body = (
            f"Hi {first_name},\n\n"
            f"Thank you for sharing the **{app_row.artist_or_label_name}** catalog with SPACE.\n\n"
            "Based on the current trailing 12-month royalty level, the catalog falls slightly below "
            "our minimum threshold for a direct buyout at this stage. However, we would be happy to "
            "revisit as the catalog grows, or provide a standalone statement-verified Catalog Valuation "
            "& Health Audit Report if helpful for your planning.\n\n"
            "Best regards,\n"
            "Emil\n"
            "SPACE (spacemusic.io)"
        )
        return ReplyDraft(
            recipient_email=app_row.contact_email,
            recipient_name=app_row.contact_name,
            subject=subject,
            body=body,
            template_type="POLITE_DECLINE_OR_PAID_AUDIT",
        )

    if valuation.pipeline_status == "AWAITING_STATEMENTS":
        subject = f"Your SPACE catalog review — {app_row.artist_or_label_name}"
        body = (
            f"Hi {first_name},\n\n"
            f"Thank you for submitting the **{app_row.artist_or_label_name}** catalog to SPACE.\n\n"
            f"Based on your reported LTM royalties ({app_row.declared_ltm_amount:,.0f} {app_row.declared_currency}) "
            f"via {dist_name}, our initial screening indicates an indicative valuation range of "
            f"**€{valuation.price_low_eur:,.0f} – €{valuation.price_high_eur:,.0f}** "
            f"(base target around **€{valuation.price_median_eur:,.0f}**, or ~{valuation.implied_ltm_multiple_median:.1f}x normalized LTM).\n\n"
            "To move to a firm, verified offer within 5–7 business days, please reply to this email with:\n"
            f"1. **Raw Royalty Statements (CSV/TSV):** Your full track-level earnings export from **{dist_name}** covering the last 24–36 months (or since release).\n"
            "2. **Scope confirmation:** Confirming whether the review covers 100% of existing releases up to closing.\n\n"
            "Best regards,\n"
            "Emil\n"
            "SPACE (spacemusic.io)"
        )
        return ReplyDraft(
            recipient_email=app_row.contact_email,
            recipient_name=app_row.contact_name,
            subject=subject,
            body=body,
            template_type="REQUEST_STATEMENTS",
        )

    # VALUATION_READY (Stage 2 verified)
    subject = f"SPACE Verified Catalog Offer — {app_row.artist_or_label_name}"
    body = (
        f"Hi {first_name},\n\n"
        f"We have completed our due diligence and track-level DCF analysis on your {dist_name} statements "
        f"for **{app_row.artist_or_label_name}**.\n\n"
        f"- **Verified Normalized LTM Baseline:** €{valuation.baseline.effective_cf0_eur:,.2f}\n"
        f"- **Proposed Purchase Price:** **€{valuation.price_median_eur:,.2f}** ({valuation.implied_ltm_multiple_median:.2f}x LTM)\n"
        f"- **Proposed Structure:** {valuation.deal_structure.rationale}\n\n"
        "Let us know if you would like us to issue the formal Term Sheet for signature.\n\n"
        "Best regards,\n"
        "Emil\n"
        "SPACE (spacemusic.io)"
    )
    return ReplyDraft(
        recipient_email=app_row.contact_email,
        recipient_name=app_row.contact_name,
        subject=subject,
        body=body,
        template_type="INDICATIVE_OFFER",
    )
