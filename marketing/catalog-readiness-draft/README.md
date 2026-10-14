# Catalog Readiness Report: beslutsunderlag

9 september 2026. **Privat utkast. Inte en lanserad produkt.**

## Rekommendation

Sälj en tydlig leverans, inte möjligheten att få ett bud: en manuellt granskad
sammanställning av katalogens intäktsunderlag, dokumentluckor och nästa steg.
Behåll kalkylatorn, Apply och SPACE:s första köpgranskning gratis. Ingen
förmånsbehandling, bättre budnivå eller snabbare köpgranskning ingår vid betalning.

**Börja med högst fem manuella pilotleveranser, efter godkända lanseringsvillkor.**
€99 är en oprövad prishypotes för lärande, inte ett bevisat lönsamt standardpris.
Vid de uttryckliga kostnadsantagandena i previewn återstår cirka €21,47 efter
60 minuters arbete men cirka -€1,03 efter 90 minuter. €149 ger cirka €35,22 vid
90 minuter. Ingen av dessa kalkyler är en offert från Stripe eller en skattebedömning.
Varje modellerad kostnadsrad avrundas till cent, så att de synliga delarna och
slutsumman stämmer överens. Detta är en planeringsmodell, inte bokföringsprogram.
Avgiftsantagandet är inte ett garanterat tak; valutaväxling, utländska kort och
andra betalprodukter kan ge högre kostnad. Stresstesta det med kontots verkliga
villkor före försäljning, inte med en antagen svensk standardtariff.

Rekommenderad prisstrategi: erbjud ett enda avgränsat paket. Testa inte ett
abonnemang, tre konstruerade nivåer eller en automatisk värdering. Om kunderna
inte ser ett eget värde i rapporten utanför SPACE:s köpgranskning, lansera inte.

## Granska i denna ordning

1. [Erbjudandet](http://127.0.0.1:4186/): engelskt erbjudande med en tydlig gratisväg.
2. [Exempelrapporten](http://127.0.0.1:4186/sample.html): full rapport, med enbart syntetiska data.
3. [Beslutsvyn](http://127.0.0.1:4186/review.html): svensk genomgång och justerbar kostnadskalkyl.
4. [Leverans och pilot](OPERATIONS.md): omfattning, arbetsflöde, kvalitetskrav och stoppregler.
5. [Betalning och lanseringsvillkor](PAYMENTS.md): Stripe, skatt, konsumentvillkor och dataskydd.
6. [Källor och faktagränser](SOURCES.md): verifierat i dag kontra föreslaget för piloten.

En PDF av samma exempelrapport byggs till
`output/pdf/space-catalog-readiness-sample.pdf`. Det är ett syntetiskt exempel,
inte en riktig kundrapport, oberoende värdering eller färdig kundreferens.

## Varför någon skulle betala

Hypotesen är att en katalogägare betalar för att slippa sammanställa och tolka
ett rörigt underlag själv, och för att förstå vad som saknas inför ett samtal
med en köpare eller egen rådgivare. De betalar inte för matematiken i kalkylatorn
eller den gratis checklista som redan finns på hemsidan.

Det egna värdet ska finnas i en källspårbar sammanställning, faktiska avvikelser,
tydliga begränsningar och en användbar åtgärdslista. Att befintliga besökare har
sökt efter katalogvärde visar inte att de vill betala för just detta.

## Affärsbrief

| Område | Verifierat / arbetsantagande |
| --- | --- |
| Nuvarande verksamhet | Direkt köpare av musikrättigheter. Gratis ansökan och första granskning enligt [erbjudandepolicyn](https://spacemusic.io/pricing.md). |
| Betalande målgrupp, föreslagen | Självständiga artister, producenter och små katalogägare som har maskinläsbart intäktsunderlag men behöver ordning och förberedelse. |
| Ny leverans, föreslagen | Engelsk PDF, summerat dataunderlag och prioriterad dokumentlista; mänsklig granskning före leverans. |
| Land och språk | Engelska är befintligt publikt språk. Företagsland, skatteregistrering, köparländer och B2B/B2C-avgränsning måste bekräftas före betalning. EUR är en prishypotes. |
| Befintligt innehåll | Kalkylator, värderingsguide, dokumentchecklista och erbjudandechecklista finns redan. Ingen konkurrerande SEO-artikel föreslås. |
| Primärt verksamhetsmål | Fler kvalificerade katalogaffärer. Rapportintäkter redovisas separat; de får inte maskera färre relevanta gratisansökningar. |
| Kapacitet / kostnad | Ingen namngiven rapportgranskare, uppmätt leveranstid eller faktisk kostnad per rapport har verifierats. |
| Betalning | Ingen Stripe-connector finns tillgänglig i denna körning. Tidigare sandbox-problem är inte bevis för kontots nuvarande status. Ingen betalningslänk har skapats. |

## Vad som inte gjorts

Ingen publicering, domänändring, ny sitemapadress, ändring i Apply, betalvägg,
Stripe-produkt, betalning, testlead, kundkontakt eller automatisk utskickskampanj.
Inga verkliga kunddokument har lästs eller använts. Befintligt material och
produktionssnapshot lämnas orört. Denna preview ska inte deployas som hela SPACE.

## Godkännande som behövs

- Affär: fristående betald rapport, omfattning och fem pilotorder; separat från köpgranskning.
- Leverans: ansvarig granskare, torrkörning, kapacitet och utlovad ledtid.
- Handel: juridisk säljare, köparländer/status, pris inklusive korrekt skatt, villkor och återbetalningsrutin.
- Data/betalning: godkänd privat filkanal, rättslig grund och lagring, fungerande Stripe live och verifierat testflöde i sandbox.

Detta är separata beslut. Ett godkännande av designen aktiverar inte betalning.

## Köra lokalt

```sh
node marketing/catalog-readiness-draft/build.mjs
node --test marketing/catalog-readiness-draft/model.test.mjs
node marketing/catalog-readiness-draft/serve.mjs
```

Servern lyssnar endast på `127.0.0.1:4186`, levererar endast previewmappen,
returnerar noindex och accepterar inga inskickade data. `PORT` kan väljas vid
portkonflikt. Kundunderlag hör aldrig hemma i detta repo eller previewmappen.

## Bygga om PDF och kontroller

De färdiga statiska PDF-typsnitten ligger i `font-assets/`, härledda från repots
OFL-licensierade Inter. Originallicensen kopieras till `preview/fonts/OFL.txt`.
Webbsidorna använder den lokala variabla Inter-filen; PDF använder inbäddade
statiska instanser för tillförlitlig rendering. Ingen extern font behövs vid läsning.

```sh
npm install --prefix tmp/catalog-readiness-tools --no-save --ignore-scripts --package-lock=false axe-core@4.10.3
node marketing/catalog-readiness-draft/check-browser.mjs
/Users/emilsoujeh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 marketing/catalog-readiness-draft/check-pdf.py
node marketing/catalog-readiness-draft/verify-package.mjs
```

Webbkontrollen genererar PDF och kopierar dess fyra syntetiska datafiler till
`output/pdf/space-catalog-readiness-evidence/`. Fontombyggnad behövs inte normalt;
`prepare-print-fonts.py` använder fontTools 4.60.1 och Brotli 1.1.0, lokalt
installerade i `tmp/catalog-readiness-python` under denna körning.

Kontrollresultat och kvarvarande begränsningar dokumenteras i `QA.md`.
