"""Synthetic INSTREAM protocol only: no socket, daemon or antivirus installation."""

import socket
import struct
from collections import deque

import pytest

from services.catalog_review import scanner as scanner_module
from services.catalog_review.scanner import (
    MAX_CHUNK_BYTES,
    MAX_DOCUMENT_BYTES,
    MAX_RESPONSE_BYTES,
    ClamAVScanner,
    ScannerUnavailable,
)

SOCKET_PATH = "/synthetic/clamd.sock"


@pytest.fixture(autouse=True)
def no_real_sockets(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Test attempted a real socket or DNS lookup")

    for name in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, forbidden)


class FakeSocket:
    def __init__(self, replies=(b"stream: OK\x00", b""), *, failure=None):
        self.replies = deque(replies)
        self.failure = failure
        self.sent = []
        self.addresses = []
        self.timeouts = []
        self.read_sizes = []
        self.closes = 0

    def settimeout(self, value):
        assert 0 < value <= 60
        if self.failure == "settimeout":
            raise OSError("synthetic timeout configuration failure")
        self.timeouts.append(value)

    def connect(self, address):
        assert self.timeouts
        self.addresses.append(address)
        if self.failure == "connect":
            raise OSError("synthetic connection failure")

    def sendall(self, data):
        self.sent.append(data)
        if self.failure == "send":
            raise BrokenPipeError("synthetic send failure")
        if self.failure == "chunk" and len(self.sent) == 2:
            raise TimeoutError("synthetic chunk timeout")
        if self.failure == "terminator" and data == b"\x00" * 4:
            raise TimeoutError("synthetic terminator timeout")

    def recv(self, amount):
        assert 0 < amount <= 1024
        self.read_sizes.append(amount)
        if self.failure == "recv":
            raise TimeoutError("synthetic read timeout")
        assert self.replies, "Adapter read beyond scripted EOF"
        item = self.replies.popleft()
        if isinstance(item, Exception):
            raise item
        if isinstance(item, bytes) and len(item) > amount:
            self.replies.appendleft(item[amount:])
            item = item[:amount]
        return item

    def close(self):
        self.closes += 1
        if self.failure == "close":
            raise OSError("synthetic close failure")


class FakeFactory:
    def __init__(self, connection=None, *, error=None):
        self.connection = connection if connection is not None else FakeSocket()
        self.error = error
        self.calls = []

    def __call__(self, family, kind):
        self.calls.append((family, kind))
        if self.error:
            raise self.error
        return self.connection


def scanner(connection=None, **overrides):
    factory = FakeFactory(connection)
    options = {"socket_factory": factory, "socket_path": SOCKET_PATH, **overrides}
    return ClamAVScanner(**options), factory


def test_constructor_does_not_contact_scanner():
    _, factory = scanner()
    assert factory.calls == []
    assert factory.connection.sent == []


@pytest.mark.parametrize(
    "path",
    [
        None,
        "",
        "/",
        "relative.sock",
        "127.0.0.1:3310",
        "unix:///tmp/clamd.sock",
        "//tmp/clamd.sock",
        "/tmp/../clamd.sock",
        "/tmp/./clamd.sock",
        "/tmp//clamd.sock",
        "/tmp/clamd.sock/",
        "/tmp/clamd\x00.sock",
        "/" + "x" * 103,
        "/" + "\u00e9" * 52,
    ],
)
def test_rejects_noncanonical_unix_paths_and_network_targets(path):
    factory = FakeFactory()
    with pytest.raises(ValueError):
        ClamAVScanner(socket_factory=factory, socket_path=path)
    assert factory.calls == []


@pytest.mark.parametrize(
    "timeout", [0, -1, 61, float("inf"), float("nan"), "10", True, None]
)
def test_rejects_unbounded_timeouts(timeout):
    with pytest.raises(ValueError):
        scanner(timeout=timeout)


@pytest.mark.parametrize("size", [0, -1, MAX_CHUNK_BYTES + 1, True, 1.5, None])
def test_rejects_invalid_chunk_limits(size):
    with pytest.raises(ValueError):
        scanner(chunk_size=size)


def test_requires_explicit_factory_and_has_no_tcp_option():
    with pytest.raises(ValueError):
        scanner(socket_factory=None)
    with pytest.raises(TypeError):
        ClamAVScanner(socket_path=SOCKET_PATH)
    with pytest.raises(TypeError):
        scanner(host="example.com")


