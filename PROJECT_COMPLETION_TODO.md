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
        - [X] `helm lint`-steg i CI.
            - **Fil:** `.github/workflows/ci.yml`
            - **Åtgärd:** Lade till steg för att installera Helm och köra `helm lint` på charts i `infra/helm/`.
        - **TODO (manuellt):** De skapade/modifierade Helm-chartsen (speciellt `deployment.yaml` och `values.yaml` för `valuation` och `api-gateway`, men även de andra) behöver kompletteras med korrekt image, portar, env-variabler, probes, resources etc.
    - **Status:** Initialt ⏳, blir ✅ efter åtgärd (med manuella uppföljningspunkter för att komplettera charts).

## Fas 4: Kärn-databas (Fortsättning)

### 4.1. Alembic 000x Payouts LedgerEntry Tabell & Index (tidigare "Alembic 0003")
    - [X] Initiera Alembic för Payouts service och skapa initial migration för `LedgerEntry`.
        - **Plats:** `services/payouts/`
        - **Åtgärd:** 
            - Felsökt och löst `psycopg2` importfel och SQLModel-konflikter (`nullable`/`index` med `sa_column`).
            - Korrigerat `alembic.ini` och `migrations/env.py` för att använda `PAYOUTS_DB_CONNECTION_STRING`.
            - Kört `alembic init migrations` i `services/payouts/`.
            - Genererat första autogenererade revisionen (`6364fcaeceb9_create_ledger_entry_table.py`) som skapar `ledgerentry`-tabellen och index på `offer_id`, `id`, `reference_id`, `transaction_timestamp`, `transaction_type`.
            - Användaren har kört `python -m alembic upgrade head` och applicerat migrationen.
    - **Status:** NY -> ✅.

## Fas 5: Backend-funktioner (enligt din nya lista)

### 5.1. Wise-API-integration (tidigare del av "Payout-flöde")
    - [ ] Implementera Wise-API-integration i backend-tjänsten.
        - **Plats:** `services/payouts/worker.py` (funktionen `_call_wise_transfer`)
        - **Åtgärd:** Implementera faktiskt HTTP-anrop till Wise API med `httpx.Client`.
        - **TODO:** Kräver Wise API-specifikationer (endpoint, auth, payload, response).
        - [ ] Skapa/refaktorera test med `respx` för att mocka Wise API-anrop.
        - [ ] Hantera `WISE_TOKEN` via Kubernetes Secret och miljövariabel.
    - **Status:** Initialt 🚧 (Placeholder), nu [ ] (Definition tydligare).

### 5.2. Kafka-bus: Event Producers & Consumers (tidigare P-09)
    - **Offers Service Producer (`offer.created`, `offer.payout.requested`):**
        - [X] Implementerad i `services/offers/routes.py`.
        - **Åtgärd:** Producerar `offer.created` vid offer-skapande och `offer.payout.requested` via ny endpoint.
        - **TODO:** Definiera hur `recipient_details` ska hanteras för `offer.payout.requested`.
    - **Valuation Service Producer (`offer.valuated`):**
        - [X] Implementerad i `services/valuation/worker.py`.
        - **Åtgärd:** Producerar `offer.valuated` efter lyckad värdering.
        - **TODO:** Verifiera `creator_id`-hantering mot Avro-schema och `Creator`-modell.
    - **Payouts Worker Consumer (`offer.payout.requested`):**
        - [X] Grundläggande konsument implementerad i `services/payouts/worker.py`.
        - **Åtgärd:** Lyssnar på topic, deserialiserar Avro-meddelande, anropar `execute_payout.delay()`.
        - **TODO:** 
            - [X] Skapa integrationstest (`test_kafka_consumer.py`) med mockad konsument. (Fil skapad och flera testfall implementerade för success, no_offer_id, kafka_error, eof, loop_stop, init_failure, schema_not_found).
            - [X] Implementera resterande testfall i `test_kafka_consumer.py` för success, saknat offer_id, Kafka-fel, EOF, loop-avstängning, samt initieringsfel för konsumenten (inkl. avsaknad av SCHEMA_REGISTRY_URL).
            - [ ] Överväg att köra konsumenten som separat process i produktion.
    - **Payouts Worker Producer (`offer.payout.completed`):**
        - [X] Implementera Kafka-producent i `services/payouts/worker.py`.
        - **Åtgärd:** Producerar `offer.payout.completed` i `finally`-blocket av `execute_payout`-tasken, med detaljer om utfallet.
    - **Docgen Worker Consumer (`offer.payout.completed`):**
        - [X] Grundläggande konsument implementerad i `services/docgen/tasks.py`.
        - **Åtgärd:** Lyssnar på `offer.payout.completed`, filtrerar på `SUCCESS`, anropar `generate_receipt_pdf.delay()` som nu innehåller logik för att skapa PDF och S3-uppladdning.
        - [X] Producerar `offer.receipt.generated`-event efter lyckad kvitto-generering.
        - **TODO:** 
            - [ ] Skapa Jinja2-mall för kvittot (`receipt_template.html`). (Mallen är skapad, men innehåll och design kan behöva finjusteras).
            - [X] Skapa tester för konsument och PDF-generering. (Grundläggande tester för konsument och task-registrering tillagda i `tests/docgen/test_tasks.py`. Fler konsumenttester och tester för renderer-funktioner/PDF-generering återstår).
            - [ ] Sätt miljövariabel `RUN_KAFKA_LISTENER_IN_DOCGEN_WORKER` för lokal dev med Docker.
            - [ ] (Valfritt) Implementera notifiering/lagring av kvitto-URL baserat på `offer.receipt.generated`-eventet i andra tjänster.
    - **Topics:** `offer.created`, `offer.valuated`, `offer.payout.requested`, `offer.payout.completed`, `offer.receipt.generated` (antingen auto-skapade eller manuellt skapade i Kafka).
    - **Avro Scheman:** `offer_created.avsc`, `offer_valuated.avsc`, `offer_payout_requested.avsc`, `offer_payout_completed.avsc` är skapade i `schema/`.
    - **Status:** Initialt ❌, nu delvis ✅ (flera producenter/konsumenter påbörjade/klara).

