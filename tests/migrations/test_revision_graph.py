from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2]


def revision_values(directory: Path) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        revision = None
        down_revision = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                value = node.value
            else:
                continue
            if not isinstance(target, ast.Name) or target.id not in {"revision", "down_revision"}:
                continue
            if isinstance(value, ast.Constant):
                if target.id == "revision":
                    revision = value.value
                else:
                    down_revision = value.value
        if revision:
            values[revision] = down_revision
    return values


def test_offers_migrations_form_a_single_chain():
    revisions = revision_values(ROOT / "services/offers/migrations/versions")

    assert revisions["0001_create_tables"] is None
    assert revisions["0002_add_offer_valuation_fields"] == "0001_create_tables"
    assert revisions["d198261eb7a4"] == "0002_add_offer_valuation_fields"


def test_payout_migrations_preserve_legacy_table_then_add_identity():
    revisions = revision_values(ROOT / "services/payouts/migrations/versions")

    assert revisions["6364fcaeceb9"] is None
    assert revisions["0002_add_payout_identity_fields"] == "6364fcaeceb9"
