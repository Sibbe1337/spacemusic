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
    - [ ] Uppdatera Celery-konfigurationen för ökad robusthet.
        - **Fil:** `libs/py_common/celery_config.py` (eller där Celery-appen konfigureras)
        - **Åtgärd:** Lägg till/verifiera `task_acks_late = True`.
        - **Åtgärd:** Lägg till/verifiera `broker_connection_retry_on_startup = True`.
    - **Status:** Initialt ✅ (namn), blir ✅ efter åtgärd.

### 1.3. Pydantic Versionering
    - [ ] Undersök och hantera Pydantic v2-kompatibilitet.
        - **Scenario 1 (Om Pydantic v2 används medvetet):**
            - **Åtgärd:** Dubbelkolla `field_serialization_defaults` i alla Pydantic-modeller som kan påverkas av v2-ändringar. Se Pydantics migreringsguide.
        - **Scenario 2 (Om Pydantic v2 *inte* ska användas än):**
            - **Fil:** `requirements.txt` (och ev. `requirements-dev.txt`)
            - **Åtgärd:** Lås versionen till `pydantic<2.0.0`.
    - **Status:** Initialt ❓, blir ✅ efter åtgärd.

### 1.4. Alembic Revisioner & Databas-schema
    - [ ] Skapa ny Alembic-revision för att lägga till index på `offers.status`.
        - **Kommando (generera revision):** `alembic revision -m "add_index_offers_status"`
        - **Fil (ny revision):** `services/offers/migrations/versions/xxxx_add_index_offers_status.py`
        - **Åtgärd (i revisionens `upgrade()`-funktion):**
          ```python
          op.create_index(op.f('ix_offers_status'), 'offers', ['status'], unique=False)
          ```
        - **Åtgärd (i revisionens `downgrade()`-funktion):**
          ```python
          op.drop_index(op.f('ix_offers_status'), table_name='offers')
          ```
        - **Kommando (applicera i dev):** `alembic upgrade head` (efter att DB-tjänsten körs)
    - **Status:** Initialt ✅ (tabeller skapade), blir ✅ efter åtgärd.

### 1.5. Structlog Konfiguration
    - [ ] Implementera Structlog-konfiguration och integration med Uvicorn.
        - **Fil (ny eller befintlig):** `libs/py_common/logging.py`
        - **Åtgärd:** Lägg till `structlog.configure(...)` med lämpliga processorer (t.ex. timestamp, log level, JSON renderer för produktion).
        - **Åtgärd (i `main.py` för FastAPI-appar, t.ex. `services/offers/main.py`):**
            - Importera den konfigurerade loggern.
            - Konfigurera Uvicorn att använda Structlog för accessloggar om möjligt, eller se till att applikationsloggar är formaterade via Structlog.
    - **Status:** Initialt ❌, blir ✅ efter åtgärd.

### 1.6. Tester (Python)
    - **Payouts Tjänsten:**
        - [ ] Refaktorera test-strategi (överväg `pytest-asyncio` + `httpx.AsyncClient`).
            - **Filer:** `tests/payouts/test_routes.py`, `tests/payouts/test_worker.py`
            - **Åtgärd:** Gradvis ersätt tunga `MagicMock`-kedjor med `httpx.AsyncClient` för att mocka externa HTTP-anrop och `pytest-asyncio` för asynkrona tester.
        - [ ] Lägg till testfall för "offer not found" i payout-logiken.
            - **Fil:** Sannolikt `tests/payouts/test_worker.py` eller där logiken som hanterar offers finns.
            - **Åtgärd:** Skapa ett test som simulerar att ett offer-ID inte kan hittas och verifierar korrekt felhantering/loggning.
        - [ ] Lägg till testfall för "Stripe + Wise both fail" i payout-logiken.
            - **Fil:** `tests/payouts/test_worker.py`
            - **Åtgärd:** Skapa ett test där både Stripe och Wise (eller motsvarande betaltjänst-mockar) returnerar fel, och verifiera att tasken hanterar detta korrekt (t.ex. retry, felstatus).
    - **Celery Tasks:**
        - [ ] Slutför tester för Celery task-registrering (om stubs finns).
            - **Plats:** Där Celery-tasks definieras och testas (t.ex. `tests/offers/test_tasks.py`, `tests/valuation/test_tasks.py`).
            - **Åtgärd:** Verifiera att tasks är korrekt registrerade i Celery-appen och kan anropas (även om det bara är en mockad `apply_async`).
    - **Status:** Initialt ⚠️, blir ✅ efter åtgärder.

## Fas 2: TypeScript & Admin UI (`services/admin_ui`)

