"""
FastAPI Routes for SPACE Catalog Review (`services/spacemusic/routes.py`)

Endpoints:
- `POST /webhooks/typeform`: Ingests Typeform `xzx5SBJb` ("SPACE catalog review") payloads,
  runs Stage 1 valuation & DD triage (or immediately executes Stage 2 if `statement_attachments` /
  `raw_statement_csv` are uploaded directly inside Typeform 2.0), generates reply draft, and stores in DB.
- `GET /catalog-review/{application_id}/instant-status`: Typeform 2.0 Redirect / Instant Valuation
  Status endpoint returning indicative/verified valuation range, forensic integrity score,
  cohort decay tier, distributor export guide, Down-Funnel monetization options, and Scrive e-sign status.
- `POST /catalog-review/evaluate`: Direct Stage 1 or Stage 2 evaluation endpoint accepting
  structured catalog data + optional raw distributor CSV/TSV statement text.
- `POST /catalog-review/{application_id}/statements`: Attaches raw distributor CSV/TSV statements
  to an existing Typeform application, upgrading it to `STAGE_2_STATEMENT_VERIFIED` and
  storing empirical RPM benchmarks in SPACE's proprietary database.
- `POST /catalog-review/{application_id}/closing-pack`: Generates the 4-part Closing Document Pack
  including SPACE's 5%–10% Carried Royalty Tail (`carried_tail_pct`).
- `POST /catalog-review/{application_id}/scrive/envelope` & `POST /webhooks/scrive`:
  Creates and executes Scrive e-signature envelopes with cryptographic SHA-256 & HMAC verification.
- `GET /catalog-review/{application_id}/monetization-plan` &
  `POST /catalog-review/{application_id}/forensic-certificate`:
  "Sov+" Down-Funnel Monetization Router & $299 Forensic Audit Certificate generator.
- `POST /catalog-review/{application_id}/fintech/split-escrow` &
  `POST /catalog-review/{application_id}/fintech/lockbox-distribution`:
  Cent-exact Multi-Currency Split-Escrow & Virtual Lockbox Monthly Waterfall Ledger.
- `GET /catalog-review/applications`: Lists evaluated catalog applications with pipeline status.
- `GET /catalog-review/benchmarks`: Returns aggregated empirical RPM benchmarks across DSPs & countries.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Body, Header, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from services.valuation.engine import (
    CatalogValuationInput,
    CatalogValuationOutput,
    SpaceValuationEngine,
)
from services.valuation.statement_parser import (
    ParsedStatementSummary,
    parse_statement_csv,
)

from .buyer_router import (
    InstitutionalRoutingReport,
    route_catalog_to_institutional_buyers,
)
from .closing_pack import (
    BlindDealTeaser,
    ClosingDocumentPack,
    DealLakeRepository,
    IsrcCollisionAlert,
    generate_blind_deal_teaser,
    generate_closing_document_pack,
)
from .fintech_escrow import (
    EscrowProviderRail,
    FintechEscrowLedger,
    MonthlyLockboxDistribution,
    SplitEscrowSettlementInstruction,
)
from .inbox_ingestor import (
    AutonomousStage2UnderwritingResult,
    InboundAttachmentPayload,
    InboundEmailStatementWebhook,
    _extract_csv_texts_from_attachments,
    ingest_inbound_email_statements,
    parse_multi_attachment_statements,
)
from .models import CatalogApplication, ProprietaryBenchmarkRecord, ReplyDraft
from .monetization_engine import (
    DownFunnelMonetizationPlan,
    ForensicAuditCertificate,
    build_down_funnel_monetization_plan,
    generate_forensic_audit_certificate,
)
from .scrive_signer import (
    ScriveExecutionEngine,
    ScriveSignatureEnvelope,
    SignatoryRole,
)
from .seo_calculator_widget import (
    InteractiveCalculatorTeaserRequest,
    InteractiveCalculatorTeaserResponse,
    evaluate_interactive_calculator_teaser,
    render_embeddable_calculator_html,
    render_embeddable_calculator_widget_js,
)
from .seo_geo_data import (
    LANDING_PAGES_BY_SLUG,
    SEO_PAGE_METADATA_OVERRIDES,
    build_page_jsonld_schemas,
    generate_cloudflare_redirects,
    get_backlink_outreach_kit,
    get_brand_facts_payload,
    get_indie_catalog_benchmark_report_2026,
    render_benchmark_report_html,
    render_landing_page_html,
    render_llms_full_txt,
    render_llms_txt,
    render_pricing_md,
    render_sitemap_xml,
    resolve_canonical_redirect,
)
from .typeform_adapter import (
    application_to_valuation_input,
    generate_reply_draft,
    parse_typeform_csv_export,
    parse_typeform_webhook_payload,
)
from .zero_touch_stage1 import (
    ImpliedRevenueCrossCheck,
    LiveSpotifyArtistSnapshot,
    execute_zero_touch_stage1,
    get_distributor_export_guide,
)

router = APIRouter()
logger = structlog.get_logger(__name__)

# In-memory store backed by SQLite DealLakeRepository so state persists across restarts
_APPLICATIONS_STORE: dict[uuid.UUID, CatalogApplication] = {}
_BENCHMARKS_STORE: list[ProprietaryBenchmarkRecord] = []
_deal_lake = DealLakeRepository()
_scrive_engine = ScriveExecutionEngine()
_fintech_ledger = FintechEscrowLedger()

_engine = SpaceValuationEngine()


class ClosingPackRequest(BaseModel):
    seller_legal_name: str
    seller_address: str
    buyer_entity_name: str = "Designated Institutional Buyer Affiliate"
    seller_agreed_price_eur: float | None = None
    buyer_gross_funding_eur: float | None = None
    origination_fee_pct: float = 0.06
    holdback_pct: float = 0.20
    carried_tail_pct: float = 0.075
    space_iban: str = "SE00 0000 0000 0000 0000 0000 (SPACE Corporate Treasury)"


class ScriveEnvelopeRequest(BaseModel):
    seller_legal_name: str
    seller_address: str
    buyer_entity_name: str = "Designated Institutional Buyer Affiliate"
    buyer_email: str = "acquisitions@institutional-buyer.io"
    seller_agreed_price_eur: float | None = None
    origination_fee_pct: float = 0.06
    holdback_pct: float = 0.20
    carried_tail_pct: float = 0.075


class ScriveSignActionRequest(BaseModel):
    signer_role: SignatoryRole = SignatoryRole.SELLER
    signer_email: str | None = None
    ip_address: str = "127.0.0.1"
    expected_document_sha256: str | None = None


class SplitEscrowRequest(BaseModel):
    seller_legal_name: str
    seller_iban: str
    buyer_entity_name: str = "Designated Institutional Buyer Affiliate"
    seller_agreed_price_eur: float | None = None
    buyer_gross_funding_eur: float | None = None
    origination_fee_pct: float = 0.06
    holdback_pct: float = 0.20
    carried_tail_pct: float = 0.075
    settlement_currency: str = "EUR"
    provider_rail: EscrowProviderRail = EscrowProviderRail.AIRWALLEX_VIRTUAL_LOCKBOX
    space_treasury_iban: str = "SE00 0000 0000 0000 0000 0000 (SPACE Corporate Treasury)"
    idempotency_key: str | None = None


class LockboxMonthlyDistributionRequest(BaseModel):
    period_month: str
    gross_royalty_inflow: float
    seller_holdback_escrow: float = 0.0
    carried_tail_pct: float = 0.075
    is_month_12_holdback_check: bool = False
    currency: str = "EUR"
    idempotency_key: str | None = None


class InstantValuationStatusResponse(BaseModel):
    application_id: uuid.UUID
    deal_code: str
    artist_or_label_name: str
    pipeline_status: str
    valuation_stage: str
    statements_verified: bool
    effective_cf0_eur: float
    price_low_eur: float
    price_median_eur: float
    price_high_eur: float
    implied_multiple_median: float
    integrity_score: float
    valuation_confidence: float
    distributor_export_guide: str
    monetization_plan: DownFunnelMonetizationPlan
    scrive_envelopes: list[ScriveSignatureEnvelope] = Field(default_factory=list)


class DirectEvaluationRequest(BaseModel):
    catalog: CatalogValuationInput
    raw_statement_csv: str | None = None


class StatementUploadRequest(BaseModel):
    raw_statement_csv: str
    default_currency: str = "USD"
    artist_or_label_override: str | None = None
    listen_url_override: str | None = None


class TypeformCsvImportRequest(BaseModel):
    csv_content: str
    skip_test_rows: bool = True


class ApplicationEvaluationResponse(BaseModel):
    application_id: uuid.UUID
    pipeline_status: str
    valuation_stage: str
    autonomous_decision: str | None = None
    valuation: CatalogValuationOutput
    reply_draft: ReplyDraft
    statement_summary: ParsedStatementSummary | None = None
    implied_revenue_crosscheck: ImpliedRevenueCrossCheck | None = None
    distributor_export_guide: str | None = None
    institutional_routing: InstitutionalRoutingReport | None = None
    blind_deal_teaser: BlindDealTeaser | None = None
    isrc_collision_alerts: list[IsrcCollisionAlert] = Field(default_factory=list)
    monetization_plan: DownFunnelMonetizationPlan | None = None


@router.post(
    "/webhooks/typeform",
    response_model=ApplicationEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def handle_typeform_webhook(payload: Annotated[dict[str, Any], Body()]):
    """
    Receives a Typeform webhook (`xzx5SBJb` - SPACE catalog review), parses all fields,
    and executes either:
    - **Typeform 2.0 Direct Statement Upload (`STAGE_2_STATEMENT_VERIFIED`)** when the payload
      includes `raw_statement_csv` or `statement_attachments` (`.csv` / `.tsv` / `.xlsx` / `.zip`),
      running all 11 forensics checks, cross-catalog ISRC collision checks, and institutional routing
      in a single atomic request; OR
    - **Zero-Touch Stage 1 Pipeline (`STAGE_1_INDICATIVE`)** with live Spotify enrichment,
      mathematical stream-to-revenue cross-check, and distributor-specific export guide injection.
    """
    app_row = parse_typeform_webhook_payload(payload)
    raw_spotify = payload.get("raw_spotify_payload")
    snap_dict = payload.get("spotify_snapshot")
    snap = LiveSpotifyArtistSnapshot(**snap_dict) if isinstance(snap_dict, dict) else None

    zt_res = execute_zero_touch_stage1(
        app_row,
        engine=_engine,
        spotify_snapshot=snap,
        raw_spotify_payload=raw_spotify if isinstance(raw_spotify, dict) else None,
    )

    # Check if Typeform 2.0 submission includes direct statement files
    direct_csv_text = payload.get("raw_statement_csv")
    raw_attachments = payload.get("statement_attachments") or []
    parsed_attachments: list[InboundAttachmentPayload] = []
    if isinstance(raw_attachments, list):
        for item in raw_attachments:
            if isinstance(item, dict):
                parsed_attachments.append(InboundAttachmentPayload(**item))

    if direct_csv_text and isinstance(direct_csv_text, str) and direct_csv_text.strip():
        parsed_attachments.append(
            InboundAttachmentPayload(filename="typeform_upload.csv", content_text=direct_csv_text)
        )

    stmt_summary: ParsedStatementSummary | None = None
    routing: InstitutionalRoutingReport | None = None
    blind_teaser: BlindDealTeaser | None = None
    collision_alerts: list[IsrcCollisionAlert] = []
    final_valuation = zt_res.valuation
    final_reply = zt_res.reply_draft
    final_decision = zt_res.autonomous_decision

    if parsed_attachments:
        file_pairs = _extract_csv_texts_from_attachments(parsed_attachments)
        stmt_summary = parse_multi_attachment_statements(
            file_pairs, default_currency=app_row.declared_currency
        )
        if stmt_summary.row_count > 0:
            app_row.statements_verified = True
            if not app_row.distributor_or_admin or app_row.distributor_or_admin == "Standard CSV":
                app_row.distributor_or_admin = stmt_summary.detected_distributor

            val_input = application_to_valuation_input(app_row)
            val_input.statements_verified = True
            val_input.monthly_history = stmt_summary.monthly_history
            val_input.tracks = stmt_summary.tracks
            val_input.dsp_share = stmt_summary.dsp_share
            val_input.country_share = stmt_summary.country_share

            final_valuation = _engine.evaluate(val_input)
            final_reply = generate_reply_draft(app_row, final_valuation)
            final_decision = "STAGE_2_INSTANT_UNDERWRITING_COMPLETE"

            app_row.pipeline_status = final_valuation.pipeline_status
            app_row.valuation_stage = final_valuation.valuation_stage
            app_row.effective_cf0_eur = final_valuation.baseline.effective_cf0_eur
            app_row.price_low_eur = final_valuation.price_low_eur
            app_row.price_median_eur = final_valuation.price_median_eur
            app_row.price_high_eur = final_valuation.price_high_eur
            app_row.implied_multiple_median = final_valuation.implied_ltm_multiple_median
            app_row.discount_rate = final_valuation.discount_rate.total_discount_rate
            app_row.integrity_score = final_valuation.integrity_score
            app_row.valuation_confidence = final_valuation.valuation_confidence
            app_row.valuation_report_json = (
                final_valuation.model_dump()
                if hasattr(final_valuation, "model_dump")
                else final_valuation.dict()
            )
            app_row.draft_reply_subject = final_reply.subject
            app_row.draft_reply_body = final_reply.body

            for b in stmt_summary.benchmarks:
                _BENCHMARKS_STORE.append(
                    ProprietaryBenchmarkRecord(
                        source_application_id=app_row.id,
                        distributor=stmt_summary.detected_distributor,
                        genre_family=final_valuation.genre_family.value,
                        dsp_store=b.dsp_store,
                        country_code=b.country_code,
                        total_streams=b.total_streams,
                        total_net_royalty_eur=b.total_net_royalty_eur,
                        observed_rpm_eur=b.observed_rpm_eur,
                        observed_rpm_usd=b.observed_rpm_usd,
                    )
                )

            routing = route_catalog_to_institutional_buyers(app_row, final_valuation)
            blind_teaser = generate_blind_deal_teaser(app_row, final_valuation, routing=routing)
            collision_alerts = _deal_lake.register_and_check_isrc_collisions(app_row, stmt_summary)

    monetization_plan = build_down_funnel_monetization_plan(app_row, final_valuation)
    _APPLICATIONS_STORE[app_row.id] = app_row
    _deal_lake.save_application(app_row)

    logger.info(
        "typeform_application_evaluated",
        application_id=str(app_row.id),
        artist=app_row.artist_or_label_name,
        pipeline_status=app_row.pipeline_status,
        valuation_stage=app_row.valuation_stage,
        autonomous_decision=final_decision,
        price_median_eur=app_row.price_median_eur,
    )

    return ApplicationEvaluationResponse(
        application_id=app_row.id,
        pipeline_status=app_row.pipeline_status,
        valuation_stage=app_row.valuation_stage,
        autonomous_decision=final_decision,
        valuation=final_valuation,
        reply_draft=final_reply,
        statement_summary=stmt_summary,
        implied_revenue_crosscheck=zt_res.implied_revenue_crosscheck,
        distributor_export_guide=zt_res.distributor_export_guide,
        institutional_routing=routing,
        blind_deal_teaser=blind_teaser,
        isrc_collision_alerts=collision_alerts,
        monetization_plan=monetization_plan,
    )


@router.get(
    "/catalog-review/{application_id}/instant-status",
    response_model=InstantValuationStatusResponse,
)
async def get_instant_valuation_status(application_id: uuid.UUID):
    """
    Typeform 2.0 Redirect / Instant Valuation Status endpoint:
    Returns the real-time underwriting status, indicative or verified valuation range,
    forensic integrity score, distributor export guide, Down-Funnel monetization plan,
    and active Scrive e-signature envelopes for the seller's instant dashboard.
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    val_input = application_to_valuation_input(app_row)
    valuation = _engine.evaluate(val_input)
    mon_plan = build_down_funnel_monetization_plan(app_row, valuation)
    envelopes = _scrive_engine.list_envelopes_for_application(str(app_row.id))

    return InstantValuationStatusResponse(
        application_id=app_row.id,
        deal_code=mon_plan.deal_code,
        artist_or_label_name=app_row.artist_or_label_name,
        pipeline_status=app_row.pipeline_status,
        valuation_stage=app_row.valuation_stage,
        statements_verified=app_row.statements_verified,
        effective_cf0_eur=round(float(app_row.effective_cf0_eur or valuation.baseline.effective_cf0_eur), 2),
        price_low_eur=round(float(app_row.price_low_eur or valuation.price_low_eur), 2),
        price_median_eur=round(float(app_row.price_median_eur or valuation.price_median_eur), 2),
        price_high_eur=round(float(app_row.price_high_eur or valuation.price_high_eur), 2),
        implied_multiple_median=round(
            float(app_row.implied_multiple_median or valuation.implied_ltm_multiple_median), 2
        ),
        integrity_score=round(float(app_row.integrity_score or valuation.integrity_score), 1),
        valuation_confidence=round(float(app_row.valuation_confidence or valuation.valuation_confidence), 2),
        distributor_export_guide=get_distributor_export_guide(app_row.distributor_or_admin),
        monetization_plan=mon_plan,
        scrive_envelopes=envelopes,
    )


