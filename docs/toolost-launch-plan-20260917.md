# SPACE Catalog Review: integrations- och lanseringsplan

Datum: 17 september 2026. Status: beslutsunderlag, inte en implementation eller ett publiceringsgodkännande.

## 1. Beslut i korthet

Bygg en sammanhängande privat kataloggranskning i SPACE:s befintliga design.
Too Lost blir en frivillig datakälla, inte ett krav för att ansöka och inte en ny
distributör, betalningsförmedlare eller automatisk katalogköpare.

Prioriteringsordning:
1. Godkänt användningsområde, säkra datagränser och tydlig designpreview.
2. Produktionsduglig privat portal och tillförlitlig koppling till dagens ansökningar.
3. Läsbaserad Too Lost-import med källspårning och manuell granskning.
4. Begränsad produktionspilot med separat godkännande.
5. Eventuell fristående betald rapport, först efter kommersiellt klartecken.

Definitionen av premium är att användaren förstår nästa steg, ser vad som är
känt respektive saknas och kan återkomma utan att förlora arbetet. Inte fler
dashboardkort, animerade belopp eller en påhittad värderingspoäng.

## 2. Verifierat nuläge och vad som saknas

| Område | Observerat | Konsekvens |
| --- | --- | --- |
| Publik release | `marketing/RELEASE.md` anger `55284dbb`, artefakt `tmp/editorial-preview-v5-20260916`, 141 sitemapadresser. | Denna är baslinjen, inte en äldre designpreview. Kontrollera på nytt före implementation och publicering. |
| Konverteringspreview | `fa09e20b`, artefakt `tmp/conversion-preview-v3-20260917`, är inte produktion. | Separat godkännande och prestandagrind; ingår inte automatiskt i detta projekt. |
| Design | `.impeccable.md`: Inter, återhållsam redaktionell layout, mörk text, ljusa ytor och blå handlingar. | Återanvänd befintlig identitet och ordmärke; inget parallellt designsystem. |
| Ansökningar | Publika Apply använder Typeform med kortformsalternativ. Repo innehåller separat signerad Typeform-notifiering till Resend. | Behåll fungerande inskickning. Notifieringens databas är inte ett komplett lead- eller katalogregister. |
| Privat portal | `services/spacemusic/portal/` är uttryckligen lokal, med SQLite, testidentiteter och testgranskare. Produktionsstart blockeras. | Den får inte bara flyttas till publik hosting. Produktionsgrund måste byggas och granskas. |
| Historisk portalbeskrivning | Delar beskriver fortfarande Formspree som huvudflöde. | Utgå från aktuell Typeform-release, inte historiska integrationsantaganden. |
| Betald rapport | `marketing/catalog-readiness-draft/` är ett privat utkast, inte en lanserad produkt. | Återanvänd metod och exempel, inte gamla pris- eller lanseringsantaganden. |
| Too Lost-ansökan | Användaren har visat `SPACE Catalog Review`, sandbox, pending. | Ingen verifierad sandbox- eller produktionsåtkomst. |
| API-avtal | Tre sidor, tillhandahållet av användaren, Effective Date 17 september 2026. | Avtalet styr användning; dokumentet i sig bevisar inte godkänd produktion eller ett utökat användningsfall. |
| Callback | Planerad registrering: `https://spacemusic.io/api/integrations/toolost/callback`. Ingen implementation hittad. | Bygg exakt denna adress eller få registreringen ändrad innan OAuth-test. |
| Affär | Ingen uppmätt betalningsvilja, granskningskostnad eller aktuell Stripe-liveverifiering i detta arbete. | Inga intäktsprognoser eller betalaktivering utan separat kontroll. |

Lokala källor: `marketing/RELEASE.md`, `marketing/conversion-20260917/README.md`,
`services/spacemusic/portal/README.md`, `marketing/typeform-intake/notification-worker/`,
`marketing/catalog-readiness-draft/README.md`, `docs/valuation-policy.md`.

## 3. Får SPACE tjäna pengar på integrationen?

**Bedömning:** en betald tilläggstjänst kan vara en affärsmöjlighet, men avtalet
ger inte ett generellt tillstånd att sälja API-data eller använda den till vilken
analys som helst. Att någon godkänner OAuth eller att vi betalar för API-anrop
ersätter inte Too Losts godkännande av användningsområdet. Detta är en
avtalsgenomgång för planering, inte ett juridiskt klartecken.

### Avtalsgränser som påverkar produkten

| Hänvisning i användarens API Developer Agreement | Innebörd för planen |
| --- | --- |
| §2, sida 1 | Produktionsåtkomst kräver Too Losts granskning och godkännande. Sandbox är en separat grind. |
| §4 Fees, sida 1 | Debiteringsmodellen börjar gälla vid produktionsanrop; aktuella priser och kvoter måste kontrolleras. Sandbox är normalt obetald men avtalet tillåter annan skriftlig/portalbaserad uppgift. |
| §4 Representations, sida 1 | Vi ansvarar för nödvändiga rättigheter, information och tillstånd. Dokumentet har två avsnitt numrerade 4; hänvisa även till rubriken. |
| §5 och §11 | Ansvar och skadeslöshetsåtaganden ligger i betydande utsträckning på utvecklaren; API-data garanteras inte vara komplett, korrekt eller tillgänglig. Jurist bör granska ansvarsfördelningen. |
| §6(C), sida 2 | Datainsamling och bulkimport måste omfattas av det uttryckligen godkända användningsfallet. Ingen generell katalogharvesting. |
| §6(D), sida 2 | Säkerhets-, belastnings-, benchmark- och liknande tester mot deras API kräver föregående skriftligt tillstånd. Kör sådana tester mot våra egna miljöer och simulatorer. |
| §7 | Skydda åtkomstuppgifter, begränsa åtkomst och ha en process för incidenter och återkallande. |
| §8, sida 2 | API-data får bara användas för godkända ändamål. Vidareutlämning och användning för bland annat profilering, automatiserade beslut, modellträning och enrichment kräver uttryckligt tillstånd enligt avsnittets villkor. |
| §9, sida 2 | Väsentliga ändringar av produkt, databehandling, aktörer eller användningsfall behöver anmälas och fortsatt tillgång är föremål för godkännande. |
| §10 | Vi behöver kunna visa datakarta, behörigheter, lagring, säkerhet och efterlevnad. |
| §14, sida 3 | Dokumenten har en uttrycklig företrädesordning. Allmänna portaltexter ersätter inte API-avtalets begränsningar. |

