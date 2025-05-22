# Projekt Slutförande: To-Do Lista för SpaceMusic

Detta dokument beskriver de återstående stegen för att färdigställa SpaceMusic-projektet, baserat på den initiala hälsorapporten och efterföljande åtgärder.

## Fas 1: Python Backend & Databas

### 1.1. Virtuell Miljö & Beroenden (Lokal Utvecklingsmiljö)
    - [X] Säkerställ att Pylance (VS Code) använder projektets virtuella miljö (`.venv`).
        - Kommando: `python -m venv .venv` (om ej existerar)
        - Kommando: `source .venv/bin/activate` (eller motsvarande för ditt OS)
        - Kommando: `pip install -r requirements-dev.txt`
        - Verifiera i VS Code att rätt Python-interpretator är vald (den från `.venv`).
    - **Status:** Initialt ⚠️, bör vara ✅ efter ovanstående.

### 1.2. Celery Konfiguration & Robusthet
    - [X] Uppdatera Celery-konfigurationen för ökad robusthet.
        - **Fil:** `libs/py_common/celery_config.py` (eller där Celery-appen konfigureras)
        - **Åtgärd:** Lägg till/verifiera `task_acks_late = True`.
        - **Åtgärd:** Lägg till/verifiera `broker_connection_retry_on_startup = True`.
    - **Status:** Initialt ✅ (namn), blir ✅ efter åtgärd.

### 1.3. Pydantic Versionering
    - [X] Undersök och hantera Pydantic v2-kompatibilitet.
        - **Scenario 1 (Om Pydantic v2 används medvetet):**
            - **Åtgärd:** Dubbelkolla `field_serialization_defaults` i alla Pydantic-modeller som kan påverkas av v2-ändringar. Se Pydantics migreringsguide.
        - **Scenario 2 (Om Pydantic v2 *inte* ska användas än):**
            - **Fil:** `requirements.txt` (och ev. `requirements-dev.txt`)
            - **Åtgärd:** Lås versionen till `pydantic<2.0.0`.
    - **Status:** Initialt ❓, blir ✅ efter åtgärd.

### 1.4. Alembic Revisioner & Databas-schema
    - [X] Skapa ny Alembic-revision för att lägga till index på `offers.status`.
        - **Kommando (generera revision):** `alembic revision -m "add_index_offers_status"` (körs från `services/offers` med aktivt `.venv`)
        - **Fil (ny revision):** `services/offers/migrations/versions/d198261eb7a4_add_index_offers_status.py` (Exempel ID, faktiskt ID kan variera)
        - **Åtgärd (i revisionens `upgrade()`-funktion):**
          ```python
          op.create_index(op.f('ix_offers_status'), 'offers', ['status'], unique=False)
          ```
        - **Åtgärd (i revisionens `downgrade()`-funktion):**
          ```python
          op.drop_index(op.f('ix_offers_status'), table_name='offers')
          ```
        - **VIKTIGT:** Verifiera `down_revision` i den nya filen. Den ska peka på ID:t för den *föregående* migrationen.
        - **Kommando (applicera i dev):** `alembic upgrade head` (från `services/offers` med aktivt `.venv` och databasen igång)
    - **Status:** Initialt ✅ (tabeller skapade), blir ✅ efter åtgärd och verifiering/applicering av användaren.

### 1.5. Structlog Konfiguration
    - [X] Implementera Structlog-konfiguration och integration med Uvicorn.
        - **Fil (ny eller befintlig):** `libs/py_common/logging.py` (Befintlig `setup_logging` användes).
        - **Åtgärd:** `setup_logging()` anropas nu i `services/offers/main.py` vid startup.
        - **Åtgärd (i `services/offers/main.py`):** Lade till `StructlogRequestLoggingMiddleware` för JSON-formaterade accessloggar via Structlog.
        - **TODO (manuellt):**
            - Uppdatera Uvicorn startkommando (t.ex. i `docker-compose.yml`) med `--no-access-log` för att undvika dubbla accessloggar.
            - Överväg att applicera liknande Structlog setup (anrop av `setup_logging` och middleware) för andra FastAPI/Python-tjänster för konsekvent loggning.
    - **Status:** Initialt ❌, blir ✅ efter åtgärd (med manuella uppföljningspunkter).

