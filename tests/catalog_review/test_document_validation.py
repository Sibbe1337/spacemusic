"""Synthetic in-memory corpus only; no daemon, customer files or public scanners.

Linux-only cases exercise real fork/exec and kernel limits. Run with the exact
PARSER_DEPENDENCIES installed in a disposable network-denied Linux container.
Host-independent tests still cover the coordinator's quarantine contract.
"""

import hashlib
import importlib.metadata
import io
import json
import signal
import struct
import subprocess
import sys
import time
import warnings
import zipfile
import zlib
from pathlib import Path

import pytest

from services.catalog_review import document_validation as validation
from services.catalog_review import parser_process as child
from services.catalog_review.document_validation import (
    MAX_DOCUMENT_BYTES,
    PARSER_DEPENDENCIES,
    ParserLimits,
    SandboxedDocumentParser,
    ValidationUnavailable,
    validate_document,
)

LINUX = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="Linux RLIMIT sandbox"
)
CSV = b"title,revenue\nSynthetic song,12.50\n"


class Inspector:
    def __init__(self, result=True, events=None, name="scan"):
        self.result = result
        self.events = events if events is not None else []
        self.name = name

    def inspect(self, *, content, filename):
        self.events.append((self.name, content, filename))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def checked(content=CSV, *, scanner=None, parser=None, **overrides):
    args = dict(
        content=content,
        filename="synthetic.csv",
        expected_sha256=hashlib.sha256(content).hexdigest(),
        expected_size=len(content),
        scanner=scanner or Inspector(),
        parser=parser or Inspector(),
    )
    args.update(overrides)
    return validate_document(**args)


def test_hash_av_parser_order_and_identical_bytes():
    events = []
    assert (
        checked(
            scanner=Inspector(events=events, name="av"),
            parser=Inspector(events=events, name="parser"),
        )
        is True
    )
    assert events == [("av", CSV, "synthetic.csv"), ("parser", CSV, "synthetic.csv")]


@pytest.mark.parametrize(
    "override",
    [
        {"expected_sha256": "0" * 64},
        {"expected_sha256": "g" * 64},
        {"expected_sha256": None},
        {"expected_size": 1},
        {"expected_size": True},
        {"content": bytearray(CSV)},
        {"content": b""},
    ],
)
def test_integrity_failure_never_scans_or_parses(override):
    events = []
    assert (
        checked(
            scanner=Inspector(events=events),
            parser=Inspector(events=events),
            **override,
        )
        is False
    )
    assert events == []


def test_25_mib_hard_cap_and_boundary():
    events = []
    assert checked(b"x" * MAX_DOCUMENT_BYTES, scanner=Inspector(events=events)) is True
    assert len(events) == 1
    events.clear()
    assert (
        checked(b"x" * (MAX_DOCUMENT_BYTES + 1), scanner=Inspector(events=events))
        is False
    )
    assert not events


@pytest.mark.parametrize(
    "result", [None, 1, 0, "clean", b"PASS", RuntimeError("secret")]
)
@pytest.mark.parametrize("stage", ["scanner", "parser"])
def test_unavailable_or_non_boolean_never_clean(result, stage):
    events = []
    args = {stage: Inspector(result, events)}
    with pytest.raises(ValidationUnavailable) as error:
        checked(**args)
    assert "secret" not in str(error.value)
    assert len(events) == 1


def test_av_rejection_short_circuits_parser():
    events = []
    assert checked(scanner=Inspector(False), parser=Inspector(events=events)) is False
    assert not events


def test_parser_rejection_is_not_overridden_by_av_pass():
    assert checked(parser=Inspector(False)) is False


def test_network_isolation_must_be_attested():
    with pytest.raises(ValidationUnavailable, match="sandbox"):
        SandboxedDocumentParser().inspect(content=CSV, filename="synthetic.csv")
    with pytest.raises(ValueError):
        SandboxedDocumentParser(network_isolated="true")


def test_unsupported_platform_quarantines(monkeypatch):
    monkeypatch.setattr(validation.sys, "platform", "darwin")
    with pytest.raises(ValidationUnavailable):
        SandboxedDocumentParser(network_isolated=True).inspect(
            content=CSV, filename="synthetic.csv"
        )


