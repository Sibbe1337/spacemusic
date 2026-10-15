"""
Regression tests for all findings in the read-only release audit
(`SPACE MUSIC – LÄSANDE RELEASEGRANSKNING` on commit `b8e874e2ccfa54fd987c2a9c0b45320a01f9314d`):

- Finding A: Never fabricate ledger rows / monthly history when statements are missing;
  propagate step-plateau & high fraud scores into the memo; mark local JEV fallback as
  deterministic model-derived rather than an independent external AI call.
- Finding B.1: Fix percentage double-scaling in deal structures (90% / 10%, never 9000% / -8900%).
- Finding B.2: Fix European comma decimal parsing in `statement_parser.py` ("1,23" -> 1.23,
  12 rows of "1,23" EUR -> 14.76 EUR, reject ambiguous "1,234").
- Additional Checks:
  - Tenet institutional model binds to `workbook_audit` cash flows and marks synthetic benchmark.
  - `buyer_router.py` respects `RightsScope` (PUBLISHING does not match MASTERS-only buyers)
    and never marks Stage 1 / unverified catalogs `READY_FOR_BUYER_SYNDICATION`.
  - `inbox_ingestor.py` requires >=1 parsed statement row with positive royalties AND
    matching sender email before setting `statements_verified=True`.
"""

from __future__ import annotations

import base64
from datetime import date

import pytest

from services.spacemusic.buyer_router import route_catalog_to_institutional_buyers
from services.spacemusic.inbox_ingestor import (
    InboundAttachmentPayload,
    InboundEmailStatementWebhook,
    ingest_inbound_email_statements,
)
from services.spacemusic.models import CatalogApplication
from services.valuation.claude_memo_generator import generate_catalog_investment_memo_deck
from services.valuation.dtw_matcher import evaluate_dtw_lifecycle
from services.valuation.engine import (
    CatalogValuationInput,
    MonthlyStatementPoint,
    RightsScope,
    SpaceValuationEngine,
    TrackInput,
)
from services.valuation.jev_evaluator import (
    build_jev_state_payload,
    call_typesafe_systemone,
    run_parallel_dtw_and_jev_evaluation,
)
from services.valuation.statement_parser import (
    StatementParseError,
    _parse_float,
    parse_statement_csv,
)


def test_finding_a_unverified_synthetic_intake_never_fabricates_rows_or_bars():
    """
    When `statements_verified=False` and no statement summary, tracks, or monthly history
    are provided, the memo generator must NOT fabricate 1,200 ledger rows, 1,000,000 streams,
    12 monthly history bars, or 3 dummy tracks.
    """
    app_input = CatalogValuationInput(
        catalog_title="Synthetic Indicative Catalog",
        artist_or_label_name="Unverified Indie Artist",
        declared_ltm_amount=40000.0,
        declared_currency="USD",
        statements_verified=False,
        monthly_history=[],
        tracks=[],
    )
    engine = SpaceValuationEngine(random_seed=42)
    valuation = engine.evaluate(app_input, reference_date=date(2026, 10, 15))
    deck = generate_catalog_investment_memo_deck(
        app_input=app_input,
        valuation=valuation,
        stmt_summary=None,
    )

    assert deck.statements_verified is False
    assert deck.verification_status == "INDICATIVE / UNVERIFIED INTAKE — NO ROYALTY STATEMENTS PROVIDED"
    assert deck.s02_primary_count == "0"
    assert deck.s04_monthly_bars == []
    assert "UNVERIFIED / NO STATEMENT HISTORY PROVIDED" in deck.s04_footer_caption
    assert "UNVERIFIED" in deck.s01_headline.upper() or "UNVERIFIED" in deck.s01_bottom_note.upper()

    # Ensure none of the slides claim "1,200 verified ledger rows" or "statement-verified" as fact
    full_json = deck.model_dump_json() if hasattr(deck, "model_dump_json") else deck.json()
    assert "1,200" not in full_json
    assert "No artificial step plateau" not in full_json
    assert "Organic listening, not farmed streams" not in full_json


