import { DEMO, DISTRIBUTORS, CURRENCIES, validateCatalog } from "/model.mjs";

const main = document.querySelector("#main");
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let account = null,
  review = null,
  draft = {},
  step = "catalog",
  csrf = "",
  busy = false,
  error = "",
  notice = "",
  email = "",
  reply = "",
  pendingLink = "",
  messages = [],
  fieldErrors = {};
let mailTest = { enabled: false, recipient: "hello@spacemusic.io" },
  mailTestId = "",
  mailTestAccepted = false,
  mailTestExpired = false,
  mailTestOpened = false;
const button = (action, label, cls = "text-button", disabled = false) =>
  `<button type="button" data-action="${action}" class="${cls}" ${busy || disabled ? "disabled" : ""}>${label}</button>`;
const panels = ["catalog", "documents", "review"];
const note = () =>
  `${error ? `<div id="error" class="error-summary" role="alert" tabindex="-1">${esc(error)}</div>` : ""}${notice ? `<p class="saved-notice" role="status">${esc(notice)}</p>` : ""}`;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    headers: {
      "X-Space-Request": "portal-v1",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      ...(options.body && typeof options.body === "string"
        ? { "Content-Type": "application/json" }
        : {}),
      ...options.headers,
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      account = null;
      review = null;
      csrf = "";
      draft = {};
      reply = "";
    }
    throw new Error(
      Array.isArray(data.detail)
        ? data.detail.map((e) => `${e.field}: ${e.message}`).join(". ")
        : data.detail || "The request did not complete. Try again.",
    );
  }
  return data;
}
const json = (method, data) => ({ method, body: JSON.stringify(data) });
const path = (suffix) => `/api/reviews/${review.id}${suffix}`;
function acceptReview(value) {
  review = value;
  draft = value.catalog
    ? Object.fromEntries(
        Object.entries(value.catalog).map(([k, v]) => [k, String(v)]),
      )
    : Object.fromEntries(
        Object.keys(DEMO.details)
          .filter((key) => key !== "exclusions")
          .map((key) => [key, ""]),
      );
}
async function loadSession() {
  account = await api("/api/session");
  csrf = account.csrf;
  if (account.reviews.length) {
    acceptReview(await api(`/api/reviews/${account.reviews[0].id}`));
    step =
      review.status !== "SUBMITTED"
        ? "status"
        : !review.catalog
          ? "catalog"
          : "documents";
  }
}
function readLink() {
  if (!location.hash.startsWith("#sign-in=")) return;
  const candidate = location.hash.slice(9);
  history.replaceState(null, "", "/");
  pendingLink = /^[A-Za-z0-9_-]{43}$/.test(candidate) ? candidate : "";
  if (!pendingLink)
    error = "This sign-in link is not valid. Request another one.";
}
function render() {
  document.querySelector("#header-actions").innerHTML = account
    ? button("logout", "Sign out on all sessions", "text-button quiet")
    : "";
  if (pendingLink) {
    main.innerHTML = `<section class="portal-login"><p class="eyebrow">Confirm access</p><h1>Continue to your<br>catalog review.</h1><p class="lede">This single-use link expires after 15 minutes. Opening this page has not consumed it.</p>${note()}${button("consume", busy ? "Signing in..." : "Confirm sign-in", "primary")}<p class="fine">This local sign-in grants access to fictional test records only. It does not verify a real seller's identity.</p></section>`;
    return;
  }
  if (!account) {
    main.innerHTML = login();
    if (messages.length || mailTestId || mailTestOpened)
      main.querySelector(".preview-controls").open = true;
    return;
  }
  if (!review) {
    main.innerHTML = `<section class="portal-login"><h1>No review is available.</h1>${note()}<p>Sign in with the email used on your application.</p></section>`;
    return;
  }
  const editable = review.status === "SUBMITTED";
  main.innerHTML = `<div class="portal-main"><p class="eyebrow">Seller workspace / local test</p><div class="portal-toolbar"><h1>${esc(review.contact.artist)}</h1><span class="badge ${review.status === "DATA_REQUIRED" ? "warning" : ""}">${esc({ SUBMITTED: "Preparing your package", UNDER_REVIEW: "Under review", DATA_REQUIRED: "Your input needed" }[review.status])}</span></div>${account.reviews.length > 1 ? `<label class="field-label catalog-picker">Choose a review<select id="review-picker" ${busy ? "disabled" : ""}>${account.reviews.map((r) => `<option value="${r.id}" ${r.id === review.id ? "selected" : ""}>${esc(r.artist)}</option>`).join("")}</select></label>` : ""}${editable ? `<nav class="portal-tabs" aria-label="Review steps">${panels.map((name, i) => `<button type="button" data-action="step:${name}" class="text-button" ${step === name ? 'aria-current="step"' : ""} ${busy || (i > 0 && !review.catalog) ? "disabled" : ""}>${i + 1}. ${name[0].toUpperCase() + name.slice(1)}</button>`).join("")}</nav>` : ""}<div class="workspace"><section>${note()}${step === "catalog" && editable ? catalog() : step === "documents" && editable ? documents() : step === "review" && editable ? finalCheck() : status()}</section>${sidebar()}</div></div>`;
  document.title = `SPACE | ${review.status === "SUBMITTED" ? "Prepare catalog" : "Review status"} - Local test`;
}
function login() {
  return `<section class="portal-login"><p class="eyebrow">Continue your application</p><h1>Your catalog review.<br>Ready when you are.</h1><p class="lede">Sign in with the email used on your application. Your catalog, documents and next steps stay together.</p><p class="portal-info">This is a local integration test, not the live application form. Only fictional example.com identities are accepted. The form below uses a simulated mailbox; the separate owner email test sends real mail only when enabled.</p>${note()}<form id="login-form" class="card"><label for="email" class="field-label">Application email</label><input id="email" type="email" maxlength="254" required value="${esc(email)}" autocomplete="off" ${busy ? "disabled" : ""}><div class="stage-buttons"><button class="primary" ${busy ? "disabled" : ""}>Create local sign-in link</button></div><p class="fine">If an application matches, its link appears in the local test mailbox. Your session will use an HttpOnly cookie, not browser storage.</p></form><details class="preview-controls"><summary>Local test controls</summary><p>Set up the fictional Night Window application, then inspect the test email. This does not contact Formspree.</p><div class="portal-controls">${button("seed", "Create test application", "secondary")}${button("mailbox", "Open local test mailbox", "secondary")}</div>${messages.length ? messages.map((m) => `<article class="mail-preview"><h2>Continue your SPACE review</h2><p>To: ${esc(m.recipient)}</p><a class="primary" href="${esc(m.url)}">Open single-use sign-in link</a><p class="fine">Local email simulation. No message was delivered to an inbox.</p></article>`).join("") : ""}${ownerEmailPanel()}</details></section>`;
}
function ownerEmailPanel() {
  return `<section class="mail-preview"><h2>Real email test / owner only</h2><p>${mailTest.enabled ? `Sends one real sign-in email to <strong>${esc(mailTest.recipient)}</strong> for the fictional alex@example.com review. Create the test application first. Open the email link on this computer, not on your phone.` : "Real email testing is disabled. Start this local server with its private Resend credential file to enable it."}</p>${button("owner-email", mailTestAccepted ? "Accepted by Resend" : mailTestExpired ? "Test link expired" : mailTestId ? "Retry the same email test" : "Send test email to hello@spacemusic.io", "secondary", !mailTest.enabled || mailTestAccepted || mailTestExpired)}${mailTestId ? button("new-owner-email", "Prepare another email test", "text-button", !mailTest.enabled) : ""}<p class="fine">No customer data is sent. Provider acceptance does not prove inbox delivery. Reloading resumes the same test; preparing another test allows a separate email.</p></section>`;
}
function field(
  key,
  label,
  { type = "text", options, optional = false, help = "" } = {},
) {
  const attrs = `id="${key}" name="${key}" data-field="${key}" ${optional ? "" : "required"} ${busy ? "disabled" : ""} aria-describedby="${key}-help" ${fieldErrors[key] ? 'aria-invalid="true"' : ""}`;
  return `<div class="field"><label class="field-label" for="${key}">${label}${optional ? '<span class="optional">Optional</span>' : ""}</label>${
    options
      ? `<select ${attrs}><option value="">Select an answer</option>${options
          .map((o) => {
            const [v, l] = Array.isArray(o) ? o : [o, o];
            return `<option value="${v}" ${draft[key] === v ? "selected" : ""}>${l}</option>`;
          })
          .join("")}</select>`
      : `<input ${attrs} type="${type}" value="${esc(draft[key])}" maxlength="500" ${type === "number" ? 'step="0.01" min="0"' : ""}>`
  }<span class="help" id="${key}-help">${esc(fieldErrors[key] || help)}</span></div>`;
}
function catalog() {
  return `<p class="eyebrow">Step 1 / Your catalog</p><h2>What would you like us to review?</h2><p class="subtext">Save the recordings and reporting period. Figures remain unverified. Future recordings and publishing are not included automatically.</p><form id="catalog-form" novalidate><section class="form-section"><div class="section-heading"><h2>The music</h2>${button("sample-catalog", "Use sample catalog")}</div>${field("artistLink", "Link to your music", { type: "url", optional: true })}<div class="row">${field("distributor", "Distributor", { options: DISTRIBUTORS })}${field("tracks", "Recordings to review", { type: "number" })}</div></section><section class="form-section"><h2>The rights you propose</h2>${field(
    "rights",
    "Which rights?",
    {
      options: [
        ["masters", "Recording rights (masters)"],
        ["unsure", "Not sure yet"],
      ],
    },
  )}<div class="row">${field("owned", "Your ownership (%)", { type: "number" })}${field("offered", "Share of your ownership to sell (%)", { type: "number", help: "50% of a 50% share is 25% of the whole recording." })}</div>${field("cutoff", "Proposed catalog cutoff date", { type: "date", optional: true })}<div class="scope-note"><strong>Future recordings stay outside the proposed sale.</strong><p>The final recording list and contract define the scope. Supplying information does not transfer rights.</p></div>${field(
    "agreements",
    "Do agreements or other people affect these rights?",
    {
      options: [
        ["none-known", "None that I know of"],
        ["shared", "Shared royalties or other agreements"],
        ["unknown", "Not sure yet"],
      ],
      help: "Unknown remains an open review question.",
    },
  )}</section><section class="form-section"><h2>The income</h2><div class="row">${field("revenue", "Royalties for this statement period", { type: "number", help: "Zero is allowed. Do not annualize a partial reporting period." })}${field("currency", "Statement currency", { options: CURRENCIES })}</div><div class="row">${field("periodStart", "First statement month", { type: "month" })}${field("periodEnd", "Last statement month", { type: "month" })}</div>${field(
    "basis",
    "Whose income is this?",
    {
      options: [
        ["own-share", "My share after collaborator splits"],
        ["catalog-total", "Full catalog before splits"],
        ["unsure", "Not sure"],
      ],
    },
  )}</section><div class="actions">${button("reload", "Reload saved details", "text-button quiet")}<button class="primary" ${busy ? "disabled" : ""}>Save catalog and continue</button></div><p class="fine">Saved explicitly to this local server. Unsaved changes are not retained on refresh or sign-out.</p></form>`;
}
function sidebar() {
  return `<aside class="sidebar" aria-label="Review summary"><h2>${esc(review.contact.artist)}</h2><p>${esc(review.contact.email)}</p><ul class="summary-list"><li><span>Review cost</span><strong>Free</strong></li><li><span>Future music</span><strong>Excluded</strong></li><li><span>Documents</span><strong>${review.documents.length} of 2 items</strong></li><li><span>Data version</span><strong>${review.revision}</strong></li></ul><h3>You stay in control.</h3><p>Submitting a package is not accepting an offer. Every figure and rights claim needs human review.</p><p class="fine">Local integration only. Do not upload customer statements, contracts or personal data.</p></aside>`;
}
function documents() {
  return `<p class="eyebrow">Step 2 / Evidence</p><h2>Bring the source, not just the total.</h2><p class="portal-info">Use the bundled sample files to test the connected upload. Other synthetic files are quarantined and cannot be downloaded or submitted until a scanner is integrated.</p>${[
    "royalties",
    "tracks",
  ]
    .map((kind) => {
      const doc = review.documents.find((d) => d.kind === kind);
      return `<section class="document-item"><h2>${kind === "royalties" ? "Royalty statements" : "Track and rights list"}</h2>${doc ? `<div class="uploaded"><div><strong>${esc(doc.name)}</strong><p class="doc-status">${doc.scan === "TEST_FIXTURE" ? "Known test fixture. Not commercially verified." : "Quarantined. Scanning is not configured."}</p>${doc.scan === "TEST_FIXTURE" ? `<a href="${path(`/documents/${doc.id}/content`)}">Download your test file</a>` : ""}</div>${button(`remove:${doc.id}`, "Remove")}</div>` : `<p class="subtext">${kind === "royalties" ? "Original distributor exports, including reporting period and currency." : "Recording titles, ISRCs, release dates and ownership shares."}</p>${button(`fixture:${kind}`, "Add bundled sample", "secondary")}<label class="upload-label">Or choose a synthetic test file<input type="file" data-kind="${kind}" accept=".csv,.tsv,.pdf,.xlsx" ${busy ? "disabled" : ""}></label><p class="fine">CSV, TSV, PDF or XLSX, up to 25 MB. This is real local storage, not public hosting.</p>`}</section>`;
    })
    .join(
      "",
    )}<div class="actions">${button("step:catalog", "Back to catalog", "text-button quiet")}${button("step:review", "Review your package", "primary", review.documents.length !== 2)}</div>`;
}
const pairs = (rows) =>
  `<dl class="review-table">${rows.map(([a, b]) => `<div><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join("")}</dl>`;
function finalCheck() {
  const c = review.catalog;
  return `<p class="eyebrow">Step 3 / Final check</p><h2>Your catalog. Clearly defined.</h2><p class="subtext">Everything below was saved on the local server. Submitting locks this version for review; it does not transfer rights.</p>${pairs(
    [
      ["Recordings", c.tracks],
      ["Distributor", c.distributor],
      [
        "Rights",
        c.rights === "masters"
          ? "Recording rights; publishing excluded"
          : "Needs clarification",
      ],
      [
        "Ownership / share offered",
        `${c.owned}% owned / ${c.offered}% of that share offered`,
      ],
      ["Future music", "Excluded"],
      ["Proposed cutoff", c.cutoff || "To be agreed"],
      ["Reported income", `${c.currency} ${c.revenue} (unverified)`],
      ["Period", `${c.periodStart} to ${c.periodEnd}`],
      ["Income basis", c.basis],
      ["Agreements", c.agreements],
      [
        "Evidence",
        `${review.documents.length} items; not commercially verified`,
      ],
    ],
  )}<div class="scope-note"><strong>No automatic valuation.</strong><p>Income, rights and unresolved questions require human review before an offer can be considered.</p></div><div class="actions">${button("step:documents", "Back to evidence", "text-button quiet")}${button("submit", "Submit test package", "primary", review.documents.length !== 2 || review.documents.some((d) => d.scan !== "TEST_FIXTURE"))}</div>`;
}
function status() {
  return `<p class="eyebrow">Your next step</p><h2>${review.status === "DATA_REQUIRED" ? "One detail to clarify." : "Your package is in the review stage."}</h2><p class="lede">${review.status === "DATA_REQUIRED" ? "Reply below without starting another application." : "This local test package is saved. No actual reviewer has been notified."}</p>${review.messages.map((m) => `<article class="request-card"><h3>${m.role === "SELLER" ? "Your clarification" : "Test reviewer question"}</h3><p class="message-body">${esc(m.body)}</p><p class="fine">${m.role === "SELLER" ? "Received for review, not automatically verified." : "Generated by the local test control, not a real reviewer."}</p></article>`).join("")}${review.status === "DATA_REQUIRED" ? `<form id="reply-form" class="form-section"><label for="reply" class="field-label">Your clarification</label><textarea id="reply" required maxlength="1500" ${busy ? "disabled" : ""}>${esc(reply)}</textarea><div class="stage-buttons"><button class="primary" ${busy ? "disabled" : ""}>Send test clarification</button></div></form>` : ""}<section class="review-block"><h2>Your scope stays visible</h2>${pairs(
    [
      ["Recordings", review.catalog.tracks],
      ["Future music", "Excluded"],
      ["Proposed cutoff", review.catalog.cutoff || "To be agreed"],
      ["Evidence", "Unverified; human review required"],
    ],
  )}</section><details class="preview-controls"><summary>Local reviewer test control</summary><p>Test a request for clarification. This action does not contact SPACE or send email.</p>${button("question", "Create test reviewer question", "secondary", review.status !== "UNDER_REVIEW")}</details>`;
}
async function run(work) {
  if (busy) return;
  busy = true;
  error = "";
  notice = "";
  render();
  try {
    await work();
  } catch (e) {
    error = e.message;
  } finally {
    busy = false;
    render();
    const target =
      main.querySelector('[aria-invalid="true"]') ||
      main.querySelector("#error") ||
      main;
    target.focus();
    document.querySelector("#announcement").textContent =
      error || notice || "Local portal updated.";
  }
}
main.addEventListener("input", (event) => {
  if (event.target.dataset.field)
    draft[event.target.dataset.field] = event.target.value;
  if (event.target.id === "email") email = event.target.value;
  if (event.target.id === "reply") reply = event.target.value;
});
main.addEventListener("submit", (event) => {
  event.preventDefault();
  const id = event.target.id;
  if (id === "catalog-form") {
    fieldErrors = validateCatalog({
      ...draft,
      artistLink: draft.artistLink || "",
      cutoff: draft.cutoff || "",
    });
    if (Object.keys(fieldErrors).length) {
      error = "Check the highlighted fields. Your input is still here.";
      render();
      main.querySelector('[aria-invalid="true"]')?.focus();
      return;
    }
  }
  void run(async () => {
    if (id === "login-form") {
      const r = await api("/api/auth/request", json("POST", { email }));
      notice = r.message;
      messages = [];
    }
    if (id === "catalog-form") {
      acceptReview(
        await api(
          path("/catalog"),
          json("PUT", { revision: review.revision, catalog: draft }),
        ),
      );
      step = "documents";
      notice = "Catalog saved on the local server.";
    }
    if (id === "reply-form") {
      review = await api(
        path("/reply"),
        json("POST", { revision: review.revision, message: reply }),
      );
      reply = "";
      notice = "Clarification saved for human review.";
    }
  });
});
async function upload(kind, file) {
  if (
    !file ||
    !file.size ||
    file.size > 25 * 1024 * 1024 ||
    !/\.(csv|tsv|pdf|xlsx)$/i.test(file.name)
  )
    throw new Error("Choose a non-empty CSV, TSV, PDF or XLSX up to 25 MB.");
  review = await api(path(`/documents/${kind}?revision=${review.revision}`), {
    method: "POST",
    body: file,
    headers: {
      "Content-Type": "application/octet-stream",
      "X-File-Name": encodeURIComponent(file.name),
    },
  });
  notice = "File stored locally. Uploading does not verify its contents.";
}
main.addEventListener("change", (event) => {
  if (event.target.dataset.kind) {
    const kind = event.target.dataset.kind,
      file = event.target.files[0];
    if (file) void run(() => upload(kind, file));
  }
  if (event.target.id === "review-picker") {
    const id = event.target.value;
    void run(async () => {
      acceptReview(await api(`/api/reviews/${id}`));
      reply = "";
      fieldErrors = {};
      step = review.status === "SUBMITTED" ? "catalog" : "status";
    });
  }
});
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target || target.disabled || busy) return;
  const action = target.dataset.action;
  if (action === "owner-email") mailTestId ||= crypto.randomUUID();
  void run(async () => {
    if (action === "seed") {
      const r = await api("/api/development/seed", json("POST", {}));
      email = r.email;
      notice =
        "Fictional application is ready. Create its local sign-in link above.";
    }
    if (action === "mailbox") {
      messages = (await api("/api/development/mailbox")).messages.slice(-1);
      notice = messages.length
        ? "Local test email available below."
        : "No active test email yet. Request a link first.";
    }
    if (action === "owner-email") {
      const r = await api(
        "/api/development/email-test",
        json("POST", {
          request_id: mailTestId,
          confirm_owner_test: true,
        }),
      );
      mailTestAccepted = r.status === "accepted_by_provider";
      notice = r.message;
    }
    if (action === "new-owner-email") {
      mailTestId = "";
      mailTestAccepted = false;
      mailTestExpired = false;
      mailTestOpened = true;
      notice = "Ready for a separate email test. Nothing has been sent yet.";
    }
    if (action === "consume") {
      await api("/api/auth/consume", json("POST", { token: pendingLink }));
      pendingLink = "";
      messages = [];
      await loadSession();
    }
    if (action === "logout") {
      await api("/api/logout", json("POST", {}));
      account = null;
      review = null;
      csrf = "";
      draft = {};
      reply = "";
      messages = [];
      notice =
        "Signed out. All existing sessions for this test identity were revoked.";
    }
    if (action === "sample-catalog") {
      const { exclusions, ...sample } = DEMO.details;
      draft = { ...sample };
      fieldErrors = {};
      notice = "Fictional details filled. Save to continue.";
    }
    if (action.startsWith("step:")) step = action.split(":")[1];
    if (action === "reload") {
      acceptReview(await api(path("")));
      fieldErrors = {};
      notice = "Saved server version loaded.";
    }
    if (action.startsWith("fixture:")) {
      const kind = action.split(":")[1];
      const response = await fetch(`/api/development/fixtures/${kind}`, {
        headers: { "X-Space-Request": "portal-v1" },
      });
      if (!response.ok) throw new Error("Test fixture is unavailable");
      await upload(
        kind,
        new File(
          [await response.blob()],
          response.headers.get("x-fixture-name"),
          { type: "text/csv" },
        ),
      );
    }
    if (action.startsWith("remove:")) {
      review = await api(
        path(`/documents/${action.split(":")[1]}`),
        json("DELETE", { revision: review.revision }),
      );
      notice = "Test file removed.";
    }
    if (action === "submit") {
      review = await api(
        path("/submit"),
        json("POST", { revision: review.revision }),
      );
      step = "status";
      notice = "Test package saved for manual review.";
    }
    if (action === "question") {
      review = await api(
        `/api/development/reviews/${review.id}/question`,
        json("POST", {}),
      );
      notice = "Local test reviewer question added.";
    }
  });
});
window.addEventListener("hashchange", () => {
  readLink();
  render();
  main.focus();
});
readLink();
try {
  mailTest = await api("/api/development/email-test");
  if (mailTest.last_test) {
    mailTestId = mailTest.last_test.request_id;
    mailTestAccepted = mailTest.last_test.accepted;
    mailTestExpired = mailTest.last_test.expired;
  }
} catch {
  // Missing configuration must never break the simulated sign-in flow.
}
if (!pendingLink) {
  try {
    await loadSession();
  } catch (e) {
    if (!e.message.includes("session")) error = e.message;
  }
}
render();
