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
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from .engine import (
    RULES_DEFAULT_PATH,
    MonthlyStatementPoint,
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
        "sales date",
        "sale date",
        "sales period",
        "reporting month",
        "reporting period",
        "statement period",
        "period",
        "activity period",
        "month",
        "date",
        "royalty period",
        "accounting period",
        "transaction month",
        "usage period",
    ],
    "isrc": [
        "isrc",
        "isrc code",
        "track isrc",
        "recording isrc",
        "asset isrc",
        "code isrc",
        "contenu",
        "content",
        "video id",
    ],
    "track_title": [
        "title",
        "song title",
        "track title",
        "track name",
        "track",
        "release title",
        "release name",
        "asset title",
        "song",
        "recording title",
        "titre de la vidéo",
        "video title",
    ],
    "artist_name": [
        "artist",
        "artist name",
        "track artist",
        "track artists",
        "release artists",
        "primary artist",
        "display artist",
        "main artist",
        "channel name",
        "chaîne",
    ],
    "dsp_store": [
        "store",
        "store name",
        "Music Store",
        "music store",
        "dsp",
        "service",
        "platform",
        "partner",
        "channel",
        "retailer",
        "digital service provider",
        "source",
        "plateforme",
    ],
    "country_code": [
        "country of sale",
        "country",
        "territory",
        "country code",
        "sale country",
        "region",
        "territory code",
    ],
    "streams": [
        "quantity",
        "qty",
        "units",
        "streams",
        "net quantity",
        "count",
        "plays",
        "units sold",
        "total streams",
        "vues engagées",
        "engaged views",
        "vues",
        "views",
    ],
    "earnings": [
        "recipient net royalty ($ usd)",
        "recipient net royalty",
        "net royalty ($ usd)",
        "net royalty (usd)",
        "net royalty (eur)",
        "earnings (usd)",
        "royalty ($us)",
        "royalty (usd)",
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
        "artist net",
        "your revenue",
        "net payout",
        "net share",
        "gross royalty ($ usd)",
        "revenus estimés (mad)",
        "revenus estimés (eur)",
        "revenus estimés (usd)",
        "revenus estimés",
        "estimated revenue (usd)",
        "estimated revenue (eur)",
        "estimated revenue",
    ],
    "currency": [
        "currency",
        "payable currency",
        "reporting currency",
        "sale currency",
        "statement currency",
    ],
    "release_date": [
        "release date",
        "original release date",
        "street date",
        "first release date",
        "heure de publication de la vidéo",
        "video publish time",
    ],
}

MONTH_NAME_MAP = {
    "jan": 1,
    "january": 1,
    "janvier": 1,
    "feb": 2,
    "february": 2,
    "février": 2,
    "fevrier": 2,
    "mar": 3,
    "march": 3,
    "mars": 3,
    "apr": 4,
    "april": 4,
    "avril": 4,
    "may": 5,
    "mai": 5,
    "jun": 6,
    "june": 6,
    "juin": 6,
    "jul": 7,
    "july": 7,
    "juillet": 7,
    "aug": 8,
    "august": 8,
    "août": 8,
    "aout": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "septembre": 9,
    "oct": 10,
    "october": 10,
    "octobre": 10,
    "nov": 11,
    "november": 11,
    "novembre": 11,
    "dec": 12,
    "december": 12,
    "décembre": 12,
    "decembre": 12,
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
    # Match MON-YY or MONTH YYYY (e.g. "MAR-26", "March 2026", "Oct-2025")
    m4 = re.match(r"^([A-Za-zÀ-ÿ]+)[\s\-_/]+(\d{2,4})$", s)
    if m4:
        m_name = m4.group(1).strip().lower()
        yr_raw = int(m4.group(2))
        year = (2000 + yr_raw) if yr_raw < 100 else yr_raw
        month = MONTH_NAME_MAP.get(m_name) or MONTH_NAME_MAP.get(m_name[:3])
        if month and 1990 <= year <= 2100:
            return f"{year:04d}-{month:02d}"
    return None


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    s = raw.strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    ):
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
    if "tiktok" in s or "bytedance" in s or "resso" in s or "capcut" in s:
        return "tiktok"
    if any(k in s for k in ("facebook", "instagram", "meta", "threads", "snapchat")):
        return "meta_social"
    if "pandora" in s:
        return "pandora"
    if "soundcloud" in s:
        return "soundcloud"
    if "yandex" in s:
        return "yandex"
    return s or "other"


