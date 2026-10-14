"""SQL rendering only. Execution requires separately approved operator tooling."""

import re
from pathlib import Path

from psycopg2 import sql


def runtime_grants_sql(role):
    """Render the exact staff grants for review_runtime or a dedicated runtime.

    Does not create roles, SET ROLE, connect, execute SQL, or grant owner access.
    Apply with a migration administrator only after operator approval.
    """
    if not isinstance(role, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise ValueError("Explicit unquoted runtime role name required")
    template = (
        Path(__file__)
        .with_name("grants.sql")
        .read_text()
        .replace("catalog_staff_runtime", "{runtime_role}")
    )
    return sql.SQL(template).format(runtime_role=sql.Identifier(role))


def erasure_grants_sql(role):
    """Render case-assignment DELETE privileges for a separate erasure worker."""
    if not isinstance(role, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise ValueError("Explicit unquoted erasure role name required")
    template = (
        Path(__file__)
        .with_name("erasure-grants.sql")
        .read_text()
        .replace("catalog_staff_erasure", "{erasure_role}")
    )
    return sql.SQL(template).format(erasure_role=sql.Identifier(role))
