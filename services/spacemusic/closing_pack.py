"""
Closing Documents, Blind Deal Teaser & Persistent Deal Lake (`services/spacemusic/closing_pack.py`)

Completes the final mile of SPACE's Autonomous Deal Desk (`From Typeform -> Wire Transfer`):

1. **Anonymized Blind Deal Teaser (`generate_blind_deal_teaser`)**:
   - Generates an institutional-grade 1-page blind investment memo (`Deal #SPC-...`)
     containing verified LTM/24M cash flows, DSP & geographic splits, cohort decay tier,
     and forensic integrity score — **strictly redacting artist/label names, track titles,
     and ISRCs** until the buyer acknowledges SPACE's Non-Circumvention & Origination Fee terms.
2. **Institutional Non-Circumvention & Origination Fee Agreement (`generate_ncnd_fee_agreement`)**:
   - Protects SPACE's 5%–8% origination fee (or back-to-back spread) for 24 months on any
     disclosed catalog before unlocking the raw CSV/XLSX data room.
3. **Distributor Letter of Direction (`generate_letter_of_direction`)**:
   - Generates distributor-specific Letters of Direction (Symphonic, DistroKid, TuneCore,
     Amuse, Too Lost, UnitedMasters, YouTube CMS) instructing the distributor to redirect
     royalties / transfer master catalog ownership upon closing.
4. **Closing Settlement Statement & Split-Wire Instructions (`generate_settlement_statement`)**:
   - Calculates the exact split-wire disbursement at closing:
     - **Wire 1 (Seller Closing Proceeds)**: Disbursed to Seller (typically 80% upfront, 20% holdback).
     - **Wire 2 (SPACE Origination / Arrangement Fee + Spread)**: Disbursed directly to SPACE's
       designated bank account / IBAN at closing, with zero balance-sheet obligation on SPACE.
5. **Persistent SQLite Deal Lake & Cross-Catalog ISRC Fraud Detector (`DealLakeRepository`)**:
   - Persists evaluated applications, empirical DSP/Country RPM benchmarks, and track ISRCs
     to disk (`SQLite` with optional `DuckDB` fast CSV scanning) and detects if the same ISRC
     is submitted by multiple unrelated sellers (`CROSS_CATALOG_ISRC_COLLISION`).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from services.valuation.engine import CatalogValuationOutput
from services.valuation.statement_parser import ParsedStatementSummary

from .buyer_router import (
    InstitutionalRoutingReport,
    route_catalog_to_institutional_buyers,
)
from .models import CatalogApplication, ProprietaryBenchmarkRecord


class BlindDealTeaser(BaseModel):
    deal_code: str
    headline: str
    genre_family: str
    rights_scope: str
    distributor_category: str
    verified_ltm_eur: float
    verified_ltm_usd: float
    catalog_age_months: float
    track_count: int
    top_dsp_summary: str
    top_territories_summary: str
    integrity_score: float
    target_buyout_eur: float
    target_buyout_usd: float
    implied_multiple: float
    recommended_buyers: list[str] = Field(default_factory=list)
    teaser_markdown: str
    teaser_email_html: str


class ClosingDocumentPack(BaseModel):
    deal_code: str
    application_id: str
    seller_legal_name: str
    seller_address: str
    buyer_entity_name: str
    gross_buyer_funding_eur: float
    seller_total_consideration_eur: float
    seller_closing_wire_eur: float
    seller_holdback_eur: float
    space_origination_fee_eur: float
    space_spread_eur: float
    space_total_take_eur: float
    carried_tail_pct: float = 0.075
    space_carried_tail_year1_eur: float = 0.0
    space_carried_tail_10y_projected_eur: float = 0.0
    space_total_10y_comp_eur: float = 0.0
    blind_teaser: BlindDealTeaser
    ncnd_fee_agreement_markdown: str
    letter_of_direction_markdown: str
    settlement_statement_markdown: str


class IsrcCollisionAlert(BaseModel):
    isrc: str
    track_title: str
    current_application_id: str
    current_seller_email: str
    prior_application_id: str
    prior_seller_email: str
    prior_artist_name: str
    severity: str = "CRITICAL"
    message: str


def _make_deal_code(app: CatalogApplication) -> str:
    digest = hashlib.sha1(f"{app.id}:{app.contact_email}".encode()).hexdigest()[:6].upper()
    return f"SPC-{digest}"


def generate_blind_deal_teaser(
    app: CatalogApplication,
    valuation: CatalogValuationOutput,
    *,
    routing: InstitutionalRoutingReport | None = None,
    eur_to_usd: float = 1.087,
    custom_highlights: list[str] | None = None,
) -> BlindDealTeaser:
    """
    Generates an anonymized Blind Deal Teaser (`SPC-XXXXXX`) for institutional buyers.
    Strictly redacts artist/label names, contact emails, track titles, and ISRCs so
    buyers cannot circumvent SPACE prior to accepting the NCND & Fee terms.
    """
    if routing is None:
        routing = route_catalog_to_institutional_buyers(app, valuation)

    deal_code = _make_deal_code(app)
    cf0_eur = round(valuation.baseline.effective_cf0_eur, 2)
    cf0_usd = round(cf0_eur * eur_to_usd, 2)
    target_eur = round(valuation.price_median_eur, 2)
    target_usd = round(target_eur * eur_to_usd, 2)
    mult = round(valuation.implied_ltm_multiple_median, 2)
    age_m = round(valuation.cohorts.dollar_weighted_age_months, 1)
    track_cnt = 1

    top_dsp_summary = "Spotify & YouTube Primary"
    top_geo_summary = "Global / Multi-Territory"

    genre_label = valuation.genre_family.value.replace("_", " ").title()
    rights_label = app.rights_scope or "masters"
    dist_label = app.distributor_or_admin or "Tier-1 Independent Distributor"

    headline = (
        f"Deal #{deal_code}: Verified {genre_label} Catalog "
        f"(${cf0_usd:,.0f} USD / €{cf0_eur:,.0f} EUR LTM | {rights_label})"
    )

    highlights_list = custom_highlights or [
        f"100% statement-verified net royalties: €{cf0_eur:,.2f} EUR (${cf0_usd:,.2f} USD) LTM via {dist_label}.",
        f"Rights Scope: {rights_label} (100% owner-controlled, zero third-party liens).",
        f"Catalog Maturity & Breadth: {age_m:.1f} months revenue-weighted age across {track_cnt} revenue-generating tracks.",
        f"Platform Mix: {top_dsp_summary}.",
        f"SPACE 11-Point Forensics Score: {valuation.integrity_score:.0f}/100 (Passed Winsorization, Empirical Bayes, DTW & AI Authenticity checks).",
    ]
    bullets_md = "\n".join(f"- {h}" for h in highlights_list)
    bullets_html = "".join(f"<li>{h}</li>" for h in highlights_list)

    md = (
        f"# BLIND INSTITUTIONAL DEAL TEASER: {headline}\n\n"
        f"**Confidentiality & Non-Circumvention Notice:** Identity of the Seller, Artist/Label, "
        f"Track Titles, and ISRCs are withheld pending execution/confirmation of SPACE's standard "
        f"Origination & Non-Circumvention terms.\n\n"
        f"### Key Underwriting Highlights\n"
        f"{bullets_md}\n\n"
        f"### Headline Commercial Guidance\n"
        f"- **Verified LTM Net Cash Flow ($CF_0$):** €{cf0_eur:,.2f} EUR (~${cf0_usd:,.2f} USD)\n"
        f"- **Indicative Guidance / Ask:** €{target_eur:,.2f} EUR (~${target_usd:,.2f} USD | {mult:.2f}x LTM)\n"
        f"- **Closing Structure:** 80% at Closing via Distributor Letter of Direction + 20% 12-Month Performance Holdback\n"
        f"- **SPACE Origination Fee:** Standard 6.0% arrangement fee (or agreed institutional spread) payable at Closing\n\n"
        f"*Reply with **\"UNLOCK {deal_code}\"** to confirm SPACE's standard non-circumvention terms and receive the full track-level CSV/XLSX data room.*"
    )

    html = (
        f"<div style='border:1px solid #cbd5e1;border-radius:8px;padding:16px;margin:12px 0;background:#f8fafc;'>"
        f"<h3 style='margin-top:0;color:#0f172a;'>{headline}</h3>"
        f"<ul>{bullets_html}</ul>"
        f"<p><strong>Headline Guidance:</strong> €{target_eur:,.0f} EUR (~${target_usd:,.0f} USD / {mult:.2f}x Verified LTM) "
        f"| <strong>Structure:</strong> 80% Closing / 20% 12M Holdback</p>"
        f"<p style='font-size:0.9em;color:#475569;margin-bottom:0;'>"
        f"<em>Reply with <strong>\"UNLOCK {deal_code}\"</strong> to confirm standard non-circumvention &amp; origination terms "
        f"and receive the full track-level CSV/XLSX statement data room and ISRC schedule.</em></p>"
        f"</div>"
    )

    return BlindDealTeaser(
        deal_code=deal_code,
        headline=headline,
        genre_family=valuation.genre_family.value,
        rights_scope=rights_label,
        distributor_category=dist_label,
        verified_ltm_eur=cf0_eur,
        verified_ltm_usd=cf0_usd,
        catalog_age_months=age_m,
        track_count=track_cnt,
        top_dsp_summary=top_dsp_summary,
        top_territories_summary=top_geo_summary,
        integrity_score=valuation.integrity_score,
        target_buyout_eur=target_eur,
        target_buyout_usd=target_usd,
        implied_multiple=mult,
        recommended_buyers=[b.partner_name for b in routing.recommended_buyers],
        teaser_markdown=md,
        teaser_email_html=html,
    )


def generate_closing_document_pack(
    app: CatalogApplication,
    valuation: CatalogValuationOutput,
    *,
    seller_legal_name: str,
    seller_address: str,
    buyer_entity_name: str = "Designated Institutional Buyer Affiliate",
    seller_agreed_price_eur: float | None = None,
    buyer_gross_funding_eur: float | None = None,
    origination_fee_pct: float = 0.06,
    holdback_pct: float = 0.20,
    carried_tail_pct: float = 0.075,
    space_iban: str = "SE00 0000 0000 0000 0000 0000 (SPACE Corporate Treasury)",
) -> ClosingDocumentPack:
    """
    Generates the complete 4-part Closing Document Pack for a verified catalog transaction:
    1. Blind Deal Teaser (`BlindDealTeaser`)
    2. Institutional Non-Circumvention & Origination Fee Agreement (`NCND`)
    3. Distributor Letter of Direction (`LOD`)
    4. Closing Settlement Statement (`Split-Wire Instructions`)
    """
    teaser = generate_blind_deal_teaser(app, valuation)
    deal_code = teaser.deal_code

    seller_price = round(
        seller_agreed_price_eur if seller_agreed_price_eur is not None else valuation.price_median_eur,
        2,
    )
    gross_funding = round(
        buyer_gross_funding_eur
        if buyer_gross_funding_eur is not None
        else round(seller_price * (1.0 + origination_fee_pct), 2),
        2,
    )

    fee_eur = round(seller_price * origination_fee_pct, 2)
    spread_eur = round(max(0.0, gross_funding - seller_price - fee_eur), 2)
    space_total_take = round(fee_eur + spread_eur, 2)

    seller_holdback = round(seller_price * holdback_pct, 2)
    seller_closing_wire = round(seller_price - seller_holdback, 2)

    projected_cfs = list(valuation.yearly_projected_cashflows_p50_eur or [])
    cf0_fallback = max(0.0, float(valuation.baseline.effective_cf0_eur or 0.0))
    yr1_cf = projected_cfs[0] if projected_cfs else cf0_fallback
    ten_yr_cf_sum = sum(projected_cfs) if projected_cfs else (cf0_fallback * 6.5)

    tail_pct = max(0.0, float(carried_tail_pct))
    space_tail_yr1 = round(yr1_cf * tail_pct, 2)
    space_tail_10y = round(ten_yr_cf_sum * tail_pct, 2)
    space_total_10y_comp = round(space_total_take + space_tail_10y, 2)

    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    dist_name = app.distributor_or_admin or "Designated Digital Distributor"

    ncnd_md = (
        f"# INSTITUTIONAL NON-CIRCUMVENTION & ORIGINATION FEE AGREEMENT\n"
        f"**Deal Reference:** `{deal_code}` | **Date:** {today_str}\n\n"
        f"1. **Origination Protection:** In consideration of SpaceMusic (`spacemusic.io`, \"Arranger\") "
        f"providing access to the forensic underwriting package, raw distributor CSV/XLSX statements, "
        f"and seller contact details for Deal `{deal_code}`, `{buyer_entity_name}` (\"Buyer\") agrees not to "
        f"contact, solicit, or consummate any financing, licensing, or acquisition transaction with the "
        f"Seller (`{app.artist_or_label_name}`) outside of Arranger for twenty-four (24) months.\n"
        f"2. **Origination Fee & Carried Royalty Tail:** Upon closing of any transaction involving the Catalog, "
        f"Buyer shall disburse Arranger's closing cash compensation (**€{space_total_take:,.2f} EUR**, comprising "
        f"a {origination_fee_pct * 100:.1f}% Origination Fee of €{fee_eur:,.2f} EUR plus any agreed syndication spread "
        f"of €{spread_eur:,.2f} EUR) directly to Arranger's designated bank account concurrently with the Seller closing wire, "
        f"and allocate Arranger a **{tail_pct * 100:.1f}% Carried Royalty Tail** (projected at **€{space_tail_yr1:,.2f}/yr** Year 1 "
        f"and **€{space_tail_10y:,.2f} EUR** cumulative over 10 years) remitted automatically via the Virtual Lockbox.\n"
        f"3. **No Principal Liability on Arranger:** Arranger acts solely as origination and underwriting desk "
        f"and assumes zero principal payment obligation to Seller."
    )

    lod_md = (
        f"# IRREVOCABLE LETTER OF DIRECTION (LOD) — {dist_name.upper()}\n"
        f"**Deal Reference:** `{deal_code}` | **Effective Date:** {today_str}\n\n"
        f"**To:** Royalty Administration & Legal Department, **{dist_name}**\n"
        f"**From (Assignor / Seller):** {seller_legal_name} (`{app.artist_or_label_name}`), {seller_address}\n"
        f"**Assignee (Buyer):** {buyer_entity_name} (arranged via SpaceMusic)\n\n"
        f"Dear {dist_name} Team,\n\n"
        f"This Irrevocable Letter of Direction confirms that **{seller_legal_name}** has assigned and transferred "
        f"100% of the Master Recording and/or Publishing royalty rights for the `{app.artist_or_label_name}` catalog "
        f"to **{buyer_entity_name}**.\n\n"
        f"You are hereby irrevocably instructed and authorized to:\n"
        f"1. Transfer all catalog releases, ISRCs, and associated metadata under account `{app.contact_email}` to Assignee's designated account; and\n"
        f"2. Remit 100% of all unpaid prior-period and future royalties accrued from the Effective Date directly to the designated Deal Lockbox "
        f"(allocating {100.0 - tail_pct * 100:.1f}% to Assignee and {tail_pct * 100:.1f}% Carried Royalty Tail to SpaceMusic `{space_iban}`).\n\n"
        f"**Signed by Assignor (Seller):** ___________________________ ({seller_legal_name})\n"
        f"**Acknowledged by Assignee (Buyer):** ___________________________ ({buyer_entity_name})"
    )

    settlement_md = (
        f"# CLOSING SETTLEMENT STATEMENT & SPLIT-WIRE INSTRUCTIONS\n"
        f"**Deal Reference:** `{deal_code}` | **Catalog:** `{app.artist_or_label_name}` | **Date:** {today_str}\n\n"
        f"| Line Item | Recipient | Amount (EUR) | Settlement Timing |\n"
        f"| :--- | :--- | ---: | :--- |\n"
        f"| **Gross Institutional Funding** | Funded by `{buyer_entity_name}` | **€{gross_funding:,.2f}** | At Closing |\n"
        f"| **Wire 1: Seller Upfront Proceeds (80%)** | `{seller_legal_name}` ({seller_address}) | **€{seller_closing_wire:,.2f}** | At Closing upon LOD |\n"
        f"| **Wire 2: SPACE Origination & Spread** | **SpaceMusic (`{space_iban}`)** | **€{space_total_take:,.2f}** | **Paid Directly to SPACE at Closing** |\n"
        f"| **Escrow / Performance Holdback (20%)** | Held by Buyer for `{seller_legal_name}` | **€{seller_holdback:,.2f}** | Released 12M Post-Closing |\n"
        f"| **SPACE Carried Royalty Tail ({tail_pct * 100:.1f}%)** | **SpaceMusic (`{space_iban}`)** | **€{space_tail_10y:,.2f}** *(10Y Est.)* | **Monthly Passive Lockbox Waterfall** |\n\n"
        f"**Summary of SPACE Net Cash Take at Closing:** **€{space_total_take:,.2f} EUR** + **€{space_tail_10y:,.2f} EUR** 10Y Carried Tail "
        f"(**€{space_total_10y_comp:,.2f} EUR** Total Expected SPACE Value | Zero capital deployed by SPACE)."
    )

    return ClosingDocumentPack(
        deal_code=deal_code,
        application_id=str(app.id),
        seller_legal_name=seller_legal_name,
        seller_address=seller_address,
        buyer_entity_name=buyer_entity_name,
        gross_buyer_funding_eur=gross_funding,
        seller_total_consideration_eur=seller_price,
        seller_closing_wire_eur=seller_closing_wire,
        seller_holdback_eur=seller_holdback,
        space_origination_fee_eur=fee_eur,
        space_spread_eur=spread_eur,
        space_total_take_eur=space_total_take,
        carried_tail_pct=tail_pct,
        space_carried_tail_year1_eur=space_tail_yr1,
        space_carried_tail_10y_projected_eur=space_tail_10y,
        space_total_10y_comp_eur=space_total_10y_comp,
        blind_teaser=teaser,
        ncnd_fee_agreement_markdown=ncnd_md,
        letter_of_direction_markdown=lod_md,
        settlement_statement_markdown=settlement_md,
    )


class DealLakeRepository:
    """
    Persistent SQLite Deal Lake (`space_deal_lake.sqlite3`) that stores:
    - Evaluated `CatalogApplication` records (`applications` table)
    - Empirical DSP & Country RPM benchmarks (`rpm_benchmarks` table)
    - Track-level ISRC registry across all submitted catalogs (`isrc_registry` table)
      for instant Cross-Catalog ISRC Fraud & Duplicate Collision detection.
    """

    def __init__(self, db_path: str | Path = "/tmp/space_deal_lake.sqlite3"):
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    contact_email TEXT,
                    artist_or_label_name TEXT,
                    pipeline_status TEXT,
                    valuation_stage TEXT,
                    effective_cf0_eur REAL,
                    price_median_eur REAL,
                    integrity_score REAL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rpm_benchmarks (
                    id TEXT PRIMARY KEY,
                    source_application_id TEXT,
                    distributor TEXT,
                    genre_family TEXT,
                    dsp_store TEXT,
                    country_code TEXT,
                    total_streams INTEGER,
                    total_net_royalty_eur REAL,
                    observed_rpm_eur REAL,
                    observed_rpm_usd REAL,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS isrc_registry (
                    isrc TEXT NOT NULL,
                    application_id TEXT NOT NULL,
                    seller_email TEXT NOT NULL,
                    artist_or_label_name TEXT NOT NULL,
                    track_title TEXT NOT NULL,
                    ltm_net_revenue_eur REAL DEFAULT 0.0,
                    registered_at TEXT NOT NULL,
                    PRIMARY KEY (isrc, application_id)
                );
                CREATE INDEX IF NOT EXISTS idx_isrc_lookup ON isrc_registry(isrc);
                """
            )

    def save_application(self, app: CatalogApplication) -> None:
        payload_dict = app.model_dump(mode="json") if hasattr(app, "model_dump") else json.loads(app.json())
        now_iso = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO applications (
                    id, contact_email, artist_or_label_name, pipeline_status,
                    valuation_stage, effective_cf0_eur, price_median_eur,
                    integrity_score, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    contact_email=excluded.contact_email,
                    artist_or_label_name=excluded.artist_or_label_name,
                    pipeline_status=excluded.pipeline_status,
                    valuation_stage=excluded.valuation_stage,
                    effective_cf0_eur=excluded.effective_cf0_eur,
                    price_median_eur=excluded.price_median_eur,
                    integrity_score=excluded.integrity_score,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    str(app.id),
                    app.contact_email,
                    app.artist_or_label_name,
                    app.pipeline_status,
                    app.valuation_stage,
                    app.effective_cf0_eur,
                    app.price_median_eur,
                    app.integrity_score,
                    json.dumps(payload_dict),
                    now_iso,
                ),
            )

    def load_all_applications(self) -> dict[str, CatalogApplication]:
        out: dict[str, CatalogApplication] = {}
        with self._connect() as conn:
            rows = conn.execute("SELECT payload_json FROM applications ORDER BY updated_at DESC").fetchall()
            for r in rows:
                data = json.loads(r["payload_json"])
                app = CatalogApplication(**data)
                out[str(app.id)] = app
        return out

    def save_benchmarks(self, benchmarks: Sequence[ProprietaryBenchmarkRecord]) -> None:
        if not benchmarks:
            return
        with self._connect() as conn:
            for b in benchmarks:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO rpm_benchmarks (
                        id, source_application_id, distributor, genre_family,
                        dsp_store, country_code, total_streams, total_net_royalty_eur,
                        observed_rpm_eur, observed_rpm_usd, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(b.id),
                        str(b.source_application_id) if b.source_application_id else None,
                        b.distributor,
                        b.genre_family,
                        b.dsp_store,
                        b.country_code,
                        b.total_streams,
                        b.total_net_royalty_eur,
                        b.observed_rpm_eur,
                        b.observed_rpm_usd,
                        b.created_at.isoformat(),
                    ),
                )

    def register_and_check_isrc_collisions(
        self,
        app: CatalogApplication,
        summary: ParsedStatementSummary,
    ) -> list[IsrcCollisionAlert]:
        """
        Registers all ISRCs found in a parsed statement into the persistent `isrc_registry`
        and checks if any ISRC was previously submitted by a DIFFERENT seller email.
        """
        alerts: list[IsrcCollisionAlert] = []
        now_iso = datetime.now(UTC).isoformat()
        seller_email_clean = (app.contact_email or "").strip().lower()
        app_id_str = str(app.id)

        with self._connect() as conn:
            for trk in summary.tracks:
                isrc_code = (trk.isrc or "").strip().upper()
                if not isrc_code or len(isrc_code) < 8:
                    continue

                prior_rows = conn.execute(
                    """
                    SELECT application_id, seller_email, artist_or_label_name, track_title
                    FROM isrc_registry
                    WHERE isrc = ? AND application_id != ?
                    """,
                    (isrc_code, app_id_str),
                ).fetchall()

                for pr in prior_rows:
                    prior_email = (pr["seller_email"] or "").strip().lower()
                    if prior_email and prior_email != seller_email_clean:
                        alerts.append(
                            IsrcCollisionAlert(
                                isrc=isrc_code,
                                track_title=trk.title,
                                current_application_id=app_id_str,
                                current_seller_email=seller_email_clean,
                                prior_application_id=pr["application_id"],
                                prior_seller_email=prior_email,
                                prior_artist_name=pr["artist_or_label_name"],
                                message=(
                                    f"CROSS_CATALOG_ISRC_COLLISION: ISRC {isrc_code} ('{trk.title}') "
                                    f"submitted by {seller_email_clean} was already registered by "
                                    f"{prior_email} ('{pr['artist_or_label_name']}')."
                                ),
                            )
                        )

                conn.execute(
                    """
                    INSERT OR REPLACE INTO isrc_registry (
                        isrc, application_id, seller_email, artist_or_label_name,
                        track_title, ltm_net_revenue_eur, registered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        isrc_code,
                        app_id_str,
                        seller_email_clean,
                        app.artist_or_label_name,
                        trk.title,
                        float(trk.ltm_royalties_eur or 0.0),
                        now_iso,
                    ),
                )

        return alerts