@pytest.mark.parametrize(
    "filename",
    ["../../a.csv", "a\\b.csv", "fake.xlsm", "bad.csv.exe", "nul\x00.csv", "x:y.csv"],
)
def test_no_filename_paths_or_unsupported_types(filename):
    assert SandboxedDocumentParser().inspect(content=CSV, filename=filename) is False


@pytest.mark.parametrize(
    "limits",
    [
        {"cpu_seconds": 0},
        {"cpu_seconds": True},
        {"cpu_seconds": 6},
        {"memory_bytes": 1024},
        {"max_rows": 100_001},
        {"max_cells": -1},
        {"wall_seconds": float("inf")},
        {"wall_seconds": float("nan")},
        {"max_zip_members": 257},
        {"max_depth": "4"},
    ],
)
def test_limits_cannot_be_disabled_or_increased(limits):
    with pytest.raises(ValueError):
        ParserLimits(**limits)


def test_dependencies_are_exact_and_missing_or_mismatched_fail_closed(monkeypatch):
    assert PARSER_DEPENDENCIES == (
        "pypdf==6.19.0",
        "openpyxl==3.1.5",
        "defusedxml==0.7.1",
        "et-xmlfile==2.0.0",
    )
    monkeypatch.setattr(child.importlib.metadata, "version", lambda name: "0.0.0")
    with pytest.raises(child.Unavailable):
        child._require_dependencies("pypdf")

    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(child.importlib.metadata, "version", missing)
    with pytest.raises(child.Unavailable):
        child._require_dependencies("openpyxl")


@pytest.fixture
def parser():
    if not sys.platform.startswith("linux"):
        pytest.skip("Real parser requires Linux resource containment")
    try:
        validation.require_network_sandbox()
    except validation.Unavailable:
        pytest.skip("Real parser requires network-isolated Linux sandbox")
    return SandboxedDocumentParser(network_isolated=True)


@pytest.fixture
def workbook():
    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    book.active.append(["title", "revenue"])
    book.active.append(["Synthetic only", -12.5])
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def pdf_bytes(change=None):
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    stream = DecodedStreamObject()
    stream.set_data(b"q 1 0 0 1 0 0 cm Q\n")
    page[NameObject("/Contents")] = writer._add_object(stream)
    if change:
        change(writer)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def rewrite_zip(content, *, updates=None, extra=(), transform=None):
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(content)) as source,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as dest,
    ):
        for info in source.infolist():
            data = (updates or {}).get(info.filename, source.read(info))
            if transform:
                info, data = transform(info, data)
            dest.writestr(info, data)
        for name, data in extra:
            dest.writestr(name, data)
    return output.getvalue()


def zip_part(content, name):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return archive.read(name)


def assert_not_clean(parser, content, filename):
    try:
        assert parser.inspect(content=content, filename=filename) is False
    except ValidationUnavailable:
        pass  # Crashes/budget exhaustion quarantine, never acceptance.


def test_static_csv_pdf_xlsx_pass_with_real_subprocess(parser, workbook):
    for content, name in [
        (CSV, "synthetic.CSV"),
        (pdf_bytes(), "synthetic.pdf"),
        (workbook, "synthetic.xlsx"),
    ]:
        assert parser.inspect(content=content, filename=name) is True
        assert checked(content, filename=name, parser=parser) is True


@pytest.mark.parametrize(
    "content",
    [
        b"title,revenue\r\nSong,12.5\r\n",
        b'\xef\xbb\xbftitle,revenue\n"Song, a",12\n',
        b'title,notes\nSong,"line one\nline two"\n',
    ],
)
def test_csv_literal_utf8_bom_quotes_and_multiline(parser, content):
    assert parser.inspect(content=content, filename="synthetic.csv") is True


