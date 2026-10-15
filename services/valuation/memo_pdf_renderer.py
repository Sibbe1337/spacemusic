"""
16:9 Institutional Slide Deck HTML & PDF Renderer (`services/valuation/memo_pdf_renderer.py`)

Renders a `CatalogInvestmentMemoDeck` (authored by `claude_memo_generator.py` + `engine.py`)
into the exact 19-slide 16:9 widescreen visual layout of `HMWME Catalog Valuation.pdf` and
`2Scratch Catalog Valuation.pdf`:
- Alternating Dark Obsidian (`#0D0E11`), Warm Ivory (`#F3F2ED`), and Executive Royal Blue (`#1E3F86`) slides
- Exact typography, concentric cover geometry, horizontal claim bars, monthly momentum chart,
  segmented WACC build-up, 5Y/10Y/12Y NPV bars, cent-exact DCF reconciliation table,
  TypeSafe AI (JEV) 10-question table, DSP/Territory breakdown, track HHI bars,
  calibrated Ask-vs-Value range corridors, Offer A/B/C cards, and 01–04 Next Steps.
"""

from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from services.valuation.claude_memo_generator import (
    CatalogInvestmentMemoDeck,
    _fmt_k,
)


def _esc(val: object) -> str:
    return html.escape(str(val if val is not None else ""))


