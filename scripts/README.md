# Script index

Run from the repository root. Dated builders are layered release tools, not a
generic website application build. Keep old inputs until the dependent manifests
and regression checks have been deliberately migrated.

## Common checks

| Command | Effect |
| --- | --- |
| `npm run project:check` | Local entry-point and recorded release-artifact checks; no network or edits |
| `npm run clean:check` | Dry-run cache inventory; lists refusals for unexpected/tracked contents |
| `npm run clean:caches` | Removes only validated disposable caches; excludes snapshots and private data |
| `npm run test:maintenance` | Tests safety rules, entry-point documentation and ignore behavior |
| `npm run test:funnel` | Calculator, attribution and Typeform tests with simulated responses |
| `npm run test:portal:ui` | Portal interface tests, with existing optional browser gates |
| `npm run preview:dealflow` | Loopback-only synthetic portal demo; requires the portal test environment |

## Website preservation

The authoritative recorded release is [marketing/RELEASE.md](../marketing/RELEASE.md).
These tests require the existing dependencies installed for `services/seller_ui`
and the complete local release snapshots. They write local QA reports, not leads.

```sh
node scripts/test-editorial.mjs
node scripts/test-conversion-preview.mjs marketing/conversion-20260917/manifest-v3.json
```

`verify-release-files.mjs` and `check-production-seo.mjs` make live network requests;
they are not included in a cache cleanup. Publishing is a separate approved action.

## Builder families

- `build-*`: construct a candidate from a specified predecessor. Never choose
  an old preview just because its name contains "release".
- `test-*`: preservation and release-layer regression suites; inspect their
  manifest/default inputs before running.
- `check-*`, `audit-*`: local or hosted verification, depending on arguments.
- `prerender-*`, `vendor-*`: supporting generation and asset tasks; not a
  replacement for the verified complete release.
- `funnel-support.mjs`, `journey-support.mjs`: shared builder/test helpers.
- `maintenance/`: dependency-free local project checks and strict cache cleanup.

No builder, old Node dependency, migration or fixture is removed solely because
it is not referenced by the root `package.json`. Several tools are invoked
directly from component release instructions.
