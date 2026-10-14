"""Synthetic AF_UNIX protocol and dedicated-container topology tests.

Set CATALOG_PARSER_TEST_SOCKET only in a network-enabled disposable client
container sharing a private socket volume with the separately hardened parser
container. The external-service test exercises all three real parsers.
"""

import hashlib
import io
import os
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest

from services.catalog_review import parser_ipc as ipc
from services.catalog_review.document_validation import (
    MAX_DOCUMENT_BYTES,
    ValidationUnavailable,
)

CSV = b"title,revenue\nSynthetic only,12\n"


@pytest.fixture
def tmp_path():
    # macOS pytest paths include /private/var/... and long test names; sockaddr_un
    # has a much smaller limit. Keep only this module's synthetic sockets short.
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="space-ipc-") as directory:
        yield Path(directory)


class Parser:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def inspect(self, *, content, filename):
        self.calls.append((content, filename))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@contextmanager
def endpoint(tmp_path, handler, timeout=1):
    path = str(tmp_path / "parser.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen(1)
    listener.settimeout(2)

    def run():
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(timeout)
            handler(connection)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run)
        try:
            yield ipc.UnixSocketDocumentParser(socket_path=path, timeout=timeout)
        finally:
            listener.close()
            future.result(timeout=3)


@pytest.mark.parametrize("result", [True, False])
def test_real_unix_socket_roundtrip(tmp_path, result):
    parser = Parser(result)
    with endpoint(
        tmp_path, lambda connection: ipc._serve_connection(connection, parser)
    ) as client:
        assert (
            client.inspect(content=CSV, filename="ignored-private-name.csv") is result
        )
    assert parser.calls == [(CSV, "document.csv")]


@pytest.mark.parametrize("result", [None, 1, "clean", RuntimeError("secret")])
def test_parser_unavailability_propagates_through_unix_socket(tmp_path, result):
    with endpoint(
        tmp_path, lambda connection: ipc._serve_connection(connection, Parser(result))
    ) as client:
        with pytest.raises(ValidationUnavailable):
            client.inspect(content=CSV, filename="synthetic.csv")


@pytest.mark.parametrize(
    "reply",
    [
        b"PASS\n",
        b"",
        ipc._RESPONSE.pack(b"WRONG!!!", 1, hashlib.sha256(CSV).digest()),
        ipc._RESPONSE.pack(ipc._MAGIC, 1, b"0" * 32),
        ipc._RESPONSE.pack(ipc._MAGIC, 1, hashlib.sha256(CSV).digest()) + b"extra",
        ipc._RESPONSE.pack(ipc._MAGIC, 9, hashlib.sha256(CSV).digest()),
    ],
)
def test_malformed_truncated_trailing_or_unbound_reply_never_clean(tmp_path, reply):
    def respond(connection):
        while connection.recv(65536):
            pass
        connection.sendall(reply)

    with endpoint(tmp_path, respond) as client:
        with pytest.raises(ValidationUnavailable):
            client.inspect(content=CSV, filename="synthetic.csv")


def test_ipc_total_deadline_and_missing_service(tmp_path):
    def stall(connection):
        time.sleep(0.25)

    with endpoint(tmp_path, stall, timeout=0.05) as client:
        start = time.monotonic()
        with pytest.raises(ValidationUnavailable):
            client.inspect(content=CSV, filename="synthetic.csv")
        assert time.monotonic() - start < 0.2
    client = ipc.UnixSocketDocumentParser(socket_path=str(tmp_path / "missing.sock"))
    with pytest.raises(ValidationUnavailable):
        client.inspect(content=CSV, filename="synthetic.csv")


@pytest.mark.parametrize(
    "path",
    ["relative.sock", "//tmp/a", "/tmp/../a", "/tmp/a\x00", "/", "/" + "x" * 104],
)
def test_operator_socket_path_validation(path):
    with pytest.raises(ValueError):
        ipc.UnixSocketDocumentParser(socket_path=path)


@pytest.mark.parametrize("timeout", [0, -1, True, float("nan"), float("inf"), 61])
def test_deadline_cannot_be_unbounded(timeout):
    with pytest.raises(ValueError):
        ipc.UnixSocketDocumentParser(socket_path="/tmp/parser.sock", timeout=timeout)


def test_oversized_or_unsupported_files_never_connect(tmp_path):
    client = ipc.UnixSocketDocumentParser(socket_path=str(tmp_path / "missing.sock"))
    assert (
        client.inspect(
            content=b"x" * (MAX_DOCUMENT_BYTES + 1), filename="synthetic.csv"
        )
        is False
    )
    assert client.inspect(content=CSV, filename="synthetic.exe") is False