COUNTRY_NAME_TO_ISO2: Dict[str, str] = {
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "united kingdom": "GB",
    "great britain": "GB",
    "uk": "GB",
    "england": "GB",
    "germany": "DE",
    "france": "FR",
    "canada": "CA",
    "australia": "AU",
    "italy": "IT",
    "poland": "PL",
    "netherlands": "NL",
    "the netherlands": "NL",
    "switzerland": "CH",
    "austria": "AT",
    "brazil": "BR",
    "finland": "FI",
    "sweden": "SE",
    "norway": "NO",
    "czech republic": "CZ",
    "czechia": "CZ",
    "russia": "RU",
    "russian federation": "RU",
    "denmark": "DK",
    "romania": "RO",
    "belgium": "BE",
    "spain": "ES",
    "ukraine": "UA",
    "hungary": "HU",
    "mexico": "MX",
    "slovakia": "SK",
    "greece": "GR",
    "turkey": "TR",
    "türkiye": "TR",
    "india": "IN",
    "israel": "IL",
    "saudi arabia": "SA",
    "bulgaria": "BG",
    "portugal": "PT",
    "united arab emirates": "AE",
    "uae": "AE",
    "new zealand": "NZ",
    "ireland": "IE",
    "japan": "JP",
    "south korea": "KR",
    "korea, republic of": "KR",
    "republic of korea": "KR",
    "china": "CN",
    "taiwan": "TW",
    "hong kong": "HK",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "vietnam": "VN",
    "viet nam": "VN",
    "indonesia": "ID",
    "philippines": "PH",
    "pakistan": "PK",
    "bangladesh": "BD",
    "egypt": "EG",
    "south africa": "ZA",
    "nigeria": "NG",
    "morocco": "MA",
    "algeria": "DZ",
    "tunisia": "TN",
    "argentina": "AR",
    "chile": "CL",
    "colombia": "CO",
    "peru": "PE",
    "croatia": "HR",
    "serbia": "RS",
    "slovenia": "SI",
    "lithuania": "LT",
    "latvia": "LV",
    "estonia": "EE",
    "luxembourg": "LU",
    "iceland": "IS",
    "cyprus": "CY",
    "malta": "MT",
    "kazakhstan": "KZ",
    "belarus": "BY",
    "trinidad and tobago": "TT",
    "guinea": "GN",
    "oman": "OM",
}


def _normalize_country_code(raw: Optional[str]) -> str:
    if not raw:
        return "US"
    s = raw.strip()
    if not s:
        return "US"
    if len(s) == 2 and s.isalpha():
        up = s.upper()
        return "GB" if up == "UK" else up
    lower = s.lower()
    if lower in COUNTRY_NAME_TO_ISO2:
        return COUNTRY_NAME_TO_ISO2[lower]
    return s.upper()[:2]


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
    elif "artist net" in lower_headers or ("reporting period" in lower_headers and "track isrc" in lower_headers):
        distributor = "UnitedMasters"
    elif "your revenue" in lower_headers or ("statement period" in lower_headers and "digital service provider" in lower_headers):
        distributor = "Too Lost"
    elif (
        "net share" in lower_headers
        or "royalty ($us)" in lower_headers
        or "sale or void" in lower_headers
        or ("usage period" in lower_headers and "partner" in lower_headers)
        or ("reporting period" in lower_headers and "activity period" in lower_headers and "digital service provider" in lower_headers)
    ):
        distributor = "Symphonic"
    elif (
        "titre de la vidéo" in lower_headers
        or "video title" in lower_headers
        or "vues engagées" in lower_headers
        or "engaged views" in lower_headers
    ):
        distributor = "YouTube Studio"
    elif "sales date" in lower_headers and "pro rata share" in lower_headers and "label name" in lower_headers:
        distributor = "Tribal Trap / LabelWorx"
    elif "recipient net royalty ($ usd)" in lower_headers or (
        "recipient share (%)" in lower_headers and "royalty per unit ($ usd)" in lower_headers
    ):
        distributor = "Trap Nation / Label Engine"
    elif "asset title" in lower_headers or "royalty period" in lower_headers:
        distributor = "FUGA / Enterprise"
    else:
        distributor = "Standard CSV"

    return mapping, distributor


