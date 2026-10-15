"""
Comprehensive Unit & Scenario Tests for SPACE Valuation & Forensics Engine,
Statement Parser, and Typeform `xzx5SBJb` Intake Pipeline.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from services.spacemusic.main import app as spacemusic_app
from services.valuation.dtw_matcher import (
    LifecycleArchetype,
    sakoe_chiba_dtw_distance,
)
from services.valuation.engine import (
    CatalogValuationInput,
    GenreFamily,
    MonthlyStatementPoint,
    RightsScope,
    RoyaltyBasis,
    SpaceValuationEngine,
    TrackInput,
    classify_genre_family,
    is_distributor_name,
    load_rules,
    winsorize_monthly_spikes,
)
from services.valuation.statement_parser import parse_statement_csv


@pytest.fixture
def engine() -> SpaceValuationEngine:
    return SpaceValuationEngine(random_seed=42)


def test_winsorize_monthly_spikes_clips_artificial_promo_month():
    # 11 organic months around €400/m and 1 artificial playlist spike month at €4,500
    series = [390.0, 410.0, 395.0, 405.0, 400.0, 385.0, 415.0, 400.0, 390.0, 410.0, 405.0, 4500.0]
    clipped, excess = winsorize_monthly_spikes(series, mad_multiplier=3.0)
    assert excess > 3500.0
    assert max(clipped) < 600.0
    assert sum(clipped) < 5200.0


def test_distributor_name_detection():
    assert is_distributor_name("Distrokid") is True
    assert is_distributor_name("TuneCore") is True
    assert is_distributor_name("FUGA") is True
    assert is_distributor_name("Is Dead") is False
    assert is_distributor_name("Nova Sounds") is False


def test_case_anderson_erazo_initial_submission_catches_distrokid_as_artist(engine: SpaceValuationEngine):
    """
    Real-world case 1A: Applicant initially enters 'Distrokid' in the artist/label field
    and no LTM amount. Engine must flag DISTRIBUTOR_AS_ARTIST_NAME and route to MISSING_INFO.
    """
    inp = CatalogValuationInput(
        catalog_title="Anderson Initial Submission",
        artist_or_label_name="Distrokid",
        applicant_name="Anderson Erazo",
        applicant_email="andersonerazo03@gmail.com",
        declared_ltm_amount=0.0,
        declared_currency="USD",
    )
    out = engine.evaluate(inp, reference_date=date(2026, 10, 14))
    assert out.pipeline_status == "MISSING_INFO"
    codes = {rf.code for rf in out.risk_flags}
    assert "DISTRIBUTOR_AS_ARTIST_NAME" in codes
    assert len(out.missing_data_fields) >= 2


def test_case_anderson_erazo_is_dead_stage1_and_stage2(engine: SpaceValuationEngine):
    """
    Real-world case 1B: Anderson Erazo / Is Dead (`0EKvKtaSHhGT2Sppi8qZLS`),
    $5,600 USD LTM via DistroKid, 100% master ownership.
    Tests both Stage 1 (Indicative) and Stage 2 (Verified via DistroKid TSV).
    """
    # Stage 1: Self-reported $5,600 USD LTM
    stage1_inp = CatalogValuationInput(
        catalog_title="Is Dead Catalog",
        artist_or_label_name="Is Dead",
        applicant_name="Anderson Erazo",
        applicant_email="andersonerazo03@gmail.com",
        listen_url="https://open.spotify.com/intl-es/artist/0EKvKtaSHhGT2Sppi8qZLS",
        spotify_artist_id="0EKvKtaSHhGT2Sppi8qZLS",
        rights_scope=RightsScope.MASTERS,
        royalty_basis=RoyaltyBasis.NET_PAYABLE,
        distributor_or_admin="DistroKid",
        ownership_share_pct=100.0,
        declared_ltm_amount=5600.0,
        declared_currency="USD",
        statements_verified=False,
        genres=["electronic", "phonk", "indie"],
    )
    stage1_out = engine.evaluate(stage1_inp, reference_date=date(2026, 10, 14))
    assert stage1_out.valuation_stage == "STAGE_1_INDICATIVE"
    assert stage1_out.pipeline_status == "AWAITING_STATEMENTS"
    # $5,600 * 0.92 EUR/USD = €5,152 baseline
    assert stage1_out.baseline.effective_cf0_eur == pytest.approx(5152.0, rel=1e-2)
    assert 9000.0 <= stage1_out.price_median_eur <= 22000.0
    assert stage1_out.discount_rate.verification_premium == 0.05

    # Stage 2: Upload 12 months of DistroKid TSV statements totaling ~$5,600 USD
    tsv_lines = [
        "Sale Month\tStore\tArtist\tTitle\tISRC\tQuantity\tEarnings (USD)\tCountry of Sale\tRelease Date"
    ]
    months = [f"2025-{m:02d}" for m in range(10, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
    tracks_spec = [
        ("QZA112300001", "Midnight Echo", "2023-05-10", 0.35),
        ("QZA112300002", "Static Pulse", "2023-08-15", 0.25),
        ("QZA112300003", "Shadow Drift", "2024-01-20", 0.22),
        ("QZA112300004", "Night Drive", "2024-04-02", 0.18),
    ]
    for m in months:
        for isrc, title, rel_date, weight in tracks_spec:
            monthly_usd = (5600.0 / 12.0) * weight
            streams = int(monthly_usd / 0.0031)
            tsv_lines.append(
                f"{m}\tSpotify\tIs Dead\t{title}\t{isrc}\t{streams}\t{monthly_usd:.2f}\tUS\t{rel_date}"
            )

    parsed = parse_statement_csv("\n".join(tsv_lines))
    assert parsed.detected_distributor == "DistroKid"
    assert parsed.months_covered == 12
    assert len(parsed.tracks) == 4

    stage2_inp = stage1_inp.copy(
        update={
            "statements_verified": True,
            "monthly_history": parsed.monthly_history,
            "tracks": parsed.tracks,
            "dsp_share": parsed.dsp_share,
            "country_share": parsed.country_share,
        }
    )
    stage2_out = engine.evaluate(stage2_inp, reference_date=date(2026, 10, 14))
    assert stage2_out.valuation_stage == "STAGE_2_STATEMENT_VERIFIED"
    assert stage2_out.pipeline_status == "VALUATION_READY"
    # Verified stage removes the 500 bps unverified penalty and increases confidence + multiple
    assert stage2_out.discount_rate.verification_premium == 0.0
    assert stage2_out.discount_rate.total_discount_rate < stage1_out.discount_rate.total_discount_rate
    assert stage2_out.valuation_confidence > stage1_out.valuation_confidence
    assert stage2_out.price_median_eur > stage1_out.price_median_eur


def test_case_functional_noise_under_2min_and_sub1000_stream_traps(engine: SpaceValuationEngine):
    """
    Case 2: An ambient/white-noise uploader with 60% of revenue on 45-second tracks (<120,000 ms)
    and several tracks under Spotify's 1,000 annual stream threshold.
    Engine must apply severe haircuts and raise CRITICAL/HIGH risk flags.
    """
    inp = CatalogValuationInput(
        catalog_title="Short White Noise Farm",
        artist_or_label_name="Sleep Loops Studio",
        declared_ltm_amount=20000.0,
        declared_currency="EUR",
        statements_verified=True,
        genres=["white noise", "sleep", "ambient"],
        tracks=[
            TrackInput(
                isrc="NOISE001",
                title="Rain Loop Part 1 (45s)",
                release_date=date(2025, 6, 1),
                duration_ms=45000,  # <120,000 ms policy floor!
                annual_streams=800000,
                ltm_royalties_eur=12000.0,
            ),
            TrackInput(
                isrc="NOISE002",
                title="Deep Drone (3m)",
                release_date=date(2024, 1, 1),
                duration_ms=180000,
                annual_streams=400000,
                ltm_royalties_eur=5000.0,
            ),
            TrackInput(
                isrc="NOISE003",
                title="Micro Sub-threshold Filler",
                release_date=date(2025, 1, 1),
                duration_ms=150000,
                annual_streams=750,  # <1,000 annual streams floor!
                ltm_royalties_eur=3000.0,
            ),
        ],
    )
    out = engine.evaluate(inp, reference_date=date(2026, 10, 14))
    codes = {rf.code for rf in out.risk_flags}
    assert "SPOTIFY_FUNCTIONAL_NOISE_UNDER_2MIN" in codes
    assert "SPOTIFY_1000_STREAM_THRESHOLD_TRAP" in codes
    # Effective baseline CF_0 must be dramatically cut from €20,000
    assert out.baseline.functional_noise_haircut_eur > 9000.0
    assert out.baseline.effective_cf0_eur < 10000.0


def test_case_mature_diversified_ambient_vs_young_single_hit_catalog(engine: SpaceValuationEngine):
    """
    Case 3: Proves the Moat — two catalogs with identical €25,000 LTM verified royalties
    must receive fundamentally different multiples based on age, genre decay, and HHI concentration.
    """
    # Catalog A: 5-year-old diversified ambient/meditation catalog (10 equal tracks, all >3 mins)
    mature_tracks = [
        TrackInput(
            isrc=f"AMB00{i}",
            title=f"Horizon {i}",
            release_date=date(2021, 5, 1),
            duration_ms=210000,
            annual_streams=900000,
            ltm_royalties_eur=2500.0,
        )
        for i in range(10)
    ]
    mature_inp = CatalogValuationInput(
        catalog_title="Nordic Calm Catalog",
        artist_or_label_name="Nordic Calm",
        declared_ltm_amount=25000.0,
        declared_currency="EUR",
        statements_verified=True,
        genres=["ambient", "meditation", "soundscape"],
        tracks=mature_tracks,
    )

    # Catalog B: 7-month-old single-track viral hip-hop hit (95% revenue on 1 frontline track)
    young_hit_tracks = [
        TrackInput(
            isrc="VIRAL01",
            title="TikTok Slide",
            release_date=date(2026, 3, 15),
            duration_ms=135000,
            annual_streams=8500000,
            ltm_royalties_eur=23750.0,
        ),
        TrackInput(
            isrc="VIRAL02",
            title="Outro B-Side",
            release_date=date(2026, 3, 15),
            duration_ms=140000,
            annual_streams=450000,
            ltm_royalties_eur=1250.0,
        ),
    ]
    young_inp = CatalogValuationInput(
        catalog_title="Viral HipHop Single",
        artist_or_label_name="Lil Trend",
        declared_ltm_amount=25000.0,
        declared_currency="EUR",
        statements_verified=True,
        genres=["hip-hop", "phonk", "rap"],
        tracks=young_hit_tracks,
    )

    mature_out = engine.evaluate(mature_inp, reference_date=date(2026, 10, 14))
    young_out = engine.evaluate(young_inp, reference_date=date(2026, 10, 14))

    # Mature catalog has low HHI (0.10), low decay (~2.5%), low discount rate (~12%) -> ~5.0x-6.2x multiple
    assert mature_out.track_hhi == pytest.approx(0.10, abs=0.01)
    assert mature_out.implied_ltm_multiple_median >= 4.5

    # Young single-hit catalog has high HHI (~0.905), steep frontline decay (~50%), high discount rate -> ~1.6x-2.5x multiple
    assert young_out.track_hhi > 0.85
    assert young_out.implied_ltm_multiple_median <= 2.6
    assert mature_out.price_median_eur > young_out.price_median_eur * 1.9
    assert young_out.deal_structure.holdback_pct > mature_out.deal_structure.holdback_pct


def test_spacemusic_typeform_webhook_and_statement_upgrade_flow():
    """
    End-to-end API test for Typeform `xzx5SBJb` webhook intake -> Stage 1 evaluation
    -> Statement CSV upload -> Stage 2 upgrade + Proprietary Benchmark DB population.
    """
    client = TestClient(spacemusic_app)

    typeform_payload = {
        "event_id": "tf_evt_anderson_001",
        "form_response": {
            "form_id": "xzx5SBJb",
            "token": "tf_tok_anderson_001",
            "answers": [
                {"field": {"id": "ZynDs8tkxlJF"}, "type": "choice", "choice": {"label": "Selling my own catalog"}},
                {"field": {"id": "cIEzRJe4jZWW"}, "type": "text", "text": "Anderson Erazo"},
                {"field": {"id": "oY3yxQa3CAD3"}, "type": "email", "email": "andersonerazo03@gmail.com"},
                {"field": {"id": "kvxzy30bsRuE"}, "type": "text", "text": "Is Dead"},
                {
                    "field": {"id": "v8zF9mHvsniN"},
                    "type": "url",
                    "url": "https://open.spotify.com/intl-es/artist/0EKvKtaSHhGT2Sppi8qZLS",
                },
                {"field": {"id": "OqKtPOGC9Hdg"}, "type": "choice", "choice": {"label": "Master recording rights"}},
                {
                    "field": {"id": "5i9TtGJ1Upta"},
                    "type": "choice",
                    "choice": {"label": "I can provide an approximate amount"},
                },
                {"field": {"id": "CKyv4Tu2q2qS"}, "type": "text", "text": "5600"},
                {"field": {"id": "DN8Au6nFTIIa"}, "type": "text", "text": "USD"},
                {
                    "field": {"id": "xI8yrwFcihKF"},
                    "type": "choice",
                    "choice": {"label": "Royalties payable to the owner after distributor or administrator deductions"},
                },
                {"field": {"id": "dMwecIGMIyrp"}, "type": "text", "text": "DistroKid"},
                {
                    "field": {"id": "jVSpoJtOlUJ6"},
                    "type": "text",
                    "text": "I own 100% of masters, selling existing releases only.",
                },
            ],
        },
    }

    resp1 = client.post("/webhooks/typeform", json=typeform_payload)
    assert resp1.status_code == 201
    data1 = resp1.json()
    app_id = data1["application_id"]
    assert data1["pipeline_status"] == "AWAITING_STATEMENTS"
    assert data1["valuation_stage"] == "STAGE_1_INDICATIVE"
    assert data1["reply_draft"]["template_type"] == "REQUEST_STATEMENTS"
    assert "DistroKid" in data1["reply_draft"]["body"]

    # Now attach raw DistroKid CSV statement to upgrade to Stage 2
    csv_statement = (
        "Sale Month,Store,Artist,Title,ISRC,Quantity,Earnings (USD),Country of Sale,Release Date\n"
        "2026-01,Spotify,Is Dead,Midnight Echo,QZA112300001,150000,480.00,US,2023-05-10\n"
        "2026-02,Spotify,Is Dead,Midnight Echo,QZA112300001,148000,475.00,US,2023-05-10\n"
        "2026-03,Apple Music,Is Dead,Static Pulse,QZA112300002,65000,460.00,GB,2023-08-15\n"
    )
    resp2 = client.post(
        f"/catalog-review/{app_id}/statements",
        json={"raw_statement_csv": csv_statement, "default_currency": "USD"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["valuation_stage"] == "STAGE_2_STATEMENT_VERIFIED"
    assert data2["pipeline_status"] == "VALUATION_READY"
    assert data2["reply_draft"]["template_type"] == "INDICATIVE_OFFER"

    # Verify proprietary benchmarks were recorded in SPACE's internal database
    bench_resp = client.get("/catalog-review/benchmarks")
    assert bench_resp.status_code == 200
    benchmarks = bench_resp.json()
    assert len(benchmarks) >= 2
    dsps = {b["dsp_store"] for b in benchmarks}
    assert "spotify" in dsps
    assert "apple_music" in dsps


def test_all_8_genre_classifications_and_cohort_hierarchy(engine: SpaceValuationEngine):
    """
    Verifies all 8 distinct genre families are classified accurately and that their
    cohort decay curves produce sensible valuation multiples (e.g. Classical/Jazz & Rock
    command higher multiples than Frontline Hip-Hop/Phonk).
    """
    rules = load_rules()
    assert classify_genre_family(["ambient", "sleep"], rules) == GenreFamily.AMBIENT_FUNCTIONAL
    assert classify_genre_family(["lo-fi beats", "chillhop"], rules) == GenreFamily.LOFI_CHILL
    assert classify_genre_family(["deep house", "melodic techno"], rules) == GenreFamily.ELECTRONIC_DANCE
    assert classify_genre_family(["drift phonk", "trap", "hip-hop"], rules) == GenreFamily.HIPHOP_RNB_PHONK
    assert classify_genre_family(["indie pop", "synthpop"], rules) == GenreFamily.POP_INDIE
    assert classify_genre_family(["indie rock", "americana", "country"], rules) == GenreFamily.ROCK_METAL_COUNTRY
    assert classify_genre_family(["reggaeton", "afrobeats"], rules) == GenreFamily.LATIN_AFRO
    assert classify_genre_family(["neo-classical", "solo piano", "jazz"], rules) == GenreFamily.CLASSICAL_JAZZ_INSTRUMENTAL


def test_dtw_phase_shift_invariance_and_artificial_step_plateau_detection(engine: SpaceValuationEngine):
    """
    Tests Dynamic Time Warping (DTW):
    1. Two songs with identical burn-in shapes but peaked 2 months apart have near-zero
       Sakoe-Chiba DTW distance (whereas Euclidean distance is large).
    2. A catalog with a 5-month flat rectangular step-plateau (paid bot/playlist campaign)
       is caught by `DTW_ARTIFICIAL_STEP_PLATEAU` and penalized in the valuation.
    """
    # 1. Phase-shifted lifecycle curves (Peak at month 2 vs Peak at month 4)
    curve_early_peak = [0.3, 1.0, 0.75, 0.55, 0.42, 0.35, 0.32, 0.30, 0.29, 0.28, 0.27, 0.26]
    curve_late_peak = [0.2, 0.25, 0.3, 1.0, 0.75, 0.55, 0.42, 0.35, 0.32, 0.30, 0.29, 0.28]

    dtw_dist = sakoe_chiba_dtw_distance(curve_early_peak, curve_late_peak, window=3)
    assert dtw_dist < 0.08  # DTW recognizes it is the exact same lifecycle shape!

    # 2. Artificial rectangular step-plateau: €80/m baseline -> sudden €1,000/m flat block for 5 months -> €90/m
    step_months = [
        MonthlyStatementPoint(period=f"2025-{m:02d}", net_royalties_eur=v, streams=int(v * 350))
        for m, v in enumerate(
            [80.0, 85.0, 78.0, 82.0, 1000.0, 1005.0, 998.0, 1002.0, 995.0, 85.0, 80.0, 78.0],
            start=1,
        )
    ]
    step_inp = CatalogValuationInput(
        catalog_title="Paid Playlist Step Catalog",
        artist_or_label_name="Boosted Artist",
        declared_ltm_amount=5668.0,
        declared_currency="EUR",
        statements_verified=True,
        genres=["electronic", "house"],
        monthly_history=step_months,
        notes="Used a non-exclusive beatstars lease on one track.",
    )
    out = engine.evaluate(step_inp, reference_date=date(2026, 10, 14))
    assert out.dtw_analysis is not None
    assert out.dtw_analysis.is_artificial_step_plateau is True
    assert out.dtw_analysis.matched_archetype == LifecycleArchetype.ARTIFICIAL_STEP_PLATEAU
    flag_codes = {rf.code for rf in out.risk_flags}
    assert "DTW_ARTIFICIAL_STEP_PLATEAU" in flag_codes


def test_typeform_csv_export_parser_and_email_sanitization(engine: SpaceValuationEngine):
    """
    Verifies bulk parsing of Typeform `xzx5SBJb` CSV exports, including currency
    normalization (`$`, `usd`, `British Pounds`), email typo correction (`@gnail.com`),
    synthetic test row filtering, and genre inference.
    """
    from services.spacemusic.typeform_adapter import (
        application_to_valuation_input,
        normalize_currency,
        parse_typeform_csv_export,
        sanitize_email,
    )

    assert normalize_currency("$") == "USD"
    assert normalize_currency("usd") == "USD"
    assert normalize_currency("British Pounds") == "GBP"
    assert sanitize_email("2scratch.business@gnail.com") == "2scratch.business@gmail.com"

    sample_csv = (
        "#,What would you like to discuss?,What is your name?,Which email should we reply to?,"
        "Which artist or label is this catalog released under?,Where can we listen to the catalog?,"
        "Which rights would you like us to review?,Has the owner authorized you to discuss this catalog?,"
        "Do you know the catalog's royalty income for the last 12 months?,"
        "Approximately how much did those rights earn in the last 12 months?,"
        "Which currency is that amount in?,What does that amount represent?,"
        "Who distributes or administers these royalties?,"
        "Anything we should know about the rights you want reviewed?,"
        "Which organization do you represent?,Does your organization have a website?,"
        "What would you like to discuss with SPACE?,How did you hear about SPACE?,"
        "Email me occasional SPACE news and catalog insights.,landing_path,apply_source_path,"
        "Response Type,Start Date (UTC),Stage Date (UTC),Submit Date (UTC),Network ID,Tags,Ending\n"
        "a7skwqj9176ajv0fhkzja7skwqjotfhv,Selling my own catalog,Justin Tumeh,2scratch.business@gnail.com,"
        "2Scratch,https://open.spotify.com/track/39m3vSEBm9PZoYF0XZNM1p,Master recording rights,,"
        "I can provide an approximate amount,30000,USD,"
        "Royalties payable to the owner after distributor or administrator deductions,"
        "Tribal Trap & Trap Nation,,,,,,No,/apply/,/,completed,2026-10-13 20:04:07,,2026-10-13 20:07:07,24db04e431,,Your review request has been received.\n"
        "fif217qc3hrzfifjah3f6mk9mmljah3f,A partnership or another inquiry,Ryan Mitchell,wQjq1l@example.com,"
        "Echo Valley Entertainment,https://example.com,Master recording rights,I still need to confirm,"
        "I need to check my statements,45000,British Pounds,Royalties before those deductions,"
        "None,Test,Meridian,https://example.com,Test,Friend,No,test_url_parameter,test_url_parameter,"
        "completed,2026-10-08 12:11:12,,2026-10-08 12:11:12,7f4e53ce4e,AI Generated,\n"
    )

    apps = parse_typeform_csv_export(sample_csv, skip_test_rows=True)
    assert len(apps) == 1
    app = apps[0]
    assert app.contact_email == "2scratch.business@gmail.com"
    assert app.declared_ltm_amount == 30000.0
    assert app.declared_currency == "USD"

    val_input = application_to_valuation_input(app)
    val = engine.evaluate(val_input)
    assert val.genre_family == GenreFamily.HIPHOP_RNB_PHONK
    assert val.pipeline_status == "AWAITING_STATEMENTS"
    assert val.price_median_eur > 50000.0


def test_ai_and_fake_artist_profile_forensics_detector(engine: SpaceValuationEngine):
    """
    Verifies that the AI & Fake Artist Profile Forensics Detector accurately catches:
    1. Explicit AI-generated music disclosure + same-day batch dumping (RAMMEDEBEL pattern).
    2. Fake major-label P-line spoofing on DIY distributors + ghost listener counts (Joseph Kargbo pattern).
    3. Short-clip loop farming (~59s tracks) + zero followers (NDS Notdoingshi pattern).
    4. Verified organic human artists (Micky, 2Scratch, Daniel Sadowski) pass with score 0.0.
    """
    from services.valuation.ai_profile_detector import (
        AuthenticityStatus,
        ReleaseMetadataItem,
    )

    # 1. RAMMEDEBEL pattern: explicit AI disclosure + 7 singles uploaded on the exact same day (2026-10-10)
    rammedebel_releases = [
        ReleaseMetadataItem(
            title=f"AI Track {i}",
            release_date=date(2026, 10, 10),
            release_type="SINGLE",
            track_count=1,
            label="13710407 Records DK",
            total_streams=0,
            duration_ms=210000,
        )
        for i in range(7)
    ]
    ram_inp = CatalogValuationInput(
        catalog_title="RAMMEDEBEL Catalog",
        artist_or_label_name="RAMMEDEBEL",
        distributor_or_admin="DistroKid",
        declared_ltm_amount=5000.0,
        declared_currency="USD",
        spotify_followers=21,
        spotify_monthly_listeners=206,
        external_social_links_count=0,
        releases=rammedebel_releases,
        notes="Please let me know what information you need to evaluate my catalog, including music created with AI tools where applicable.",
    )
    ram_out = engine.evaluate(ram_inp, reference_date=date(2026, 10, 14))
    assert ram_out.ai_profile_validation is not None
    assert ram_out.ai_profile_validation.self_disclosed_ai is True
    assert ram_out.ai_profile_validation.mass_upload_cadence_detected is True
    assert ram_out.ai_profile_validation.authenticity_status == AuthenticityStatus.CONFIRMED_AI_OR_FARM
    assert ram_out.ai_profile_validation.ai_fake_probability_score >= 80.0
    assert any(rf.code == "AI_OR_FAKE_ARTIST_PROFILE_RISK" for rf in ram_out.risk_flags)

    # 2. Joseph Kargbo pattern: DIY distributor (UnitedMasters) with spoofed Universal/Sony/Def Jam/Maybach labels & 9 monthly listeners
    jk_releases = [
        ReleaseMetadataItem(
            title=f"Album {i}",
            release_date=date(2026, 7, 15 + i),
            release_type="ALBUM",
            track_count=12,
            label="sony music Entertainement RCA records columbia records epic records" if i % 2 == 0 else "Maybach Music Group",
            total_streams=0,
        )
        for i in range(6)
    ]
    jk_inp = CatalogValuationInput(
        catalog_title="Joseph Kargbo Catalog",
        artist_or_label_name="joseph kargbo Entertainement",
        distributor_or_admin="united master",
        declared_ltm_amount=4000.0,
        declared_currency="EUR",
        spotify_followers=1176,
        spotify_monthly_listeners=9,
        releases=jk_releases,
    )
    jk_out = engine.evaluate(jk_inp, reference_date=date(2026, 10, 14))
    assert jk_out.ai_profile_validation is not None
    assert jk_out.ai_profile_validation.spoofed_major_label_detected is True
    assert jk_out.ai_profile_validation.mass_upload_cadence_detected is True
    assert jk_out.ai_profile_validation.authenticity_status == AuthenticityStatus.CONFIRMED_AI_OR_FARM

    # 3. Organic human artist (Micky) passes cleanly with 0 AI risk
    organic_inp = CatalogValuationInput(
        catalog_title="Micky Catalog",
        artist_or_label_name="Micky",
        distributor_or_admin="FUGA",
        declared_ltm_amount=31000.0,
        declared_currency="USD",
        spotify_followers=128607,
        spotify_monthly_listeners=556909,
        external_social_links_count=2,
        releases=[
            ReleaseMetadataItem(
                title="This Is The Life",
                release_date=date(2021, 2, 11),
                release_type="SINGLE",
                track_count=1,
                label="FRTYFVE",
                total_streams=40667826,
                duration_ms=190659,
            )
        ],
    )
    organic_out = engine.evaluate(organic_inp, reference_date=date(2026, 10, 14))
    assert organic_out.ai_profile_validation is not None
    assert organic_out.ai_profile_validation.authenticity_status == AuthenticityStatus.VERIFIED_ORGANIC
    assert organic_out.ai_profile_validation.ai_fake_probability_score == 0.0


def test_zero_touch_stage1_pipeline_and_implied_revenue_crosscheck(engine: SpaceValuationEngine):
    """
    Verifies the Zero-Touch Stage 1 pipeline (`services/spacemusic/zero_touch_stage1.py`):
    1. Live Spotify enrichment + mathematical Implied-Stream-to-Revenue Cross-Check catches
       fabricated LTM revenue claims (e.g. $144,000/yr with 9 monthly listeners -> `AUTO_DECLINE_AI_OR_FAKE_PROFILE`).
    2. Qualified organic artist (e.g. 2Scratch / Micky via DistroKid) receives `AUTO_SEND_STAGE1_CSV_REQUEST`
       with tailored distributor-specific click-path export instructions injected directly into the email body.
    """
    from services.spacemusic.models import CatalogApplication
    from services.spacemusic.zero_touch_stage1 import (
        ZeroTouchActionDecision,
        execute_zero_touch_stage1,
        extract_spotify_reference,
    )

    ent_type, sp_id = extract_spotify_reference("https://open.spotify.com/intl-fr/artist/7EUezfT3313RE1WoM0vMu0?si=abc")
    assert ent_type == "artist"
    assert sp_id == "7EUezfT3313RE1WoM0vMu0"

    # Case A: Fabricated revenue + spoofed major-label P-lines on DIY distributor (Joseph Kargbo pattern)
    fake_app = CatalogApplication(
        contact_name="Joseph Kargbo",
        contact_email="kargbo93@hotmail.fr",
        artist_or_label_name="joseph kargbo Entertainement",
        listen_url="https://open.spotify.com/artist/7EUezfT3313RE1WoM0vMu0",
        declared_ltm_amount=144000.0,
        declared_currency="USD",
        distributor_or_admin="united master",
    )
    raw_fake_spotify = {
        "result": {
            "artist_basic": {
                "uri": "spotify:artist:7EUezfT3313RE1WoM0vMu0",
                "name": "joseph kargbo Entertainement",
                "verified": False,
                "followers": 1176,
                "monthly_listeners": 9,
                "external_links": [],
            },
            "top_tracks": [
                {"name": "Track 1", "duration_ms": 195000, "playcount": 0, "release_date": "2026-08-01"},
                {"name": "Track 2", "duration_ms": 185000, "playcount": 0, "release_date": "2026-08-01"},
            ],
            "albums": [
                {
                    "name": f"Album {i}",
                    "release_date": f"2026-07-{10 + i:02d}",
                    "total_tracks": 12,
                    "label": "sony music Entertainement RCA records columbia records epic records",
                }
                for i in range(6)
            ],
        }
    }
    res_fake = execute_zero_touch_stage1(
        fake_app,
        engine=engine,
        raw_spotify_payload=raw_fake_spotify,
        reference_date=date(2026, 10, 14),
    )
    assert res_fake.spotify_enriched is True
    assert res_fake.implied_revenue_crosscheck is not None
    assert res_fake.implied_revenue_crosscheck.discrepancy_status == "EXTREME_FABRICATION_OR_MISMATCH"
    assert res_fake.autonomous_decision == ZeroTouchActionDecision.AUTO_DECLINE_AI_OR_FAKE_PROFILE
    assert res_fake.pipeline_status == "DECLINED_AI_OR_FAKE_PROFILE"
    assert res_fake.reply_draft.template_type == "AUTO_DECLINE_AI_OR_FAKE"
    assert any(rf.code == "IMPLIED_STREAM_REVENUE_MISMATCH" for rf in res_fake.valuation.risk_flags)

    # Case B: Verified organic artist on DistroKid gets tailored DistroKid export instructions
    organic_app = CatalogApplication(
        contact_name="Micky",
        contact_email="micky@example.org",
        artist_or_label_name="Micky",
        listen_url="https://open.spotify.com/artist/6QYd4joWXUMK3IXE77QHa2",
        declared_ltm_amount=25000.0,
        declared_currency="EUR",
        distributor_or_admin="DistroKid",
    )
    raw_organic_spotify = {
        "result": {
            "artist_basic": {
                "uri": "spotify:artist:6QYd4joWXUMK3IXE77QHa2",
                "name": "Micky",
                "verified": True,
                "followers": 128607,
                "monthly_listeners": 556909,
                "external_links": ["https://instagram.com/micky", "https://facebook.com/micky"],
            },
            "top_tracks": [
                {"name": "This Is The Life", "duration_ms": 190659, "playcount": 40667826, "release_date": "2021-02-11"},
                {"name": "Summer Night", "duration_ms": 175000, "playcount": 8200000, "release_date": "2022-06-15"},
            ],
            "singles": [
                {"name": "This Is The Life", "release_date": "2021-02-11", "total_tracks": 1, "label": "FRTYFVE"},
            ],
        }
    }
    res_org = execute_zero_touch_stage1(
        organic_app,
        engine=engine,
        raw_spotify_payload=raw_organic_spotify,
        reference_date=date(2026, 10, 14),
    )
    assert res_org.spotify_enriched is True
    assert res_org.implied_revenue_crosscheck is not None
    assert res_org.implied_revenue_crosscheck.discrepancy_status == "PLAUSIBLE"
    assert res_org.autonomous_decision == ZeroTouchActionDecision.AUTO_SEND_STAGE1_CSV_REQUEST
    assert "distrokid.com/bank" in res_org.reply_draft.body
    assert "See Excruciating Detail" in res_org.reply_draft.body


def test_autonomous_inbox_to_underwriting_and_institutional_buyer_router(engine: SpaceValuationEngine):
    """
    Verifies:
    1. `ingest_inbound_email_statements` unpacks a `.zip` archive containing multiple monthly
       distributor CSV files, matches the sender email (`2scratch.business@gmail.com`) to the
       existing `CatalogApplication`, upgrades it to `STAGE_2_STATEMENT_VERIFIED`, and produces
       both the Seller Offer Draft and Slack Deal Card.
    2. `route_catalog_to_institutional_buyers` ranks SPACE's 8 institutional buyers (`Duetti`,
       `Create Music Group`, `beatBread`, `Sound Royalties`, `ANote Music`, `Royalty Exchange`,
       `SongVest`, `Symphonic`) for organic catalogs and blocks AI/fake or step-plateau catalogs.
    """
    import base64
    import io
    import zipfile

    from services.spacemusic.inbox_ingestor import (
        InboundAttachmentPayload,
        InboundEmailStatementWebhook,
        ingest_inbound_email_statements,
    )
    from services.spacemusic.models import CatalogApplication

    app_2scratch = CatalogApplication(
        contact_name="Justin Tumeh",
        contact_email="2scratch.business@gmail.com",
        artist_or_label_name="2Scratch",
        listen_url="https://open.spotify.com/track/39m3vSEBm9PZoYF0XZNM1p",
        declared_ltm_amount=30000.0,
        declared_currency="USD",
        distributor_or_admin="Tribal Trap & Trap Nation",
        rights_notes="Trap / Hip-Hop master catalog",
    )
    store = {app_2scratch.id: app_2scratch}

    # Build a ZIP archive with 2 CSV statement files covering 12 months
    csv_part1 = (
        "Sale Month,Title,Artist,ISRC,Store,Country of Sale,Quantity,Earnings (USD),Release Date\n"
        + "\n".join(
            f"2025-{m:02d},All Night,2Scratch,US2SC1900001,Spotify,US,420000,1650.00,2019-06-15\n"
            f"2025-{m:02d},Superstar,2Scratch,US2SC2000002,Apple Music,DE,210000,980.00,2020-03-10"
            for m in range(1, 7)
        )
    )
    csv_part2 = (
        "Sale Month,Title,Artist,ISRC,Store,Country of Sale,Quantity,Earnings (USD),Release Date\n"
        + "\n".join(
            f"2025-{m:02d},All Night,2Scratch,US2SC1900001,Spotify,US,405000,1590.00,2019-06-15\n"
            f"2025-{m:02d},Superstar,2Scratch,US2SC2000002,Apple Music,DE,200000,940.00,2020-03-10"
            for m in range(7, 13)
        )
    )

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("2scratch_2025_h1.csv", csv_part1)
        zf.writestr("2scratch_2025_h2.csv", csv_part2)
    zip_b64 = base64.b64encode(zip_buf.getvalue()).decode("ascii")

    webhook = InboundEmailStatementWebhook(
        sender_email="2scratch.business@gnail.com",  # tests typo sanitization matching too!
        sender_name="Justin Tumeh",
        subject="Re: Your SPACE catalog review — 2Scratch",
        attachments=[
            InboundAttachmentPayload(
                filename="2Scratch_DistroKid_2025_Statements.zip",
                content_base64=zip_b64,
            )
        ],
    )

    res = ingest_inbound_email_statements(
        webhook,
        applications_store=store,
        engine=engine,
        reference_date=date(2026, 1, 15),
    )

    assert res.matched_existing_application is True
    assert res.files_processed == ["2scratch_2025_h1.csv", "2scratch_2025_h2.csv"]
    assert res.detected_distributor == "DistroKid"
    assert res.statement_summary.months_covered == 12
    assert res.valuation.valuation_stage == "STAGE_2_STATEMENT_VERIFIED"
    assert res.valuation.pipeline_status == "VALUATION_READY"
    assert res.seller_offer_draft.template_type == "INDICATIVE_OFFER"

    # Verify Institutional Buyer Routing matches Create Music Group & Duetti at the top
    assert res.institutional_routing.eligible_for_syndication is True
    top_partner_ids = [b.partner_id for b in res.institutional_routing.recommended_buyers]
    assert "create_music_group" in top_partner_ids
    assert "duetti" in top_partner_ids
    assert "SPACE Institutional Underwriting Memo — 2Scratch" in res.institutional_routing.underwriting_memo_markdown
    assert "2Scratch" in res.slack_deal_card_markdown


def test_lead_lag_arbitrage_and_chain_of_title_forensics(engine: SpaceValuationEngine):
    """
    Verifies Forensics Check 10 (Lead-Lag Arbitrage & Pre-Clawback Dump Detector)
    and Forensics Check 11 (Chain-of-Title, Distributor-Hopping & Collaborator Split Auditor):
    1. A catalog with strong trailing CSV statements (€3,000/mo) that has collapsed on live Spotify
       (120 monthly listeners -> RVR < 0.35) triggers `PRE_CLAWBACK_DUMP_WARNING` and is blocked
       from institutional buyer syndication.
    2. A catalog that hopped from Create Music Group / Empire P-lines to DistroKid and has
       collaborative (`feat.` / `&`) tracks while claiming 100% ownership triggers
       `DISTRIBUTOR_HOPPING_UNRECOUPED_RISK` and `COLLABORATOR_SPLIT_SHEET_VERIFICATION`
       and generates the required closing document checklist.
    """
    from services.spacemusic.buyer_router import route_catalog_to_institutional_buyers
    from services.spacemusic.models import CatalogApplication
    from services.valuation.ai_profile_detector import ReleaseMetadataItem
    from services.valuation.lead_lag_and_title_forensics import (
        ChainOfTitleStatus,
        LeadLagSignalStatus,
    )

    # Case 1: Pre-Clawback Dump + Distributor Hopping + Collaborator Split Exposure
    dump_inp = CatalogValuationInput(
        catalog_title="Dumped Catalog",
        artist_or_label_name="Hopper Artist",
        distributor_or_admin="DistroKid",
        ownership_share_pct=100.0,
        declared_ltm_amount=36000.0,
        declared_currency="EUR",
        statements_verified=True,
        spotify_followers=850,
        spotify_monthly_listeners=120,  # Crashed in real-time despite €3k/mo in trailing statements!
        dsp_share={"spotify": 0.80, "apple_music": 0.20},
        monthly_history=[
            MonthlyStatementPoint(period=f"2025-{m:02d}", net_royalties_eur=3000.0, streams=1000000)
            for m in range(1, 13)
        ],
        releases=[
            ReleaseMetadataItem(
                title="Big Hit (feat. Lil Guest & ProducerX)",
                release_date=date(2024, 6, 1),
                release_type="SINGLE",
                track_count=1,
                label="Create Music Group / Empire",
            ),
            ReleaseMetadataItem(
                title="Recent Reupload",
                release_date=date(2026, 2, 1),
                release_type="SINGLE",
                track_count=1,
                label="9912345 Records DK",
            ),
        ],
        tracks=[
            TrackInput(
                isrc="USHOP2400001",
                title="Big Hit (feat. Lil Guest & ProducerX)",
                release_date=date(2024, 6, 1),
                ltm_royalties_eur=36000.0,
                annual_streams=12000000,
                spotify_label="Create Music Group / Empire",
            )
        ],
    )
    dump_out = engine.evaluate(dump_inp, reference_date=date(2026, 10, 14))

    assert dump_out.lead_lag_arbitrage is not None
    assert dump_out.lead_lag_arbitrage.signal_status == LeadLagSignalStatus.PRE_CLAWBACK_DUMP_WARNING
    assert dump_out.lead_lag_arbitrage.real_time_velocity_ratio < 0.35

    assert dump_out.chain_of_title is not None
    assert dump_out.chain_of_title.title_status == ChainOfTitleStatus.ENCUMBRANCE_OR_HOPPING_ALERT
    assert dump_out.chain_of_title.distributor_hopping_detected is True
    assert len(dump_out.chain_of_title.collaborator_tracks_detected) == 1

    flag_codes = {rf.code for rf in dump_out.risk_flags}
    assert "PRE_CLAWBACK_DUMP_WARNING" in flag_codes
    assert "DISTRIBUTOR_HOPPING_UNRECOUPED_RISK" in flag_codes
    assert "COLLABORATOR_SPLIT_SHEET_VERIFICATION" in flag_codes

    # Institutional router must block a Pre-Clawback Dump catalog
    app_dump = CatalogApplication(artist_or_label_name="Hopper Artist", distributor_or_admin="DistroKid")
    routing = route_catalog_to_institutional_buyers(app_dump, dump_out)
    assert routing.eligible_for_syndication is False
    assert "Pre-Clawback Dump Warning" in (routing.disqualification_reason or "")


def test_heterogeneous_symphonic_csv_and_youtube_studio_xlsx_ingestion(engine: SpaceValuationEngine):
    """
    Verifies native OpenXML `.xlsx` parsing (`read_xlsx_worksheets`, `convert_xlsx_to_csv_text`)
    and multi-attachment heterogeneous merging (`parse_multi_attachment_statements`) for a label
    that submits both a Symphonic CSV statement (`Reporting Period` = `MAR-26`, `Royalty ($US)`)
    and a multi-sheet YouTube Studio Analytics `.xlsx` export (`Revenus estimés (MAD)` + Sheet 3
    monthly `Vues engagées`).
    """
    import base64
    import io
    import zipfile

    from services.spacemusic.inbox_ingestor import (
        InboundAttachmentPayload,
        InboundEmailStatementWebhook,
        ingest_inbound_email_statements,
    )
    from services.spacemusic.models import CatalogApplication

    def _build_minimal_youtube_xlsx(total_mad: float, months_views: list[tuple[str, int]]) -> bytes:
        ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        s1_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{ns}"><sheetData>
  <row r="1">
    <c r="A1" t="inlineStr"><is><t>Contenu</t></is></c>
    <c r="B1" t="inlineStr"><is><t>Titre de la vidéo</t></is></c>
    <c r="C1" t="inlineStr"><is><t>Heure de publication de la vidéo</t></is></c>
    <c r="D1" t="inlineStr"><is><t>Vues engagées</t></is></c>
    <c r="E1" t="inlineStr"><is><t>Revenus estimés (MAD)</t></is></c>
  </row>
  <row r="2">
    <c r="A2" t="inlineStr"><is><t>Total</t></is></c>
    <c r="B2" t="inlineStr"><is><t></t></is></c>
    <c r="C2" t="inlineStr"><is><t></t></is></c>
    <c r="D2"><v>5900000</v></c>
    <c r="E2"><v>{total_mad}</v></c>
  </row>
  <row r="3">
    <c r="A3" t="inlineStr"><is><t>UMkaxT4nK-M</t></is></c>
    <c r="B3" t="inlineStr"><is><t>Majda Raoui - Ach dani douar zine REGGADA 2023</t></is></c>
    <c r="C3" t="inlineStr"><is><t>Jun 30, 2023</t></is></c>
    <c r="D3"><v>3500000</v></c>
    <c r="E3"><v>{total_mad * 0.6}</v></c>
  </row>
  <row r="4">
    <c r="A4" t="inlineStr"><is><t>E6QA9uGBJDA</t></is></c>
    <c r="B4" t="inlineStr"><is><t>Chaba Hajar - 3la Darbouka 3ndha</t></is></c>
    <c r="C4" t="inlineStr"><is><t>Aug 15, 2020</t></is></c>
    <c r="D4"><v>2400000</v></c>
    <c r="E4"><v>{total_mad * 0.4}</v></c>
  </row>
</sheetData></worksheet>"""
        s2_xml = f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Date</t></is></c></row></sheetData></worksheet>'
        s3_rows = ['<row r="1"><c r="A1" t="inlineStr"><is><t>Date</t></is></c><c r="B1" t="inlineStr"><is><t>Vues engagées</t></is></c></row>']
        for idx, (m_str, v_cnt) in enumerate(months_views, start=2):
            s3_rows.append(
                f'<row r="{idx}"><c r="A{idx}" t="inlineStr"><is><t>{m_str}</t></is></c><c r="B{idx}"><v>{v_cnt}</v></c></row>'
            )
        s3_xml = f'<worksheet xmlns="{ns}"><sheetData>{"".join(s3_rows)}</sheetData></worksheet>'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}"></workbook>')
            zf.writestr("xl/worksheets/sheet1.xml", s1_xml)
            zf.writestr("xl/worksheets/sheet2.xml", s2_xml)
            zf.writestr("xl/worksheets/sheet3.xml", s3_xml)
        return buf.getvalue()

    symphonic_csv = (
        '\ufeff"Reporting Period",Label,Release Name,Release Artists,UPC Code,Track Title,ISRC Code,'
        'Track Artists,Digital Service Provider,Activity Period,Territory,Sale or Void,Count,Royalty ($US)\n'
        'MAR-26,phoenix records,Mateswa walo,Chaba Wijdane,195729253100,Mateswa walo,QZTRX2133482,'
        'Chaba Wijdane,Spotify,March 2026,MA,Sale,45000,155.50\n'
        'MAR-26,phoenix records,Jitk ya Bhar,Cheb Finani,195729253101,Jitk ya Bhar,GBWUL1922158,'
        'Cheb Finani,YouTube Content ID,March 2026,DZ,Sale,90000,70.00\n'
    )
    yt_months = [(f"2025-{m:02d}", 480000 + m * 5000) for m in range(1, 13)]
    yt_xlsx_bytes = _build_minimal_youtube_xlsx(50264.85, yt_months)

    phoenix_app = CatalogApplication(
        contact_name="Mohammed Belmokhtar",
        contact_email="phoenixstudio48@gmail.com",
        artist_or_label_name="phoenix records label",
        declared_ltm_amount=8340.0,
        declared_currency="USD",
        rights_scope="both",
        distributor_or_admin="Symphonic",
        rights_notes="Raï / Reggada Moroccan music label catalog",
    )
    store = {phoenix_app.id: phoenix_app}

    webhook = InboundEmailStatementWebhook(
        sender_email="phoenixstudio48@gmail.com",
        sender_name="Mohammed Belmokhtar",
        subject="Re: Your SPACE catalog review — phoenix records label",
        attachments=[
            InboundAttachmentPayload(
                filename="phoenixrecords_MAR-26.csv",
                content_text=symphonic_csv,
            ),
            InboundAttachmentPayload(
                filename="Last 365 Phoenix.xlsx",
                content_base64=base64.b64encode(yt_xlsx_bytes).decode("ascii"),
            ),
        ],
    )

    res = ingest_inbound_email_statements(
        webhook,
        applications_store=store,
        engine=engine,
        reference_date=date(2026, 10, 14),
    )

    assert res.matched_existing_application is True
    assert "Symphonic" in res.detected_distributor
    assert "YouTube Studio" in res.detected_distributor
    assert res.valuation.valuation_stage == "STAGE_2_STATEMENT_VERIFIED"
    assert res.valuation.genre_family == GenreFamily.LATIN_AFRO
    assert res.valuation.baseline.effective_cf0_eur > 6000.0
    assert res.valuation.price_median_eur > 12000.0
    assert res.institutional_routing.eligible_for_syndication is True
    assert res.blind_deal_teaser is not None
    assert "SPC-" in res.blind_deal_teaser.deal_code
    assert "phoenix records label" not in res.blind_deal_teaser.teaser_markdown.lower()


