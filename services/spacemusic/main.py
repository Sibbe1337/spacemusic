import hmac
import os
from uuid import UUID

import structlog
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, status

from libs.catalog.models import (
    ApplicationStatus,
    CatalogPassportDraft,
    DocumentCreate,
    DocumentReview,
    DocumentStatus,
    DocumentType,
    PayoutRequest,
    SellerApplicationCreate,
    ValuationRequest,
)
from libs.catalog.offers import build_offer_scenarios
from libs.catalog.payouts import TestPayoutAdapter
from libs.catalog.valuation import calculate_valuation
from . import routes
from .store import SellerStore

app = FastAPI()
logger = structlog.get_logger(__name__)
app.state.seller_store = SellerStore()
app.state.payout_adapter = TestPayoutAdapter()


@app.on_event("startup")
async def startup_event():
    logger.info("spacemusic_service_startup", service="spacemusic", status="service_started")


@app.get("/")
async def read_root():
    logger.info("root_accessed", service="spacemusic", request_id="dummy_request_id")
    return {"message": "Welcome to SpaceMusic Service"}


def _seller_store(request: Request) -> SellerStore:
    return request.app.state.seller_store


def _translate_seller_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc).strip("'"))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, ValueError):
        detail = str(exc)
        if detail in {"idempotency_key_conflict", "payout_already_succeeded"}:
            return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.post("/seller/applications", status_code=status.HTTP_201_CREATED)
async def create_seller_application(payload: SellerApplicationCreate, request: Request):
    application, token = _seller_store(request).create_application(payload)
    return {"application": application, "seller_token": token}


@app.get("/seller/applications/{application_id}")
async def get_seller_application(
    application_id: UUID,
    request: Request,
    x_seller_token: str = Header(default=""),
):
    try:
        return _seller_store(request).get_application(application_id, x_seller_token)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.put("/seller/applications/{application_id}/passport")
async def update_seller_passport(
    application_id: UUID,
    payload: CatalogPassportDraft,
    request: Request,
    x_seller_token: str = Header(default=""),
):
    try:
        return _seller_store(request).update_passport(application_id, x_seller_token, payload)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.post("/seller/applications/{application_id}/documents")
