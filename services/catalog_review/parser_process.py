"""Internal, standalone parser subprocess. Do not call parsing helpers in workers.

Policy: UTF-8 comma CSV, static PDF, and a narrow data-only OOXML XLSX subset.
Reject formula-looking CSV cells (including leading whitespace/Unicode disguises)
rather than mutate the evidence. XLSX formulas, defined names, hyperlinks,
extensions, drawings, macros, attachments and external relationships are rejected.
PDF actions, attachments, forms, encryption and incremental/hybrid updates are
rejected. Parsing is not rendering and does not prove safety of other viewers.

Dependencies are installed by deployment, never downloaded at validation time.
Pins checked in the child: pypdf==6.19.0, openpyxl==3.1.5,
defusedxml==0.7.1, et-xmlfile==2.0.0. CSV uses only Python's stdlib.
Python 3.11+ on Linux is the supported sandbox runtime.
"""

import csv
import importlib.metadata
import io
import json
import logging
import math
import os
import posixpath
import re
import signal
import socket
import stat
import struct
import sys
import unicodedata
import zipfile
import zlib
from dataclasses import asdict, dataclass, fields
from pathlib import Path

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
PARSER_DEPENDENCIES = (
    "pypdf==6.19.0",
    "openpyxl==3.1.5",
    "defusedxml==0.7.1",
    "et-xmlfile==2.0.0",
)


@dataclass(frozen=True)
class ParserLimits:
    """Operator budgets may be tightened, never raised above these hard ceilings."""

    cpu_seconds: int = 5
    wall_seconds: float = 10.0
    memory_bytes: int = 512 * 1024 * 1024
    max_rows: int = 100_000
    max_columns: int = 256
    max_cells: int = 500_000
    max_cell_chars: int = 32_768
    max_zip_members: int = 256
    max_member_bytes: int = 16 * 1024 * 1024
    max_expanded_bytes: int = 64 * 1024 * 1024
    max_compression_ratio: int = 100
    max_xml_nodes: int = 1_000_000
    max_depth: int = 64
    max_sheets: int = 16
    max_pdf_pages: int = 1_000
    max_pdf_objects: int = 50_000

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            numeric = (
                type(value) in (int, float)
                if field.name == "wall_seconds"
                else type(value) is int
            )
            if (
                not numeric
                or not math.isfinite(value)
                or not 0 < value <= field.default
            ):
                raise ValueError("Invalid parser budget: " + field.name)
        if self.memory_bytes < 64 * 1024 * 1024:
            raise ValueError("At least 64 MiB of address space is required")

    def to_json(self):
        return json.dumps(asdict(self), separators=(",", ":"))


class Rejected(ValueError):
    """A policy violation or malformed document, with no customer data in errors."""


class Unavailable(RuntimeError):
    """Dependencies or containment are not available; not a clean verdict."""


def _interface_is_up(name):
    return bool(int(Path("/sys/class/net", name, "flags").read_text().strip(), 16) & 1)


def require_network_sandbox():
    """Reject direct use in a networked worker; attestation alone is insufficient.

    Deployment still supplies network_mode:none, seccomp and mount isolation.
    Some kernels expose dormant tunnel devices in that namespace; zero effective
    capabilities prevents bringing them up. Every active non-loopback device fails.
    """
    try:
        if not sys.platform.startswith("linux") or os.geteuid() == 0:
            raise Unavailable("Unprivileged Linux parser container required")
        interfaces = {name for _, name in socket.if_nameindex()}
        if "lo" not in interfaces or any(
            _interface_is_up(name) for name in interfaces - {"lo"}
        ):
            raise Unavailable("Parser has network interfaces")
        values = dict(
            line.split(":", 1)
            for line in Path("/proc/self/status").read_text().splitlines()
            if ":" in line
        )
        capabilities = ("CapEff", "CapPrm", "CapInh", "CapAmb", "CapBnd")
        if (
            any(int(values[name], 16) for name in capabilities)
            or values["NoNewPrivs"].strip() != "1"
        ):
            raise Unavailable("Parser privileges not denied")
    except (OSError, ValueError, KeyError):
        raise Unavailable("Parser isolation unverified") from None