@router.post(
    "/catalog-review/evaluate",
    response_model=ApplicationEvaluationResponse,
)
async def evaluate_catalog_direct(req: DirectEvaluationRequest):
    """
    Evaluates a catalog directly from structured input and optional raw CSV/TSV distributor statement.
    Automatically enriches SPACE's proprietary RPM benchmark store when a CSV statement is supplied.
    """
    val_input = req.catalog
    stmt_summary: ParsedStatementSummary | None = None

    if req.raw_statement_csv:
        stmt_summary = parse_statement_csv(
            req.raw_statement_csv,
            default_currency=val_input.declared_currency,
        )
        if stmt_summary.row_count > 0:
            val_input.statements_verified = True
            val_input.monthly_history = stmt_summary.monthly_history
            if not val_input.tracks:
                val_input.tracks = stmt_summary.tracks
            val_input.dsp_share = stmt_summary.dsp_share
            val_input.country_share = stmt_summary.country_share
            if not val_input.distributor_or_admin:
                val_input.distributor_or_admin = stmt_summary.detected_distributor

    valuation = _engine.evaluate(val_input)

    app_row = CatalogApplication(
        inquiry_route=val_input.representation_type,
        contact_name=val_input.applicant_name or "",
        contact_email=val_input.applicant_email or "",
        artist_or_label_name=val_input.artist_or_label_name,
        listen_url=val_input.listen_url,
        spotify_artist_id=val_input.spotify_artist_id,
        rights_scope=val_input.rights_scope.value,
        owner_authorized=val_input.owner_authorized,
        declared_ltm_amount=val_input.declared_ltm_amount,
        declared_currency=val_input.declared_currency,
        royalty_basis=val_input.royalty_basis.value,
        distributor_or_admin=val_input.distributor_or_admin,
        rights_notes=val_input.notes,
        statements_verified=val_input.statements_verified,
        pipeline_status=valuation.pipeline_status,
        valuation_stage=valuation.valuation_stage,
        effective_cf0_eur=valuation.baseline.effective_cf0_eur,
        price_low_eur=valuation.price_low_eur,
        price_median_eur=valuation.price_median_eur,
        price_high_eur=valuation.price_high_eur,
        implied_multiple_median=valuation.implied_ltm_multiple_median,
        discount_rate=valuation.discount_rate.total_discount_rate,
        integrity_score=valuation.integrity_score,
        valuation_confidence=valuation.valuation_confidence,
        valuation_report_json=valuation.dict() if hasattr(valuation, "dict") else valuation.model_dump(),
    )

    reply_draft = generate_reply_draft(app_row, valuation)
    app_row.draft_reply_subject = reply_draft.subject
    app_row.draft_reply_body = reply_draft.body
    _APPLICATIONS_STORE[app_row.id] = app_row
    _deal_lake.save_application(app_row)

    if stmt_summary and stmt_summary.benchmarks:
        for b in stmt_summary.benchmarks:
            _BENCHMARKS_STORE.append(
                ProprietaryBenchmarkRecord(
                    source_application_id=app_row.id,
                    distributor=stmt_summary.detected_distributor,
                    genre_family=valuation.genre_family.value,
                    dsp_store=b.dsp_store,
                    country_code=b.country_code,
                    total_streams=b.total_streams,
                    total_net_royalty_eur=b.total_net_royalty_eur,
                    observed_rpm_eur=b.observed_rpm_eur,
                    observed_rpm_usd=b.observed_rpm_usd,
                )
            )

    mon_plan = build_down_funnel_monetization_plan(app_row, valuation)

    return ApplicationEvaluationResponse(
        application_id=app_row.id,
        pipeline_status=valuation.pipeline_status,
        valuation_stage=valuation.valuation_stage,
        valuation=valuation,
        reply_draft=reply_draft,
        statement_summary=stmt_summary,
        monetization_plan=mon_plan,
    )