Vi utgår **inte** från att en härledd PDF, aggregerad statistik eller mänsklig
slutgranskning automatiskt undantar oss från §8. Även tänkta nyckeltal,
riskindikatorer, kombination med kunddokument och visning för kunden ska beskrivas.

### Rekommenderad affärsmodell

| Spår | Kundvärde | Beslut |
| --- | --- | --- |
| Gratis köpgranskning | Mindre manuellt arbete för kunden och bättre underlag för SPACE:s möjliga katalogköp. | Första prioritet. Förtydliga för Too Lost att SPACE kan vara köpare och använder underlaget för mänsklig köpgranskning. |
| Catalog Readiness Report | Avgränsad, källspårbar sammanställning och dokumentluckor som kunden har nytta av även utan försäljning till SPACE. | Bäst kandidat för en betald pilot, men endast efter uttryckligt godkänt kommersiellt användningsfall. |
| Löpande katalogbevakning för skivbolag | Återkommande avstämning och rapportering när underlaget ändras. | Senare hypotes. Kräver återkommande nytta, godkänd synkfrekvens och separat avtalsbedömning. |
| Förmedling till andra köpare | Möjlig separat affär, men externa mottagare och intressekonflikter tillkommer. | Ingår inte. Inga delade leads eller rapporter till köpare/mäklare utan nödvändiga avtal och tillstånd. |
| Återförsäljning av rådata, annonsprofiler eller träning av AI-modeller | Inte nödvändigt för kunduppgiften. | Ingår inte; behandlas inte som tillåtet av standardåtkomsten. |

En eventuell betald rapport får aldrig bli ett villkor för ett kostnadsfritt
köpbud, ge påstått bättre bud eller marknadsföras som oberoende om SPACE är en
potentiell köpare. Vi tar betalt för verifierbar arbetsinsats och leverans, inte
för en gratis miniräknare, API-åtkomst i sig eller ett löfte om katalogvärde.

### Skriftliga besked att begära från Too Lost

1. Godkänns användarinitierad katalog- och royaltyimport till SPACE för manuell köpgranskning?
2. Godkänns en separat betald readiness-rapport till den anslutna katalogägaren, även om ingen försäljning sker?
3. Vilka beräkningar, avstämningar och eventuella indikatorer får vi göra; vad betraktar ni som profilering eller enrichment?
4. Får normaliserad data och rapporter sparas, hur länge, och vad ska raderas vid frånkoppling eller återkallad API-åtkomst?
5. Vilka angivna drift-, lagrings-, e-post- och eventuella betalningsleverantörer får hantera respektive datakategori?
6. Vilken volym, historik, paginering och uppdateringsfrekvens godkänns för en individuell import respektive löpande tjänst?
7. Krävs ett uppdaterat användningsfall och separat produktionsansökan? Vilka vanliga sandbox-funktionstester omfattas av godkännandet?

Inget mejl skickas och inga avtal accepteras genom denna plan.

## 4. Omfattning för första versionen

**Ingår:** säker inloggning, ett privat arbetsutrymme per ansökan, frivillig
Too Lost-koppling, dokumentväg för andra distributörer, importgranskning,
tydlig datatäckning, versionsmärkt inskickning och mänskliga kompletteringsfrågor.

**Ingår inte:** ändringar av releaser, ljudnedladdning, distributionsflytt,
royaltyutbetalningar, automatisk värdering, automatiska avslag, lånebeslut,
marknadsplats, investerarportal, AI-träning eller betalvägg framför Apply.

En betalprodukt är en separat andra release. Ingen ny betald prenumeration eller
API-plan köps automatiskt. Befintlig pipeline för erbjudanden och utbetalningar
kopplas inte in av misstag när portalen driftsätts.

## 5. Användarresa och konkreta skärmar

Föreslagna skärmnamn och knappar är på engelska, i linje med webbplatsen.

| Steg | Skärm och primär handling | Vad användaren ska förstå |
| --- | --- | --- |
| 1 | Befintlig Apply, oförändrad | Kostnadsfri första granskning. Inget Too Lost-konto krävs. |
| 2 | Privat inbjudan: Continue your catalog review | Ansökan är mottagen. Säker länk öppnar rätt ansökan efter identitetskontroll. |
| 3 | Choose how to add your catalog | Connect Too Lost eller Add statements instead; ingen distributör får presenteras som ett behörighetskrav. |
| 4 | Before you connect | Exakt vilken data som hämtas, syfte, vem som får se den och hur kopplingen tas bort. Ingen lösenordsruta för Too Lost på SPACE. |
| 5 | Too Losts godkännandesida | Separat extern autentisering med minsta godkända läsbehörigheter. |
| 6 | Confirm connected account | Visa verifierad kontobeteckning och bekräfta koppling till rätt SPACE-ansökan. Fel konto kan avbrytas utan import. |
| 7 | Importing your catalog | Verkliga etapper: katalog, royaltyhistorik, avstämning. Antal först när känt; inga fabricerade procent eller sluttider. |
| 8 | Review imported information | Källor, datum, tillgängliga månader, valuta och luckor. Importerat betyder inte rättighetsverifierat. |
| 9 | Choose what you want reviewed | Markera befintliga releaser/rättigheter. Framtida musik är inte automatiskt inkluderad. |
| 10 | Rights and documents | Ägarandelar, avtal och oklarheter kompletteras av kunden. Okänt är ett tillåtet svar, inte noll eller automatiskt avslag. |
| 11 | Review and submit | En sammanfattning av exakt den version kunden skickar in; en tydlig slutknapp. |
| 12 | Under review / Information requested | Status och eventuella frågor i samma arbetsutrymme, med säker återkomst via mejl. |
| 13 | Connection settings | Senaste lyckade import, behörigheter, frånkoppling och separat begäran om radering. |

