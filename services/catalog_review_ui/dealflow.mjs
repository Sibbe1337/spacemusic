import { createClient, errorMessage, PortalError } from "./client.mjs";

const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const label = (value) => String(value).replaceAll("_", " ");
const checks = {
  scope: "Transaction scope",
  authority: "Authority to act",
  ownership: "Rights chain",
  income: "Royalty history",
  agreements: "Existing restrictions",
  catalog: "Included catalog",
};
const options = (items, selected) =>
  items
    .map(
      (i) =>
        `<option value="${escape(i)}"${selected === i ? " selected" : ""}>${escape(label(i))}</option>`,
    )
    .join("");
const field = (name, title, value = "", type = "text", extra = "") =>
  `<label class="field">${escape(title)}<input name="${escape(name)}" type="${type}" value="${escape(value)}" ${extra}></label>`;
const select = (name, title, values, current) =>
  `<label class="field">${escape(title)}<select name="${name}">${options(values, current)}</select></label>`;
const area = (name, title, value, max = 800) =>
  `<label class="field">${escape(title)}<textarea name="${name}" maxlength="${max}" required>${escape(value)}</textarea></label>`;

export function initialReview(view) {
  return structuredClone(
    view.review || {
      rights: "unknown",
      structure: "unknown",
      seller_goal: "",
      exclusions: "Future music is excluded. Confirm any other exclusions.",
      annual_net: null,
      currency: null,
      period_start: null,
      period_end: null,
      buyers: [],
      checks: Object.keys(checks).map((key) => ({
        key,
        status: "missing",
        sources: [],
        note: "Not yet reviewed.",
      })),
    },
  );
}

export function parseReview(form, model, view, requestId) {
  const values = new form.ownerDocument.defaultView.FormData(form);
  const body = structuredClone(model);
  for (const key of ["rights", "structure", "seller_goal", "exclusions"])
    body[key] = values.get(key);
  for (const key of ["annual_net", "currency", "period_start", "period_end"])
    body[key] = values.get(key) || null;
  body.checks = body.checks.map((c) => ({
    ...c,
    status: values.get(`${c.key}-status`),
    note: values.get(`${c.key}-note`),
    sources: values.getAll(`${c.key}-sources`),
  }));
  body.buyers = body.buyers.map((b, index) => ({
    ...b,
    name: values.get(`b${index}-name`),
    mandate_reference: values.get(`b${index}-reference`),
    checked_on: values.get(`b${index}-checked`),
    expires_on: values.get(`b${index}-expires`),
    rights: values.getAll(`b${index}-rights`),
    structures: values.getAll(`b${index}-structures`),
    minimum_annual_net: values.get(`b${index}-minimum`) || null,
    currency: values.get(`b${index}-currency`) || null,
  }));
  return {
    ...body,
    request_id: requestId,
    revision: view.revision,
    source_digest: view.evidence.digest,
  };
}

function sources(view, name, selected, documentsOnly = false) {
  return `<div class="source-list">${view.evidence.sources
    .filter((s) => !documentsOnly || s.kind === "document")
    .map(
      (s) =>
        `<label><input type="checkbox" name="${escape(name)}" value="${escape(s.id)}"${selected.includes(s.id) ? " checked" : ""}>${escape(s.label)} <small>(${escape(s.kind)})</small></label>`,
    )
    .join("")}</div>`;
}

function buyerForm(b, i) {
  const choices = (name, values, selected) =>
    `<div class="source-list">${values.map((v) => `<label><input type="checkbox" name="b${i}-${name}" value="${v}"${selected.includes(v) ? " checked" : ""}>${escape(label(v))}</label>`).join("")}</div>`;
  return `<details class="section" open><summary><span>Buyer mandate ${i + 1}: ${escape(b.name || "New buyer")}</span><span>Manual record</span></summary>${field(`b${i}-name`, "Recipient / buyer name", b.name, "text", 'required maxlength="120"')}${field(`b${i}-reference`, "Where were these criteria confirmed?", b.mandate_reference, "text", 'required maxlength="180"')}<div class="pair">${field(`b${i}-checked`, "Confirmed on", b.checked_on, "date", "required")}${field(`b${i}-expires`, "Reconfirm by (within 90 days)", b.expires_on, "date", "required")}</div><p class="form-help">Only record criteria actually provided by the buyer. This is not proof of funds or confirmation of interest.</p><fieldset><legend>Rights accepted</legend>${choices("rights", ["masters", "publishing", "both"], b.rights)}</fieldset><fieldset><legend>Structures accepted</legend>${choices("structures", ["full_sale", "partial_sale", "term_license"], b.structures)}</fieldset><div class="pair">${field(`b${i}-minimum`, "Optional minimum annual net", b.minimum_annual_net ?? "", "number", 'min="0" step="0.01"')}${select(`b${i}-currency`, "Minimum currency", ["", "EUR", "USD", "GBP", "SEK"], b.currency || "")}</div><button type="button" data-remove-buyer="${i}">Remove this mandate</button></details>`;
}