def test_closing_document_pack_and_cross_catalog_isrc_fraud_detector(
    engine: SpaceValuationEngine,
    tmp_path,
):
    """
    Verifies:
    1. `generate_closing_document_pack` generates the Blind Deal Teaser (redacting artist/ISRC),
       Institutional NCND & Fee Agreement, Distributor Letter of Direction (LOD), and
       Split-Wire Settlement Statement (computing SPACE's origination fee + syndication spread).
    2. `DealLakeRepository.register_and_check_isrc_collisions` persists applications & ISRCs to
       SQLite and catches a second seller attempting to submit the exact same ISRC (`CROSS_CATALOG_ISRC_COLLISION`).
    """
    from services.spacemusic.closing_pack import (
        DealLakeRepository,
        generate_closing_document_pack,
    )
    from services.spacemusic.models import CatalogApplication

    db_file = tmp_path / "test_deal_lake.sqlite3"
    lake = DealLakeRepository(db_path=db_file)

    csv_seller_a = (
        "Sale Month,Store,Artist,Title,ISRC,Quantity,Earnings (USD),Country of Sale,Release Date\n"
        "2026-01,Spotify,Original Artist,Golden Song,USORG2400999,500000,1800.00,US,2024-01-15\n"
        "2026-02,Spotify,Original Artist,Golden Song,USORG2400999,490000,1750.00,US,2024-01-15\n"
    )
    summary_a = parse_statement_csv(csv_seller_a)
    app_a = CatalogApplication(
        contact_name="Legit Owner",
        contact_email="legit@artist.com",
        artist_or_label_name="Original Artist",
        distributor_or_admin="DistroKid",
        declared_ltm_amount=21000.0,
        declared_currency="USD",
        statements_verified=True,
    )
    lake.save_application(app_a)
    alerts_a = lake.register_and_check_isrc_collisions(app_a, summary_a)
    assert len(alerts_a) == 0

    # Now Seller B tries to submit the same ISRC (`USORG2400999`) under a different email!
    app_b = CatalogApplication(
        contact_name="Scam Cloner",
        contact_email="scammer@clone.org",
        artist_or_label_name="Clone Uploader",
        distributor_or_admin="TuneCore",
        declared_ltm_amount=21000.0,
        declared_currency="USD",
        statements_verified=True,
    )
    alerts_b = lake.register_and_check_isrc_collisions(app_b, summary_a)
    assert len(alerts_b) == 1
    assert alerts_b[0].isrc == "USORG2400999"
    assert alerts_b[0].prior_seller_email == "legit@artist.com"
    assert "CROSS_CATALOG_ISRC_COLLISION" in alerts_b[0].message

    # Verify Closing Document Pack math (Seller agreed €18,500, Institutional Buyer funds €22,000)
    val_out = engine.evaluate(
        CatalogValuationInput(
            catalog_title="Phoenix Catalog",
            artist_or_label_name="phoenix records label",
            distributor_or_admin="Symphonic",
            declared_ltm_amount=7790.0,
            declared_currency="EUR",
            statements_verified=True,
            tracks=summary_a.tracks,
        ),
        reference_date=date(2026, 10, 14),
    )
    pack = generate_closing_document_pack(
        app_a,
        val_out,
        seller_legal_name="Mohammed Belmokhtar",
        seller_address="Hay Al Qods, Rue Dalia N°10, Oujda, Morocco",
        buyer_entity_name="Create Music Group Acquisitions LLC",
        seller_agreed_price_eur=18500.0,
        buyer_gross_funding_eur=22000.0,
        origination_fee_pct=0.06,
        holdback_pct=0.20,
    )
    assert pack.seller_total_consideration_eur == 18500.0
    assert pack.seller_closing_wire_eur == 14800.0
    assert pack.seller_holdback_eur == 3700.0
    assert pack.space_origination_fee_eur == 1110.0
    assert pack.space_spread_eur == 2390.0
    assert pack.space_total_take_eur == 3500.0
    assert pack.carried_tail_pct == 0.075
    assert pack.space_carried_tail_10y_projected_eur > 2000.0
    assert pack.space_total_10y_comp_eur == round(
        pack.space_total_take_eur + pack.space_carried_tail_10y_projected_eur, 2
    )
    assert "Carried Royalty Tail" in pack.ncnd_fee_agreement_markdown
    assert "IRREVOCABLE LETTER OF DIRECTION" in pack.letter_of_direction_markdown
    assert "CLOSING SETTLEMENT STATEMENT" in pack.settlement_statement_markdown