def test_finding_a_step_plateau_and_high_fraud_score_propagate_into_memo_and_jev():
    """
    When a catalog exhibits an artificial step-plateau or elevated JEV fraud probability,
    both JEV and the 19-slide memo must flag the manipulation risk and NEVER output
    'Organic listening, not farmed streams' or 'No artificial step plateau'.
    """
    # Construct a 12-month history with a sharp step-function plateau (100 -> 10,000 flat)
    step_history = [
        MonthlyStatementPoint(period=f"2025-{m:02d}", net_royalties_eur=100.0, streams=30000)
        for m in range(1, 7)
    ] + [
        MonthlyStatementPoint(period=f"2025-{m:02d}", net_royalties_eur=10000.0, streams=3000000)
        for m in range(7, 13)
    ]
    tracks = [
        TrackInput(
            title="Bot Farmed Track A",
            isrc="USBOT2600001",
            release_date=date(2025, 1, 1),
            ltm_royalties_eur=30300.0,
            annual_streams=9090000,
            monthly_royalties_eur=[100.0] * 6 + [5000.0] * 6,
        ),
        TrackInput(
            title="Bot Farmed Track B",
            isrc="USBOT2600002",
            release_date=date(2025, 1, 1),
            ltm_royalties_eur=30300.0,
            annual_streams=9090000,
            monthly_royalties_eur=[100.0] * 6 + [5000.0] * 6,
        ),
    ]
    app_input = CatalogValuationInput(
        catalog_title="Suspicious Step Plateau Catalog",
        artist_or_label_name="StepBot Records",
        declared_ltm_amount=60600.0,
        declared_currency="EUR",
        statements_verified=True,
        monthly_history=step_history,
        tracks=tracks,
    )
    engine = SpaceValuationEngine(random_seed=42)
    valuation = engine.evaluate(app_input, reference_date=date(2026, 10, 15))
    dtw_res = valuation.dtw_analysis or evaluate_dtw_lifecycle(
        [pt.net_royalties_eur for pt in step_history]
    )
    assert dtw_res.is_artificial_step_plateau is True

    state = build_jev_state_payload(
        app_input=app_input,
        stmt_summary=None,
        valuation_report=valuation,
    )
    jev_run = call_typesafe_systemone(state=state, model="jev-1.14.0")
    assert jev_run.evaluation_mode == "deterministic_local_model"
    assert jev_run.is_independent_ai_evaluation is False
    assert "deterministic local cross-check" in jev_run.provenance_notice.lower()
    assert jev_run.fraud_likelihood_score >= 0.70
    assert len(jev_run.manipulation_flags) >= 1

    parallel_report = run_parallel_dtw_and_jev_evaluation(
        app_input=app_input,
        stmt_summary=None,
        valuation_report=valuation,
    )
    assert parallel_report.evaluation_mode == "deterministic_local_model"
    assert parallel_report.is_independent_ai_evaluation is False
    assert parallel_report.fraud_likelihood_score >= 0.70

    deck = generate_catalog_investment_memo_deck(
        app_input=app_input,
        valuation=valuation,
        stmt_summary=None,
    )
    assert deck.step_function_detected is True
    assert deck.fraud_likelihood_score >= 0.70
    assert deck.jev_evaluation_mode == "deterministic_local_model"
    assert deck.jev_is_independent_ai is False
    assert "deterministic" in deck.s07_jev_crosscheck_note.lower()

    deck_json = deck.model_dump_json() if hasattr(deck, "model_dump_json") else deck.json()
    assert "Organic listening, not farmed streams" not in deck_json
    assert "No artificial step plateau" not in deck_json
    assert "Zero bot/step-function manipulation" not in deck_json
    assert "STEP-PLATEAU" in deck.s11_headline.upper() or "MANIPULATION" in deck.s11_headline.upper()
    assert "FORENSIC HOLD" in deck.s17_bottom_note.upper() or "STEP-PLATEAU" in deck.s17_bottom_note.upper()


def test_finding_b1_deal_structure_percentage_never_double_scales():
    """
    Verifies that `valuation.deal_structure.upfront_pct` (90.0) and `holdback_pct` (10.0)
    are never multiplied by 100 again to produce 9000% and -8900%.
    """
    csv_text = (
        "reporting_month,title,isrc,store,country,quantity,net_royalty_usd,release_date\n"
        + "\n".join(
            f"2025-{m:02d},Track {m},USTEST2100{m:02d},Spotify,US,250000,4500.00,2021-01-15"
            for m in range(1, 13)
        )
    )
    stmt = parse_statement_csv(csv_text, default_currency="USD")
    app_input = CatalogValuationInput(
        catalog_title="Clean Percentage Test",
        artist_or_label_name="Nordic Masters AB",
        declared_ltm_amount=54000.0,
        declared_currency="USD",
        statements_verified=True,
        monthly_history=stmt.monthly_history,
        tracks=stmt.tracks,
        dsp_share=stmt.dsp_share,
        country_share=stmt.country_share,
    )
    engine = SpaceValuationEngine(random_seed=42)
    valuation = engine.evaluate(app_input, reference_date=date(2026, 10, 15))
    assert valuation.deal_structure is not None
    assert valuation.deal_structure.upfront_pct == pytest.approx(90.0)
    assert valuation.deal_structure.holdback_pct == pytest.approx(10.0)

    deck = generate_catalog_investment_memo_deck(
        app_input=app_input,
        valuation=valuation,
        stmt_summary=stmt,
    )
    opt_a = deck.s16_options[0]
    labels = [line.label for line in opt_a.breakdown_lines]
    values = [line.value for line in opt_a.breakdown_lines]
    assert any("90%" in lbl for lbl in labels)
    assert any("10%" in lbl for lbl in labels)
    assert all(not val.startswith("-$") for val in values)

    deck_json = deck.model_dump_json() if hasattr(deck, "model_dump_json") else deck.json()
    assert "9000%" not in deck_json
    assert "-8900%" not in deck_json