@router.post(
    "/catalog-review/{application_id}/statements",
    response_model=ApplicationEvaluationResponse,
)
async def attach_statements_to_application(
    application_id: uuid.UUID,
    req: StatementUploadRequest,
):
    """
    Upgrades an existing Stage 1 application to Stage 2 (`STAGE_2_STATEMENT_VERIFIED`)
    by parsing uploaded distributor CSV/TSV statements and re-running the DCF + Forensics engine.
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if req.artist_or_label_override:
        app_row.artist_or_label_name = req.artist_or_label_override
    if req.listen_url_override:
        app_row.listen_url = req.listen_url_override

    stmt_summary = parse_statement_csv(
        req.raw_statement_csv,
        default_currency=req.default_currency or app_row.declared_currency,
    )
    if stmt_summary.row_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded statement CSV/TSV contained no valid royalty rows.",
        )

    app_row.statements_verified = True
    val_input = application_to_valuation_input(app_row)
    val_input.statements_verified = True
    val_input.monthly_history = stmt_summary.monthly_history
    val_input.tracks = stmt_summary.tracks
    val_input.dsp_share = stmt_summary.dsp_share
    val_input.country_share = stmt_summary.country_share

    valuation = _engine.evaluate(val_input)
    reply_draft = generate_reply_draft(app_row, valuation)

    app_row.pipeline_status = valuation.pipeline_status
    app_row.valuation_stage = valuation.valuation_stage
    app_row.effective_cf0_eur = valuation.baseline.effective_cf0_eur
    app_row.price_low_eur = valuation.price_low_eur
    app_row.price_median_eur = valuation.price_median_eur
    app_row.price_high_eur = valuation.price_high_eur
    app_row.implied_multiple_median = valuation.implied_ltm_multiple_median
    app_row.discount_rate = valuation.discount_rate.total_discount_rate
    app_row.integrity_score = valuation.integrity_score
    app_row.valuation_confidence = valuation.valuation_confidence
    app_row.valuation_report_json = valuation.dict() if hasattr(valuation, "dict") else valuation.model_dump()
    app_row.draft_reply_subject = reply_draft.subject
    app_row.draft_reply_body = reply_draft.body
    app_row.updated_at = datetime.now(UTC).replace(tzinfo=None)

    for b in stmt_summary.benchmarks:
        _BENCHMARKS_STORE.append(
            ProprietaryBenchmarkRecord(
                source_application_id=app_row.id,
                distributor=stmt_summary.detected_distributor,
                genre_family=valuation.genre_family.value,
                dsp_store=b.dsp_store,
                country_code=b.country_code,
                total_streams=b.total_streams,
                total_net_royalty_eur=b.total_net_royalty_eur,
                observed_rpm_eur=b.observed_rpm_eur,
                observed_rpm_usd=b.observed_rpm_usd,
            )
        )

    routing = route_catalog_to_institutional_buyers(app_row, valuation)
    blind_teaser = generate_blind_deal_teaser(app_row, valuation, routing=routing)
    collision_alerts = _deal_lake.register_and_check_isrc_collisions(app_row, stmt_summary)
    mon_plan = build_down_funnel_monetization_plan(app_row, valuation)
    _deal_lake.save_application(app_row)

    return ApplicationEvaluationResponse(
        application_id=app_row.id,
        pipeline_status=valuation.pipeline_status,
        valuation_stage=valuation.valuation_stage,
        valuation=valuation,
        reply_draft=reply_draft,
        statement_summary=stmt_summary,
        institutional_routing=routing,
        blind_deal_teaser=blind_teaser,
        isrc_collision_alerts=collision_alerts,
        monetization_plan=mon_plan,
    )


@router.post(
    "/webhooks/inbound-email",
    response_model=AutonomousStage2UnderwritingResult,
)
async def handle_inbound_email_statements(webhook: InboundEmailStatementWebhook):
    """
    Autonomous Inbox-to-Underwriting endpoint:
    When an artist replies to `hello@spacemusic.io` with attached `.csv` / `.tsv` / `.zip`
    royalty statements, matches their application, merges and parses all statements,
    upgrades the valuation to `STAGE_2_STATEMENT_VERIFIED`, routes the catalog to
    SPACE's 8 institutional buyers, and returns both the Seller Offer Draft and Slack Deal Card.
    """
    res = ingest_inbound_email_statements(
        webhook,
        applications_store=_APPLICATIONS_STORE,
        engine=_engine,
    )
    for b in res.statement_summary.benchmarks:
        _BENCHMARKS_STORE.append(
            ProprietaryBenchmarkRecord(
                source_application_id=uuid.UUID(res.application_id),
                distributor=res.detected_distributor,
                genre_family=res.valuation.genre_family.value,
                dsp_store=b.dsp_store,
                country_code=b.country_code,
                total_streams=b.total_streams,
                total_net_royalty_eur=b.total_net_royalty_eur,
                observed_rpm_eur=b.observed_rpm_eur,
                observed_rpm_usd=b.observed_rpm_usd,
            )
        )
    return res


@router.get(
    "/catalog-review/{application_id}/buyer-routing",
    response_model=InstitutionalRoutingReport,
)
async def get_application_buyer_routing(application_id: uuid.UUID):
    """
    Returns the ranked Institutional Buy-Box matches and Markdown Underwriting Memo
    for an evaluated application.
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    val_input = application_to_valuation_input(app_row)
    valuation = _engine.evaluate(val_input)
    return route_catalog_to_institutional_buyers(app_row, valuation)


