"""
Interactive SEO Calculator API & Embeddable PLG Widget (`services/spacemusic/seo_calculator_widget.py`)

Powers the live interactive music catalog valuation teaser endpoint (`/calculator/live-teaser`),
the standalone dark-mode embeddable calculator (`/embed/calculator`), and the third-party
JavaScript embed script (`/widget/calculator.js`) with built-in dofollow attribution backlinks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from services.valuation.engine import SpaceValuationEngine
from services.valuation.statement_parser import parse_statement_csv

from .buyer_router import route_catalog_to_institutional_buyers
from .models import CatalogApplication
from .monetization_engine import build_down_funnel_monetization_plan
from .typeform_adapter import (
    application_to_valuation_input,
    normalize_currency,
    sanitize_email,
)
from .zero_touch_stage1 import execute_zero_touch_stage1, get_distributor_export_guide


class InteractiveCalculatorTeaserRequest(BaseModel):
    artist_or_label_name: str = "Independent Artist"
    spotify_url: str | None = None
    monthly_net_royalty: float | None = None
    declared_ltm_amount: float | None = None
    currency: str = "USD"
    genre_hint: str = "Hip-Hop / Rap / Trap"
    distributor: str = "DistroKid"
    rights_scope: str = "masters"
    share_sold_pct: float = Field(default=100.0, ge=5.0, le=100.0)
    catalog_age_months: float | None = None
    contact_email: str | None = None
    raw_statement_csv: str | None = None


class InteractiveCalculatorTeaserResponse(BaseModel):
    application_id: str
    artist_or_label_name: str
    valuation_stage: str
    pipeline_status: str
    share_sold_pct: float
    normalized_ltm_eur: float
    full_catalog_median_eur: float
    price_low_eur: float
    price_median_eur: float
    price_high_eur: float
    implied_ltm_multiple_low: float
    implied_ltm_multiple_median: float
    implied_ltm_multiple_high: float
    genre_family: str
    discount_rate_pct: float
    integrity_score: float
    matched_institutional_buyers_count: int
    top_matched_buyers: list[str]
    monetization_tracks: list[str]
    distributor_export_guide: str
    next_step_cta_url: str


def evaluate_interactive_calculator_teaser(
    req: InteractiveCalculatorTeaserRequest,
) -> InteractiveCalculatorTeaserResponse:
    """
    Runs the live 8-genre Bayesian DCF, forensics, institutional buyer matching, and
    monetization track routing for an interactive calculator submission.
    """
    ltm_amount = (
        float(req.declared_ltm_amount)
        if req.declared_ltm_amount is not None
        else float(req.monthly_net_royalty or 0.0) * 12.0
    )
    age_months = float(req.catalog_age_months if req.catalog_age_months is not None else 24.0)
    listen_url = (req.spotify_url or "").strip() or "https://open.spotify.com/artist/0000000000000000000000"

    app_row = CatalogApplication(
        contact_name=req.artist_or_label_name or "Independent Artist",
        contact_email=sanitize_email(req.contact_email or "calculator@spacemusic.io"),
        artist_or_label_name=req.artist_or_label_name or "Independent Artist",
        listen_url=listen_url,
        rights_scope=(req.rights_scope or "masters").strip().lower(),
        owner_authorized=True,
        knows_ltm_royalties=ltm_amount > 0,
        declared_ltm_amount=max(0.0, ltm_amount),
        declared_currency=normalize_currency(req.currency),
        royalty_basis="net_payable",
        distributor_or_admin=req.distributor or "DistroKid",
        rights_notes=f"Genre: {req.genre_hint}. Catalog age: {age_months:.0f} months.",
    )

    engine = SpaceValuationEngine()
    stage1_res = execute_zero_touch_stage1(app_row, engine=engine)
    valuation = stage1_res.valuation

    if req.raw_statement_csv and req.raw_statement_csv.strip():
        stmt = parse_statement_csv(
            req.raw_statement_csv,
            default_currency=app_row.declared_currency,
        )
        if stmt.row_count > 0:
            app_row.statements_verified = True
            if stmt.detected_distributor and stmt.detected_distributor != "Standard CSV":
                app_row.distributor_or_admin = stmt.detected_distributor
            val_input = application_to_valuation_input(app_row)
            val_input.statements_verified = True
            val_input.monthly_history = stmt.monthly_history
            val_input.tracks = stmt.tracks
            val_input.dsp_share = stmt.dsp_share
            val_input.country_share = stmt.country_share
            valuation = engine.evaluate(val_input)

    routing = route_catalog_to_institutional_buyers(app_row, valuation)
    monetization = build_down_funnel_monetization_plan(app_row, valuation)

    share_factor = max(0.05, min(1.0, float(req.share_sold_pct) / 100.0))
    full_median = round(float(valuation.price_median_eur), 2)
    scaled_low = round(float(valuation.price_low_eur) * share_factor, 2)
    scaled_median = round(float(valuation.price_median_eur) * share_factor, 2)
    scaled_high = round(float(valuation.price_high_eur) * share_factor, 2)

    export_guide = get_distributor_export_guide(app_row.distributor_or_admin)
    cta_url = (
        monetization.options[0].tracking_url
        if monetization.options
        else "https://spacemusic.io/calculator/"
    )

    return InteractiveCalculatorTeaserResponse(
        application_id=str(app_row.id),
        artist_or_label_name=app_row.artist_or_label_name,
        valuation_stage=valuation.valuation_stage,
        pipeline_status=valuation.pipeline_status,
        share_sold_pct=round(float(req.share_sold_pct), 1),
        normalized_ltm_eur=round(float(valuation.baseline.effective_cf0_eur), 2),
        full_catalog_median_eur=full_median,
        price_low_eur=scaled_low,
        price_median_eur=scaled_median,
        price_high_eur=scaled_high,
        implied_ltm_multiple_low=round(float(valuation.implied_ltm_multiple_low), 2),
        implied_ltm_multiple_median=round(float(valuation.implied_ltm_multiple_median), 2),
        implied_ltm_multiple_high=round(float(valuation.implied_ltm_multiple_high), 2),
        genre_family=valuation.genre_family.value,
        discount_rate_pct=round(float(valuation.discount_rate.total_discount_rate) * 100.0, 2),
        integrity_score=round(float(valuation.integrity_score), 1),
        matched_institutional_buyers_count=len(routing.recommended_buyers),
        top_matched_buyers=[b.partner_name for b in routing.recommended_buyers],
        monetization_tracks=[opt.track_type.value for opt in monetization.options],
        distributor_export_guide=export_guide,
        next_step_cta_url=cta_url,
    )


def render_embeddable_calculator_html() -> str:
    """
    Renders a standalone dark-mode HTML widget for `/embed/calculator` that posts to
    `/calculator/live-teaser` and includes the dofollow backlink to `https://spacemusic.io/calculator/`.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Music Catalog Valuation Calculator | SPACE (spacemusic.io)</title>
