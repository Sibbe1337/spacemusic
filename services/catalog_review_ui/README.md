# Catalog Review interface

Customer workspace, staff intake/identity screens and reviewer/dealflow views for
the [Catalog Review backend](../catalog_review/README.md). This is not a separate
React app: versioned plain JavaScript, HTML, CSS and local font assets are served
through the backend's explicit asset registry and deployment allowlist.

Do not use a generic static server as a substitute for authenticated portal
behavior. API requests depend on same-origin sessions, CSRF and server-side roles.
Do not put demo role switches or credentials in these production-shared assets.

## Work locally

- [Connected dealflow demo](../../experiments/dealflow-preview/README.md):
  disposable database and fictional case, loopback only.
- [Hosted visual preview](../catalog_review_cloud_preview/README.md):
  five read-only fictional states, not a customer pilot.
- [Pilot verification](../catalog_review/PILOT-VERIFICATION.md): environment,
  optional real-browser checks and production limitations.

```sh
node --test services/catalog_review_ui/*.test.mjs
```

Run from the repository root. Browser-specific tests have explicit opt-in gates;
a default test run can skip them. Public website Apply is a different surface
owned by the [marketing release](../../marketing/RELEASE.md).