def test_finding_b2_european_comma_decimal_parsing_and_ambiguous_rejection():
    """
    Verifies:
    - Semicolon-separated CSV with 12 rows of `1,23` EUR parses to `14.76` EUR (matching `1.23` EUR).
    - European thousands + comma decimal `"1.234,56"` and `"1 234,56"` parse to `1234.56`.
    - Negative comma decimal `"-0,45"` parses to `-0.45`.
    - Ambiguous single-comma 3-digit string `"1,234"` and malformed `"1,23,45"` raise `StatementParseError`.
    """
    assert _parse_float("1,23") == pytest.approx(1.23)
    assert _parse_float("1.23") == pytest.approx(1.23)
    assert _parse_float("-0,45") == pytest.approx(-0.45)
    assert _parse_float("1.234,56") == pytest.approx(1234.56)
    assert _parse_float("1 234,56") == pytest.approx(1234.56)
    assert _parse_float("1,234.56") == pytest.approx(1234.56)

    for ambiguous in ("1,234", "-2,500", "1,23,45", "1.23.45"):
        with pytest.raises(StatementParseError):
            _parse_float(ambiguous)

    csv_comma = "reporting_month;title;isrc;store;country;quantity;net_royalty_eur\n" + "\n".join(
        f"2025-{m:02d};Euro Track;SE00125000{m:02d};Spotify;SE;1000;1,23"
        for m in range(1, 13)
    )
    csv_dot = "reporting_month,title,isrc,store,country,quantity,net_royalty_eur\n" + "\n".join(
        f"2025-{m:02d},Euro Track,SE00125000{m:02d},Spotify,SE,1000,1.23"
        for m in range(1, 13)
    )

    summary_comma = parse_statement_csv(csv_comma, default_currency="EUR")
    summary_dot = parse_statement_csv(csv_dot, default_currency="EUR")

    assert summary_comma.row_count == 12
    assert summary_comma.total_net_royalty_eur == pytest.approx(14.76, abs=1e-4)
    assert summary_comma.ltm_net_royalty_eur == pytest.approx(14.76, abs=1e-4)
    assert summary_comma.total_net_royalties == pytest.approx(14.76, abs=1e-4)
    assert summary_comma.total_net_royalty_eur == pytest.approx(summary_dot.total_net_royalty_eur, abs=1e-4)

    csv_ambiguous = (
        "reporting_month;title;isrc;store;country;quantity;net_royalty_eur\n"
        "2025-01;Ambiguous Track;SE0012500001;Spotify;SE;1000;1,234\n"
    )
    with pytest.raises(StatementParseError):
        parse_statement_csv(csv_ambiguous, default_currency="EUR")


def test_buyer_router_rights_scope_and_stage1_unverified_guard():
    """
    Verifies:
    1. A `PUBLISHING`-only catalog never matches `MASTERS`-only buyers (like Duetti, beatBread, Symphonic).
    2. A Stage 1 or `statements_verified=False` catalog never receives `eligible_for_syndication=True`
       or `routing_status="READY_FOR_BUYER_SYNDICATION"`.
    """
    engine = SpaceValuationEngine(random_seed=42)

    pub_input = CatalogValuationInput(
        catalog_title="Nordic Songbook Publishing",
        artist_or_label_name="Stockholm Writers Collective",
        rights_scope=RightsScope.PUBLISHING,
        declared_ltm_amount=85000.0,
        declared_currency="EUR",
        statements_verified=True,
        genres=["pop", "electronic"],
    )
    pub_val = engine.evaluate(pub_input, reference_date=date(2026, 10, 15))
    pub_app = CatalogApplication(
        artist_or_label_name="Stockholm Writers Collective",
        rights_scope="publishing",
        pipeline_status="STAGE_2_STATEMENT_VERIFIED",
        valuation_stage="STAGE_2_STATEMENT_VERIFIED",
        statements_verified=True,
    )
    pub_routing = route_catalog_to_institutional_buyers(pub_app, pub_val)

    masters_only_buyers = {"duetti", "beatbread", "symphonic_distribution"}
    for match in pub_routing.recommended_buyers:
        assert match.partner_id not in masters_only_buyers

    # Stage 1 / unverified catalog must NOT be eligible for syndication
    unverified_input = pub_input.model_copy(update={"statements_verified": False})
    unverified_val = engine.evaluate(unverified_input, reference_date=date(2026, 10, 15))
    stage1_app = CatalogApplication(
        artist_or_label_name="Stockholm Writers Collective",
        rights_scope="publishing",
        pipeline_status="STAGE_1_INITIAL",
        valuation_stage="STAGE_1_INDICATIVE",
        statements_verified=False,
    )
    stage1_routing = route_catalog_to_institutional_buyers(stage1_app, unverified_val)
    assert stage1_routing.eligible_for_syndication is False
    assert stage1_routing.routing_status == "AWAITING_STATEMENT_VERIFICATION"


