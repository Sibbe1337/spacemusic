"""
FastAPI Routes for SPACE Catalog Review (`services/spacemusic/routes.py`)

Endpoints:
- `POST /webhooks/typeform`: Ingests Typeform `xzx5SBJb` ("SPACE catalog review") payloads,
  runs Stage 1 valuation & DD triage, generates reply draft, and stores in DB.
- `POST /catalog-review/evaluate`: Direct Stage 1 or Stage 2 evaluation endpoint accepting
  structured catalog data + optional raw distributor CSV/TSV statement text.
- `POST /catalog-review/{application_id}/statements`: Attaches raw distributor CSV/TSV statements
  to an existing Typeform application, upgrading it to `STAGE_2_STATEMENT_VERIFIED` and
  storing empirical RPM benchmarks in SPACE's proprietary database.
- `GET /catalog-review/applications`: Lists evaluated catalog applications with pipeline status.
- `GET /catalog-review/benchmarks`: Returns aggregated empirical RPM benchmarks across DSPs & countries.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel

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
from .inbox_ingestor import (
    AutonomousStage2UnderwritingResult,
    InboundEmailStatementWebhook,
    ingest_inbound_email_statements,
)
from .models import CatalogApplication, ProprietaryBenchmarkRecord, ReplyDraft
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
)

router = APIRouter()
logger = structlog.get_logger(__name__)

# In-memory store with optional SQLite/Postgres persistence fallback so service works out-of-the-box
_APPLICATIONS_STORE: Dict[uuid.UUID, CatalogApplication] = {}
_BENCHMARKS_STORE: List[ProprietaryBenchmarkRecord] = []

_engine = SpaceValuationEngine()


class DirectEvaluationRequest(BaseModel):
    catalog: CatalogValuationInput
    raw_statement_csv: Optional[str] = None


class StatementUploadRequest(BaseModel):
    raw_statement_csv: str
    default_currency: str = "USD"
    artist_or_label_override: Optional[str] = None
    listen_url_override: Optional[str] = None


class TypeformCsvImportRequest(BaseModel):
    csv_content: str
    skip_test_rows: bool = True


class ApplicationEvaluationResponse(BaseModel):
    application_id: uuid.UUID
    pipeline_status: str
    valuation_stage: str
    autonomous_decision: Optional[str] = None
    valuation: CatalogValuationOutput
    reply_draft: ReplyDraft
    statement_summary: Optional[ParsedStatementSummary] = None
    implied_revenue_crosscheck: Optional[ImpliedRevenueCrossCheck] = None
    distributor_export_guide: Optional[str] = None
    institutional_routing: Optional[InstitutionalRoutingReport] = None


@router.post(
    "/webhooks/typeform",
    response_model=ApplicationEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def handle_typeform_webhook(payload: Dict[str, Any] = Body(...)):
    """
    Receives a Typeform webhook (`xzx5SBJb` - SPACE catalog review), parses all 19 fields,
    executes the Zero-Touch Stage 1 pipeline (optional embedded `spotify_snapshot` or
    `raw_spotify_payload`, mathematical stream-to-revenue cross-check, 8-genre DCF,
    AI/fake profile forensics, and distributor-specific export guide injection),
    and stores the evaluated application.
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

    _APPLICATIONS_STORE[app_row.id] = app_row
    logger.info(
        "typeform_application_evaluated",
        application_id=str(app_row.id),
        artist=app_row.artist_or_label_name,
        pipeline_status=app_row.pipeline_status,
        autonomous_decision=zt_res.autonomous_decision,
        price_median_eur=app_row.price_median_eur,
    )

    return ApplicationEvaluationResponse(
        application_id=app_row.id,
        pipeline_status=zt_res.pipeline_status,
        valuation_stage=zt_res.valuation.valuation_stage,
        autonomous_decision=zt_res.autonomous_decision,
        valuation=zt_res.valuation,
        reply_draft=zt_res.reply_draft,
        implied_revenue_crosscheck=zt_res.implied_revenue_crosscheck,
        distributor_export_guide=zt_res.distributor_export_guide,
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
    stmt_summary: Optional[ParsedStatementSummary] = None

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

    return ApplicationEvaluationResponse(
        application_id=app_row.id,
        pipeline_status=valuation.pipeline_status,
        valuation_stage=valuation.valuation_stage,
        valuation=valuation,
        reply_draft=reply_draft,
        statement_summary=stmt_summary,
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
    app_row.updated_at = datetime.utcnow()

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

    return ApplicationEvaluationResponse(
        application_id=app_row.id,
        pipeline_status=valuation.pipeline_status,
        valuation_stage=valuation.valuation_stage,
        valuation=valuation,
        reply_draft=reply_draft,
        statement_summary=stmt_summary,
        institutional_routing=routing,
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


@router.post("/catalog-review/import-csv")
async def import_typeform_csv(req: TypeformCsvImportRequest):
    """
    Bulk-imports and evaluates a Typeform CSV export (`responses-xzx5SBJb-*.csv`),
    running the Zero-Touch Stage 1 pipeline across all rows and returning their
    full DCF + Forensics evaluations, autonomous routing decisions, and reply drafts.
    """
    apps = parse_typeform_csv_export(req.csv_content, skip_test_rows=req.skip_test_rows)
    results: List[ApplicationEvaluationResponse] = []
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