Portalinbjudan får inte vara en oskyddad länk med bara ett ansöknings-ID. Samma
e-postadress i SPACE och Too Lost får inte ensam användas som behörighetsbevis.
En manager kan ha en annan adress; det är ett tydligt verifierat medlemskap och
auktoriserad ansökan som binder data till rätt arbetsutrymme.

## 6. Designspecifikation

- Återanvänd Inter och det godkända SPACE-ordmärket; inga nya fonter eller generiska avatarer.
- Vit huvudyta, diskreta pappersgrå paneler, mörk text och återhållsamma blå huvudhandlingar.
- Desktop: läsbar arbetsyta, cirka 960-1120 px; en kolumn för frågor och dokument, tabell först där jämförelse behövs.
- Mobil: samma uppgifter och handlingar i en kolumn. Breda tabeller får namngiven horisontell rullning, inte gömt innehåll.
- En huvudhandling per steg. Tillbaka, spara och avbryt är tydliga men konkurrerar inte visuellt.
- Synligt sparläge: Saving, Saved och Could not save. Bekräfta aldrig sparande före serverns svar.
- Fel beskriver vad som hände och nästa val. Inmatning och tidigare lyckade importer ligger kvar.
- Visa datatäckning som exempelvis "8 reported months; 4 months not confirmed", inte en påhittad kvalitetspoäng.
- Använd statusorden Imported, Needs clarification och Reviewed med skilda betydelser. Ingen grön VERIFIED-stämpel efter bara ett API-anrop.
- Stöd tangentbord, synlig fokus, 200 % zoom, reducerad rörelse och skärmläsare; mål WCAG 2.2 AA.
- Vanlig text ska nå minst 4,5:1 kontrast, relevanta kontrollgränser 3:1 och viktiga tryckytor minst 44 x 44 px som produktkrav. [S8]
- Behåll synliga fältetiketter. Statusmeddelanden annonseras utan att stjäla fokus.
- Ingen autoplay, nedräkning, falsk brådska, bakgrundsglöd eller dekorativ diagramdata.

Leverans före backendkoppling: klickbar preview av lyckat flöde, fel konto,
avbruten OAuth, utgången session, tom katalog, delvis import och saknade dokument.
Alla visade belopp är syntetiska och tydligt märkta. Inga verkliga leaduppgifter
eller avtal används på en publik previewadress.

## 7. Arkitektur och isolering från marknadssajten

Rekommenderad teknisk riktning är ett isolerat privat portal/API-system som
återanvänder det granskade FastAPI-grundarbetet, inte hela den äldre seller-API:n.
Den faktiska produktionshosten väljs först efter kostnads- och driftbeslut.

```text
Befintlig Apply / Typeform / kortformsalternativ
  -> befintligt mottagande och notifiering fortsätter
  -> verifierad, idempotent ansökningshändelse
  -> privat ansökan och säker portalinbjudan

SPACE /workspace/ + egna /api/portal/*
  -> autentisering, medlemskap, behörighetskontroll
  -> /api/integrations/toolost/*
  -> provideradapter: mock | sandbox | production
  -> beständig importkö -> validering -> versionsmärkt underlag
  -> mänsklig granskning -> privat rapport, om separat godkänd
```

Föreslagen hostinggräns: ett separat driftsatt backend bakom smala regler för
nya `/workspace/`, `/api/portal/` och `/api/integrations/toolost/`-vägar.
Den exakta registrerade callbacken måste gå direkt till backend, aldrig falla
tillbaka till marknadssajtens SPA. Ingen catch-all som tar över befintliga SEO-sidor.

Använd en hanterad relationsdatabas med transaktioner, privat objektlagring,
hanterade hemligheter och en beständig jobbkö. PostgreSQL är förstahandsförslag
för portalens normaliserade data; dagens notifierings-D1 hålls separat.
Leverantör, region, personuppgiftsbiträdesvillkor, krypteringsnycklar och
backupkostnad ska godkännas. Lokal SQLite eller publik Pages-lagring får inte
bli kunddatabas av bekvämlighet.

Utveckling, staging och produktion har separata klienter, nycklar, databaser,
lagringsytor, köer och mejlinställningar. Mockmiljön har inga API-nycklar och
får inte göra utgående anrop till Too Lost. Fixtures eller testgranskare får inte
finnas i produktionsentrypointen.

## 8. Befintliga leads får inte tappas

Typeform fortsätter vara mottagare för befintlig guided form. Vi lägger inte till
en andra klient-POST till ett nytt leadregister. Typeforms inskickade svar och
dess signerade händelse är grunden, inte webbläsarens completion-event.

Planerad förändring, först efter separat regressionstest: notifieringsgränsen
utökas med en beständig vidareleverans till portalens ingest. Den får en egen
kö/outbox och egna försök, skilda från befintlig Resend-leverans. Ett portalavbrott
får inte stoppa mottagandet eller det nuvarande notifieringsflödet.

- Verifiera Typeforms signatur på ursprunglig body, förväntat formulär och händelsetyp.
- Använd unik nyckel på källa + formulär + svarstoken; samma persons nya ansökan är inte automatiskt en dubblett.
- Signera server-till-server-vidareleverans med separat hemlighet, tidsfönster och idempotens-ID.
- Spara portalansökan och inbjudningsoutbox atomiskt. Bekräfta bara en beständigt registrerad händelse.
- Reconciliationsjobb jämför mottagna händelser mot källans svar, om erforderlig Responses API-åtkomst finns. Annars dokumenteras en operatörsdriven kontroll före pilot.
- Kortformsalternativets mottagare behöver en egen verifierad adapter; anta inte att Typeform täcker dess leads.
- Kunden får aldrig två portalansökningar eller två inbjudningar av samma händelse trots återförsök.
- Bevara nuvarande mottagare. Äldre leads importeras inte i bulk utan avgränsat beslut, laglig grund och kontroll av källa.