### 1.6. Tester (Python)
    - **Payouts Tjänsten:**
        - [ ] Refaktorera test-strategi (överväg `pytest-asyncio` + `httpx.AsyncClient`).
            - **Filer:** `tests/payouts/test_routes.py`, `tests/payouts/test_worker.py`
            - **Åtgärd:** Gradvis ersätt tunga `MagicMock`-kedjor med `httpx.AsyncClient` för att mocka externa HTTP-anrop och `pytest-asyncio` för asynkrona tester. (Delvis påbörjad genom att förbereda för `_call_wise_transfer` refaktorering).
        - [X] Lägg till testfall för "offer not found" i payout-logiken.
            - **Fil:** `tests/payouts/test_worker.py`
            - **Åtgärd:** Test `test_execute_payout_offer_not_found` tillagt. Verifierar korrekt returvärde, att inga betalningsanrop görs och att `APP_ERRORS_TOTAL` metrik sätts.
        - [X] Lägg till testfall för "no median price" i payout-logiken.
            - **Fil:** `tests/payouts/test_worker.py`
            - **Åtgärd:** Test `test_execute_payout_no_median_price` tillagt. Verifierar korrekt returvärde och att `APP_ERRORS_TOTAL` metrik sätts.
        - [X] Lägg till testfall för "Stripe + Wise both fail" i payout-logiken.
            - **Fil:** `tests/payouts/test_worker.py`
            - **Åtgärd:** Test `test_execute_payout_stripe_and_wise_fail` tillagt. Verifierar felhantering, korrekt returvärde och relevanta metriker (`APP_ERRORS_TOTAL`, `WISE_TRANSFERS_TOTAL`).
    - **Celery Tasks:**
        - [X] Slutför tester för Celery task-registrering (om stubs finns).
            - **Plats:** `tests/payouts/test_worker.py`, `tests/valuation/test_worker.py`, `tests/docgen/test_tasks.py`.
            - **Åtgärd:** Verifierat/skapat tester (`test_payout_task_registered`, `test_task_registered` i valuation, `test_generate_termsheet_task_registered`) som kollar att tasks finns i `celery_app.tasks`.
    - **Status:** Initialt ⚠️, blir ✅ efter åtgärder.

## Fas 2: TypeScript & Admin UI (`services/admin_ui`)

### 2.1. UI Primitives (shadcn/ui)
    - [X] Slutför shadcn/ui-komponenter.
        - **Drawer:**
            - **Åtgärd:** Körde `npx shadcn@latest add drawer --yes` i `services/admin_ui`.
            - **Verifierat:** `services/admin_ui/src/components/ui/drawer.tsx` skapad och exporterar `DrawerContent` m.fl.
        - **Spinner/Loader (vid behov):**
            - [ ] **Åtgärd (om standardkomponent saknas):** Överväg att lägga till en enkel spinner-komponent eller använd en från ett bibliotek om en sådan inte redan finns och behövs för att indikera laddningstillstånd. (Beslut: Använd `lucide-react/Loader2` direkt vid behov, ingen separat komponent skapas just nu).
    - **Status:** Initialt ⚠️, blir delvis ✅ efter åtgärd (Drawer klar, Spinner avvaktar specifik implementation).

### 2.2. Auth0 Konfiguration
    - [X] Säkerställ Auth0-konfiguration för lokal utveckling.
        - **Fil:** `services/admin_ui/.env.local` (skapas manuellt av användaren p.g.a. globalIgnore-regler).
        - **Åtgärd:** Användaren lägger till nödvändiga Auth0 miljövariabler (t.ex. `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_CALLBACK_URL`) i den manuellt skapade filen.
        - **Referens:** Auth0 dokumentation och exempel för React/Vite.
    - **Status:** Initialt ❓, blir ✅ efter manuell åtgärd av användaren.

