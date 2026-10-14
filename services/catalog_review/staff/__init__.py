"""Isolated staff identity. HTTP and real transport require explicit wiring."""

from .admin import StaffAdministration
from .config import StaffError, StaffSettings
from .erasure import StaffErasureParticipant
from .oidc import GoogleOIDCVerifier, JwksSnapshot
from .repository import StaffRepository
from .service import StaffService
from .transport import GoogleOIDCTransport

__all__ = [
    "GoogleOIDCVerifier",
    "GoogleOIDCTransport",
    "JwksSnapshot",
    "StaffAdministration",
    "StaffError",
    "StaffErasureParticipant",
    "StaffRepository",
    "StaffService",
    "StaffSettings",
]
