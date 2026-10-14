import json
from dataclasses import asdict, replace

import pytest

from services.catalog_review.operations.config import (
    ConfigurationError,
    DatabaseConfig,
    OperationsConfig,
    load_json,
)


def configuration(environment="production"):
    suffix = "prod" if environment == "production" else "staging"
    return OperationsConfig(
        environment=environment,
        origin="https://review.spacemusic.io"
        if suffix == "prod"
        else "https://review-staging.spacemusic.io",
        generation="8f402b34-49b3-400c-a800-17c15ff96160",
        release_sha256="a" * 64,
        database=DatabaseConfig(
            "10.2.0.3",
            "review_" + suffix,
            "review_runtime",
            "/run/secrets/postgres-ca",
            "/run/secrets/runtime-pgpass",
        ),
        r2_account_id="a" * 32,
        document_bucket="review-" + suffix + "-documents",
        export_bucket="review-" + suffix + "-exports",
        journal_bucket="review-" + suffix + "-journal",
        independent_backup_bucket="review-" + suffix + "-backup",
        independent_journal_bucket="review-" + suffix + "-journal-mirror",
        google_client_id="123456-abcd.apps.googleusercontent.com",
        workspace_domain="spacemusic.io",
    )


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_valid_configuration_is_deterministic_and_secret_free(environment):
    config = configuration(environment).validate()
    restored = OperationsConfig.from_mapping(asdict(config))
    assert restored == config
    assert restored.fingerprint == config.fingerprint
    assert config.r2_endpoint == "https://" + "a" * 32 + ".eu.r2.cloudflarestorage.com"
    assert config.tem_endpoint.endswith("/regions/fr-par")
    assert config.backup_endpoint == "https://s3.fr-par.scw.cloud"
    kwargs = config.database.connect_kwargs()
    assert kwargs["sslmode"] == "verify-full"
    assert kwargs["connect_timeout"] == 5
    assert "password" not in kwargs and "dsn" not in kwargs


@pytest.mark.parametrize(
    "field,value",
    [
        ("environment", "test"),
        ("origin", "https://review.test"),
        ("origin", "https://review.spacemusic.io/"),
        ("origin", "http://review.spacemusic.io"),
        ("origin", "https://review.spacemusic.io:443"),
        ("origin", "https://spacemusic.io/review"),
        ("generation", "0" * 32),
        ("generation", "bad"),
        ("release_sha256", "0" * 64),
        ("region", "nl-ams"),
        ("zone", "fr-par-2"),
        ("r2_account_id", "0" * 32),
        ("r2_account_id", "a.eu.r2.cloudflarestorage.com.evil.test"),
        ("document_bucket", "review-staging-documents"),
        ("document_bucket", "https://public.example.com"),
        ("export_bucket", "review-prod-documents"),
        ("scanner_socket", "tcp://127.0.0.1:3310"),
        ("google_client_id", "missing"),
        ("workspace_domain", "gmail.com"),
        ("backup_retention_days", 8),
        ("inactivity_days", 91),
        ("planning_sek", 1700.0),
        ("ceiling_sek", 2001),
        ("backup_retention_days", True),
    ],
)
def test_unsafe_config_is_rejected(field, value):
    with pytest.raises(ConfigurationError):
        replace(configuration(), **{field: value}).validate()


@pytest.mark.parametrize(
    "field,value",
    [
        ("host", "127.0.0.1"),
        ("host", "169.254.169.254"),
        ("host", "8.8.8.8"),
        ("host", "::1"),
        ("host", "10.0.0.1,10.0.0.2"),
        ("host", "/tmp/postgres"),
        ("host", "db.example.com"),
        ("dbname", "postgres"),
        ("user", "postgres"),
        ("port", True),
        ("port", 0),
        ("port", 65536),
        ("passfile", "../secret"),
        ("sslrootcert", "/run/secrets/../ca"),
        ("max_connections", 9),
        ("max_connections", True),
        ("checkout_timeout_seconds", float("nan")),
        ("checkout_timeout_seconds", float("inf")),
        ("checkout_timeout_seconds", 0),
    ],
)
def test_database_configuration_is_bounded(field, value):
    with pytest.raises(ConfigurationError):
        replace(configuration().database, **{field: value}).validate()


def test_environment_and_runtime_roles_cannot_cross():
    config = configuration()
    with pytest.raises(ConfigurationError):
        replace(
            config, database=replace(config.database, dbname="review_staging")
        ).validate()
    with pytest.raises(ConfigurationError):
        replace(
            config, database=replace(config.database, user="review_migration")
        ).validate()


@pytest.mark.parametrize(
    "extra",
    ["invitations_enabled", "r2_endpoint", "sslmode", "cookie_domain", "cors_origins"],
)
def test_unknown_security_overrides_are_rejected(extra):
    data = asdict(configuration())
    data[extra] = "unsafe"
    with pytest.raises(ConfigurationError):
        OperationsConfig.from_mapping(data)


def test_json_loader_is_bounded_and_rejects_duplicates(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(asdict(configuration())))
    assert OperationsConfig.from_mapping(load_json(path)) == configuration()
    for text in ('{"origin":1,"origin":2}', "[1]", "{bad", "x" * 65537):
        path.write_text(text)
        with pytest.raises(ConfigurationError):
            load_json(path)


def test_errors_do_not_echo_values():
    with pytest.raises(ConfigurationError) as caught:
        OperationsConfig.from_mapping({"password": "secret-test-value"})
    assert "secret-test-value" not in str(caught.value)
