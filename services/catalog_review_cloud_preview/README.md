# Railway + Vercel Read-Only Preview

Separate public design preview requested September 18, 2026. This is **not the
production backend, a customer pilot, or proof that the deployment gates passed**.
The current customer/reviewer UI is reused from `catalog_review_ui`; none of the
production authentication, origin or launch guards are loosened.

Five prebuilt fictional states show draft, submission, document request,
published supplement and reviewer view. This preview has no editable inputs,
real authentication, uploads, database, object store, email, payments, OAuth or
analytics. No customer records or secrets are in either upload bundle. The fake
session expiry and CSRF value are display-contract fields, not credentials.
Staff login/enrollment and intake administration are outside this visual preview.

The Railway Node service exposes only exact GET/HEAD scenario reads and health.
The Vercel function makes bounded server-side requests to that fixed backend;
browser cookies, authorization and request bodies are never forwarded. No browser
CORS access to Railway is needed. Error responses do not reveal upstream details.
Both sides use noindex/no-store. A public synthetic preview is not confidential.

## Build And Verify

```sh
node services/catalog_review_cloud_preview/build.mjs
node --test services/catalog_review_cloud_preview/preview.test.mjs
```

The build copies explicit assets into ignored `build/frontend` and
`build/backend`. Never deploy the repository root. `source-manifest.json` records
the exact source asset hashes; the original production modules remain unchanged.
The browser suite requires the local bundled Playwright and Google Chrome.

## Deployment

1. Authenticate Railway; create a new isolated `space-review-preview` project
   and a `preview` environment. Do not link to an existing production service.
2. Create one `preview-api` service, no database or persistent volume. Deploy
   only `build/backend`, using its Railpack configuration, then request a Railway
   generated domain. Keep one replica; no unrelated cloud resources are touched.
   Use the absolute build/backend path with `railway up --path-as-root
   --no-gitignore` and explicit project/environment/service IDs so the ignored
   build directory is uploaded without including its repository parent.
3. Link `build/frontend` to a separate Vercel `space-review-preview` project.
   Set `REVIEW_PREVIEW_BACKEND_URL` to the exact HTTPS Railway generated origin
   as a server runtime environment variable. It is not a secret.
4. Deploy with target `preview`, never `production`; keep account deployment
   protection enabled. Sharing permissions remain those of the user's account.
5. Do not change spacemusic.io, Apply, its DNS or the 141 sitemap destinations.
   Delete/stop this isolated preview when no longer needed to stop compute use.

Railway/Vercel preview hosting does not replace the approved EU customer-pilot
architecture. Moving real customer processing requires a separate decision and
verification of residency, identity, storage, backups and operational gates.

## Current Status

September 21: the isolated read-only preview is deployed. This is still not a
customer pilot or a deployment of the production portal.

- Frontend: https://space-review-preview-fyijozdwm-moodytunes.vercel.app
- Vercel project: `moodytunes/space-review-preview`.
- Vercel deployment: `dpl_5pjozh2ApNoGfsTZinZCXST1SwTX`, target `preview`, `Ready`.
- Railway origin: https://preview-api-preview-901b.up.railway.app
- Railway project: `57d6a8bd-32bd-4d37-bac1-a0b6e37e48c1` (`space-review-preview`).
- Railway environment: `6787f69e-b7ba-4a0c-b9f6-3bc0d6797ee4` (`preview`).
- Railway service: `062ee8b8-1bfc-4cf9-bdd0-be53577aca2c` (`preview-api`).
- Railway deployment: `799b9f8e-fcfa-4644-bc9b-d58cb708f5d8`, `SUCCESS`.

The local 17-check suite passes, including all five states at 390 px and 1440 px
in real Chrome. Live Railway checks confirmed health, all five scenario reads,
test-only records, noindex headers and rejected POST requests (405). Vercel's
deployment inspection confirms the built API function and Ready state; the
deployed frontend has not undergone a full browser acceptance test.

Vercel authentication remains enabled (`all_except_custom_domains`). Viewers
need authorized Vercel access; no protection bypass or public sharing token was
created. No custom domain or production DNS was changed.

Vercel classified the first deployment as production despite `--target=preview`.
That deployment (`dpl_A43FEphaSRuSyXBsiZT663EWufQV`) exists only in this new isolated
preview project, contains the same synthetic bundle, and retains Vercel protection.
The second deployment above was explicitly verified as target `preview`. Use its
URL for review, not the isolated project's production alias. Railway's empty
`production` environment has no deployed service. The public marketing site,
Apply and production portal remain unchanged.