def _require_dependencies(*names):
    for requirement in PARSER_DEPENDENCIES:
        name, version = requirement.split("==")
        if name in names:
            try:
                if importlib.metadata.version(name) != version:
                    raise Unavailable("Unvetted parser dependency")
            except importlib.metadata.PackageNotFoundError:
                raise Unavailable("Missing parser dependency") from None


def _apply_limits(limits):
    if not sys.platform.startswith("linux") or sys.version_info < (3, 11):
        raise Unavailable("Unsupported sandbox runtime")
    import resource

    for name, soft, hard in (
        (resource.RLIMIT_CPU, limits.cpu_seconds, limits.cpu_seconds + 1),
        (resource.RLIMIT_AS, limits.memory_bytes, limits.memory_bytes),
        (resource.RLIMIT_FSIZE, 0, 0),
        (resource.RLIMIT_CORE, 0, 0),
        (resource.RLIMIT_NOFILE, 32, 32),
    ):
        current_soft, current_hard = resource.getrlimit(name)
        if current_hard != resource.RLIM_INFINITY:
            hard = min(hard, current_hard)
        if current_soft != resource.RLIM_INFINITY:
            soft = min(soft, current_soft)
        resource.setrlimit(name, (min(soft, hard), hard))
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, limits.wall_seconds)


def _safe_cell(value, limits):
    if len(value) > limits.max_cell_chars:
        raise Rejected("Cell limit")
    if any(unicodedata.category(c) == "Cc" and c not in "\r\n\t" for c in value):
        raise Rejected("Control character")
    normalized = unicodedata.normalize("NFKC", value)
    candidate = normalized.lstrip()
    # Spreadsheet importers disagree on ignorable format/control characters.
    candidate = candidate.lstrip("'\ufeff\u200b\u200c\u200d\u2060").lstrip()
    candidate = "".join(
        c for c in candidate if unicodedata.category(c) != "Cf"
    ).lstrip()
    if candidate.startswith(("=", "+", "-", "@")):
        raise Rejected("Formula-like cell")


def _parse_csv(content, limits):
    prefix = content.removeprefix(b"\xef\xbb\xbf").lstrip()
    if prefix.startswith((b"%PDF-", b"PK", b"MZ", b"\x7fELF", b"<", b"{", b"[", b"#!")):
        raise Rejected("Mismatched text format")
    csv.field_size_limit(limits.max_cell_chars)
    rows = cells = 0
    width = None
    try:
        with io.TextIOWrapper(
            io.BytesIO(content), encoding="utf-8-sig", newline=""
        ) as source:
            for row in csv.reader(source, dialect="excel", strict=True):
                rows += 1
                cells += len(row)
                if (
                    rows > limits.max_rows
                    or cells > limits.max_cells
                    or not 2 <= len(row) <= limits.max_columns
                ):
                    raise Rejected("CSV dimensions")
                if width is not None and len(row) != width:
                    raise Rejected("Ragged CSV")
                width = len(row)
                for cell in row:
                    _safe_cell(cell, limits)
    except (UnicodeError, csv.Error):
        raise Rejected("Malformed CSV") from None
    if not rows:
        raise Rejected("Empty CSV")


_SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
_TYPE_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_XML_NAMESPACES = {
    _SHEET_NS,
    _REL_NS,
    _TYPE_NS,
    _OFFICE_REL.rstrip("/"),
    "http://schemas.openxmlformats.org/drawingml/2006/main",
    "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
    "http://purl.org/dc/elements/1.1/",
    "http://purl.org/dc/terms/",
    "http://purl.org/dc/dcmitype/",
    "http://www.w3.org/2001/XMLSchema-instance",
    "http://www.w3.org/XML/1998/namespace",
}
_FORBIDDEN_XML = {
    "f",
    "formula",
    "formula1",
    "formula2",
    "definedName",
    "externalReference",
    "externalReferences",
    "externalLink",
    "ddeLink",
    "oleLink",
    "oleObject",
    "oleObjects",
    "control",
    "controls",
    "drawing",
    "legacyDrawing",
    "legacyDrawingHF",
    "hyperlink",
    "hyperlinks",
    "extLst",
    "AlternateContent",
    "webPublishItems",
    "webQuery",
    "connections",
    "connection",
    "embeddedObject",
}
_PARTS = {
    "[Content_Types].xml": ("Types", _TYPE_NS, "application/xml"),
    "_rels/.rels": (
        "Relationships",
        _REL_NS,
        "application/vnd.openxmlformats-package.relationships+xml",
    ),
    "docProps/core.xml": (
        "coreProperties",
        "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "application/vnd.openxmlformats-package.core-properties+xml",
    ),
    "docProps/app.xml": (
        "Properties",
        "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
        "application/vnd.openxmlformats-officedocument.extended-properties+xml",
    ),
    "xl/workbook.xml": (
        "workbook",
        _SHEET_NS,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    ),
    "xl/_rels/workbook.xml.rels": (
        "Relationships",
        _REL_NS,
        "application/vnd.openxmlformats-package.relationships+xml",
    ),
    "xl/styles.xml": (
        "styleSheet",
        _SHEET_NS,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml",
    ),
    "xl/sharedStrings.xml": (
        "sst",
        _SHEET_NS,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml",
    ),
}


def _part_policy(name):
    if name in _PARTS:
        return _PARTS[name]
    if re.fullmatch(r"xl/worksheets/sheet[1-9][0-9]*\.xml", name):
        return (
            "worksheet",
            _SHEET_NS,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        )
    if re.fullmatch(r"xl/theme/theme[1-9][0-9]*\.xml", name):
        return (
            "theme",
            "http://schemas.openxmlformats.org/drawingml/2006/main",
            "application/vnd.openxmlformats-officedocument.theme+xml",
        )
    raise Rejected("Unsupported package part")


def _package_name(name):
    if (
        not name
        or not name.isascii()
        or any(c in name for c in "\\:%?#\x00")
        or name.startswith("/")
        or any(p in ("", ".", "..") for p in name.split("/"))
    ):
        raise Rejected("Unsafe archive path")
    return name


