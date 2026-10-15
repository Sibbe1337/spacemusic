"""
Paid Valuation Model & Claude Investment Memo Checkout Service
(`services/spacemusic/paid_memo_service.py`)

Exposes SPACE's institutional valuation model (`engine.py` + `dtw_matcher.py` + `jev_evaluator.py`)
and Claude 19-slide 16:9 Investment Memo generator (`claude_memo_generator.py` + `memo_pdf_renderer.py`)
as a self-serve paid product:

1. **Freemium Teaser -> Paid 19-Slide Investment Memo (`$299 / €275`)**:
   - Visitors upload distributor statements (`.csv` / `.tsv`) or enter catalog telemetry.
   - The engine immediately computes the 10,000-path Monte Carlo DCF, DTW lifecycle match, and
     TypeSafe AI (JEV) 10-question audit, returning a live preview of **Slides 01–02** while
     blurring **Slides 03–19** until payment is completed.
   - 100% of the `$299` fee is credited back against closing fees if the seller accepts a SPACE M&A offer.
2. **Stripe Checkout & HMAC Webhook Verification**:
   - Creates a Stripe Checkout Session via `https://api.stripe.com/v1/checkout/sessions` when
     `STRIPE_SECRET_KEY` is configured, or issues a signed checkout session in local/test mode.
   - Verifies `Stripe-Signature` (`t=<timestamp>,v1=<hmac_sha256>`) on `POST /webhooks/stripe-memo`
     to unlock full 19-slide PDF & HTML downloads.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from services.valuation.claude_memo_generator import (
    DEFAULT_CLAUDE_MEMO_MODEL,
    CatalogInvestmentMemoDeck,
    generate_catalog_investment_memo_deck,
)
from services.valuation.engine import (
    CatalogValuationInput,
    RightsScope,
    RoyaltyBasis,
    SpaceValuationEngine,
)
from services.valuation.statement_parser import parse_statement_csv


class PaidMemoPlanTier(str, Enum):
    SINGLE_MEMO_299 = "SINGLE_MEMO_299"
    DESK_PASS_499 = "DESK_PASS_499"


class PaymentStatus(str, Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"


PLAN_PRICING: Dict[PaidMemoPlanTier, Dict[str, Any]] = {
    PaidMemoPlanTier.SINGLE_MEMO_299: {
        "name": "SPACE 19-Slide Institutional Catalog Valuation Memo (PDF + DCF Schedule)",
        "amount_usd_cents": 29900,
        "amount_usd": 299.0,
        "amount_eur": 275.0,
    },
    PaidMemoPlanTier.DESK_PASS_499: {
        "name": "SPACE Manager / Label Underwriting Desk Pass (Up to 10 Catalog Memos / mo)",
        "amount_usd_cents": 49900,
        "amount_usd": 499.0,
        "amount_eur": 459.0,
    },
}

VIP_WAIVER_COUPONS = {"SPACE-PARTNER-VIP", "SPACE-INTERNAL-100"}


class PaidMemoCheckoutRequest(BaseModel):
    application_id: Optional[uuid.UUID] = None
    artist_or_label_name: str = "Independent Artist"
    catalog_title: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    declared_ltm_amount: float = 50000.0
    currency: str = "USD"
    distributor: str = "DistroKid"
    rights_scope: str = "masters"
    royalty_basis: str = "net_payable"
    ownership_share_pct: float = Field(default=100.0, ge=5.0, le=100.0)
    genres: list[str] = Field(default_factory=lambda: ["Electronic / Dance"])
    raw_statement_csv: Optional[str] = None
    seller_quote_text: Optional[str] = None
    seller_quote_attribution: Optional[str] = None
    seller_ask_low_usd: Optional[float] = None
    seller_ask_high_usd: Optional[float] = None
    plan_tier: PaidMemoPlanTier = PaidMemoPlanTier.SINGLE_MEMO_299
    coupon_code: Optional[str] = None
    claude_model: str = DEFAULT_CLAUDE_MEMO_MODEL


class PaidMemoOrder(BaseModel):
    order_id: str
    application_id: uuid.UUID
    deal_code: str
    artist_or_label_name: str
    plan_tier: PaidMemoPlanTier
    amount_usd: float
    amount_eur: float
    payment_status: PaymentStatus
    stripe_session_id: str
    checkout_url: str
    receipt_token: str
    locked_preview_url: str
    unlocked_html_url: str
    unlocked_pdf_url: str
    created_at_utc: str
    paid_at_utc: Optional[str] = None
    deck: CatalogInvestmentMemoDeck


class PaidMemoCheckoutResponse(BaseModel):
    order_id: str
    application_id: uuid.UUID
    deal_code: str
    artist_or_label_name: str
    plan_tier: PaidMemoPlanTier
    amount_usd: float
    amount_eur: float
    payment_status: PaymentStatus
    stripe_session_id: str
    checkout_url: str
    locked_preview_url: str
    unlocked_html_url: Optional[str] = None
    unlocked_pdf_url: Optional[str] = None
    receipt_token: Optional[str] = None
    teaser_headline: str
    teaser_standalone_base_usd: str
    teaser_ltm_verified_usd: str
    teaser_wacc_pct: float
    claude_model_used: str
    claude_execution_mode: str


class PaidMemoStore:
    """
    In-memory order & deck store indexed by `order_id`, `application_id`, and `stripe_session_id`.
    """

    def __init__(self) -> None:
        self._orders_by_id: Dict[str, PaidMemoOrder] = {}
        self._orders_by_app: Dict[uuid.UUID, PaidMemoOrder] = {}
        self._orders_by_session: Dict[str, PaidMemoOrder] = {}

    def save(self, order: PaidMemoOrder) -> None:
        self._orders_by_id[order.order_id] = order
        self._orders_by_app[order.application_id] = order
        self._orders_by_session[order.stripe_session_id] = order

    def get_by_order_id(self, order_id: str) -> Optional[PaidMemoOrder]:
        return self._orders_by_id.get(order_id)

    def get_by_application_id(self, app_id: uuid.UUID) -> Optional[PaidMemoOrder]:
        return self._orders_by_app.get(app_id)

    def get_by_stripe_session(self, session_id: str) -> Optional[PaidMemoOrder]:
        return self._orders_by_session.get(session_id)


def _create_stripe_checkout_session(
    *,
    order_id: str,
    app_id: uuid.UUID,
    deal_code: str,
    artist_name: str,
    plan_tier: PaidMemoPlanTier,
) -> tuple[str, str]:
    """
    Creates a live Stripe Checkout Session when `STRIPE_SECRET_KEY` is set, or returns a
    deterministic local checkout session ID and URL.
    """
    pricing = PLAN_PRICING[plan_tier]
    stripe_key = os.environ.get("STRIPE_SECRET_KEY")

    if stripe_key:
        form_data = urllib.parse.urlencode(
            {
                "mode": "payment",
                "success_url": f"https://spacemusic.io/catalog-review/{app_id}/investment-memo.html?order_id={order_id}&status=success",
                "cancel_url": f"https://spacemusic.io/valuation-memo?order_id={order_id}&status=cancelled",
                "client_reference_id": order_id,
                "metadata[order_id]": order_id,
                "metadata[application_id]": str(app_id),
                "metadata[deal_code]": deal_code,
                "line_items[0][quantity]": "1",
                "line_items[0][price_data][currency]": "usd",
                "line_items[0][price_data][unit_amount]": str(pricing["amount_usd_cents"]),
                "line_items[0][price_data][product_data][name]": f"{pricing['name']} — {artist_name}",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.stripe.com/v1/checkout/sessions",
            data=form_data,
            headers={
                "Authorization": f"Bearer {stripe_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("id") and body.get("url"):
                    return str(body["id"]), str(body["url"])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            pass

    session_id = f"cs_live_{hashlib.sha256(f'{order_id}:{app_id}'.encode()).hexdigest()[:24]}"
    checkout_url = f"https://checkout.stripe.com/c/pay/{session_id}?order_id={order_id}"
    return session_id, checkout_url


def verify_stripe_webhook_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    webhook_secret: Optional[str] = None,
    tolerance_sec: int = 300,
) -> bool:
    """
    Verifies Stripe's `Stripe-Signature: t=<timestamp>,v1=<hmac_sha256>` header.
    """
    secret = webhook_secret or os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_space_memo_default_secret")
    if not signature_header:
        return False
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        if "=" in item:
            k, v = item.strip().split("=", 1)
            parts[k] = v
    if "t" not in parts or "v1" not in parts:
        return False
    try:
        ts = int(parts["t"])
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > tolerance_sec:
        return False
    signed_payload = f"{ts}.".encode("utf-8") + raw_body
    expected_sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, parts["v1"])


def create_paid_memo_checkout_order(
    req: PaidMemoCheckoutRequest,
    store: PaidMemoStore,
    engine: Optional[SpaceValuationEngine] = None,
) -> PaidMemoCheckoutResponse:
    """
    Evaluates the catalog via `SpaceValuationEngine` + `ClaudeMemoGenerator`, creates a
    `PaidMemoOrder`, and returns the teaser metrics + Stripe Checkout URL (or immediate
    unlocked links if a valid partner waiver coupon is supplied).
    """
    eng = engine or SpaceValuationEngine()
    app_id = req.application_id or uuid.uuid4()

    scope_map = {
        "masters": RightsScope.MASTERS,
        "publishing": RightsScope.PUBLISHING,
        "both": RightsScope.BOTH,
    }
    basis_map = {
        "net_payable": RoyaltyBasis.NET_PAYABLE,
        "gross_before_deductions": RoyaltyBasis.GROSS_BEFORE_DEDUCTIONS,
    }

    val_input = CatalogValuationInput(
        catalog_title=req.catalog_title or req.artist_or_label_name,
        artist_or_label_name=req.artist_or_label_name,
        applicant_name=req.contact_name,
        applicant_email=req.contact_email,
        rights_scope=scope_map.get(req.rights_scope.lower().strip(), RightsScope.MASTERS),
        royalty_basis=basis_map.get(req.royalty_basis.lower().strip(), RoyaltyBasis.NET_PAYABLE),
        distributor_or_admin=req.distributor,
        ownership_share_pct=req.ownership_share_pct,
        declared_ltm_amount=req.declared_ltm_amount,
        declared_currency=req.currency.upper().strip(),
        genres=req.genres or ["Electronic / Dance"],
    )

    stmt_summary = None
    if req.raw_statement_csv and req.raw_statement_csv.strip():
        stmt_summary = parse_statement_csv(
            req.raw_statement_csv,
            default_currency=val_input.declared_currency,
        )
        if stmt_summary.row_count > 0:
            val_input.statements_verified = True
            val_input.monthly_history = stmt_summary.monthly_history
            val_input.tracks = stmt_summary.tracks
            val_input.dsp_share = stmt_summary.dsp_share
            val_input.country_share = stmt_summary.country_share
            if stmt_summary.detected_distributor and stmt_summary.detected_distributor != "Standard CSV":
                val_input.distributor_or_admin = stmt_summary.detected_distributor

    valuation = eng.evaluate(val_input)

    extra_ctx: Dict[str, Any] = {}
    if req.seller_quote_text:
        extra_ctx["seller_quote_text"] = req.seller_quote_text
    if req.seller_quote_attribution:
        extra_ctx["seller_quote_attribution"] = req.seller_quote_attribution
    if req.seller_ask_low_usd is not None:
        extra_ctx["seller_ask_low_usd"] = req.seller_ask_low_usd
    if req.seller_ask_high_usd is not None:
        extra_ctx["seller_ask_high_usd"] = req.seller_ask_high_usd

    deck = generate_catalog_investment_memo_deck(
        app_input=val_input,
        valuation=valuation,
        stmt_summary=stmt_summary,
        extra_context=extra_ctx,
        claude_model=req.claude_model,
    )

    order_id = f"ORD-{deck.deal_code}-{uuid.uuid4().hex[:6].upper()}"
    receipt_token = hashlib.sha256(f"{order_id}:{app_id}:{time.time_ns()}".encode()).hexdigest()[:32]
    session_id, checkout_url = _create_stripe_checkout_session(
        order_id=order_id,
        app_id=app_id,
        deal_code=deck.deal_code,
        artist_name=req.artist_or_label_name,
        plan_tier=req.plan_tier,
    )

    pricing = PLAN_PRICING[req.plan_tier]
    is_waived = (req.coupon_code or "").strip().upper() in VIP_WAIVER_COUPONS
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    locked_url = f"/catalog-review/{app_id}/investment-memo.html"
    unlocked_html = f"/catalog-review/{app_id}/investment-memo.html?receipt_token={receipt_token}"
    unlocked_pdf = f"/catalog-review/{app_id}/investment-memo.pdf?receipt_token={receipt_token}"

    order = PaidMemoOrder(
        order_id=order_id,
        application_id=app_id,
        deal_code=deck.deal_code,
        artist_or_label_name=req.artist_or_label_name,
        plan_tier=req.plan_tier,
        amount_usd=0.0 if is_waived else pricing["amount_usd"],
        amount_eur=0.0 if is_waived else pricing["amount_eur"],
        payment_status=PaymentStatus.PAID if is_waived else PaymentStatus.PENDING_PAYMENT,
        stripe_session_id=session_id,
        checkout_url=checkout_url,
        receipt_token=receipt_token,
        locked_preview_url=locked_url,
        unlocked_html_url=unlocked_html,
        unlocked_pdf_url=unlocked_pdf,
        created_at_utc=now_iso,
        paid_at_utc=now_iso if is_waived else None,
        deck=deck,
    )
    store.save(order)

    return PaidMemoCheckoutResponse(
        order_id=order.order_id,
        application_id=order.application_id,
        deal_code=order.deal_code,
        artist_or_label_name=order.artist_or_label_name,
        plan_tier=order.plan_tier,
        amount_usd=order.amount_usd,
        amount_eur=order.amount_eur,
        payment_status=order.payment_status,
        stripe_session_id=order.stripe_session_id,
        checkout_url=order.checkout_url,
        locked_preview_url=order.locked_preview_url,
        unlocked_html_url=order.unlocked_html_url if order.payment_status == PaymentStatus.PAID else None,
        unlocked_pdf_url=order.unlocked_pdf_url if order.payment_status == PaymentStatus.PAID else None,
        receipt_token=order.receipt_token if order.payment_status == PaymentStatus.PAID else None,
        teaser_headline=deck.s01_headline,
        teaser_standalone_base_usd=deck.s01_cards[1].value,
        teaser_ltm_verified_usd=deck.s01_cards[0].value,
        teaser_wacc_pct=deck.s06_total_wacc_pct,
        claude_model_used=deck.claude_model_used,
        claude_execution_mode=deck.claude_execution_mode,
    )


def render_self_serve_valuation_studio_html() -> str:
    """
    Renders the public self-serve SPACE + Claude Investment Memo Studio (`/valuation-memo`)
    where users can upload distributor CSV/TSV files, preview Slides 01–02 for free,
    and pay $299 (or apply a partner coupon) to download the full 19-slide 16:9 PDF.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SPACE Institutional Catalog Valuation Memo Studio | Claude + DTW + Monte Carlo DCF</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: #0D0E11;
    color: #F5F6F8;
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  .topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 48px;
    border-bottom: 1px solid #1E2330;
  }
  .brand { font-size: 18px; font-weight: 800; letter-spacing: 0.18em; }
  .badge {
    font-family: monospace;
    font-size: 11px;
    color: #84B1FF;
    background: rgba(132, 177, 255, 0.12);
    border: 1px solid rgba(132, 177, 255, 0.3);
    padding: 5px 12px;
    border-radius: 999px;
  }
  .container {
    max-width: 1180px;
    margin: 36px auto;
    padding: 0 24px;
    display: grid;
    grid-template-columns: 440px 1fr;
    gap: 32px;
  }
  .panel {
    background: #141720;
    border: 1px solid #252A3A;
    border-radius: 10px;
    padding: 26px;
  }
  h1 { font-size: 26px; margin: 0 0 8px; letter-spacing: -0.02em; }
  p.lead { font-size: 13.5px; color: #9BA3B8; line-height: 1.5; margin: 0 0 20px; }
  label { display: block; font-size: 12px; color: #B4BCCF; margin: 12px 0 5px; font-weight: 500; }
  input, select, textarea {
    width: 100%;
    padding: 10px 12px;
    background: #0D0E11;
    border: 1px solid #2A3145;
    border-radius: 6px;
    color: #FFFFFF;
    font-size: 13px;
  }
  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .btn-primary {
    margin-top: 18px;
    width: 100%;
    padding: 13px;
    background: #2356C8;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
  }
  .btn-primary:hover { background: #2D64DF; }
  .preview-frame {
    width: 100%;
    height: 640px;
    border: 1px solid #252A3A;
    border-radius: 8px;
    background: #090A0D;
  }
  .action-bar {
    display: none;
    margin-bottom: 16px;
    padding: 14px 18px;
    background: #171D2B;
    border: 1px solid #84B1FF;
    border-radius: 8px;
    justify-content: space-between;
    align-items: center;
  }
  .action-links a {
    display: inline-block;
    margin-left: 10px;
    padding: 9px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    text-decoration: none;
  }
  .btn-pdf { background: #84B1FF; color: #0D0E11; }
  .btn-stripe { background: #F99441; color: #0D0E11; }
</style>
</head>
<body>
  <div class="topbar">
    <div class="brand">SPACE</div>
    <div class="badge">CLAUDE + SPACE ENGINE · 19-SLIDE 16:9 INVESTMENT MEMO</div>
  </div>
  <div class="container">
    <div class="panel">
      <h1>Generate Catalog Investment Memo</h1>
      <p class="lead">
        Run our 10,000-path Monte Carlo DCF, Dynamic Time Warping (DTW), and TypeSafe AI (JEV)
        forensics engine. Preview Slides 01–02 free, or unlock the full 19-slide 16:9 PDF ($299, 100% credited if you sell with SPACE).
      </p>
      <form id="memoForm">
        <div class="row-2">
          <div>
            <label>Artist or Label Name</label>
            <input type="text" id="artist_name" value="HMWME" required>
          </div>
          <div>
            <label>Catalog Title</label>
            <input type="text" id="catalog_title" value="The Family of One">
          </div>
        </div>
        <div class="row-2">
          <div>
            <label>Claimed / Trailing LTM ($ USD)</label>
            <input type="number" id="ltm_amount" value="80000" step="100">
          </div>
          <div>
            <label>Primary Distributor</label>
            <input type="text" id="distributor" value="DistroKid + Amuse">
          </div>
        </div>
        <label>Paste Raw Distributor CSV / TSV Rows (Optional — upgrades to Stage 2 Verified)</label>
        <textarea id="raw_csv" rows="4" placeholder="reporting_month,title,isrc,store,country,quantity,net_royalty_usd..."></textarea>
        <div class="row-2">
          <div>
            <label>Plan Tier</label>
            <select id="plan_tier">
              <option value="SINGLE_MEMO_299">Single 19-Slide Memo PDF ($299 / €275)</option>
              <option value="DESK_PASS_499">Label / Manager Desk Pass ($499/mo)</option>
            </select>
          </div>
          <div>
            <label>Partner / VIP Code (Optional)</label>
            <input type="text" id="coupon_code" placeholder="e.g. SPACE-PARTNER-VIP">
          </div>
        </div>
        <button type="submit" class="btn-primary">Run Engine &amp; Build 19-Slide Memo</button>
      </form>
    </div>
    <div>
      <div id="actionBar" class="action-bar">
        <div id="statusSummary" style="font-size: 13px;"></div>
        <div class="action-links" id="actionLinks"></div>
      </div>
      <iframe id="deckIframe" class="preview-frame" title="SPACE 19-Slide Investment Memo Preview"></iframe>
    </div>
  </div>
<script>
document.getElementById("memoForm").addEventListener("submit", async function(e) {
  e.preventDefault();
  var payload = {
    artist_or_label_name: document.getElementById("artist_name").value,
    catalog_title: document.getElementById("catalog_title").value,
    declared_ltm_amount: parseFloat(document.getElementById("ltm_amount").value || "50000"),
    distributor: document.getElementById("distributor").value,
    raw_statement_csv: document.getElementById("raw_csv").value || null,
    plan_tier: document.getElementById("plan_tier").value,
    coupon_code: document.getElementById("coupon_code").value || null
  };
  var res = await fetch("/catalog-review/paid-memo/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) return;
  var data = await res.json();
  var bar = document.getElementById("actionBar");
  var links = document.getElementById("actionLinks");
  bar.style.display = "flex";
  document.getElementById("statusSummary").innerHTML =
    "<strong>" + data.deal_code + "</strong> · Standalone Base: <strong>" + data.teaser_standalone_base_usd +
    "</strong> · WACC: " + data.teaser_wacc_pct + "%";
  if (data.payment_status === "PAID" && data.unlocked_pdf_url) {
    document.getElementById("deckIframe").src = data.unlocked_html_url;
    links.innerHTML = '<a class="btn-pdf" href="' + data.unlocked_pdf_url + '">Download 19-Slide PDF</a>';
  } else {
    document.getElementById("deckIframe").src = data.locked_preview_url;
    links.innerHTML = '<a class="btn-stripe" href="' + data.checkout_url + '" target="_blank">Unlock All 19 Slides ($' + data.amount_usd + ')</a>';
  }
});
</script>
</body>
</html>
"""
