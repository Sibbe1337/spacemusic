# SpaceMusic Projektet

Välkommen till SpaceMusic-projektet! Detta är en plattform för [kort beskrivning av vad SpaceMusic gör, t.ex. "hantering och validering av musikerbjudanden"].

## Översikt

Detta monorepo innehåller flera mikrotjänster, delade bibliotek, infrastrukturkod (Terraform, Helm) och dokumentation. För en detaljerad mappstruktur, se [`folderstructure.md`](./folderstructure.md).

För en komplett lista över återstående uppgifter för att färdigställa projektet, se [`PROJECT_COMPLETION_TODO.md`](./PROJECT_COMPLETION_TODO.md).

## Komma Igång (Lokal Utveckling)

### Förutsättningar

*   Docker & Docker Compose
*   Python 3.12+ (eller den version som används för att skapa `.venv`)
*   Node.js (för `services/admin_ui`, se dess `README.md` för specifik version, t.ex. v18.x) och `pnpm`
*   `make` eller `just` (om `Justfile` eller `Makefile` används för kommandon - *lägg till om relevant*)
*   Helm CLI (för att hantera Kubernetes-paket)
*   `kubectl` (för interaktion med Kubernetes)
*   AWS CLI (konfigurerad för åtkomst till ditt AWS-konto för Terraform)
*   Terraform CLI

### Sätta upp den virtuella Python-miljön

Från projektets rotkatalog:
```bash
python3 -m venv .venv
source .venv/bin/activate  # För macOS/Linux. För Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt 
# Installera även tjänstespecifika dependencies om du ska arbeta med en specifik tjänst, t.ex.:
# pip install -r services/offers/requirements.txt
```
Se till att din IDE (t.ex. VS Code) använder Python-interpretatorn från `.venv/`.

### Köra Projektet Lokalt med Docker Compose

De flesta backend-tjänster och deras beroenden (PostgreSQL, Redis, Kafka etc.) kan startas lokalt med Docker Compose:
```bash
docker-compose up -d
```
Detta kommer att starta de tjänster som definieras i `docker-compose.yml`. Individuella Python-tjänster (som `offers-api`) körs ofta med `uvicorn --reload` inuti sina containers för live-uppdatering av kod.

Se `docker-compose.yml` för detaljer om vilka tjänster och portar som exponeras.

### Köra Admin UI Lokalt

Navigera till `services/admin_ui` och följ instruktionerna i dess `README.md` (vanligtvis `pnpm install` följt av `pnpm dev`).

### Databasmigreringar (Alembic)

För tjänster som använder databaser (t.ex. `offers`), körs migreringar med Alembic:
1.  Se till att relevant databastjänst körs (via Docker Compose, t.ex. `docker-compose up -d offers-db`).
2.  Aktivera din Python venv (`source .venv/bin/activate`).
3.  Navigera till tjänstens katalog (t.ex. `cd services/offers`).
4.  Kör migreringar:
    ```bash
    alembic upgrade head
    ```

## Testning

*   **Python-tester:** Körs med Pytest från projektets rot (med aktivt venv):
    ```bash
    pytest
    ```
*   **Admin UI-tester:** Körs från `services/admin_ui`-katalogen (se dess `package.json` för test-skript, oftast `pnpm test`).

## Infrastruktur & Deployment

*   **Terraform:** Hanterar molninfrastruktur (AWS). Se `infra/tf/envs/` för staging och produktion.
*   **Helm:** Används för att paketera och deploya applikationer till Kubernetes. Charts finns under `infra/helm/`.
*   **Linkerd:** Används som service mesh. Applikationer annoteras för Linkerd-injektion.

## Bidra

[Information om hur man bidrar, kodstandarder, PR-process etc. kan läggas till här.] 