function editor(view, model) {
  return `<form id="review-form"><fieldset id="review-fields"><section id="checks"><h2>Evidence, not assumptions.</h2><p class="form-help">Reviewed means a named human has checked the cited material. It is not an ownership warranty. Keep restrictions and contradictory evidence visible.</p>${model.checks.map((c) => `<details class="check"><summary><span>${checks[c.key]}</span><span>${escape(label(c.status))}</span></summary><div class="check-body">${select(`${c.key}-status`, "Review status", ["missing", "seller_reported", "reviewed", "conflicting"], c.status)}<fieldset><legend>Supporting sources</legend>${sources(view, `${c.key}-sources`, c.sources)}</fieldset>${area(`${c.key}-note`, "Findings, limitations and contradictions", c.note, 600)}</div></details>`).join("")}</section><section class="section"><h2>Proposed scope</h2><div class="pair">${select("rights", "Rights offered", ["unknown", "masters", "publishing", "both"], model.rights)}${select("structure", "Transaction structure", ["unknown", "full_sale", "partial_sale", "term_license"], model.structure)}</div>${area("seller_goal", "Seller objective", model.seller_goal)}${area("exclusions", "Excluded rights, recordings and obligations", model.exclusions)}<p class="form-help">Future music always remains excluded. Clarify shares and any time limit in the objective.</p></section><details class="section"><summary><span>Documented net revenue</span><span>No valuation</span></summary><p class="form-help">Enter only reconciled twelve-month net receipts. Do not sum overlapping reports or convert currencies here. A complete period and supporting document are required before marking income reviewed.</p><div class="pair">${field("annual_net", "Twelve-month net receipts", model.annual_net ?? "", "number", 'min="0" step="0.01"')}${select("currency", "Currency", ["", "EUR", "USD", "GBP", "SEK"], model.currency || "")}${field("period_start", "Period starts", model.period_start || "", "date")}${field("period_end", "Period ends", model.period_end || "", "date")}</div></details><section id="mandates" class="section"><h2>Who could this fit?</h2><p class="form-help">Up to ten current, named mandates per case. No scraped investor lists or automatic contact.</p>${model.buyers.map(buyerForm).join("")}<button type="button" id="add-buyer"${model.buyers.length >= 10 ? " disabled" : ""}>Add a documented buyer mandate</button></section><div class="actions"><button class="primary" type="submit">Save reviewed version</button></div><p class="review-limit">New versions invalidate previous presentation approvals. Saving does not send anything.</p></fieldset></form>`;
}

export function packageHtml(p, role) {
  const data = p.payload;
  return `<article class="package"><p class="eyebrow">${escape(label(p.status))}</p><h3>Introduction to ${escape(data.recipient.name)}</h3><p>${escape(data.purpose)}</p><details><summary><span>Read the exact presentation</span><span>Version ${data.review_revision}</span></summary><dl><dt>Rights / structure</dt><dd>${escape(label(data.rights))} / ${escape(label(data.structure))}</dd><dt>Seller objective</dt><dd>${escape(data.seller_goal)}</dd><dt>Exclusions</dt><dd>${escape(data.exclusions)}</dd><dt>Future music</dt><dd>Always excluded</dd><dt>Reported net receipts</dt><dd>${escape(data.reported_financials.annual_net ?? "Not established")} ${escape(data.reported_financials.currency || "")}</dd><dt>Reporting period</dt><dd>${escape(data.reported_financials.period_start || "Unknown")} to ${escape(data.reported_financials.period_end || "unknown")}</dd></dl><h3>All review findings</h3>${data.review_notes.map((c) => `<p><strong>${checks[c.key]}</strong>: ${escape(c.note)}</p>`).join("")}<h3>Documents proposed for this recipient</h3>${data.documents.length ? `<ul>${data.documents.map((d) => `<li>${escape(d.label)} <span class="source-ref">SHA-256 ${escape(d.sha256)}</span></li>`).join("")}</ul>` : "<p>No documents included.</p>"}<p class="notice">${escape(data.limitations)}</p><p class="source-ref">Presentation fingerprint: ${escape(p.digest)}</p></details><p class="form-help">Approval expires ${escape(new Date(p.expires_at).toLocaleString())}. New evidence or a changed review invalidates it earlier. No message is sent by this application.</p>${role === "owner" && p.status === "awaiting_owner_approval" ? `<form data-decision="${p.package_id}"><label class="consent"><input name="consent" type="checkbox" required>I have read this exact presentation, including the findings and listed documents, and authorize SPACE to use it only for an introduction to ${escape(data.recipient.name)}. This does not approve a sale or onward circulation.</label><div class="actions"><button class="primary" type="submit">Approve this presentation</button><button type="button" data-decision-action="declined" data-package="${p.package_id}">Decline</button></div></form>` : ""}${role === "owner" && p.status === "approved" ? `<button type="button" data-decision-action="revoked" data-package="${p.package_id}">Revoke this approval</button>` : ""}${role === "reviewer" && p.status === "approved" ? '<p class="notice">Seller approval recorded. Delivery remains disabled; no buyer has received this presentation.</p>' : ""}</article>`;
}

