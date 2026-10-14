import { mkdir, readFile, writeFile, copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import {
  syntheticRows,
  summarize,
  sampleDefinition,
  scenario,
  economics,
  planningAssumptions,
} from "./model.mjs";

const root = path.dirname(fileURLToPath(import.meta.url)),
  out = path.join(root, "preview");
await mkdir(path.join(out, "fonts"), { recursive: true });
await copyFile(
  path.resolve(root, "../design/fonts/inter-latin-c940764593d0.woff2"),
  path.join(out, "fonts/inter.woff2"),
);
await copyFile(
  path.resolve(root, "../design/fonts/inter-OFL.txt"),
  path.join(out, "fonts/OFL.txt"),
);
for (const name of ["styles.css", "model.mjs", "review.mjs"])
  await copyFile(path.join(root, name), path.join(out, name));
for (const weight of [400, 550, 650, 700]) {
  await copyFile(
    path.join(root, "font-assets", `inter-print-${weight}.ttf`),
    path.join(out, "fonts", `inter-print-${weight}.ttf`),
  );
}
const e = (v) =>
  String(v).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const euro = (cents) =>
  new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(cents / 100);
const euro2 = (euros) =>
  new Intl.NumberFormat("sv-SE", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(euros);
const months = sampleDefinition.monthlyEuros.map(
  (_, i) => `2025-${String(i + 1).padStart(2, "0")}`,
);
const rows = syntheticRows(),
  totals = summarize(rows, months);
const monthLabels = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const sourceLinks = `<a href="https://spacemusic.io/pricing.md">Current free-review policy</a> · <a href="https://spacemusic.io/blog/music-catalog-sale-documents-checklist/">Seller document checklist</a> · <a href="https://spacemusic.io/blog/music-catalog-offer-checklist/">Offer checklist</a>`;
const header = (active) =>
  `<div class="draft-strip" lang="en" role="region" aria-label="Concept status">PRIVATE CONCEPT · Proposed service, not available to buy. No payments or uploads.</div><a class="skip" href="#main" lang="en">Skip to content</a><header class="site-header wrap" lang="en"><div class="brand-group"><a class="wordmark" href="./index.html" aria-label="SPACE report concept home">SPACE</a><span class="brand-subtitle">Catalog<br>Readiness</span></div><nav class="nav" aria-label="Main navigation"><a href="./index.html#the-report"${active === "offer" ? ' aria-current="page"' : ""}>The report</a><a href="./sample.html"${active === "sample" ? ' aria-current="page"' : ""}>Sample report</a><a href="./review.html"${active === "review" ? ' aria-current="page"' : ""}>Owner review</a></nav></header>`;
const footer = `<footer class="end-note wrap" lang="en"><p>SPACE is a direct catalog buyer. This optional service is a proposal, not an independent valuation or a purchase offer. The existing free review stays free.</p><nav aria-label="Footer"><a href="./sources.html">Sources &amp; boundaries</a><a href="https://spacemusic.io/apply/">Existing free Apply</a></nav></footer>`;
const page = (title, active, body, { lang = "en", script = false } = {}) =>
  `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="no-referrer"><meta name="description" content="Private SPACE Catalog Readiness Report concept. Proposed service and explicitly synthetic example. Not available for purchase."><title>${e(title)} | SPACE private draft</title><link rel="icon" href="data:,"><link rel="stylesheet" href="./styles.css"><link rel="preload" as="font" type="font/woff2" crossorigin href="./fonts/inter.woff2">${script ? '<script type="module" src="./review.mjs"></script>' : ""}</head><body>${header(active)}${body}${footer}</body></html>`;

const landing = `<main id="main" class="wrap"><section class="hero"><div class="reveal"><p class="eyebrow">A report you can take with you</p><h1>Know your catalog.<br>Before you sell.</h1><p class="intro">Your royalty records, explained. Your document gaps, made visible. A practical next step, whether you sell to SPACE, someone else, or not at all.</p><div class="actions"><a class="button" href="./sample.html">Read the sample report <span aria-hidden="true">↗</span></a><a class="text-link" href="#scope">See the proposed scope</a></div><p class="hero-note">Proposed paid report. Not a valuation or a purchase offer.<br>Just want a SPACE offer? <a href="https://spacemusic.io/apply/">Start with the existing free review.</a></p></div><div class="reveal delay"><aside class="report-object" aria-label="Extract from the synthetic sample report"><div class="object-head"><b>SPACE</b><span>Synthetic example / 01</span></div><h2>One clear record.<br>Three useful findings.</h2><p class="object-summary">Sample catalog · 6 recordings<br>January to December 2025</p><div class="object-finding"><span>Clarify before a buyer conversation</span>One recording has an unresolved split in the example. The report explains what is missing and what to ask for.</div><div class="object-line"><span>Supplied net receipts</span><b>${euro(totals.totalCents)}</b></div><div class="object-line"><span>First to final quarter</span><b>−18.2%</b></div><div class="object-line"><span>Top recording share</span><b>40%</b></div><p class="object-bottom">All figures and document conditions shown here are invented for demonstration. No real customer, appraisal or verified transaction.</p></aside></div></section>
<section class="section" id="the-report"><div class="section-heading"><h2>Not another number.<br>A clearer picture.</h2><p>A calculator can show an assumption. The proposed report would do the practical work on your supplied records: reconcile the figures, explain the changes and identify what still needs attention.</p></div><div class="deliverables"><article class="deliverable"><h3>The income, reconciled.</h3><p>One consistent statement window, with monthly totals and recording/platform breakdowns where the data supports them. Every total traces back to the supplied rows.</p></article><article class="deliverable"><h3>The gaps, explained.</h3><p>See what was observed, what you declared and what was not supplied. A missing split agreement is a question to resolve, not an automated ownership verdict.</p></article><article class="deliverable"><h3>The next steps, prioritized.</h3><p>A short action list with a reason for each step. A readable PDF and summary data you can use with another buyer or your own adviser.</p></article></div></section>
<section class="section" id="choose"><div class="section-heading"><h2>Two different jobs.<br>No paid shortcut.</h2><p>The report would be an optional service. Paying would not improve your eligibility, accelerate a purchase review or increase a SPACE offer.</p></div><div class="comparison"><article><p class="eyebrow">Existing service</p><h3>“Will SPACE buy my catalog?”</h3><p>Request a free initial review for a possible sale. SPACE considers the income, rights and supporting evidence individually. No obligation to accept an offer.</p><a class="text-link" href="https://spacemusic.io/apply/">Request the existing free review ↗</a></article><article><p class="eyebrow">Proposed paid service</p><h3>“Help me understand my records.”</h3><p>Get a standalone summary of the agreed evidence, the questions it raises and the work to prepare. No requirement to enter a sale process with SPACE.</p><a class="text-link" href="./sample.html">See exactly what the report looks like ↗</a></article></div><p class="plain-note">You can keep using the <a href="https://spacemusic.io/calculator/">free calculator</a> and <a href="https://spacemusic.io/blog/music-catalog-sale-documents-checklist/">document checklist</a>. The paid proposal is for work on your records, not access to those resources.</p></section>
<section class="section" id="scope"><div class="scope-layout"><div><p class="eyebrow">Small enough to do properly</p><h2>One defined catalog.<br>One useful report.</h2><p>The first pilot would cover a manageable slice of your master-recording catalog. Format and scope would be checked before any payment.</p><ul><li>Up to 25 recordings and 12 complete, consecutive statement months.</li><li>One distributor, one payee and one currency.</li><li>An agreed CSV export, track list and document inventory.</li><li>An English PDF, summary CSV and one correction round on the agreed inputs.</li></ul><p class="small">No account passwords or audio files. PDF-only statements, mixed currencies, additional distributors and publishing analysis are outside the initial package.</p></div><section class="scope-box" aria-label="Proposed pilot price"><p class="eyebrow">Price hypothesis / not a live offer</p><div class="price">€99</div><h3>One report. No subscription.</h3><p>Proposed pilot price. The final total, applicable tax, scope and terms must be confirmed before this can be sold.</p><a class="button" href="./sample.html">Inspect the sample first <span aria-hidden="true">↗</span></a><p>Proposed delivery target: five business days after successful payment and complete accepted inputs. Capacity is not yet verified.</p><p class="small">Checkout is intentionally absent. This is an owner-review concept, not an order form.</p></section></div><div class="rule-list"><article><h3>Scope first.</h3><p>Confirm that the source format and requested work fit. If they do not, decline or agree a different scope before charging.</p></article><article><h3>Evidence before claims.</h3><p>Reconcile to the supplied files. Do not pretend that receiving a document authenticates it or proves transferable rights.</p></article><article><h3>Useful without a sale.</h3><p>Keep the deliverable. Take your questions to another buyer or an independent adviser. No sale to SPACE required.</p></article></div></section>
<section class="section faq"><div><p class="eyebrow">Clear boundaries</p><h2>Before you<br>pay anything.</h2></div><div><details><summary>Is this an independent valuation?</summary><p>No. SPACE is also a potential buyer of music rights. The proposed report organizes and explains supplied evidence; it would not give an independent market appraisal, certify ownership or replace legal advice.</p></details><details><summary>Why pay when the purchase review is free?</summary><p>Only if you want a separate, reusable deliverable. A free review answers whether SPACE may consider buying rights. If that is all you need, use the free route. Buying a report would not be necessary.</p></details><details><summary>What if my records are incomplete?</summary><p>We would confirm the scope first and explain missing inputs. We would not invent income, fill missing months with zero or mark unproven rights as verified. If the agreed work cannot be delivered after payment, a refund or explicitly agreed alternative would be offered.</p></details><details><summary>Will the report tell me my sale price?</summary><p>No. Any calculation would state its assumptions and would not be a market benchmark or offer. An actual transaction requires individual assessment, agreed rights, terms and a willing buyer.</p></details><details><summary>Can I buy it now?</summary><p>Not yet. This is a private concept. The owner still needs to approve the service, capacity, customer terms, privacy arrangements and payment setup. No real documents are accepted here.</p></details></div></section></main>`;
await writeFile(
  path.join(out, "index.html"),
  page("Know your catalog. Before you sell.", "offer", landing),
);

const sheet = (n, title, body) =>
  `<article class="report-sheet" id="section-${n}" aria-label="${e(title)}"><div class="sheet-head"><strong>SPACE / Catalog Readiness</strong><span>SYNTHETIC-001 · Illustrative only</span></div>${body}<footer class="sheet-foot"><span>Fictional data. Not a customer report, independent appraisal or offer.</span><span>Draft · 09 Sep 2026 · ${n}/4</span></footer></article>`;
const finding = (n, title, copy, evidence) =>
  `<article class="finding"><span>${n}</span><div><h2>${title}</h2><p>${copy}</p><p class="evidence">${evidence}</p></div></article>`;
const monthlyTable = `<table class="data-table"><caption>Net receipts by statement month (EUR)</caption><thead><tr><th scope="col">2025</th><th scope="col" class="numeric">Net receipts</th><th scope="col">Source rows</th></tr></thead><tbody>${months.map((m, i) => `<tr><th scope="row">${monthLabels[i]}</th><td class="numeric">${euro(totals.monthly[m])}</td><td>${String(i * 18 + 1).padStart(3, "0")}–${String((i + 1) * 18).padStart(3, "0")}</td></tr>`).join("")}</tbody><tfoot><tr><th scope="row">Total</th><td class="numeric">${euro(totals.totalCents)}</td><td>001–216</td></tr></tfoot></table>`;
const trackTable = `<table class="data-table"><caption>Recording breakdown (same 216 rows)</caption><thead><tr><th scope="col">Recording</th><th scope="col" class="numeric">EUR</th><th scope="col" class="numeric">Share</th></tr></thead><tbody>${sampleDefinition.tracks.map((t) => `<tr><th scope="row">${e(t.name)}</th><td class="numeric">${euro(totals.tracks[t.id])}</td><td class="numeric">${t.percent}%</td></tr>`).join("")}</tbody><tfoot><tr><th scope="row">Total</th><td class="numeric">${euro(totals.totalCents)}</td><td class="numeric">100%</td></tr></tfoot></table>`;
const platformTable = `<table class="data-table"><caption>Platform breakdown (same 216 rows)</caption><thead><tr><th scope="col">Platform</th><th scope="col" class="numeric">EUR</th><th scope="col" class="numeric">Share</th></tr></thead><tbody>${sampleDefinition.platforms.map((p) => `<tr><th scope="row">${e(p.id)}</th><td class="numeric">${euro(totals.platforms[p.id])}</td><td class="numeric">${p.percent}%</td></tr>`).join("")}</tbody><tfoot><tr><th scope="row">Total</th><td class="numeric">${euro(totals.totalCents)}</td><td class="numeric">100%</td></tr></tfoot></table>`;
const sample = `<div class="report-toolbar wrap" role="region" aria-label="Sample report information"><p>A complete sample, not a real review. All records, amounts and document conditions are synthetic. No customer information is used.</p><nav aria-label="Report actions"><a href="./sample-report.pdf" download>Download sample PDF ↓</a><a href="./index.html#scope">Back to scope</a></nav></div><main id="main" class="report-wrap">${sheet(1, "Decision summary", `<p class="eyebrow">01 / Decision summary</p><h1>Clarify the evidence.<br>Then choose your next step.</h1><p class="sheet-intro">This invented six-recording catalog has a consistent set of example receipts, a lower final quarter and a rights-document gap. Here is what the supplied example supports, and what it does not.</p><dl class="report-meta"><div><dt>Catalog / reference</dt><dd>Sample catalog / SYNTHETIC-001</dd></div><div><dt>Statement window</dt><dd>January–December 2025</dd></div><div><dt>Scope</dt><dd>Masters · 6 recordings · EUR</dd></div></dl><div class="findings">${finding("01", "Resolve the split on Recording F.", "The example declaration mentions a collaborator, but no signed split document is included. Recording F contributes €720, or 6% of the supplied receipts. Ask for the agreement before describing the rights as transferable.", "Synthetic evidence: track register DEMO-F; document inventory D3; receipt rows filtered to DEMO-F.")}${finding("02", "Understand the smaller final quarter.", "October–December totals €2,700, against €3,300 for January–March: 18.2% lower. This is a statement-quarter comparison, not a forecast or proof of declining audience demand.", "Synthetic evidence: statement rows DEMO-001–054 and DEMO-163–216.")}${finding("03", "Prepare for questions about concentration.", "Recording A accounts for 40% of receipts; Platform A accounts for 60%. Explain the sources and context rather than assigning an unsupported risk score.", "Synthetic evidence: all 216 rows, grouped separately by recording and platform.")}</div><p class="report-disclosure"><strong>What this report is not.</strong> SPACE is a potential music-rights buyer, not an independent adviser to the seller. A real report would reconcile supplied evidence, not authenticate it with its issuer, certify ownership or promise a sale. This sample has no real reviewer or verified documents.</p>`)}
${sheet(2, "Income and method", `<p class="eyebrow">02 / Income and method</p><h2>€12,000 in the supplied year.<br>Not a predicted sale price.</h2><p class="sheet-intro">All figures are synthetic net receipts for the example payee's already-defined interest, after the example distributor deductions. No publishing income, unpaid balances or unallocated advances are modeled. Statement months are not necessarily usage months.</p><div class="bars" role="img" aria-label="Synthetic monthly net receipts fall from 1200 euros in January to 850 euros in December. Every monthly figure is in the following table.">${sampleDefinition.monthlyEuros.map((v) => `<span class="bar" style="height:${v / 12}%"></span>`).join("")}</div><div class="bar-labels"><span>Jan 2025 / €1,200</span><span>Dec 2025 / €850</span></div><div class="report-columns"><section>${monthlyTable}</section><section>${trackTable}${platformTable}</section></div><h3>How the totals were checked</h3><p>216 uniquely identified rows: 12 statement months × 6 recordings × 3 platform groups. Monthly, recording and platform totals each sum to €12,000. No missing months or adjustments are modeled. Source total and reconciliation difference: €12,000 and €0 respectively.</p><p class="report-caption">Method: sum integer EUR cents; no FX conversion. First-to-final quarter change = (€2,700 ÷ €3,300 − 1) × 100 = −18.2%. This is not a year-over-year comparison. The synthetic platform allocation is constant by construction, not a real finding about listener behavior.</p>`)}
${sheet(3, "Evidence and documentation", `<p class="eyebrow">03 / Evidence and documentation</p><h2>What is present.<br>What is still a question.</h2><p class="sheet-intro">This inventory is entirely invented for demonstration. “Observed” means present in the hypothetical supplied set, not authenticated or legally verified. An actual report would cite the real private file and relevant page or rows.</p><table class="data-table"><caption>Synthetic document inventory</caption><thead><tr><th scope="col">Ref / evidence</th><th scope="col">Example status</th><th scope="col">Useful next action</th></tr></thead><tbody><tr><th scope="row">D1 / Receipt export<br><span class="small">216 rows; 12 months</span></th><td>Observed in sample</td><td>For a real review, retain original statements and reconcile the same scope.</td></tr><tr><th scope="row">D2 / Track register<br><span class="small">6 recordings</span></th><td>Incomplete</td><td>Obtain Recording F's identifier. The other five placeholders are not valid ISRCs.</td></tr><tr><th scope="row">D3 / Recording F split</th><td>Declared; not supplied</td><td>Ask the collaborator for the signed agreement and confirmation of the rights it covers.</td></tr><tr><th scope="row">D4 / Distribution agreement</th><td>Not supplied</td><td>Ask an independent adviser to check restrictions, term and any transfer requirements.</td></tr><tr><th scope="row">D5 / Advance or lien status</th><td>Unknown</td><td>Request the relevant balance and release evidence if applicable. Do not assume zero.</td></tr></tbody></table><div class="report-columns"><section><h3>Income is not ownership evidence.</h3><p>A royalty statement can show a reported payment basis without proving that a person owns, controls or can transfer the rights. The customer's declaration remains a declaration until the relevant evidence is checked.</p></section><section><h3>Masters are not publishing.</h3><p>The sample covers only its defined recording receipts. Musical compositions and sound recordings are distinct works in the US Copyright Office reference. This does not resolve any particular country's ownership or transfer rules.</p></section></div><p class="report-disclosure"><strong>No readiness score.</strong> The important result is the specific unresolved item and what to do about it. Five identifiers being present does not make a catalog “83% sale-ready.” Neither a document count nor a synthetic status badge proves transferability.</p><p class="report-sources">Method reference: <a href="https://www.copyright.gov/circs/circ56a.pdf">US Copyright Office, Circular 56A</a>. Preparation resource: <a href="https://spacemusic.io/blog/music-catalog-sale-documents-checklist/">SPACE seller document checklist</a>. These sources explain concepts; they do not verify this fictional catalog.</p>`)}
${sheet(4, "Scenario and next steps", `<p class="eyebrow">04 / Scenario and next steps</p><h2>An assumption is useful.<br>Only if it stays an assumption.</h2><p>For illustration only, apply an arbitrary annual-income multiple of 4 to 50% of the already-defined interest represented by the synthetic receipts. Four is not a market benchmark, recommendation or offer multiple.</p><div class="report-flow"><span>€12,000 / year</span><span aria-hidden="true">×</span><span>4 assumed</span><span aria-hidden="true">×</span><span>50% share</span><span aria-hidden="true">=</span><b>${euro(scenario(totals.totalCents, 4, 50))}</b></div><p class="report-caption">Same arithmetic: €1,000 monthly average × 12 × 4 × 50%. No additional ownership haircut, extra year multiplier or predicted range. Taxes, transaction costs, balances, contract restrictions and payment conditions are excluded. The hypothetical figure is not net cash at closing.</p><h3>Three actions before a transaction discussion</h3><ol><li><strong>Close the document gaps.</strong> Request Recording F's identifier and signed split evidence. Ask the appropriate adviser about transfer restrictions and any outstanding obligations.</li><li><strong>Explain the income window.</strong> Retain the original source files. Check reporting lag and context for the quarter difference; do not infer an audience trend from receipts alone.</li><li><strong>Choose the conversation you actually need.</strong> Use the record with your own adviser or another buyer. If you want SPACE to consider a purchase, request the separate free review. No report purchase is required.</li></ol><p class="report-disclosure"><strong>Scope limits.</strong> A future real report must be signed off by a named reviewer against the accepted evidence set. It is not legal, tax or investment advice, a certified appraisal, a fraud clearance or a promise that anyone will buy. SPACE's commercial interest must remain disclosed.</p><h3>Evidence trail and useful resources</h3><p class="report-sources">Internal example evidence: <a href="./synthetic-receipts.csv">synthetic-receipts.csv</a> (DEMO-001–216); <a href="./synthetic-track-register.csv">synthetic-track-register.csv</a> (DEMO-A–F); <a href="./synthetic-document-inventory.csv">synthetic-document-inventory.csv</a> (D1–D5). Values generated from explicit fictional allocations, not customer files.<br>Public resources: ${sourceLinks}.<br>Next step: <a href="https://spacemusic.io/apply/">request SPACE's existing free review</a>, or speak with an independent adviser. A paid report and a purchase application are separate decisions.</p><div class="download-row"><a href="./synthetic-receipts.csv" download>Download synthetic source rows ↓</a><a href="./synthetic-summary.csv" download>Download reconciled summary ↓</a></div>`)}
</main>`;
await writeFile(
  path.join(out, "sample.html"),
  page("Catalog Readiness sample report", "sample", sample),
);

const inputLabels = {
  gross: "Pris till kund, EUR totalt",
  taxPercent: "Antagen inkluderad skatt, %",
  feePercent: "Rörlig avgiftsbuffert, %",
  fixedFee: "Fast avgiftsbuffert, EUR",
  reservePercent: "Reserv av intäkt exkl. skatt, %",
  minutes: "Total arbetstid, minuter",
  hourlyCost: "Full arbetskostnad, EUR/timme",
  otherCost: "Övrig kostnad, EUR/order",
};
const r = economics(planningAssumptions);
const review = `<main id="main" class="wrap"><section class="owner-hero"><p class="eyebrow">Ägargranskning / inte en försäljningssida</p><h1>En bra produkt måste<br>fungera på båda sidor.</h1><p>För kunden: en användbar rapport även utan en affär med SPACE. För oss: avgränsat arbete, tydlig kvalitet och ett pris som håller när människans tid räknas med.</p></section><section class="decision"><h2>Rekommendationen i en mening.</h2><p>Pröva en separat, manuell rapport i högst fem betalda pilotleveranser efter godkända villkor. Behåll hela gratisvägen. Bygg inte ett abonnemang eller en automatiserad värderingsprodukt innan efterfrågan och leveransen är bevisade.</p><p class="small">€99 är en prishypotes, inte ett beslutat eller validerat pris. Ingen tjänst är aktiverad, ingen betalning kopplad och inget i produktion ändrat.</p></section><section class="section" id="economics"><div class="section-heading"><h2>Räkna på arbetet.<br>Inte bara priset.</h2><p>Alla ingångsvärden nedan är justerbara planeringsantaganden. Ingen verklig Stripe-avgift, skattesats eller uppmätt leveranstid används. Kalkylen stannar i din webbläsare.</p></div><div class="economics"><div><div class="inputs">${Object.entries(
  planningAssumptions,
)
  .map(
    ([key, value]) =>
      `<div class="input"><label for="${key}">${inputLabels[key]}</label><input id="${key}" name="${key}" type="number" min="0" max="${["taxPercent", "feePercent", "reservePercent"].includes(key) ? 100 : key === "minutes" || key === "hourlyCost" ? 100000 : 1000000}" step="any" inputmode="decimal" value="${value}" aria-describedby="cost-assumptions"></div>`,
  )
  .join(
    "",
  )}</div><p id="cost-error" class="error-text" role="status" aria-live="polite"></p></div><section class="result-panel" aria-label="Illustrativt bidrag per order"><p class="eyebrow">Kvar efter modellerade kostnader</p><output class="result-value" id="contribution">${euro2(r.contribution)}</output><p id="result-note">Vid 75 minuters arbete. Inte vinst efter alla bolagskostnader.</p><div class="result-row"><span>Intäkt exklusive antagen skatt</span><span id="revenue">${euro2(r.revenue)}</span></div><div class="result-row"><span>Betalavgiftsbuffert</span><span id="fees">${euro2(r.fees)}</span></div><div class="result-row"><span>Återbetalningsreserv</span><span id="reserve">${euro2(r.reserve)}</span></div><div class="result-row"><span>Arbetskostnad</span><span id="labor">${euro2(r.labor)}</span></div><div class="result-row"><span>Övrig kostnad</span><span id="otherCostResult">${euro2(r.otherCost)}</span></div><p id="break-even">Utrymme för cirka ${Math.floor(r.breakEvenMinutes)} minuters arbete före nollbidrag.</p></section></div><p class="assumptions" id="cost-assumptions">Metod: pris ÷ (1 + antagen skatt) − avgift på hela betalningen − reserv på intäkt exkl. skatt − arbetstid × timkostnad − övrig kostnad. Reserven är ett planeringsavdrag, inte faktisk återbetalning. Räkna inte båda när verkliga order följs upp. Avgiftsbufferten 3,5% + €0,30 är inte Stripes publicerade tariff.</p><noscript><p class="plain-note">JavaScript är avstängt. De synliga resultaten avser grundantagandena ovan; ändrade fält räknas inte om. Den fasta jämförelsetabellen nedan fungerar fortfarande.</p></noscript><div class="table-container"><table class="data-table"><caption>Fast känslighetsanalys: samma skatte-, avgifts- och kostnadsantaganden som startvärdena</caption><thead><tr><th scope="col">Totalpris</th><th scope="col" class="numeric">60 min</th><th scope="col" class="numeric">90 min</th><th scope="col" class="numeric">120 min</th></tr></thead><tbody>${[99, 149, 199].map((gross) => `<tr><th scope="row">€${gross}</th>${[60, 90, 120].map((minutes) => `<td class="numeric">${euro2(economics({ ...planningAssumptions, gross, minutes }).contribution)}</td>`).join("")}</tr>`).join("")}</tbody></table></div><p class="plain-note"><strong>Slutsats:</strong> €99 kan vara en begränsad lärandepilot, men är svagt som standardpris om arbetet tar 90 minuter eller mer. Pröva €149 som nästa hypotes om nyttan och betalningsviljan håller. Höj inte priset med ett påhittat marknadsvärde som motivering.</p></section><section class="section"><div class="section-heading"><h2>Fyra grindar.<br>Före första betalningen.</h2><p>Alla är öppna beslut. Att godkänna denna design är inte samma sak som att godkänna villkor, drift, kundkontakt eller en livebetalning.</p></div><ol class="owner-gates"><li><div><h3>Värde och omfattning</h3><p>Bekräfta den fristående rapporten, 25 inspelningar, ett underlag och en valuta. Visa exemplet för relevanta personer efter tillstånd. Ingen köpgranskning bakom betalvägg.</p></div></li><li><div><h3>Verklig leveranskapacitet</h3><p>Utse granskare och kvalitetskontrollant. Gör en torrkörning med tidtagning och kontrollera att underlag kan tas emot privat. Fem arbetsdagar är ännu bara ett föreslaget mål.</p></div></li><li><div><h3>Pris, skatt och kundvillkor</h3><p>Bekräfta juridisk säljare, land, B2B/B2C, totalpris, skatt, ångerrätt och återbetalningsrutin. En artist är inte automatiskt företagskund.</p></div></li><li><div><h3>Betalning och dataskydd</h3><p>Verifiera Stripe live, genomför testfallen i sandbox och etablera privat lagring. Inga riktiga kunddokument i denna preview, Git, betalningsmetadata eller analysverktyg.</p></div></li></ol></section><section class="section"><div class="section-heading"><h2>Det färdiga utkastet.<br>Och det som återstår.</h2><p>Rapporten är konkret. Tjänsten är fortfarande ett beslut.</p></div><div class="owner-docs"><article><h3>Klart att granska</h3><p>Erbjudande, syntetisk rapport, källunderlag, kostnadsmodell, leveransrutin, pilotmått och betalningsspecifikation. Previewn har inga köp- eller uppladdningsfunktioner.</p><a class="text-link" href="./sample.html">Läs hela exempelrapporten ↗</a></article><article><h3>Inte verifierat</h3><p>Betalningsvilja, faktisk personalkostnad, bemanning, Stripe-kontot, skatteregistrering, kundländer och säker filkanal. Inga påhittade svar eller kundcase fyller dessa luckor.</p><a class="text-link" href="./sources.html">Se källor och faktagränser ↗</a></article></div></section></main>`;
await writeFile(
  path.join(out, "review.html"),
  page("Beslutsunderlag och kostnadskalkyl", "review", review, {
    lang: "sv",
    script: true,
  }),
);

const sources = `<main id="main" class="wrap"><section class="owner-hero"><p class="eyebrow">Evidence / reviewed 09 September 2026</p><h1>Facts where we have them.<br>Limits where we do not.</h1><p>The service, price and delivery target are proposals. The sample is entirely synthetic. No private customer material, invented testimonial or claimed paid order is used.</p></section><section class="section"><div class="section-heading"><h2>Verified context.</h2><p>These sources support the boundaries of the proposal. They do not validate demand for a paid report.</p></div><ol class="source-list"><li>${sourceLinks}: existing free services and educational resources. A paid report must add individualized work.</li><li><a href="https://www.copyright.gov/circs/circ56a.pdf">US Copyright Office, Circular 56A</a>: distinct composition and recording works. Not proof of any customer's rights.</li><li><a href="https://docs.stripe.com/payment-links">Stripe Payment Links</a> and <a href="https://docs.stripe.com/testing">testing guidance</a>: hosted one-time payment capability and simulated test payments. This account's live eligibility is not verified.</li><li><a href="https://stripe.com/en-se/pricing">Stripe Sweden pricing</a>: published card fees depend on card and other circumstances. The owner calculator instead uses an explicit illustrative EUR fee buffer.</li><li><a href="https://www.konsumentverket.se/lagar/lagen-om-distansavtal-och-avtal-utanfor-affarslokaler/">Konsumentverket: distance contracts</a>: consumer rights need handling before launch. A manual report delivered as a PDF is not automatically non-refundable.</li><li><a href="https://www.skatteverket.se/foretag/moms/saljavarorochtjanster/forsaljningtillandraeulander/saljatjanstertillandraeulander.4.76a43be412206334b89800010696.html">Skatteverket: cross-border services</a>: buyer status, location and service classification matter. Tax treatment is a launch blocker.</li><li><a href="https://www.imy.se/verksamhet/dataskydd/det-har-galler-enligt-gdpr/grundlaggande-principer/">IMY: data-protection principles</a>: minimize, protect and limit use/retention of customer data. No approved customer-storage channel is established by this preview.</li></ol></section><section class="section"><div class="section-heading"><h2>The synthetic evidence.</h2><p>Every monetary total in the sample can be traced to the included demonstration rows. This is a reproducibility check, not verification of real royalty receipts.</p></div><div class="download-row"><a href="./synthetic-receipts.csv" download>216 synthetic source rows ↓</a><a href="./synthetic-summary.csv" download>Reconciled summary ↓</a><a href="./synthetic-track-register.csv" download>Track register ↓</a><a href="./synthetic-document-inventory.csv" download>Document inventory ↓</a><a href="./sample-report.pdf" download>Sample PDF ↓</a></div><p class="plain-note">All statements, track labels, allocations, identifier placeholders and document conditions are invented. The live SPACE site has not been changed. There are no checkout, upload, analytics or customer-account integrations in this concept.</p></section></main>`;
await writeFile(
  path.join(out, "sources.html"),
  page("Sources and boundaries", "sources", sources),
);

const csvRow = (values) =>
  values.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(",");
await writeFile(
  path.join(out, "synthetic-receipts.csv"),
  [
    "synthetic_only,line_id,statement_month,track_reference,platform,currency,net_receipts",
    ...rows.map((r) =>
      csvRow([
        "SYNTHETIC NOT REAL",
        r.id,
        r.month,
        r.track,
        r.platform,
        r.currency,
        (r.netCents / 100).toFixed(2),
      ]),
    ),
  ].join("\n") + "\n",
);
await writeFile(
  path.join(out, "synthetic-summary.csv"),
  [
    "synthetic_only,group,reference,currency,net_receipts",
    ...Object.entries({
      month: totals.monthly,
      track: totals.tracks,
      platform: totals.platforms,
    }).flatMap(([group, values]) =>
      Object.entries(values).map(([ref, cents]) =>
        csvRow([
          "SYNTHETIC NOT REAL",
          group,
          ref,
          "EUR",
          (cents / 100).toFixed(2),
        ]),
      ),
    ),
  ].join("\n") + "\n",
);
await writeFile(
  path.join(out, "synthetic-track-register.csv"),
  [
    "synthetic_only,track_reference,label,identifier_example,rights_declaration",
    ...sampleDefinition.tracks.map((t) =>
      csvRow([
        "SYNTHETIC NOT REAL",
        t.id,
        t.name,
        t.identifierPresent
          ? `PLACEHOLDER-${t.id} (not a valid ISRC)`
          : "NOT SUPPLIED",
        t.id === "DEMO-F"
          ? "Collaborator declared; split agreement not supplied"
          : "Sole control declared in fictional input; not legally verified",
      ]),
    ),
  ].join("\n") + "\n",
);
await writeFile(
  path.join(out, "synthetic-document-inventory.csv"),
  [
    "synthetic_only,reference,document,example_status",
    ...[
      [
        "D1",
        "Receipt export",
        "Observed in synthetic set; no issuer authentication",
      ],
      ["D2", "Track register", "Recording F identifier not supplied"],
      ["D3", "Recording F split", "Declared; signed document not supplied"],
      ["D4", "Distribution agreement", "Not supplied"],
      ["D5", "Advance or lien status", "Unknown"],
    ].map((row) => csvRow(["SYNTHETIC NOT REAL", ...row])),
  ].join("\n") + "\n",
);
await writeFile(path.join(out, "robots.txt"), "User-agent: *\nDisallow: /\n");
await writeFile(
  path.join(out, "sample-data.json"),
  JSON.stringify({ synthetic: true, rows: rows.length, ...totals }, null, 2),
);
console.log(
  JSON.stringify({
    preview: out,
    syntheticRows: rows.length,
    totalCents: totals.totalCents,
    pages: 4,
    productionChanged: false,
  }),
);