@pytest.mark.parametrize(
    "cell",
    [
        "=1+1",
        "+1+1",
        "-1+1",
        "@SUM(A1)",
        "\t=1+1",
        "\r=1+1",
        "\n=1+1",
        '   =HYPERLINK("https://example.invalid")',
        "\ufeff=1",
        "\u200b=1",
        "\u200b \ufeff=1",
        "\uff1d1+1",
        "'=1+1",
        "\x00=1+1",
        "=cmd|' /C synthetic'!A0",
    ],
)
def test_csv_formula_disguises_rejected_without_evaluation(parser, cell):
    import csv

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["title", "value"])
    writer.writerow(["synthetic", cell])
    assert (
        parser.inspect(content=output.getvalue().encode(), filename="synthetic.csv")
        is False
    )


@pytest.mark.parametrize(
    "content",
    [
        b'a,b\n"unclosed,2',
        b'a,b\n"bad"stuff,2',
        b"a,b\none,two,three\n",
        b"plain text",
        b"a,b\n\xff,b\n",
        b"a,b\nx,\x00\n",
        b"a,b\n\n",
        b"<html>,stuff</html>",
        b'{"json":1},2',
        b"PK\x03\x04,a",
        b"%PDF-1.7,a",
        b"MZ,a",
        b"a\x00,\x00b\x00",
        b"\xef\xbb\xbf",
    ],
)
def test_csv_malformed_and_format_confusion(parser, content):
    assert parser.inspect(content=content, filename="synthetic.csv") is False


@pytest.mark.parametrize(
    "limit,content",
    [
        ({"max_rows": 1}, CSV),
        ({"max_columns": 1}, CSV),
        ({"max_cells": 3}, CSV),
        ({"max_cell_chars": 4}, CSV),
    ],
)
def test_csv_resource_dimensions(limit, content):
    parser = SandboxedDocumentParser(
        network_isolated=True, limits=ParserLimits(**limit)
    )
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux sandbox")
    try:
        validation.require_network_sandbox()
    except validation.Unavailable:
        pytest.skip("Real parser requires network-isolated Linux sandbox")
    assert parser.inspect(content=content, filename="synthetic.csv") is False


def test_extension_content_consistency(parser, workbook):
    for content, suffix in [
        (CSV, "pdf"),
        (CSV, "xlsx"),
        (workbook, "pdf"),
        (workbook, "csv"),
        (pdf_bytes(), "xlsx"),
        (pdf_bytes(), "csv"),
    ]:
        assert parser.inspect(content=content, filename="synthetic." + suffix) is False


@pytest.mark.parametrize(
    "name",
    [
        "../escape.xml",
        "/absolute.xml",
        "xl/../escape.xml",
        "xl\\escape.xml",
        "C:/escape.xml",
        "xl/%2e%2e/escape.xml",
        "xl//escape.xml",
        "xl/./escape.xml",
        "xl/vbaProject.bin",
        "xl/embeddings/object.bin",
        "xl/activeX/activeX1.xml",
        "xl/externalLinks/externalLink1.xml",
        "xl/connections.xml",
        "customUI/customUI.xml",
        "nested.zip",
        "xl/worksheets/_rels/sheet1.xml.rels",
    ],
)
def test_xlsx_path_macro_external_embedded_unknown_parts(parser, workbook, name):
    content = rewrite_zip(workbook, extra=[(name, b"synthetic")])
    assert parser.inspect(content=content, filename="synthetic.xlsx") is False


def test_xlsx_duplicate_symlink_encrypted_and_hidden_members(parser, workbook):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        duplicate = rewrite_zip(workbook, extra=[("xl/workbook.xml", b"duplicate")])

    def symlink(info, data):
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        return info, data

    encrypted = bytearray(workbook)
    for magic, flags_offset in [(b"PK\x03\x04", 6), (b"PK\x01\x02", 8)]:
        offset = encrypted.index(magic) + flags_offset
        flags = struct.unpack_from("<H", encrypted, offset)[0]
        struct.pack_into("<H", encrypted, offset, flags | 1)
    for content in [
        duplicate,
        rewrite_zip(workbook, transform=symlink),
        bytes(encrypted),
        workbook + b"payload",
        b"MZ" + workbook,
        workbook[:-10],
    ]:
        assert parser.inspect(content=content, filename="synthetic.xlsx") is False