def render_investment_memo_html(
    deck: CatalogInvestmentMemoDeck,
    *,
    locked_preview: bool = False,
    checkout_url: Optional[str] = None,
) -> str:
    """
    Renders the 19-slide 16:9 SPACE Investment Memo Deck as self-contained HTML/CSS/SVG.
    When `locked_preview=True`, Slides 01–02 are visible in full and Slides 03–19 are blurred
    behind a Stripe Checkout unlock banner.
    """
    memo_footer_left = f"SPACE · {_esc(deck.artist_or_label_name)} catalog memo"

    # Slide 01 cards
    s01_cards_html = "".join(
        f"""
        <div class="dark-card {'highlight-border' if c.highlight else ''}">
          <div class="card-label">{_esc(c.label)}</div>
          <div class="card-big-val {'accent-blue' if c.highlight else ''}">{_esc(c.value)}</div>
          <div class="card-detail">{_esc(c.detail)}</div>
        </div>
        """
        for c in deck.s01_cards
    )

    # Slide 02 data cells
    s02_cells_html = "".join(
        f"""
        <div class="light-data-cell">
          <div class="cell-title">{_esc(c.label)}</div>
          <div class="cell-val {'accent-royal' if c.highlight else ''}">{_esc(c.value)}</div>
          <div class="cell-sub">{_esc(c.detail)}</div>
        </div>
        """
        for c in deck.s02_cards
    )

    # Slide 03 Claim check horizontal bars
    max_s03 = max((b.amount_usd for b in deck.s03_bars), default=1.0) or 1.0
    s03_bars_html = ""
    for b in deck.s03_bars:
        width_pct = max(12.0, min(100.0, (b.amount_usd / max_s03) * 100.0))
        bar_cls = (
            "bar-orange"
            if b.variant == "orange"
            else ("bar-muted" if b.variant == "muted" else "bar-blue")
        )
        val_cls = (
            "accent-orange"
            if b.variant == "orange"
            else ("accent-blue" if b.variant == "blue" else "")
        )
        s03_bars_html += f"""
        <div class="claim-bar-row">
          <div class="claim-bar-label">{_esc(b.label)}</div>
          <div class="claim-bar-track">
            <div class="claim-bar-fill {bar_cls}" style="width: {width_pct:.1f}%;"></div>
          </div>
          <div class="claim-bar-val {val_cls}">{_esc(b.formatted_value)}</div>
        </div>
        """

    # Slide 04 Monthly Momentum vertical bars
    max_m_usd = max((m.amount_usd for m in deck.s04_monthly_bars), default=1000.0) or 1000.0
    s04_bars_html = ""
    for m in deck.s04_monthly_bars:
        h_pct = max(4.0, min(100.0, (m.amount_usd / max_m_usd) * 100.0))
        b_cls = "vbar-ltm" if m.in_ltm_window else "vbar-before"
        s04_bars_html += f"""
        <div class="vbar-col">
          <div class="vbar-wrap">
            <div class="vbar-fill {b_cls}" style="height: {h_pct:.1f}%;"></div>
          </div>
          <div class="vbar-month">{_esc(m.month_short)}</div>
        </div>
        """

    # Slide 05 Model parameters (6 cards)
    s05_cards_html = "".join(
        f"""
        <div class="dark-card">
          <div class="card-label">{_esc(c.label)}</div>
          <div class="card-big-val {'accent-blue' if c.highlight else ''}">{_esc(c.value)}</div>
          <div class="card-detail">{_esc(c.detail)}</div>
        </div>
        """
        for c in deck.s05_cards
    )

    # Slide 06 WACC Segmented Bar
    total_wacc = max(deck.s06_total_wacc_pct, 1.0)
    s06_segs_html = ""
    for seg in deck.s06_segments:
        w_pct = max(14.0, (seg.rate_pct / total_wacc) * 100.0)
        seg_cls = (
            "wacc-seg-dark"
            if seg.variant == "dark"
            else ("wacc-seg-royal" if seg.variant == "blue_primary" else "wacc-seg-sky")
        )
        s06_segs_html += f"""
        <div class="wacc-seg {seg_cls}" style="flex: {w_pct:.1f};">
          <div class="wacc-seg-pct">{_esc(seg.formatted_pct)}</div>
          <div class="wacc-seg-lbl">{_esc(seg.label)}</div>
        </div>
        """

    # Slide 07 Standalone Value (3 cards)
    s07_cards_html = "".join(
        f"""
        <div class="dark-card {'highlight-border' if c.highlight else ''}">
          <div class="card-label">{_esc(c.label)}</div>
          <div class="card-huge-val {'accent-blue' if c.highlight else ''}">{_esc(c.value)}</div>
          <div class="card-detail">{_esc(c.detail)}</div>
        </div>
        """
        for c in deck.s07_cards
    )

    # Slide 08 Cumulative NPV by Horizon (3 groups × 3 bars)
    max_npv = max((h.p90_usd for h in deck.s08_horizons), default=100_000.0) or 100_000.0
    s08_groups_html = ""
    for h in deck.s08_horizons:
        h10 = max(12.0, (h.p10_usd / max_npv) * 100.0)
        h50 = max(16.0, (h.p50_usd / max_npv) * 100.0)
        h90 = max(20.0, (h.p90_usd / max_npv) * 100.0)
        s08_groups_html += f"""
        <div class="npv-group">
          <div class="npv-bars-triad">
            <div class="npv-bar-col">
              <div class="npv-bar-top-val muted-text">{_fmt_k(h.p10_usd)}</div>
              <div class="npv-bar-rect npv-p10" style="height: {h10:.1f}%;"></div>
            </div>
            <div class="npv-bar-col">
              <div class="npv-bar-top-val">{_fmt_k(h.p50_usd)}</div>
              <div class="npv-bar-rect npv-p50" style="height: {h50:.1f}%;"></div>
            </div>
            <div class="npv-bar-col">
              <div class="npv-bar-top-val accent-blue">{_fmt_k(h.p90_usd)}</div>
              <div class="npv-bar-rect npv-p90" style="height: {h90:.1f}%;"></div>
            </div>
          </div>
          <div class="npv-group-label">{_esc(h.horizon_label)}</div>
        </div>
        """

    # Slide 09 DCF Reconciliation Table + Pillars
    s09_rows_html = ""
    for h in deck.s09_horizons:
        p50_cls = "accent-royal bold" if h.is_anchor else "bold"
        s09_rows_html += f"""
        <tr>
          <td class="bold">{_esc(h.horizon_label)}</td>
          <td class="mono">${h.p10_usd:,.2f}</td>
          <td class="mono {p50_cls}">${h.p50_usd:,.2f}</td>
          <td class="mono">${h.p90_usd:,.2f}</td>
          <td class="mono">€{h.p50_eur:,.2f}</td>
        </tr>
        """

    s09_pillars_html = "".join(
        f"""
        <div class="light-pillar">
          <div class="pillar-big {'accent-royal' if p.highlight else ''}">{_esc(p.label)}</div>
          <div class="pillar-sub">{_esc(p.detail)}</div>
        </div>
        """
        for p in deck.s09_pillars
    )

    # Slide 10 TypeSafe AI Cross-Check Table (10 questions)
    s10_rows_html = ""
    for q in deck.s10_questions:
        row_cls = "jev-row-highlight" if q.highlight else ""
        ans_cls = "accent-orange bold" if q.highlight else ""
        s10_rows_html += f"""
        <tr class="{row_cls}">
          <td class="jev-q-col">{_esc(q.question)}</td>
          <td class="jev-ans-col {ans_cls}">{_esc(q.posterior_answer)}</td>
          <td class="jev-conf-col mono">{q.confidence_pct}%</td>
        </tr>
        """

    # Slide 11 Stream Integrity (4 big metrics)
    s11_cards_html = "".join(
        f"""
        <div class="integrity-col">
          <div class="integrity-num {'accent-royal' if c.highlight else ''}">{_esc(c.value)}</div>
          <div class="integrity-lbl">{_esc(c.label)}</div>
          <div class="integrity-desc">{_esc(c.detail)}</div>
        </div>
        """
        for c in deck.s11_cards
    )

    # Slide 12 Platform & Territory Share Bars
    s12_plat_html = "".join(
        f"""
        <div class="share-row">
          <div class="share-name">{_esc(p.name)}</div>
          <div class="share-track">
            <div class="share-fill {'bar-blue' if p.highlight else 'bar-muted'}" style="width: {max(4.0, p.share_pct):.1f}%;"></div>
          </div>
          <div class="share-pct mono {'accent-blue' if p.highlight else ''}">{p.share_pct:.1f}%</div>
        </div>
        """
        for p in deck.s12_platforms
    )
    s12_terr_html = "".join(
        f"""
        <div class="share-row">
          <div class="share-name">{_esc(t.name)}</div>
          <div class="share-track">
            <div class="share-fill bar-blue" style="width: {max(5.0, min(100.0, t.share_pct * 2.1)):.1f}%;"></div>
          </div>
          <div class="share-pct mono accent-blue">{t.share_pct:.1f}%</div>
        </div>
        """
        for t in deck.s12_territories
    )

    # Slide 13 Track Concentration
    max_tr_usd = max((t.ltm_usd for t in deck.s13_tracks), default=1000.0) or 1000.0
    s13_tracks_html = ""
    for t in deck.s13_tracks:
        w_pct = max(6.0, (t.ltm_usd / max_tr_usd) * 100.0)
        b_cls = "tr-bar-royal" if t.is_top3 else "tr-bar-slate"
        s13_tracks_html += f"""
        <div class="tr-row">
          <div class="tr-title">{_esc(t.title[:24])}</div>
          <div class="tr-track">
            <div class="tr-fill {b_cls}" style="width: {w_pct:.1f}%;"></div>
          </div>
          <div class="tr-val mono">${t.ltm_usd:,.0f}</div>
        </div>
        """
    s13_kpis_html = "".join(
        f"""
        <div class="tr-kpi-box">
          <div class="tr-kpi-val {'accent-royal' if k.highlight else ''}">{_esc(k.value)}</div>
          <div class="tr-kpi-lbl">{_esc(k.label)}</div>
          <div class="tr-kpi-sub">{_esc(k.detail)}</div>
        </div>
        """
        for k in deck.s13_summary_cards
    )

    # Slide 15 Ask vs Value Range Corridors
    axis_max = max(deck.s15_axis_max_usd, 100_000.0)
    s15_rows_html = ""
    for c in deck.s15_corridors:
        left_pct = max(0.0, min(92.0, (c.low_usd / axis_max) * 100.0))
        width_pct = max(4.0, min(100.0 - left_pct, ((c.high_usd - c.low_usd) / axis_max) * 100.0))
        cls_map = {
            "blue_light": "corridor-sky",
            "blue_dark": "corridor-royal",
            "orange_bar": "corridor-orange",
            "orange_marker": "corridor-orange",
        }
        c_cls = cls_map.get(c.variant, "corridor-royal")
        marker_html = ""
        if c.marker_usd is not None:
            m_pct = max(0.0, min(99.0, (c.marker_usd / axis_max) * 100.0))
            marker_html = f'<div class="corridor-marker" style="left: {m_pct:.1f}%;"></div>'
        s15_rows_html += f"""
        <div class="corridor-row">
          <div class="corridor-meta">
            <div class="corridor-title">{_esc(c.label)}</div>
            <div class="corridor-sub mono">{_esc(c.sublabel)}</div>
          </div>
          <div class="corridor-track">
            <div class="corridor-bar {c_cls}" style="left: {left_pct:.1f}%; width: {width_pct:.1f}%;"></div>
            {marker_html}
          </div>
        </div>
        """

    # Slide 16 Offer Structures (3 columns)
    s16_cards_html = ""
    for opt in deck.s16_options:
        lines_html = "".join(
            f"""
            <div class="offer-line">
              <span>{_esc(ln.label)}</span>
              <span class="mono bold">{_esc(ln.value)}</span>
            </div>
            """
            for ln in opt.breakdown_lines
        )
        s16_cards_html += f"""
        <div class="offer-card {'offer-card-rec' if opt.recommended else ''}">
          <div class="offer-badge {'accent-blue' if opt.recommended else 'muted-text'}">{_esc(opt.badge)}</div>
          <div class="offer-price">{_esc(opt.price_headline)}</div>
          <div class="offer-desc">{_esc(opt.description)}</div>
          <div class="offer-lines">{lines_html}</div>
        </div>
        """

    # Slide 17 Proposed Next Steps (4 columns)
    s17_steps_html = "".join(
        f"""
        <div class="step-col">
          <div class="step-num mono accent-royal">{_esc(s.step_number)}</div>
          <div class="step-title">{_esc(s.title)}</div>
          <div class="step-desc">{_esc(s.description)}</div>
        </div>
        """
        for s in deck.s17_steps
    )

    paywall_banner_html = ""
    locked_cls = "locked-slide" if locked_preview else ""
    if locked_preview:
        cta_href = _esc(checkout_url or "#unlock-checkout")
        paywall_banner_html = f"""
        <div class="paywall-floating-cta">
          <div>
            <strong>Previewing Slides 01–02 of 19</strong> · Unlock the complete Claude + SPACE 19-Slide Institutional Investment Memo PDF (including DCF Schedule, WACC Build-up, TypeSafe AI 10-Question Audit &amp; Offer Structures).
          </div>
          <a href="{cta_href}" class="paywall-btn">Unlock Full 19-Slide PDF ($299 / €275)</a>
        </div>
        """

    if locked_preview:
        redacted_slide_specs = [
            ("03", "02 · THE DATA", "Royalty Statement & Ledger Telemetry"),
            ("04", "03 · CLAIM CHECK", "Declared vs. Verified Cash Flow Reconciliation"),
            ("05", "04 · MOMENTUM", "Monthly Royalty Trajectory & Seasonality"),
            ("06", "05 · THE MODEL", "Weibull Monte Carlo & DTW Architecture"),
            ("07", "06 · DISCOUNT RATE BUILD-UP", "Risk-Adjusted WACC Decomposition"),
            ("08", "07 · STANDALONE VALUE", "Standalone Catalog Valuation Corridor"),
            ("09", "08 · CUMULATIVE NPV BY HORIZON", "Horizon Valuation & Payback Profile"),
            ("10", "09 · DCF RECONCILIATION", "10-Year DCF Cash Flow Schedule"),
            ("11", "10 · TYPESAFE AI CROSS-CHECK", "10-Question TypeSafe AI (JEV) Audit"),
            ("12", "11 · STREAM INTEGRITY", "Streaming Authenticity & Fraud Audit"),
            ("13", "12 · WHERE THE MONEY COMES FROM", "Platform & Territory Breakdown"),
            ("14", "13 · TRACK CONCENTRATION", "ISRC Concentration & Top Track Share"),
            ("15", "14 · THE SELLER'S POSITION", "Commercial Context & Seller Expectations"),
            ("16", "15 · ASK VS VALUE", "Valuation Corridor vs. Seller Ask"),
            ("17", "16 · OFFER STRUCTURES", "Institutional Deal Options (A / B / C)"),
            ("18", "17 · PROPOSED NEXT STEPS", "Risk Matrix & Execution Roadmap"),
            ("19", "18 · CLOSING", "Institutional Closing & Contacts"),
        ]
        cta_href = _esc(checkout_url or "#unlock-checkout")
        slides_03_to_19_html = "\n".join(
            f"""<!-- SLIDE {s_num}: {s_tag} (REDACTED) -->
<section class="slide slide-dark locked-slide" data-slide-number="{s_num}" data-redacted="true">
  <div>
    <div class="section-tag mono">{_esc(s_tag)}</div>
    <h2 class="slide-headline">{_esc(s_title)}</h2>
  </div>
  <div class="redacted-placeholder-card" style="border:1px dashed #3A435E; border-radius:8px; padding:32px; background:#12151E; text-align:center; margin:auto 0;">
    <div class="mono bold accent-orange" style="font-size:13px; letter-spacing:0.08em; margin-bottom:10px;">
      LOCKED — SERVER ENTITLEMENT REQUIRED TO RENDER SLIDE CONTENT
    </div>
    <p style="font-size:14px; color:#9BA3B8; margin:0 0 16px;">
      Slide {s_num} of 19 ({_esc(s_title)}) has been withheld on the server until a verified payment receipt or Desk Pass entitlement is presented.
    </p>
    <a href="{cta_href}" class="paywall-btn" style="display:inline-block;">Unlock Full 19-Slide Memo ($299 / €275)</a>
  </div>
  <div class="slide-footer mono">
    <span>{memo_footer_left} · SERVER-REDACTED PREVIEW</span>
    <span>{s_num}</span>
  </div>
</section>"""
            for s_num, s_tag, s_title in redacted_slide_specs
        )
    else:
        slides_03_to_19_html = f"""<!-- SLIDE 03: 02 · THE DATA -->
<section class="slide slide-light">
  <div>
    <div class="section-tag mono">02 · THE DATA</div>
    <h2 class="slide-headline">{_esc(deck.s02_headline)}</h2>
  </div>
  <div class="data-split">
    <div>
      <div class="giant-number">{_esc(deck.s02_primary_count)}</div>
      <div class="giant-label">{_esc(deck.s02_primary_label)}</div>
    </div>
    <div class="light-cells-grid">{s02_cells_html}</div>
  </div>
  <div>
    <p class="bottom-note">{_esc(deck.s02_bottom_note)}</p>
    <div class="slide-footer mono">
      <span>{memo_footer_left}</span>
      <span>03</span>
    </div>
  </div>
</section>

<!-- SLIDE 04: 03 · CLAIM CHECK -->
<section class="slide slide-dark">
  <div>
    <div class="section-tag mono">03 · CLAIM CHECK</div>
    <h2 class="slide-headline">{_esc(deck.s03_headline)}</h2>
  </div>
  <div class="claim-bars-wrap">{s03_bars_html}</div>
  <div>
    <p class="bottom-note">{_esc(deck.s03_bottom_note)}</p>
    <div class="slide-footer mono">
      <span>{memo_footer_left}</span>
      <span>04</span>
    </div>
  </div>
</section>

<!-- SLIDE 05: 04 · MOMENTUM -->
<section class="slide slide-light">
  <div style="display:flex; justify-content:space-between; align-items:flex-end;">
    <div>
      <div class="section-tag mono">04 · MOMENTUM</div>
      <h2 class="slide-headline" style="margin-bottom:6px;">{_esc(deck.s04_headline)}</h2>
    </div>
    <div class="mono" style="font-size:11px; color:#4A4F5C;">
      <span style="color:#2356C8;">■</span> LTM window &nbsp;&nbsp;
      <span style="color:#B8B6AF;">■</span> Before
    </div>
  </div>
  <div class="vchart-area">{s04_bars_html}</div>
  <div class="slide-footer mono">
    <span>{_esc(deck.s04_footer_caption)}</span>
    <span>05</span>
  </div>
</section>

<!-- SLIDE 06: 05 · THE MODEL -->
<section class="slide slide-dark">
  <div>
    <div class="section-tag mono">05 · THE MODEL</div>
    <h2 class="slide-headline">{_esc(deck.s05_headline)}</h2>
  </div>
  <div class="grid-6">{s05_cards_html}</div>
  <div>
    <p class="bottom-note">{_esc(deck.s05_bottom_note)}</p>
    <div class="slide-footer mono">
      <span>{memo_footer_left}</span>
      <span>06</span>
    </div>
  </div>
</section>

<!-- SLIDE 07: 06 · DISCOUNT RATE BUILD-UP -->
<section class="slide slide-light">
  <div>
    <div class="section-tag mono">06 · DISCOUNT RATE BUILD-UP</div>
    <h2 class="slide-headline">{_esc(deck.s06_headline)}</h2>
    <div class="wacc-bar-row">{s06_segs_html}</div>
    <div class="wacc-total-row">
      <div class="wacc-total-num">= {deck.s06_total_wacc_pct:.2f}%</div>
      <div class="bottom-note" style="margin:0;">{_esc(deck.s06_bottom_note)}</div>
    </div>
  </div>
  <div class="slide-footer mono">
    <span>{memo_footer_left}</span>
    <span>07</span>
  </div>
</section>

<!-- SLIDE 08: 07 · STANDALONE VALUE -->
<section class="slide slide-dark">
  <div>
    <div class="section-tag mono">07 · STANDALONE VALUE</div>
    <h2 class="slide-headline">{_esc(deck.s07_headline)}</h2>
  </div>
  <div class="grid-3">{s07_cards_html}</div>
  <div>
    <p class="bottom-note">{_esc(deck.s07_jev_crosscheck_note)}</p>
    <div class="slide-footer mono">
      <span>{memo_footer_left}</span>
      <span>08</span>
    </div>
  </div>
</section>

<!-- SLIDE 09: 08 · CUMULATIVE NPV BY HORIZON -->
<section class="slide slide-dark">
  <div style="display:flex; justify-content:space-between; align-items:flex-end;">
    <div>
      <div class="section-tag mono">08 · CUMULATIVE NPV BY HORIZON</div>
      <h2 class="slide-headline" style="margin-bottom:4px;">{_esc(deck.s08_headline)}</h2>
    </div>
    <div class="mono" style="font-size:11px; color:#9BA3B8;">
      <span style="color:#363C4E;">■</span> P10 &nbsp;
      <span style="color:#F5F6F8;">■</span> P50 &nbsp;
      <span style="color:#84B1FF;">■</span> P90
    </div>
  </div>
  <div class="npv-groups-row">{s08_groups_html}</div>
  <div class="slide-footer mono">
    <span>{_esc(deck.s08_footer_caption)}</span>
    <span>09</span>
  </div>
</section>

<!-- SLIDE 10: 09 · DCF RECONCILIATION -->
<section class="slide slide-light">
  <div>
    <div class="section-tag mono">09 · DCF RECONCILIATION</div>
    <h2 class="slide-headline" style="margin-bottom:10px;">{_esc(deck.s09_headline)}</h2>
    <table class="recon-table">
      <thead>
        <tr>
          <th>Horizon</th>
          <th>P10</th>
          <th>P50</th>
          <th>P90</th>
          <th>P50 EUR</th>
        </tr>
      </thead>
      <tbody>{s09_rows_html}</tbody>
    </table>
    <div class="pillars-row">{s09_pillars_html}</div>
  </div>
  <div class="slide-footer mono">
    <span>{_esc(deck.s09_footer_caption)}</span>
    <span>10</span>
  </div>
</section>

<!-- SLIDE 11: 10 · TYPESAFE AI CROSS-CHECK -->
<section class="slide slide-dark">
  <div class="jev-top-row">
    <div>
      <div class="section-tag mono">10 · TYPESAFE AI CROSS-CHECK</div>
      <h2 class="slide-headline" style="margin-bottom:8px;">{_esc(deck.s10_headline)}</h2>
    </div>
    <div class="jev-pill mono">{_esc(deck.s10_agreement_badge)}</div>
  </div>
  <table class="jev-table">
    <thead>
      <tr>
        <th>JEV question</th>
        <th>Posterior answer</th>
        <th style="text-align:right;">Confidence</th>
      </tr>
    </thead>
    <tbody>{s10_rows_html}</tbody>
  </table>
  <div class="slide-footer mono">
    <span>{_esc(deck.s10_footer_caption)}</span>
    <span>11</span>
  </div>
</section>

<!-- SLIDE 12: 11 · STREAM INTEGRITY -->
<section class="slide slide-light">
  <div>
    <div class="section-tag mono">11 · STREAM INTEGRITY</div>
    <h2 class="slide-headline">{_esc(deck.s11_headline)}</h2>
    <div class="integrity-grid">{s11_cards_html}</div>
  </div>
  <div>
    <p class="bottom-note">{_esc(deck.s11_bottom_note)}</p>
    <div class="slide-footer mono">
      <span>{memo_footer_left}</span>
      <span>12</span>
    </div>
  </div>
</section>

<!-- SLIDE 13: 12 · WHERE THE MONEY COMES FROM -->
<section class="slide slide-dark">
  <div>
    <div class="section-tag mono">12 · WHERE THE MONEY COMES FROM</div>
    <h2 class="slide-headline" style="margin-bottom:10px;">{_esc(deck.s12_headline)}</h2>
  </div>
  <div class="two-col-charts">
    <div>
      <div class="col-subhead mono">BY PLATFORM</div>
      {s12_plat_html}
    </div>
    <div>
      <div class="col-subhead mono">BY TERRITORY</div>
      {s12_terr_html}
    </div>
  </div>
  <div>
    <p class="bottom-note">{_esc(deck.s12_bottom_note)}</p>
    <div class="slide-footer mono">
      <span>SPACE · Territory: share of audio streams</span>
      <span>13</span>
    </div>
  </div>
</section>

<!-- SLIDE 14: 13 · TRACK CONCENTRATION -->
<section class="slide slide-light">
  <div>
    <div class="section-tag mono">13 · TRACK CONCENTRATION</div>
    <h2 class="slide-headline" style="margin-bottom:10px;">{_esc(deck.s13_headline)}</h2>
  </div>
  <div class="tracks-layout">
    <div>{s13_tracks_html}</div>
    <div class="tr-kpis-col">{s13_kpis_html}</div>
  </div>
  <div class="slide-footer mono">
    <span>{_esc(deck.s13_footer_caption)}</span>
    <span>14</span>
  </div>
</section>

<!-- SLIDE 15: 14 · THE SELLER'S POSITION -->
<section class="slide slide-blue">
  <div class="section-tag mono">14 · THE SELLER'S POSITION</div>
  <div>
    <blockquote class="quote-block">“{_esc(deck.s14_quote_text)}”</blockquote>
    <div class="quote-attr">{_esc(deck.s14_attribution)}</div>
  </div>
  <div class="slide-footer mono">
    <span>{_esc(deck.s14_footer_caption)}</span>
    <span>15</span>
  </div>
</section>

<!-- SLIDE 16: 15 · ASK VS VALUE -->
<section class="slide slide-light">
  <div>
    <div class="section-tag mono">15 · ASK VS VALUE</div>
    <h2 class="slide-headline" style="margin-bottom:8px;">{_esc(deck.s15_headline)}</h2>
  </div>
  <div class="corridors-wrap">{s15_rows_html}</div>
  <div class="slide-footer mono">
    <span>{_esc(deck.s15_footer_caption)}</span>
    <span>16</span>
  </div>
</section>

<!-- SLIDE 17: 16 · OFFER STRUCTURES -->
<section class="slide slide-dark">
  <div>
    <div class="section-tag mono">16 · OFFER STRUCTURES</div>
    <h2 class="slide-headline" style="margin-bottom:12px;">{_esc(deck.s16_headline)}</h2>
  </div>
  <div class="grid-3">{s16_cards_html}</div>
  <div class="slide-footer mono">
    <span>{_esc(deck.s16_fallback_footer)}</span>
    <span>17</span>
  </div>
</section>

<!-- SLIDE 18: 17 · PROPOSED NEXT STEPS -->
<section class="slide slide-light">
  <div>
    <div class="section-tag mono">17 · PROPOSED NEXT STEPS</div>
    <h2 class="slide-headline">{_esc(deck.s17_headline)}</h2>
  </div>
  <div class="steps-grid">{s17_steps_html}</div>
  <div>
    <p class="bottom-note">{_esc(deck.s17_bottom_note)}</p>
    <div class="slide-footer mono">
      <span>{memo_footer_left}</span>
      <span>18</span>
    </div>
  </div>
</section>

<!-- SLIDE 19: CLOSING QUESTIONS -->
<section class="slide slide-blue">
  <div class="cover-brand">SPACE</div>
  <div>
    <h2 class="cover-title" style="font-size:68px;">{_esc(deck.s18_headline)}</h2>
  </div>
  <div class="slide-footer mono">
    <span>{_esc(deck.s18_footer)}</span>
    <span>19</span>
  </div>
</section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(deck.artist_or_label_name)} Catalog Valuation — SPACE Investment Memo</title>
<style>
  @page {{
    size: 960px 540px;
    margin: 0;
  }}
  * {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }}
  body {{
    margin: 0;
    padding: 0;
    background: #07080a;
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #f5f6f8;
  }}
  .mono {{
    font-family: "JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  }}
  .bold {{ font-weight: 700; }}
  .accent-blue {{ color: #84B1FF !important; }}
  .accent-royal {{ color: #2356C8 !important; }}
  .accent-orange {{ color: #F99441 !important; }}
  .muted-text {{ color: #8B92A5 !important; }}

  .slide {{
    width: 960px;
    height: 540px;
    position: relative;
    overflow: hidden;
    padding: 44px 56px 40px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    page-break-after: always;
    break-after: page;
    margin: 0 auto;
  }}
  @media screen {{
    body {{ padding: 24px 0 80px; }}
    .slide {{
      margin-bottom: 24px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.55);
      border-radius: 6px;
    }}
  }}
  .slide-dark {{
    background: #0D0E11;
    color: #F5F6F8;
  }}
  .slide-light {{
    background: #F3F2ED;
    color: #111318;
  }}
  .slide-blue {{
    background: #1E3F86;
    color: #FFFFFF;
  }}
  .locked-slide {{
    user-select: none;
    opacity: 0.95;
  }}
  .paywall-floating-cta {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(13, 14, 17, 0.96);
    border-top: 1px solid #2b3550;
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    z-index: 9999;
    color: #f5f6f8;
    font-size: 14px;
  }}
  .paywall-btn {{
    background: #2356C8;
    color: #ffffff;
    text-decoration: none;
    padding: 11px 22px;
    border-radius: 6px;
    font-weight: 700;
    white-space: nowrap;
  }}

  /* Header & Footer */
  .section-tag {{
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 8px;
  }}
  .slide-dark .section-tag {{ color: #84B1FF; }}
  .slide-light .section-tag {{ color: #2356C8; }}
  .slide-blue .section-tag {{ color: #A9C6FF; }}

  .slide-headline {{
    font-size: 32px;
    line-height: 1.14;
    font-weight: 700;
    letter-spacing: -0.025em;
    margin: 0 0 18px 0;
    max-width: 780px;
  }}
  .slide-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 10.5px;
    letter-spacing: 0.04em;
    padding-top: 10px;
    border-top: 1px solid rgba(139, 146, 165, 0.18);
  }}
  .slide-dark .slide-footer {{ color: #7C8498; }}
  .slide-light .slide-footer {{ color: #6E717A; border-top-color: rgba(17, 19, 24, 0.12); }}
  .slide-blue .slide-footer {{ color: #B8CEFF; border-top-color: rgba(255, 255, 255, 0.2); }}

  .bottom-note {{
    font-size: 13px;
    line-height: 1.45;
    margin-top: 10px;
    max-width: 820px;
  }}
  .slide-dark .bottom-note {{ color: #B4BCCF; }}
  .slide-light .bottom-note {{ color: #3D414C; }}

  /* Cover Slide */
  .cover-brand {{
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 0.18em;
    color: #FFFFFF;
  }}
  .cover-center {{
    position: relative;
    z-index: 2;
    max-width: 560px;
    margin-top: 30px;
  }}
  .cover-kicker {{
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #84B1FF;
    margin-bottom: 14px;
  }}
  .cover-title {{
    font-size: 64px;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.02;
    margin: 0 0 16px 0;
    color: #FFFFFF;
  }}
  .cover-sub {{
    font-size: 17px;
    line-height: 1.45;
    color: #B6C0D4;
    margin: 0;
  }}
  .cover-circles {{
    position: absolute;
    right: -40px;
    top: 45px;
    width: 450px;
    height: 450px;
    pointer-events: none;
    z-index: 1;
  }}

  /* Cards Grid */
  .grid-4 {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    flex: 1;
    align-items: stretch;
  }}
  .grid-3 {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    flex: 1;
    align-items: stretch;
  }}
  .grid-6 {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    flex: 1;
  }}
  .dark-card {{
    background: #141720;
    border: 1px solid #252A3A;
    border-radius: 6px;
    padding: 18px 18px 16px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}
  .highlight-border {{
    border-color: #84B1FF;
  }}
  .card-label {{
    font-size: 11.5px;
    color: #9BA3B8;
    font-weight: 500;
  }}
  .card-big-val {{
    font-size: 30px;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 8px 0;
    color: #FFFFFF;
  }}
  .card-huge-val {{
    font-size: 36px;
    font-weight: 700;
    letter-spacing: -0.025em;
    margin: 12px 0;
    color: #FFFFFF;
  }}
  .card-detail {{
    font-size: 12px;
    line-height: 1.4;
    color: #8D96AC;
  }}

  /* Slide 02 Light Data Layout */
  .data-split {{
    display: grid;
    grid-template-columns: 1.05fr 1.45fr;
    gap: 32px;
    align-items: center;
    flex: 1;
  }}
  .giant-number {{
    font-size: 68px;
    font-weight: 800;
    letter-spacing: -0.035em;
    color: #2356C8;
    line-height: 1;
  }}
  .giant-label {{
    font-size: 16px;
    font-weight: 600;
    color: #2C303A;
    margin-top: 8px;
  }}
  .light-cells-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px 24px;
  }}
  .light-data-cell {{
    border-top: 2px solid #111318;
    padding-top: 10px;
  }}
  .cell-title {{ font-size: 12px; font-weight: 600; color: #4A4F5C; }}
  .cell-val {{ font-size: 24px; font-weight: 700; margin: 4px 0; color: #111318; }}
  .cell-sub {{ font-size: 11.5px; color: #686D7A; }}

  /* Slide 03 Claim Check Bars */
  .claim-bars-wrap {{
    display: flex;
    flex-direction: column;
    gap: 18px;
    margin: 18px 0;
    flex: 1;
    justify-content: center;
  }}
  .claim-bar-row {{
    display: grid;
    grid-template-columns: 210px 1fr 110px;
    align-items: center;
    gap: 16px;
  }}
  .claim-bar-label {{ font-size: 13.5px; color: #D0D6E4; font-weight: 500; }}
  .claim-bar-track {{
    height: 30px;
    background: #171A24;
    border-radius: 4px;
    overflow: hidden;
  }}
  .claim-bar-fill {{ height: 100%; border-radius: 4px; }}
  .bar-orange {{ background: #F99441; }}
  .bar-muted {{ background: #3A4052; }}
  .bar-blue {{ background: #84B1FF; }}
  .claim-bar-val {{
    font-size: 18px;
    font-weight: 700;
    text-align: right;
  }}

  /* Slide 04 Vertical Momentum Chart */
  .vchart-area {{
    display: flex;
    align-items: flex-end;
    gap: 8px;
    height: 250px;
    padding: 16px 0 8px;
    border-bottom: 1px solid #C9C7BE;
  }}
  .vbar-col {{
    flex: 1;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: center;
  }}
  .vbar-wrap {{
    width: 100%;
    height: 210px;
    display: flex;
    align-items: flex-end;
  }}
  .vbar-fill {{
    width: 100%;
    border-radius: 3px 3px 0 0;
  }}
  .vbar-ltm {{ background: #2356C8; }}
  .vbar-before {{ background: #B8B6AF; }}
  .vbar-month {{
    font-size: 10px;
    color: #5C606B;
    margin-top: 6px;
  }}

  /* Slide 06 WACC Segmented Bar */
  .wacc-bar-row {{
    display: flex;
    gap: 4px;
    margin: 22px 0 18px;
    height: 82px;
  }}
  .wacc-seg {{
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    border-radius: 4px;
  }}
  .wacc-seg-dark {{ background: #111318; color: #FFFFFF; }}
  .wacc-seg-royal {{ background: #2356C8; color: #FFFFFF; }}
  .wacc-seg-sky {{ background: #7BA7FF; color: #111318; }}
  .wacc-seg-pct {{ font-size: 20px; font-weight: 700; }}
  .wacc-seg-lbl {{ font-size: 11px; opacity: 0.9; }}
  .wacc-total-row {{
    display: flex;
    align-items: center;
    gap: 28px;
    padding-top: 16px;
    border-top: 1px solid #C9C7BE;
  }}
  .wacc-total-num {{
    font-size: 46px;
    font-weight: 800;
    color: #2356C8;
    letter-spacing: -0.03em;
    white-space: nowrap;
  }}

  /* Slide 08 Cumulative NPV Triad Bars */
  .npv-groups-row {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 28px;
    height: 265px;
    align-items: end;
    margin: 12px 0;
  }}
  .npv-group {{
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
  }}
  .npv-bars-triad {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    height: 215px;
    align-items: end;
    border-bottom: 1px solid #2A3042;
    padding-bottom: 6px;
  }}
  .npv-bar-col {{
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: center;
  }}
  .npv-bar-top-val {{
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 5px;
  }}
  .npv-bar-rect {{ width: 100%; border-radius: 3px 3px 0 0; }}
  .npv-p10 {{ background: #363C4E; }}
  .npv-p50 {{ background: #F5F6F8; }}
  .npv-p90 {{ background: #84B1FF; }}
  .npv-group-label {{
    text-align: center;
    font-size: 12.5px;
    color: #B4BCCF;
    margin-top: 10px;
    font-weight: 500;
  }}

  /* Slide 09 Reconciliation Table */
  .recon-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
    margin: 6px 0 16px;
  }}
  .recon-table th {{
    text-align: left;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #636875;
    padding: 8px 10px;
    border-bottom: 2px solid #111318;
  }}
  .recon-table td {{
    padding: 11px 10px;
    border-bottom: 1px solid #D6D4CC;
  }}
  .pillars-row {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-top: 8px;
  }}
  .light-pillar {{
    border-top: 2px solid #111318;
    padding-top: 10px;
  }}
  .pillar-big {{ font-size: 22px; font-weight: 800; color: #111318; margin-bottom: 4px; }}
  .pillar-sub {{ font-size: 12px; color: #4A4F5C; line-height: 1.35; }}

  /* Slide 10 JEV 10-Question Table */
  .jev-top-row {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .jev-pill {{
    background: #F5F6F8;
    color: #0D0E11;
    font-size: 11px;
    font-weight: 700;
    padding: 6px 12px;
    border-radius: 999px;
  }}
  .jev-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }}
  .jev-table th {{
    text-align: left;
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8B92A5;
    padding: 5px 8px;
    border-bottom: 1px solid #2A3042;
  }}
  .jev-table td {{
    padding: 6.5px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }}
  .jev-row-highlight {{
    background: rgba(249, 148, 65, 0.14);
  }}
  .jev-q-col {{ color: #D5DBE8; font-weight: 500; width: 28%; }}
  .jev-ans-col {{ color: #9BA3B8; }}
  .jev-conf-col {{ text-align: right; width: 12%; color: #D5DBE8; }}

  /* Slide 11 Stream Integrity */
  .integrity-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin: 22px 0;
  }}
  .integrity-col {{
    border-top: 2px solid #111318;
    padding-top: 14px;
  }}
  .integrity-num {{
    font-size: 48px;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1;
    margin-bottom: 8px;
  }}
  .integrity-lbl {{ font-size: 13px; font-weight: 700; color: #111318; margin-bottom: 4px; }}
  .integrity-desc {{ font-size: 12px; color: #4E5360; line-height: 1.35; }}

  /* Slide 12 Platform & Territory Two-Column */
  .two-col-charts {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 36px;
    flex: 1;
    align-items: start;
    margin-top: 6px;
  }}
  .col-subhead {{
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #8B92A5;
    margin-bottom: 10px;
    font-weight: 600;
  }}
  .share-row {{
    display: grid;
    grid-template-columns: 95px 1fr 54px;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }}
  .share-name {{ font-size: 12.5px; color: #DCE1EE; }}
  .share-track {{ height: 14px; background: #181C26; border-radius: 3px; overflow: hidden; }}
  .share-fill {{ height: 100%; border-radius: 3px; }}
  .share-pct {{ font-size: 12px; text-align: right; }}

  /* Slide 13 Track Concentration */
  .tracks-layout {{
    display: grid;
    grid-template-columns: 1.55fr 0.85fr;
    gap: 32px;
    flex: 1;
    align-items: center;
  }}
  .tr-row {{
    display: grid;
    grid-template-columns: 145px 1fr 68px;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }}
  .tr-title {{ font-size: 11px; font-weight: 600; color: #22252E; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .tr-track {{ height: 13px; background: #E2E0D8; border-radius: 2px; overflow: hidden; }}
  .tr-fill {{ height: 100%; }}
  .tr-bar-royal {{ background: #2356C8; }}
  .tr-bar-slate {{ background: #9E9D97; }}
  .tr-val {{ font-size: 11px; text-align: right; color: #333742; }}
  .tr-kpis-col {{
    display: flex;
    flex-direction: column;
    gap: 14px;
  }}
  .tr-kpi-box {{
    border-top: 2px solid #111318;
    padding-top: 8px;
  }}
  .tr-kpi-val {{ font-size: 28px; font-weight: 800; line-height: 1.1; }}
  .tr-kpi-lbl {{ font-size: 12px; font-weight: 700; color: #22252E; }}
  .tr-kpi-sub {{ font-size: 11px; color: #636875; }}

  /* Slide 14 Seller Position Quote */
  .quote-block {{
    font-size: 30px;
    font-weight: 700;
    line-height: 1.28;
    letter-spacing: -0.02em;
    max-width: 800px;
    margin: 24px 0 16px;
  }}
  .quote-attr {{
    font-size: 15px;
    color: #B8CEFF;
    font-weight: 500;
  }}

  /* Slide 15 Ask vs Value Corridors */
  .corridors-wrap {{
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1;
    justify-content: center;
  }}
  .corridor-row {{
    display: grid;
    grid-template-columns: 250px 1fr;
    align-items: center;
    gap: 18px;
  }}
  .corridor-title {{ font-size: 13px; font-weight: 700; color: #111318; }}
  .corridor-sub {{ font-size: 11px; color: #5B606E; }}
  .corridor-track {{
    position: relative;
    height: 22px;
    background: #E4E2DA;
    border-radius: 4px;
  }}
  .corridor-bar {{
    position: absolute;
    top: 2px;
    bottom: 2px;
    border-radius: 3px;
  }}
  .corridor-sky {{ background: #84B1FF; }}
  .corridor-royal {{ background: #2356C8; }}
  .corridor-orange {{ background: #F99441; }}
  .corridor-marker {{
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 3px;
    background: #111318;
  }}

  /* Slide 16 Offer Cards */
  .offer-card {{
    background: #141720;
    border: 1px solid #262C3D;
    border-radius: 6px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}
  .offer-card-rec {{
    border: 1.5px solid #84B1FF;
    background: #161B28;
  }}
  .offer-badge {{
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }}
  .offer-price {{
    font-size: 32px;
    font-weight: 800;
    margin: 6px 0;
    color: #FFFFFF;
  }}
  .offer-desc {{
    font-size: 12px;
    color: #A2ABC0;
    line-height: 1.4;
    margin-bottom: 12px;
  }}
  .offer-lines {{
    border-top: 1px solid #262C3D;
    padding-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .offer-line {{
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: #CFD6E6;
  }}

  /* Slide 17 Proposed Next Steps */
  .steps-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 18px;
    margin: 24px 0;
    flex: 1;
  }}
  .step-col {{
    border-top: 2px solid #2356C8;
    padding-top: 12px;
  }}
  .step-num {{ font-size: 13px; font-weight: 700; margin-bottom: 8px; }}
  .step-title {{ font-size: 17px; font-weight: 700; color: #111318; margin-bottom: 8px; }}
  .step-desc {{ font-size: 12.5px; color: #4A4F5C; line-height: 1.45; }}
</style>
</head>
<body>

{paywall_banner_html}

<!-- SLIDE 01: COVER -->
<section class="slide slide-dark">
  <div class="cover-brand">SPACE</div>
  <svg class="cover-circles" viewBox="0 0 450 450" fill="none">
    <circle cx="250" cy="225" r="190" stroke="#232838" stroke-width="1.2"/>
    <circle cx="250" cy="225" r="125" stroke="#2D3448" stroke-width="1.2"/>
    <circle cx="358" cy="162" r="6.5" fill="#84B1FF"/>
  </svg>
  <div class="cover-center">
    <div class="cover-kicker mono">{_esc(deck.cover_kicker)}</div>
    <h1 class="cover-title">{_esc(deck.cover_title)}</h1>
    <p class="cover-sub">{_esc(deck.cover_subtitle)}</p>
  </div>
  <div class="slide-footer mono">
    <span>{_esc(deck.cover_footer)}</span>
    <span>01</span>
  </div>
</section>

<!-- SLIDE 02: 01 · AT A GLANCE -->
<section class="slide slide-dark">
  <div>
    <div class="section-tag mono">01 · AT A GLANCE</div>
    <h2 class="slide-headline">{_esc(deck.s01_headline)}</h2>
  </div>
  <div class="grid-4">{s01_cards_html}</div>
  <div>
    <p class="bottom-note">{_esc(deck.s01_bottom_note)}</p>
    <div class="slide-footer mono">
      <span>{memo_footer_left}</span>
      <span>02</span>
    </div>
  </div>
</section>

{slides_03_to_19_html}

</body>
</html>
"""