## 9. OAuth och säker sessionshantering

Planerat flöde: Authorization Code med PKCE S256 samt confidential serverklient.
Exakta sandbox-auktoriserings- och tokenadresser måste verifieras; att bara byta
API-basadress är inte en godtagbar miljöväxling. [S2, S3]

Krav:
- Start kräver inloggad SPACE-användare, rätt ansökningsmedlemskap, POST och CSRF-skydd.
- Servern skapar kortlivad, engångsanvänd OAuth-transaktion bunden till session, workspace, provider, miljö och fast redirect URI.
- State är kryptografiskt slumpmässig och kontrolleras atomiskt vid callback; PKCE-verifier lagras skyddat på serversidan. Ingen godtycklig return_url.
- Access- och refresh-token lagras krypterade med hanterad nyckel, separerat från databasen. Endast digest för hemligheter som inte behöver återläsas.
- Sessionscookies är Secure, HttpOnly och hostbegränsade. Callbackens cross-site toppnavigation utformas uttryckligen med lämplig SameSite-hantering; dagens lokala Strict-regler får inte brytas genom generell CORS-uppluckring.
- Alla mutationer har origin- och CSRF-kontroll. Tillåt den avsedda callbacknavigationen, inte godtyckliga cross-site anrop.
- Ingen kod, token, rå callback-query eller känslig body i CDN-, backend-, fel- eller analysloggar. Callbacken har ingen analytics eller tredje parts script.
- Efter kodutbyte används en ren redirect till portalen med ett ofarligt status-ID. Cache-Control no-store och Referrer-Policy no-referrer.
- Bekräfta verifierad provideridentitet före dataimport. Koppla aldrig konton på endast en inskriven e-postadress.
- Lås samtidig tokenförnyelse per koppling och spara eventuell roterad refresh-token atomiskt. Okänt resultat får inte orsaka obegränsad replay av engångskoder.
- Hantera avslag, återanvänd kod, state-mismatch, utgången session och delvis beviljade scopes med säkert stopp och möjlighet att börja om.
- Frånkoppling stoppar nya och köade anrop, tar bort lokala tokens och återkallar hos leverantören om en verifierad revocation-mekanism finns. Påstå inte att leverantörens åtkomst återkallats om endast lokal koppling tagits bort.

Säkerhetsreferens: [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) och
[OWASP OAuth](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html).
Testa vår klient och våra simulatorer. Tester riktade mot Too Lost omfattas av
avtalets särskilda skriftliga tillståndskrav, även om klienten i sig har sandbox.

## 10. API-kontrakt och minsta behörigheter

De generiska scopebeskrivningarna i ansökan är inte tillräcklig specifikation.
Vid granskning av den publika referensen framkom följande. [S2]

| Anrop | Dokumenterat krav / detalj | Plan |
| --- | --- | --- |
| `GET /me` | `read:profile` | Läs minsta identifieringsuppgifter för att bekräfta anslutet konto. |
| `GET /releases` och `GET /releases/{releaseId}` | `read:releases`; listan använder `page` och `perPage`, max 100. | Importera godkända metadata. Beviljat `read:catalog` antas inte automatiskt ge denna rätt. |
| `GET /releases/{releaseId}/tracks` | Endpoint finns i referensen. | Verifiera exakt schema/scope och använd bara om nödvändiga spårfält inte redan ingår. |
| `GET /sales/overview` | `read:sales`; `page` och `per_page`, max 100; månader i fallande ordning. | Importera redovisade månader med tydlig täckning. Notera skillnaden mot `perPage`. |
| `/sales/tracks`, `/sales/releases` och visade breakdown-rutter | Grupperna anger `read:sales`. | Hämta endast nödvändiga breakdowns efter verifierat periodfilter och schema. |
| Analytics, audience, preferences och skrivoperationer | Finns men behövs inte för första versionen. | Avstängda och inte begärda. |

Arbetsförslag för scopes är alltså `read:profile`, `read:releases` och
`read:sales`, med andra lässcope bara om endpointinventeringen visar ett behov.
Detta är en rättelse/förfining av den tidigare bredare rekommendationen, inte en
ändring av inskickad ansökan. Too Lost måste bekräfta beviljade scopes.

Före kodgenerering ska den officiella fullständiga OpenAPI-specifikationen
hämtas via dess publicerade exportväg och versionsmärkas med datum och checksumma.
Använd ett litet granskat HTTP-lager, inte ett otestat community-SDK som
auktoritativt kontrakt. Diffa specifikationen manuellt inför uppdateringar.

**Öppna semantiska frågor:** overview-exemplet visar `date` och `total`, men
ingen valuta eller tydlig definition av gross/net/utbetalt. Detta måste förklaras
av leverantören. Ingen USD-standard, tillgänglig kontantsumma, nettoägarsandel,
12-månadershistorik eller slutgiltig avräkning får antas utifrån exempelvärdet.

Hämta inte artwork, ljudfiler, kontraktslänkar eller annan rådata bara för att
URL:er finns i ett svar. Ingen serverfetch av kundstyrda externa URL:er. Normalisera
endast en allowlist av behövda fält; kasta okända/känsliga extrafält ur vår vy.

## 11. Import, beräkningsregler och datakvalitet

Importen körs som återupptagbara serverjobb. En webbläsarstängning får inte tappa
jobbet och en omladdning får inte starta om hela importen.