@pytest.mark.parametrize(
    "xml",
    [
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>',
        b'<!DOCTYPE worksheet [<!ENTITY x SYSTEM "file:///etc/passwd">]><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">&x;</worksheet>',
        b'<!DOCTYPE worksheet [<!ENTITY a "AAAA"><!ENTITY b "&a;&a;&a;">]><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">&b;</worksheet>',
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><extLst/></worksheet>',
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:XFD1048576"/></worksheet>',
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1048576"><c r="A1048576"/></row></sheetData></worksheet>',
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="XFD1"/></row></sheetData></worksheet>',
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><hyperlinks/></worksheet>',
    ],
)
def test_xlsx_active_xml_entities_and_sparse_dimensions(parser, workbook, xml):
    content = rewrite_zip(workbook, updates={"xl/worksheets/sheet1.xml": xml})
    assert parser.inspect(content=content, filename="synthetic.xlsx") is False


def test_xlsx_external_targets_and_macro_content_types(parser, workbook):
    name = "xl/_rels/workbook.xml.rels"
    rels = zip_part(workbook, name)
    external = rels.replace(b'Type="', b'TargetMode="External" Type="', 1)
    types = zip_part(workbook, "[Content_Types].xml").replace(
        b"spreadsheetml.sheet.main+xml", b"ms-excel.sheet.macroEnabled.main+xml"
    )
    for updates in [{name: external}, {"[Content_Types].xml": types}]:
        assert (
            parser.inspect(
                content=rewrite_zip(workbook, updates=updates),
                filename="synthetic.xlsx",
            )
            is False
        )


@pytest.mark.parametrize(
    "limits",
    [
        {"max_zip_members": 2},
        {"max_member_bytes": 128},
        {"max_expanded_bytes": 256},
        {"max_compression_ratio": 2},
        {"max_xml_nodes": 8},
        {"max_depth": 2},
        {"max_rows": 1},
        {"max_columns": 1},
        {"max_cells": 2},
        {"max_cell_chars": 4},
    ],
)
def test_xlsx_resource_limits(parser, workbook, limits):
    limited = SandboxedDocumentParser(
        network_isolated=True, limits=ParserLimits(**limits)
    )
    assert limited.inspect(content=workbook, filename="synthetic.xlsx") is False


def test_xlsx_zipbomb_rejected_before_xml_or_workbook(parser, workbook):
    content = rewrite_zip(
        workbook, updates={"xl/worksheets/sheet1.xml": b"x" * (2 * 1024 * 1024)}
    )
    assert len(content) < 30_000
    assert parser.inspect(content=content, filename="synthetic.xlsx") is False


def test_xlsx_forged_zip_lengths_do_not_hide_deflate_payload(parser, workbook):
    part = "xl/worksheets/sheet1.xml"
    original = zip_part(workbook, part)
    # Real deflate stream expands beyond the CRC/size promised by BOTH headers.
    altered = bytearray(
        rewrite_zip(workbook, updates={part: original + b"x" * 100_000})
    )
    with zipfile.ZipFile(io.BytesIO(altered)) as archive:
        info = archive.getinfo(part)
    struct.pack_into("<L", altered, info.header_offset + 14, zlib.crc32(original))
    struct.pack_into("<L", altered, info.header_offset + 22, len(original))
    position = 0
    while True:
        position = altered.index(b"PK\x01\x02", position)
        name_size = struct.unpack_from("<H", altered, position + 28)[0]
        if altered[position + 46 : position + 46 + name_size] == part.encode():
            struct.pack_into("<L", altered, position + 16, zlib.crc32(original))
            struct.pack_into("<L", altered, position + 24, len(original))
            break
        position += 4
    assert parser.inspect(content=bytes(altered), filename="synthetic.xlsx") is False


def test_xlsx_crc_failure_and_stored_zip(parser, workbook):
    def stored(info, data):
        info.compress_type = zipfile.ZIP_STORED
        return info, data

    content = rewrite_zip(workbook, transform=stored)
    assert parser.inspect(content=content, filename="synthetic.xlsx") is True
    content = content.replace(b"Synthetic only", b"Corrupted only")
    assert parser.inspect(content=content, filename="synthetic.xlsx") is False


