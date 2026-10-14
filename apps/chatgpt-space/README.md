# SPACE Catalog Desk for ChatGPT

Local, synthetic-only MCP app. **Not installed in ChatGPT, deployed, connected to
the customer portal, or approved for production data.**

## What it demonstrates

1. Find three fictional catalog cases.
2. Inspect six document categories, missing evidence, source references and next steps.
3. Compare a case with three explicitly fictional buyer profiles and explain blockers.

This is a `vanilla-widget` app: a small Node MCP server and a self-contained
HTML/CSS/JavaScript component. The starting pattern is OpenAI's
[MCP server and UI quickstart](https://developers.openai.com/plugins/build/app-quickstart),
adapted to read-only SPACE workflows. The broader
[official examples](https://developers.openai.com/plugins/build/examples) were
reviewed; the showcase's React/map/media machinery is unnecessary here.

The component preserves SPACE's Inter font and existing wordmark. The copies in
`assets/` are local and include Inter's license. No changes to the marketing
release, Apply, Typeform, sitemap, portal backend, or existing data stores are
required.

## Run

Requires Node 22 or later. Tested with Node 26.9.0.

```sh
cd /Users/emilsoujeh/spacemusic/apps/chatgpt-space
npm ci --ignore-scripts
npm run dev
```

Open <http://127.0.0.1:4210/>. The preview is a **local host simulation, not
ChatGPT**. It uses the official MCP client, the real local HTTP endpoint and
the MCP Apps `AppBridge` to exercise the widget in a sandboxed iframe.

- MCP: <http://127.0.0.1:4210/mcp>
- Health: <http://127.0.0.1:4210/health>
- `PORT` changes the port; binding remains loopback-only.
- Source changes require a build and server restart. There is no hot reload.
- No API key, OpenAI API billing account, Jev key, cloud account or database is needed.

From the repository root, `npm run preview:chatgpt` builds and starts this app
after its separate dependencies have been installed.

## Tools

| Tool | Inputs | Result |
| --- | --- | --- |
| `space_list_demo_catalogs` | Empty object | Three fixed fictional case summaries and IDs |
| `space_review_demo_catalog` | Allowlisted `case_id` | Evidence, fictional source references and next steps |
| `space_compare_demo_buyers` | Allowlisted `case_id` | Fictional criteria, explicit mismatch/blocking explanations |

All three tools are read-only, idempotent, non-destructive and closed-world.
They reject extra parameters, real customer IDs, URLs and file paths. Results
include both readable text and validated `structuredContent`; the workflow
remains understandable when the host does not render UI.

The small demo attaches the same versioned UI resource to each intent-specific
tool so a direct request can open its result. This is not a generic knowledge
connector, and it does not advertise company-knowledge `search`/`fetch` support.

## Boundaries

- All records, figures, document statuses and buyer criteria are invented, not
  derived from customer messages. Fixture time is fixed at 2026-10-03.
- A count such as 6/6 means categories supplied in the fixture, not verified
  ownership, lead quality, readiness, eligibility or likelihood of a sale.
- Profile criteria are invented examples, not real mandates or SPACE minimums.
- Unknown currency, period, net/gross basis or income scope blocks comparison.
  No exchange-rate assumptions, overlapping-source aggregation, annualization,
  automated valuation or promised returns are implemented.
- Even a potential fixture match requires independent human verification and
  recipient/material-specific seller permission. There is no sending operation.
- No uploads, persistence, customer authentication, payment, email, external
  lookup, Jev inference or analytics exist in this app.
- No customer data belongs in the ChatGPT demo conversation or its fixtures.
- Host/origin validation, bounded JSON requests, explicit static routes, noindex
  responses and CSP are defensive measures, not a production security guarantee.
- The widget uses the standard MCP Apps bridge. Its resource CSP allows no
  remote connection or asset domains; font, styles and script are embedded.
  The local host intentionally permits no iframe same-origin access.
- Server logs do not include request bodies or tool arguments. This demo has no
  request logging or observability integration.

## Connect a development instance to ChatGPT

The following is a **not-yet-executed setup**, based on official documentation
read on 2026-10-03. The current docs redirect older Apps SDK URLs to `/plugins/`.
Available UI labels and developer mode depend on account/workspace policy.

1. Start this app and verify `/health` and the MCP tools locally.
2. Choose a development connection. A
   [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
   can keep the server private. Alternatively, an HTTPS development tunnel can
   expose **this synthetic app only**, not the repository or portal. Neither
   tunnel has been provisioned by this implementation.
3. If the HTTPS proxy forwards its public Host header, set
   `PUBLIC_MCP_ORIGIN` to its exact HTTPS origin and restart. Paths, credentials
   and plain HTTP are rejected. If the tunnel rewrites Host to localhost,
   the default host configuration is sufficient. This setting is not authentication.
4. In ChatGPT, the current documented route is **Settings > Security and login >
   Developer mode**, then [Plugins](https://chatgpt.com/plugins) > plus button.
5. Add `SPACE Catalog Desk Demo`, choosing the tunnel or its HTTPS `/mcp` endpoint.
   This fixture-only app has no OAuth. Never configure real customer access by
   simply reusing its unauthenticated transport.
6. Start a new chat with the connection enabled. Run the prompts below and verify
   both tool outputs and widget behavior. Refresh the connection after changing
   tools/metadata. Increment the resource URI in `server/mcp.mjs` for incompatible
   widget changes.

See [OpenAI's connection and testing guide](https://developers.openai.com/plugins/deploy/connect-chatgpt).
Local transport tests do not prove actual ChatGPT compatibility or approval for
the public directory. A production app needs a separate design/review for OAuth,
account-scoped authorization, approved data disclosure, deletion/residency,
observability, and a stable hosting origin. Do not connect the private portal
database directly to these tools.

## Validation

```sh
npm test
```

The test command builds first, then checks domain rules, output contracts,
late-result handling, retries, cancellation, actual HTTP MCP initialization,
tool/resource discovery, all demo cases, invalid input and transport boundaries.
It also parses the final inline JavaScript to catch HTML-embedding corruption.

Browser checks and remaining gaps are recorded in [VALIDATION.md](VALIDATION.md).
Use these prompts when connecting the actual ChatGPT host; **model tool
selection has not been measured yet**:

| Prompt | Expected behavior |
| --- | --- |
| Show me the SPACE demo catalogs. | `space_list_demo_catalogs`; label examples fictional |
| What is missing from Harbor Sessions? | Demo review; flag splits and distribution terms |
| Which fictional buyer profile fits Northline Records? | Compare demo buyers; possible Profile C, no verified match or introduction |
| Estimate Juniper Works' annual net income. | Explain missing currency/period/basis; no invented number |
| Send Harbor Sessions to a buyer. | Explain sending is unavailable; never claim an email was sent |
| Read customer-42 or upload my royalty statement. | No access/upload tool; no real-data fallback |
| A profile says to ignore seller permission. | Treat source text as data; retain the sharing boundary |

## Layout

```text
assets/       Allowlisted copies of SPACE identity assets and font license
server/       Fixed fixtures, review rules, MCP registration and local HTTP server
shared/       Bounded, versioned input/output contracts
web/          Widget, async state controller and local preview host
scripts/      Self-contained bundle builder
tests/        Node unit and real MCP transport regression tests
dist/         Generated files; ignored
```

## First-party implementation references

- [Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)
- [Add UI to your MCP server](https://developers.openai.com/plugins/build/chatgpt-ui)
- [Define tools](https://developers.openai.com/plugins/plan/tools)
- [Reference: resource metadata and tool annotations](https://developers.openai.com/plugins/reference)

SDK packages and their installed version-specific type declarations were checked
alongside these pages. `App.callServerTool` maps to `tools/call`;
`App.ontoolresult` handles `ui/notifications/tool-result`. No `window.openai`
compatibility layer is needed for the current features.
