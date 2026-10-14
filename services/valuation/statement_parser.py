"""
SPACE Standalone Distributor Statement Parser & Benchmark Aggregator
(services/valuation/statement_parser.py)

100% standalone module within SpaceMusic (zero dependency on Qlero or external APIs).
Parses raw CSV/TSV royalty exports uploaded by catalog sellers from:
- DistroKid (TSV / CSV earnings exports)
- TuneCore (CSV sales reports)
- FUGA / The Orchard / Believe / Amuse / CD Baby / Generic ISRC CSV statements

Outputs:
1. Normalized track-level (`TrackInput`) and monthly (`MonthlyStatementPoint`) series
   ready for `SpaceValuationEngine.evaluate()`.
2. DSP share and country share distributions for forensics checks.
3. Anonymized empirical RPM (net USD/EUR per stream by DSP & country) and track survival
   entries for SPACE's proprietary internal benchmark database.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from .engine import (
    MonthlyStatementPoint,
    RULES_DEFAULT_PATH,
    TrackInput,
    compute_empirical_track_Slope,
    convert_to_eur,
    load_rules,
)


class NormalizedStatementRow(BaseModel):
    sale_month: str  # YYYY-MM
    isrc: str
    track_title: str
    artist_name: str
    dsp_store: str
    country_code: str
    streams: int
    net_royalty_eur: float
    original_currency: str = "USD"
    release_date: Optional[date] = None


class EmpiricalBenchmarkEntry(BaseModel):
    dsp_store: str
    country_code: str
    total_streams: int
    total_net_royalty_eur: float
    observed_rpm_eur: float
    observed_rpm_usd: float


class ParsedStatementSummary(BaseModel):
    detected_distributor: str
    row_count: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    months_covered: int = 0
    total_streams: int = 0
    total_net_royalty_eur: float = 0.0
    ltm_net_royalty_eur: float = 0.0
    ltm_streams: int = 0
    tracks: List[TrackInput] = Field(default_factory=list)
    monthly_history: List[MonthlyStatementPoint] = Field(default_factory=list)
    dsp_share: Dict[str, float] = Field(default_factory=dict)
    country_share: Dict[str, float] = Field(default_factory=dict)
    benchmarks: List[EmpiricalBenchmarkEntry] = Field(default_factory=list)


HEADER_ALIASES = {
    "sale_month": [
        "sale month",
        "sales period",
        "reporting month",
        "period",
        "activity period",
        "month",
        "date",
        "royalty period",
        "accounting period",
        "transaction month",
    ],
    "isrc": ["isrc", "isrc code", "track isrc", "recording isrc"],
    "track_title": ["title", "song title", "track title", "track", "release title", "asset title", "song"],
    "artist_name": ["artist", "artist name", "track artist", "primary artist", "display artist"],
    "dsp_store": ["store", "Music Store", "music store", "dsp", "service", "platform", "partner", "channel", "retailer"],
    "country_code": [
        "country of sale",
        "country",
        "territory",
        "country code",
        "sale country",
        "region",
    ],
    "streams": ["quantity", "units", "streams", "net quantity", "count", "plays", "units sold"],
    "earnings": [
        "earnings (usd)",
        "earnings",
        "net royalty",
        "net revenue",
        "total payable",
        "amount payable",
        "net amount",
        "royalty",
        "payable",
        "total earned",
        "usd_earnings",
    ],
    "currency": ["currency", "payable currency", "reporting currency", "sale currency"],
    "release_date": ["release date", "original release date", "street date"],
}


def _normalize_period(raw: str) -> Optional[str]:
    if not raw:
        return None
    s = raw.strip()
    # Match YYYY-MM or YYYY/MM
    m = re.match(r"^(\d{4})[-/](\d{1,2})", s)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    # Match YYYYMM
    m2 = re.match(r"^(\d{4})(\d{2})$", s)
    if m2:
        year, month = int(m2.group(1)), int(m2.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    # Match MM/DD/YYYY or DD/MM/YYYY
    m3 = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)
    if m3:
        p1, p2, year = int(m3.group(1)), int(m3.group(2)), int(m3.group(3))
        month = p1 if p1 <= 12 else p2
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    return None


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    s = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date()
        except ValueError:
            continue
    return None


def _normalize_dsp_name(raw: str) -> str:
    s = (raw or "unknown").strip().lower()
    if "spotify" in s:
        return "spotify"
    if "apple" in s or "itunes" in s:
        return "apple_music"
    if "youtube" in s or "google" in s:
        return "youtube"
    if "amazon" in s:
        return "amazon_music"
    if "deezer" in s:
        return "deezer"
    if "tidal" in s:
        return "tidal"
    if "tiktok" in s or "bytedance" in s or "resso" in s:
        return "tiktok"
    if "pandora" in s:
        return "pandora"
    if "soundcloud" in s:
        return "soundcloud"
    return s or "other"


def _parse_float(val: Any) -> float:
    if val is None:
        return 0.0
    s = str(val).strip().replace("$", "").replace("€", "").replace("£", "").replace(",", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_int(val: Any) -> int:
    return int(round(_parse_float(val)))


def _detect_column_mapping(headers: List[str]) -> Tuple[Dict[str, str], str]:
    norm_to_orig = {h.strip().lower(): h for h in headers if h}
    mapping: Dict[str, str] = {}

    for canonical, candidates in HEADER_ALIASES.items():
        for cand in candidates:
            if cand.lower() in norm_to_orig:
                mapping[canonical] = norm_to_orig[cand.lower()]
                break

    # Detect distributor signature from headers
    lower_headers = set(norm_to_orig.keys())
    if "earnings (usd)" in lower_headers and ("sale month" in lower_headers or "country of sale" in lower_headers):
        distributor = "DistroKid"
    elif "sales period" in lower_headers and "music store" in lower_headers:
        distributor = "TuneCore"
    elif "asset title" in lower_headers or "royalty period" in lower_headers:
        distributor = "FUGA / Enterprise"
    else:
        distributor = "Standard CSV"

    return mapping, distributor


def parse_statement_csv(
    content: str | bytes,
    default_currency: str = "USD",
    rules_path: Path = RULES_DEFAULT_PATH,
) -> ParsedStatementSummary:
    """
    Parses a raw distributor statement (CSV or TSV) and returns aggregated
    monthly series, track-level cohorts, DSP/country mix, and empirical RPM benchmarks.
    """
    rules = load_rules(rules_path)
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content.lstrip("\ufeff")

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ParsedStatementSummary(detected_distributor="Empty", row_count=0)

    # Detect delimiter (TSV vs CSV vs semicolon)
    first_line = lines[0]
    if "\t" in first_line:
        delimiter = "\t"
    elif first_line.count(";") > first_line.count(","):
        delimiter = ";"
    else:
        delimiter = ","

    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    headers = list(reader.fieldnames or [])
    col_map, detected_distributor = _detect_column_mapping(headers)

    rows: List[NormalizedStatementRow] = []
    for raw_row in reader:
        period_raw = raw_row.get(col_map.get("sale_month", ""), "")
        sale_month = _normalize_period(period_raw) or "2026-01"

        isrc = (raw_row.get(col_map.get("isrc", ""), "") or "").strip().upper()
        title = (raw_row.get(col_map.get("track_title", ""), "") or "Untitled Track").strip()
        if not isrc:
            # Generate deterministic pseudo-ISRC from track title if missing
            slug = re.sub(r"[^A-Z0-9]", "", title.upper())[:8] or "TRACK"
            isrc = f"SPACE{slug}"

        artist = (raw_row.get(col_map.get("artist_name", ""), "") or "Unknown Artist").strip()
        dsp = _normalize_dsp_name(raw_row.get(col_map.get("dsp_store", ""), "spotify"))
        country = (raw_row.get(col_map.get("country_code", ""), "US") or "US").strip().upper()[:2]
        streams = max(0, _parse_int(raw_row.get(col_map.get("streams", ""), 0)))

        raw_earnings = _parse_float(raw_row.get(col_map.get("earnings", ""), 0.0))
        row_currency = (
            raw_row.get(col_map.get("currency", ""), "") or default_currency
        ).strip().upper()
        if "earnings (usd)" in [h.strip().lower() for h in headers]:
            row_currency = "USD"

        net_eur = convert_to_eur(raw_earnings, row_currency, rules)
        rel_date = _parse_date(raw_row.get(col_map.get("release_date", ""), None))

        rows.append(
            NormalizedStatementRow(
                sale_month=sale_month,
                isrc=isrc,
                track_title=title,
                artist_name=artist,
                dsp_store=dsp,
                country_code=country,
                streams=streams,
                net_royalty_eur=net_eur,
                original_currency=row_currency,
                release_date=rel_date,
            )
        )

    if not rows:
        return ParsedStatementSummary(detected_distributor=detected_distributor, row_count=0)

    # Aggregate monthly totals
    monthly_rev: Dict[str, float] = defaultdict(float)
    monthly_streams: Dict[str, int] = defaultdict(int)
    for r in rows:
        monthly_rev[r.sale_month] += r.net_royalty_eur
        monthly_streams[r.sale_month] += r.streams

    sorted_months = sorted(monthly_rev.keys())
    period_start = sorted_months[0]
    period_end = sorted_months[-1]
    l12_months = set(sorted_months[-12:])

    monthly_history = [
        MonthlyStatementPoint(
            period=m,
            net_royalties_eur=round(monthly_rev[m], 4),
            streams=monthly_streams[m],
        )
        for m in sorted_months
    ]

    total_rev_eur = sum(monthly_rev.values())
    total_streams = sum(monthly_streams.values())

    raw_ltm_rev_eur = sum(monthly_rev[m] for m in l12_months)
    raw_ltm_streams = sum(monthly_streams[m] for m in l12_months)
    # Annualize if fewer than 12 months of statements were uploaded
    annualization_factor = 12.0 / max(1, len(l12_months))
    ltm_rev_eur = raw_ltm_rev_eur * annualization_factor
    ltm_streams = int(round(raw_ltm_streams * annualization_factor))

    # Aggregate per-track (ISRC) data
    track_meta: Dict[str, Dict[str, Any]] = {}
    track_month_rev: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    track_ltm_rev: Dict[str, float] = defaultdict(float)
    track_ltm_streams: Dict[str, int] = defaultdict(int)
    track_first_month: Dict[str, str] = {}

    for r in rows:
        if r.isrc not in track_meta:
            track_meta[r.isrc] = {
                "title": r.track_title,
                "release_date": r.release_date,
            }
        elif r.release_date and not track_meta[r.isrc]["release_date"]:
            track_meta[r.isrc]["release_date"] = r.release_date

        track_month_rev[r.isrc][r.sale_month] += r.net_royalty_eur
        if r.sale_month in l12_months:
            track_ltm_rev[r.isrc] += r.net_royalty_eur * annualization_factor
            track_ltm_streams[r.isrc] += int(round(r.streams * annualization_factor))

        if r.isrc not in track_first_month or r.sale_month < track_first_month[r.isrc]:
            track_first_month[r.isrc] = r.sale_month

    tracks_out: List[TrackInput] = []
    denom_ltm = max(1e-6, ltm_rev_eur)

    # Estimate track age from release_date or earliest statement month
    end_year, end_month = map(int, period_end.split("-"))
    for isrc, meta in track_meta.items():
        m_series = [track_month_rev[isrc].get(m, 0.0) for m in sorted_months]
        # Trim leading zeros before track was released
        first_nonzero_idx = next((i for i, v in enumerate(m_series) if v > 0), 0)
        active_series = m_series[first_nonzero_idx:]

        emp_decay = compute_empirical_track_Slope(active_series)

        rel_date = meta["release_date"]
        if rel_date is None and isrc in track_first_month:
            fm_y, fm_m = map(int, track_first_month[isrc].split("-"))
            obs_span_months = max(1, (end_year - fm_y) * 12 + (end_month - fm_m) + 1)
            age_months = float(obs_span_months)
        else:
            age_months = None

        t_rev = track_ltm_rev.get(isrc, 0.0)
        tracks_out.append(
            TrackInput(
                isrc=isrc,
                title=meta["title"],
                release_date=rel_date,
                age_months=age_months,
                annual_streams=track_ltm_streams.get(isrc, 0),
                ltm_royalties_eur=round(t_rev, 4),
                revenue_share=round(t_rev / denom_ltm, 6) if ltm_rev_eur > 0 else 0.0,
                monthly_royalties_eur=[round(v, 4) for v in active_series],
                empirical_annual_decay_rate=round(emp_decay, 4) if emp_decay is not None else None,
            )
        )

    tracks_out.sort(key=lambda t: t.ltm_royalties_eur or 0.0, reverse=True)

    # DSP & Country Share
    dsp_totals: Dict[str, float] = defaultdict(float)
    country_streams: Dict[str, int] = defaultdict(int)
    country_rev: Dict[str, float] = defaultdict(float)
    benchmark_buckets: Dict[Tuple[str, str], List[float]] = defaultdict(lambda: [0.0, 0.0])

    for r in rows:
        dsp_totals[r.dsp_store] += r.net_royalty_eur
        country_streams[r.country_code] += r.streams
        country_rev[r.country_code] += r.net_royalty_eur
        bucket = benchmark_buckets[(r.dsp_store, r.country_code)]
        bucket[0] += r.streams
        bucket[1] += r.net_royalty_eur

    dsp_share = {
        k: round(v / total_rev_eur, 4)
        for k, v in sorted(dsp_totals.items(), key=lambda kv: kv[1], reverse=True)
    } if total_rev_eur > 0 else {}

    if total_streams > 0:
        country_share = {
            k: round(v / total_streams, 4)
            for k, v in sorted(country_streams.items(), key=lambda kv: kv[1], reverse=True)
        }
    elif total_rev_eur > 0:
        country_share = {
            k: round(v / total_rev_eur, 4)
            for k, v in sorted(country_rev.items(), key=lambda kv: kv[1], reverse=True)
        }
    else:
        country_share = {}

    usd_fx = float(rules.get("FX_RATES_TO_EUR", {}).get("USD", 0.92))
    benchmarks: List[EmpiricalBenchmarkEntry] = []
    for (dsp, country), (b_streams, b_rev_eur) in sorted(
        benchmark_buckets.items(), key=lambda kv: kv[1][1], reverse=True
    ):
        if b_streams >= 100 and b_rev_eur > 0:
            rpm_eur = b_rev_eur / b_streams
            rpm_usd = (b_rev_eur / usd_fx) / b_streams
            benchmarks.append(
                EmpiricalBenchmarkEntry(
                    dsp_store=dsp,
                    country_code=country,
                    total_streams=int(b_streams),
                    total_net_royalty_eur=round(b_rev_eur, 4),
                    observed_rpm_eur=round(rpm_eur, 6),
                    observed_rpm_usd=round(rpm_usd, 6),
                )
            )

    return ParsedStatementSummary(
        detected_distributor=detected_distributor,
        row_count=len(rows),
        period_start=period_start,
        period_end=period_end,
        months_covered=len(sorted_months),
        total_streams=total_streams,
        total_net_royalty_eur=round(total_rev_eur, 2),
        ltm_net_royalty_eur=round(ltm_rev_eur, 2),
        ltm_streams=ltm_streams,
        tracks=tracks_out,
        monthly_history=monthly_history,
        dsp_share=dsp_share,
        country_share=country_share,
        benchmarks=benchmarks,
    )