@router.post(
    "/catalog-review/{application_id}/closing-pack",
    response_model=ClosingDocumentPack,
)
async def create_application_closing_pack(
    application_id: uuid.UUID,
    req: ClosingPackRequest,
):
    """
    Generates the 4-part Closing Document Pack for an evaluated catalog:
    1. Blind Deal Teaser (`SPC-XXXXXX`)
    2. Institutional Non-Circumvention & Origination Fee Agreement (`NCND`) + Carried Royalty Tail
    3. Irrevocable Distributor Letter of Direction (`LOD`)
    4. Closing Settlement Statement & Split-Wire Instructions
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    val_input = application_to_valuation_input(app_row)
    valuation = _engine.evaluate(val_input)
    return generate_closing_document_pack(
        app_row,
        valuation,
        seller_legal_name=req.seller_legal_name,
        seller_address=req.seller_address,
        buyer_entity_name=req.buyer_entity_name,
        seller_agreed_price_eur=req.seller_agreed_price_eur,
        buyer_gross_funding_eur=req.buyer_gross_funding_eur,
        origination_fee_pct=req.origination_fee_pct,
        holdback_pct=req.holdback_pct,
        carried_tail_pct=req.carried_tail_pct,
        space_iban=req.space_iban,
    )


@router.post(
    "/catalog-review/{application_id}/scrive/envelope",
    response_model=ScriveSignatureEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def create_scrive_closing_envelope(
    application_id: uuid.UUID,
    req: ScriveEnvelopeRequest,
):
    """
    Generates the Closing Document Pack for an application and dispatches a multi-party
    Scrive e-signature envelope (`SENT_FOR_SIGNATURE`) with a locked SHA-256 document hash.
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    val_input = application_to_valuation_input(app_row)
    valuation = _engine.evaluate(val_input)
    pack = generate_closing_document_pack(
        app_row,
        valuation,
        seller_legal_name=req.seller_legal_name,
        seller_address=req.seller_address,
        buyer_entity_name=req.buyer_entity_name,
        seller_agreed_price_eur=req.seller_agreed_price_eur,
        origination_fee_pct=req.origination_fee_pct,
        holdback_pct=req.holdback_pct,
        carried_tail_pct=req.carried_tail_pct,
    )
    combined_doc = (
        f"{pack.ncnd_fee_agreement_markdown}\n\n---\n\n"
        f"{pack.letter_of_direction_markdown}\n\n---\n\n"
        f"{pack.settlement_statement_markdown}"
    )
    return _scrive_engine.create_and_send_closing_envelope(
        deal_code=pack.deal_code,
        application_id=str(app_row.id),
        title=f"SPACE Catalog Acquisition & LOD Pack — {app_row.artist_or_label_name}",
        document_markdown=combined_doc,
        seller_name=req.seller_legal_name,
        seller_email=app_row.contact_email,
        buyer_name=req.buyer_entity_name,
        buyer_email=req.buyer_email,
        buyer_company=req.buyer_entity_name,
    )