@pytest.mark.parametrize(
    "attribute",
    [
        b'xml:base="https://example.invalid/"',
        b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:test https://example.invalid/schema"',
    ],
)
def test_xlsx_xml_external_resolution_hints_rejected(parser, workbook, attribute):
    name = "xl/worksheets/sheet1.xml"
    data = zip_part(workbook, name).replace(
        b"<worksheet ", b"<worksheet " + attribute + b" ", 1
    )
    assert (
        parser.inspect(
            content=rewrite_zip(workbook, updates={name: data}),
            filename="synthetic.xlsx",
        )
        is False
    )


def test_xlsx_sheet_limit_and_declared_dimensions_cannot_hide_cells(parser, workbook):
    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    book.create_sheet("Synthetic two")
    output = io.BytesIO()
    book.save(output)
    book.close()
    limited = SandboxedDocumentParser(
        network_isolated=True, limits=ParserLimits(max_sheets=1)
    )
    assert (
        limited.inspect(content=output.getvalue(), filename="synthetic.xlsx") is False
    )
    part = "xl/worksheets/sheet1.xml"
    data = zip_part(workbook, part).replace(b"A1:B2", b"A1:A1")
    data = data.replace(
        b'<c r="B2" t="n"><v>-12.5</v></c>', b'<c r="B2"><f>1+1</f><v>2</v></c>'
    )
    assert b"<f>1+1</f>" in data
    assert (
        parser.inspect(
            content=rewrite_zip(workbook, updates={part: data}),
            filename="synthetic.xlsx",
        )
        is False
    )


@pytest.mark.parametrize(
    "key",
    [
        "/OpenAction",
        "/AA",
        "/AcroForm",
        "/XFA",
        "/EmbeddedFiles",
        "/AF",
        "/Collection",
        "/OPI",
    ],
)
def test_pdf_active_dictionaries(parser, key):
    from pypdf.generic import DictionaryObject, NameObject

    def change(writer):
        writer._root_object[NameObject(key)] = DictionaryObject()

    assert parser.inspect(content=pdf_bytes(change), filename="synthetic.pdf") is False


@pytest.mark.parametrize(
    "action",
    [
        "/JavaScript",
        "/Launch",
        "/URI",
        "/SubmitForm",
        "/GoToR",
        "/ImportData",
        "/RichMedia",
        "/Filespec",
    ],
)
def test_pdf_unreferenced_actions_are_still_inspected(parser, action):
    from pypdf.generic import DictionaryObject, NameObject

    def change(writer):
        writer._add_object(DictionaryObject({NameObject("/S"): NameObject(action)}))

    assert parser.inspect(content=pdf_bytes(change), filename="synthetic.pdf") is False


def test_pdf_attachments_external_streams_and_encryption(parser):
    from pypdf.generic import DecodedStreamObject, NameObject, TextStringObject

    def external(writer):
        stream = DecodedStreamObject()
        stream.set_data(b"synthetic")
        stream[NameObject("/F")] = TextStringObject(
            "https://example.invalid/never-request"
        )
        writer._add_object(stream)

    for change in [
        external,
        lambda writer: writer.add_attachment("synthetic.txt", b"synthetic"),
        lambda writer: writer.add_js("app.alert('synthetic')"),
        lambda writer: writer.encrypt("synthetic-only"),
    ]:
        assert (
            parser.inspect(content=pdf_bytes(change), filename="synthetic.pdf") is False
        )


def test_pdf_stream_bomb_page_and_object_limits(parser):
    from pypdf.generic import DecodedStreamObject

    def bomb(writer):
        stream = DecodedStreamObject()
        stream.set_data(b"x" * 100_000)
        writer._add_object(stream.flate_encode())

    limited = SandboxedDocumentParser(
        network_isolated=True, limits=ParserLimits(max_member_bytes=1024)
    )
    assert_not_clean(limited, pdf_bytes(bomb), "synthetic.pdf")
    pages = pdf_bytes(lambda writer: writer.add_blank_page(width=20, height=20))
    limited = SandboxedDocumentParser(
        network_isolated=True, limits=ParserLimits(max_pdf_pages=1)
    )
    assert limited.inspect(content=pages, filename="synthetic.pdf") is False
    limited = SandboxedDocumentParser(
        network_isolated=True, limits=ParserLimits(max_pdf_objects=2)
    )
    assert limited.inspect(content=pdf_bytes(), filename="synthetic.pdf") is False