def _infer_header_currency(earnings_header: str, headers: List[str], fallback: str) -> str:
    eh = (earnings_header or "").strip().upper()
    m = re.search(r"\(([A-Z$€£]{2,4})\)", eh)
    if m:
        tok = m.group(1)
        if tok in ("$US", "USD", "US$"):
            return "USD"
        if tok in ("EUR", "€"):
            return "EUR"
        if tok in ("GBP", "£"):
            return "GBP"
        return tok
    lower_headers = [h.strip().lower() for h in headers]
    if "earnings (usd)" in lower_headers or "royalty ($us)" in lower_headers:
        return "USD"
    return fallback



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
    inferred_hdr_currency = _infer_header_currency(
        col_map.get("earnings", ""), headers, default_currency
    )

    rows: List[NormalizedStatementRow] = []
    for raw_row in reader:
        period_raw = raw_row.get(col_map.get("sale_month", ""), "")
        sale_month = _normalize_period(period_raw)
        if not sale_month and "Activity Period" in raw_row:
            sale_month = _normalize_period(raw_row.get("Activity Period", ""))
        sale_month = sale_month or "2026-01"

        isrc = (raw_row.get(col_map.get("isrc", ""), "") or "").strip().upper()
        title = (
            raw_row.get(col_map.get("track_title", ""), "")
            or raw_row.get("Release Name", "")
            or raw_row.get("Product Name", "")
            or "Untitled Track"
        ).strip()
        if isrc.lower() in ("total", "totals", "grand total") or title.lower() in ("total", "totals"):
            continue
        if not isrc:
            # Generate deterministic pseudo-ISRC from track title if missing
            slug = re.sub(r"[^A-Z0-9]", "", title.upper())[:8] or "TRACK"
            isrc = f"SPACE{slug}"

        artist = (raw_row.get(col_map.get("artist_name", ""), "") or "Unknown Artist").strip()
        default_dsp = "youtube" if detected_distributor == "YouTube Studio" else "spotify"
        dsp = _normalize_dsp_name(raw_row.get(col_map.get("dsp_store", ""), default_dsp))
        country = _normalize_country_code(raw_row.get(col_map.get("country_code", ""), "US"))
        streams = max(0, _parse_int(raw_row.get(col_map.get("streams", ""), 0)))

        raw_earnings = _parse_float(raw_row.get(col_map.get("earnings", ""), 0.0))
        # Exclude sub-$0.0001/unit social UGC micro-impressions (Facebook/Instagram/TikTok/Threads/Snapchat)
        # from audio DSP stream totals so 100M+ $0.000003 social video views do not distort audio RPM or geo stream share,
        # while retaining 100% of their royalty revenue.
        if dsp in ("tiktok", "meta_social") and streams > 0 and (raw_earnings / streams) < 0.0001:
            streams = 0
        row_currency = (
            raw_row.get(col_map.get("currency", ""), "") or inferred_hdr_currency
        ).strip().upper()

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

    return _summarize_normalized_rows(rows, detected_distributor, rules)


def _col_letters_to_index(cell_ref: str) -> int:
    m = re.match(r"^([A-Za-z]+)", cell_ref or "")
    if not m:
        return 0
    idx = 0
    for ch in m.group(1).upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return max(0, idx - 1)