@pytest.mark.parametrize(
    "content", [b"", "text", bytearray(b"x"), None, b"x" * (MAX_DOCUMENT_BYTES + 1)]
)
def test_rejects_invalid_content_before_creating_socket(content):
    adapter, factory = scanner()
    with pytest.raises(ValueError):
        adapter.inspect(content=content, filename="synthetic.csv")
    assert factory.calls == []


@pytest.mark.parametrize("chunk_size", [1, 3, MAX_CHUNK_BYTES])
def test_complete_clean_reply_and_exact_instream_framing(chunk_size):
    connection = FakeSocket()
    adapter, factory = scanner(connection, chunk_size=chunk_size)
    content = b"synthetic\x00payload"
    assert (
        adapter.inspect(content=content, filename="../../never-open.pdf\nSCAN /secret")
        is True
    )
    assert factory.calls == [(socket.AF_UNIX, socket.SOCK_STREAM)]
    assert connection.addresses == [SOCKET_PATH]
    assert connection.sent[0] == b"zINSTREAM\x00"
    assert connection.sent[-1] == b"\x00\x00\x00\x00"
    recovered = bytearray()
    for packet in connection.sent[1:-1]:
        size = struct.unpack("!I", packet[:4])[0]
        assert 0 < size <= chunk_size
        assert len(packet) == size + 4
        recovered.extend(packet[4:])
    assert recovered == content
    assert connection.closes == 1
    assert len(connection.read_sizes) == 2  # Includes EOF after the NUL.


def test_stream_accepts_exact_25_mib_limit_without_oversized_chunks():
    connection = FakeSocket()
    adapter, _ = scanner(connection)
    assert (
        adapter.inspect(content=b"x" * MAX_DOCUMENT_BYTES, filename="synthetic.xlsx")
        is True
    )
    assert sum(len(part) - 4 for part in connection.sent[1:-1]) == MAX_DOCUMENT_BYTES
    assert max(len(part) for part in connection.sent[1:-1]) <= MAX_CHUNK_BYTES + 4


@pytest.mark.parametrize(
    "reply",
    [
        b"stream: OK\x00",
        b"stream: Synthetic-Test-Signature FOUND\x00",
        b"stream: Test signature (synthetic) FOUND\x00",
    ],
)
def test_fragmented_valid_responses_only_return_exact_bool(reply):
    connection = FakeSocket([bytes([byte]) for byte in reply] + [b""])
    adapter, _ = scanner(connection)
    verdict = adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert type(verdict) is bool
    assert verdict is (reply == b"stream: OK\x00")
    assert connection.closes == 1


@pytest.mark.parametrize(
    "reply",
    [
        b"",
        b"stream: OK",
        b"stream: OK\n",
        b"stream: OK\r\n",
        b"OK\x00",
        b"stream: ok\x00",
        b"stream: OK \x00",
        b"other: OK\x00",
        b"1: stream: OK\x00",
        b"stream: UNKNOWN\x00",
        b"UNKNOWN COMMAND\x00",
        b"stream: ERROR\x00",
        b"stream: Permission denied ERROR\x00",
        b"INSTREAM size limit exceeded. ERROR\x00",
        b"stream:  FOUND\x00",
        b"stream: FOUND\x00",
        b"stream: Synthetic FOUND",
        b"stream: Synthetic FOUND\n",
        b"stream: Synthetic\n FOUND\x00",
        b"stream: Synthetic\xff FOUND\x00",
        b"stream: OK\x00garbage",
        b"stream: OK\x00\x00",
        b"stream: OK\x00stream: Synthetic FOUND\x00",
        b"stream: Synthetic FOUND\x00stream: OK\x00",
    ],
)
def test_rejects_unknown_malformed_truncated_or_multiple_replies(reply):
    connection = FakeSocket([reply, b""] if reply else [b""])
    adapter, _ = scanner(connection)
    with pytest.raises(ScannerUnavailable):
        adapter.inspect(content=b"synthetic", filename="synthetic.pdf")
    assert connection.closes == 1


def test_valid_prefix_does_not_hide_trailing_data_in_later_packet():
    connection = FakeSocket([b"stream: OK\x00", b"junk", b""])
    adapter, _ = scanner(connection)
    with pytest.raises(ScannerUnavailable):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert connection.closes == 1


