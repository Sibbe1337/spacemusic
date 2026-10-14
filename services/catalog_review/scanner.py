"""Optional ClamAV AV-only adapter, not document/parser security or upload approval.

No CSV/PDF/XLSX structural preflight is claimed. A clean AV verdict does not rule
out active content, formula injection, parser exploits, archive bombs or skipped
content. Deployment must separately enforce sandboxed parser/resource limits,
fresh signatures and clamd limits/alert policy (including encrypted archives).
No daemon is installed, started, configured or contacted at import/construction.

INSTREAM framing and NUL-terminated replies:
https://github.com/Cisco-Talos/clamav/blob/main/docs/man/clamd.8.in
"""

import math
import re
import socket
import struct
import time
from contextlib import closing
from pathlib import PurePosixPath

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_CHUNK_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 4096
_FOUND = re.compile(rb"stream: [!-~](?:[ -~]*[!-~])? FOUND\x00")


class ScannerUnavailable(RuntimeError):
    """No trustworthy complete AV verdict; keep the document quarantined."""


class ClamAVScanner:
    """One INSTREAM command per injected AF_UNIX socket, never TCP or DNS.

    socket_factory must accept (socket.AF_UNIX, socket.SOCK_STREAM) and return a
    fresh socket-compatible object. The configured absolute Unix socket path is a
    trusted operator setting, never a document name. Its directory/permissions and
    daemon identity must be secured separately. The factory itself must not block.
    The deadline bounds connect, all sends and the entire response, not each chunk.
    """

    def __init__(
        self, *, socket_factory, socket_path, timeout=10.0, chunk_size=MAX_CHUNK_BYTES
    ):
        if not callable(socket_factory):
            raise ValueError("An injected socket factory is required")
        if (
            not isinstance(socket_path, str)
            or not socket_path.startswith("/")
            or socket_path.startswith("//")
            or "\x00" in socket_path
            or len(socket_path.encode("utf-8")) > 103
            or str(PurePosixPath(socket_path)) != socket_path
            or ".." in PurePosixPath(socket_path).parts
            or socket_path == "/"
        ):
            raise ValueError("Expected a canonical absolute Unix socket path")
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 60
        ):
            raise ValueError("Timeout must be finite and between 0 and 60 seconds")
        if type(chunk_size) is not int or not 1 <= chunk_size <= MAX_CHUNK_BYTES:
            raise ValueError("Stream chunks must be between 1 and 65536 bytes")
        self._socket_factory = socket_factory
        self._socket_path = socket_path
        self._timeout = timeout
        self._chunk_size = chunk_size

    @staticmethod
    def _set_remaining_timeout(connection, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ScannerUnavailable("Scanner deadline exceeded")
        connection.settimeout(remaining)

    def inspect(self, *, content, filename):
        """True for exact OK, False for FOUND, exception for everything else.

        filename is interface compatibility only; never open it or send it to clamd.
        Even a NUL-terminated verdict must be followed by EOF on this non-session
        connection, preventing extra/trailing responses from being treated as clean.
        """
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_DOCUMENT_BYTES:
            raise ValueError("Expected 1 to 25 MiB of document bytes")
        deadline = time.monotonic() + self._timeout
        try:
            with closing(
                self._socket_factory(socket.AF_UNIX, socket.SOCK_STREAM)
            ) as connection:
                self._set_remaining_timeout(connection, deadline)
                connection.connect(self._socket_path)
                self._set_remaining_timeout(connection, deadline)
                connection.sendall(b"zINSTREAM\x00")
                for offset in range(0, len(content), self._chunk_size):
                    chunk = content[offset : offset + self._chunk_size]
                    self._set_remaining_timeout(connection, deadline)
                    connection.sendall(struct.pack("!I", len(chunk)) + chunk)
                self._set_remaining_timeout(connection, deadline)
                connection.sendall(b"\x00\x00\x00\x00")
                response = bytearray()
                while True:
                    self._set_remaining_timeout(connection, deadline)
                    amount = min(1024, MAX_RESPONSE_BYTES - len(response) + 1)
                    chunk = connection.recv(amount)
                    if not isinstance(chunk, bytes) or len(chunk) > amount:
                        raise ScannerUnavailable("Invalid scanner response chunk")
                    if not chunk:
                        break
                    response.extend(chunk)
                    if len(response) > MAX_RESPONSE_BYTES:
                        raise ScannerUnavailable("Scanner response exceeds limit")
                    if b"\x00" in response[:-1]:
                        raise ScannerUnavailable("Trailing scanner response data")
                self._set_remaining_timeout(connection, deadline)
                if response == b"stream: OK\x00":
                    return True
                if _FOUND.fullmatch(response):
                    return False
                raise ScannerUnavailable("Unrecognized or incomplete scanner verdict")
        except OSError as exc:
            raise ScannerUnavailable("Scanner transport unavailable") from exc