- En aktiv import per koppling/omfattning, med idempotensnyckel, worker-lease och checkpoint.
- Läs faktisk paginering, stoppa vid dokumenterat slut och upptäck upprepade sidor, ändrade totalsiffror och maxsidgränser. Inget antagande om en enda sida.
- Förvissa oss om att omfattning och hämtad historik ryms i godkänt användningsfall; större import kräver uttryckligt beslut, inte obegränsad loop.
- Validera datatyper, perioder, identiteter och schema. Saknat fält är okänt, inte noll. Ny eller bruten struktur ger kontrollerat stopp, inte felaktig rapport.
- Spara decimalbelopp utan binära flyttalsfel. Bevara källans precision vid import och definiera avrundning först vid presentation.
- Separera intjänandeperiod, rapportperiod, hämtningstid och utbetalningsdatum. "Senaste tolv månader" betyder inte tolv godtyckliga tillgängliga rader.
- Redovisa delvis rapporterade månader och sena justeringar. Skapa ny version vid ändringar; tidigare rapporter behåller sin versionsreferens tills lagringspolicyn kräver radering.
- Blanda inte valutor. Ingen FX i v1; visa separat per verifierad valuta. Okänd valuta blockerar monetär slutsats.
- Ta inte bort negativa belopp eller återföringar. Avstämningsdifferenser ska synas, inte döljas genom avrundning eller nollning.
- Koppla med provider-ID och rätt datakontext. ISRC eller låttitel ensamt är inte ett unikt ägar- eller intäktsbevis; samma inspelning kan finnas på flera releaser.
- Summera inte track-, release-, kanal- och territorieaggregat ovanpå varandra. De är alternativa uppdelningar av samma underlag, inte extra intäkter.
- Håll kontoöversikt skild från kundens valda releaser. Om valda spår inte kan avgränsas tillförlitligt visar vi inte hela kontots intäkter som det urvalets värde.
- Lägg inte API-import och uppladdad export för samma period på varandra. Använd dem för avstämning med konfliktmarkering.
- Kontobehörighet och providerdata bevisar inte juridiskt ägande, överlåtbarhet, avsaknad av samägare eller att inkomsten är fri från återkrav.

De första redovisningarna är en källsammanställning, inte en värderingsmodell.
Tillåtna summeringar och avstämningar ska ingå i Too Losts godkända användningsfall.
Ingen automatisk riskprofil, segmentering av personer, budnivå eller finansierings-
rekommendation lanseras genom att kalla den en indikator.

## 12. Privat datamodell och granskningsspår

| Objekt | Syfte och integritetskrav |
| --- | --- |
| Workspace och membership | Separat, verifierad åtkomst för ägare och utsedd granskare. Ingen implicit åtkomst via delad e-post eller gissat ID. |
| Application | Källreferens, mottagningstid, känt publikt source path och egen review-status. |
| Connection | Provideridentitet, miljö, beviljade scopes, krypterad tokenreferens och anslutningsstatus. |
| Consent/use-case record | Version av kundinformationen, godkänt ändamål, tidpunkt och hanterad behörighet. OAuth-godkännande är inte samma sak som all rättslig grund. |
| Import run | Omfattning, checkpoint, sidantal, kontraktsversion, datatäckning, kostnadsräknare och säkra felkoder. |
| Evidence snapshot | Minimerad källdata med hämtningstid och checksumma inom godkänd lagringstid; inte oändlig rådump. |
| Normalized facts | Belopp, valuta, period och källa; härledningar kan följas tillbaka till sina ingångsvärden. |
| Document | Privat objektreferens, checksumma, version, scanstatus och rättighetskontroll för läsning. |
| Submission/review | Låst inlämnad version, granskare, frågor och dokumenterat beslut. |
| Report/order, senare | Separat produkt, godkänd omfattning, betalningsstatus och versionsmärkt leverans; inget automatiskt bud. |
| Audit/outbox/deletion | Åtkomstspår, beständiga notifieringar, raderingsjobb och hanterade lagliga lagringsundantag. |

Varje kundobjekt är knutet till workspace. Kontroller sker i API och jobbworker,
inte bara i UI. RLS eller motsvarande databasskydd används som extra barriär och
testas med två konton. Revisionsloggar minimerar känsligt innehåll; append-only
betyder inte obegränsad lagring av personuppgifter.

Separata tillståndsmaskiner:
- Koppling: disconnected, authorizing, connected, reauth_required, revoked.
- Import: queued, running, partial, complete, blocked, failed, cancelled.
- Granskning: draft, submitted, needs_information, under_review, completed.
- Dokument: quarantined, scanning, accepted_for_review, rejected.

"Import complete" sätter inte "reviewed". Ett dokument som passerat säkerhets-
kontroll är inte bevisat äkta eller kommersiellt verifierat.

## 13. Filhantering, integritet och avtal

Dokumentvägen behövs för alla andra distributörer och när API-data är otillräcklig.
Använd befintligt lokalt portalflöde som prototyp, inte dess fixturegodkännande
som säkerhetskontroll i produktion.

Krav: kortlivade privata uppladdningsrättigheter, fil- och storleksallowlist,
signaturkontroll, karantän, skadlig-kod-skanning och begränsad parsermiljö. CSV-
formler neutraliseras vid export, XLSX-zipbomber begränsas och PDF får inte köra
aktivt innehåll. Inga filer till publika virusskannings- eller AI-tjänster.
Nedladdning kräver behörighet, loggas säkert och levereras som attachment eller
via kortlivad privat länk. [S5]

Före kunddata: dokumentera ansvarig juridisk part, ändamål, rättslig grund,
biträden, lagringsregioner, internationella överföringar, kundinformation,
registerutdrag, korrigering, frånkoppling och radering. Föreslagen grund är
dataminimering och ändamålsbegränsning, inte ett generellt samtycke till allt. [S6]