def test_pdf_truncation_polyglot_and_malformed(parser):
    content = pdf_bytes()
    for altered in [
        content[:-30],
        content + b"<script>synthetic</script>",
        b"MZ" + content,
        b"%PDF-1.7\ninvalid\n%%EOF",
        content.replace(b"startxref", b"badxxxxxx"),
    ]:
        assert_not_clean(parser, altered, "synthetic.pdf")


def test_pdf_incremental_update_rejected(parser):
    from pypdf import PdfWriter

    writer = PdfWriter(io.BytesIO(pdf_bytes()), incremental=True)
    writer.add_metadata({"/Title": "Synthetic incremental update"})
    output = io.BytesIO()
    writer.write(output)
    assert b"/Prev" in output.getvalue()
    assert parser.inspect(content=output.getvalue(), filename="synthetic.pdf") is False


def test_pdf_escaped_action_names_rejected(parser):
    # Construct offsets after encoding escaped names, rather than corrupt xref.
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 20 20] >>",
        b"<< /S /Java#53cript /J#53 (synthetic) >>",
    ]
    data = bytearray(b"%PDF-1.7\n")
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(b"xref\n0 5\n0000000000 65535 f \n")
    for offset in offsets:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    assert parser.inspect(content=bytes(data), filename="synthetic.pdf") is False


@LINUX
def test_missing_dependencies_in_real_child_never_pass():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(Path(child.__file__).resolve()),
            "pdf",
            ParserLimits().to_json(),
        ],
        input=pdf_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=12,
    )
    assert result.stdout == b"UNAVAILABLE\n"
    assert result.stderr == b""


def probe(body, limits=None):
    limits = limits or ParserLimits(
        cpu_seconds=1, wall_seconds=4, memory_bytes=64 * 1024 * 1024
    )
    code = (
        "import runpy,resource,signal,sys,time,os,json; "
        f"ns=runpy.run_path({str(Path(child.__file__).resolve())!r}); "
        f"limits=ns['ParserLimits'](**json.loads({limits.to_json()!r})); "
        "ns['_apply_limits'](limits);\n" + body
    )
    return subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=8,
    )


@LINUX
def test_real_linux_cpu_limit_kills_busy_child():
    result = probe("while True: pass")
    assert result.returncode in (-signal.SIGXCPU, -signal.SIGKILL)


@LINUX
def test_real_linux_memory_limit_prevents_large_allocation():
    result = probe(
        "try:\n bytearray(256*1024*1024)\nexcept MemoryError:\n sys.exit(73)"
    )
    assert result.returncode == 73


@LINUX
def test_real_linux_alarm_bounds_wallclock():
    result = probe("time.sleep(5)", ParserLimits(wall_seconds=0.2))
    assert result.returncode == -signal.SIGALRM


@LINUX
def test_real_linux_auxiliary_limits():
    result = probe(
        "print(json.dumps({n:resource.getrlimit(getattr(resource,n)) for n in ['RLIMIT_CORE','RLIMIT_FSIZE','RLIMIT_NOFILE','RLIMIT_AS','RLIMIT_CPU']}))"
    )
    assert result.returncode == 0
    limits = json.loads(result.stdout)
    assert limits == {
        "RLIMIT_CORE": [0, 0],
        "RLIMIT_FSIZE": [0, 0],
        "RLIMIT_NOFILE": [32, 32],
        "RLIMIT_AS": [64 * 1024 * 1024] * 2,
        "RLIMIT_CPU": [1, 2],
    }


