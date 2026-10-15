"""
Autonomous Inbox-to-Underwriting Statement Ingestor (`services/spacemusic/inbox_ingestor.py`)

Automates the transition from Stage 1 (`AWAITING_STATEMENTS`) to Stage 2
(`STAGE_2_STATEMENT_VERIFIED` + Institutional Deal Memo) when an artist replies to
`hello@spacemusic.io` with royalty attachments:

1. Matches incoming email replies (`sender_email`, `subject`, `body_text`) to the
   corresponding `CatalogApplication` in SPACE's pipeline (or auto-creates one if new).
2. Unpacks and merges multi-file attachments:
   - Single or multiple `.csv` / `.tsv` / `.txt` files (e.g. 24 monthly UnitedMasters CSVs).
   - `.zip` archives containing multiple monthly CSV/TSV royalty statements.
   - Base64-encoded attachment payloads (from Gmail / Superhuman / SendGrid / Postmark webhooks).
3. Runs `parse_statement_csv()` across all extracted files, deduplicating/merging rows into
   a unified `ParsedStatementSummary` (with track-level `TrackInput`, `MonthlyStatementPoint`,
   DSP & country shares, and empirical RPM benchmarks).
4. Executes `SpaceValuationEngine.evaluate()` in Stage 2 (`statements_verified=True`),
   triggering Winsorization, Empirical Bayes track survival shrinkage, DTW Step-Plateau
   bot detection, and AI/Fake profile validation.
5. Automatically runs `route_catalog_to_institutional_buyers()` to match the verified
   catalog against SPACE's 8 institutional buyers (`Duetti`, `Create Music Group`,
   `beatBread`, `Sound Royalties`, `ANote Music`, `Royalty Exchange`, `SongVest`, `Symphonic`)
   and generates both the Stage 2 Seller Offer Draft and the Institutional Deal Card.
"""

from __future__ import annotations

import base64
import io
import zipfile
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, Field

from services.valuation.engine import (
    CatalogValuationOutput,
    SpaceValuationEngine,
)
from services.valuation.statement_parser import (
    ParsedStatementSummary,
    convert_xlsx_to_csv_text,
    merge_statement_summaries,
    parse_statement_csv,
)

from .buyer_router import (
    InstitutionalRoutingReport,
    route_catalog_to_institutional_buyers,
)
from .closing_pack import (
    BlindDealTeaser,
    IsrcCollisionAlert,
    generate_blind_deal_teaser,
)
from .models import CatalogApplication, ReplyDraft
from .typeform_adapter import (
    application_to_valuation_input,
    generate_reply_draft,
    sanitize_email,
)


class InboundAttachmentPayload(BaseModel):
    filename: str
    content_text: str | None = None
    content_base64: str | None = None
    content_type: str | None = None


class InboundEmailStatementWebhook(BaseModel):
    sender_email: str
    sender_name: str | None = None
    subject: str | None = None
    body_text: str | None = None
    application_id: str | None = None
    default_currency: str = "USD"
    attachments: list[InboundAttachmentPayload] = Field(default_factory=list)


class AutonomousStage2UnderwritingResult(BaseModel):
    application_id: str
    matched_existing_application: bool
    statements_verified: bool = False
    sender_verified: bool = True
    quarantined: bool = False
    quarantine_reason: str | None = None
    artist_or_label_name: str
    contact_email: str
    files_processed: list[str]
    detected_distributor: str
    statement_summary: ParsedStatementSummary
    valuation: CatalogValuationOutput
    seller_offer_draft: ReplyDraft
    institutional_routing: InstitutionalRoutingReport
    blind_deal_teaser: BlindDealTeaser | None = None
    isrc_collision_alerts: list[IsrcCollisionAlert] = Field(default_factory=list)
    slack_deal_card_markdown: str