const growth = `<section id="growth" class="section"><p class="eyebrow">Acquisition worklist / drafts only</p><h2>More of the right conversations.</h2><p>Improve the quality of existing leads before buying more traffic. These are proposed experiments, not measured results or published changes.</p><div class="growth-list"><article><h3>01 / Close the missing-information loop</h3><p>Prioritize cases waiting for a specific document. Review the next question, then use the existing portal conversation. Do not start a marketing sequence from an application consent.</p><a href="/workspace/#questions">Open the current case conversation</a></article><article><h3>02 / Test partner referrals</h3><p>Prepare a seller-facing introduction for managers, accountants and label administrators. The owner submits their own application; do not import a partner's private contact list.</p><a href="https://spacemusic.io/apply/" target="_blank" rel="noopener noreferrer">Inspect the existing application journey</a></article><article><h3>03 / Make the calculator's next step clearer</h3><p>Draft a scope check explaining that a scenario is not an offer, and invite an individual review. Preserve the existing URL, content and metadata. Publish only after separate preview approval.</p><a href="https://spacemusic.io/calculator/" target="_blank" rel="noopener noreferrer">Inspect the existing calculator</a></article></div><p class="notice">Measure unique received applications, reviewed applications, seller-approved presentations and actual introductions separately, over equal complete 28-day periods. Unknown or unreviewed leads are not rejected leads. Traffic and keyword volume are not measured in this workspace.</p></section>`;