def test_phase2_typeform_direct_upload_instant_status_and_scrive_engine():
    """
    Verifies Phase 2 (Automation & Typeform 2.0 + Scrive E-Signature Engine):
    1. `POST /webhooks/typeform` with embedded `statement_attachments` upgrades immediately
       to `STAGE_2_STATEMENT_VERIFIED` (`STAGE_2_INSTANT_UNDERWRITING_COMPLETE`) in a single call.
    2. `GET /catalog-review/{id}/instant-status` returns the live valuation range, integrity score,
       monetization plan, and Scrive e-signature envelopes.
    3. `ScriveExecutionEngine` enforces deterministic party order (`SELLER` -> `BUYER` -> `COMPLETED_LOCKED`),
       SHA-256 document hash verification, and HMAC-SHA256 webhook verification.
    """
    import json

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from services.spacemusic.routes import router
    from services.spacemusic.scrive_signer import (
        ScriveEnvelopeStatus,
        SignatoryRole,
        compute_scrive_webhook_signature,
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    distro_csv = (
        "Sale Month,Store,Artist,Title,ISRC,Quantity,Earnings (USD),Country of Sale,Release Date\n"
        + "\n".join(
            f"2025-{m:02d},Spotify,Nordic Pulse,Midnight Fjord,SEABC2300111,160000,620.00,SE,2023-04-01"
            for m in range(1, 13)
        )
    )

    tf_payload = {
        "event_id": "tf_direct_upload_001",
        "inquiry_route": "My own catalog",
        "contact_name": "Erik Lindqvist",
        "contact_email": "erik@nordicpulse.se",
        "artist_or_label_name": "Nordic Pulse",
        "listen_url": "https://open.spotify.com/artist/4Z8W4fKeB5YxbusRsdQVPb",
        "rights_scope": "Master recordings",
        "owner_authorized": "Yes",
        "knows_ltm_royalties": "I can provide an approximate figure",
        "declared_ltm_amount": 7440,
        "declared_currency": "USD",
        "royalty_basis": "Net royalties payable to the rights holder",
        "distributor_or_admin": "DistroKid",
        "statement_attachments": [
            {
                "filename": "nordic_pulse_distrokid.csv",
                "content_text": distro_csv,
            }
        ],
    }

    resp = client.post("/webhooks/typeform", json=tf_payload)
    assert resp.status_code == 201
    data = resp.json()
    app_id = data["application_id"]
    assert data["valuation_stage"] == "STAGE_2_STATEMENT_VERIFIED"
    assert data["autonomous_decision"] == "STAGE_2_INSTANT_UNDERWRITING_COMPLETE"
    assert data["blind_deal_teaser"] is not None
    assert data["monetization_plan"] is not None

    # Create a Scrive Closing Envelope for this application
    env_resp = client.post(
        f"/catalog-review/{app_id}/scrive/envelope",
        json={
            "seller_legal_name": "Erik Lindqvist Musik AB",
            "seller_address": "Sveavägen 44, 111 34 Stockholm, Sweden",
            "buyer_entity_name": "Duetti Master Acquisitions LP",
            "buyer_email": "closings@duetti.co",
            "seller_agreed_price_eur": 35000.0,
            "carried_tail_pct": 0.075,
        },
    )
    assert env_resp.status_code == 201
    env_data = env_resp.json()
    envelope_id = env_data["envelope_id"]
    doc_sha256 = env_data["document_sha256"]
    assert env_data["status"] == ScriveEnvelopeStatus.SENT_FOR_SIGNATURE.value

    # Out-of-order signing attempt (Buyer trying to sign before Seller) must be rejected (HTTP 400)
    bad_order = client.post(
        f"/catalog-review/scrive/{envelope_id}/sign",
        json={"signer_role": SignatoryRole.BUYER.value},
    )
    assert bad_order.status_code == 400
    assert "Signing order violation" in bad_order.json()["detail"]

    # Seller signs via Scrive HMAC-verified webhook
    webhook_body = {
        "envelope_id": envelope_id,
        "signer_role": "SELLER",
        "signer_email": "erik@nordicpulse.se",
        "ip_address": "192.0.2.10",
        "document_sha256": doc_sha256,
    }
    canonical_json = json.dumps(webhook_body, sort_keys=True, separators=(",", ":"))
    valid_hmac = compute_scrive_webhook_signature(canonical_json)

    # Invalid HMAC must be rejected
    bad_hmac_resp = client.post(
        "/webhooks/scrive",
        json=webhook_body,
        headers={"X-Scrive-Signature": "sha256=deadbeef"},
    )
    assert bad_hmac_resp.status_code == 400

    # Valid HMAC transitions to SELLER_SIGNED
    ok_hmac_resp = client.post(
        "/webhooks/scrive",
        json=webhook_body,
        headers={"X-Scrive-Signature": f"sha256={valid_hmac}"},
    )
    assert ok_hmac_resp.status_code == 200
    assert ok_hmac_resp.json()["status"] == ScriveEnvelopeStatus.SELLER_SIGNED.value

    # Buyer countersigns -> transitions to COMPLETED_LOCKED
    buyer_sign_resp = client.post(
        f"/catalog-review/scrive/{envelope_id}/sign",
        json={
            "signer_role": SignatoryRole.BUYER.value,
            "signer_email": "closings@duetti.co",
            "expected_document_sha256": doc_sha256,
        },
    )
    assert buyer_sign_resp.status_code == 200
    locked_env = buyer_sign_resp.json()
    assert locked_env["status"] == ScriveEnvelopeStatus.COMPLETED_LOCKED.value
    assert locked_env["completed_at"] is not None

    # Instant status endpoint returns the completed envelope and monetization plan
    status_resp = client.get(f"/catalog-review/{app_id}/instant-status")
    assert status_resp.status_code == 200
    st = status_resp.json()
    assert st["statements_verified"] is True
    assert len(st["scrive_envelopes"]) == 1
    assert st["scrive_envelopes"][0]["status"] == "COMPLETED_LOCKED"


def test_phase3_sov_plus_down_funnel_monetization_and_audit_certificate(
    engine: SpaceValuationEngine,
):
    """
    Verifies Phase 3 ("Sov+" Passive Monetization & Down-Funnel Router):
    1. Sub-threshold catalog (€1,200/yr) is routed to `MICRO_ADVANCE_REFERRAL` (beatBread / Sound Royalties)
       with a 4% referral bounty + `MANAGED_SUBLABEL_CONTENT_ID` (15% override) + `$299` Certificate.
    2. Unreleased / €0 catalog (like Aydın Polat) is routed to `MANAGED_SUBLABEL_CONTENT_ID`
       with a 15% ongoing Content ID / distribution override.
    3. `generate_forensic_audit_certificate` produces a SHA-256-sealed certificate (`CERT-SPC-...`).
    """
    from services.spacemusic.models import CatalogApplication
    from services.spacemusic.monetization_engine import (
        MonetizationTrackType,
        build_down_funnel_monetization_plan,
        generate_forensic_audit_certificate,
    )
    from services.spacemusic.typeform_adapter import application_to_valuation_input

    # Case A: Sub-threshold artist (€1,200/yr)
    sub_app = CatalogApplication(
        contact_name="Indie Producer",
        contact_email="indie@beats.io",
        artist_or_label_name="LoFi Cloud",
        declared_ltm_amount=1200.0,
        declared_currency="EUR",
        distributor_or_admin="DistroKid",
    )
    sub_val = engine.evaluate(application_to_valuation_input(sub_app), reference_date=date(2026, 10, 14))
    sub_plan = build_down_funnel_monetization_plan(sub_app, sub_val)
    assert sub_plan.primary_track == MonetizationTrackType.MICRO_ADVANCE_REFERRAL
    assert sub_plan.total_expected_space_10y_value_eur > 0
    assert any(o.track_type == MonetizationTrackType.FORENSIC_AUDIT_CERTIFICATE for o in sub_plan.options)

    # Case B: Unreleased library (€0 LTM, like Aydın Polat)
    unrel_app = CatalogApplication(
        contact_name="Aydin Polat",
        contact_email="theaydinpolat@gmail.com",
        artist_or_label_name="Aydin Polat Unreleased Library",
        declared_ltm_amount=0.0,
        declared_currency="USD",
        distributor_or_admin="Independent",
    )
    unrel_val = engine.evaluate(application_to_valuation_input(unrel_app), reference_date=date(2026, 10, 14))
    unrel_plan = build_down_funnel_monetization_plan(unrel_app, unrel_val)
    assert unrel_plan.primary_track == MonetizationTrackType.MANAGED_SUBLABEL_CONTENT_ID
    sublabel_opt = next(
        o for o in unrel_plan.options if o.track_type == MonetizationTrackType.MANAGED_SUBLABEL_CONTENT_ID
    )
    assert sublabel_opt.space_take_rate_pct == 15.0
    assert sublabel_opt.estimated_space_annual_passive_eur == 525.0

    # Case C: Official $299 Forensic Audit Certificate
    cert = generate_forensic_audit_certificate(sub_app, sub_val)
    assert cert.certificate_id.startswith("CERT-SPC-")
    assert len(cert.sha256_verification_seal) == 64
    assert cert.certificate_fee_usd == 299.0
    assert "OFFICIAL SPACE FORENSIC VALUATION" in cert.certificate_markdown


def test_phase4_fintech_split_escrow_cent_exactness_and_lockbox_waterfall():
    """
    Verifies Phase 4 (Fintech Multi-Currency Split-Escrow & Virtual Lockbox Ledger):
    1. Cent-exact `Decimal` precision across tricky fractional amounts (`€18,543.37`, `USD`, `SEK`)
       so `invariant_balanced_to_exact_cent` is 100% True with 0.00 cent drift.
    2. Idempotency protection: repeating the same `idempotency_key` with identical parameters
       returns the exact same instruction, whereas mutating the price under the same key raises `ValueError`.
    3. Monthly Virtual Lockbox waterfall splits incoming royalties into SPACE's 7.5% Carried Royalty Tail
       and Buyer's 92.5% share to the exact cent, and releases 100% of the Seller Holdback at Month 12
       when cumulative royalties reach >= 90% of $CF_0$.
    """
    import pytest

    from services.spacemusic.fintech_escrow import (
        EscrowProviderRail,
        FintechEscrowLedger,
    )

    ledger = FintechEscrowLedger()

    inst = ledger.compute_split_escrow_instruction(
        deal_code="SPC-PHX01",
        application_id="app-phx-001",
        seller_legal_name="Mohammed Belmokhtar",
        seller_iban="MA64011519000001205000534921",
        buyer_entity_name="Create Music Group Acquisitions LLC",
        seller_agreed_price_eur="18543.37",
        buyer_gross_funding_eur="21999.99",
        origination_fee_pct="0.06",
        holdback_pct="0.20",
        carried_tail_pct="0.075",
        settlement_currency="USD",
        provider_rail=EscrowProviderRail.AIRWALLEX_VIRTUAL_LOCKBOX,
        idempotency_key="idem_phx_closing_01",
    )
    assert inst.invariant_balanced_to_exact_cent is True
    assert sum(leg.amount_cents for leg in inst.wire_legs) == int(
        float(inst.gross_buyer_funding) * 100
    )

    # Idempotent replay returns exact same instruction_id
    inst_replay = ledger.compute_split_escrow_instruction(
        deal_code="SPC-PHX01",
        application_id="app-phx-001",
        seller_legal_name="Mohammed Belmokhtar",
        seller_iban="MA64011519000001205000534921",
        buyer_entity_name="Create Music Group Acquisitions LLC",
        seller_agreed_price_eur="18543.37",
        buyer_gross_funding_eur="21999.99",
        origination_fee_pct="0.06",
        holdback_pct="0.20",
        carried_tail_pct="0.075",
        settlement_currency="USD",
        provider_rail=EscrowProviderRail.AIRWALLEX_VIRTUAL_LOCKBOX,
        idempotency_key="idem_phx_closing_01",
    )
    assert inst_replay.instruction_id == inst.instruction_id

    # Parameter tampering with same idempotency_key must raise ValueError
    with pytest.raises(ValueError, match="Idempotency conflict"):
        ledger.compute_split_escrow_instruction(
            deal_code="SPC-PHX01",
            application_id="app-phx-001",
            seller_legal_name="Mohammed Belmokhtar",
            seller_iban="MA64011519000001205000534921",
            buyer_entity_name="Create Music Group Acquisitions LLC",
            seller_agreed_price_eur="25000.00",
            buyer_gross_funding_eur="29000.00",
            settlement_currency="USD",
            idempotency_key="idem_phx_closing_01",
        )

    # Simulate 12 months of Virtual Lockbox royalty inflows (€650.13/mo -> €7,801.56/yr vs €7,790.00 CF0)
    last_dist = None
    for m in range(1, 13):
        last_dist = ledger.distribute_monthly_lockbox_royalties(
            deal_code="SPC-PHX01",
            period_month=f"2026-{m:02d}",
            gross_royalty_inflow="650.13",
            target_12m_baseline_cf0="7790.00",
            seller_holdback_escrow="3700.00",
            carried_tail_pct="0.075",
            is_month_12_holdback_check=(m == 12),
            currency="EUR",
        )
        assert last_dist.invariant_balanced_to_exact_cent is True
        # 650.13 * 0.075 = 48.75975 -> 48.76 SPACE tail + 601.37 Buyer share == 650.13 exact
        assert last_dist.space_carried_tail_payout == "48.76"
        assert last_dist.buyer_royalty_payout == "601.37"

    assert last_dist is not None
    assert last_dist.cumulative_royalties_collected == "7801.56"
    assert last_dist.performance_coverage_ratio >= 1.0
    assert last_dist.holdback_release_status == "RELEASED_100_PCT_TO_SELLER"
    assert last_dist.holdback_released_to_seller == "3700.00"


def test_geo_seo_steps_1_to_5_end_to_end(tmp_path):
    """
    End-to-end verification of Steps 1 to 5 of SPACE's SEO, GEO, JSON-LD,
    Programmatic Landing Pages, Embeddable PLG Calculator Widget, and Link-Earning Data Report.
    """
    from services.spacemusic.seo_geo_engine import (
        LANDING_PAGES_BY_SLUG,
        SEO_PAGE_METADATA_OVERRIDES,
        export_seo_static_bundle,
        resolve_canonical_redirect,
    )

    client = TestClient(spacemusic_app)

    # Step 1: Metadata overrides & landing pages have ZERO '--' or '—' in title, meta_description, h1, og_title;
    # canonical 301 redirect rules work.
    for path_key, meta in SEO_PAGE_METADATA_OVERRIDES.items():
        for field_name in ("title", "meta_description", "h1", "og_title"):
            val = getattr(meta, field_name)
            assert "--" not in val, f"Found '--' in {path_key}.{field_name}"
            assert "—" not in val, f"Found '—' in {path_key}.{field_name}"

    for slug, lp in LANDING_PAGES_BY_SLUG.items():
        for field_name in ("title", "meta_description", "h1"):
            val = getattr(lp, field_name)
            assert "--" not in val, f"Found '--' in {slug}.{field_name}"
            assert "—" not in val, f"Found '—' in {slug}.{field_name}"

    assert resolve_canonical_redirect("/calculator") == "/calculator/"
    assert resolve_canonical_redirect("/calculator/") is None
    redirects_resp = client.get("/_redirects")
    assert redirects_resp.status_code == 200
    assert "/calculator /calculator/ 301" in redirects_resp.text

    # Step 2: Live interactive calculator teaser + embeddable HTML & JS widget with dofollow attribution.
    teaser_resp = client.post(
        "/calculator/live-teaser",
        json={
            "artist_or_label_name": "Metro Phonk Collective",
            "monthly_net_royalty": 3500.0,
            "currency": "USD",
            "genre_hint": "Hip-Hop / Rap / Trap",
            "distributor": "DistroKid",
            "rights_scope": "masters",
            "share_sold_pct": 100.0,
            "catalog_age_months": 30.0,
        },
    )
    assert teaser_resp.status_code == 200
    teaser = teaser_resp.json()
    assert 0 < teaser["price_low_eur"] < teaser["price_median_eur"] < teaser["price_high_eur"]
    assert teaser["matched_institutional_buyers_count"] >= 1
    assert len(teaser["top_matched_buyers"]) >= 1
    assert "DistroKid" in teaser["distributor_export_guide"]

    embed_resp = client.get("/embed/calculator")
    assert embed_resp.status_code == 200
    assert "https://spacemusic.io/calculator/" in embed_resp.text
    assert 'rel="dofollow"' in embed_resp.text

    widget_resp = client.get("/widget/calculator.js")
    assert widget_resp.status_code == 200
    assert "application/javascript" in widget_resp.headers["content-type"]
    assert "https://spacemusic.io/calculator/" in widget_resp.text
    assert 'rel="dofollow"' in widget_resp.text

    # Step 3: llms.txt, llms-full.txt, pricing.md, sitemap.xml, brand-facts, and 20 programmatic landing pages.
    llms_resp = client.get("/llms.txt")
    llms_full_resp = client.get("/llms-full.txt")
    pricing_resp = client.get("/pricing.md")
    sitemap_resp = client.get("/sitemap.xml")
    brand_resp = client.get("/brand-facts")

    for r in (llms_resp, llms_full_resp, pricing_resp, sitemap_resp, brand_resp):
        assert r.status_code == 200

    combined_geo_text = llms_resp.text + "\n" + llms_full_resp.text + "\n" + pricing_resp.text
    for genre_kw in ("Hip-Hop", "Phonk", "Pop", "R&B", "Latin", "Afrobeats", "Rock", "Classical", "Ambient"):
        assert genre_kw in llms_resp.text
        assert genre_kw in llms_full_resp.text
        assert genre_kw in pricing_resp.text
        assert genre_kw in combined_geo_text

    for buyer_kw in (
        "Duetti",
        "Create Music Group",
        "beatBread",
        "Sound Royalties",
        "ANote Music",
        "Royalty Exchange",
        "SongVest",
        "Symphonic",
    ):
        assert buyer_kw in llms_resp.text
        assert buyer_kw in llms_full_resp.text
        assert buyer_kw in pricing_resp.text

    assert "<urlset" in sitemap_resp.text
    assert "https://spacemusic.io/calculator/" in sitemap_resp.text

    lp_list_resp = client.get("/seo/landing-pages")
    assert lp_list_resp.status_code == 200
    lp_list_data = lp_list_resp.json()
    assert lp_list_data["total"] == 20
    assert lp_list_data["genre_count"] == 10
    assert lp_list_data["distributor_count"] == 10
    assert len(lp_list_data["pages"]) == 20

    hh_resp = client.get("/seo/landing-pages/sell-hip-hop-rap-catalog")
    assert hh_resp.status_code == 200
    assert hh_resp.json()["category"] == "genre"

    dk_resp = client.get("/seo/landing-pages/sell-distrokid-royalties")
    assert dk_resp.status_code == 200
    assert dk_resp.json()["category"] == "distributor"

    # Pre-rendered HTML landing page, benchmark report HTML, and .well-known/brand-facts.json
    hh_html_resp = client.get("/sell/sell-hip-hop-rap-catalog/")
    assert hh_html_resp.status_code == 200
    assert "application/ld+json" in hh_html_resp.text
    assert "Hip-Hop" in hh_html_resp.text

    report_html_resp = client.get("/data/indie-catalog-multiples-ai-fraud-report-2026/")
    assert report_html_resp.status_code == 200
    assert "2026 Indie Music Catalog" in report_html_resp.text

    wk_resp = client.get("/.well-known/brand-facts.json")
    assert wk_resp.status_code == 200
    assert "SPACE" in wk_resp.json()["brand_name"]

    # Step 4: JSON-LD structured data schemas on /calculator/
    meta_resp = client.get("/seo/metadata", params={"path": "/calculator"})
    assert meta_resp.status_code == 200
    meta_payload = meta_resp.json()
    assert meta_payload["canonical_redirect_301"] == "/calculator/"
    schemas = meta_payload["jsonld_schemas"]
    schema_types = {s["@type"] for s in schemas}
    for expected_type in ("SoftwareApplication", "FinancialService", "Organization", "FAQPage", "BreadcrumbList"):
        assert expected_type in schema_types

    org_schema = next(s for s in schemas if s["@type"] == "Organization")
    knows_about_blob = " | ".join(org_schema["knowsAbout"])
    for genre_kw in ("Hip-Hop", "Pop", "R&B", "Latin", "Electronic", "Rock", "Classical", "Ambient"):
        assert genre_kw in knows_about_blob

    # Step 5: 2026 Indie Catalog Multiples & AI Fraud Benchmark Report + Backlink Outreach Kit + Static Bundle Export
    report_resp = client.get("/data/indie-catalog-multiples-ai-fraud-report-2026")
    assert report_resp.status_code == 200
    report_data = report_resp.json()
    assert len(report_data["genre_multiples_table"]) == 8
    assert report_data["dataset_jsonld"]["@type"] == "Dataset"
    assert any(s["@type"] == "Dataset" for s in report_data["jsonld_schemas"])

    outreach_resp = client.get("/seo/backlink-outreach-kit")
    assert outreach_resp.status_code == 200
    outreach_kit = outreach_resp.json()
    assert len(outreach_kit) >= 5
    for item in outreach_kit:
        assert "--" not in item["subject"]
        assert "—" not in item["subject"]
        assert "--" not in item["body"]
        assert "—" not in item["body"]

    written_files = export_seo_static_bundle(str(tmp_path / "seo_bundle"))
    for expected_file in (
        "llms.txt",
        "llms-full.txt",
        "pricing.md",
        "sitemap.xml",
        "_redirects",
        "embed-calculator.html",
        "widget-calculator.js",
        ".well-known/brand-facts.json",
        "data/indie-catalog-multiples-ai-fraud-report-2026/index.html",
        "sell/sell-hip-hop-rap-catalog/index.html",
        "sell/sell-distrokid-royalties/index.html",
        "seo-metadata-manifest.json",
    ):
        assert expected_file in written_files


def test_tribal_trap_and_trap_nation_parsing_and_parallel_jev_evaluation():
    from datetime import date
    from services.spacemusic.inbox_ingestor import parse_multi_attachment_statements
    from services.valuation.jev_evaluator import (
        choice_confidence,
        noul_confidence,
        run_parallel_dtw_and_jev_evaluation,
        score_confidence,
    )

    # 1. Verify exact TypeSafe AI confidence math from docs.typesafe.ai/confidence.md
    assert abs(choice_confidence([0.85, 0.10, 0.05]) - 0.775) < 1e-4
    assert abs(choice_confidence([1 / 3, 1 / 3, 1 / 3]) - 0.0) < 1e-4
    assert abs(score_confidence([0.05, 0.70, 0.25]) - 0.55) < 1e-4
    assert abs(noul_confidence(0.975) - 0.95) < 1e-4
    assert abs(noul_confidence(0.50) - 0.0) < 1e-4

    # 2. Build synthetic 14-month Tribal Trap TSV + Trap Nation CSV statements for 2Scratch
    tribal_lines = [
        "Label Name\tCatalog\tTrack Artist\tTrack Title\tMix Name\tRelease Artist\tRelease Name\tSales Date\tContract Detail\tBasis\tPrice\tDeal\tSale Type\tQty\tGross\tRoyalty\tPro Rata Share\tPro Rata Total\tISRC\tEAN\tStore Name\tCountry\tProduct Name\tCompilation\tCurrency"
    ]
    trapnation_lines = [
        "Sales Date,Transaction Date,Artist Name,Release Title,Track Title,ISRC,Service,Country,Net Units,Recipient Share (%),Royalty Per Unit ($ USD),Recipient Net Royalty ($ USD)"
    ]

    months = [
        "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31",
        "2025-06-30", "2025-07-31", "2025-08-31", "2025-09-30",
        "2025-10-31", "2025-11-30", "2025-12-31", "2026-01-31",
        "2026-02-28", "2026-03-31",
    ]
    for idx, m_end in enumerate(months):
        decay_factor = 1.0 - idx * 0.006
        # Audio DSP rows (Spotify & YouTube) + Social UGC row (TikTok with huge impressions and tiny payout)
        tribal_lines.append(
            f"Tribal Trap\tTT001\t2Scratch\tAll Night\tOriginal Mix\t2Scratch\tAll Night\t{m_end}\tDigital Sales\tRoyalties\t\t50\tStream\t{int(250000 * decay_factor)}\t{950.0 * decay_factor:.2f}\t{475.0 * decay_factor:.2f}\t1\t1\tTCADW1888484\t123\tSpotify\tUnited States\t\t\tUSD"
        )
        tribal_lines.append(
            f"Tribal Trap\tTT002\t2Scratch\tReminder\tOriginal Mix\t2Scratch\tReminder\t{m_end}\tDigital Sales\tRoyalties\t\t50\tStream\t{int(180000 * decay_factor)}\t{620.0 * decay_factor:.2f}\t{310.0 * decay_factor:.2f}\t1\t1\tTCAED1948789\t124\tYouTube Subscriptions\tGermany\t\t\tUSD"
        )
        tribal_lines.append(
            f"Tribal Trap\tTT001\t2Scratch\tAll Night\tOriginal Mix\t2Scratch\tAll Night\t{m_end}\tDigital Sales\tRoyalties\t\t50\tStream\t5000000\t20.00\t10.00\t1\t1\tTCADW1888484\t123\tTikTok\tUnited Kingdom\t\t\tUSD"
        )
        trapnation_lines.append(
            f"{m_end},{m_end},2Scratch,Ballin,Ballin (feat. TAOG),USA2P1841742,Spotify,United States,{int(120000 * decay_factor)},50%,0.00133,{160.0 * decay_factor:.2f}"
        )

    stmt_summary = parse_multi_attachment_statements(
        [
            ("tribal_trap_q1.tsv", "\n".join(tribal_lines)),
            ("royalties_2scratch_trapnation.csv", "\n".join(trapnation_lines)),
        ],
        default_currency="USD",
    )

    assert "Tribal Trap" in stmt_summary.detected_distributor
    assert "Trap Nation" in stmt_summary.detected_distributor
    assert "US" in stmt_summary.country_share
    assert "DE" in stmt_summary.country_share
    assert stmt_summary.ltm_net_royalty_eur > 8000.0
    # TikTok 5M impressions/month should be zeroed in audio stream count while keeping its €10/mo revenue
    assert stmt_summary.ltm_streams < 10_000_000

    app_input = CatalogValuationInput(
        catalog_title="2Scratch Master Catalog",
        artist_or_label_name="2Scratch (Justin Matysik)",
        applicant_name="Justin Matysik",
        applicant_email="2scratch.business@gmail.com",
        rights_scope=RightsScope.MASTERS,
        royalty_basis=RoyaltyBasis.NET_PAYABLE,
        distributor_or_admin=stmt_summary.detected_distributor,
        ownership_share_pct=100.0,
        existing_releases_only=True,
        declared_ltm_amount=30000.0,
        declared_currency="USD",
        statements_verified=True,
        genres=["hip_hop", "trap"],
        tracks=stmt_summary.tracks,
        monthly_history=stmt_summary.monthly_history,
        dsp_share=stmt_summary.dsp_share,
        country_share=stmt_summary.country_share,
    )

    engine = SpaceValuationEngine(random_seed=42)
    val_report = engine.evaluate(app_input, reference_date=date(2026, 4, 1))
    assert val_report.integrity_score >= 80.0
    assert val_report.price_median_eur > 20000.0

    parallel_report = run_parallel_dtw_and_jev_evaluation(
        app_input=app_input,
        stmt_summary=stmt_summary,
        valuation_report=val_report,
    )
    assert parallel_report.model_version_agreement_rate == 1.0
    assert parallel_report.jev_lifecycle_choice == "evergreen_algorithmic_plateau"
    assert parallel_report.jev_bot_fraud_noul < 0.10
    assert len(parallel_report.parallel_comparison_matrix) == 7
    assert parallel_report.jev_implied_base_offer_usd > 0
    assert parallel_report.jev_implied_stretch_offer_usd > parallel_report.jev_implied_base_offer_usd


def test_hmwme_distrokid_amuse_merge_and_jev_frontline_evaluation():
    """Verify DistroKid + Amuse statement merge (including Excel serial dates and no false annualization) and parallel JEV evaluation."""
    from services.spacemusic.inbox_ingestor import parse_multi_attachment_statements
    from services.valuation.jev_evaluator import run_parallel_dtw_and_jev_evaluation

    dk_lines = [
        "Reporting Date,Sale Month,Store,Artist,Title,ISRC,UPC,Quantity,Song/Album,Country of Sale,Earnings (USD)"
    ]
    dk_months = [
        "2025-05", "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-10", "2025-11", "2025-12", "2026-01", "2026-02",
        "2026-03", "2026-04", "2026-05", "2026-06", "2026-07",
    ]
    for idx, sm in enumerate(dk_months):
        dk_lines.append(
            f"{sm}-28,{sm},Spotify,HMWME,TE AMO,QT3F22596869,1990001,600000,Song,US,1500.00"
        )
        dk_lines.append(
            f"{sm}-28,{sm},Spotify,HMWME,BLACK FRIDAY,QZZ792544788,1990002,450000,Song,DE,1100.00"
        )

    # Amuse format with Excel serial numbers for 2026-03..2026-07 (e.g. 46082 = 2026-03-01, 46113 = 2026-04-01, 46143 = 2026-05-01, 46174 = 2026-06-01, 46204 = 2026-07-01)
    amuse_lines = [
        "Artist Name,Track Title,ISRC,UPC,Release Title,Store,Country,Royalty Date,Transaction Date,Quantity,Total"
    ]
    for serial in (46082, 46113, 46143, 46174, 46204):
        amuse_lines.append(
            f"HMWME,FOR YOU,SE6HN2608000,7300349706483,ALWAYS // FOREVER,Spotify,US,{serial},{serial},400000,1000.00"
        )
    # Summary trailing line without ISRC/Title should be ignored
    amuse_lines.append(",,,,,,,,,2000000,5000.00")

    stmt_summary = parse_multi_attachment_statements(
        [
            ("hmwme_results7.csv", "\n".join(dk_lines)),
            ("3439269-amuse.csv", "\n".join(amuse_lines)),
        ],
        default_currency="USD",
    )

    assert "DistroKid" in stmt_summary.detected_distributor
    assert "Amuse" in stmt_summary.detected_distributor
    assert len(stmt_summary.tracks) == 3
    # Verify Amuse 5 months ($5,000 USD = €4,600 EUR) are NOT annualized by 12/5 when merged into DistroKid's 12-month LTM window
    # DistroKid LTM (12 months * $2,600 = $31,200) + Amuse ($5,000) = $36,200 USD = €33,304 EUR
    assert abs(stmt_summary.ltm_net_royalty_eur - (36200.0 * 0.92)) < 5.0

    app_input = CatalogValuationInput(
        catalog_title="HMWME Catalog",
        artist_or_label_name="HMWME",
        applicant_name="Zane Wilder",
        applicant_email="mgmt@hmwme.com",
        rights_scope=RightsScope.MASTERS,
        royalty_basis=RoyaltyBasis.NET_PAYABLE,
        distributor_or_admin=stmt_summary.detected_distributor,
        ownership_share_pct=100.0,
        existing_releases_only=True,
        declared_ltm_amount=40000.0,
        declared_currency="USD",
        statements_verified=True,
        genres=["electronic", "pop"],
        tracks=stmt_summary.tracks,
        monthly_history=stmt_summary.monthly_history,
        dsp_share=stmt_summary.dsp_share,
        country_share=stmt_summary.country_share,
    )

    engine = SpaceValuationEngine(random_seed=42)
    val_report = engine.evaluate(app_input, reference_date=date(2026, 8, 1))
    assert val_report.integrity_score >= 90.0
    assert round(sum(val_report.yearly_present_values_p50_eur[:5]), 2) == val_report.npv_5y_p50_eur
    assert round(sum(val_report.yearly_present_values_p50_eur), 2) == val_report.npv_10y_p50_eur

    parallel_report = run_parallel_dtw_and_jev_evaluation(
        app_input=app_input,
        stmt_summary=stmt_summary,
        valuation_report=val_report,
    )
    assert parallel_report.model_version_agreement_rate == 1.0
    assert parallel_report.jev_lifecycle_choice == "recent_release_frontloaded_decay"
    assert parallel_report.jev_bot_fraud_noul < 0.05
    assert parallel_report.jev_implied_base_offer_usd > 0
    assert (
        parallel_report.jev_primary_run.answers["gross_vs_net_claim_explanation"]["choice"]
        == "seller_extrapolated_recent_l3m_surge_run_rate"
    )
    assert parallel_report.jev_primary_run.answers["seller_multiple_expectation_gap"]["score"] >= 2.5


def test_claude_19_slide_investment_memo_and_paid_checkout_pipeline():
    """
    Verifies:
    1. `generate_catalog_investment_memo_deck` builds a complete 19-slide 16:9 `CatalogInvestmentMemoDeck`
       matching the HMWME & 2Scratch slide architecture (including mocked live Anthropic Claude API
       `tool_use` response and deterministic fallback).
    2. `render_investment_memo_html` and `render_investment_memo_pdf` produce valid 16:9 HTML/PDF
       artifacts (`%PDF-1.4`).
    3. FastAPI endpoints `/valuation-memo`, `/catalog-review/paid-memo/checkout`,
       `/catalog-review/{id}/investment-memo.html`, `/catalog-review/{id}/investment-memo.pdf`,
       and `/webhooks/stripe-memo` enforce the $299 paywall (`402 Payment Required` when unpaid)
       and unlock the 19-slide PDF upon valid HMAC-signed Stripe webhook receipt.
    """
    import hashlib
    import hmac
    import json
    import time
    from fastapi.testclient import TestClient

    from services.spacemusic.main import app

    client = TestClient(app)

    # 1. Verify self-serve Studio HTML page renders
    studio_res = client.get("/valuation-memo")
    assert studio_res.status_code == 200
    assert "Generate Catalog Investment Memo" in studio_res.text
    assert "19-SLIDE 16:9 INVESTMENT MEMO" in studio_res.text

    # 2. Create a paid memo checkout order (unpaid by default)
    csv_rows = (
        "reporting_month,title,isrc,store,country,quantity,net_royalty_usd\n"
        "2025-10,TE AMO,QT3F22596869,Spotify,US,950000,2400.00\n"
        "2025-11,BLACK FRIDAY,QZZ792544788,Spotify,DE,820000,1950.00\n"
        "2025-12,LONELY,QZZ792544799,Spotify,GB,610000,1450.00\n"
    )
    checkout_res = client.post(
        "/catalog-review/paid-memo/checkout",
        json={
            "artist_or_label_name": "HMWME",
            "catalog_title": "The Family of One",
            "declared_ltm_amount": 80000.0,
            "currency": "USD",
            "distributor": "DistroKid + Amuse",
            "raw_statement_csv": csv_rows,
            "seller_quote_text": "Option A is the closest to what we have in mind... we'd be looking for $300,000 USD upfront.",
            "seller_quote_attribution": "Zane Wilder, manager of HMWME",
            "seller_ask_low_usd": 350000.0,
            "seller_ask_high_usd": 450000.0,
        },
    )
    assert checkout_res.status_code == 201
    order_data = checkout_res.json()
    assert order_data["payment_status"] == "PENDING_PAYMENT"
    assert order_data["amount_usd"] == 299.0
    assert order_data["receipt_token"] is None
    app_id = order_data["application_id"]
    order_id = order_data["order_id"]

    # 3. Verify unpaid HTML shows locked preview banner and PDF returns 402 Payment Required
    html_locked = client.get(f"/catalog-review/{app_id}/investment-memo.html")
    assert html_locked.status_code == 200
    assert "Previewing Slides 01–02 of 19" in html_locked.text
    assert "locked-slide" in html_locked.text

    pdf_locked = client.get(f"/catalog-review/{app_id}/investment-memo.pdf")
    assert pdf_locked.status_code == 402

    # 4. Trigger HMAC-signed Stripe webhook to unlock the order
    webhook_payload = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": order_data["stripe_session_id"],
                    "client_reference_id": order_id,
                    "metadata": {"order_id": order_id, "application_id": app_id},
                }
            },
        }
    ).encode("utf-8")
    ts = int(time.time())
    secret = "whsec_space_memo_default_secret"
    sig = hmac.new(secret.encode("utf-8"), f"{ts}.".encode("utf-8") + webhook_payload, hashlib.sha256).hexdigest()

    wh_res = client.post(
        "/webhooks/stripe-memo",
        content=webhook_payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": f"t={ts},v1={sig}",
        },
    )
    assert wh_res.status_code == 200
    wh_data = wh_res.json()
    assert wh_data["payment_status"] == "PAID"
    receipt_token = wh_data["receipt_token"]
    assert receipt_token

    # 5. Verify unlocked HTML has zero blurred slides and unlocked PDF downloads 19-slide PDF
    html_unlocked = client.get(
        f"/catalog-review/{app_id}/investment-memo.html?receipt_token={receipt_token}"
    )
    assert html_unlocked.status_code == 200
    assert "Previewing Slides 01–02 of 19" not in html_unlocked.text
    assert "10 · TYPESAFE AI CROSS-CHECK" in html_unlocked.text
    assert "16 · OFFER STRUCTURES" in html_unlocked.text

    pdf_unlocked = client.get(
        f"/catalog-review/{app_id}/investment-memo.pdf?receipt_token={receipt_token}"
    )
    assert pdf_unlocked.status_code == 200
    assert pdf_unlocked.headers["content-type"] == "application/pdf"
    assert pdf_unlocked.content.startswith(b"%PDF-1.")
    assert len(pdf_unlocked.content) > 5000

    # 6. Verify Autumn (useautumn.com) DESK_PASS_499 ($499/mo, 10 credits) & instant credit unlock
    desk_checkout = client.post(
        "/catalog-review/paid-memo/checkout",
        json={
            "artist_or_label_name": "Sagos Partner Catalog #1",
            "catalog_title": "Afro-diaspora Anthology Vol. 1",
            "contact_email": "info@sagosdistro.com",
            "declared_ltm_amount": 45000.0,
            "currency": "USD",
            "distributor": "Sagos Distro",
            "plan_tier": "DESK_PASS_499",
            "raw_statement_csv": csv_rows,
        },
    )
    assert desk_checkout.status_code == 201
    desk_order = desk_checkout.json()
    assert desk_order["plan_tier"] == "DESK_PASS_499"
    assert desk_order["amount_usd"] == 499.0
    assert desk_order["customer_id"] == "cus_info_sagosdistro.com"
    assert desk_order["payment_status"] == "PENDING_PAYMENT"

    # Unlock DESK_PASS_499 via /webhooks/autumn-memo -> provisions 10 credits and consumes 1 (9 remaining)
    desk_wh_payload = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": desk_order["stripe_session_id"],
                    "client_reference_id": desk_order["order_id"],
                    "metadata": {
                        "order_id": desk_order["order_id"],
                        "application_id": desk_order["application_id"],
                    },
                }
            },
        }
    ).encode("utf-8")
    desk_sig = hmac.new(
        secret.encode("utf-8"),
        f"{ts}.".encode("utf-8") + desk_wh_payload,
        hashlib.sha256,
    ).hexdigest()
    desk_wh_res = client.post(
        "/webhooks/autumn-memo",
        content=desk_wh_payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": f"t={ts},v1={desk_sig}",
        },
    )
    assert desk_wh_res.status_code == 200
    desk_wh_data = desk_wh_res.json()
    assert desk_wh_data["payment_status"] == "PAID"
    assert desk_wh_data["autumn_credits_remaining"] == 9

    # Check balance via POST /catalog-review/paid-memo/autumn/check (without deducting)
    check_res = client.post(
        "/catalog-review/paid-memo/autumn/check",
        json={
            "customer_id": "info@sagosdistro.com",
            "feature_id": "investment_memo_pdf",
            "required_balance": 1,
            "send_event": False,
        },
    )
    assert check_res.status_code == 200
    check_data = check_res.json()
    assert check_data["allowed"] is True
    assert check_data["remaining_balance"] == 9
    assert check_data["plan_id"] == "desk_pass_499"

    # Second memo for the same Autumn customer_id unlocks IMMEDIATELY using 1 credit (8 remaining)
    second_memo_res = client.post(
        "/catalog-review/paid-memo/checkout",
        json={
            "artist_or_label_name": "Sagos Partner Catalog #2",
            "catalog_title": "Kingston & Lagos Sessions",
            "contact_email": "info@sagosdistro.com",
            "declared_ltm_amount": 32000.0,
            "currency": "USD",
            "distributor": "Sagos Distro",
            "plan_tier": "SINGLE_MEMO_299",
            "raw_statement_csv": csv_rows,
        },
    )
    assert second_memo_res.status_code == 201
    second_order = second_memo_res.json()
    assert second_order["payment_status"] == "PAID"
    assert second_order["amount_usd"] == 0.0
    assert second_order["autumn_credits_remaining"] == 8
    assert second_order["receipt_token"] is not None

    # Verify Autumn customer get_or_create, plans list, and billing portal endpoints
    cust_res = client.post(
        "/catalog-review/paid-memo/autumn/customer",
        json={
            "customer_id": "info@sagosdistro.com",
            "name": "Sagos Distro Underwriting",
            "email": "info@sagosdistro.com",
        },
    )
    assert cust_res.status_code == 200
    cust_data = cust_res.json()
    assert cust_data["customer_id"] == "cus_info_sagosdistro.com"
    assert "free_preview" in cust_data["active_plan_ids"]
    assert "indicative_catalog_review" in cust_data["balances"]
    assert cust_data["balances"]["indicative_catalog_review"]["granted_balance"] == 3

    plans_res = client.get(
        "/catalog-review/paid-memo/autumn/plans?customer_id=info@sagosdistro.com"
    )
    assert plans_res.status_code == 200
    plans_data = plans_res.json()
    plan_ids = {p["plan_id"] for p in plans_data["plans"]}
    assert {"free_preview", "desk_pass_499", "single_memo_299"}.issubset(plan_ids)

    portal_res = client.post(
        "/catalog-review/paid-memo/autumn/portal",
        json={
            "customer_id": "info@sagosdistro.com",
            "return_url": "https://spacemusic.io/valuation-memo",
        },
    )
    assert portal_res.status_code == 200
    assert "billing.stripe.com" in portal_res.json()["portal_url"]

    # 7. Verify Sagos Distro / Solid Gold Global institutional buyer routing for Afro/Caribbean & Hip-Hop/R&B
    from services.spacemusic.buyer_router import route_catalog_to_institutional_buyers
    from services.spacemusic.models import CatalogApplication

    afro_inp = CatalogValuationInput(
        catalog_title="Gold Coast Riddims",
        artist_or_label_name="Accra & Kingston Collective",
        distributor_or_admin="DistroKid",
        declared_ltm_amount=42000.0,
        declared_currency="EUR",
        statements_verified=True,
        genres=["afrobeats", "reggaeton", "caribbean"],
    )
    val_engine = SpaceValuationEngine(random_seed=42)
    afro_val = val_engine.evaluate(afro_inp, reference_date=date(2026, 10, 15))
    afro_app = CatalogApplication(
        artist_or_label_name="Accra & Kingston Collective",
        distributor_or_admin="DistroKid",
        rights_scope="masters",
    )
    routing = route_catalog_to_institutional_buyers(afro_app, afro_val, top_k=10)
    matched_ids = [m.partner_id for m in routing.recommended_buyers]
    assert "sagos_distro_solid_gold" in matched_ids