### 5.3. Feature-toggle LaunchDarkly (P-11)
    - [X] Implementera LaunchDarkly-integrering i backend-tjänsten.
        - **Fil:** `libs/py_common/flags.py` (redan skapad med grundläggande `is_enabled`).
        - **Plats för användning:** `services/offers/routes/calculator.py` (förberedd för `calculator_v2` toggle).
        - **Åtgärd:** 
            - [X] Anrop till `is_enabled("calculator-v2-range", ...)` med placeholder V1/V2-logik är nu på plats i `calculator.py`.
            - [X] Säkerställt att `LAUNCHDARKLY_SDK_KEY` kan hanteras som Kubernetes Secret och miljövariabel via Helm chart för `offers-api` (`infra/helm/offers/templates/deployment.yaml`).
        - **TODO (manuellt):** 
            - Användaren skapar K8s Secret med faktiskt SDK-nyckel.
            - Användaren implementerar faktisk V1/V2-logik i `calculator.py`.
            - Om andra tjänster initierar LD-klient, uppdatera deras Helm charts liknande.
            - Konfigurera flaggan "calculator-v2-range" i LaunchDarkly UI.
    - **Status:** Initialt ❌, nu ✅ (Grundläggande flagg-kod, Helm-setup och placeholder-logik klar. Verklig logik och K8s Secret återstår).

## Fas 6: Robusthet & Kostnadskontroll (Enligt din nya lista)

### 6.1. Chaos-cron (P-12)
    - [X] Konfigurera och schemalägg Litmus Chaos-experiment.
        - **Plats:** `infra/helm/litmus/chaos_kill_random.yaml` (grund skapad, nu templatiserad).
        - **Åtgärd:** 
            - [X] Verifierat/justerat `ChaosEngine`-definitionen genom att göra den Helm-templatiserad för flexibel konfiguration (namespace, appns, applabel, experimentparametrar, probe-detaljer).
            - [ ] Skapa och applicera `CronWorkflow` för att schemalägga experimentet (exempel finns i runbook, behöver templatiseras och skapas).
            - [ ] Helm-installera Litmus i Kubernetes-klustret (om ej gjort).
            - [ ] Konfigurera SLO-alert (t.ex. `MyCriticalSLOBreachAlert`) i Prometheus/Grafana som proben kan verifiera.
    - **Status:** Initialt ❌, nu delvis ✅ (ChaosEngine templatiserad, resten återstår).

### 6.2. FinOps-dashboard & Alert (P-13)
    - [X] Implementera kostnadsövervakning och notifiering.
        - **Plats:** 
            - Dashboard: `infra/helm/grafana/dashboards/cost_per_offer.json` (grund skapad).
            - Alert: `infra/helm/prometheus/rules/cost_alerts.yaml` (grund skapad, PromQL-uttryck justerat).
        - **Åtgärd:** 
            - [X] Justerat PromQL-uttrycket i `cost_alerts.yaml` till att använda `increase()` för kostnadsmetriken (med antaganden om metrikens beteende).
            - [ ] Konfigurera AWS Cost Explorer-metriker via `cloudwatch-exporter` att skrapas av Prometheus.
            - [ ] Verifiera/justera `aws_ce_daily_cost_usd_sum`-metriken namn, labels och beteende i PromQL-queryn.
            - [ ] Säkerställ att Prometheus Alertmanager är konfigurerad att skicka till korrekt Slack-webhook (kräver manuell uppdatering av URL/kanal i `cost_alerts.yaml`).
            - [ ] Verifiera att `exchange_rate_usd_to_eur`-metriken finns och är korrekt.
    - **Status:** Initialt ❌, nu delvis ✅ (Alert-regelns query justerad, konfiguration och verifiering av metriker/Alertmanager återstår).