async def create_seller_document(
    application_id: UUID,
    payload: DocumentCreate,
    request: Request,
    x_seller_token: str = Header(default=""),
):
    try:
        doc, upload_token = _seller_store(request).create_document(application_id, x_seller_token, payload)
        return {
            "document": doc,
            "upload_url": f"/seller/applications/{application_id}/documents/{doc.id}/upload?upload_token={upload_token}",
            "expires_in_seconds": 900,
        }
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.put("/seller/applications/{application_id}/documents/{document_id}/upload")
async def upload_seller_document(
    application_id: UUID,
    document_id: UUID,
    request: Request,
    upload_token: str = Query(default=""),
):
    body = await request.body()
    try:
        doc = _seller_store(request).complete_document(document_id, upload_token, body, application_id)
        return {"document": doc}
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.get("/seller/applications/{application_id}/documents")
async def list_seller_documents(
    application_id: UUID,
    request: Request,
    x_seller_token: str = Header(default=""),
):
    try:
        return {"documents": _seller_store(request).list_documents(application_id, x_seller_token)}
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.post("/internal/applications/{application_id}/documents/{document_id}/review")
async def review_seller_document(
    application_id: UUID,
    document_id: UUID,
    payload: DocumentReview,
    request: Request,
    x_internal_token: str = Header(default=""),
):
    configured = os.getenv("SPACEMUSIC_INTERNAL_TOKEN", "")
    if not configured or not x_internal_token or not hmac.compare_digest(configured, x_internal_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_internal_token")
    try:
        doc = _seller_store(request).review_document(document_id, DocumentStatus(payload.status), payload.reason)
        return {"document": doc}
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.post("/seller/applications/{application_id}/valuation")
async def evaluate_seller_application(
    application_id: UUID,
    payload: ValuationRequest,
    request: Request,
    x_seller_token: str = Header(default=""),
):
    store = _seller_store(request)
    try:
        application = store.get_application(application_id, x_seller_token)
        docs = store.list_documents(application_id, x_seller_token)
        verified_source_docs = {
            DocumentType.ROYALTY_STATEMENT,
            DocumentType.DISTRIBUTOR_EXPORT,
            DocumentType.PUBLISHER_STATEMENT,
        }
        has_verified_source_doc = any(
            d.status == DocumentStatus.VERIFIED and d.document_type in verified_source_docs for d in docs
        )
        passport = application.catalog_passport
        if has_verified_source_doc:
            passport = passport.model_copy(
                update={
                    "revenue_history": [
                        p.model_copy(update={"verified": True}) for p in passport.revenue_history
                    ]
                }
            )
        store.set_status(
            application_id,
            ApplicationStatus.UNDER_REVIEW,
            actor_role="SYSTEM",
            action="REVIEW_STARTED",
        )
        valuation = calculate_valuation(passport, payload)
        offers = build_offer_scenarios(application_id, passport, valuation, payload)
        store.save_valuation(application_id, valuation, offers)
        return {"valuation": valuation, "offers": offers}
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.post("/seller/applications/{application_id}/offers/{offer_id}/accept")
async def accept_seller_offer(
    application_id: UUID,
    offer_id: UUID,
    request: Request,
    x_seller_token: str = Header(default=""),
):
    try:
        offer = _seller_store(request).accept_offer(application_id, x_seller_token, offer_id)
        return {"status": "ACCEPTED", "offer": offer}
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.get("/seller/applications/{application_id}/termsheet")
async def get_seller_termsheet(
    application_id: UUID,
    request: Request,
    x_seller_token: str = Header(default=""),
):
    try:
        application = _seller_store(request).get_application(application_id, x_seller_token)
        offer = next((item for item in application.offers if item.id == application.accepted_offer_id), None)
        if offer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offer_not_found")
        return {"application_id": str(application_id), "offer": offer}
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.post("/seller/applications/{application_id}/payout")
async def execute_seller_payout(
    application_id: UUID,
    payload: PayoutRequest,
    request: Request,
    x_seller_token: str = Header(default=""),
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
):
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="idempotency_key_required")
    store = _seller_store(request)
    try:
        application = store.get_application(application_id, x_seller_token)
        offer = next((item for item in application.offers if item.id == payload.offer_id), None)
        if offer is None:
            raise KeyError("offer_not_found")
        payout = store.create_payout_intent(
            application_id=application_id,
            offer_id=payload.offer_id,
            idempotency_key=idempotency_key,
            amount_cents=offer.cash_median_cents,
            currency_code=offer.currency_code,
            recipient_token=payload.recipient_token,
        )
        if payout.status != "SUCCEEDED":
            adapter = request.app.state.payout_adapter
            result = adapter.create_payout(
                payout_intent_id=payout.id,
                amount_cents=payout.amount_cents,
                currency_code=payout.currency_code,
                recipient_token=payload.recipient_token,
                idempotency_key=idempotency_key,
            )
            payout = store.complete_payout(payout.id, result.provider_reference)
        return {"payout": payout, "ledger_status": "RECORDED"}
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.get("/seller/applications/{application_id}/timeline")
async def get_seller_timeline(
    application_id: UUID,
    request: Request,
    x_seller_token: str = Header(default=""),
):
    try:
        return {"events": _seller_store(request).timeline(application_id, x_seller_token)}
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


@app.get("/seller/applications/{application_id}/payouts/{payout_id}/receipt")
async def download_seller_receipt(
    application_id: UUID,
    payout_id: UUID,
    request: Request,
    download_token: str = Query(default=""),
):
    store = _seller_store(request)
    try:
        payout = store.get_payout_internal(payout_id)
        if payout.application_id != application_id:
            raise KeyError("receipt_not_found")
        pdf_bytes, sha256 = store.read_receipt(payout_id, download_token)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"X-Receipt-SHA256": sha256},
        )
    except (KeyError, PermissionError, ValueError) as exc:
        raise _translate_seller_error(exc)


app.include_router(routes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)