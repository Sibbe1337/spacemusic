"""Read-only preflight/plan by default; migrations require an explicit command."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from .config import OperationsConfig, load_json
from .migrations import load_pilot_plan, plan_digest, run_migrations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "migration-plan", "migrate"))
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--source-root", default=str(Path(__file__).resolve().parents[1])
    )
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--migration-passfile")
    parser.add_argument(
        "--staff-runtime-role",
        choices=("review_runtime", "catalog_staff_runtime"),
        default="review_runtime",
    )
    parser.add_argument("--include-providers", action="store_true")
    args = parser.parse_args()
    config = OperationsConfig.from_mapping(load_json(args.config))
    if args.command == "check":
        print(
            json.dumps(
                {"config_sha256": config.fingerprint, "invitations_allowed": False}
            )
        )
        return
    migrations, grants = load_pilot_plan(
        args.source_root,
        staff_runtime_role=args.staff_runtime_role,
        include_providers=args.include_providers,
    )
    if args.command == "migration-plan":
        print(
            json.dumps(
                {
                    "plan_sha256": plan_digest(migrations, grants),
                    "migrations": [m.name for m in migrations],
                }
            )
        )
        return
    if not args.expected_plan_sha256 or not args.migration_passfile:
        parser.error(
            "migrate requires an approved plan digest and a separate mounted migration passfile"
        )
    database = replace(
        config.database, user="review_migration", passfile=args.migration_passfile
    )
    count = run_migrations(
        database, migrations, grants, expected_plan_sha256=args.expected_plan_sha256
    )
    print(json.dumps({"applied": count, "invitations_allowed": False}))


if __name__ == "__main__":
    main()
