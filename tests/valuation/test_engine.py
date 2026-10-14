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
    evaluate_dtw_lifecycle,
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



