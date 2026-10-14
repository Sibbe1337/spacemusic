"""Hash -> private AV -> isolated content validation; not wired into workers yet.

Coordinator contract: call ``validate_document`` on the exact immutable blob and
trusted stored size/SHA-256. Only True may become accepted_for_review. False is a
rejection; ValidationUnavailable MUST leave the document quarantined for bounded
retry/operator action. Never translate an exception into a clean verdict.

Production workers inject ClamAVScanner and parser_ipc.UnixSocketDocumentParser,
not test stubs. SandboxedDocumentParser runs ONLY in the separate parser service,
never with network_isolated=True in the DB/R2-connected worker container.
The parser requires Linux and a deployment-enforced network-denied container
(including metadata endpoints, DNS and local sockets). ``network_isolated`` is
an operator attestation, NOT a Python network sandbox. Use a dedicated unprivileged
container, no secrets, read-only root, bounded tmpfs/pids/concurrency and seccomp.
RLIMITs alone are not a containment boundary for a compromised interpreter.

No input is uploaded, rendered, evaluated, extracted to disk, or returned. A pass
does not sanitize a document for HTML rendering or later spreadsheet exports.
The intentionally narrow policy rejects features rather than silently removing
them. Exact third-party pins are exposed as PARSER_DEPENDENCIES; missing or other
versions quarantine that format. Dependency upgrades require corpus retesting.
"""

import hashlib
import hmac
import os
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Protocol

from .parser_process import (
    MAX_DOCUMENT_BYTES,
    PARSER_DEPENDENCIES,
    ParserLimits,
    Unavailable,
    require_network_sandbox,
)

__all__ = [
    "DocumentInspector",
    "MAX_DOCUMENT_BYTES",
    "PARSER_DEPENDENCIES",
    "ParserLimits",
    "SandboxedDocumentParser",
    "ValidationUnavailable",
    "validate_document",
]


class ValidationUnavailable(RuntimeError):
    """No complete trustworthy verdict. Retain quarantine, never mark clean."""


class DocumentInspector(Protocol):
    def inspect(self, *, content: bytes, filename: str) -> bool:
        """Return an exact bool, or raise if inspection is unavailable."""
        ...


def validate_document(
    *,
    content: bytes,
    filename: str,
    expected_sha256: str,
    expected_size: int,
    scanner: DocumentInspector,
    parser: DocumentInspector,
) -> bool:
    """Validate stored integrity and require BOTH explicit AV and parser passes.

    No DB state is changed here. The coordinator must bind its completion to the same
    stored SHA-256/job lease, as complete_scan already does. Injected implementations
    are trusted code; an AV-only scanner must never be passed as ``parser``.
    """
    if (
        type(content) is not bytes
        or not 0 < len(content) <= MAX_DOCUMENT_BYTES
        or type(expected_size) is not int
        or len(content) != expected_size
        or not isinstance(expected_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), expected_sha256)
    ):
        return False
    for inspector in (scanner, parser):
        try:
            verdict = inspector.inspect(content=content, filename=filename)
        except Exception:
            # Do not propagate library errors containing document text/filenames.
            raise ValidationUnavailable("Document validation unavailable") from None
        if type(verdict) is not bool:
            raise ValidationUnavailable("Invalid validation verdict")
        if not verdict:
            return False
    return True


def _document_kind(content, filename):
    if (
        type(content) is not bytes
        or not 0 < len(content) <= MAX_DOCUMENT_BYTES
        or not isinstance(filename, str)
        or not 5 <= len(filename) <= 180
        or any(ord(c) < 32 or ord(c) == 127 or c in '/\\:"' for c in filename)
    ):
        return None
    extension = filename.rsplit(".", 1)[-1].lower()
    return extension if extension in {"csv", "pdf", "xlsx"} else None


class SandboxedDocumentParser:
    """Fresh isolated Python subprocess for every document; fail closed by default.

    CPU/address space/FD/core/file-size limits and an alarm are installed inside
    the exec'd child before importing document libraries or reading any input.
    The parent separately bounds wall time and output, and kills the process group
    on every exit path. No preexec_fn (unsafe in threaded workers) or shell is used.
    """

    def __init__(self, *, network_isolated=False, limits=None):
        if type(network_isolated) is not bool:
            raise ValueError("network_isolated must be an operator boolean")
        self.network_isolated = network_isolated
        self.limits = limits if limits is not None else ParserLimits()
        if type(self.limits) is not ParserLimits:
            raise ValueError("Expected ParserLimits")

    def inspect(self, *, content, filename):
        kind = _document_kind(content, filename)
        if kind is None:
            return False
        if not self.network_isolated or not sys.platform.startswith("linux"):
            raise ValidationUnavailable("Linux/network sandbox unavailable")
        try:
            require_network_sandbox()
        except Unavailable:
            raise ValidationUnavailable(
                "Parser requires a dedicated isolated service"
            ) from None
        deadline = time.monotonic() + self.limits.wall_seconds
        process = None
        try:
            # An unnamed, private snapshot avoids path/TOCTOU attacks and gives the
            # child only this file descriptor, not object-store credentials.
            with tempfile.TemporaryFile() as source:
                source.write(content)
                source.seek(0)
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        str(Path(__file__).with_name("parser_process.py").resolve()),
                        kind,
                        self.limits.to_json(),
                    ],
                    stdin=source,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    start_new_session=True,
                    cwd="/",
                    env={
                        "OPENPYXL_LXML": "False",
                        "OPENPYXL_DEFUSEDXML": "True",
                        "OPENPYXL_NUMPY": "False",
                        "OPENBLAS_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "1",
                        "LC_ALL": "C.UTF-8",
                    },
                )
                response = self._read_response(process, deadline)
            if process.returncode != 0:
                raise ValidationUnavailable("Parser failed or exceeded resource limits")
            if response == b"PASS\n":
                return True
            if response == b"REJECT\n":
                return False
            raise ValidationUnavailable("Parser unavailable or invalid response")
        except (OSError, subprocess.SubprocessError):
            raise ValidationUnavailable("Parser process unavailable") from None
        finally:
            if process is not None:
                # Kill descendants as well, even if the main process already died.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                finally:
                    process.wait()
                    process.stdout.close()

    @staticmethod
    def _read_response(process, deadline):
        response = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise ValidationUnavailable("Parser wall-clock limit exceeded")
                chunk = os.read(process.stdout.fileno(), 65 - len(response))
                if not chunk:
                    break
                response.extend(chunk)
                if len(response) > 64:
                    raise ValidationUnavailable("Parser response exceeds limit")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValidationUnavailable("Parser wall-clock limit exceeded")
        process.wait(timeout=remaining)
        return bytes(response)