export function mountDealflow({
  document: doc = globalThis.document,
  window: win = globalThis.window,
  client = createClient(),
  uuid = () => crypto.randomUUID(),
  now = () => Date.now(),
  schedule = setTimeout,
  unschedule = clearTimeout,
} = {}) {
  const root = doc.getElementById("deal-content"),
    announcement = doc.getElementById("deal-announcement");
  let view = null,
    model = null,
    busy = false,
    pending = null,
    dirty = false,
    epoch = 0,
    timer = null,
    identity = null;
  const announce = (t) => {
    announcement.textContent = t;
  };
  function clear(message, cancel = true) {
    epoch++;
    unschedule(timer);
    if (cancel) client.clear();
    view = null;
    model = null;
    pending = null;
    dirty = false;
    busy = false;
    identity = null;
    root.innerHTML = `<h1>Workspace closed.</h1><p>${escape(message)}</p><a href="/workspace/">Return to catalog access</a>`;
    announce(message);
  }
  function capture() {
    const f = doc.getElementById("review-form");
    if (f && view?.role === "reviewer")
      model = parseReview(f, model, view, uuid());
  }
  function render() {
    if (!view) return;
    const assessment = view.assessment;
    root.innerHTML = `<p class="eyebrow">${view.role === "reviewer" ? "Assigned reviewer / catalog passport" : "Catalog owner / sharing control"}</p><h1>${view.role === "reviewer" ? "From inquiry.<br>To a considered introduction." : "Your catalog.<br>Your permission."}</h1><p class="intro">${view.role === "reviewer" ? "Keep the facts, the missing pieces and the next action in one place. Nothing moves to a buyer without the owner reviewing the exact presentation." : "Review the named recipient, exact text and document list before deciding. You can decline or revoke without changing your original catalog submission."}</p><div class="meta"><span>Review version ${view.revision}</span><span>${view.role === "reviewer" ? `${assessment.reviewed_checks} of ${assessment.total_checks} checks reviewed` : "Recipient-specific approval"}</span><span>No automatic sending</span></div><div id="deal-feedback" role="status"></div>${pending ? '<div class="notice">The last request may have been saved. Retry the same request or reload the server state before changing anything.<div class="actions"><button id="retry">Retry same request</button><button id="reconcile">Reload server state</button></div></div>' : ""}${view.role === "reviewer" ? `<nav class="step-links" aria-label="Deal preparation"><a href="#checks">Evidence</a><a href="#mandates">Buyer mandates</a><a href="#presentations">Presentations</a><a href="#growth">Acquisition worklist</a></nav><div class="columns"><div>${editor(view, model)}</div><aside class="side"><section class="next-action"><p class="eyebrow">Next useful action</p><h2>${escape(assessment.actions[0]?.title || "Review the buyer fit.")}</h2><p>${escape(assessment.actions[0]?.question || "The checklist is complete. A matching mandate permits preparation, not sharing.")}</p><a href="/workspace/#questions">Open the case conversation</a></section><h2>Buyer fit</h2><p class="form-help">Based on the last saved version only. No investment score, inferred budget or guarantee of interest.</p>${assessment.matches.map((m) => `<article class="buyer"><span class="pill">${escape(label(m.status))}</span><h3>${escape(m.name)}</h3><ul>${m.reasons.map((r) => `<li>${escape(r)}</li>`).join("")}</ul>${m.status === "candidate_for_introduction" ? `<form data-prepare="${m.buyer_id}"><fieldset><legend>Documents to propose sharing</legend>${sources(view, `share-docs-${m.buyer_id}`, [], true)}</fieldset><button class="primary" type="submit"${dirty ? " disabled" : ""}>Prepare for owner approval</button></form>` : ""}</article>`).join("") || '<p class="form-help">No buyer mandates recorded. Add only confirmed requirements, not guesses.</p>'}<p class="review-limit">${escape(assessment.limitations)}</p></aside></div>` : ""}<section id="presentations" class="section"><h2>Presentations &amp; permissions</h2>${view.packages.map((p) => packageHtml(p, view.role)).join("") || '<p class="form-help">No presentations prepared. Complete a review and record a matching buyer mandate first.</p>'}</section>${view.role === "reviewer" ? growth : ""}`;
    if (pending || busy)
      for (const el of root.querySelectorAll("fieldset,form button,form input"))
        el.disabled = true;
  }
  async function load({ discard = false } = {}) {
    if (busy) return;
    if (
      (dirty || pending) &&
      !discard &&
      !win.confirm(
        "Reload the saved version? Unsaved entries will be discarded. Any already-saved request remains on the server.",
      )
    )
      return;
    const ticket = ++epoch;
    busy = true;
    announce("Loading current case.");
    try {
      const workspace = await client.workspace();
      if (ticket !== epoch) return;
      if (
        identity &&
        (identity.id !== workspace.workspace_id ||
          identity.role !== workspace.role)
      )
        return clear(
          "The active case or account changed. Reopen the workspace.",
        );
      client.setCsrf(workspace.csrf);
      const next = await client.dealflow();
      if (ticket !== epoch) return;
      if (
        !["owner", "reviewer"].includes(next.role) ||
        next.role !== workspace.role ||
        !Array.isArray(next.packages) ||
        !Number.isSafeInteger(next.revision)
      )
        throw new Error("contract");
      const remaining = Date.parse(workspace.session_expires_at) - now();
      if (!(remaining > 0)) return clear("Your session has expired.");
      unschedule(timer);
      timer = schedule(
        () =>
          clear(
            "Your session has expired. Reopen your invitation or staff access.",
          ),
        Math.min(remaining, 3600000),
      );
      identity = { id: workspace.workspace_id, role: workspace.role };
      view = next;
      model = next.role === "reviewer" ? initialReview(next) : null;
      dirty = false;
      busy = false;
      render();
      root.focus({ preventScroll: true });
      announce(
        pending
          ? "Current case loaded. The pending request still needs a same-reference retry to confirm its outcome."
          : "Current case loaded.",
      );
      return true;
    } catch (error) {
      if (ticket !== epoch) return;
      if ([401, 403, 404].includes(error.status))
        return clear(errorMessage(error));
      root.innerHTML = `<h1>Workspace unavailable.</h1><p>${escape(errorMessage(error))}</p><button id="deal-open">Try again</button>`;
      announce("Unable to load this case.");
    } finally {
      if (ticket === epoch) busy = false;
    }
  }
  async function mutate(kind, body, identifier) {
    if (busy) return;
    const ticket = epoch;
    pending ??= { kind, body: structuredClone(body), identifier };
    busy = true;
    render();
    try {
      const ack = await client[pending.kind](pending.body, pending.identifier);
      if (ticket !== epoch) return;
      if (
        !ack ||
        typeof ack.created !== "boolean" ||
        (pending.kind === "dealflowSave" &&
          (!Number.isSafeInteger(ack.revision) ||
            ack.revision !== pending.body.revision + 1)) ||
        (pending.kind === "dealflowPrepare" &&
          !/^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(ack.package_id))
      )
        throw new PortalError("contract");
      pending = null;
      dirty = false;
      busy = false;
      if (await load({ discard: true }))
        announce("Saved. No external message was sent.");
    } catch (error) {
      if (ticket !== epoch) return;
      busy = false;
      if ([401, 403, 404].includes(error.status))
        return clear(errorMessage(error));
      if ([409, 422].includes(error.status)) pending = null;
      render();
      const feedback = doc.getElementById("deal-feedback");
      feedback.className = "notice error";
      feedback.textContent = errorMessage(error);
      feedback.tabIndex = -1;
      feedback.focus();
      announce(feedback.textContent);
    }
  }
  async function click(event) {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.id === "deal-logout") {
      const request = client.logout();
      clear(
        "Private data cleared from this screen. If logout could not reach the server, its session expires automatically.",
        false,
      );
      try {
        await request;
      } catch {}
      return;
    }
    if (busy) return;
    if (
      button.id === "deal-open" ||
      button.id === "deal-refresh" ||
      button.id === "reconcile"
    )
      return load();
    if (button.id === "retry" && pending)
      return mutate(pending.kind, pending.body, pending.identifier);
    if (pending) return;
    if (button.id === "add-buyer") {
      capture();
      model.buyers.push({
        buyer_id: uuid(),
        name: "",
        mandate_reference: "",
        checked_on: "",
        expires_on: "",
        rights: [],
        structures: [],
        minimum_annual_net: null,
        currency: null,
      });
      dirty = true;
      render();
      return;
    }
    if (button.dataset.removeBuyer !== undefined) {
      capture();
      model.buyers.splice(Number(button.dataset.removeBuyer), 1);
      dirty = true;
      render();
      return;
    }
    if (button.dataset.decisionAction) {
      const p = view.packages.find(
        (p) => p.package_id === button.dataset.package,
      );
      if (
        p &&
        win.confirm(
          `${label(button.dataset.decisionAction)} this presentation for ${p.payload.recipient.name}?`,
        )
      )
        await mutate(
          "dealflowDecide",
          {
            request_id: uuid(),
            digest: p.digest,
            decision: button.dataset.decisionAction,
          },
          p.package_id,
        );
    }
  }
  async function submit(event) {
    const form = event.target;
    if (!form.matches("#review-form,[data-prepare],[data-decision]")) return;
    event.preventDefault();
    if (busy || pending || !form.reportValidity()) return;
    if (form.id === "review-form") {
      const body = parseReview(form, model, view, uuid());
      model = structuredClone(body);
      await mutate("dealflowSave", body);
    } else if (form.dataset.prepare) {
      if (dirty) return;
      await mutate("dealflowPrepare", {
        request_id: uuid(),
        revision: view.revision,
        buyer_id: form.dataset.prepare,
        document_ids: new form.ownerDocument.defaultView.FormData(form)
          .getAll(`share-docs-${form.dataset.prepare}`)
          .map((id) => id.slice(9)),
      });
    } else {
      const p = view.packages.find(
        (p) => p.package_id === form.dataset.decision,
      );
      await mutate(
        "dealflowDecide",
        { request_id: uuid(), digest: p.digest, decision: "approved" },
        p.package_id,
      );
    }
  }
  function input(event) {
    if (event.target.closest("#review-form")) {
      dirty = true;
      for (const b of root.querySelectorAll("[data-prepare] button"))
        b.disabled = true;
    }
  }
  doc.addEventListener("click", click);
  root.addEventListener("submit", submit);
  root.addEventListener("input", input);
  const unload = (event) => {
    if (dirty || pending) {
      event.preventDefault();
      event.returnValue = "";
    }
  };
  win.addEventListener("beforeunload", unload);
  const hide = () =>
    clear("Workspace closed. Reopen the current case to continue.");
  win.addEventListener("pagehide", hide);
  return {
    load,
    destroy() {
      clear("Workspace closed.");
      doc.removeEventListener("click", click);
      root.removeEventListener("submit", submit);
      root.removeEventListener("input", input);
      win.removeEventListener("beforeunload", unload);
      win.removeEventListener("pagehide", hide);
    },
  };
}

if (globalThis.document?.documentElement.dataset.autostart === "true")
  mountDealflow();