### 2.1. UI Primitives (shadcn/ui)
    - [ ] Slutför shadcn/ui-komponenter.
        - **Drawer:**
            - **Åtgärd:** Kör `pnpm dlx shadcn-ui@latest add drawer` (eller `npx`) i `services/admin_ui`.
            - **Verifiera:** Att `DrawerContent` och andra nödvändiga delar exporteras korrekt från `components/ui/drawer.tsx`.
        - **Spinner/Loader (vid behov):**
            - **Åtgärd (om standardkomponent saknas):** Överväg att lägga till en enkel spinner-komponent eller använd en från ett bibliotek om en sådan inte redan finns och behövs för att indikera laddningstillstånd.
    - **Status:** Initialt ⚠️, blir ✅ efter åtgärd.

### 2.2. Auth0 Konfiguration
    - [ ] Säkerställ Auth0-konfiguration för lokal utveckling.
        - **Fil:** `services/admin_ui/.env.local` (skapa om den inte finns)
        - **Åtgärd:** Lägg till nödvändiga Auth0 miljövariabler (t.ex. `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CALLBACK_URL`).
        - **Referens:** Auth0 dokumentation och exempel för React/Vite.
    - **Status:** Initialt ❓, blir ✅ efter åtgärd.

### 2.3. Vitest Typsäkerhet
    - [ ] Förbättra typsäkerheten i Vitest-tester.
        - **Filer:** Alla `.test.tsx` eller `.test.ts` filer i `services/admin_ui/src/`.
        - **Åtgärd:** Ersätt användning av `any` med `unknown` (och gör typskydd), mer specifika typer, eller generiska typer där det är lämpligt.
    - **Status:** Initialt ⚠️, blir ✅ efter åtgärd.

### 2.4. CI Workflow (admin_ui)
    - [ ] Verifiera att `pnpm install` körs korrekt i CI för `admin_ui`.
        - **Fil:** `.github/workflows/ci.yml`
        - **Åtgärd:** Säkerställ att ett steg finns för att `cd services/admin_ui && pnpm install && pnpm build` (eller motsvarande test/lint-kommandon).
    - **Status:** Initialt ✅ (parse-bar), blir ✅ efter verifiering/åtgärd.

## Fas 3: Infrastruktur (Terraform & Helm)

### 3.1. Terraform (VPC & Security Groups)
    - [ ] Anslut VPC-outputs till `aws_security_group.db` i Terraform.
        - **Plats:** `infra/tf/envs/prod/security_groups.tf` och `infra/tf/envs/staging/security_groups.tf`.
        - **Åtgärd:** Se till att databasens säkerhetsgrupp korrekt refererar till VPC-ID och subnät från VPC-modulen (t.ex. via `module.vpc.vpc_id`, `module.vpc.private_subnets`). Detta kan innebära att säkerställa att VPC-modulen exporterar dessa outputs och att de konsumeras korrekt.
    - **Status:** Initialt ⏳, blir ✅ efter åtgärd.

### 3.2. Helm Charts (Linkerd-injektion)
    - [ ] Lägg till Linkerd-injektionsannotation i Deployment-charts.
        - **Plats:** Alla relevanta Deployment YAML-filer i `infra/helm/<service-name>/templates/deployment.yaml`.
        - **Åtgärd:** Under `spec.template.metadata.annotations`, lägg till:
          ```yaml
          linkerd.io/inject: enabled
          ```
    - **Status:** Initialt ⏳, blir ✅ efter åtgärd.

## Fas 4: Dokumentation & Slutstädning

### 4.1. Skapa detta To-Do dokument
    - [X] Skapa `PROJECT_COMPLETION_TODO.md`.
    - **Status:** ✅

### 4.2. Projekt Readme
    - [ ] Uppdatera/skapa en övergripande `README.md` för projektet.
        - **Innehåll:** Kort beskrivning, hur man sätter upp utvecklingsmiljön, hur man kör projektet, länk till denna To-Do (eller dess innehåll när slutfört).
    - **Status:** ⬜ (Nytt)

### 4.3. Granska och slå samman feature-branchar
    - [ ] Säkerställ att allt arbete är på en `main` eller `develop`-branch och att feature-branchar är granskade och sammanslagna.
    - **Status:** ⬜ (Process)

### 4.4. Slutlig testning (E2E om möjligt)
    - [ ] Genomför en sista övergripande testrunda av systemet.
    - **Status:** ⬜ (Nytt)

---
**Prioritering:**
Följ numreringen eller prioritera enligt teamets behov. De mest kritiska punkterna från rapporten (som Alembic-index och Structlog-konfiguration) bör nog tas tidigt.