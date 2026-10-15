"""
Paid Valuation Model & Claude Investment Memo Checkout Service — Powered by Autumn + Stripe
(`services/spacemusic/paid_memo_service.py`)

Exposes SPACE's institutional valuation model (`engine.py` + `dtw_matcher.py` + `jev_evaluator.py`)
and Claude 19-slide 16:9 Investment Memo generator (`claude_memo_generator.py` + `memo_pdf_renderer.py`)
as a self-serve paid product with **Autumn (`https://useautumn.com`)** as the billing, credit, and
entitlement layer on top of Stripe:

1. **Autumn Billing & Entitlement Pipeline (`https://api.useautumn.com/v1`)**:
   - `customers.getOrCreate` (`POST /v1/customers.get_or_create`): Ensures the customer exists in
     Autumn before any balance check, usage track, or checkout attach, auto-enabling the
     `free_preview` plan (`3` `indicative_catalog_review` credits/mo).
   - `balances.check` (`POST /v1/balances.check`): Checks whether a `customer_id` has remaining
     `investment_memo_pdf` or `indicative_catalog_review` credits. When `send_event=True`,
     atomically deducts 1 credit and unlocks all 19 slides immediately without requiring a new
     checkout redirect.
   - `billing.attach` (`POST /v1/billing.attach`): Attaches either `single_memo_299` ($299 one-time
     add-on) or `desk_pass_499` ($499/mo subscription with 10 memos/mo) to `customer_id`, returning
     Autumn's Stripe Checkout `payment_url` (or `None` if a saved payment method / credit balance
     covered the purchase immediately).
   - `balances.track` (`POST /v1/balances.track`): Records metered consumption of
     `investment_memo_pdf` / `indicative_catalog_review` (`value: 1`) or credits back (`value: -1`).
   - `plans.list` (`POST /v1/plans.list`): Lists active plans with per-customer eligibility and
     `attach_action` (`purchase`, `upgrade`, `none`).
   - `billing.openCustomerPortal` (`POST /v1/billing.open_customer_portal`): Creates a Stripe
     Billing Portal session for managing active subscriptions and invoices.
2. **Freemium Teaser -> Paid 19-Slide Investment Memo (`$299 / €275`)**:
   - Visitors upload distributor statements (`.csv` / `.tsv`) or enter catalog telemetry.
   - The engine immediately computes the 10,000-path Monte Carlo DCF, DTW lifecycle match, and
     TypeSafe AI (JEV) 7-question audit, returning a live preview of **Slides 01–02** while
     blurring **Slides 03–19** until Autumn/Stripe entitlement is verified.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
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


AUTUMN_API_BASE_URL = "https://api.useautumn.com/v1"
AUTUMN_FEATURE_MEMO_PDF = "investment_memo_pdf"
AUTUMN_FEATURE_INDICATIVE_REVIEW = "indicative_catalog_review"
AUTUMN_PLAN_FREE_PREVIEW = "free_preview"
AUTUMN_PLAN_DESK_PASS_499 = "desk_pass_499"
AUTUMN_PLAN_SINGLE_MEMO_299 = "single_memo_299"


class PaidMemoPlanTier(str, Enum):
    SINGLE_MEMO_299 = "SINGLE_MEMO_299"
    DESK_PASS_499 = "DESK_PASS_499"


class PaymentStatus(str, Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"


class BillingProvider(str, Enum):
    AUTUMN = "AUTUMN"
    STRIPE_DIRECT = "STRIPE_DIRECT"
    PARTNER_WAIVER = "PARTNER_WAIVER"


PLAN_PRICING: Dict[PaidMemoPlanTier, Dict[str, Any]] = {
    PaidMemoPlanTier.SINGLE_MEMO_299: {
        "autumn_plan_id": "single_memo_299",
        "name": "SPACE 19-Slide Institutional Catalog Valuation Memo (PDF + DCF Schedule)",
        "amount_usd_cents": 29900,
        "amount_usd": 299.0,
        "amount_eur": 275.0,
        "granted_credits": 1,
    },
    PaidMemoPlanTier.DESK_PASS_499: {
        "autumn_plan_id": "desk_pass_499",
        "name": "SPACE Manager / Label Underwriting Desk Pass (Up to 10 Catalog Memos / mo)",
        "amount_usd_cents": 49900,
        "amount_usd": 499.0,
        "amount_eur": 459.0,
        "granted_credits": 10,
    },
}

VIP_WAIVER_COUPONS = {"SPACE-PARTNER-VIP", "SPACE-INTERNAL-100"}


class AutumnBalanceSnapshot(BaseModel):
    customer_id: str
    feature_id: str = AUTUMN_FEATURE_MEMO_PDF
    allowed: bool
    granted_balance: int = 0
    used_balance: int = 0
    remaining_balance: int = 0
    plan_id: Optional[str] = None
    unlimited: bool = False
    execution_mode: str = "LOCAL_LEDGER"  # LIVE_AUTUMN_API | LOCAL_LEDGER


class AutumnCustomerRequest(BaseModel):
    customer_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutumnCustomerSnapshot(BaseModel):
    customer_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    active_plan_ids: list[str] = Field(default_factory=list)
    balances: Dict[str, AutumnBalanceSnapshot] = Field(default_factory=dict)
    execution_mode: str = "LOCAL_LEDGER"


class AutumnPlanItemSummary(BaseModel):
    feature_id: str
    included: int = 0
    unlimited: bool = False
    reset_interval: Optional[str] = None
    primary_text: Optional[str] = None


class AutumnPlanSummary(BaseModel):
    plan_id: str
    name: str
    description: Optional[str] = None
    add_on: bool = False
    auto_enable: bool = False
    amount_usd: Optional[float] = None
    interval: Optional[str] = None
    attach_action: Optional[str] = None
    items: list[AutumnPlanItemSummary] = Field(default_factory=list)


class AutumnPlansListResponse(BaseModel):
    customer_id: Optional[str] = None
    plans: list[AutumnPlanSummary] = Field(default_factory=list)
    execution_mode: str = "LOCAL_LEDGER"


class AutumnPortalRequest(BaseModel):
    customer_id: str
    return_url: str = "https://spacemusic.io/valuation-memo"


class AutumnPortalResponse(BaseModel):
    customer_id: str
    portal_url: str
    execution_mode: str = "LOCAL_LEDGER"


class AutumnCheckRequest(BaseModel):
    customer_id: str
    feature_id: str = AUTUMN_FEATURE_MEMO_PDF
    required_balance: int = Field(default=1, ge=1)
    send_event: bool = False


class AutumnTrackRequest(BaseModel):
    customer_id: str
    feature_id: str = AUTUMN_FEATURE_MEMO_PDF
    value: int = 1
    idempotency_key: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class PaidMemoCheckoutRequest(BaseModel):
    application_id: Optional[uuid.UUID] = None
    customer_id: Optional[str] = None
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
    customer_id: str
    deal_code: str
    artist_or_label_name: str
    plan_tier: PaidMemoPlanTier
    autumn_plan_id: str
    autumn_feature_id: str = AUTUMN_FEATURE_MEMO_PDF
    billing_provider: BillingProvider = BillingProvider.AUTUMN
    amount_usd: float
    amount_eur: float
    payment_status: PaymentStatus
    stripe_session_id: str
    checkout_url: str
    receipt_token: str
    locked_preview_url: str
    unlocked_html_url: str
    unlocked_pdf_url: str
    autumn_credits_remaining: int = 0
    created_at_utc: str
    paid_at_utc: Optional[str] = None
    deck: CatalogInvestmentMemoDeck


class PaidMemoCheckoutResponse(BaseModel):
    order_id: str
    application_id: uuid.UUID
    customer_id: str
    deal_code: str
    artist_or_label_name: str
    plan_tier: PaidMemoPlanTier
    autumn_plan_id: str
    autumn_feature_id: str = AUTUMN_FEATURE_MEMO_PDF
    billing_provider: BillingProvider = BillingProvider.AUTUMN
    amount_usd: float
    amount_eur: float
    payment_status: PaymentStatus
    stripe_session_id: str
    checkout_url: str
    locked_preview_url: str
    unlocked_html_url: Optional[str] = None
    unlocked_pdf_url: Optional[str] = None
    receipt_token: Optional[str] = None
    autumn_credits_remaining: int = 0
    teaser_headline: str
    teaser_standalone_base_usd: str
    teaser_ltm_verified_usd: str
    teaser_wacc_pct: float
    claude_model_used: str
    claude_execution_mode: str


def _canonical_customer_id(raw: str) -> str:
    val = raw.strip()
    if "@" in val and not val.startswith("cus_"):
        slug = re.sub(r"[^a-z0-9_.-]+", "_", val.lower()).strip("_")
        return f"cus_{slug}"
    return val


def _normalize_customer_id(
    customer_id: Optional[str],
    contact_email: Optional[str],
    artist_or_label_name: str,
) -> str:
    if customer_id and customer_id.strip():
        return _canonical_customer_id(customer_id)
    if contact_email and contact_email.strip():
        return _canonical_customer_id(contact_email)
    slug = re.sub(r"[^a-z0-9]+", "_", artist_or_label_name.strip().lower()).strip("_") or "guest"
    return f"cus_{slug}"


class AutumnBillingClient:
    """
    Client for Autumn (`https://useautumn.com` / `https://api.useautumn.com/v1`) providing:
      - `get_or_create_customer` (`POST /v1/customers.get_or_create`)
      - `check_balance` (`POST /v1/balances.check`)
      - `attach_plan` (`POST /v1/billing.attach`)
      - `track_usage` (`POST /v1/balances.track`)
      - `list_plans` (`POST /v1/plans.list`)
      - `open_customer_portal` (`POST /v1/billing.open_customer_portal`)

    When `AUTUMN_SECRET_KEY` is configured in the environment, requests are sent to the live
    Autumn API (`https://api.useautumn.com/v1`). Also maintains an in-memory credit & entitlement
    ledger so tests and local development behave identically to production Autumn balances.
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        base_url: str = AUTUMN_API_BASE_URL,
    ) -> None:
        self._explicit_secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self._ledger: Dict[tuple[str, str], Dict[str, Any]] = {}
        self._customers: Dict[str, Dict[str, Any]] = {}

    @property
    def secret_key(self) -> Optional[str]:
        return self._explicit_secret_key or os.environ.get("AUTUMN_SECRET_KEY")

    def _get_or_init_entry(self, customer_id: str, feature_id: str = AUTUMN_FEATURE_MEMO_PDF) -> Dict[str, Any]:
        cid = _canonical_customer_id(customer_id)
        key = (cid, feature_id)
        if key not in self._ledger:
            if feature_id == AUTUMN_FEATURE_INDICATIVE_REVIEW:
                self._ledger[key] = {
                    "granted": 3,
                    "used": 0,
                    "plan_id": AUTUMN_PLAN_FREE_PREVIEW,
                    "unlimited": False,
                }
            else:
                self._ledger[key] = {
                    "granted": 0,
                    "used": 0,
                    "plan_id": None,
                    "unlimited": False,
                }
        return self._ledger[key]

    @staticmethod
    def _parse_balance_dict(
        customer_id: str,
        feature_id: str,
        bal: Dict[str, Any],
        *,
        allowed_override: Optional[bool] = None,
    ) -> AutumnBalanceSnapshot:
        granted = int(bal.get("granted_balance") or bal.get("granted") or 0)
        used = int(bal.get("usage") or bal.get("used") or 0)
        remaining = int(
            bal.get("remaining")
            if bal.get("remaining") is not None
            else max(0, granted - used)
        )
        unlimited = bool(bal.get("unlimited", False))
        plan_id = bal.get("plan_id")
        if not plan_id:
            breakdown = bal.get("breakdown")
            if isinstance(breakdown, list) and breakdown:
                first_row = breakdown[0]
                if isinstance(first_row, dict):
                    plan_id = first_row.get("plan_id")
        allowed = (
            bool(allowed_override)
            if allowed_override is not None
            else (unlimited or remaining > 0)
        )
        return AutumnBalanceSnapshot(
            customer_id=customer_id,
            feature_id=feature_id,
            allowed=allowed,
            granted_balance=granted,
            used_balance=used,
            remaining_balance=remaining,
            plan_id=plan_id,
            unlimited=unlimited,
            execution_mode="LIVE_AUTUMN_API",
        )

    def get_or_create_customer(
        self,
        *,
        customer_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AutumnCustomerSnapshot:
        """
        Calls `POST https://api.useautumn.com/v1/customers.get_or_create` to ensure the customer
        exists in Autumn before calling `balances.check`, `balances.track`, or `billing.attach`.
        Automatically enables the `free_preview` plan on new customers.
        """
        cid = _canonical_customer_id(customer_id)
        key = self.secret_key
        if key:
            payload_obj: Dict[str, Any] = {"customer_id": cid}
            if name:
                payload_obj["name"] = name
            if email:
                payload_obj["email"] = email
            if metadata:
                payload_obj["metadata"] = metadata
            payload = json.dumps(payload_obj).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/customers.get_or_create",
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    subs = body.get("subscriptions") or []
                    purchases = body.get("purchases") or []
                    active_plans: list[str] = []
                    for sub in subs:
                        if isinstance(sub, dict) and sub.get("status") in ("active", "trialing"):
                            pid = sub.get("plan_id")
                            if pid and pid not in active_plans:
                                active_plans.append(str(pid))
                    for pur in purchases:
                        if isinstance(pur, dict):
                            pid = pur.get("plan_id")
                            if pid and pid not in active_plans:
                                active_plans.append(str(pid))
                    raw_balances = body.get("balances") or {}
                    parsed_balances: Dict[str, AutumnBalanceSnapshot] = {}
                    if isinstance(raw_balances, dict):
                        for fid, bdict in raw_balances.items():
                            if isinstance(bdict, dict):
                                parsed_balances[str(fid)] = self._parse_balance_dict(
                                    cid, str(fid), bdict
                                )
                    return AutumnCustomerSnapshot(
                        customer_id=str(body.get("id") or cid),
                        name=body.get("name") or name,
                        email=body.get("email") or email,
                        active_plan_ids=active_plans,
                        balances=parsed_balances,
                        execution_mode="LIVE_AUTUMN_API",
                    )
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                pass

        # Local ledger fallback
        if cid not in self._customers:
            self._customers[cid] = {
                "customer_id": cid,
                "name": name,
                "email": email,
                "metadata": metadata or {},
            }
        else:
            if name:
                self._customers[cid]["name"] = name
            if email:
                self._customers[cid]["email"] = email

        memo_entry = self._get_or_init_entry(cid, AUTUMN_FEATURE_MEMO_PDF)
        rev_entry = self._get_or_init_entry(cid, AUTUMN_FEATURE_INDICATIVE_REVIEW)
        active_plans_local = [AUTUMN_PLAN_FREE_PREVIEW]
        if memo_entry.get("plan_id") and memo_entry["plan_id"] not in active_plans_local:
            active_plans_local.append(str(memo_entry["plan_id"]))

        memo_rem = max(0, memo_entry["granted"] - memo_entry["used"])
        rev_rem = max(0, rev_entry["granted"] - rev_entry["used"])
        return AutumnCustomerSnapshot(
            customer_id=cid,
            name=self._customers[cid].get("name"),
            email=self._customers[cid].get("email"),
            active_plan_ids=active_plans_local,
            balances={
                AUTUMN_FEATURE_INDICATIVE_REVIEW: AutumnBalanceSnapshot(
                    customer_id=cid,
                    feature_id=AUTUMN_FEATURE_INDICATIVE_REVIEW,
                    allowed=bool(rev_entry["unlimited"]) or rev_rem > 0,
                    granted_balance=rev_entry["granted"],
                    used_balance=rev_entry["used"],
                    remaining_balance=rev_rem,
                    plan_id=rev_entry["plan_id"],
                    unlimited=bool(rev_entry["unlimited"]),
                    execution_mode="LOCAL_LEDGER",
                ),
                AUTUMN_FEATURE_MEMO_PDF: AutumnBalanceSnapshot(
                    customer_id=cid,
                    feature_id=AUTUMN_FEATURE_MEMO_PDF,
                    allowed=bool(memo_entry["unlimited"]) or memo_rem > 0,
                    granted_balance=memo_entry["granted"],
                    used_balance=memo_entry["used"],
                    remaining_balance=memo_rem,
                    plan_id=memo_entry["plan_id"],
                    unlimited=bool(memo_entry["unlimited"]),
                    execution_mode="LOCAL_LEDGER",
                ),
            },
            execution_mode="LOCAL_LEDGER",
        )

    def provision_plan_credits(
        self,
        customer_id: str,
        plan_tier: PaidMemoPlanTier,
        feature_id: str = AUTUMN_FEATURE_MEMO_PDF,
        consume_immediately: int = 0,
    ) -> AutumnBalanceSnapshot:
        """
        Provisions plan credits in the local Autumn balance ledger when a plan or one-time
        pack is paid (`SINGLE_MEMO_299` -> +1 credit, `DESK_PASS_499` -> +10 credits).
        """
        pricing = PLAN_PRICING[plan_tier]
        entry = self._get_or_init_entry(customer_id, feature_id)
        entry["granted"] += int(pricing["granted_credits"])
        entry["plan_id"] = pricing["autumn_plan_id"]
        if consume_immediately > 0:
            entry["used"] = min(entry["granted"], entry["used"] + consume_immediately)
        remaining = max(0, entry["granted"] - entry["used"])
        return AutumnBalanceSnapshot(
            customer_id=customer_id,
            feature_id=feature_id,
            allowed=remaining > 0 or bool(entry["unlimited"]),
            granted_balance=entry["granted"],
            used_balance=entry["used"],
            remaining_balance=remaining,
            plan_id=entry["plan_id"],
            unlimited=bool(entry["unlimited"]),
            execution_mode="LIVE_AUTUMN_API" if self.secret_key else "LOCAL_LEDGER",
        )

    def check_balance(
        self,
        *,
        customer_id: str,
        feature_id: str = AUTUMN_FEATURE_MEMO_PDF,
        required_balance: int = 1,
        send_event: bool = False,
    ) -> AutumnBalanceSnapshot:
        """
        Calls `POST https://api.useautumn.com/v1/balances.check` when `AUTUMN_SECRET_KEY` is set,
        falling back to the in-memory Autumn balance ledger.
        If `send_event=True` and the customer has >= `required_balance` credits, atomically
        deducts `required_balance` from their balance.
        """
        cid = _canonical_customer_id(customer_id)
        key = self.secret_key
        if key:
            self.get_or_create_customer(customer_id=cid)
            payload = json.dumps(
                {
                    "customer_id": cid,
                    "feature_id": feature_id,
                    "required_balance": required_balance,
                    "send_event": send_event,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/balances.check",
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    allowed = bool(body.get("allowed", False))
                    bal = body.get("balance") or {}
                    return self._parse_balance_dict(
                        customer_id,
                        feature_id,
                        bal if isinstance(bal, dict) else {},
                        allowed_override=allowed,
                    )
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                pass

        entry = self._get_or_init_entry(customer_id, feature_id)
        remaining = max(0, entry["granted"] - entry["used"])
        allowed = bool(entry["unlimited"]) or (remaining >= required_balance)
        if allowed and send_event and not entry["unlimited"]:
            entry["used"] += required_balance
            remaining = max(0, entry["granted"] - entry["used"])

        return AutumnBalanceSnapshot(
            customer_id=customer_id,
            feature_id=feature_id,
            allowed=allowed,
            granted_balance=entry["granted"],
            used_balance=entry["used"],
            remaining_balance=remaining,
            plan_id=entry["plan_id"],
            unlimited=bool(entry["unlimited"]),
            execution_mode="LOCAL_LEDGER",
        )

    def track_usage(
        self,
        *,
        customer_id: str,
        feature_id: str = AUTUMN_FEATURE_MEMO_PDF,
        value: int = 1,
        idempotency_key: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> AutumnBalanceSnapshot:
        """
        Calls `POST https://api.useautumn.com/v1/balances.track` (`async: false`) when
        `AUTUMN_SECRET_KEY` is configured, and updates the local Autumn balance ledger.
        Use `value=1` to consume 1 memo credit, or `value=-1` to credit back a memo.
        """
        cid = _canonical_customer_id(customer_id)
        key = self.secret_key
        if key:
            self.get_or_create_customer(customer_id=cid)
            payload = json.dumps(
                {
                    "customer_id": cid,
                    "feature_id": feature_id,
                    "value": value,
                    "async": False,
                    "properties": properties or {},
                }
            ).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            if idempotency_key:
                headers["Idempotency-Key"] = idempotency_key
            req = urllib.request.Request(
                f"{self.base_url}/balances.track",
                data=payload,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    bal = body.get("balance") or {}
                    return self._parse_balance_dict(
                        customer_id,
                        feature_id,
                        bal if isinstance(bal, dict) else {},
                    )
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                pass

        entry = self._get_or_init_entry(customer_id, feature_id)
        entry["used"] = max(0, entry["used"] + value)
        remaining = max(0, entry["granted"] - entry["used"])
        return AutumnBalanceSnapshot(
            customer_id=customer_id,
            feature_id=feature_id,
            allowed=bool(entry["unlimited"]) or remaining > 0,
            granted_balance=entry["granted"],
            used_balance=entry["used"],
            remaining_balance=remaining,
            plan_id=entry["plan_id"],
            unlimited=bool(entry["unlimited"]),
            execution_mode="LOCAL_LEDGER",
        )

    def list_plans(
        self,
        *,
        customer_id: Optional[str] = None,
    ) -> AutumnPlansListResponse:
        """
        Calls `POST https://api.useautumn.com/v1/plans.list` to fetch the catalog plans
        (`free_preview`, `desk_pass_499`, `single_memo_299`) along with per-customer
        eligibility (`attach_action`) when `customer_id` is provided.
        """
        cid = _canonical_customer_id(customer_id) if customer_id else None
        key = self.secret_key
        if key:
            if cid:
                self.get_or_create_customer(customer_id=cid)
            payload_obj: Dict[str, Any] = {}
            if cid:
                payload_obj["customer_id"] = cid
            req = urllib.request.Request(
                f"{self.base_url}/plans.list",
                data=json.dumps(payload_obj).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    raw_list = body.get("list") or []
                    summaries: list[AutumnPlanSummary] = []
                    for item in raw_list:
                        if not isinstance(item, dict):
                            continue
                        price_obj = item.get("price") or {}
                        elig_obj = item.get("customer_eligibility") or {}
                        plan_items: list[AutumnPlanItemSummary] = []
                        for p_item in item.get("items") or []:
                            if not isinstance(p_item, dict):
                                continue
                            reset_obj = p_item.get("reset") or {}
                            disp_obj = p_item.get("display") or {}
                            plan_items.append(
                                AutumnPlanItemSummary(
                                    feature_id=str(p_item.get("feature_id") or ""),
                                    included=int(p_item.get("included") or 0),
                                    unlimited=bool(p_item.get("unlimited", False)),
                                    reset_interval=(
                                        str(reset_obj.get("interval"))
                                        if reset_obj.get("interval")
                                        else None
                                    ),
                                    primary_text=disp_obj.get("primary_text"),
                                )
                            )
                        summaries.append(
                            AutumnPlanSummary(
                                plan_id=str(item.get("id") or ""),
                                name=str(item.get("name") or ""),
                                description=item.get("description"),
                                add_on=bool(item.get("add_on", False)),
                                auto_enable=bool(item.get("auto_enable", False)),
                                amount_usd=(
                                    float(price_obj["amount"])
                                    if isinstance(price_obj, dict) and price_obj.get("amount") is not None
                                    else None
                                ),
                                interval=(
                                    str(price_obj["interval"])
                                    if isinstance(price_obj, dict) and price_obj.get("interval")
                                    else None
                                ),
                                attach_action=(
                                    str(elig_obj["attach_action"])
                                    if isinstance(elig_obj, dict) and elig_obj.get("attach_action")
                                    else None
                                ),
                                items=plan_items,
                            )
                        )
                    return AutumnPlansListResponse(
                        customer_id=cid,
                        plans=summaries,
                        execution_mode="LIVE_AUTUMN_API",
                    )
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                pass

        # Local fallback matching autumn/plans.ts
        memo_entry = self._get_or_init_entry(cid, AUTUMN_FEATURE_MEMO_PDF) if cid else {}
        has_desk_pass = memo_entry.get("plan_id") == AUTUMN_PLAN_DESK_PASS_499
        return AutumnPlansListResponse(
            customer_id=cid,
            plans=[
                AutumnPlanSummary(
                    plan_id=AUTUMN_PLAN_FREE_PREVIEW,
                    name="Free Catalog Review & Preview",
                    description="Free indicative Monte Carlo DCF & DTW catalog review with Slides 01–02 memo preview",
                    add_on=False,
                    auto_enable=True,
                    amount_usd=None,
                    interval=None,
                    attach_action="none" if cid else "activate",
                    items=[
                        AutumnPlanItemSummary(
                            feature_id=AUTUMN_FEATURE_INDICATIVE_REVIEW,
                            included=3,
                            unlimited=False,
                            reset_interval="month",
                            primary_text="3 indicative catalog valuations & forensics previews",
                        )
                    ],
                ),
                AutumnPlanSummary(
                    plan_id=AUTUMN_PLAN_DESK_PASS_499,
                    name="SPACE Manager / Label Underwriting Desk Pass",
                    description="Up to 10 institutional 19-slide 16:9 catalog investment memos per month plus unlimited indicative reviews",
                    add_on=False,
                    auto_enable=False,
                    amount_usd=499.0,
                    interval="month",
                    attach_action="none" if has_desk_pass else "upgrade",
                    items=[
                        AutumnPlanItemSummary(
                            feature_id=AUTUMN_FEATURE_MEMO_PDF,
                            included=10,
                            unlimited=False,
                            reset_interval="month",
                            primary_text="10 19-Slide Institutional Investment Memo PDFs",
                        ),
                        AutumnPlanItemSummary(
                            feature_id=AUTUMN_FEATURE_INDICATIVE_REVIEW,
                            included=0,
                            unlimited=True,
                            reset_interval="one_off",
                            primary_text="Unlimited indicative catalog valuations & forensics previews",
                        ),
                    ],
                ),
                AutumnPlanSummary(
                    plan_id=AUTUMN_PLAN_SINGLE_MEMO_299,
                    name="SPACE 19-Slide Institutional Investment Memo",
                    description="One-off 19-slide 16:9 institutional catalog valuation memo PDF + 10Y DCF schedule",
                    add_on=True,
                    auto_enable=False,
                    amount_usd=299.0,
                    interval="one_off",
                    attach_action="purchase",
                    items=[
                        AutumnPlanItemSummary(
                            feature_id=AUTUMN_FEATURE_MEMO_PDF,
                            included=1,
                            unlimited=False,
                            reset_interval="one_off",
                            primary_text="1 19-Slide Institutional Investment Memo PDF",
                        )
                    ],
                ),
            ],
            execution_mode="LOCAL_LEDGER",
        )

    def open_customer_portal(
        self,
        *,
        customer_id: str,
        return_url: str = "https://spacemusic.io/valuation-memo",
    ) -> AutumnPortalResponse:
        """
        Calls `POST https://api.useautumn.com/v1/billing.open_customer_portal` to create
        a Stripe Billing Portal session for managing active subscriptions and invoices.
        """
        cid = _canonical_customer_id(customer_id)
        key = self.secret_key
        if key:
            self.get_or_create_customer(customer_id=cid)
            payload = json.dumps(
                {
                    "customer_id": cid,
                    "return_url": return_url,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/billing.open_customer_portal",
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    url = body.get("url") or body.get("portal_url")
                    if url:
                        return AutumnPortalResponse(
                            customer_id=cid,
                            portal_url=str(url),
                            execution_mode="LIVE_AUTUMN_API",
                        )
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                pass

        return AutumnPortalResponse(
            customer_id=cid,
            portal_url=f"https://billing.stripe.com/p/session/{cid}?return_url={urllib.parse.quote(return_url)}",
            execution_mode="LOCAL_LEDGER",
        )

    def attach_plan(
        self,
        *,
        customer_id: str,
        order_id: str,
        app_id: uuid.UUID,
        deal_code: str,
        artist_name: str,
        plan_tier: PaidMemoPlanTier,
        customer_name: Optional[str] = None,
        customer_email: Optional[str] = None,
    ) -> tuple[str, Optional[str], BillingProvider]:
        """
        Calls `POST https://api.useautumn.com/v1/billing.attach` to attach `single_memo_299`
        or `desk_pass_499` to `customer_id`, passing `checkoutSessionParams` with SPACE's
        order metadata.
        Returns `(session_id, payment_url, billing_provider)`.
        Note: Under Autumn's API contract, if `payment_url` (`paymentUrl` / `url`) is `None` in a
        live response, the customer's payment method on file already succeeded and the order can be
        unlocked immediately.
        """
        cid = _canonical_customer_id(customer_id)
        pricing = PLAN_PRICING[plan_tier]
        autumn_plan_id = str(pricing["autumn_plan_id"])
        success_url = (
            f"https://spacemusic.io/catalog-review/{app_id}/investment-memo.html"
            f"?order_id={order_id}&customer_id={urllib.parse.quote(cid)}&status=success"
        )
        key = self.secret_key
        if key:
            self.get_or_create_customer(
                customer_id=cid,
                name=customer_name or artist_name,
                email=customer_email,
            )
            payload = json.dumps(
                {
                    "customer_id": cid,
                    "plan_id": autumn_plan_id,
                    "success_url": success_url,
                    "checkout_session_params": {
                        "client_reference_id": order_id,
                        "metadata": {
                            "order_id": order_id,
                            "application_id": str(app_id),
                            "customer_id": cid,
                            "deal_code": deal_code,
                            "autumn_plan_id": autumn_plan_id,
                        },
                    },
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/billing.attach",
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    payment_url = (
                        body.get("payment_url")
                        or body.get("paymentUrl")
                        or body.get("checkout_url")
                        or body.get("url")
                    )
                    session_id = str(
                        body.get("stripe_session_id")
                        or body.get("id")
                        or f"aut_cs_{hashlib.sha256(f'{order_id}:{customer_id}'.encode()).hexdigest()[:20]}"
                    )
                    return session_id, payment_url, BillingProvider.AUTUMN
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                pass

        # Fallback to direct Stripe Checkout if `STRIPE_SECRET_KEY` is set without `AUTUMN_SECRET_KEY`
        if os.environ.get("STRIPE_SECRET_KEY"):
            session_id, checkout_url = _create_stripe_checkout_session(
                order_id=order_id,
                app_id=app_id,
                deal_code=deal_code,
                artist_name=artist_name,
                plan_tier=plan_tier,
            )
            return session_id, checkout_url, BillingProvider.STRIPE_DIRECT

        # Deterministic Autumn-backed Stripe Checkout URL in local/test mode
        session_id = f"cs_autumn_{hashlib.sha256(f'{order_id}:{app_id}:{customer_id}'.encode()).hexdigest()[:22]}"
        checkout_url = (
            f"https://checkout.useautumn.com/c/pay/{session_id}"
            f"?order_id={order_id}&customer_id={urllib.parse.quote(customer_id)}&plan_id={autumn_plan_id}"
        )
        return session_id, checkout_url, BillingProvider.AUTUMN


class PaidMemoStore:
    """
    In-memory order, deck, and Autumn entitlement store indexed by `order_id`,
    `application_id`, `stripe_session_id`, and `customer_id`.
    """

    def __init__(self, autumn_client: Optional[AutumnBillingClient] = None) -> None:
        self._orders_by_id: Dict[str, PaidMemoOrder] = {}
        self._orders_by_app: Dict[uuid.UUID, PaidMemoOrder] = {}
        self._orders_by_session: Dict[str, PaidMemoOrder] = {}
        self.autumn = autumn_client or AutumnBillingClient()

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
    Verifies Stripe / Autumn webhook `Stripe-Signature: t=<timestamp>,v1=<hmac_sha256>` header.
    """
    secret = (
        webhook_secret
        or os.environ.get("AUTUMN_WEBHOOK_SECRET")
        or os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_space_memo_default_secret")
    )
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
    Evaluates the catalog via `SpaceValuationEngine` + `ClaudeMemoGenerator`, checks Autumn
    entitlement balance (`POST /v1/balances.check`), and either:
      1. Atomically deducts 1 credit from the customer's active Autumn `desk_pass_499` / credit balance
         and unlocks all 19 slides immediately (`PaymentStatus.PAID`), or
      2. Attaches the requested plan via Autumn (`POST /v1/billing.attach`) and returns the
         Autumn/Stripe `checkout_url` (`PaymentStatus.PENDING_PAYMENT`).
    """
    eng = engine or SpaceValuationEngine()
    app_id = req.application_id or uuid.uuid4()
    customer_id = _normalize_customer_id(req.customer_id, req.contact_email, req.artist_or_label_name)

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
    pricing = PLAN_PRICING[req.plan_tier]
    autumn_plan_id = str(pricing["autumn_plan_id"])
    is_waived = (req.coupon_code or "").strip().upper() in VIP_WAIVER_COUPONS
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    locked_url = f"/catalog-review/{app_id}/investment-memo.html"
    unlocked_html = f"/catalog-review/{app_id}/investment-memo.html?receipt_token={receipt_token}"
    unlocked_pdf = f"/catalog-review/{app_id}/investment-memo.pdf?receipt_token={receipt_token}"

    # 0. Resolve customer in Autumn first (`customers.get_or_create` per autumn-integrate)
    store.autumn.get_or_create_customer(
        customer_id=customer_id,
        name=req.contact_name or req.artist_or_label_name,
        email=req.contact_email,
    )

    # 1. Check if customer already has available Autumn `investment_memo_pdf` credits (e.g. Desk Pass)
    balance_check = store.autumn.check_balance(
        customer_id=customer_id,
        feature_id=AUTUMN_FEATURE_MEMO_PDF,
        required_balance=1,
        send_event=True,
    )

    if is_waived:
        payment_status = PaymentStatus.PAID
        billing_provider = BillingProvider.PARTNER_WAIVER
        session_id = f"waived_{order_id}"
        checkout_url = unlocked_html
        amount_usd = 0.0
        amount_eur = 0.0
        credits_remaining = balance_check.remaining_balance
    elif balance_check.allowed:
        # Customer had an active Autumn Desk Pass / credit balance; 1 credit was atomically deducted!
        payment_status = PaymentStatus.PAID
        billing_provider = BillingProvider.AUTUMN
        session_id = f"aut_bal_{order_id}"
        checkout_url = unlocked_html
        amount_usd = 0.0
        amount_eur = 0.0
        credits_remaining = balance_check.remaining_balance
    else:
        # 2. Attach plan via Autumn (`POST /v1/billing.attach`) to get Checkout URL
        session_id, payment_url, billing_provider = store.autumn.attach_plan(
            customer_id=customer_id,
            order_id=order_id,
            app_id=app_id,
            deal_code=deck.deal_code,
            artist_name=req.artist_or_label_name,
            plan_tier=req.plan_tier,
            customer_name=req.contact_name or req.artist_or_label_name,
            customer_email=req.contact_email,
        )
        if payment_url is None:
            # Autumn attached the plan immediately using customer's saved card on file
            snap = store.autumn.provision_plan_credits(
                customer_id=customer_id,
                plan_tier=req.plan_tier,
                feature_id=AUTUMN_FEATURE_MEMO_PDF,
                consume_immediately=1,
            )
            payment_status = PaymentStatus.PAID
            checkout_url = unlocked_html
            credits_remaining = snap.remaining_balance
        else:
            payment_status = PaymentStatus.PENDING_PAYMENT
            checkout_url = payment_url
            credits_remaining = balance_check.remaining_balance
        amount_usd = pricing["amount_usd"]
        amount_eur = pricing["amount_eur"]

    order = PaidMemoOrder(
        order_id=order_id,
        application_id=app_id,
        customer_id=customer_id,
        deal_code=deck.deal_code,
        artist_or_label_name=req.artist_or_label_name,
        plan_tier=req.plan_tier,
        autumn_plan_id=autumn_plan_id,
        autumn_feature_id=AUTUMN_FEATURE_MEMO_PDF,
        billing_provider=billing_provider,
        amount_usd=amount_usd,
        amount_eur=amount_eur,
        payment_status=payment_status,
        stripe_session_id=session_id,
        checkout_url=checkout_url,
        receipt_token=receipt_token,
        locked_preview_url=locked_url,
        unlocked_html_url=unlocked_html,
        unlocked_pdf_url=unlocked_pdf,
        autumn_credits_remaining=credits_remaining,
        created_at_utc=now_iso,
        paid_at_utc=now_iso if payment_status == PaymentStatus.PAID else None,
        deck=deck,
    )
    store.save(order)

    return PaidMemoCheckoutResponse(
        order_id=order.order_id,
        application_id=order.application_id,
        customer_id=order.customer_id,
        deal_code=order.deal_code,
        artist_or_label_name=order.artist_or_label_name,
        plan_tier=order.plan_tier,
        autumn_plan_id=order.autumn_plan_id,
        autumn_feature_id=order.autumn_feature_id,
        billing_provider=order.billing_provider,
        amount_usd=order.amount_usd,
        amount_eur=order.amount_eur,
        payment_status=order.payment_status,
        stripe_session_id=order.stripe_session_id,
        checkout_url=order.checkout_url,
        locked_preview_url=order.locked_preview_url,
        unlocked_html_url=order.unlocked_html_url if order.payment_status == PaymentStatus.PAID else None,
        unlocked_pdf_url=order.unlocked_pdf_url if order.payment_status == PaymentStatus.PAID else None,
        receipt_token=order.receipt_token if order.payment_status == PaymentStatus.PAID else None,
        autumn_credits_remaining=order.autumn_credits_remaining,
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
    powered by Autumn (`useautumn.com`) + Stripe where users can upload distributor CSV/TSV
    files, preview Slides 01–02 for free, check/consume Desk Pass credits, or pay $299 to
    download the full 19-slide 16:9 PDF.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SPACE Institutional Catalog Valuation Memo Studio | Claude + Autumn Billing + DTW DCF</title>
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
  .plans-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }
  .plan-card {
    background: #141720;
    border: 1px solid #252A3A;
    border-radius: 8px;
    padding: 14px;
    font-size: 12px;
  }
  .plan-card strong { font-size: 13px; color: #84B1FF; display: block; margin-bottom: 4px; }
  .plan-price { font-size: 16px; font-weight: 800; color: #FFFFFF; margin: 6px 0; }
</style>
</head>
<body>
  <div class="topbar">
    <div class="brand">SPACE</div>
    <div class="badge">CLAUDE + AUTUMN BILLING · 19-SLIDE 16:9 INVESTMENT MEMO</div>
  </div>
  <div class="container">
    <div class="panel">
      <h1>Generate Catalog Investment Memo</h1>
      <p class="lead">
        Run our 10,000-path Monte Carlo DCF, Dynamic Time Warping (DTW), and TypeSafe AI (JEV)
        forensics engine. Preview Slides 01–02 free, or unlock the full 19-slide 16:9 PDF via Autumn + Stripe ($299 single memo or $499/mo Desk Pass).
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
            <label>Customer Email / Autumn ID</label>
            <input type="email" id="contact_email" placeholder="mgmt@hmwme.com">
          </div>
          <div>
            <label>Primary Distributor</label>
            <input type="text" id="distributor" value="DistroKid + Amuse">
          </div>
        </div>
        <div class="row-2">
          <div>
            <label>Claimed / Trailing LTM ($ USD)</label>
            <input type="number" id="ltm_amount" value="80000" step="100">
          </div>
          <div>
            <label>Partner / VIP Code (Optional)</label>
            <input type="text" id="coupon_code" placeholder="e.g. SPACE-PARTNER-VIP">
          </div>
        </div>
        <label>Paste Raw Distributor CSV / TSV Rows (Optional — upgrades to Stage 2 Verified)</label>
        <textarea id="raw_csv" rows="4" placeholder="reporting_month,title,isrc,store,country,quantity,net_royalty_usd..."></textarea>
        <label>Autumn Plan (`billing.attach` / `balances.check`)</label>
        <select id="plan_tier">
          <option value="SINGLE_MEMO_299">single_memo_299 — Single 19-Slide Memo PDF ($299 / €275)</option>
          <option value="DESK_PASS_499">desk_pass_499 — Label / Manager Desk Pass (10 Memos/mo · $499/mo)</option>
        </select>
        <button type="submit" class="btn-primary">Run Engine &amp; Build 19-Slide Memo</button>
      </form>
    </div>
    <div>
      <div id="autumnPlansGrid" class="plans-grid"></div>
      <div id="actionBar" class="action-bar">
        <div id="statusSummary" style="font-size: 13px;"></div>
        <div class="action-links" id="actionLinks"></div>
      </div>
      <iframe id="deckIframe" class="preview-frame" title="SPACE 19-Slide Investment Memo Preview"></iframe>
    </div>
  </div>
<script>
async function loadAutumnCatalogPlans() {
  var emailVal = document.getElementById("contact_email").value || "";
  var qs = emailVal ? "?customer_id=" + encodeURIComponent(emailVal) : "";
  var res = await fetch("/catalog-review/paid-memo/autumn/plans" + qs);
  if (!res.ok) return;
  var data = await res.json();
  var grid = document.getElementById("autumnPlansGrid");
  if (!grid || !data.plans) return;
  grid.innerHTML = data.plans.map(function(p) {
    var priceStr = p.amount_usd != null ? ("$" + p.amount_usd + (p.interval === "month" ? "/mo" : " one-off")) : "Free (auto-enabled)";
    var itemsStr = (p.items || []).map(function(i) { return i.primary_text || (i.included + " " + i.feature_id); }).join(" · ");
    return '<div class="plan-card"><strong>' + p.name + ' (' + p.plan_id + ')</strong><div class="plan-price">' + priceStr + '</div><div style="color:#9BA3B8">' + itemsStr + '</div></div>';
  }).join("");
}
loadAutumnCatalogPlans();
document.getElementById("memoForm").addEventListener("submit", async function(e) {
  e.preventDefault();
  var payload = {
    artist_or_label_name: document.getElementById("artist_name").value,
    catalog_title: document.getElementById("catalog_title").value,
    contact_email: document.getElementById("contact_email").value || null,
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
    "</strong> · WACC: " + data.teaser_wacc_pct + "% · Autumn Credits Remaining: <strong>" + data.autumn_credits_remaining + "</strong>";
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
