"""Read-only recipe/Compose checks. Never build, pull, or start a service."""

import ast
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "services/catalog_review/deployment"


def compose(name, *profiles):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose required for read-only configuration validation")
    args = ["docker", "compose", "-f", str(DEPLOYMENT / name)]
    for profile in profiles:
        args.extend(["--profile", profile])
    result = subprocess.run(
        args + ["config", "--no-interpolate", "--format", "json"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("recipe", ["api", "parser", "scanner"])
def test_recipes_have_pinned_bases_and_explicit_existing_source_allowlists(recipe):
    source = DEPLOYMENT / ("Dockerfile." + recipe)
    dockerfile = source.read_text()
    ignored = (
        source.with_suffix(source.suffix + ".dockerignore").read_text().splitlines()
    )
    assert ignored[0] == "**"
    assert re.search(r"^FROM [^\s]+@sha256:[a-f0-9]{64}$", dockerfile, re.MULTILINE)
    assert "USER 100" in dockerfile and "ADD " not in dockerfile
    for line in dockerfile.splitlines():
        if line.startswith("COPY "):
            for path in shlex.split(line)[1:-1]:
                assert not path.startswith((".", "/")) and ".." not in path.split("/")
                assert path.startswith(("services/", "marketing/"))
                assert "!" + path in ignored
                matches = list(ROOT.glob(path))
                assert matches and all(
                    item.is_file() and not item.is_symlink() for item in matches
                )
                assert not any(
                    "fixture" in part or "simulator" in part or part == "tests"
                    for part in Path(path).parts
                )
                if "catalog_review_preview" in path:
                    assert path == "services/catalog_review_preview/ui/review.css"
    if recipe in ("api", "parser"):
        assert "--no-index --find-links=/wheels" in dockerfile
        assert "--require-hashes --only-binary=:all:" in dockerfile
        assert "from=wheels,target=/wheels" in dockerfile


def api_image_files():
    """Map explicit COPY inputs to their installed /app-relative resource paths."""
    packaged = {}
    for line in (DEPLOYMENT / "Dockerfile.api").read_text().splitlines():
        if not line.startswith("COPY "):
            continue
        _, *sources, destination = shlex.split(line)
        for source in sources:
            for path in ROOT.glob(source):
                target = PurePosixPath(destination)
                if destination.endswith("/"):
                    target /= path.name
                relative = target.relative_to("/app").as_posix()
                assert relative not in packaged, relative
                packaged[relative] = path
    return packaged


def test_every_runtime_asset_and_production_variant_is_installed_at_its_read_path():
    source = ROOT / "services/catalog_review/http.py"
    tree = ast.parse(source.read_text())
    assets = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "ASSETS"
            for target in node.targets
        )
    )
    paths = {filename for filename, _ in assets.values()}
    paths.update(
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "filename"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )
    assert "services/catalog_review_ui/index.production.html" in paths
    packaged = api_image_files()
    for path in sorted(paths):
        assert packaged.get(path) == ROOT / path, (
            f"Runtime resource not installed: {path}"
        )
        assert packaged[path].is_file()


def test_api_packages_glue_modules_and_local_import_closure_without_import_side_effects():
    packaged = api_image_files()
    for name in (
        "encryption",
        "runtime",
        "jobs",
        "operations/bootstrap",
        "staff/erasure",
    ):
        assert f"services/catalog_review/{name}.py" in packaged

    def require_module(module):
        if not module.startswith("services.") and module != "services":
            return
        path = module.replace(".", "/")
        candidates = (path + ".py", path + "/__init__.py")
        present = next(
            (candidate for candidate in candidates if (ROOT / candidate).is_file()),
            None,
        )
        assert present is not None, f"Unknown repository import: {module}"
        assert packaged.get(present) == ROOT / present, (
            f"Unpackaged repository import: {module}"
        )
        for parent in PurePosixPath(present).parents:
            initializer = (parent / "__init__.py").as_posix()
            if (ROOT / initializer).is_file():
                assert initializer in packaged

    for relative, source in packaged.items():
        if source.suffix != ".py":
            continue
        package = PurePosixPath(relative).parts[:-1]
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    require_module(alias.name)
            elif isinstance(node, ast.ImportFrom):
                prefix = package[: len(package) - node.level + 1] if node.level else ()
                module = ".".join(
                    (*prefix, *((node.module or "").split(".") if node.module else ()))
                )
                require_module(module)
                for alias in node.names:
                    imported = module + "." + alias.name
                    path = ROOT / imported.replace(".", "/")
                    if (
                        path.with_suffix(".py").is_file()
                        or (path / "__init__.py").is_file()
                    ):
                        require_module(imported)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # The allowlisted bootstrap selection is a literal module:symbol,
                # not a regular import statement.
                module, separator, symbol = node.value.partition(":")
                if (
                    separator
                    and module.startswith("services.")
                    and symbol.isidentifier()
                ):
                    require_module(module)