### 2.3. Vitest Typsäkerhet
    - [X] Förbättra typsäkerheten i Vitest-tester.
        - **Filer:** `services/admin_ui/src/pages/DealsPage.test.tsx`.
        - **Åtgärd:** Ersatt användning av `as any` för `Auth0Context.Provider` genom att definiera en mer komplett och typsäker `mockAuth0ContextValue` som uppfyller `Auth0ContextInterface<User>`.
    - **Status:** Initialt ⚠️, blir ✅ efter åtgärd.

### 2.4. CI Workflow (admin_ui)
    - [X] Verifiera att `pnpm install` körs korrekt i CI för `admin_ui`.
        - **Fil:** `.github/workflows/ci.yml`
        - **Åtgärd:** Säkerställt att steg finns för `pnpm install` och `pnpm test`. Lade till ett steg för `pnpm build` efter testerna.
    - **Status:** Initialt ✅ (parse-bar), blir ✅ efter verifiering/åtgärd.

## Fas 3: Infrastruktur (Terraform & Helm)

### 3.1. Terraform (VPC & Security Groups)
    - [X] Anslut VPC-outputs till `aws_security_group.db` i Terraform.
        - **Plats:** `infra/tf/envs/prod/security_groups.tf` och `infra/tf/envs/staging/security_groups.tf`.
        - **Åtgärd:** Verifierat att `aws_security_group.db` i både prod och staging korrekt använder `module.vpc.vpc_id` för `vpc_id` och `module.vpc.private_subnets_cidr_blocks` för ingress `cidr_blocks`.
    - **Status:** Initialt ⏳, blir ✅ efter verifiering.

### 3.2. Helm Charts (Linkerd-injektion)
    - [X] Lägg till Linkerd-injektionsannotation i Deployment-charts.
        - **Plats:** `infra/helm/<service-name>/templates/deployment.yaml` för `offers`, `payouts`, `docgen`, `event-consumer`, `valuation`, `api-gateway`.
        - **Åtgärd:** Skapade Helm chart-scaffolds för nya tjänster. Lade till/skapade `deployment.yaml` med `linkerd.io/inject: enabled` annotationen för alla listade tjänster.
        - **TODO (manuellt):** De skapade/modifierade Helm-chartsen (speciellt `deployment.yaml` och `values.yaml` för `valuation` och `api-gateway`, men även de andra) behöver kompletteras med korrekt image, portar, env-variabler, probes, resources etc.
    - **Status:** Initialt ⏳, blir ✅ efter åtgärd (med manuella uppföljningspunkter för att komplettera charts).

## Fas 4: Dokumentation & Slutstädning

### 4.1. Skapa detta To-Do dokument
    - [X] Skapa `PROJECT_COMPLETION_TODO.md`.
    - **Status:** ✅

### 4.2. Projekt Readme
    - [X] Uppdatera/skapa en övergripande `README.md` för projektet.
        - **Innehåll:** Kort beskrivning, hur man sätter upp utvecklingsmiljön, hur man kör projektet, länk till `PROJECT_COMPLETION_TODO.md`.
        - **Åtgärd:** Skapade `README.md` i projektets rot med grundläggande struktur och information.
    - **Status:** ⬜ (Nytt) -> ✅

### 4.3. Granska och slå samman feature-branchar
    - [ ] Säkerställ att allt arbete är på en `main` eller `develop`-branch och att feature-branchar är granskade och sammanslagna.
    - **Status:** ⬜ (Process)

### 4.4. Slutlig testning (E2E om möjligt)
    - [ ] Genomför en sista övergripande testrunda av systemet.
    - **Status:** ⬜ (Nytt)

---
**Prioritering:**
Följ numreringen eller prioritera enligt teamets behov. De mest kritiska punkterna från rapporten (som Alembic-index och Structlog-konfiguration) bör nog tas tidigt. 