Retentionsmatris beslutas per kategori: OAuth-transaktion, token, arbetsunderlag,
inlämnad granskning, levererad rapport, säkerhetslogg och bokföringsunderlag.
Ingen godtycklig "sparas för alltid". Slutlig tidsgräns kräver leverantörsvillkor,
verksamhetsbehov och juridisk granskning. Radering omfattar köer, cache, filer,
normaliserade fakta och härledda rapporter där så krävs. Backup har dokumenterad
livslängd och återställning får inte återinföra tidigare begärd radering.

Frånkoppling och radering är två olika handlingar och ska beskrivas tydligt.
Om Too Lost instruerar om radering får vi inte anta att en äldre rapport är
undantagen. Eventuella lagliga bevarandekrav hanteras uttryckligen, inte som
skäl att spara hela datamängden. Inga kundunderlag i Git, publik preview,
Plausible, mejlämnen eller AI-prompter.

Granskare har namngivna konton med MFA, tilldelade ärenden och separata roller
för support, granskning och systemadministration. Inga delade adminlösenord,
ingen inloggning som kund utan ett särskilt granskat supportförfarande och
ingen åtkomst från lokala fixture-/reviewer-endpoints. Borttaget medlemskap
ska stoppa både pågående sessioner och bakgrundsjobb. Känslig export och
behörighetsändring kräver ny identitetskontroll och revisionshändelse.

## 14. Drift, kostnader och felhantering

Publika dokumentationen visar 17 september: Free 5 000 produktionsanrop/månad och
60 anrop/minut med hårt stopp; Starter $99 med 250 000 anrop och överdebitering;
Scale $999 med 3 miljoner anrop och överdebitering. Kvoten delas mellan
utvecklarkontots produktionsappar. Detta är en daterad observation, inte en
prisgaranti. Bekräfta kontots aktuella villkor innan första produktionsanrop. [S2]

V1 använder användarinitierad engångsimport och kontrollerad manuell uppdatering,
inte kontinuerlig polling. Klientens sidvisningar ska läsa lokal godkänd snapshot,
inte starta nya API-hämtningar. Återanvänd metadata som redan ingår i ett svar.

- Lägre intern anropsgräns än leverantörens, gemensam budget över workers och integrationens appar.
- Läs kvot- och Retry-After-headers; följ även betald överförbrukning, inte bara kvarvarande gratiskvot.
- Förslag: varning vid 70 %, ägarbeslut vid 85 %, pausa nya bakgrundsjobb vid 95 %. Trösklar är lokala skydd, inte garanti mot leverantörskostnad.
- Ingen automatisk uppgradering. Ett hårt beloppstak i våra jobb och en reserverad fel-/återförsöksbudget krävs på betald plan.
- `429` burst: schemalägg ny körning efter Retry-After med begränsad jitter. `quota_exceeded`: pausa för kvotåterställning/ägarbeslut, inte retry-loop.
- Timeout/5xx: begränsade återförsök med backoff. 403/schemafel: stoppa och eskalera. 401: högst ett samordnat förnyelseförsök enligt verifierat tokenkontrakt.
- Lagrade jobs har tidsgräns, lease och dead-letter-läge med manuell återstart. Systemet får inte duplicera en import när en worker dör.
- Kill switch för nya kopplingar, importer och eventuell betalning var för sig. Redan fungerande Apply ska förbli öppet vid Too Lost-avbrott.
- Separera queued, accepted by email provider, delivered och bounced. Resend-acceptans är inte inboxleverans.
- Syntetiska driftskontroller av vår egen portal. Ingen belastningstest eller säkerhetsskanning av Too Lost utan föregående skriftligt godkännande.

API-budget för en import beräknas som profil + katalogsidor + faktiskt behövda
spår-/royaltysidor + avstämning + reserverade återförsök. Det går inte att lova
ett visst antal kunder per 5 000 anrop utan uppmätta katalogstorlekar.

Incidentrutin: stoppa nya importer, isolera berörd koppling/workspace, rotera
berörda hemligheter, säkra minimerade loggar, informera ansvarig och Too Lost
enligt avtalet samt bedöm tillämpliga myndighets-/kundaviseringar. Öva på egna
testdata. Utsedd driftansvarig, backupåterställning och supportkanal krävs före pilot.

## 15. Testmatris och godkännandekrav

| Testområde | Obligatoriska fall | Godkänt när |
| --- | --- | --- |
| Identitet | Två användare, två workspaces, delad/ändrad e-post, fel konto, roll borttagen | Ingen korsläsning, inget konto kopplas genom e-postlikhet. |
| OAuth | Avslag, state mismatch, kodreplay, utgången transaktion, fel miljö/redirect, saknade scopes | Säkert stopp; inga tokens i loggar eller webbläsarlagring. |
| Tokenlivscykel | Samtidig förnyelse, roterad refresh-token, revocation, timeout | En koordinerad förnyelse, säker återanslutning och stoppade köjobb. |
| Kontrakt | Okända fält, saknade fält, ändrad datatyp, nya enumvärden, fel paginering | Kontrollerad avvikelse, aldrig tyst felaktiga summor. |
| Import | Dubbelklick, omladdning, död worker, återupptagning, ändrade sidor, mycket stor katalog | En logisk import, spårbart delresultat och budgetgräns. |
| Ekonomi | Decimaler, flera/okänd valuta, negativa belopp, saknade månader, senaste månad delvis, retrojustering | Reproducerbart facit eller uttryckligt blockerad slutsats. |
| Avstämning | Samma spår på flera releaser, konto kontra valt urval, API/exportöverlapp | Ingen dubblerad omsättning; differenser synliga. |
| Dokument | Fel ändelse/MIME, överstor fil, zipbomb, CSV-formel, skadlig PDF, fel användares länk | Karantän eller avslag; ingen kodkörning eller otillåten åtkomst. |
| Ansökningshändelser | Dubbla/omkastade webhooks, fel signatur, portal nere, kortformslead | Inget tappat eller dubblerat lead; befintlig notifiering kvar. |
| E-post | Leverantör nere, dubbelklick, länk scanneröppnas, länk används två gånger | Beständig outbox; explicita säkra engångsflöden. |
| Integritet | Export, frånkoppling, radering, backuprestore, cache och loggar | Utförd åtgärd verifierad utan att tidigare raderad data återuppstår. |
| UX | 320/390/768/desktop, tangentbord, zoom, skärmläsare, reducerad rörelse, svagt nät | Alla centrala uppgifter möjliga; bevarad inmatning och begripliga fel. |
| Återställning | Databasbackup, objektfiler, dött jobb, rollback av app | Visat återställningsprov; inga löften om RPO/RTO före mätning. |
| Betalning, senare | Simulerad framgång/avslag, asynkron betalning, dubbla events, fel belopp, refund | En order och korrekt status, aldrig upplåsning genom endast return-URL. |