## Fas 7: Admin-UI (Fortsättning)

### 7.1. Live-SSE i Deals-tabell
    - [X] Implementera Server-Sent Events (SSE) för realtidsuppdateringar i Admin UI.
        - [X] **Backend:** Skapade en SSE-endpoint (`/offers/events/deals`) i `services/offers/routes.py`.
        - [X] **Backend Kafka Consumer:** Implementerade en Kafka-konsument i `Offers-API` (`services/offers/routes.py`) som lyssnar på `offer.valuated` och `offer.payout.completed` och anropar `broadcast_deal_update`.
            - [X] Förbättrad schemahantering: Konsumenten använder nu Schema Registry dynamiskt istället för ett fixerat schema.
        - [X] **Frontend:** Lade till grundläggande `EventSource`-logik i `services/admin_ui/src/pages/DealsPage.tsx` för att ansluta till SSE-endpointen, ta emot och bearbeta meddelanden för att uppdatera deals-listan. Linter-fel åtgärdade.
        - **TODO (Frontend):** Grundlig testning av SSE-flödet och UI-uppdateringar. Verifiera datastruktur och mappning i payload för alla event-typer.
        - **TODO (Skalbarhet):** För produktionsmiljö med flera instanser, ersätt in-memory SSE-klienthantering med t.ex. Redis Pub/Sub.
    - **Status:** Initialt ⏳, nu delvis ✅ (Backend och Frontend SSE-grund på plats och typsäkrad. Testning, förfining av payload-mappning och skalbarhetslösning återstår).

## Fas 8: CI / QA (Fortsättning)

### 8.1. Testtäckning Payouts (tidigare del av "Täcka Missing Tests")
    - [X] Kompletterat med felscenarion för `execute_payout` i `tests/payouts/test_worker.py`.
    - [X] Implementerat testfall i `tests/payouts/test_kafka_consumer.py` för success, saknat offer_id, Kafka-fel, EOF, loop-avstängning, samt initieringsfel för konsumenten (inkl. avsaknad av SCHEMA_REGISTRY_URL).
    - **Status:** Delvis ✅ -> ✅ (Huvudsakliga konsument-testscenarion nu implementerade).

### 8.2. Lägg till Coverage-rapport i CI
    - [X] Konfigurera CI-pipeline att generera och ev. publicera en testtäckningsrapport.
        - **Fil:** `.github/workflows/ci.yml`
        - **Åtgärd:** Lade till steg efter `pytest` för att köra `pytest --cov=. --cov-report=xml --cov-report=html` och `actions/upload-artifact@v4` för att ladda upp `htmlcov/`.
        - **TODO (manuellt):** (Valfritt) Integrera med Codecov/Coveralls med `coverage.xml`.
    - **Status:** Initialt ⏳, nu ✅ (Grundläggande HTML-rapportsgenerering och uppladdning på plats).

## Fas 9: Performance & Release (Enligt din nya lista)

### 9.1. Load-test + SLO-gate
    - [ ] Utför lasttester och verifiera SLO:er.
        - **Verktyg:** k6 (eller liknande).
        - **Skript:** Skapa k6-skript för att simulera 1000 RPS i 10 minuter mot kritiska endpoints.
        - **Verifiering:** Använd `linkerd stat` och Grafana-dashboards för att mäta P95-latens och andra SLO:er (t.ex. < 5s).
        - **Gate:** Definiera framgångskriterier för att godkänna prestanda.
    - **Status:** Initialt ❌, nu [ ].

### 9.2. Blue-green deploy / rollout
    - [ ] Implementera strategi för blue-green eller canary deployments.
        - **Verktyg:** Argo Rollouts, eller Linkerd SMI + Flagger.
        - **Åtgärd:** Konfigurera deployment-strategi för minst en nyckel-tjänst.
        - **Verifiering:** Skapa och verifiera rollback-skript/process.
    - **Status:** Initialt ❌, nu [ ].

## Fas 10: Dokumentation & Compliance (Fortsättning)

### 10.1. ISO 27001-mappning (tidigare "ISO-evidence")
    - [ ] Komplettera ISO 27001-mappningsdokument.
        - **Fil:** `docs/iso-controls.md` (antar att denna fil behöver skapas eller redan finns med placeholders).
        - **Åtgärd:** Fyll i dokumentet med bevis och länkar till relevanta system/loggar/konfigurationer för logging, backup, RBAC, etc.
    - **Status:** Initialt ⏳, nu [ ].

---
**Prioritering:**
Följ numreringen eller prioritera enligt teamets behov. De mest kritiska punkterna från rapporten (som Alembic-index och Structlog-konfiguration) bör nog tas tidigt. 