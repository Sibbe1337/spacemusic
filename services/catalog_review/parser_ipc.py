"""Bounded Unix-socket transport to a dedicated network-denied parser container.

Worker: inject UnixSocketDocumentParser(socket_path=...) into validate_document
after ClamAV, NOT SandboxedDocumentParser(network_isolated=True). The worker may
retain its DB/R2 networking; the parser service must be a DIFFERENT container.

Service entry point (application package installed/on its trusted module path)::

    python -m services.catalog_review.parser_ipc --socket-path /run/parser/validate.sock

Deployment requirements: Linux/Python 3.11+, exact PARSER_DEPENDENCIES, Docker
network_mode: none, non-root UID, cap_drop: [ALL], no-new-privileges, read-only
root, bounded private /tmp tmpfs, pids/memory/concurrency limits, no DB/R2 secrets
or sockets. Share ONLY a dedicated protected Unix-socket directory with the worker
(matching group, non-world-writable). Do not expose TCP, Docker sockets or host
networking. No active non-loopback interfaces, capabilities and no_new_privs are checked
at startup AND per request; these checks do not replace the deployment boundary.

One request per connection, sequential service, bounded backlog, total deadlines,
fixed binary framing and exact SHA-256-bound replies. No JSON/pickle/content logs,
filenames, paths or executable flags cross the trust boundary. Missing/crashed/
timed-out service or any malformed response means ValidationUnavailable.
"""

import argparse
import hashlib
import hmac
import math
import os
import signal
import socket
import stat
import struct
import time
from contextlib import closing
from pathlib import Path, PurePosixPath

from . import parser_process as isolation
from .document_validation import (
    MAX_DOCUMENT_BYTES,
    SandboxedDocumentParser,
    ValidationUnavailable,
    _document_kind,
)

_MAGIC = b"SPCDOC1\x00"
_REQUEST = struct.Struct("!8sBI32s")
_RESPONSE = struct.Struct("!8sB32s")
_KINDS = {"csv": 1, "pdf": 2, "xlsx": 3}
_PASS, _REJECT, _UNAVAILABLE = 1, 2, 3
_CHUNK = 64 * 1024
_TIMEOUT = 20.0


def _socket_path(value):
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value.startswith("//")
        or "\x00" in value
        or len(value.encode()) > 103
        or str(PurePosixPath(value)) != value
        or ".." in PurePosixPath(value).parts
        or value == "/"
    ):
        raise ValueError("Expected a canonical absolute Unix socket path")
    return value


def _remaining(connection, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValidationUnavailable("Parser IPC deadline exceeded")
    connection.settimeout(remaining)


def _read_exact(connection, size, deadline):
    result = bytearray()
    while len(result) < size:
        _remaining(connection, deadline)
        chunk = connection.recv(min(_CHUNK, size - len(result)))
        if not chunk:
            raise ValidationUnavailable("Truncated parser IPC frame")
        result.extend(chunk)
    return bytes(result)


def _expect_eof(connection, deadline):
    _remaining(connection, deadline)
    if connection.recv(1):
        raise ValidationUnavailable("Trailing parser IPC frame")


class UnixSocketDocumentParser:
    """Network-enabled worker adapter; makes AF_UNIX calls only, never TCP/DNS."""

    def __init__(self, *, socket_path, timeout=_TIMEOUT):
        self.socket_path = _socket_path(socket_path)
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 60
        ):
            raise ValueError("Timeout must be finite and between 0 and 60 seconds")
        self.timeout = timeout

    def inspect(self, *, content, filename):
        kind = _document_kind(content, filename)
        if kind is None:
            return False
        deadline = time.monotonic() + self.timeout
        digest = hashlib.sha256(content).digest()
        try:
            with closing(
                socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            ) as connection:
                _remaining(connection, deadline)
                connection.connect(self.socket_path)
                _remaining(connection, deadline)
                connection.sendall(
                    _REQUEST.pack(_MAGIC, _KINDS[kind], len(content), digest)
                )
                for offset in range(0, len(content), _CHUNK):
                    _remaining(connection, deadline)
                    connection.sendall(content[offset : offset + _CHUNK])
                connection.shutdown(socket.SHUT_WR)
                response = _read_exact(connection, _RESPONSE.size, deadline)
                _expect_eof(connection, deadline)
            magic, verdict, received_digest = _RESPONSE.unpack(response)
            if magic != _MAGIC or not hmac.compare_digest(received_digest, digest):
                raise ValidationUnavailable("Invalid parser IPC binding")
            if verdict == _PASS:
                return True
            if verdict == _REJECT:
                return False
            raise ValidationUnavailable("Parser service unavailable")
        except OSError:
            raise ValidationUnavailable("Parser IPC unavailable") from None


def _verify_service_sandbox():
    try:
        isolation.require_network_sandbox()
    except isolation.Unavailable:
        raise ValidationUnavailable("Dedicated parser isolation unverified") from None


def _serve_connection(connection, parser, *, timeout=_TIMEOUT):
    deadline = time.monotonic() + timeout
    magic, kind, size, digest = _REQUEST.unpack(
        _read_exact(connection, _REQUEST.size, deadline)
    )
    if (
        magic != _MAGIC
        or kind not in _KINDS.values()
        or not 0 < size <= MAX_DOCUMENT_BYTES
    ):
        raise ValidationUnavailable("Invalid parser IPC request")
    content = _read_exact(connection, size, deadline)
    _expect_eof(connection, deadline)
    if not hmac.compare_digest(hashlib.sha256(content).digest(), digest):
        verdict = _REJECT
    else:
        extension = next(name for name, code in _KINDS.items() if code == kind)
        try:
            result = parser.inspect(content=content, filename="document." + extension)
            verdict = (
                _PASS
                if result is True
                else _REJECT
                if result is False
                else _UNAVAILABLE
            )
        except Exception:
            verdict = _UNAVAILABLE
    _remaining(connection, deadline)
    connection.sendall(_RESPONSE.pack(_MAGIC, verdict, digest))


def serve_forever(socket_path):
    """Production entry point: no injected parser or network-bypass flag."""
    socket_path = _socket_path(socket_path)
    _verify_service_sandbox()
    parent = Path(socket_path).parent.stat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_mode & stat.S_IWOTH:
        raise ValidationUnavailable("Private parser socket directory required")
    parser = SandboxedDocumentParser(network_isolated=True)
    bound_identity = None
    try:
        with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as listener:
            # Never unlink an existing socket: that could replace a live service.
            listener.bind(socket_path)
            bound = Path(socket_path).stat()
            bound_identity = (bound.st_dev, bound.st_ino)
            os.chmod(socket_path, 0o660)
            listener.listen(8)
            while True:
                connection, _ = listener.accept()
                with closing(connection):
                    try:
                        _verify_service_sandbox()
                        _serve_connection(connection, parser)
                    except Exception:
                        # Closing the connection without a valid reply quarantines.
                        # No attacker-controlled diagnostics are retained.
                        continue
    finally:
        if bound_identity is not None:
            try:
                current = Path(socket_path).stat()
                if (current.st_dev, current.st_ino) == bound_identity:
                    Path(socket_path).unlink()
            except FileNotFoundError:
                pass


def main():
    arguments = argparse.ArgumentParser(
        description="Network-denied document parser service"
    )
    arguments.add_argument("--socket-path", required=True)
    args = arguments.parse_args()

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        serve_forever(args.socket_path)
    except KeyboardInterrupt:
        return
    except Exception:
        raise SystemExit("Parser service startup/runtime unavailable") from None


if __name__ == "__main__":
    main()