Syntetiska testdata och kontrakttester körs utan Too Lost-åtkomst. Godkända
sandbox-funktionstester görs först när rättigheter finns. Skadliga, belastande
och säkerhetsrelaterade testfall riktas bara mot våra egna system/mockad provider.
Inga fiktiva leads skickas till den riktiga Typeform-mottagaren.

Definition of done för pilot: alla kritiska tester passerar; inga öppna kritiska
säkerhets-/integritetsfel eller höga fel som kan påverka belopp, åtkomst eller
mottagna ansökningar; oberoende kodgranskning av våra ändringar; verklig
backupåterställning och driftsinstruktion; begränsningar dokumenterade.

## 16. Skydda SEO och nuvarande konvertering

- Privat portal/API ska inte ingå i sitemap, indexeras eller exponera data i strukturerad markup. Auth är säkerhetsgränsen; noindex är bara indexeringsstyrning.
- Behåll alla 141 nuvarande sitemapadresser, texter, canonical, metadata, strukturerad data och interna länkar i denna integrationsrelease.
- Privat no-store/noindex måste vara snävt routat. Ingen global header över marknadssajten.
- Befintlig Apply behåller gratisväg, frågor och mottagare. Ett senare länktillägg till arbetsutrymmet är en egen testad ändring.
- Ingen Too Lost-SDK, OAuth-kod eller portalbundle laddas på startsida, artiklar eller kalkylator bara för att integrationen finns.
- Testa alla sitemap-URL:er, befintliga Apply-navigationskontroller och de 13 scenario/tracking/intake-testerna från releaseunderlaget; uppdatera inte gamla antal utan att köra aktuell suite.
- Kör tre jämförbara mobila prestandatester före/efter varje publik ändring. Utred median-LCP som ökar både över 10 % och över 250 ms.
- SEO-sidor om integrationen eller betald rapport publiceras först när funktionen verkligen finns, villkoren tillåter det och sökintentionen är granskad. Ingen ny konkurrerande värderingsguide i detta paket.
- Separat fullständig marketing-rollback och backendrollback. Behåll schema bakåtkompatibelt; en återställning får inte ta bort inskickade kunduppgifter.

## 17. Genomförande i ordning

Detta är arbetsblock med beslutspunkter, inte en utlovad kalender. Too Losts
godkännande, semantiska svar och juridisk granskning är externa beroenden.

| Fas | Leverans | Kan göras utan API-åtkomst? | Krav för nästa fas |
| --- | --- | --- | --- |
| 0. Mandat och kontrakt | Användningsfall, scopes, datakarta, avtalsfrågor, systembaslinje och godkända driftval | Ja | Ägaren godkänner avgränsningen. Kunddata/kommersiell användning hålls blockerad tills rätt tillstånd finns. |
| 1. Designpreview | Alla skärmar och felvägar i SPACE:s design, enbart syntetiska data | Ja | Mobil/tangentbordskontroll och ägarens designgodkännande. |
| 2. Privat grund | Säker identitet, databas, lagring, kö, inbjudan, revieweråtkomst och dokumentkarantän | Ja, i isolerad testmiljö | Ingen lokal testbakdörr kvar; två-kontotester, återställning och behörighetsgranskning klara. |
| 3. Provideradapter | Versionsbundet kontrakt, mockserver, OAuth-klient, normalisering och quota manager | Ja, mot simulator | Kontrakttestmatris klar; inget live-påstående. Semantiska luckor tydliga. |
| 4. Sandbox | Godkänd autentisering och lågvolym-funktionstest med tilldelade testkonton | Nej | Scope, paginering, tokenlivscykel och beloppsbetydelse verifierade; ingen obehörig testning. |
| 5. Ansökningskedja | Signerade event, idempotent portalansökan, e-post och avstämning med nuvarande intake | Delvis | Simulerade fel/replays och överenskomna riktiga testhändelser passerar utan kundpåverkan. |
| 6. Stängd produktionspilot | Förslag: 3-5 uttryckligen inbjudna katalogägare, gratis granskning och namngiven ansvarig | Nej | Produktionsgodkännande, integritet, drift och ägarens separata publiceringsbeslut. |
| 7. Öppnare lansering | Frivillig portalväg; manuellt alternativ fortsatt tillgängligt | Nej | Pilotens fel och datadifferenser åtgärdade, kostnad/arbetsinsats uppmätt. |
| 8. Betald rapportpilot | Högst fem avgränsade rapportorder som första arbetsantagande | Nej | Too Lost godkänner betald användning; juridisk säljare, pris, skatt, villkor och leveranskapacitet godkända. |

Ingen fas växlar automatiskt från sandbox till produktion. Pipeline ska kräva
separat produktionskonfiguration, godkänd scopeallowlist och aktiv kill switch-
kontroll. Planeringsarbete ger inte tillstånd att publicera eller ta betalt.

## 18. Betald pilot och ekonomi

Rekommendation: ett enda tydligt engångspaket före abonnemang. Leveransen är
en mänskligt granskad readiness-rapport med definierad dataperiod, omfattning,
källor, begränsningar, dokumentluckor och nästa steg. Inget garanterat
marknadsvärde, myndighetsgodkänd värdering eller köpbud ingår.