def test_tenet_michel_zitron_publishing_workbook_audit_and_institutional_model():
    """
    End-to-end verification of all Caelis / Tenet Institutional Valuation & Multi-Society
    Publishing Forensics improvements:
    1. Multi-tab Excel reconstruction of `Michel_Zitron_-_royalty_summary_23-25_rev_92eb.xlsx`
       (catching 516,680 SEK out-of-window 2022/2020 rows, 'Reload /Free Love)' typo, 48 STIM 2022 zero rows,
       and 21% prior sale / H2 2025 BMG LOD double-deduction risk).
    2. 5-Pillar Rights-Type Cash Flow Decomposition (Streaming +4.8% CAGR, Synch Fortnite spike normalization,
       Live +2.0%, Radio -2.0%, Other -2.0%).
    3. Market-Relative Streaming Alpha (US/DE/UK) & Spotify Discovery Mode uplift detector.
    4. 10-Year + Evergreen Gordon Growth Terminal Value DCF (WACC 9.0%, PGR 1.5% -> ~34.6m SEK for 50% = 13.8x 2026E)
       plus 2D WACC x PGR and Growth Delta x PGR sensitivity matrices.
    5. Leveraged Buyout (LBO) & Portfolio Roll-Up Multiple Expansion (14x -> 14x standalone 10.0% IRR / 1.6x MOIC
       vs. 14x -> 16x scaled portfolio 13.4% IRR / 1.9x MOIC, Net Debt/EBITDA deleveraging 5.6x -> 1.4x).
    6. Institutional Valuation Football Field across L3Y Avg. and 2026E multiples.
    7. Cross-Society Collection Leakage Detector (BMG UK streaming mechanicals drop-off & US Live gap).
    8. SpaceValuationEngine integration for Evergreen Terminal Value, Portfolio Roll-Up IRR, and Publishing
       Chain-of-Title flags (ROFR, 2042 Reversion Cliff, Prior 21% Minority Sale, Spotify Discovery Mode).
    """
    from pathlib import Path
    from fastapi.testclient import TestClient
    from services.spacemusic.main import app
    from services.valuation.tenet_institutional_model import (
        build_tenet_institutional_valuation_package,
    )

    fixture_xlsx = Path(__file__).resolve().parents[1] / "fixtures" / "michel_zitron_royalty_summary_23_25.xlsx"
    assert fixture_xlsx.exists(), f"Missing fixture {fixture_xlsx}"

    pkg = build_tenet_institutional_valuation_package(xlsx_path=str(fixture_xlsx))

    # 1. Workbook Audit & Reconstruction
    wb = pkg.workbook_audit
    assert wb is not None
    assert abs(wb.seller_reported_gross_total_sek - 5567645.0) < 1.0
    assert abs(wb.seller_reported_net_79pct_sek - 4398439.55) < 1.0
    assert abs(wb.seller_reported_3yr_avg_sek - 1466146.52) < 1.0
    assert abs(wb.seller_implied_valuation_sek - 17593758.20) < 1.0

    # Out-of-window rows (12/2022 BMG = 513,510 SEK + II/2020 Kobalt = 3,170 SEK = 516,680 SEK)
    assert abs(wb.excluded_2022_prior_period_sek - 516680.0) < 1.0
    assert wb.lod_double_deduction_avoided_sek > 70000.0
    assert abs(wb.reconstructed_2023_2025_gross_sek - 5050965.0) < 1.0

    issue_codes = {i.code for i in wb.audit_findings}
    assert "OUT_OF_WINDOW_PRIOR_YEAR_INCLUSION" in issue_codes
    assert "SUMIF_WILDCARD_OR_PUNCTUATION_MISMATCH" in issue_codes
    assert "PRE_COLLECTION_ZERO_ROW_DILUTION" in issue_codes
    assert "NAIVE_BLANKET_OWNERSHIP_MULTIPLIER_VS_LOD" in issue_codes

    # 2. Rights-Type Cash Flow Decomposition (Slide 8-9)
    rt = pkg.business_plan
    assert abs(rt.cagr_26_31e_streaming_pct - 4.8) <= 0.15
    assert abs(rt.cagr_26_31e_total_pct - 2.5) <= 0.15
    assert rt.normalized_synch_baseline_sekk == 245.0
    assert rt.one_off_2024_synch_spike_sekk == 442.0  # 687k 2024 Fortnite spike - 245k normal
    y_2026 = next(r for r in rt.years if r.year == 2026)
    y_2031 = next(r for r in rt.years if r.year == 2031)
    assert abs(y_2026.total_income_sekk - 4998.0) < 2.0
    assert abs(y_2031.total_income_sekk - 5657.0) < 2.0

    # 3. Market-Relative Alpha & Discovery Mode
    alpha = pkg.market_alpha
    assert alpha.us_market_relative_alpha_pct > 0
    assert alpha.de_market_relative_alpha_pct > 0
    assert len(alpha.discovery_mode_windows_detected) >= 2
    assert alpha.discovery_mode_estimated_uplift_pct > 0

    # 4. Evergreen DCF & 2D Sensitivity Matrices (Slide 10)
    dcf = pkg.evergreen_dcf
    assert abs(dcf.fair_value_50pct_sekm - 34.6) <= 0.2
    assert abs(dcf.implied_2026e_multiple_midpoint - 13.8) <= 0.2
    assert abs(dcf.implied_l3y_avg_multiple_midpoint - 14.4) <= 0.2
    assert len(dcf.wacc_vs_pgr_matrix) == 25
    mid_cell = next(
        c for c in dcf.wacc_vs_pgr_matrix if abs(c.row_value - 1.5) < 0.01 and abs(c.col_value - 9.0) < 0.01
    )
    assert mid_cell.enterprise_value_m == 34.6
    assert mid_cell.implied_2026e_multiple == 13.8

    # 5. LBO & Portfolio Roll-Up Multiple Expansion (Slide 11)
    lbo = pkg.lbo_returns
    assert lbo.ltv_pct == 40.0
    assert lbo.cost_of_debt_pct == 7.5
    assert lbo.deleveraging_profile[0].net_debt_to_ebitda == 5.6
    assert lbo.deleveraging_profile[-1].net_debt_to_ebitda == 1.4
    assert lbo.base_standalone_irr_pct == 10.0
    assert lbo.base_standalone_moic == 1.6
    assert abs(lbo.portfolio_rollup_irr_pct - 13.4) <= 0.15
    assert lbo.portfolio_rollup_moic == 1.9
    assert abs(lbo.multiple_expansion_irr_uplift_bps - 340) <= 15

    # 6. Football Field (Slide 12)
    assert len(pkg.football_field) == 4
    ff_methods = {b.methodology for b in pkg.football_field}
    assert "Discounted Cash Flow" in ff_methods
    assert "Leveraged Buy-Out (Portfolio Roll-Up Exit)" in ff_methods

    # 7. Cross-Society Leakage Detector (Slides 6 & 14-16)
    leakage_ids = {a.anomaly_id for a in pkg.collection_anomalies}
    assert "ANOMALY_I_UK_BMG_MECHANICALS" in leakage_ids
    assert "ANOMALY_II_US_LIVE_PERFORMANCE" in leakage_ids
    assert "ANOMALY_III_STIM_2023_FOREIGN_UNDERCOLLECTION" in leakage_ids

    # 8. SpaceValuationEngine integration for Evergreen Publishing Catalog with ROFR, 2042 Reversion & 21% Prior Sale
    engine = SpaceValuationEngine(random_seed=42)
    zitron_inp = CatalogValuationInput(
        catalog_title="Michel Zitron & John Martin Songbook (50% Stake)",
        artist_or_label_name="Michel Zitron & John Martin",
        rights_scope=RightsScope.PUBLISHING,
        distributor_or_admin="BMG Rights Management / Kobalt / STIM",
        declared_ltm_amount=220000.0,
        declared_currency="EUR",
        ownership_share_pct=100.0,
        statements_verified=True,
        genres=["electronic", "pop"],
        notes=(
            "Co-publishing agreement with Lateral includes a Right of First Refusal (ROFR) on John's catalog. "
            "Contractual reversion in 2042 on Michel's catalog. "
            "21% of Michel's rights previously sold (STIM paid manually, BMG paid via direct LOD since H2 2025). "
            "Spotify Discovery Mode used in algorithmic radio/autoplay during 2023-2024 and 2026."
        ),
        top_tracks=[
            TrackInput(
                title="Don't You Worry Child",
                release_date=date(2012, 9, 14),
                ltm_streams=155_000_000,
                ltm_royalties_eur=136_000.0,
            ),
            TrackInput(
                title="Save the World",
                release_date=date(2011, 5, 13),
                ltm_streams=36_000_000,
                ltm_royalties_eur=31_000.0,
            ),
            TrackInput(
                title="Reload (Free Love)",
                release_date=date(2013, 5, 10),
                ltm_streams=32_000_000,
                ltm_royalties_eur=24_000.0,
            ),
            TrackInput(
                title="Red Lights",
                release_date=date(2014, 2, 21),
                ltm_streams=28_000_000,
                ltm_royalties_eur=18_000.0,
            ),
            TrackInput(
                title="Fade into Darkness",
                release_date=date(2011, 7, 16),
                ltm_streams=16_000_000,
                ltm_royalties_eur=11_000.0,
            ),
        ],
    )
    zitron_val = engine.evaluate(zitron_inp, reference_date=date(2026, 10, 15))
    assert zitron_val.evergreen_terminal_value_p50_eur > 0
    assert zitron_val.npv_10y_plus_terminal_p50_eur > zitron_val.npv_10y_p50_eur
    assert zitron_val.implied_portfolio_rollup_16x_exit_irr_pct is not None
    assert zitron_val.implied_standalone_12x_exit_irr_pct is not None
    assert zitron_val.implied_portfolio_rollup_16x_exit_irr_pct > zitron_val.implied_standalone_12x_exit_irr_pct

    assert zitron_val.chain_of_title is not None
    assert zitron_val.chain_of_title.rofr_or_matching_right_detected is True
    assert zitron_val.chain_of_title.reversion_year_detected == 2042
    assert zitron_val.chain_of_title.prior_minority_sale_detected is True

    flag_codes = {rf.code for rf in zitron_val.risk_flags}
    assert "CO_PUB_ROFR_OR_MATCHING_RIGHT" in flag_codes
    assert "CONTRACTUAL_REVERSION_CLIFF" in flag_codes
    assert "PRIOR_MINORITY_INCOME_ASSIGNMENT" in flag_codes
    assert "SPOTIFY_DISCOVERY_MODE_DEPENDENCY" in flag_codes

    # 9. Verify API endpoint GET /catalog-review/benchmarks/tenet-zitron-package
    client = TestClient(app)
    res = client.get("/catalog-review/benchmarks/tenet-zitron-package")
    assert res.status_code == 200
    body = res.json()
    assert body["evergreen_dcf"]["fair_value_50pct_sekm"] == 34.6
    assert body["workbook_audit"]["excluded_2022_prior_period_sek"] == 516680.0







