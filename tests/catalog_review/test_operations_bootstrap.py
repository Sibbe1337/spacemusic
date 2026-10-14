from types import SimpleNamespace

import pytest
from test_operations_config import configuration
from test_operations_gates import request

from services.catalog_review.operations.bootstrap import (
    FACTORY,
    RuntimeDependencies,
    assemble,
)


@pytest.mark.parametrize(
    "selection", [None, "", "os:system", "/run/runtime.py", FACTORY + " "]
)
def test_bootstrap_never_imports_unselected_or_arbitrary_factory(selection):
    def forbidden(_):
        raise AssertionError("unapproved import")

    app = assemble(configuration(), None, selection, import_module=forbidden)
    assert app.startup_blockers == ("reviewed_bootstrap_not_selected",)
    assert request(app)[0] == 503


def test_selected_missing_factory_stays_closed():
    app = assemble(
        configuration(), None, FACTORY, import_module=lambda _: SimpleNamespace()
    )
    assert app.startup_blockers == ("reviewed_bootstrap_missing",)


def test_factory_cannot_return_unguarded_asgi_or_green_dictionary():
    for value in (lambda *_: None, {"healthy": True}, None):
        app = assemble(
            configuration(),
            None,
            FACTORY,
            import_module=lambda _: SimpleNamespace(
                build_dependencies=lambda **__: value
            ),
        )
        assert app.startup_blockers == ("invalid_bootstrap_contract",)


def test_factory_dependencies_still_pass_essential_adapter_validation():
    def forbidden(**_):
        raise AssertionError("incomplete builder called")

    app = assemble(
        configuration(),
        None,
        FACTORY,
        import_module=lambda _: SimpleNamespace(
            build_dependencies=lambda **__: RuntimeDependencies(
                {}, forbidden, lambda: None
            )
        ),
    )
    assert "adapter_database" in app.startup_blockers
    assert request(app)[0] == 503


def test_factory_exception_never_leaks_secrets():
    def broken(**_):
        raise ValueError("secret=synthetic-not-real")

    app = assemble(
        configuration(),
        None,
        FACTORY,
        import_module=lambda _: SimpleNamespace(build_dependencies=broken),
    )
    assert app.startup_blockers == ("reviewed_bootstrap_failed",)
    assert b"secret" not in request(app)[1]