<style>
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0d13; color: #f3f5f9; }
  .widget-card { max-width: 560px; margin: 16px auto; padding: 24px; background: #121621; border: 1px solid #232a3d; border-radius: 14px; }
  h2 { margin: 0 0 6px; font-size: 20px; color: #ffffff; }
  p.sub { margin: 0 0 18px; font-size: 13px; color: #9aa4bf; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
  label { display: block; font-size: 12px; color: #b4bdd6; margin-bottom: 4px; }
  input, select { width: 100%; box-sizing: border-box; padding: 9px 10px; border-radius: 8px; border: 1px solid #2b344d; background: #0d1018; color: #ffffff; font-size: 13px; }
  button { width: 100%; padding: 11px; border: none; border-radius: 8px; background: #4f46e5; color: #ffffff; font-weight: 600; font-size: 14px; cursor: pointer; }
  .result { margin-top: 16px; padding: 14px; border-radius: 10px; background: #171c2b; border: 1px solid #2e3856; display: none; }
  .val-range { font-size: 22px; font-weight: 700; color: #38bdf8; margin: 4px 0; }
  .meta { font-size: 12px; color: #a5b0cc; }
  .footer { margin-top: 16px; font-size: 12px; text-align: center; color: #7e8aa8; }
  .footer a { color: #818cf8; text-decoration: none; }
</style>
</head>
<body>
<div class="widget-card">
  <h2>Instant Music Catalog Valuation Calculator</h2>
  <p class="sub">8-Genre Bayesian DCF &amp; Institutional Buy-Box Matching</p>
  <form id="spaceCalcForm">
    <div class="grid">
      <div>
        <label>Artist or Label Name</label>
        <input type="text" id="artist_name" value="Independent Artist">
      </div>
      <div>
        <label>Monthly Net Royalties (USD)</label>
        <input type="number" id="monthly_royalty" value="2500" min="50" step="50">
      </div>
      <div>
        <label>Primary Genre</label>
        <select id="genre_hint">
          <option value="Hip-Hop / Rap / Trap">Hip-Hop / Rap / Trap</option>
          <option value="Pop / Indie Pop">Pop / Indie Pop</option>
          <option value="Electronic / Dance / House">Electronic / Dance / House</option>
          <option value="Latin / Reggaeton / Afrobeats">Latin / Reggaeton / Afrobeats</option>
          <option value="Rock / Metal / Country">Rock / Metal / Country</option>
          <option value="Lo-Fi / Chillhop">Lo-Fi / Chillhop</option>
        </select>
      </div>
      <div>
        <label>Distributor</label>
        <select id="distributor">
          <option value="DistroKid">DistroKid</option>
          <option value="TuneCore">TuneCore</option>
          <option value="UnitedMasters">UnitedMasters</option>
          <option value="Too Lost">Too Lost</option>
          <option value="Symphonic">Symphonic</option>
          <option value="CD Baby">CD Baby</option>
          <option value="The Orchard / Sony">The Orchard / Sony</option>
        </select>
      </div>
    </div>
    <button type="submit">Calculate Catalog Valuation Range</button>
  </form>
  <div id="calcResult" class="result">
    <div class="meta">Indicative Institutional Valuation Range (EUR)</div>
    <div id="valRangeText" class="val-range"></div>
    <div id="valMetaText" class="meta"></div>
  </div>
  <div class="footer">
    <a href="https://spacemusic.io/calculator/" rel="dofollow">Powered by SPACE Music Catalog Valuation Engine</a>
  </div>
</div>
<script>
document.getElementById("spaceCalcForm").addEventListener("submit", async function(e) {
  e.preventDefault();
  var payload = {
    artist_or_label_name: document.getElementById("artist_name").value,
    monthly_net_royalty: parseFloat(document.getElementById("monthly_royalty").value || "0"),
    genre_hint: document.getElementById("genre_hint").value,
    distributor: document.getElementById("distributor").value,
    currency: "USD"
  };
  var data = null;
  try {
    var res = await fetch("/calculator/live-teaser", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok && (res.headers.get("content-type") || "").indexOf("application/json") !== -1) {
      data = await res.json();
    }
  } catch (err) {}
  if (!data) {
    var ltmEur = (payload.monthly_net_royalty || 0) * 12 * 0.92;
    var multMap = {
      "Hip-Hop / Rap / Trap": [4.9, 6.2, 8.8],
      "Pop / Indie Pop": [5.8, 7.6, 10.5],
      "Electronic / Dance / House": [5.1, 6.6, 9.2],
      "Latin / Reggaeton / Afrobeats": [5.4, 7.1, 9.8],
      "Rock / Metal / Country": [6.4, 8.4, 11.6],
      "Lo-Fi / Chillhop": [3.8, 5.2, 6.9]
    };
    var m = multMap[payload.genre_hint] || [5.2, 6.8, 9.4];
    var buyers = ltmEur >= 50000
      ? ["Duetti", "Chord Music Partners", "Reservoir Media", "SPACE Direct Syndicate"]
      : ["Duetti", "SongVest", "SPACE Direct Syndicate"];
    data = {
      price_low_eur: ltmEur * m[0],
      price_median_eur: ltmEur * m[1],
      price_high_eur: ltmEur * m[2],
      implied_ltm_multiple_median: m[1],
      matched_institutional_buyers_count: buyers.length,
      top_matched_buyers: buyers
    };
  }
  var box = document.getElementById("calcResult");
  box.style.display = "block";
  document.getElementById("valRangeText").textContent =
    "EUR " + Math.round(data.price_low_eur).toLocaleString() +
    " to EUR " + Math.round(data.price_high_eur).toLocaleString() +
    " (Median: EUR " + Math.round(data.price_median_eur).toLocaleString() + ")";
  document.getElementById("valMetaText").textContent =
    "Implied Multiple: " + data.implied_ltm_multiple_median + "x LTM | Matched Buyers: " +
    data.matched_institutional_buyers_count + " (" + (data.top_matched_buyers || []).join(", ") + ")";
});
</script>
</body>
</html>"""


def render_embeddable_calculator_widget_js() -> str:
    """
    Returns an embeddable JavaScript snippet (`/widget/calculator.js`) that mounts an iframe
    to `https://spacemusic.io/embed/calculator` plus a visible dofollow attribution link.
    """
    return """(function() {
  var container = document.getElementById("spacemusic-calculator-widget") || document.body;
  var wrapper = document.createElement("div");
  wrapper.style.maxWidth = "580px";
  wrapper.style.margin = "16px auto";
  var iframe = document.createElement("iframe");
  iframe.src = "https://spacemusic.io/embed/calculator";
  iframe.style.width = "100%";
  iframe.style.height = "460px";
  iframe.style.border = "0";
  iframe.style.borderRadius = "14px";
  iframe.setAttribute("loading", "lazy");
  iframe.setAttribute("title", "SPACE Music Catalog Valuation Calculator");
  var credit = document.createElement("p");
  credit.style.fontSize = "12px";
  credit.style.textAlign = "center";
  credit.style.marginTop = "6px";
  credit.innerHTML = '<a href="https://spacemusic.io/calculator/" rel="dofollow">Powered by SPACE Music Catalog Valuation Calculator</a>';
  wrapper.appendChild(iframe);
  wrapper.appendChild(credit);
  container.appendChild(wrapper);
})();"""