@pytest.mark.parametrize(
    "prefix", [b"stream: OK\x00", b"stream: Synthetic FOUND\x00", b"stream: OK"]
)
def test_timeout_after_apparent_verdict_is_not_a_complete_reply(prefix):
    connection = FakeSocket([prefix, TimeoutError("synthetic EOF timeout")])
    adapter, _ = scanner(connection)
    with pytest.raises(ScannerUnavailable):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert connection.closes == 1


@pytest.mark.parametrize("extra", [1, 5000])
def test_response_cap_is_enforced_with_bounded_reads(extra):
    connection = FakeSocket([b"x" * (MAX_RESPONSE_BYTES + extra), b""])
    adapter, _ = scanner(connection)
    with pytest.raises(ScannerUnavailable, match="exceeds limit"):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert sum(connection.read_sizes) == MAX_RESPONSE_BYTES + 1
    assert connection.closes == 1


def test_response_exactly_at_cap_can_contain_a_complete_detection():
    reply = (
        b"stream: "
        + b"x" * (MAX_RESPONSE_BYTES - len(b"stream:  FOUND\x00"))
        + b" FOUND\x00"
    )
    assert len(reply) == MAX_RESPONSE_BYTES
    connection = FakeSocket([reply, b""])
    adapter, _ = scanner(connection)
    assert adapter.inspect(content=b"synthetic", filename="synthetic.csv") is False
    assert connection.closes == 1


@pytest.mark.parametrize(
    "reply", [None, "stream: OK\x00", bytearray(b"stream: OK\x00")]
)
def test_rejects_non_bytes_transport_responses(reply):
    connection = FakeSocket([reply])
    adapter, _ = scanner(connection)
    with pytest.raises(ScannerUnavailable):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert connection.closes == 1


def test_rejects_transport_that_exceeds_requested_read_size():
    connection = FakeSocket()
    connection.recv = lambda amount: b"x" * (amount + 1)
    adapter, _ = scanner(connection)
    with pytest.raises(ScannerUnavailable):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert connection.closes == 1


@pytest.mark.parametrize(
    "failure", ["settimeout", "connect", "send", "chunk", "terminator", "recv", "close"]
)
def test_closes_and_raises_on_every_transport_failure(failure):
    connection = FakeSocket(failure=failure)
    adapter, _ = scanner(connection)
    with pytest.raises(ScannerUnavailable):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert connection.closes == 1


def test_socket_creation_failure_is_unavailable_not_clean():
    factory = FakeFactory(error=OSError("synthetic creation failure"))
    adapter, _ = scanner(socket_factory=factory)
    with pytest.raises(ScannerUnavailable):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert factory.calls == [(socket.AF_UNIX, socket.SOCK_STREAM)]


def test_total_deadline_stops_slow_trickle_not_just_individual_reads(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(scanner_module.time, "monotonic", lambda: now[0])
    connection = FakeSocket([b"s", b"t", b"r", b"e", b""])
    original_recv = connection.recv

    def slow_recv(amount):
        now[0] += 0.4
        return original_recv(amount)

    connection.recv = slow_recv
    adapter, _ = scanner(connection, timeout=1.0)
    with pytest.raises(ScannerUnavailable, match="deadline"):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert connection.closes == 1
    assert len(connection.read_sizes) == 3
    assert connection.timeouts == sorted(connection.timeouts, reverse=True)


def test_total_deadline_includes_sending_chunks(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(scanner_module.time, "monotonic", lambda: now[0])
    connection = FakeSocket()
    original_send = connection.sendall

    def slow_send(data):
        now[0] += 0.6
        original_send(data)

    connection.sendall = slow_send
    adapter, _ = scanner(connection, timeout=1.0, chunk_size=1)
    with pytest.raises(ScannerUnavailable, match="deadline"):
        adapter.inspect(content=b"synthetic", filename="synthetic.csv")
    assert connection.closes == 1
    assert connection.read_sizes == []


def test_each_inspection_uses_a_new_connection():
    connections = []

    def factory(family, kind):
        assert (family, kind) == (socket.AF_UNIX, socket.SOCK_STREAM)
        connection = FakeSocket()
        connections.append(connection)
        return connection

    adapter, _ = scanner(socket_factory=factory)
    assert adapter.inspect(content=b"one", filename="synthetic.csv") is True
    assert adapter.inspect(content=b"two", filename="synthetic.pdf") is True
    assert len(connections) == 2
    assert all(connection.closes == 1 for connection in connections)