def test_api_packages_all_default_pilot_sql_sources():
    packaged = api_image_files()
    for path in (
        "schema.sql",
        "grants.sql",
        "intake-schema.sql",
        "erasure-grants.sql",
        "staff/schema.sql",
        "staff/grants.sql",
        "staff/erasure-grants.sql",
    ):
        relative = "services/catalog_review/" + path
        assert packaged.get(relative) == ROOT / relative


def pins(name):
    result = {}
    for line in (DEPLOYMENT / name).read_text().splitlines():
        if line and not line.startswith("#"):
            match = re.fullmatch(
                r"([A-Za-z0-9_-]+)==([^\s]+)(?: --hash=sha256:[a-f0-9]{64})+", line
            )
            assert match, line
            assert match[1].lower() not in result
            result[match[1].lower().replace("_", "-")] = match[2]
    return result


def test_dependency_locks_match_staff_and_isolated_parser_contract():
    api = pins("requirements-api.lock")
    parser = pins("requirements-parser.lock")
    assert api["boto3"] == api["botocore"]
    assert not set(api) & {"pytest", "pypdf", "openpyxl"}
    source = ast.parse((ROOT / "services/catalog_review/parser_process.py").read_text())
    value = next(
        ast.literal_eval(node.value)
        for node in source.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "PARSER_DEPENDENCIES"
            for t in node.targets
        )
    )
    assert parser == {
        name.lower().replace("_", "-"): version
        for name, version in (item.split("==") for item in value)
    }
    for line in (
        (ROOT / "services/catalog_review/staff/requirements.txt")
        .read_text()
        .splitlines()
    ):
        match = re.match(r"([^=\s]+)==([^\s]+)", line)
        if match:
            assert api[match[1].split("[", 1)[0].lower().replace("_", "-")] == match[2]


def test_worker_is_not_the_networkless_parser_and_updater_cannot_read_documents():
    services = compose(
        "compose.worker.yaml", "approved-worker", "approved-signature-updates"
    )["services"]
    parser = services["parser"]
    scanner = services["clamav"]
    worker = services["worker"]
    updater = services["signature-updater"]
    for service in (parser, scanner):
        assert service["network_mode"] == "none"
        assert (
            not service.get("networks")
            and not service.get("ports")
            and not service.get("secrets")
        )
        assert service["read_only"] and service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert not service["user"].startswith("0:")
    assert [(v["type"], v["source"], v["target"]) for v in parser["volumes"]] == [
        ("volume", "parser_socket", "/run/parser")
    ]
    assert set(worker["networks"]) == {"worker_egress"}
    assert set(updater["networks"]) == {"signature_egress"}
    assert {v["source"] for v in updater["volumes"]} == {"signatures"}
    assert not updater.get("secrets")
    assert worker["depends_on"]["clamav"]["condition"] == "service_healthy"
    assert "Blocked: reviewed worker integration required" in " ".join(
        worker["command"]
    )
    assert all(v["read_only"] for v in worker["volumes"])
    assert scanner["mem_limit"] == "4g" and parser["mem_limit"] == "768m"
    for service in services.values():
        assert (
            service["platform"] == "linux/amd64" and service["pull_policy"] == "never"
        )
        assert len(service["tmpfs"]) == 1 and service["tmpfs"][0].startswith(
            "/tmp:size="
        )


def test_api_has_no_repo_mount_or_public_container_port_and_default_factory_is_closed():
    api = compose("compose.api.yaml", "approved-api")["services"]["api"]
    assert api["network_mode"] == "host" and not api.get("ports")
    assert api["build"]["network"] == "none"
    assert "wheels" in api["build"]["additional_contexts"]
    assert api["profiles"] == ["approved-api"]
    for volume in api["volumes"]:
        assert volume["target"] in (
            "/run/config/operations.json",
            "/run/config/launch.json",
        )
        assert volume["read_only"] and volume["bind"]["create_host_path"] is False
    dockerfile = (DEPLOYMENT / "Dockerfile.api").read_text()
    assert '"services.catalog_review.operations.bootstrap:create_app"' in dockerfile
    assert '"--host", "127.0.0.1"' in dockerfile
    assert '"--forwarded-allow-ips", "127.0.0.1"' in dockerfile
    assert "COPY services/catalog_review/intake-schema.sql" in dockerfile
    assert "COPY services/catalog_review/staff/schema.sql" in dockerfile


def test_clamav_is_unix_only_bounded_and_does_not_run_freshclam_implicitly():
    clamd = (DEPLOYMENT / "clamd.conf").read_text()
    assert "TCPSocket" not in clamd
    assert "LocalSocket /run/clamav/clamd.sock" in clamd
    assert "StreamMaxLength 25M" in clamd and "MaxThreads 1" in clamd
    assert "ConcurrentDatabaseReload no" in clamd
    assert 'ENTRYPOINT ["clamd"]' in (DEPLOYMENT / "Dockerfile.scanner").read_text()
    assert "NotifyClamd" not in (DEPLOYMENT / "freshclam.conf").read_text()
