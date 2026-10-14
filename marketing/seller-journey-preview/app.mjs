import {
  STORAGE_KEY,
  DEMO,
  DOCUMENTS,
  DISTRIBUTORS,
  CURRENCIES,
  fresh,
  restore,
  validateContact,
  validateCatalog,
  addDemoDocument,
  missingDocuments,
  submitPackage,
  requestClarification,
  sendReply,
} from "./model.mjs";

const main = document.querySelector("#main");
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let state = fresh(),
  errors = {},
  busy = false,
  busyKind = "",
  fileError = "",
  fileErrorKind = "",
  failSubmit = false,
  storageWorks = true;
try {
  const raw = localStorage.getItem(STORAGE_KEY),
    saved = restore(raw);
  if (saved) {
    state = saved;
    if (state.progress > 0 && state.screen !== "paused") {
      state.returnScreen = state.screen;
      state.screen = "paused";
    }
  } else if (raw)
    document.querySelector("#storage-note").textContent =
      "The saved demo was not usable. Start a new demo below.";
} catch {
  storageWorks = false;
}

function announce(message) {
  document.querySelector("#announcement").textContent = message;
}
function storageNote() {
  if (!storageWorks) {
    document.querySelector("#storage-note").textContent =
      "Browser storage is unavailable. The demo still works, but recent changes may be lost if you refresh or close this tab.";
    const indicator = document.querySelector(".save-indicator");
    if (indicator) indicator.textContent = "Temporary demo";
  }
}
function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    storageWorks = false;
  }
  storageNote();
}
function go(screen) {
  state.screen = screen;
  errors = {};
  save();
  render();
  main.focus();
  window.scrollTo({ top: 0, behavior: "instant" });
}
const button = (action, label, cls = "text-button", disabled = false) =>
  `<button type="button" data-action="${action}" class="${cls}" ${disabled ? "disabled" : ""}>${label}</button>`;
