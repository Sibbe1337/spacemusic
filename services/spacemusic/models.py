"""
Database & API Models for SPACE Catalog Review (`services/spacemusic/models.py`)

Maps the 19-field Typeform (`xzx5SBJb` - SPACE catalog review), statement uploads,
DCF + Forensics outputs, email reply drafts, and SPACE's proprietary empirical
RPM/survival benchmark records.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Column, Field, JSON, SQLModel


class CatalogApplication(SQLModel, table=True):
    __tablename__ = "catalog_applications"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    typeform_response_id: Optional[str] = Field(default=None, index=True, unique=True)
    typeform_form_id: str = Field(default="xzx5SBJb", index=True)

    # Typeform core fields (1..19)
    inquiry_route: str = Field(default="own_catalog", index=True)  # own_catalog | represented_catalog | partnership
    contact_name: str = Field(default="")
    contact_email: str = Field(default="", index=True)
    artist_or_label_name: str = Field(default="", index=True)
    listen_url: Optional[str] = Field(default=None)
    spotify_artist_id: Optional[str] = Field(default=None, index=True)
    rights_scope: str = Field(default="masters")
    owner_authorized: bool = Field(default=True)
    knows_ltm_royalties: bool = Field(default=True)
    declared_ltm_amount: float = Field(default=0.0)
    declared_currency: str = Field(default="USD")
    royalty_basis: str = Field(default="net_payable")
    distributor_or_admin: Optional[str] = Field(default=None)
    rights_notes: Optional[str] = Field(default=None)

    # Partnership branch fields (14..16)
    organization_name: Optional[str] = Field(default=None)
    organization_website: Optional[str] = Field(default=None)
    partnership_topic: Optional[str] = Field(default=None)

    # Attribution & opt-in (17..18)
    referral_source: Optional[str] = Field(default=None)
    newsletter_opt_in: bool = Field(default=False)

    # Pipeline & Valuation State
    pipeline_status: str = Field(default="SCREENING", index=True)
    valuation_stage: str = Field(default="STAGE_1_INDICATIVE")
    statements_verified: bool = Field(default=False)

    effective_cf0_eur: float = Field(default=0.0)
    price_low_eur: float = Field(default=0.0)
    price_median_eur: float = Field(default=0.0)
    price_high_eur: float = Field(default=0.0)
    implied_multiple_median: float = Field(default=0.0)
    discount_rate: float = Field(default=0.12)
    integrity_score: float = Field(default=100.0)
    valuation_confidence: float = Field(default=0.5)

    # Rich JSON artifacts stored for auditability and UI inspection
    valuation_report_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    draft_reply_subject: Optional[str] = Field(default=None)
    draft_reply_body: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProprietaryBenchmarkRecord(SQLModel, table=True):
    """
    Stores anonymized empirical per-stream payout rates (RPM) and decay slopes
    extracted from uploaded distributor statements. Every reviewed catalog
    compounds SPACE's proprietary moat.
    """

    __tablename__ = "space_proprietary_benchmarks"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_application_id: Optional[uuid.UUID] = Field(default=None, index=True)
    distributor: str = Field(default="Unknown", index=True)
    genre_family: str = Field(default="electronic_indie", index=True)
    dsp_store: str = Field(default="spotify", index=True)
    country_code: str = Field(default="US", index=True)
    total_streams: int = Field(default=0)
    total_net_royalty_eur: float = Field(default=0.0)
    observed_rpm_eur: float = Field(default=0.0)
    observed_rpm_usd: float = Field(default=0.0)
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class ReplyDraft(BaseModel):
    recipient_email: str
    recipient_name: str
    subject: str
    body: str
    template_type: str  # MISSING_INFO | REQUEST_STATEMENTS | INDICATIVE_OFFER | POLITE_DECLINE_OR_PAID_AUDIT | PARTNERSHIP