def _zip_members(content, limits):
    if not content.startswith(b"PK\x03\x04") or len(content) < 22:
        raise Rejected("Not XLSX ZIP")
    # No ZIP64, multidisk, comments, prepended executables or trailing payloads.
    end = struct.unpack("<4s4H2LH", content[-22:])
    if (
        end[0] != b"PK\x05\x06"
        or end[1]
        or end[2]
        or end[3] != end[4]
        or not 1 <= end[4] <= limits.max_zip_members
        or end[7]
        or end[5] + end[6] != len(content) - 22
    ):
        raise Rejected("Unsupported ZIP directory")
    members = {}
    total = 0
    seen = set()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = sorted(archive.infolist(), key=lambda info: info.header_offset)
        if len(infos) != end[4] or archive.start_dir != end[6]:
            raise Rejected("Inconsistent ZIP directory")
        offset = 0
        for info in infos:
            name = _package_name(info.filename)
            _part_policy(name)
            mode = stat.S_IFMT(info.external_attr >> 16)
            if (
                name.casefold() in seen
                or info.orig_filename != name
                or mode not in (0, stat.S_IFREG)
                or info.is_dir()
                or info.flag_bits & ~0x808
                or info.extract_version > 20
                or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                or info.extra
                or info.comment
                or info.header_offset != offset
                or info.file_size > limits.max_member_bytes
                or info.file_size
                > max(1, info.compress_size) * limits.max_compression_ratio
            ):
                raise Rejected("Unsafe ZIP member")
            seen.add(name.casefold())
            total += info.file_size
            if total > limits.max_expanded_bytes:
                raise Rejected("ZIP expansion limit")
            header = content[offset : offset + 30]
            if len(header) != 30:
                raise Rejected("Truncated ZIP header")
            local = struct.unpack("<4s5H3L2H", header)
            if (
                local[0] != b"PK\x03\x04"
                or local[2] != info.flag_bits
                or local[1] != info.extract_version
                or local[3] != info.compress_type
                or local[10]
            ):
                raise Rejected("Inconsistent ZIP header")
            start = offset + 30 + local[9]
            if content[offset + 30 : start] != name.encode("ascii"):
                raise Rejected("Inconsistent ZIP filename")
            offset = start + info.compress_size
            if offset > archive.start_dir:
                raise Rejected("Overlapping ZIP members")
            packed = content[start:offset]
            # ZipExtFile may truncate at the *declared* file size. Independently
            # check actual deflate EOF/length/CRC so forged sizes cannot hide an
            # expansion bomb or payload after the apparent XML document.
            if info.compress_type == zipfile.ZIP_DEFLATED:
                decoder = zlib.decompressobj(-15)
                try:
                    data = decoder.decompress(packed, limits.max_member_bytes + 1)
                except zlib.error:
                    raise Rejected("Invalid deflate stream") from None
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise Rejected("Incomplete or oversized deflate stream")
            else:
                data = packed
            if len(data) != info.file_size or zlib.crc32(data) != info.CRC:
                raise Rejected("ZIP size/CRC mismatch")
            if info.flag_bits & 8:
                # Signed and unsigned standard data descriptors, never ZIP64.
                if content[offset : offset + 4] == b"PK\x07\x08":
                    offset += 4
                descriptor = content[offset : offset + 12]
                if len(descriptor) != 12 or struct.unpack("<3L", descriptor) != (
                    info.CRC,
                    info.compress_size,
                    info.file_size,
                ):
                    raise Rejected("Invalid ZIP descriptor")
                offset += 12
            elif local[6:9] != (info.CRC, info.compress_size, info.file_size):
                raise Rejected("Inconsistent ZIP sizes")
            members[name] = data
        if offset != archive.start_dir:
            raise Rejected("Hidden ZIP payload")
    required = {
        "[Content_Types].xml",
        "_rels/.rels",
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
    }
    if not required <= members.keys():
        raise Rejected("Missing workbook parts")
    return members


def _cell_position(reference, limits):
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", reference)
    if not match:
        raise Rejected("Invalid cell reference")
    column = 0
    for char in match[1]:
        column = column * 26 + ord(char) - 64
    row = int(match[2])
    if row > limits.max_rows or column > limits.max_columns:
        raise Rejected("Worksheet dimensions")
    return row, column