@router.post(
    "/catalog-review/scrive/{envelope_id}/sign",
    response_model=ScriveSignatureEnvelope,
)
async def sign_scrive_envelope_endpoint(
    envelope_id: str,
    req: ScriveSignActionRequest,
):
    """
    Records a party signature (`SELLER` or `BUYER`) on an active Scrive envelope,
    enforcing party order and SHA-256 integrity checks.
    """
    try:
        return _scrive_engine.record_signature(
            envelope_id,
            signer_role=req.signer_role,
            signer_email=req.signer_email,
            ip_address=req.ip_address,
            expected_document_sha256=req.expected_document_sha256,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/webhooks/scrive",
    response_model=ScriveSignatureEnvelope,
)
async def handle_scrive_webhook(
    payload: Annotated[dict[str, Any], Body()],
    x_scrive_signature: str | None = Header(default=None),
):
    """
    Webhook callback receiver for Scrive e-signature events (`SELLER_SIGNED`, `COMPLETED_LOCKED`).
    Verifies HMAC-SHA256 signature (`X-Scrive-Signature`).
    """
    try:
        return _scrive_engine.process_webhook_callback(
            payload,
            signature_header=x_scrive_signature,
            require_hmac=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/catalog-review/{application_id}/monetization-plan",
    response_model=DownFunnelMonetizationPlan,
)
async def get_application_monetization_plan(application_id: uuid.UUID):
    """
    Returns the "Sov+" Down-Funnel Monetization Plan for any evaluated catalog
    (Direct M&A Syndication + Carried Tail, Automated Micro-Advance Referral,
    SPACE Managed Sub-Label & 15% Content ID Override, and $299 Forensic Audit Certificate).
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    val_input = application_to_valuation_input(app_row)
    valuation = _engine.evaluate(val_input)
    return build_down_funnel_monetization_plan(app_row, valuation)


@router.post(
    "/catalog-review/{application_id}/forensic-certificate",
    response_model=ForensicAuditCertificate,
)
async def create_forensic_audit_certificate(application_id: uuid.UUID):
    """
    Generates a SHA-256-sealed Official SPACE 11-Point Forensic Valuation & Chain-of-Title
    Audit Certificate (`$299 / €275`).
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    val_input = application_to_valuation_input(app_row)
    valuation = _engine.evaluate(val_input)
    return generate_forensic_audit_certificate(app_row, valuation)


