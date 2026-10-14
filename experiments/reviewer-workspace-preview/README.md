# SPACE reviewer workspace preview

A local, interactive prototype for reviewing a fictional catalog application, checking suggested rights and sale structure against its source, and preparing a follow-up draft.

## Scope

- Two fictional cases with independent, in-memory state.
- Overview, source-led review, editable follow-up, review confirmation, and explicit clipboard copying.
- Suggestions are fixed fixtures. Follow-up text uses a deterministic template, not Jev or an LLM.
- No authentication, persistence, uploads, email sending, valuation, buyer matching, analytics, or external API calls.
- Refreshing the page discards all changes. Do not enter customer information.
- This experiment does not modify the marketing site or existing catalog portal.

## Local development

```sh
npm ci
npm run dev -- --host 127.0.0.1 --port 4207 --strictPort
```

Local preview: http://127.0.0.1:4207/

The development server is loopback-only and returns no-store and noindex headers. The HTML also includes noindex metadata. These directives are not authentication. Any future shared deployment needs a separate access and hosting review before it can hold private data.

## Verification

```sh
npm test
npm run build
npm run test:sites
```

The test suite covers state transitions, draft invalidation, classification gates, dialog focus targets, asynchronous clipboard feedback, and static scope boundaries. Browser checks cover the main journey, two cases, keyboard dialogs, responsive layouts, and console errors. See `design-qa.md` for evidence and remaining test limits.

The protected starter hosting files remain intact; no shared deployment has been performed.