def _build_minimal_16x9_pdf_fallback(deck: CatalogInvestmentMemoDeck) -> bytes:
    """
    Pure-Python 16:9 (`960 x 540 pt`) PDF fallback in case headless Chrome is unavailable.
    """
    slides_text = [
        (deck.cover_title, deck.cover_subtitle),
        ("01 · AT A GLANCE", deck.s01_headline),
        ("02 · THE DATA", f"{deck.s02_primary_count} {deck.s02_primary_label}"),
        ("03 · CLAIM CHECK", deck.s03_headline),
        ("04 · MOMENTUM", deck.s04_headline),
        ("05 · THE MODEL", deck.s05_headline),
        ("06 · DISCOUNT RATE BUILD-UP", f"{deck.s06_headline} (= {deck.s06_total_wacc_pct:.2f}%)"),
        ("07 · STANDALONE VALUE", deck.s07_headline),
        ("08 · CUMULATIVE NPV BY HORIZON", deck.s08_headline),
        ("09 · DCF RECONCILIATION", deck.s09_headline),
        ("10 · TYPESAFE AI CROSS-CHECK", deck.s10_headline),
        ("11 · STREAM INTEGRITY", deck.s11_headline),
        ("12 · WHERE THE MONEY COMES FROM", deck.s12_headline),
        ("13 · TRACK CONCENTRATION", deck.s13_headline),
        ("14 · THE SELLER'S POSITION", deck.s14_quote_text[:90]),
        ("15 · ASK VS VALUE", deck.s15_headline),
        ("16 · OFFER STRUCTURES", deck.s16_headline),
        ("17 · PROPOSED NEXT STEPS", deck.s17_headline),
        ("SPACE", deck.s18_headline),
    ]
    objects: list[bytes] = []
    page_ids: list[int] = []

    # 1: Catalog, 2: Pages, 3: Font
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")  # placeholder for Pages
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    for idx, (hdr, sub) in enumerate(slides_text):
        safe_h = hdr.encode("latin-1", "replace").replace(b"(", b"\\(").replace(b")", b"\\)")
        safe_s = sub.encode("latin-1", "replace").replace(b"(", b"\\(").replace(b")", b"\\)")
        stream = (
            b"0.05 0.055 0.067 rg 0 0 960 540 re f "
            b"BT /F1 14 Tf 0.52 0.69 1.0 rg 56 470 Td (" + safe_h + b") Tj ET "
            b"BT /F1 26 Tf 1 1 1 rg 56 410 Td (" + safe_s + b") Tj ET "
            + f"BT /F1 10 Tf 0.6 0.65 0.75 rg 56 36 Td (SPACE · {deck.deal_code} · Slide {idx+1:02d}/19) Tj ET".encode("latin-1", "replace")
        )
        content_id = len(objects) + 1
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        page_id = len(objects) + 1
        page_ids.append(page_id)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 960 540] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )

    kids_str = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_ids)} >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def render_investment_memo_pdf(
    deck: CatalogInvestmentMemoDeck,
    *,
    output_path: Optional[Path] = None,
) -> bytes:
    """
    Renders the 19-slide 16:9 `CatalogInvestmentMemoDeck` to a print-ready PDF using
    headless Google Chrome (`--headless --print-to-pdf`), falling back to a pure-Python
    16:9 PDF builder if Chrome is unavailable.
    """
    html_str = render_investment_memo_html(deck, locked_preview=False)
    chrome_bin = (
        ("/usr/bin/google-chrome-stable" if Path("/usr/bin/google-chrome-stable").exists() else None)
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("google-chrome")
    )

    pdf_bytes: Optional[bytes] = None
    if chrome_bin:
        with tempfile.TemporaryDirectory(
            prefix="space_memo_",
            ignore_cleanup_errors=True,
        ) as tmpdir:
            tmp_html = Path(tmpdir) / "memo.html"
            tmp_pdf = Path(tmpdir) / "memo.pdf"
            tmp_profile = Path(tmpdir) / "chrome_profile"
            tmp_profile.mkdir(parents=True, exist_ok=True)
            tmp_html.write_text(html_str, encoding="utf-8")
            cmd = [
                chrome_bin,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={tmp_profile}",
                "--no-pdf-header-footer",
                f"--print-to-pdf={tmp_pdf}",
                f"file://{tmp_html}",
            ]
            try:
                subprocess.run(cmd, check=False, capture_output=True, timeout=12)
            except subprocess.TimeoutExpired:
                pass
            if tmp_pdf.exists() and tmp_pdf.stat().st_size > 1000:
                pdf_bytes = tmp_pdf.read_bytes()

    if not pdf_bytes:
        pdf_bytes = _build_minimal_16x9_pdf_fallback(deck)

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(pdf_bytes)

    return pdf_bytes
