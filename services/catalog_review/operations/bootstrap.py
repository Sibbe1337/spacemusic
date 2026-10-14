"""Opt-in, allowlisted composition root. No secret discovery or SDK creation.

The coordinator implements runtime.build_dependencies, reads explicitly mounted
secrets there, and returns RuntimeDependencies. Arbitrary modules, file paths,
ASGI apps and boolean health dictionaries are never accepted from environment.
"""

import importlib
import os
from dataclasses import dataclass

from .asgi import GuardedApplication
from .config import OperationsConfig, load_json
from .gates import LaunchGate, LaunchManifest
from .runtime import build_runtime

FACTORY = "services.catalog_review.runtime:build_dependencies"


@dataclass(frozen=True)
class RuntimeDependencies:
    adapters: object
    app_builder: object
    restore_provider: object


def assemble(config, manifest, selection, *, import_module=importlib.import_module):
    """Trusted test seam is callable-only; production always uses importlib."""
    closed = GuardedApplication(config, LaunchGate(config, manifest))
    if selection != FACTORY:
        closed.startup_blockers = ("reviewed_bootstrap_not_selected",)
        return closed
    try:
        module = import_module("services.catalog_review.runtime")
        factory = getattr(module, "build_dependencies", None)
        if not callable(factory):
            closed.startup_blockers = ("reviewed_bootstrap_missing",)
            return closed
        dependencies = factory(config=config)
        if not isinstance(dependencies, RuntimeDependencies):
            closed.startup_blockers = ("invalid_bootstrap_contract",)
            return closed
        return build_runtime(
            config,
            adapters=dependencies.adapters,
            app_builder=dependencies.app_builder,
            restore_provider=dependencies.restore_provider,
            manifest=manifest,
        )
    except Exception:
        # Never expose mounted credentials or vendor exception text via health.
        closed.startup_blockers = ("reviewed_bootstrap_failed",)
        return closed


def create_app():
    config = OperationsConfig.from_mapping(
        load_json(os.environ["REVIEW_OPERATIONS_CONFIG"])
    )
    path = os.environ.get("REVIEW_LAUNCH_MANIFEST")
    manifest = LaunchManifest.from_mapping(load_json(path)) if path else None
    return assemble(config, manifest, os.environ.get("REVIEW_RUNTIME_FACTORY"))