@router.post(
    "/catalog-review/{application_id}/fintech/split-escrow",
    response_model=SplitEscrowSettlementInstruction,
)
async def create_fintech_split_escrow_instruction(
    application_id: uuid.UUID,
    req: SplitEscrowRequest,
):
    """
    Generates a cent-exact (`Decimal` + `ROUND_HALF_UP`) Multi-Currency Split-Escrow
    Settlement Instruction with idempotency protection.
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    val_input = application_to_valuation_input(app_row)
    valuation = _engine.evaluate(val_input)
    teaser = generate_blind_deal_teaser(app_row, valuation)

    seller_price = (
        req.seller_agreed_price_eur
        if req.seller_agreed_price_eur is not None
        else (app_row.price_median_eur or valuation.price_median_eur)
    )
    try:
        return _fintech_ledger.compute_split_escrow_instruction(
            deal_code=teaser.deal_code,
            application_id=str(app_row.id),
            seller_legal_name=req.seller_legal_name,
            seller_iban=req.seller_iban,
            buyer_entity_name=req.buyer_entity_name,
            seller_agreed_price_eur=seller_price,
            buyer_gross_funding_eur=req.buyer_gross_funding_eur,
            origination_fee_pct=req.origination_fee_pct,
            holdback_pct=req.holdback_pct,
            carried_tail_pct=req.carried_tail_pct,
            settlement_currency=req.settlement_currency,
            provider_rail=req.provider_rail,
            space_treasury_iban=req.space_treasury_iban,
            idempotency_key=req.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/catalog-review/{application_id}/fintech/lockbox-distribution",
    response_model=MonthlyLockboxDistribution,
)
async def execute_fintech_lockbox_distribution(
    application_id: uuid.UUID,
    req: LockboxMonthlyDistributionRequest,
):
    """
    Executes a cent-exact monthly Virtual Lockbox royalty waterfall distribution,
    splitting incoming DSP royalties between SPACE's Carried Royalty Tail and the
    Institutional Buyer, and evaluating the 12-month Seller Performance Holdback release.
    """
    app_row = _APPLICATIONS_STORE.get(application_id)
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    val_input = application_to_valuation_input(app_row)
    valuation = _engine.evaluate(val_input)
    teaser = generate_blind_deal_teaser(app_row, valuation)
    cf0 = app_row.effective_cf0_eur or valuation.baseline.effective_cf0_eur or 1.0

    try:
        return _fintech_ledger.distribute_monthly_lockbox_royalties(
            deal_code=teaser.deal_code,
            period_month=req.period_month,
            gross_royalty_inflow=req.gross_royalty_inflow,
            target_12m_baseline_cf0=cf0,
            seller_holdback_escrow=req.seller_holdback_escrow,
            carried_tail_pct=req.carried_tail_pct,
            is_month_12_holdback_check=req.is_month_12_holdback_check,
            currency=req.currency,
            idempotency_key=req.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/catalog-review/import-csv")
async def import_typeform_csv(req: TypeformCsvImportRequest):
    """
    Bulk-imports and evaluates a Typeform CSV export (`responses-xzx5SBJb-*.csv`),
    running the Zero-Touch Stage 1 pipeline across all rows and returning their
    full DCF + Forensics evaluations, autonomous routing decisions, and reply drafts.
    """
    apps = parse_typeform_csv_export(req.csv_content, skip_test_rows=req.skip_test_rows)
    results: list[ApplicationEvaluationResponse] = []
    for app_row in apps:
        zt_res = execute_zero_touch_stage1(app_row, engine=_engine)
        _APPLICATIONS_STORE[app_row.id] = app_row
        results.append(
            ApplicationEvaluationResponse(
                application_id=app_row.id,
                pipeline_status=zt_res.pipeline_status,
                valuation_stage=zt_res.valuation.valuation_stage,
                autonomous_decision=zt_res.autonomous_decision,
                valuation=zt_res.valuation,
                reply_draft=zt_res.reply_draft,
                implied_revenue_crosscheck=zt_res.implied_revenue_crosscheck,
                distributor_export_guide=zt_res.distributor_export_guide,
                monetization_plan=build_down_funnel_monetization_plan(app_row, zt_res.valuation),
            )
        )
    return results


@router.get("/catalog-review/applications")
async def list_applications():
    return [
        {
            "id": str(app.id),
            "typeform_response_id": app.typeform_response_id,
            "artist_or_label_name": app.artist_or_label_name,
            "contact_name": app.contact_name,
            "contact_email": app.contact_email,
            "inquiry_route": app.inquiry_route,
            "pipeline_status": app.pipeline_status,
            "valuation_stage": app.valuation_stage,
            "effective_cf0_eur": app.effective_cf0_eur,
            "price_low_eur": app.price_low_eur,
            "price_median_eur": app.price_median_eur,
            "price_high_eur": app.price_high_eur,
            "implied_multiple_median": app.implied_multiple_median,
            "discount_rate": app.discount_rate,
            "integrity_score": app.integrity_score,
            "created_at": app.created_at.isoformat(),
        }
        for app in sorted(_APPLICATIONS_STORE.values(), key=lambda a: a.created_at, reverse=True)
    ]


@router.get("/catalog-review/benchmarks")
async def list_proprietary_benchmarks():
    return [
        {
            "distributor": b.distributor,
            "genre_family": b.genre_family,
            "dsp_store": b.dsp_store,
            "country_code": b.country_code,
            "total_streams": b.total_streams,
            "total_net_royalty_eur": b.total_net_royalty_eur,
            "observed_rpm_eur": b.observed_rpm_eur,
            "observed_rpm_usd": b.observed_rpm_usd,
        }
        for b in _BENCHMARKS_STORE
    ]


@router.post(
    "/calculator/live-teaser",
    response_model=InteractiveCalculatorTeaserResponse,
)
async def post_calculator_live_teaser(req: InteractiveCalculatorTeaserRequest):
    return evaluate_interactive_calculator_teaser(req)


@router.get("/embed/calculator", response_class=HTMLResponse)
async def get_embed_calculator():
    return HTMLResponse(content=render_embeddable_calculator_html())


@router.get("/widget/calculator.js")
async def get_widget_calculator_js():
    return Response(
        content=render_embeddable_calculator_widget_js(),
        media_type="application/javascript",
    )


@router.get("/llms.txt", response_class=PlainTextResponse)
async def get_llms_txt():
    return PlainTextResponse(content=render_llms_txt())


@router.get("/llms-full.txt", response_class=PlainTextResponse)
async def get_llms_full_txt():
    return PlainTextResponse(content=render_llms_full_txt())


@router.get("/pricing.md", response_class=PlainTextResponse)
async def get_pricing_md():
    return PlainTextResponse(content=render_pricing_md())


@router.get("/_redirects", response_class=PlainTextResponse)
async def get_cloudflare_redirects():
    return PlainTextResponse(content=generate_cloudflare_redirects())


@router.get("/sitemap.xml")
async def get_sitemap_xml():
    return Response(content=render_sitemap_xml(), media_type="application/xml")


@router.get("/brand-facts")
async def get_brand_facts():
    return get_brand_facts_payload()


@router.get("/.well-known/brand-facts.json")
async def get_well_known_brand_facts():
    return get_brand_facts_payload()


@router.get("/sell/{slug}/", response_class=HTMLResponse)
async def get_sell_landing_page_html(slug: str):
    lp = LANDING_PAGES_BY_SLUG.get(slug)
    if not lp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")
    return HTMLResponse(content=render_landing_page_html(lp))


@router.get("/data/indie-catalog-multiples-ai-fraud-report-2026/", response_class=HTMLResponse)
async def get_indie_catalog_benchmark_report_html():
    return HTMLResponse(content=render_benchmark_report_html())


@router.get("/seo/metadata")
async def get_seo_metadata(path: str = Query(default="/")):
    norm_path = path if path == "/" or path.endswith("/") else f"{path}/"
    meta = SEO_PAGE_METADATA_OVERRIDES.get(norm_path, SEO_PAGE_METADATA_OVERRIDES["/"])
    return {
        "metadata": meta.model_dump() if hasattr(meta, "model_dump") else meta.dict(),
        "jsonld_schemas": build_page_jsonld_schemas(norm_path),
        "canonical_redirect_301": resolve_canonical_redirect(path),
    }


@router.get("/seo/landing-pages")
async def list_seo_landing_pages():
    pages = []
    for lp in LANDING_PAGES_BY_SLUG.values():
        lp_dict = lp.model_dump() if hasattr(lp, "model_dump") else lp.dict()
        lp_dict["jsonld_schemas"] = build_page_jsonld_schemas(lp.canonical_path)
        pages.append(lp_dict)
    return {
        "total": len(pages),
        "genre_count": sum(1 for p in pages if p["category"] == "genre"),
        "distributor_count": sum(1 for p in pages if p["category"] == "distributor"),
        "pages": pages,
    }


@router.get("/seo/landing-pages/{slug}")
async def get_seo_landing_page_by_slug(slug: str):
    lp = LANDING_PAGES_BY_SLUG.get(slug)
    if not lp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")
    lp_dict = lp.model_dump() if hasattr(lp, "model_dump") else lp.dict()
    lp_dict["jsonld_schemas"] = build_page_jsonld_schemas(lp.canonical_path)
    return lp_dict


@router.get("/data/indie-catalog-multiples-ai-fraud-report-2026")
async def get_indie_catalog_benchmark_report():
    return get_indie_catalog_benchmark_report_2026()


@router.get("/seo/backlink-outreach-kit")
async def get_seo_backlink_outreach_kit():
    return get_backlink_outreach_kit()