De tidigare lokala prisförslagen är hypoteser. Denna plan väljer inte ett nytt
offentligt pris och gör inte de gamla till godkända priser. Börja med tre
syntetiska leveransövningar, mät aktiv granskningstid, korrigeringstid och support,
och prata med möjliga kunder om rapportens fristående nytta.

```text
Täckningsbidrag per rapport =
intäkt exklusive tillämplig skatt
- betalningskostnad
- granskningstid x verklig intern timkostnad
- API/lagring/driftallokering
- support och korrigeringar
- förväntad kostnad för återbetalningar/omleverans
```

Varken API-priset eller fem testkunder visar långsiktig lönsamhet. Mät också om
betalprodukten minskar relevanta gratisansökningar eller skapar missförstånd om
budprocessen. Stoppa piloten om kunden huvudsakligen betalar för att få ett bud,
om rapporten inte har självständigt värde eller om arbetsinsatsen inte täcks.

Betalning får aktiveras först efter verifierad Stripe-livebehörighet, juridisk
säljare, köparländer/B2B-B2C, korrekt skatt och tydliga villkor. Använd hostad
betalning eller kundspecifik faktura, inte egen kortinsamling. Royaltydata får
inte skickas i betalningsmetadata. Automatisk leverans kräver verifierat
betalningsevent, belopp/valuta/orderkoppling och idempotens, inte bara en lyckad
redirect. Simulerade betalningar först. [S7]

## 19. Mätning, uppföljning och lanseringsbeslut

Primärt mål för köpgranskningen: unika manuellt kvalificerade ansökningar per
28 kompletta dagar. Kvalificering omfattar kontaktbarhet, rättigheter och
dokumenterat intäktsunderlag. Ej granskade leads redovisas separat.

Privata driftmått: anslutningsförsök/lyckade kopplingar, fullständiga/delvisa
importer, avstämningsdifferenser, supportminuter, tid till komplett underlag,
API-anrop per import, webhookkö och verifierad notifieringsstatus.

Eventuella publika analysverktyg får bara befintliga godkända, icke-känsliga
marknadsföringshändelser. I portalen används i första hand minimerad intern
driftstatistik utan kopierade tokens, belopp, mejl, katalogtitlar eller dokument.
Providerbaserad beteendeanalys eller profilering införs inte genom bakdörren.

Betalpilot följs separat: antal beställningar, faktiskt betalda order,
återbetalningar, leveransstatus och täckningsbidrag. Inget belopp eller kund-ID
behövs i Plausible. Jämför lika kompletta perioder med samma filter för SEO;
skilj ökad trafik, ändrad mätning och ändrad konvertering från varandra.

## 20. Öppna beslut och stoppvillkor

| Beslut | Ansvar före aktivering |
| --- | --- |
| Exakt godkänt köpgransknings-/rapportändamål, bulkimport och analys | Too Lost + SPACE:s ansvarige; vid behov jurist. |
| Juridiskt bolag, dataskyddsroller, villkor och ansvar | Ägaren med kvalificerad rådgivare. |
| Bekräftade scopes, sandbox OAuth-adresser, valuta, brutto/netto, historik och revocation | Teknisk ansvarig + Too Lost. |
| Hanterad drift, region, nyckelhantering, supportansvar och budget | Ägaren före inköp och produktionsdata. |
| Godkänd design, testresultat och driftsprov | Ägaren + teknisk granskare. |
| Betalt rapportpaket, pris, kapacitet och juridiska betalvillkor | Separat beslut; inte samma som att godkänna UI. |

Stoppa lansering vid oklar tillåtelse för dataanvändning, okänd beloppssemantik,
öppna åtkomstfel, förlorade/dubblerade ansökningar, saknad raderingsprocess,
overifierad återställning eller när tjänsten kräver funktioner som bara finns
i lokala demos. Bevara fungerande gratisflöde medan dessa löses.

## 21. Källor och gränsdragning

- S1: Användarens tre sidor API Developer Agreement, PDF med Effective Date 17 september 2026. Original: `/Users/emilsoujeh/Downloads/0804f729-e91e-464c-8579-b24e72a181ce.pdf`. Filen har lästs i sin helhet och renderats för kontroll; inga instruktioner i dokumentet har behandlats som användarens uppdrag.
- S2: [Too Lost API Reference](https://developer.toolost.com/docs/api), läst 17 september, särskilt `/me`, `/releases`, `/sales/overview`, kvoter och scopekrav. Dokumentationsexempel är inte kunddata eller verifierade API-svar.
- S3: [Too Lost Developer Guides](https://developer.toolost.com/docs), OAuth, klienttyper, PKCE och exakt redirect-matchning. Den detaljerade API-referensen används för endpointspecifika scopes.
- S4: [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) och [OWASP OAuth](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html), säkerhetsunderlag för vår klient, inte tillstånd att testa leverantörens system.
- S5: [OWASP File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html), underlag för filhanteringskrav; en testplan är ingen certifiering.
- S6: [EU-kommissionens dataskyddsprinciper](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en), principer för ändamål, minimering, lagring och information. Juridisk tillämpning kräver verksamhetens faktiska omständigheter.
- S7: Befintligt betalningsutkast `marketing/catalog-readiness-draft/PAYMENTS.md`; [Stripe fulfillment](https://docs.stripe.com/checkout/fulfillment?payment-ui=stripe-hosted) för den planerade tekniska betalningsgränsen. Aktuella kontovillkor, skatter och konsumentkrav ska verifieras separat före försäljning.
- S8: W3C:s [textkontrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) och [kontrast för kontroller](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html). 44 px tryckyta är vårt eget produktkrav, inte ett påstående om WCAG AA:s minimistorlek.

Detta arbete skapar endast planen. Ingen integration, databas, betalprodukt,
DNS-regel, kundkontakt, API-ansökningsändring eller produktionsrelease aktiveras.