def _check_xml(members, limits):
    from defusedxml import ElementTree

    nodes = rows = cells = sheets = strings = 0
    defaults, overrides = {}, {}
    relationships = []
    for name, data in members.items():
        expected, namespace, _ = _part_policy(name)
        depth = 0
        previous_row = 0
        previous_cell = (0, 0)
        relationship_ids = set()
        for event, element in ElementTree.iterparse(
            io.BytesIO(data),
            events=("start", "end"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        ):
            if event == "start":
                depth += 1
                nodes += 1
                if depth > limits.max_depth or nodes > limits.max_xml_nodes:
                    raise Rejected("XML resource limit")
                if depth == 1 and element.tag != "{" + namespace + "}" + expected:
                    raise Rejected("Unexpected part root")
                if not element.tag.startswith("{"):
                    raise Rejected("Missing XML namespace")
                ns, tag = element.tag[1:].split("}", 1)
                if ns not in _XML_NAMESPACES or tag in _FORBIDDEN_XML:
                    raise Rejected("Active or unsupported XML")
                for key, value in element.attrib.items():
                    if len(value) > limits.max_cell_chars:
                        raise Rejected("XML attribute limit")
                    if (
                        key.startswith("{")
                        and key[1:].split("}", 1)[0] not in _XML_NAMESPACES
                    ):
                        raise Rejected("Unsupported XML attribute")
                    if key.rsplit("}", 1)[-1] in {
                        "base",
                        "schemaLocation",
                        "noNamespaceSchemaLocation",
                        "href",
                        "src",
                    }:
                        raise Rejected("External XML reference")
                if tag == "sheet":
                    sheets += 1
                    if sheets > limits.max_sheets:
                        raise Rejected("Sheet limit")
                if expected == "worksheet":
                    if tag == "dimension":
                        for reference in element.get("ref", "").split(":"):
                            _cell_position(reference, limits)
                    if tag == "row":
                        index = element.get("r", "")
                        if not re.fullmatch(r"[1-9][0-9]{0,6}", index):
                            raise Rejected("Invalid row index")
                        index = int(index)
                        rows += 1
                        if (
                            index <= previous_row
                            or index > limits.max_rows
                            or rows > limits.max_rows
                        ):
                            raise Rejected("Row limit/order")
                        previous_row = index
                    if tag == "c":
                        position = _cell_position(element.get("r", ""), limits)
                        cells += 1
                        if (
                            position <= previous_cell
                            or position[0] != previous_row
                            or cells > limits.max_cells
                        ):
                            raise Rejected("Cell limit/order")
                        previous_cell = position
                if tag == "si":
                    strings += 1
                    if strings > limits.max_cells:
                        raise Rejected("Shared string limit")
                if name == "[Content_Types].xml" and depth == 2:
                    if tag == "Default":
                        key = element.get("Extension", "")
                        if key not in {"xml", "rels"} or key in defaults:
                            raise Rejected("Unsupported content type")
                        defaults[key] = element.get("ContentType")
                    elif tag == "Override":
                        part = element.get("PartName", "")
                        if not part.startswith("/"):
                            raise Rejected("Invalid content type part")
                        key = _package_name(part[1:])
                        if key not in members or key in overrides:
                            raise Rejected("Invalid content type override")
                        overrides[key] = element.get("ContentType")
                    else:
                        raise Rejected("Invalid content type entry")
                if expected == "Relationships" and depth == 2:
                    if (
                        tag != "Relationship"
                        or element.get("TargetMode", "Internal") != "Internal"
                    ):
                        raise Rejected("External relationship")
                    identifier = element.get("Id")
                    if not identifier or identifier in relationship_ids:
                        raise Rejected("Duplicate relationship")
                    relationship_ids.add(identifier)
                    relationships.append((name, dict(element.attrib)))
            else:
                if element.text:
                    if len(element.text) > limits.max_cell_chars:
                        raise Rejected("XML text limit")
                    if element.tag == "{" + _SHEET_NS + "}t":
                        _safe_cell(element.text, limits)
                element.clear()
                depth -= 1
    for name in members:
        if name != "[Content_Types].xml":
            actual = overrides.get(name, defaults.get(name.rsplit(".", 1)[-1]))
            if actual != _part_policy(name)[2]:
                raise Rejected("Mismatched part content type")
    if any(
        value != {"xml": "application/xml", "rels": _PARTS["_rels/.rels"][2]}[key]
        for key, value in defaults.items()
    ):
        raise Rejected("Unsupported default content type")
    targets = set()
    for source, relationship in relationships:
        target = relationship.get("Target", "")
        target = _package_name(target[1:] if target.startswith("/") else target)
        if not relationship["Target"].startswith("/") and source != "_rels/.rels":
            target = posixpath.join("xl", target)
        kind = relationship.get("Type", "")
        allowed = (
            {
                _OFFICE_REL + "officeDocument": "xl/workbook.xml",
                _OFFICE_REL + "extended-properties": "docProps/app.xml",
                "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties": "docProps/core.xml",
            }
            if source == "_rels/.rels"
            else {
                _OFFICE_REL + "worksheet": r"xl/worksheets/sheet[1-9][0-9]*\.xml",
                _OFFICE_REL + "styles": "xl/styles.xml",
                _OFFICE_REL + "sharedStrings": "xl/sharedStrings.xml",
                _OFFICE_REL + "theme": r"xl/theme/theme[1-9][0-9]*\.xml",
            }
        )
        if (
            kind not in allowed
            or not re.fullmatch(allowed[kind], target)
            or target not in members
        ):
            raise Rejected("Unsupported relationship")
        targets.add(target)
    if not sheets or "xl/workbook.xml" not in targets:
        raise Rejected("No workbook/sheets")
    if any(
        name not in targets
        for name in members
        if not name.endswith(".rels") and name != "[Content_Types].xml"
    ):
        raise Rejected("Unreferenced package part")


def _parse_xlsx(content, limits):
    _require_dependencies("openpyxl", "defusedxml", "et-xmlfile")
    from xml.etree.ElementTree import ParseError

    from defusedxml.common import DefusedXmlException

    try:
        members = _zip_members(content, limits)
        _check_xml(members, limits)
        # Import only after ZIP/XML preflight; never conceal formulas using cached
        # values. Disabling links/macros is defense in depth, not their validation.
        import openpyxl
        from openpyxl.xml import DEFUSEDXML, LXML

        if not DEFUSEDXML or LXML:
            raise Unavailable("Required XML backend unavailable")
        workbook = openpyxl.load_workbook(
            io.BytesIO(content),
            read_only=True,
            data_only=False,
            keep_links=False,
            keep_vba=False,
        )
        try:
            count = rows = 0
            if not 1 <= len(workbook.worksheets) <= limits.max_sheets:
                raise Rejected("Worksheet limit")
            for worksheet in workbook.worksheets:
                worksheet.reset_dimensions()
                for row in worksheet.iter_rows():
                    rows += 1
                    count += len(row)
                    if (
                        rows > limits.max_rows
                        or len(row) > limits.max_columns
                        or count > limits.max_cells
                    ):
                        raise Rejected("Worksheet expansion limit")
                    for cell in row:
                        if cell.data_type == "f":
                            raise Rejected("Spreadsheet formula")
                        if isinstance(cell.value, str):
                            _safe_cell(cell.value, limits)
        finally:
            workbook.close()
    except (zipfile.BadZipFile, DefusedXmlException, ParseError, UnicodeError):
        raise Rejected("Malformed workbook") from None


_PDF_FORBIDDEN_KEYS = {
    "/A",
    "/AA",
    "/OpenAction",
    "/JS",
    "/JavaScript",
    "/Launch",
    "/URI",
    "/SubmitForm",
    "/ImportData",
    "/GoToR",
    "/GoToE",
    "/Rendition",
    "/RichMedia",
    "/Movie",
    "/Sound",
    "/EmbeddedFiles",
    "/EF",
    "/AF",
    "/AcroForm",
    "/XFA",
    "/Collection",
    "/OPI",
    "/Ref",
    "/PS",
    "/PresSteps",
    "/Requirements",
}
_PDF_FORBIDDEN_NAMES = {
    "/Action",
    "/JavaScript",
    "/Launch",
    "/URI",
    "/SubmitForm",
    "/ImportData",
    "/GoToR",
    "/GoToE",
    "/Rendition",
    "/RichMedia",
    "/Movie",
    "/Sound",
    "/EmbeddedFile",
    "/Filespec",
    "/3D",
    "/PS",
    "/Named",
    "/Thread",
    "/Hide",
    "/ResetForm",
    "/SetOCGState",
    "/Trans",
    "/GoTo",
    "/GoTo3DView",
}


def _parse_pdf(content, limits):
    _require_dependencies("pypdf")
    from pypdf import PdfReader, filters
    from pypdf.errors import PdfReadError
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        IndirectObject,
        NameObject,
        StreamObject,
    )

    if not re.match(rb"%PDF-(?:1\.[0-7]|2\.0)[\r\n]", content):
        raise Rejected("PDF signature mismatch")
    if not re.search(rb"%%EOF[ \t\r\n]{0,128}\Z", content):
        raise Rejected("PDF trailer mismatch")
    filters.ZLIB_MAX_OUTPUT_LENGTH = limits.max_member_bytes
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if (
            reader.is_encrypted
            or "/Prev" in reader.trailer
            or "/XRefStm" in reader.trailer
        ):
            raise Rejected("Encrypted or incremental PDF")
        references = [
            IndirectObject(number, generation, reader)
            for generation, table in reader.xref.items()
            for number in table
            if number and generation != 65535
        ]
        references.extend(
            IndirectObject(number, 0, reader) for number in reader.xref_objStm
        )
        if len(references) > limits.max_pdf_objects:
            raise Rejected("PDF object limit")
        # Xref streams can omit their own ID from xref, and pypdf normalizes /Prev
        # out of the public trailer. Include objects resolved while reading xref.
        stack = (
            [(reader.trailer, 0)]
            + [(obj, 0) for obj in reader.resolved_objects.values()]
            + [(ref, 0) for ref in references]
        )
        seen = set()
        nodes = expanded = 0
        while stack:
            obj, depth = stack.pop()
            nodes += 1
            if depth > limits.max_depth or nodes > limits.max_pdf_objects:
                raise Rejected("PDF graph limit")
            if isinstance(obj, IndirectObject):
                key = (obj.idnum, obj.generation)
                if key in seen:
                    continue
                seen.add(key)
                obj = obj.get_object()
                if obj is None:
                    raise Rejected("Missing PDF object")
            if isinstance(obj, DictionaryObject):
                if _PDF_FORBIDDEN_KEYS.intersection(obj):
                    raise Rejected("Active PDF dictionary")
                if obj.get("/Type") == "/XRef" and "/Prev" in obj:
                    raise Rejected("Incremental PDF xref stream")
                if isinstance(obj, StreamObject):
                    if {"/F", "/FFilter", "/FDecodeParms"}.intersection(obj):
                        raise Rejected("External PDF stream")
                    filters_used = obj.get("/Filter", [])
                    if isinstance(filters_used, NameObject):
                        filters_used = [filters_used]
                    if any(
                        item
                        not in {
                            "/FlateDecode",
                            "/ASCIIHexDecode",
                            "/ASCII85Decode",
                            "/RunLengthDecode",
                            "/DCTDecode",
                        }
                        for item in filters_used
                    ):
                        raise Rejected("Unsupported PDF filter")
                    data = obj.get_data()
                    expanded += len(data)
                    if (
                        len(data) > limits.max_member_bytes
                        or expanded > limits.max_expanded_bytes
                    ):
                        raise Rejected("PDF stream expansion limit")
                stack.extend((value, depth + 1) for value in obj.values())
            elif isinstance(obj, ArrayObject):
                stack.extend((value, depth + 1) for value in obj)
            elif isinstance(obj, NameObject) and obj in _PDF_FORBIDDEN_NAMES:
                raise Rejected("Active PDF name")
        if not 1 <= len(reader.pages) <= limits.max_pdf_pages:
            raise Rejected("PDF page limit")
        operations = 0
        for page in reader.pages:
            contents = page.get_contents()
            if contents is not None:
                operations += len(contents.operations)
                if operations > limits.max_pdf_objects:
                    raise Rejected("PDF operation limit")
    except PdfReadError:
        raise Rejected("Malformed PDF") from None


def main():
    response = b"UNAVAILABLE\n"
    try:
        if len(sys.argv) != 3:
            raise Unavailable("Invalid parser invocation")
        limits = ParserLimits(**json.loads(sys.argv[2]))
        _apply_limits(limits)
        require_network_sandbox()
        logging.disable(logging.CRITICAL)
        content = sys.stdin.buffer.read(MAX_DOCUMENT_BYTES + 1)
        if not 0 < len(content) <= MAX_DOCUMENT_BYTES:
            raise Rejected("Document size limit")
        parser = {"csv": _parse_csv, "pdf": _parse_pdf, "xlsx": _parse_xlsx}.get(
            sys.argv[1]
        )
        if parser is None:
            raise Rejected("Unsupported document type")
        parser(content, limits)
        response = b"PASS\n"
    except Rejected:
        response = b"REJECT\n"
    except Exception:
        # Includes memory exhaustion, missing dependencies and unexpected failures.
        # No attacker-controlled content, stack traces or exception text is emitted.
        pass
    os.write(1, response)


if __name__ == "__main__":
    main()