def test_inbox_ingestor_rejects_empty_attachments_and_mismatched_sender():
    """
    Verifies that `ingest_inbound_email_statements` does NOT mark an existing application
    `statements_verified=True` when:
      1. Zero valid statement rows are parsed, OR
      2. The inbound email `sender_email` does not match the applicant's registered `contact_email`.
    """
    app_row = CatalogApplication(
        artist_or_label_name="Verified Artist",
        contact_email="owner@verifiedartist.com",
        distributor_or_admin="DistroKid",
        declared_ltm_amount=25000.0,
        declared_currency="EUR",
        pipeline_status="STAGE_1_INITIAL",
        valuation_stage="STAGE_1_INDICATIVE",
        statements_verified=False,
    )
    applications_store = {app_row.id: app_row}
    engine = SpaceValuationEngine(random_seed=42)

    # Case 1: Matching sender, but 0 attachments / 0 valid rows -> quarantined, stays unverified
    empty_webhook = InboundEmailStatementWebhook(
        sender_email="owner@verifiedartist.com",
        subject=f"Statements for {app_row.id}",
        application_id=str(app_row.id),
        attachments=[],
    )
    res_empty = ingest_inbound_email_statements(
        webhook=empty_webhook,
        applications_store=applications_store,
        engine=engine,
    )
    assert res_empty.statements_verified is False
    assert res_empty.quarantined is True
    assert applications_store[app_row.id].statements_verified is False

    # Case 2: Valid CSV attachment, but sender_email does NOT match app_row.contact_email -> quarantined!
    valid_csv = (
        "reporting_month,title,isrc,store,country,quantity,net_royalty_eur\n"
        "2025-10,Track One,SEAA12500001,Spotify,SE,120000,450.00\n"
        "2025-11,Track One,SEAA12500001,Spotify,SE,130000,490.00\n"
    )
    spoofed_webhook = InboundEmailStatementWebhook(
        sender_email="spoofed_attacker@untrusted.org",
        subject=f"Statements for {app_row.id}",
        application_id=str(app_row.id),
        attachments=[
            InboundAttachmentPayload(
                filename="statements.csv",
                content_type="text/csv",
                content_text=valid_csv,
            )
        ],
    )
    res_spoofed = ingest_inbound_email_statements(
        webhook=spoofed_webhook,
        applications_store=applications_store,
        engine=engine,
    )
    assert res_spoofed.statements_verified is False
    assert res_spoofed.sender_verified is False
    assert res_spoofed.quarantined is True
    assert applications_store[app_row.id].statements_verified is False

    # Case 3: Valid CSV attachment AND matching sender_email -> verified and upgraded to STAGE_2_STATEMENT_VERIFIED
    authentic_webhook = InboundEmailStatementWebhook(
        sender_email="owner@verifiedartist.com",
        subject=f"Statements for {app_row.id}",
        application_id=str(app_row.id),
        attachments=[
            InboundAttachmentPayload(
                filename="statements.csv",
                content_type="text/csv",
                content_base64=base64.b64encode(valid_csv.encode("utf-8")).decode("ascii"),
            )
        ],
    )
    res_authentic = ingest_inbound_email_statements(
        webhook=authentic_webhook,
        applications_store=applications_store,
        engine=engine,
    )
    assert res_authentic.statements_verified is True
    assert res_authentic.sender_verified is True
    assert res_authentic.quarantined is False
    assert applications_store[app_row.id].statements_verified is True
    assert applications_store[app_row.id].valuation_stage == "STAGE_2_STATEMENT_VERIFIED"