@LINUX
def test_resource_limit_installation_failure_never_reads_document():
    code = (
        "import runpy,sys; "
        f"ns=runpy.run_path({str(Path(child.__file__).resolve())!r}); "
        f"sys.argv=['parser','csv',{ParserLimits().to_json()!r}]; "
        "ns['main'].__globals__['_apply_limits']=lambda _: (_ for _ in ()).throw(OSError()); "
        "ns['main']()"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        input=CSV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    assert result.stdout == b"UNAVAILABLE\n"
    assert not result.stderr


def replace_child(monkeypatch, code):
    monkeypatch.setattr(validation, "require_network_sandbox", lambda: None)
    real_popen = subprocess.Popen
    processes = []

    def launch(args, **kwargs):
        assert args[1:3] == ["-I", "-B"]
        assert kwargs["close_fds"] and kwargs["start_new_session"]
        assert kwargs["cwd"] == "/"
        assert "PYTHONPATH" not in kwargs["env"]
        assert "SECRET" not in kwargs["env"]
        process = real_popen([sys.executable, "-I", "-B", "-c", code], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(validation.subprocess, "Popen", launch)
    return processes


@LINUX
@pytest.mark.parametrize(
    "code",
    [
        "import os; os.write(1,b'PASS\\nextra')",
        "import os; os.write(1,b'PASS\\n'); os._exit(1)",
        "import os; os.write(1,b'PASS\\n'*100000)",
        "import os; os._exit(0)",
        "import os,signal; os.kill(os.getpid(),signal.SIGKILL)",
        "import os; os.write(1,b'UNAVAILABLE\\n')",
    ],
)
def test_failed_crashed_or_oversized_child_protocol_quarantines(monkeypatch, code):
    processes = replace_child(monkeypatch, code)
    with pytest.raises(ValidationUnavailable):
        SandboxedDocumentParser(network_isolated=True).inspect(
            content=CSV, filename="synthetic.csv"
        )
    assert all(
        process.poll() is not None and process.stdout.closed for process in processes
    )


@LINUX
def test_parent_wallclock_kills_and_reaps_unresponsive_child(monkeypatch):
    processes = replace_child(monkeypatch, "import time; time.sleep(20)")
    parser = SandboxedDocumentParser(
        network_isolated=True, limits=ParserLimits(wall_seconds=0.2)
    )
    start = time.monotonic()
    with pytest.raises(ValidationUnavailable):
        parser.inspect(content=CSV, filename="synthetic.csv")
    assert time.monotonic() - start < 3
    assert processes[0].returncode == -signal.SIGKILL


@LINUX
def test_parent_kills_process_group_including_descendant(monkeypatch, tmp_path):
    pidfile = tmp_path / "synthetic-child.pid"
    code = (
        "import os,time; pid=os.fork(); "
        f"open({str(pidfile)!r},'w').write(str(os.getpid())) if pid==0 else None; "
        "time.sleep(20)"
    )
    processes = replace_child(monkeypatch, code)
    parser = SandboxedDocumentParser(
        network_isolated=True, limits=ParserLimits(wall_seconds=0.5)
    )
    with pytest.raises(ValidationUnavailable):
        parser.inspect(content=CSV, filename="synthetic.csv")
    assert processes[0].returncode == -signal.SIGKILL
    descendant = int(pidfile.read_text())
    status = Path(f"/proc/{descendant}/stat")
    for _ in range(50):
        if not status.exists() or status.read_text().split()[2] == "Z":
            break
        time.sleep(0.01)
    else:
        pytest.fail("Parser descendant survived process-group cleanup")


@LINUX
def test_spawn_failure_and_tempfile_failure_quarantine(monkeypatch):
    monkeypatch.setattr(validation, "require_network_sandbox", lambda: None)

    def unavailable(*args, **kwargs):
        raise OSError("secret")

    monkeypatch.setattr(validation.subprocess, "Popen", unavailable)
    parser = SandboxedDocumentParser(network_isolated=True)
    with pytest.raises(ValidationUnavailable, match="process unavailable"):
        parser.inspect(content=CSV, filename="synthetic.csv")
    monkeypatch.setattr(validation.tempfile, "TemporaryFile", unavailable)
    with pytest.raises(ValidationUnavailable, match="process unavailable"):
        parser.inspect(content=CSV, filename="synthetic.csv")