def _extract_csv_texts_from_attachments(
    attachments: Sequence[InboundAttachmentPayload],
) -> list[tuple[str, str]]:
    """
    Extracts `(filename, decoded_csv_text)` pairs from raw text, base64, `.xlsx` Excel
    workbooks, or `.zip` archives (containing `.csv`, `.tsv`, `.txt`, or `.xlsx` files).
    """
    extracted: list[tuple[str, str]] = []
    for att in attachments:
        fname = (att.filename or "statement.csv").strip()
        raw_bytes: bytes | None = None

        if att.content_base64:
            try:
                raw_bytes = base64.b64decode(att.content_base64)
            except (ValueError, TypeError):
                raw_bytes = att.content_base64.encode("utf-8", errors="replace")
        elif att.content_text is not None:
            raw_bytes = att.content_text.encode("utf-8")

        if not raw_bytes:
            continue

        is_xlsx = fname.lower().endswith(".xlsx")
        if is_xlsx:
            try:
                csv_text = convert_xlsx_to_csv_text(raw_bytes, filename=fname)
                if csv_text.strip():
                    extracted.append((fname, csv_text))
                continue
            except (ValueError, KeyError, zipfile.BadZipFile, OSError):
                is_xlsx = False

        if fname.lower().endswith(".zip") or (raw_bytes[:4] == b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                    names = zf.namelist()
                    # Check if this PK zip is actually an unmarked .xlsx OpenXML workbook
                    if "xl/workbook.xml" in names:
                        csv_text = convert_xlsx_to_csv_text(raw_bytes, filename=fname)
                        if csv_text.strip():
                            extracted.append((fname, csv_text))
                        continue
                    for member in sorted(names):
                        base_member = member.rsplit("/", 1)[-1]
                        if member.endswith("/") or member.startswith("__MACOSX") or base_member.startswith("._"):
                            continue
                        m_lower = member.lower()
                        if m_lower.endswith(".xlsx"):
                            m_bytes = zf.read(member)
                            csv_text = convert_xlsx_to_csv_text(m_bytes, filename=member)
                            if csv_text.strip():
                                extracted.append((member, csv_text))
                        elif any(m_lower.endswith(ext) for ext in (".csv", ".tsv", ".txt")):
                            member_bytes = zf.read(member)
                            extracted.append(
                                (member, member_bytes.decode("utf-8-sig", errors="replace"))
                            )
            except zipfile.BadZipFile:
                pass
        else:
            extracted.append((fname, raw_bytes.decode("utf-8-sig", errors="replace")))

    return extracted


def combine_csv_statement_texts(file_pairs: Sequence[tuple[str, str]]) -> str:
    """
    Combines multiple CSV/TSV files from the same distributor (e.g. 12 monthly CSVs)
    by keeping the header of the first non-empty file and appending data rows from
    subsequent files whose header matches.
    """
    if not file_pairs:
        return ""
    if len(file_pairs) == 1:
        return file_pairs[0][1]

    combined_lines: list[str] = []
    primary_header: str | None = None

    for _, text in file_pairs:
        lines = [ln for ln in text.lstrip("\ufeff").splitlines() if ln.strip()]
        if not lines:
            continue
        header = lines[0].strip()
        if primary_header is None:
            primary_header = header
            combined_lines.append(lines[0])
            combined_lines.extend(lines[1:])
        else:
            if header.lower() == primary_header.lower():
                combined_lines.extend(lines[1:])
            else:
                combined_lines.extend(lines[1:])

    return "\n".join(combined_lines)


def parse_multi_attachment_statements(
    file_pairs: Sequence[tuple[str, str | bytes]],
    *,
    default_currency: str = "USD",
) -> ParsedStatementSummary:
    """
    Parses one or more extracted statement files (`(filename, csv_text_or_bytes)`).
    - Raw `.xlsx` bytes are automatically converted via `convert_xlsx_to_csv_text()`.
    - Files sharing the exact same schema header are grouped and parsed together.
    - Heterogeneous statement schemas (e.g. a Symphonic `.csv` + a YouTube Studio `.xlsx`,
      or a DistroKid `.xlsx` + an Amuse `.xlsx`) are parsed individually with their
      respective schema/currency detectors and merged via `merge_statement_summaries()`.
    """
    if not file_pairs:
        return ParsedStatementSummary(detected_distributor="Empty", row_count=0)

    normalized_pairs: list[tuple[str, str]] = []
    for fname, raw_val in file_pairs:
        if isinstance(raw_val, bytes):
            if fname.lower().endswith(".xlsx") or raw_val[:4] == b"PK\x03\x04":
                txt = convert_xlsx_to_csv_text(raw_val, filename=fname)
            else:
                txt = raw_val.decode("utf-8-sig", errors="replace")
        else:
            txt = raw_val
        normalized_pairs.append((fname, txt))

    if len(normalized_pairs) == 1:
        return parse_statement_csv(normalized_pairs[0][1], default_currency=default_currency)

    # Group by header line unless the file is a YouTube Studio workbook (which should be parsed individually first so Last 365 vs Lifetime deduplication works cleanly)
    header_groups: dict[str, list[tuple[str, str]]] = {}
    individual_summaries: list[ParsedStatementSummary] = []

    for fname, text in normalized_pairs:
        lines = [ln for ln in text.lstrip("\ufeff").splitlines() if ln.strip()]
        if not lines:
            continue
        hdr_key = lines[0].strip().lower()
        is_yt_studio_hdr = any(
            k in hdr_key for k in ("titre de la vidéo", "video title", "vues engagées", "engaged views")
        )
        if fname.lower().endswith(".xlsx") or is_yt_studio_hdr:
            individual_summaries.append(
                parse_statement_csv(text, default_currency=default_currency)
            )
        else:
            header_groups.setdefault(hdr_key, []).append((fname, text))

    for grp in header_groups.values():
        combined_txt = combine_csv_statement_texts(grp)
        individual_summaries.append(
            parse_statement_csv(combined_txt, default_currency=default_currency)
        )

    return merge_statement_summaries(individual_summaries)



def match_application_by_email_or_subject(
    applications: Iterable[CatalogApplication],
    *,
    sender_email: str,
    subject: str | None = None,
    application_id: str | None = None,
) -> CatalogApplication | None:
    app_list = list(applications)
    if application_id:
        for app in app_list:
            if str(app.id) == str(application_id):
                return app

    clean_sender = sanitize_email(sender_email).lower()
    if clean_sender:
        email_matches = [
            app for app in app_list if sanitize_email(app.contact_email).lower() == clean_sender
        ]
        if email_matches:
            # Prefer the one with highest declared LTM or most recent
            email_matches.sort(key=lambda a: (a.declared_ltm_amount, a.created_at), reverse=True)
            return email_matches[0]

    if subject:
        subj_lower = subject.lower()
        for app in app_list:
            artist = (app.artist_or_label_name or "").strip().lower()
            if artist and len(artist) >= 3 and artist in subj_lower:
                return app

    return None


def _build_slack_deal_card(
    app_row: CatalogApplication,
    stmt: ParsedStatementSummary,
    valuation: CatalogValuationOutput,
    routing: InstitutionalRoutingReport,
) -> str:
    dtw_arch = (
        valuation.dtw_analysis.matched_archetype.value
        if valuation.dtw_analysis
        else "COHORT_PRIOR"
    )
    top_buyers_str = (
        ", ".join(f"*{b.partner_name}* ({b.fit_score:.0f}%)" for b in routing.recommended_buyers[:3])
        if routing.eligible_for_syndication and routing.recommended_buyers
        else f"Not eligible ({routing.disqualification_reason or 'Hold'})"
    )
    return (
        f"*:rocket: SPACE Stage 2 Autonomous Underwriting Complete — {app_row.artist_or_label_name}*\n"
        f"> *Seller:* {app_row.contact_name} (`{app_row.contact_email}`) | *Distributor:* `{stmt.detected_distributor}` ({stmt.months_covered}m, {stmt.row_count} rows)\n"
        f"> *Verified Normalized LTM ($CF_0$):* *€{valuation.baseline.effective_cf0_eur:,.2f}* (Declared: {app_row.declared_ltm_amount:,.0f} {app_row.declared_currency})\n"
        f"> *Stage 2 DCF Offer Range:* *€{valuation.price_low_eur:,.0f} – €{valuation.price_high_eur:,.0f}* (Target: *€{valuation.price_median_eur:,.0f}* / `{valuation.implied_ltm_multiple_median:.2f}x`)\n"
        f"> *Forensics:* Integrity `{valuation.integrity_score:.0f}/100` | DTW Archetype: `{dtw_arch}` | Track HHI: `{valuation.track_hhi:.2f}`\n"
        f"> *Top Institutional Buyers:* {top_buyers_str}"
    )


def ingest_inbound_email_statements(
    webhook: InboundEmailStatementWebhook,
    *,
    applications_store: dict[Any, CatalogApplication],
    engine: SpaceValuationEngine | None = None,
    reference_date: date | None = None,
) -> AutonomousStage2UnderwritingResult:
    """
    End-to-end Inbox-to-Underwriting pipeline:
    1. Matches incoming email to existing Stage 1 `CatalogApplication` (or creates a new record).
    2. Extracts and merges all attached `.csv` / `.tsv` / `.zip` files.
    3. Parses track-level and monthly series via `parse_statement_csv()`.
    4. Upgrades the application to `STAGE_2_STATEMENT_VERIFIED` and evaluates via `SpaceValuationEngine`.
    5. Routes the catalog to SPACE's 8 institutional buyers (`route_catalog_to_institutional_buyers`).
    6. Returns the Seller Offer Draft, Institutional Underwriting Memo, and Slack Deal Card.
    """
    eng = engine or SpaceValuationEngine()
    matched_app = match_application_by_email_or_subject(
        applications_store.values(),
        sender_email=webhook.sender_email,
        subject=webhook.subject,
        application_id=webhook.application_id,
    )
    was_existing = matched_app is not None

    file_pairs = _extract_csv_texts_from_attachments(webhook.attachments)

    currency = (
        matched_app.declared_currency
        if matched_app and matched_app.declared_currency
        else webhook.default_currency
    )
    stmt_summary = parse_multi_attachment_statements(
        file_pairs, default_currency=currency
    )
    has_valid_statements = bool(
        stmt_summary.row_count > 0
        and (stmt_summary.total_net_royalty_eur > 0.0 or stmt_summary.ltm_net_royalty_eur > 0.0)
    )

    clean_inbound_sender = sanitize_email(webhook.sender_email or "").lower().strip()
    sender_verified = True
    quarantine_reason: str | None = None

    if matched_app is not None:
        registered_email = sanitize_email(matched_app.contact_email or "").lower().strip()
        if not clean_inbound_sender or not registered_email or clean_inbound_sender != registered_email:
            sender_verified = False
            quarantine_reason = (
                f"Inbound sender email '{webhook.sender_email}' does not match registered applicant email "
                f"'{matched_app.contact_email}'."
            )
        elif not has_valid_statements:
            quarantine_reason = (
                "No valid royalty statement rows or positive net royalties found in inbound attachments."
            )
    else:
        if not has_valid_statements:
            quarantine_reason = (
                "No valid royalty statement rows or positive net royalties found in inbound attachments."
            )
        inferred_artist = (
            stmt_summary.tracks[0].title
            if stmt_summary.tracks and not webhook.sender_name
            else (webhook.sender_name or "Inbound Artist Catalog")
        )
        matched_app = CatalogApplication(
            contact_name=webhook.sender_name or "Artist",
            contact_email=sanitize_email(webhook.sender_email),
            artist_or_label_name=inferred_artist,
            declared_ltm_amount=stmt_summary.ltm_net_royalty_eur,
            declared_currency="EUR",
            distributor_or_admin=stmt_summary.detected_distributor,
            statements_verified=has_valid_statements,
        )
        if has_valid_statements:
            applications_store[matched_app.id] = matched_app

    is_quarantined = bool(not sender_verified or not has_valid_statements)
    if is_quarantined:
        # Do NOT mutate existing application's statements_verified or overwrite store state!
        val_input = application_to_valuation_input(matched_app)
        val_input.statements_verified = bool(was_existing and matched_app.statements_verified)
        valuation = eng.evaluate(val_input, reference_date=reference_date)
        seller_offer_draft = generate_reply_draft(matched_app, valuation)
        routing_report = route_catalog_to_institutional_buyers(matched_app, valuation)
        slack_card = (
            f"*:warning: SPACE Inbound Statement Quarantined — {matched_app.artist_or_label_name}*\n"
            f"> *Reason:* {quarantine_reason}\n"
            f"> *Inbound Sender:* `{webhook.sender_email}` | *Registered:* `{matched_app.contact_email}`\n"
            f"> *Parsed Rows:* `{stmt_summary.row_count}`"
        )
        return AutonomousStage2UnderwritingResult(
            application_id=str(matched_app.id),
            matched_existing_application=was_existing,
            statements_verified=False,
            sender_verified=sender_verified,
            quarantined=True,
            quarantine_reason=quarantine_reason,
            artist_or_label_name=matched_app.artist_or_label_name,
            contact_email=matched_app.contact_email,
            files_processed=[fp[0] for fp in file_pairs],
            detected_distributor=stmt_summary.detected_distributor,
            statement_summary=stmt_summary,
            valuation=valuation,
            seller_offer_draft=seller_offer_draft,
            institutional_routing=routing_report,
            blind_deal_teaser=None,
            slack_deal_card_markdown=slack_card,
        )

    matched_app.statements_verified = True
    if not matched_app.distributor_or_admin or matched_app.distributor_or_admin == "Standard CSV":
        matched_app.distributor_or_admin = stmt_summary.detected_distributor

    val_input = application_to_valuation_input(matched_app)
    val_input.statements_verified = True
    val_input.monthly_history = stmt_summary.monthly_history
    val_input.tracks = stmt_summary.tracks
    val_input.dsp_share = stmt_summary.dsp_share
    val_input.country_share = stmt_summary.country_share

    valuation = eng.evaluate(val_input, reference_date=reference_date)
    seller_offer_draft = generate_reply_draft(matched_app, valuation)
    routing_report = route_catalog_to_institutional_buyers(matched_app, valuation)
    blind_teaser = generate_blind_deal_teaser(
        matched_app,
        valuation,
        routing=routing_report,
    )

    # Update application state in store
    matched_app.pipeline_status = valuation.pipeline_status
    matched_app.valuation_stage = valuation.valuation_stage
    matched_app.effective_cf0_eur = valuation.baseline.effective_cf0_eur
    matched_app.price_low_eur = valuation.price_low_eur
    matched_app.price_median_eur = valuation.price_median_eur
    matched_app.price_high_eur = valuation.price_high_eur
    matched_app.implied_multiple_median = valuation.implied_ltm_multiple_median
    matched_app.discount_rate = valuation.discount_rate.total_discount_rate
    matched_app.integrity_score = valuation.integrity_score
    matched_app.valuation_confidence = valuation.valuation_confidence
    matched_app.valuation_report_json = (
        valuation.model_dump() if hasattr(valuation, "model_dump") else valuation.dict()
    )
    matched_app.draft_reply_subject = seller_offer_draft.subject
    matched_app.draft_reply_body = seller_offer_draft.body
    matched_app.updated_at = datetime.now(UTC).replace(tzinfo=None)

    slack_card = _build_slack_deal_card(matched_app, stmt_summary, valuation, routing_report)

    return AutonomousStage2UnderwritingResult(
        application_id=str(matched_app.id),
        matched_existing_application=was_existing,
        statements_verified=True,
        sender_verified=True,
        quarantined=False,
        quarantine_reason=None,
        artist_or_label_name=matched_app.artist_or_label_name,
        contact_email=matched_app.contact_email,
        files_processed=[fp[0] for fp in file_pairs],
        detected_distributor=stmt_summary.detected_distributor,
        statement_summary=stmt_summary,
        valuation=valuation,
        seller_offer_draft=seller_offer_draft,
        institutional_routing=routing_report,
        blind_deal_teaser=blind_teaser,
        slack_deal_card_markdown=slack_card,
    )