def read_xlsx_worksheets(raw_bytes: bytes) -> List[Tuple[str, List[List[str]]]]:
    """
    Zero-dependency OpenXML `.xlsx` reader using Python's standard library (`zipfile` + `xml.etree`).
    Returns a list of `(sheet_name, rows_matrix)` tuples across all worksheets in the workbook.
    """
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    sheets_out: List[Tuple[str, List[List[str]]]] = []
    with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zf:
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.findall(f".//{ns}si"):
                texts = [t.text or "" for t in si.findall(f".//{ns}t")]
                shared_strings.append("".join(texts))

        sheet_files = sorted(
            name
            for name in zf.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        for s_name in sheet_files:
            s_root = ET.fromstring(zf.read(s_name))
            matrix: List[List[str]] = []
            for row_el in s_root.findall(f".//{ns}row"):
                cells = row_el.findall(f"{ns}c")
                if not cells:
                    continue
                row_vals: List[str] = []
                for pos, c_el in enumerate(cells):
                    ref = c_el.attrib.get("r", "")
                    col_idx = _col_letters_to_index(ref) if ref else pos
                    while len(row_vals) < col_idx:
                        row_vals.append("")
                    c_type = c_el.attrib.get("t", "")
                    v_el = c_el.find(f"{ns}v")
                    is_el = c_el.find(f"{ns}is")
                    val_str = ""
                    if v_el is not None and v_el.text is not None:
                        if c_type == "s":
                            s_idx = int(v_el.text)
                            val_str = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else ""
                        else:
                            val_str = v_el.text
                    elif is_el is not None:
                        val_str = "".join(t.text or "" for t in is_el.findall(f".//{ns}t"))
                    row_vals.append(val_str.strip())
                if any(v for v in row_vals):
                    matrix.append(row_vals)
            if matrix:
                sheets_out.append((s_name, matrix))
    return sheets_out


def convert_xlsx_to_csv_text(
    raw_bytes: bytes,
    *,
    filename: str = "statement.xlsx",
    reference_end_month: str = "2026-09",
) -> str:
    """
    Converts a distributor or YouTube Studio `.xlsx` workbook into a normalized CSV text
    suitable for `parse_statement_csv()`.

    Supports:
    1. Standard single-sheet or multi-sheet distributor `.xlsx` files (TuneCore, Symphonic, Believe, FUGA).
    2. Multi-sheet YouTube Studio Analytics exports (`Table data` / `Données du tableau` in Sheet 1
       with per-video revenues + `Totals` / `Totaux` in Sheet 3 with monthly engaged views),
       proportionally allocating LTM or lifetime YouTube video revenue across active months so both
       track-level HHI/decay and monthly time-series DTW trajectories are preserved.
    """
    sheets = read_xlsx_worksheets(raw_bytes)
    if not sheets:
        return ""

    sheet1_headers = [h.strip() for h in sheets[0][1][0]]
    lower_s1 = {h.lower() for h in sheet1_headers if h}
    is_youtube_studio = any(
        k in lower_s1
        for k in ("titre de la vidéo", "video title", "vues engagées", "engaged views")
    )

    if is_youtube_studio:
        # Parse Sheet 1 per-video totals and revenue
        s1_rows = sheets[0][1]
        col_map_s1, _ = _detect_column_mapping(sheet1_headers)
        hdr_idx = {h: i for i, h in enumerate(sheet1_headers)}

        def _get_cell(r_list: List[str], canonical: str, default: str = "") -> str:
            col_name = col_map_s1.get(canonical, "")
            idx = hdr_idx.get(col_name, -1)
            return r_list[idx] if 0 <= idx < len(r_list) else default

        earnings_col_name = col_map_s1.get("earnings", "Revenus estimés (MAD)")
        yt_currency = _infer_header_currency(earnings_col_name, sheet1_headers, "MAD")

        video_records: List[Dict[str, Any]] = []
        total_video_rev = 0.0
        total_video_views = 0

        for r in s1_rows[1:]:
            vid_id = _get_cell(r, "isrc", "").strip()
            vid_title = _get_cell(r, "track_title", "").strip()
            if not vid_id or vid_id.lower() in ("total", "totaux", "totals"):
                continue
            views = max(0, _parse_int(_get_cell(r, "streams", "0")))
            rev = max(0.0, _parse_float(_get_cell(r, "earnings", "0")))
            pub_date = _parse_date(_get_cell(r, "release_date", ""))
            # Extract artist from "Artist - Track" if present
            if " - " in vid_title:
                artist_part = vid_title.split(" - ", 1)[0].strip()
            elif " | " in vid_title:
                artist_part = vid_title.split(" | ", 1)[0].strip()
            else:
                artist_part = "YouTube Channel"
            video_records.append(
                {
                    "id": f"YT{re.sub(r'[^A-Za-z0-9]', '', vid_id)[:10].upper()}",
                    "title": vid_title or vid_id,
                    "artist": artist_part,
                    "views": views,
                    "rev": rev,
                    "release_date": pub_date.isoformat() if pub_date else "",
                }
            )
            total_video_rev += rev
            total_video_views += views

        # Check Sheet 3 for monthly engaged-view series (`Date`, `Vues engagées` / `Engaged views`)
        monthly_views_series: List[Tuple[str, int]] = []
        if len(sheets) >= 3:
            s3_rows = sheets[2][1]
            for r in s3_rows[1:]:
                if len(r) >= 2:
                    m_norm = _normalize_period(r[0])
                    v_cnt = max(0, _parse_int(r[1]))
                    if m_norm and v_cnt > 0 and m_norm <= reference_end_month:
                        monthly_views_series.append((m_norm, v_cnt))

        # Keep trailing 36 months (or 12 months for a Last-365 export) to avoid double-counting or partial current month
        is_last_365 = "365" in filename.lower() or len(monthly_views_series) <= 14
        if is_last_365 and len(monthly_views_series) > 12:
            monthly_views_series = monthly_views_series[-12:]
        elif len(monthly_views_series) > 36:
            monthly_views_series = monthly_views_series[-36:]

        out_buf = io.StringIO()
        writer = csv.writer(out_buf)
        writer.writerow(
            [
                "Sale Month",
                "ISRC",
                "Video Title",
                "Artist Name",
                "DSP",
                "Country",
                "Engaged Views",
                "Earnings",
                "Currency",
                "Release Date",
            ]
        )

        if monthly_views_series and video_records:
            total_series_views = max(1, sum(v for _, v in monthly_views_series))
            # Scale revenue to the selected window if lifetime workbook was sliced to 36m
            window_view_ratio = (
                1.0
                if is_last_365
                else min(1.0, total_series_views / max(1, total_video_views))
            )
            top_videos = video_records[:40]
            top_rev_sum = max(1e-6, sum(v["rev"] for v in top_videos))
            top_view_sum = max(1, sum(v["views"] for v in top_videos))

            for m_str, m_views in monthly_views_series:
                m_share = m_views / total_series_views
                for v in top_videos:
                    v_rev_share = (
                        (v["rev"] / top_rev_sum)
                        if total_video_rev > 0
                        else (v["views"] / top_view_sum)
                    )
                    v_view_share = v["views"] / top_view_sum
                    alloc_rev = total_video_rev * window_view_ratio * m_share * v_rev_share
                    alloc_views = int(round(m_views * v_view_share))
                    if alloc_rev > 0 or alloc_views > 0:
                        writer.writerow(
                            [
                                m_str,
                                v["id"],
                                v["title"],
                                v["artist"],
                                "YouTube",
                                "MA",
                                alloc_views,
                                f"{alloc_rev:.4f}",
                                yt_currency,
                                v["release_date"],
                            ]
                        )
            return out_buf.getvalue()

    # Default single-sheet / generic Excel conversion
    out_buf = io.StringIO()
    writer = csv.writer(out_buf)
    for r in sheets[0][1]:
        writer.writerow(r)
    return out_buf.getvalue()


def _summarize_normalized_rows(
    rows: List[NormalizedStatementRow],
    detected_distributor: str,
    rules: Dict[str, Any],
) -> ParsedStatementSummary:

    if not rows:
        return ParsedStatementSummary(detected_distributor=detected_distributor, row_count=0)

    # Reconcile rows missing an ISRC (`SPACE...`) when another row has the exact same track title and a real ISRC
    title_to_real_isrc: Dict[str, str] = {}
    for r in rows:
        if not r.isrc.startswith("SPACE") and r.track_title and r.track_title != "Untitled Track":
            norm_t = r.track_title.strip().lower()
            if norm_t not in title_to_real_isrc:
                title_to_real_isrc[norm_t] = r.isrc
    for r in rows:
        if r.isrc.startswith("SPACE") and r.track_title:
            matched_isrc = title_to_real_isrc.get(r.track_title.strip().lower())
            if matched_isrc:
                r.isrc = matched_isrc

    # Aggregate monthly totals
    monthly_rev: Dict[str, float] = defaultdict(float)
    monthly_streams: Dict[str, int] = defaultdict(int)
    month_dsp_rev: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    dsp_totals_all: Dict[str, float] = defaultdict(float)
    for r in rows:
        monthly_rev[r.sale_month] += r.net_royalty_eur
        monthly_streams[r.sale_month] += r.streams
        month_dsp_rev[r.sale_month][r.dsp_store] += r.net_royalty_eur
        dsp_totals_all[r.dsp_store] += r.net_royalty_eur

    total_rev_eur = sum(monthly_rev.values())
    total_streams = sum(monthly_streams.values())

    all_sorted_months = sorted(monthly_rev.keys())
    complete_months = list(all_sorted_months)

    # When multi-quarter Sales-Date exports span >12 months, trim partial accounting-lag
    # boundary months at the tail (where the dominant DSP has not yet reported for the latest
    # usage month) and prior-period catch-up remnants at the head, while always keeping >=12 months.
    top4_rev_share = (
        sum(sorted(monthly_rev.values(), reverse=True)[:4]) / total_rev_eur
        if total_rev_eur > 0
        else 1.0
    )
    if len(complete_months) > 12 and total_rev_eur > 0 and top4_rev_share < 0.55:
        top_dsp, top_dsp_rev = max(dsp_totals_all.items(), key=lambda kv: kv[1])
        top_dsp_share = top_dsp_rev / total_rev_eur
        active_top_dsp_vals = sorted(
            month_dsp_rev[m][top_dsp] for m in complete_months if month_dsp_rev[m][top_dsp] > 0
        )
        median_top_dsp = (
            active_top_dsp_vals[len(active_top_dsp_vals) // 2] if active_top_dsp_vals else 0.0
        )

        # 1. Trim up to 2 trailing incomplete DSP-lag months
        for _ in range(2):
            if len(complete_months) <= 12:
                break
            last_m = complete_months[-1]
            prev_6 = [monthly_rev[m] for m in complete_months[-7:-1]]
            prev_6_sorted = sorted(prev_6)
            med_prev_6 = prev_6_sorted[len(prev_6_sorted) // 2] if prev_6_sorted else 0.0
            missing_primary_dsp = (
                top_dsp_share >= 0.30
                and median_top_dsp > 0
                and month_dsp_rev[last_m][top_dsp] < 0.15 * median_top_dsp
            )
            severe_lag_drop = med_prev_6 > 0 and monthly_rev[last_m] < 0.45 * med_prev_6
            if missing_primary_dsp or severe_lag_drop:
                complete_months.pop()
            else:
                break

        # 2. Trim leading prior-period catch-up / partial ramp-up months
        max_m_rev = max((monthly_rev[m] for m in complete_months), default=0.0)
        core_revs = sorted(monthly_rev[m] for m in complete_months if monthly_rev[m] >= 0.20 * max_m_rev)
        p75_rev = core_revs[int(0.75 * (len(core_revs) - 1))] if core_revs else 0.0
        while len(complete_months) > 12:
            first_m = complete_months[0]
            threshold = 0.65 * p75_rev if len(complete_months) > 18 else 0.18 * p75_rev
            if monthly_rev[first_m] < threshold:
                complete_months.pop(0)
            else:
                break

    sorted_months = complete_months
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
        if rel_date is None:
            m_isrc = re.match(r"^[A-Z]{2}[A-Z0-9]{3}(\d{2})\d{5}$", isrc)
            if m_isrc and not isrc.startswith(("SPACE", "YT")):
                yy = int(m_isrc.group(1))
                isrc_year = (2000 + yy) if yy <= 35 else (1900 + yy)
                if 1960 <= isrc_year <= end_year:
                    if isrc in track_first_month:
                        fm_y, fm_m = map(int, track_first_month[isrc].split("-"))
                        if isrc_year == fm_y and fm_m < 6:
                            rel_date = date(isrc_year, fm_m, 1)
                        elif isrc_year <= fm_y:
                            rel_date = date(isrc_year, 6, 15)
                    else:
                        rel_date = date(isrc_year, 6, 15)

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


def merge_statement_summaries(
    summaries: Sequence[ParsedStatementSummary],
) -> ParsedStatementSummary:
    """
    Merges multiple `ParsedStatementSummary` objects (for example, a Symphonic master/Content-ID
    CSV statement + a direct YouTube Studio Analytics `.xlsx` statement) into a single unified
    `ParsedStatementSummary` while reconciling overlapping vs. non-overlapping time windows.
    """
    valid = [s for s in summaries if s.row_count > 0]
    if not valid:
        return ParsedStatementSummary(detected_distributor="Empty", row_count=0)
    if len(valid) == 1:
        return valid[0]

    # Deduplicate if both a "Last 365" and "Lifetime" YouTube Studio workbook were uploaded
    yt_summaries = [s for s in valid if s.detected_distributor == "YouTube Studio"]
    other_summaries = [s for s in valid if s.detected_distributor != "YouTube Studio"]
    if len(yt_summaries) > 1:
        # Prefer the 12-month Last 365 workbook for LTM accuracy, but take monthly history from the longest one
        yt_sorted_by_len = sorted(yt_summaries, key=lambda s: s.months_covered)
        ltm_yt = yt_sorted_by_len[0]
        long_yt = yt_sorted_by_len[-1]
        # Scale the long_yt monthly history so its trailing 12 months match ltm_yt's exact LTM revenue
        long_l12 = sum(p.net_royalties_eur for p in long_yt.monthly_history[-12:])
        scale = (ltm_yt.ltm_net_royalty_eur / long_l12) if long_l12 > 0 else 1.0
        scaled_history = [
            MonthlyStatementPoint(
                period=p.period,
                net_royalties_eur=round(p.net_royalties_eur * scale, 4),
                streams=p.streams,
            )
            for p in long_yt.monthly_history
        ]
        merged_yt = ParsedStatementSummary(
            detected_distributor="YouTube Studio",
            row_count=ltm_yt.row_count + long_yt.row_count,
            period_start=long_yt.period_start,
            period_end=long_yt.period_end,
            months_covered=len(scaled_history),
            total_streams=long_yt.total_streams,
            total_net_royalty_eur=round(sum(p.net_royalties_eur for p in scaled_history), 2),
            ltm_net_royalty_eur=ltm_yt.ltm_net_royalty_eur,
            ltm_streams=ltm_yt.ltm_streams,
            tracks=ltm_yt.tracks,
            monthly_history=scaled_history,
            dsp_share=ltm_yt.dsp_share,
            country_share=ltm_yt.country_share,
            benchmarks=ltm_yt.benchmarks,
        )
        valid = other_summaries + [merged_yt]
        if len(valid) == 1:
            return valid[0]

    # First consolidate multiple files belonging to the same distributor (e.g. 160 monthly/quarterly
    # Tribal Trap TSVs + 10 quarterly Trap Nation CSVs) so single-month files are not 12x-annualized
    # before being summed across a multi-distributor catalog.
    by_distributor: Dict[str, List[ParsedStatementSummary]] = defaultdict(list)
    for s in valid:
        by_distributor[s.detected_distributor].append(s)

    if any(len(grp) > 1 for grp in by_distributor.values()) and len(by_distributor) > 1:
        consolidated_valid: List[ParsedStatementSummary] = []
        for dist_name, grp in by_distributor.items():
            if len(grp) == 1:
                consolidated_valid.append(grp[0])
            else:
                consolidated_valid.append(merge_statement_summaries(grp))
        valid = consolidated_valid
        if len(valid) == 1:
            return valid[0]

    dist_names: List[str] = []
    for s in valid:
        if s.detected_distributor not in dist_names:
            dist_names.append(s.detected_distributor)
    combined_distributor = " + ".join(dist_names)

    # Combine LTM royalties and streams additively across distinct royalty sources
    # (or average if identical distributor months were split across files)
    same_distributor = len(set(s.detected_distributor for s in valid)) == 1
    monthly_rev: Dict[str, float] = defaultdict(float)
    monthly_streams: Dict[str, int] = defaultdict(int)
    for s in valid:
        for pt in s.monthly_history:
            monthly_rev[pt.period] += pt.net_royalties_eur
            monthly_streams[pt.period] += pt.streams or 0

    sorted_months = sorted(monthly_rev.keys())
    if same_distributor and len(sorted_months) > 12:
        for _ in range(2):
            if len(sorted_months) <= 12:
                break
            last_m = sorted_months[-1]
            prev_6 = sorted(monthly_rev[m] for m in sorted_months[-7:-1])
            med_prev_6 = prev_6[len(prev_6) // 2] if prev_6 else 0.0
            if med_prev_6 > 0 and monthly_rev[last_m] < 0.45 * med_prev_6:
                sorted_months.pop()
            else:
                break
        max_m_rev = max((monthly_rev[m] for m in sorted_months), default=0.0)
        core_revs = sorted(monthly_rev[m] for m in sorted_months if monthly_rev[m] >= 0.20 * max_m_rev)
        p75_rev = core_revs[int(0.75 * (len(core_revs) - 1))] if core_revs else 0.0
        while len(sorted_months) > 12:
            first_m = sorted_months[0]
            threshold = 0.65 * p75_rev if len(sorted_months) > 18 else 0.18 * p75_rev
            if monthly_rev[first_m] < threshold:
                sorted_months.pop(0)
            else:
                break

    monthly_history = [
        MonthlyStatementPoint(
            period=m,
            net_royalties_eur=round(monthly_rev[m], 4),
            streams=monthly_streams[m],
        )
        for m in sorted_months
    ]

    if same_distributor:
        l12 = sorted_months[-12:]
        ann = 12.0 / max(1, len(l12))
        combined_ltm_eur = round(sum(monthly_rev[m] for m in l12) * ann, 2)
        combined_ltm_streams = int(round(sum(monthly_streams[m] for m in l12) * ann))
    else:
        combined_ltm_eur = round(sum(s.ltm_net_royalty_eur for s in valid), 2)
        combined_ltm_streams = sum(s.ltm_streams for s in valid)
        # If all major distributor summaries have >=12 complete months and share >=12 overlapping
        # months, restrict monthly_history to their common overlapping window so earlier single-label
        # months do not create artificial step-jumps when the larger label's export begins.
        major_month_sets = [
            {pt.period for pt in s.monthly_history}
            for s in valid
            if len(s.monthly_history) >= 12 and s.ltm_net_royalty_eur >= 0.05 * combined_ltm_eur
        ]
        if len(major_month_sets) >= 2:
            common_months = sorted(set.intersection(*major_month_sets))
            if len(common_months) >= 12:
                sorted_months = common_months
                monthly_history = [
                    MonthlyStatementPoint(
                        period=m,
                        net_royalties_eur=round(monthly_rev[m], 4),
                        streams=monthly_streams[m],
                    )
                    for m in sorted_months
                ]
                l12 = sorted_months[-12:]
                combined_ltm_eur = round(sum(monthly_rev[m] for m in l12), 2)
                combined_ltm_streams = int(round(sum(monthly_streams[m] for m in l12)))
        # Ensure trailing 12 months of monthly_history reflect the combined LTM run-rate
        # when one source only uploaded a partial 1-quarter sample (e.g. Symphonic MAR-26)
        raw_l12_sum = sum(monthly_rev[m] for m in sorted_months[-12:])
        if 0 < raw_l12_sum < combined_ltm_eur * 0.85:
            missing_annual_eur = combined_ltm_eur - raw_l12_sum
            monthly_topup = missing_annual_eur / max(1, len(sorted_months[-12:]))
            l12_set = set(sorted_months[-12:])
            monthly_history = [
                MonthlyStatementPoint(
                    period=pt.period,
                    net_royalties_eur=round(
                        pt.net_royalties_eur + (monthly_topup if pt.period in l12_set else 0.0),
                        4,
                    ),
                    streams=pt.streams,
                )
                for pt in monthly_history
            ]

    # Combine tracks by ISRC (and reconcile synthetic SPACE... ISRCs by normalized title)
    track_map: Dict[str, TrackInput] = {}
    for s in valid:
        # If merging multiple files from the same distributor, un-annualize per-file track LTM first
        rev_scale = (
            (s.total_net_royalty_eur / s.ltm_net_royalty_eur)
            if (same_distributor and len(valid) > 1 and s.ltm_net_royalty_eur > 0 and s.total_net_royalty_eur > 0)
            else 1.0
        )
        stream_scale = (
            (s.total_streams / s.ltm_streams)
            if (same_distributor and len(valid) > 1 and s.ltm_streams > 0 and s.total_streams > 0)
            else 1.0
        )
        for t in s.tracks:
            t_eur = round((t.ltm_royalties_eur or 0.0) * rev_scale, 4)
            t_streams = int(round((t.annual_streams or 0) * stream_scale))
            if t.isrc not in track_map:
                copied = t.model_copy(deep=True) if hasattr(t, "model_copy") else t.copy(deep=True)
                copied.ltm_royalties_eur = t_eur
                copied.annual_streams = t_streams
                if same_distributor and len(valid) > 1:
                    copied.monthly_royalties_eur = []
                    copied.empirical_annual_decay_rate = None
                track_map[t.isrc] = copied
            else:
                existing = track_map[t.isrc]
                if existing.release_date is None and t.release_date is not None:
                    existing.release_date = t.release_date
                existing.ltm_royalties_eur = round(
                    (existing.ltm_royalties_eur or 0.0) + t_eur, 4
                )
                existing.annual_streams = (existing.annual_streams or 0) + t_streams
                if same_distributor and len(valid) > 1:
                    existing.monthly_royalties_eur = []
                    existing.empirical_annual_decay_rate = None

    # Reconcile any synthetic SPACE... ISRC with a real ISRC that has the same track title
    title_to_real_isrc: Dict[str, str] = {}
    for isrc_key, trk in track_map.items():
        if isrc_key and not isrc_key.startswith("SPACE") and trk.title:
            norm_t = re.sub(r"\s+", " ", trk.title.strip().lower())
            if norm_t not in title_to_real_isrc:
                title_to_real_isrc[norm_t] = isrc_key

    for isrc_key in list(track_map.keys()):
        if isrc_key and isrc_key.startswith("SPACE"):
            trk = track_map[isrc_key]
            norm_t = re.sub(r"\s+", " ", (trk.title or "").strip().lower())
            real_key = title_to_real_isrc.get(norm_t)
            if real_key and real_key in track_map and real_key != isrc_key:
                target = track_map[real_key]
                target.ltm_royalties_eur = round((target.ltm_royalties_eur or 0.0) + (trk.ltm_royalties_eur or 0.0), 4)
                target.annual_streams = (target.annual_streams or 0) + (trk.annual_streams or 0)
                if trk.monthly_royalties_eur:
                    target.monthly_royalties_eur = (target.monthly_royalties_eur or []) + list(trk.monthly_royalties_eur)
                del track_map[isrc_key]

    tracks_list = list(track_map.values())
    raw_track_eur_sum = sum(t.ltm_royalties_eur or 0.0 for t in tracks_list)
    raw_track_stream_sum = sum(t.annual_streams or 0 for t in tracks_list)
    if same_distributor and len(valid) > 1 and raw_track_eur_sum > 0:
        ltm_norm_factor = combined_ltm_eur / raw_track_eur_sum
        stream_norm_factor = (combined_ltm_streams / raw_track_stream_sum) if raw_track_stream_sum > 0 else ltm_norm_factor
        for t in tracks_list:
            t.ltm_royalties_eur = round((t.ltm_royalties_eur or 0.0) * ltm_norm_factor, 4)
            t.annual_streams = int(round((t.annual_streams or 0) * stream_norm_factor))
            if t.monthly_royalties_eur and len(t.monthly_royalties_eur) >= 6:
                t.empirical_annual_decay_rate = compute_empirical_track_Slope(t.monthly_royalties_eur)

    total_track_ltm = max(1e-6, sum(t.ltm_royalties_eur or 0.0 for t in tracks_list))
    for t in tracks_list:
        t.revenue_share = round((t.ltm_royalties_eur or 0.0) / total_track_ltm, 6)
    tracks_list.sort(key=lambda t: t.ltm_royalties_eur or 0.0, reverse=True)

    # Combine DSP share weighted by LTM royalty
    dsp_weighted: Dict[str, float] = defaultdict(float)
    country_weighted: Dict[str, float] = defaultdict(float)
    for s in valid:
        w = max(1.0, s.ltm_net_royalty_eur)
        for dsp, sh in s.dsp_share.items():
            dsp_weighted[dsp] += sh * w
        for c, sh in s.country_share.items():
            country_weighted[c] += sh * w

    dsp_denom = max(1e-6, sum(dsp_weighted.values()))
    country_denom = max(1e-6, sum(country_weighted.values()))
    dsp_share = {
        k: round(v / dsp_denom, 4)
        for k, v in sorted(dsp_weighted.items(), key=lambda kv: kv[1], reverse=True)
    }
    country_share = {
        k: round(v / country_denom, 4)
        for k, v in sorted(country_weighted.items(), key=lambda kv: kv[1], reverse=True)
    }

    all_benchmarks: List[EmpiricalBenchmarkEntry] = []
    for s in valid:
        all_benchmarks.extend(s.benchmarks)

    return ParsedStatementSummary(
        detected_distributor=combined_distributor,
        row_count=sum(s.row_count for s in valid),
        period_start=sorted_months[0] if sorted_months else None,
        period_end=sorted_months[-1] if sorted_months else None,
        months_covered=len(sorted_months),
        total_streams=sum(s.total_streams for s in valid),
        total_net_royalty_eur=round(sum(s.total_net_royalty_eur for s in valid), 2),
        ltm_net_royalty_eur=combined_ltm_eur,
        ltm_streams=combined_ltm_streams,
        tracks=tracks_list,
        monthly_history=monthly_history,
        dsp_share=dsp_share,
        country_share=country_share,
        benchmarks=all_benchmarks[:50],
    )