@pytest.mark.parametrize(
    "frame",
    [
        b"bad",
        ipc._REQUEST.pack(b"WRONG!!!", 1, 1, b"0" * 32),
        ipc._REQUEST.pack(ipc._MAGIC, 1, MAX_DOCUMENT_BYTES + 1, b"0" * 32),
        ipc._REQUEST.pack(ipc._MAGIC, 1, 0, b"0" * 32),
        ipc._REQUEST.pack(ipc._MAGIC, 4, 1, b"0" * 32),
        ipc._REQUEST.pack(ipc._MAGIC, 1, 20, b"0" * 32) + b"short",
        ipc._REQUEST.pack(ipc._MAGIC, 1, 1, b"0" * 32) + b"xx",
    ],
)
def test_server_rejects_bad_framing_before_parser(frame):
    client, server = socket.socketpair()
    parser = Parser()
    with client, server:
        client.sendall(frame)
        client.shutdown(socket.SHUT_WR)
        with pytest.raises(ValidationUnavailable):
            ipc._serve_connection(server, parser, timeout=0.1)
    assert not parser.calls


def test_server_hash_mismatch_never_parses():
    client, server = socket.socketpair()
    parser = Parser()
    with client, server:
        client.sendall(ipc._REQUEST.pack(ipc._MAGIC, 1, len(CSV), b"0" * 32) + CSV)
        client.shutdown(socket.SHUT_WR)
        ipc._serve_connection(server, parser)
        assert ipc._RESPONSE.unpack(client.recv(ipc._RESPONSE.size))[1] == ipc._REJECT
    assert not parser.calls


@pytest.mark.parametrize(
    "uid,interfaces,status",
    [
        (0, [(1, "lo")], "CapEff:\t0\nNoNewPrivs:\t1\n"),
        (1000, [(1, "lo"), (2, "eth0")], "CapEff:\t0\nNoNewPrivs:\t1\n"),
        (1000, [(1, "lo")], "CapEff:\t0000000000000001\nNoNewPrivs:\t1\n"),
        (1000, [(1, "lo")], "CapEff:\t0\nNoNewPrivs:\t0\n"),
    ],
)
def test_service_refuses_unsafe_topology(monkeypatch, uid, interfaces, status):
    monkeypatch.setattr(ipc.isolation.sys, "platform", "linux")
    monkeypatch.setattr(ipc.os, "geteuid", lambda: uid)
    monkeypatch.setattr(ipc.socket, "if_nameindex", lambda: interfaces)
    monkeypatch.setattr(ipc.isolation, "_interface_is_up", lambda name: True)
    monkeypatch.setattr(
        ipc.Path,
        "read_text",
        lambda self: status + "CapPrm:\t0\nCapInh:\t0\nCapAmb:\t0\nCapBnd:\t0\n",
    )
    with pytest.raises(ValidationUnavailable):
        ipc._verify_service_sandbox()


def test_inactive_kernel_tunnels_allowed_only_without_capabilities(monkeypatch):
    monkeypatch.setattr(ipc.isolation.sys, "platform", "linux")
    monkeypatch.setattr(ipc.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ipc.socket, "if_nameindex", lambda: [(1, "lo"), (2, "tunl0")])
    monkeypatch.setattr(ipc.isolation, "_interface_is_up", lambda name: False)
    monkeypatch.setattr(
        ipc.Path,
        "read_text",
        lambda self: "CapEff:\t0\nCapPrm:\t0\nCapInh:\t0\nCapAmb:\t0\nCapBnd:\t0\nNoNewPrivs:\t1\n",
    )
    ipc._verify_service_sandbox()


def test_no_cli_flag_can_attest_or_bypass_isolation():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.catalog_review.parser_ipc",
            "--socket-path",
            "/tmp/synthetic.sock",
            "--network-isolated",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    assert result.returncode != 0


def test_external_dedicated_service_from_network_enabled_worker():
    path = os.environ.get("CATALOG_PARSER_TEST_SOCKET")
    if not path:
        pytest.skip("Dedicated two-container topology not supplied")
    assert sys.platform.startswith("linux")
    assert any(name != "lo" for _, name in socket.if_nameindex())
    # A boolean attestation cannot make the local parser accept this topology.
    with pytest.raises(ValidationUnavailable):
        ipc.SandboxedDocumentParser(network_isolated=True).inspect(
            content=CSV, filename="synthetic.csv"
        )
    # Proves the same server entry point cannot start in the networked worker.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.catalog_review.parser_ipc",
            "--socket-path",
            "/tmp/synthetic-networked-parser.sock",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    assert result.returncode != 0
    client = ipc.UnixSocketDocumentParser(socket_path=path)
    assert client.inspect(content=CSV, filename="synthetic.csv") is True
    assert client.inspect(content=b"a,b\n=1+1,2", filename="synthetic.csv") is False
    from openpyxl import Workbook
    from pypdf import PdfWriter

    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=20, height=20)
    writer.write(pdf)
    workbook = Workbook()
    workbook.active.append(["Synthetic", 12])
    xlsx = io.BytesIO()
    workbook.save(xlsx)
    workbook.close()
    assert client.inspect(content=pdf.getvalue(), filename="synthetic.pdf") is True
    assert client.inspect(content=xlsx.getvalue(), filename="synthetic.xlsx") is True