function field(
  key,
  label,
  {
    type = "text",
    help = "",
    optional = false,
    options,
    group = "details",
    min,
    max,
    step,
  } = {},
) {
  const value = state[group][key],
    invalid = errors[key];
  const attrs = `id="${key}" name="${key}" data-group="${group}" ${invalid ? 'aria-invalid="true"' : ""} aria-describedby="${key}-help${invalid ? ` ${key}-error` : ""}" ${!optional ? "required" : ""} ${busy ? "disabled" : ""}`;
  const input = options
    ? `<select ${attrs}><option value="">Select an answer</option>${options
        .map((option) => {
          const [v, l] = Array.isArray(option) ? option : [option, option];
          return `<option value="${esc(v)}" ${v === value ? "selected" : ""}>${esc(l)}</option>`;
        })
        .join("")}</select>`
    : `<input ${attrs} type="${type}" value="${esc(value)}" maxlength="500" autocomplete="off" ${min !== undefined ? `min="${min}"` : ""} ${max !== undefined ? `max="${max}"` : ""} ${step ? `step="${step}"` : ""} ${type === "number" ? 'inputmode="decimal"' : ""}>`;
  return `<div class="field"><label class="field-label" for="${key}">${label}${optional ? '<span class="optional">Optional</span>' : ""}</label>${input}<span class="help" id="${key}-help">${help}</span>${invalid ? `<span class="field-error" id="${key}-error">${esc(invalid)}</span>` : ""}</div>`;
}
function errorSummary() {
  if (!Object.keys(errors).length) return "";
  return `<div class="error-summary" role="alert"><strong>${errors.general ? esc(errors.general) : "A few details need your attention."}</strong>${errors.general ? "" : "<p>Check the highlighted fields below. Everything you entered is still here.</p>"}</div>`;
}
function stepper(current) {
  return `<nav aria-label="Application progress"><ol class="stepper">${[
    "Apply",
    "Catalog",
    "Documents",
    "Review",
  ]
    .map((label, i) => {
      const complete = i < current,
        enabled = state.status === "SUBMITTED" && i <= state.progress;
      return `<li class="${i === current ? "current" : complete ? "done" : ""}"><button type="button" data-step="${i}" ${enabled ? "" : "disabled"} ${i === current ? 'aria-current="step"' : ""}><span class="number" aria-hidden="true">${complete ? "&#10003;" : i + 1}</span><span>${label}</span></button></li>`;
    })
    .join("")}</ol></nav>`;
}
function sidebar() {
  return `<aside class="sidebar" aria-label="Your review summary"><p class="eyebrow">Demo review / SP-DEMO-001</p><h2>${esc(state.contact.artist || "Your catalog")}</h2><p>One place for your catalog, evidence and next steps.</p><ul class="summary-list"><li><span>Initial review</span><strong>Free</strong></li><li><span>Sale scope</span><strong>Existing recordings</strong></li><li><span>Future music</span><strong>Excluded</strong></li><li><span>Commitment</span><strong>No obligation to sell</strong></li></ul><div class="sidebar-note"><h3>You stay in control.</h3><p>Providing information is not accepting an offer. Rights and terms would be agreed separately, after review.</p></div><p class="fine">Prototype only. No customer account or real review exists here. Use fictional information.</p></aside>`;
}
function previewControls(content) {
  return `<details class="preview-controls"><summary>Preview controls</summary><p>These controls simulate the experience. They do not change a real application.</p>${content}</details>`;
}
function actions(back, label, disabled = false) {
  return `<div class="actions">${button(`back:${back}`, "Back", "text-button quiet", busy)}<button class="primary" type="submit" ${busy || disabled ? "disabled" : ""}>${busy ? '<span class="loader" aria-hidden="true"></span> Working in demo...' : label + ' <span aria-hidden="true">&rarr;</span>'}</button></div>`;
}
function landing() {
  return `<section class="landing panel-enter"><div class="landing-copy"><p class="eyebrow">For independent catalog owners</p><h1>We buy your<br>music catalog.</h1><p class="lede">Start with a free review. Keep your catalog details, documents and next steps together, without the back-and-forth.</p><ul class="assurances"><li><span class="tick" aria-hidden="true">&#10003;</span>Direct review, no auction</li><li><span class="tick" aria-hidden="true">&#10003;</span>No obligation to accept an offer</li><li><span class="tick" aria-hidden="true">&#10003;</span>Your future music stays yours</li></ul></div><form class="card intake" id="apply-form" novalidate><p class="eyebrow">Your first step</p><h2>Tell us who you are.</h2><p class="subtext">No statements needed yet. You can add the details after your request is received.</p>${errorSummary()}${field("email", "Email address", { type: "email", group: "contact", help: "In the live flow, this would be used to verify access to your review." })}${field("artist", "Artist or label name", { group: "contact", help: "Your music identity, not DistroKid or another distributor." })}${field("name", "Your name", { group: "contact", optional: true })}${button("sample-contact", "Fill with fictional demo details", "sample-button", busy)}<button class="primary wide" type="submit" ${busy ? "disabled" : ""}>${busy ? "Creating demo..." : "Start demo review"}<span aria-hidden="true">&rarr;</span></button><p class="fine">Nothing is submitted. This preview stores your demo progress in this browser only. Please do not enter real personal information.</p></form></section><section class="process-overview" aria-label="What happens next"><article><h3>Start simple</h3><p>Make the introduction. No documents or commitments upfront.</p></article><article><h3>Add your evidence</h3><p>Share the recordings and income you want us to review.</p></article><article><h3>Know your next step</h3><p>See what is received, what is missing, and what needs your input.</p></article></section>`;
}
function received() {
  return `${stepper(0)}<section class="center-stage panel-enter"><span class="success-mark" aria-hidden="true">&#10003;</span><p class="eyebrow">Demo application received</p><h1>Your first step is done.</h1><p class="lede">Next, tell us about the catalog you would like reviewed. You can continue now or return to this demo later.</p><div class="confirmation-summary"><div><span>Artist or label</span><strong>${esc(state.contact.artist)}</strong></div><div><span>Contact</span><strong>${esc(state.contact.email)}</strong></div><div><span>Demo reference</span><strong>SP-DEMO-001</strong></div></div><div class="actions">${button("pause", "Save and leave demo", "text-button quiet")}${button("continue-catalog", 'Add catalog details <span aria-hidden="true">&rarr;</span>', "primary")}</div><p class="fine">Simulated receipt only. No application was sent to SPACE or Formspree, and no email was sent.</p></section>`;
}
function catalog() {
  return `${stepper(1)}<div class="workspace panel-enter"><section><p class="eyebrow">Step 2 / Your catalog</p><h1>What would you<br>like us to review?</h1><p class="lede">Define the recordings and income. These are your estimates, not verified figures or an offer.</p><form id="catalog-form" novalidate>${errorSummary()}<section class="form-section"><div class="section-heading"><h2>The music</h2>${button("sample-catalog", "Use sample catalog", "text-button", busy)}</div>${field("artistLink", "Link to your music", { type: "url", optional: true, help: "An artist profile, release or catalog link." })}<div class="row">${field("distributor", "Distributor", { options: DISTRIBUTORS })}${field("tracks", "Recordings to review", { type: "number", min: 1, max: 1000000, step: 1 })}</div></section><section class="form-section"><h2>The rights you want to sell</h2>${field(
    "rights",
    "Which rights are you proposing?",
    {
      options: [
        ["masters", "Recording rights (masters)"],
        ["unsure", "Not sure yet"],
      ],
      help: "Composition and publishing rights are separate. They are not included automatically.",
    },
  )}<div class="row">${field("owned", "Your ownership (%)", { type: "number", min: 0.01, max: 100, step: 0.01, help: "Your share of the recording rights." })}${field("offered", "Share of your ownership to sell (%)", { type: "number", min: 0.01, max: 100, step: 0.01, help: "50% of a 50% ownership share is 25% of the whole recording." })}</div>${field("cutoff", "Proposed catalog cutoff date", { type: "date", optional: true, help: "A proposed boundary, not an agreed contract date. The final recording list defines what is included." })}<div class="scope-note"><strong>Only the existing recordings you agree to sell.</strong><p>Future music is excluded. Uploading evidence does not transfer rights, and this preview creates no agreement.</p></div>${field(
    "agreements",
    "Do agreements or other people affect these rights?",
    {
      options: [
        ["none-known", "None that I know of"],
        ["shared", "Yes, shared royalties or other agreements"],
        ["unknown", "Not sure yet"],
      ],
      help: "Include collaborators, samples, licenses, label deals or advances. Unknown is not treated as cleared.",
    },
  )}</section><section class="form-section"><h2>The income behind the catalog</h2><p class="subtext">Use the available statement period. Do not turn a few months into an annual estimate.</p><div class="row">${field("revenue", "Royalties reported for this period", { type: "number", min: 0, step: 0.01, help: "Zero is allowed. This is not a valuation or asking price." })}${field("currency", "Statement currency", { options: CURRENCIES })}</div><div class="row">${field("periodStart", "First statement month", { type: "month" })}${field("periodEnd", "Last statement month", { type: "month" })}</div>${field(
    "basis",
    "Whose income does this amount represent?",
    {
      options: [
        ["own-share", "My share, after collaborator splits"],
        ["catalog-total", "Catalog total, before collaborator splits"],
        ["unsure", "Not sure"],
      ],
      help: "The reviewer will reconcile this against your original statements.",
    },
  )}</section>${actions("received", "Continue to documents")}</form></section>${sidebar()}</div>`;
}
function documentRow(kind) {
  const doc = DOCUMENTS[kind],
    added = state.docs.includes(kind);
  const description =
    kind === "royalties"
      ? "Original distributor exports for the period you entered. Keep the currency, reporting dates and adjustments."
      : "The recordings to review, with titles, ISRCs, release dates and your ownership shares.";
  return `<article class="document-item"><div class="document-heading"><span class="document-number" aria-hidden="true">${kind === "royalties" ? "01" : "02"}</span><div><h2>${doc.label}</h2><p>${description}</p></div></div><div class="document-body">${added ? `<div class="uploaded"><span class="tick" aria-hidden="true">&#10003;</span><div><strong>${doc.name}</strong><small>Demo file added &middot; Not reviewed</small></div>${button("remove:" + kind, "Remove", "text-button", busy)}</div>` : `<div class="doc-action">${button("add:" + kind, busyKind === kind ? "Adding demo file..." : fileErrorKind === kind ? "Retry demo upload" : "Add sample " + (kind === "royalties" ? "royalty statement" : "track list"), "secondary", busy)}<p>Sample data only. Real file selection is disabled in this preview.</p></div>`}${fileErrorKind === kind ? `<p class="field-error" role="alert">${esc(fileError)}</p>` : ""}${kind === "royalties" ? `<details class="help-details"><summary>Where do I find a DistroKid report?</summary><ol><li>Open the Bank section of your DistroKid account.</li><li>Choose See Excruciating Detail, then Download.</li><li>Keep the original export and note its reporting period.</li></ol><p><a href="https://support.distrokid.com/hc/en-us/articles/360013648253-Saving-Your-Earnings-Information-as-a-Spreadsheet-File" target="_blank" rel="noopener noreferrer">DistroKid's export instructions (opens a new tab)</a>. A streaming dashboard screenshot does not replace a royalty report.</p></details>` : ""}</div></article>`;
}
function documents() {
  return `${stepper(2)}<div class="workspace panel-enter"><section><p class="eyebrow">Step 3 / Supporting evidence</p><h1>Bring the source,<br>not just the total.</h1><p class="lede">Add the two items below so a reviewer can connect the income to the recordings.</p><p class="subtext"><strong>${state.docs.length} of 2 demo items added.</strong> Added does not mean verified.</p>${documentRow("royalties")}${documentRow("tracks")}<details class="help-details"><summary>What about contracts and sensitive information?</summary><p>A reviewer may request relevant agreements after checking your scope. Do not send passwords or login codes. The live flow needs authenticated, private storage and agreed handling of sensitive information before it can accept files.</p></details><form id="documents-form">${actions("catalog", "Review your package", missingDocuments(state).length > 0)}</form><p class="fine">You can save and return if evidence is not ready. Nothing here is uploaded, scanned or verified.</p>${previewControls(button("upload-failure", "Simulate a failed upload", "secondary", busy || state.docs.includes("royalties")))}</section>${sidebar()}</div>`;
}
const pairs = (rows) =>
  `<dl class="review-table">${rows.map(([label, value]) => `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>`;
function moneySummary() {
  return `${state.details.currency} ${Number(state.details.revenue).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function review() {
  const d = state.details;
  const scope = [
    ["Artist or label", state.contact.artist],
    ["Distributor", d.distributor],
    ["Recordings", d.tracks],
    [
      "Rights",
      d.rights === "masters"
        ? "Recording rights only; publishing excluded"
        : "Needs clarification before an offer",
    ],
    [
      "Owned / share of ownership offered",
      `${d.owned}% owned / ${d.offered}% of that share offered`,
    ],
    ["Proposed cutoff", d.cutoff || "To be agreed"],
    ["Future recordings", "Excluded"],
    [
      "Other agreements",
      {
        "none-known": "None known, still subject to review",
        shared: "Shared royalties or agreements disclosed",
        unknown: "Not yet confirmed; reviewer follow-up needed",
      }[d.agreements],
    ],
  ];
  const income = [
    ["Reported royalties", moneySummary() + " (not verified)"],
    ["Statement period", `${d.periodStart} to ${d.periodEnd}`],
    [
      "Income basis",
      {
        "own-share": "Your share after collaborator splits",
        "catalog-total": "Full catalog before collaborator splits",
        unsure: "Needs clarification",
      }[d.basis],
    ],
  ];
  return `${stepper(3)}<div class="workspace panel-enter"><section><p class="eyebrow">Step 4 / Final check</p><h1>Your catalog.<br>Clearly defined.</h1><p class="lede">Check the scope before handing it to a reviewer. You are requesting a review, not accepting an offer.</p>${errorSummary()}<section class="review-block"><h2>What you are proposing</h2>${pairs(scope)}</section><section class="review-block"><h2>Income reported by you</h2>${pairs(income)}</section><section class="review-block"><h2>Evidence included</h2>${pairs(state.docs.map((kind) => [DOCUMENTS[kind].label, "Demo file provided; not reviewed"]))}</section><div class="scope-note"><strong>There is no automatic valuation.</strong><p>A human reviewer needs to check the income, rights and any open questions before deciding whether to prepare an offer.</p></div><form id="review-form">${actions("documents", "Submit demo package")}</form><p class="fine">Simulates submission only. No real review, purchase agreement, payment or email is created.</p>${previewControls(button("fail-submit", failSubmit ? "Next demo submission will fail" : "Make the next demo submission fail", "secondary", busy))}</section>${sidebar()}</div>`;
}
function status() {
  const needsReply = state.status === "DATA_REQUIRED";
  return `${stepper(3)}<div class="workspace panel-enter"><section><div class="status-head"><p class="eyebrow">Demo review / SP-DEMO-001</p><span class="badge ${needsReply ? "warning" : ""}">${needsReply ? "Your input needed" : "Under review"}</span></div><h1>${needsReply ? "One detail<br>to clarify." : state.replied ? "Your reply is<br>ready for review." : "Everything in<br>one place."}</h1><p class="lede">${needsReply ? "Answer the question below to keep the review moving. No need to start a new application." : state.replied ? "The reviewer would see your response with the original package. Nothing is treated as verified automatically." : "Your demo package is in the review stage. This is where you would see updates and requests for more information."}</p><ol class="timeline"><li><strong>Application received</strong><p>${esc(state.contact.artist)} &middot; SP-DEMO-001 &middot; Fictional record</p></li><li><strong>Evidence provided</strong><p>2 sample files. Both remain unverified.</p></li><li><strong>${needsReply ? "Clarification requested" : state.replied ? "Your clarification received" : "Review in progress"}</strong><p>${needsReply ? "A simulated reviewer has a question about the income basis." : state.replied ? "Your response is available for human review, not automatically approved." : "Income, ownership and sale scope would be checked by a human."}</p></li></ol>${needsReply || state.replied ? `<article class="request-card"><p class="eyebrow">Example reviewer message</p><h2>Help us match the income.</h2><p>Does ${esc(moneySummary())} represent your share after any collaborator splits, or the full catalog total? Please clarify how it relates to the statement.</p><p class="message-meta">Simulated SPACE reviewer &middot; No real message was sent</p>${needsReply ? `<form id="reply-form" novalidate>${errorSummary()}<label class="field-label" for="reply">Your clarification</label><textarea id="reply" name="reply" maxlength="1500" required aria-describedby="reply-help" ${busy ? "disabled" : ""}>${esc(state.reply)}</textarea><p id="reply-help" class="help">Use fictional details. Do not include passwords or bank details.</p><button class="primary" type="submit" ${busy ? "disabled" : ""}>${busy ? "Saving demo reply..." : "Send demo clarification"}</button></form>` : `<div class="reply-note"><h3>Your demo reply</h3><p>${esc(state.reply)}</p><span class="badge green">Awaiting human review</span></div>`}</article>` : ""}<section class="review-block"><h2>Your scope stays visible</h2>${pairs(
    [
      ["Catalog", state.contact.artist],
      ["Recordings", state.details.tracks],
      ["Future music", "Excluded"],
      ["Proposed cutoff", state.details.cutoff || "To be agreed"],
      ["Review cost", "Free; no obligation to sell"],
    ],
  )}</section><details class="help-details"><summary>What happens after review?</summary><p>SPACE may ask for more evidence or decide whether to prepare an offer. Any rights transfer, agreement, signature and payment would be separate, reviewed steps. None of those actions is enabled in this preview.</p></details>${previewControls(button("request-clarification", state.replied ? "Example follow-up completed" : "Simulate a reviewer follow-up", "secondary", busy || needsReply || state.replied))}</section>${sidebar()}</div>`;
}
function paused() {
  return `<section class="center-stage panel-enter"><p class="eyebrow">Saved demo</p><h1>Pick up where<br>you left off.</h1><p class="lede">Your demo for ${esc(state.contact.artist || "this catalog")} is ${storageWorks ? "saved in this browser" : "still available in this tab"}. You do not need to repeat the completed steps.</p><div class="email-preview"><p class="eyebrow">Proposed live experience</p><h2>Continue your SPACE catalog review</h2><p>A verified, expiring email sign-in link would bring the seller back to their own private review.</p><p class="fine"><strong>No email has been sent.</strong> This button only reopens local demo data. It is not a sign-in link, and this prototype has no authentication.</p></div><div class="actions">${button("reset", "Start a new demo", "text-button quiet")}${button("resume", 'Continue saved demo <span aria-hidden="true">&rarr;</span>', "primary")}</div></section>`;
}
function render() {
  document.querySelector("#header-actions").innerHTML =
    `${state.progress > 0 && state.screen !== "paused" ? '<span class="save-indicator">' + (storageWorks ? "Demo saved in browser" : "Temporary demo") + "</span>" + button("pause", "Save & exit", "text-button", busy) : ""}${button("reset", "Restart demo", "text-button quiet", busy)}`;
  main.innerHTML = (
    { apply: landing, received, catalog, documents, review, status, paused }[
      state.screen
    ] || landing
  )();
  document.title = `SPACE | ${{ apply: "Start", received: "Received", catalog: "Catalog details", documents: "Documents", review: "Check your package", status: "Review status", paused: "Resume" }[state.screen]} - Preview`;
  storageNote();
}
function showErrors(next) {
  errors = next;
  render();
  const invalid = main.querySelector('[aria-invalid="true"]');
  if (invalid) invalid.focus();
  else main.focus();
}
function updateInput(target) {
  if (target.id === "reply") {
    state.reply = target.value.slice(0, 1500);
    save();
    return;
  }
  const group = target.dataset.group,
    key = target.name;
  if (!group || !Object.hasOwn(state[group] || {}, key)) return;
  state[group][key] = target.value.slice(0, 500);
  if (group === "details" && state.status === "SUBMITTED") {
    state.progress = 1;
    for (const step of main.querySelectorAll("[data-step]"))
      step.disabled = Number(step.dataset.step) > state.progress;
  }
  save();
}
main.addEventListener("input", (event) => updateInput(event.target));
main.addEventListener("change", (event) => updateInput(event.target));
async function addFile(kind, fail = false) {
  if (busy || state.status !== "SUBMITTED" || state.docs.includes(kind)) return;
  busy = true;
  busyKind = kind;
  fileError = "";
  fileErrorKind = "";
  render();
  announce("Adding a sample file in the demo.");
  await new Promise((resolve) => setTimeout(resolve, 550));
  if (fail) {
    fileErrorKind = kind;
    fileError =
      "Simulated upload failed. No file was added. Try again; your other progress is saved.";
  } else addDemoDocument(state, kind);
  busy = false;
  busyKind = "";
  save();
  render();
  const action = main.querySelector(
    `[data-action="${fail ? "add" : "remove"}:${kind}"]`,
  );
  action?.focus();
  announce(fail ? fileError : "Sample file added. It has not been reviewed.");
}
document.addEventListener("click", (event) => {
  const target = event.target.closest("button");
  if (!target || target.disabled || busy) return;
  if (target.dataset.step !== undefined) {
    const step = Number(target.dataset.step);
    if (state.status === "SUBMITTED" && step <= state.progress)
      go(["received", "catalog", "documents", "review"][step]);
    return;
  }
  const action = target.dataset.action;
  if (!action) return;
  if (action.startsWith("back:")) {
    go(action.split(":")[1]);
    return;
  }
  if (action.startsWith("add:")) {
    void addFile(action.split(":")[1]);
    return;
  }
  if (action.startsWith("remove:")) {
    state.docs = state.docs.filter((kind) => kind !== action.split(":")[1]);
    state.progress = Math.min(state.progress, 2);
    save();
    render();
    main.querySelector(`[data-action="add:${action.split(":")[1]}"]`)?.focus();
    return;
  }
  if (action === "sample-contact") {
    state.contact = { ...DEMO.contact };
    errors = {};
    save();
    render();
    main.querySelector('button[type="submit"]')?.focus();
    announce("Fictional contact details added.");
  }
  if (action === "sample-catalog") {
    state.details = { ...DEMO.details };
    state.progress = 1;
    errors = {};
    save();
    render();
    main.querySelector("#artistLink")?.focus();
    announce("Fictional catalog details added.");
  }
  if (action === "continue-catalog") go("catalog");
  if (action === "pause") {
    state.returnScreen = state.screen;
    go("paused");
  }
  if (action === "resume")
    go(state.returnScreen === "paused" ? "received" : state.returnScreen);
  if (action === "fail-submit") {
    failSubmit = !failSubmit;
    announce(
      failSubmit
        ? "The next demo submission will fail without losing your details."
        : "Normal demo submission restored.",
    );
    target.textContent = failSubmit
      ? "Next demo submission will fail"
      : "Make the next demo submission fail";
  }
  if (action === "upload-failure") void addFile("royalties", true);
  if (action === "request-clarification") {
    requestClarification(state);
    go("status");
    announce("Example reviewer question added. No real message was sent.");
  }
  if (action === "reset") {
    document.querySelector("#reset-slot").innerHTML =
      `<div class="reset-box" role="region" aria-label="Confirm demo reset"><p>Start over? This clears only this preview's saved demo.</p>${button("confirm-reset", "Clear and restart", "secondary")}${button("cancel-reset", "Keep working", "text-button")}</div>`;
    document.querySelector('[data-action="cancel-reset"]').focus();
  }
  if (action === "cancel-reset") {
    document.querySelector("#reset-slot").innerHTML = "";
    document.querySelector('#header-actions [data-action="reset"]')?.focus();
  }
  if (action === "confirm-reset") {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      storageWorks = false;
    }
    state = fresh();
    errors = {};
    fileError = "";
    fileErrorKind = "";
    failSubmit = false;
    document.querySelector("#reset-slot").innerHTML = "";
    document.querySelector("#storage-note").textContent = "";
    render();
    main.focus();
    window.scrollTo(0, 0);
    announce("Demo reset. No other data was changed.");
  }
});
main.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const id = event.target.id;
  if (id === "catalog-form") {
    const next = validateCatalog(state.details);
    if (Object.keys(next).length) return showErrors(next);
    state.progress = Math.max(2, state.progress);
    go("documents");
    return;
  }
  if (id === "documents-form") {
    if (missingDocuments(state).length) return;
    state.progress = 3;
    go("review");
    return;
  }
  if (id === "apply-form") {
    const next = validateContact(state.contact);
    if (Object.keys(next).length) return showErrors(next);
  }
  if (id === "reply-form" && !state.reply.trim())
    return showErrors({
      general: "Add a short clarification before sending the demo reply.",
    });
  busy = true;
  errors = {};
  render();
  announce("Simulating submission. No network request is made.");
  await new Promise((resolve) => setTimeout(resolve, 650));
  busy = false;
  if (failSubmit) {
    failSubmit = false;
    return showErrors({
      general:
        "Simulated submission failed. Your package is still here. Try again when ready.",
    });
  }
  if (id === "apply-form") {
    state.progress = 1;
    state.status = "SUBMITTED";
    go("received");
    announce("Demo application received. Nothing was submitted.");
  }
  if (id === "review-form") {
    try {
      submitPackage(state);
      go("status");
      announce("Demo package is under review. No real application was sent.");
    } catch (error) {
      showErrors({ general: error.message });
    }
  }
  if (id === "reply-form") {
    try {
      sendReply(state, state.reply);
      go("status");
      announce(
        "Demo clarification saved. It is not verified and was not emailed.",
      );
    } catch (error) {
      showErrors({ general: error.message });
    }
  }
});
render();
