import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { mountDealflow, initialReview, packageHtml } from "./dealflow.mjs";
import { createClient } from "./client.mjs";

const require = createRequire(
  new URL("../seller_ui/package.json", import.meta.url),
);
const { JSDOM } = require("jsdom");
const html = await readFile(
  new URL("./dealflow.html", import.meta.url),
  "utf8",
);
const ID = (n) => `10000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const START = Date.parse("2026-09-25T12:00:00Z");
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const deferred = () => {
  let resolve;
  const promise = new Promise((r) => {
    resolve = r;
  });
  return { promise, resolve };
};
const workspace = (role) => ({
  workspace_id: ID(1),
  role,
  csrf: "synthetic-csrf",
  session_expires_at: new Date(START + 60000).toISOString(),
});
function view(role = "reviewer") {
  const review = initialReview({ review: null });
  review.seller_goal = "Synthetic partial catalog sale";
  review.rights = "masters";
  review.structure = "partial_sale";
  review.buyers = [
    {
      buyer_id: ID(2),
      name: "Fictional buyer",
      mandate_reference: "Synthetic reference",
      checked_on: "2026-09-25",
      expires_on: "2026-10-25",
      rights: ["masters"],
      structures: ["partial_sale"],
      minimum_annual_net: "0",
      currency: "EUR",
    },
  ];
  const result = { role, revision: 1, packages: [] };
  if (role === "reviewer")
    Object.assign(result, {
      review,
      evidence: {
        digest: "a".repeat(64),
        sources: [
          {
            id: `submission:${ID(3)}`,
            kind: "submission",
            label: "Submitted scope",
          },
          {
            id: `document:${ID(4)}`,
            kind: "document",
            label: "synthetic.csv",
            sha256: "b".repeat(64),
          },
        ],
      },
      assessment: {
        reviewed_checks: 0,
        total_checks: 6,
        actions: [
          { title: "Check scope", question: "Which rights are included?" },
        ],
        matches: [
          {
            buyer_id: ID(2),
            name: "Fictional buyer",
            status: "candidate_for_introduction",
            reasons: ["Synthetic match"],
          },
        ],
        limitations: "No automatic sending.",
      },
    });
  return result;
}
function presentation(status = "awaiting_owner_approval") {
  return {
    package_id: ID(5),
    digest: "c".repeat(64),
    expires_at: "2026-10-01T12:00:00Z",
    status,
    payload: {
      recipient: { buyer_id: ID(2), name: "Fictional buyer" },
      purpose: "One named recipient only.",
      rights: "masters",
      structure: "partial_sale",
      seller_goal: "Synthetic sale",
      exclusions: "Future music",
      reported_financials: {
        annual_net: "0",
        currency: "EUR",
        period_start: "2025-09-01",
        period_end: "2026-08-31",
      },
      review_revision: 1,
      review_notes: [{ key: "scope", note: "Documented synthetic share" }],
      documents: [{ label: "synthetic.csv", sha256: "b".repeat(64) }],
      limitations: "Not an offer.",
    },
  };
}
function fixture(t) {
  const dom = new JSDOM(html, {
      url: "https://review.test/dealflow/",
      runScripts: "outside-only",
    }),
    win = dom.window,
    doc = win.document;
  win.confirm = () => true;
  const queue = [],
    calls = [],
    unexpected = [],
    timers = new Set();
  let sequence = 100;
  const client = createClient({
    fetchImpl: async (path, options) => {
      const call = {
        path,
        options,
        body: options.body ? JSON.parse(options.body) : null,
      };
      calls.push(call);
      if (!queue.length) {
        unexpected.push(path);
        throw Error("Unexpected request");
      }
      const next = queue.shift();
      return typeof next === "function" ? next(call) : next;
    },
  });
  const app = mountDealflow({
    document: doc,
    window: win,
    client,
    uuid: () => ID(sequence++),
    now: () => START,
    schedule: (fn) => {
      timers.add(fn);
      return fn;
    },
    unschedule: (fn) => timers.delete(fn),
  });
  t.after(() => {
    app.destroy();
    win.close();
    assert.deepEqual(unexpected, []);
  });
  const get = (s) => {
    const e = doc.querySelector(s);
    assert.ok(e, s);
    return e;
  };
  async function until(predicate) {
    for (let i = 0; i < 100; i++) {
      if (predicate()) return;
      await new Promise((r) => setTimeout(r, 2));
    }
    assert.fail("UI did not settle");
  }
  const read = (next = view()) =>
    queue.push(json(workspace(next.role)), json(next));
  const open = async (next = view()) => {
    read(next);
    await app.load();
  };
  const set = (s, value) => {
    const e = get(s);
    e.value = value;
    e.dispatchEvent(new win.Event("input", { bubbles: true }));
  };
  const submit = (s) =>
    get(s).dispatchEvent(
      new win.Event("submit", { bubbles: true, cancelable: true }),
    );
  return {
    win,
    doc,
    app,
    get,
    set,
    submit,
    read,
    open,
    until,
    queue,
    calls,
    timers,
    click: (s) => get(s).click(),
    text: () => doc.body.textContent,
  };
}

test("explicit loading, separate roles, no browser persistence and same-origin reads", async (t) => {
  const f = fixture(t);
  assert.equal(f.calls.length, 0);
  await f.open();
  assert.equal(f.calls.length, 2);
  assert.ok(f.doc.querySelector("#review-form"));
  assert.equal(f.calls[1].path, "/api/portal/dealflow");
  assert.equal(f.calls[1].options.credentials, "same-origin");
  assert.equal(f.calls[1].options.cache, "no-store");
  assert.equal(f.win.localStorage.length, 0);
  assert.equal(f.win.sessionStorage.length, 0);
});

test("owner sees only exact presentations, not editing or buyer research", async (t) => {
  const f = fixture(t),
    v = view("owner");
  v.packages = [presentation()];
  await f.open(v);
  assert.equal(f.doc.querySelector("#review-form"), null);
  assert.equal(f.doc.querySelector("#growth"), null);
  assert.match(f.text(), /One named recipient only/);
  assert.match(f.text(), /Documented synthetic share/);
});

test("review save keeps zero amounts, references and revision; double submit sends once", async (t) => {
  const f = fixture(t);
  await f.open();
  f.set("[name=annual_net]", "0");
  f.set("[name=currency]", "EUR");
  f.set("[name=period_start]", "2025-09-01");
  f.set("[name=period_end]", "2026-08-31");
  f.set("[name=scope-status]", "seller_reported");
  f.click("[name=scope-sources]");
  const next = view();
  next.revision = 2;
  f.queue.push(json({ created: true, revision: 2 }));
  f.read(next);
  f.submit("#review-form");
  f.submit("#review-form");
  await f.until(() => f.text().includes("Review version 2"));
  const writes = f.calls.filter((c) => c.options.method === "POST");
  assert.equal(writes.length, 1);
  const saved = writes[0];
  assert.equal(saved.body.annual_net, "0");
  assert.equal(saved.body.buyers[0].minimum_annual_net, "0");
  assert.equal(saved.body.revision, 1);
  assert.equal(saved.body.source_digest, "a".repeat(64));
  assert.deepEqual(saved.body.checks[0].sources, [`submission:${ID(3)}`]);
  assert.equal(saved.options.headers["X-CSRF-Token"], "synthetic-csrf");
});

test("editing disables preparation and adding/removing a mandate preserves edits", async (t) => {
  const f = fixture(t);
  await f.open();
  f.set("[name=seller_goal]", "Changed objective");
  assert.equal(f.get("[data-prepare] button").disabled, true);
  f.click("#add-buyer");
  assert.equal(f.get("[name=seller_goal]").value, "Changed objective");
  f.click('[data-remove-buyer="1"]');
  assert.equal(f.get("[name=seller_goal]").value, "Changed objective");
  f.submit("[data-prepare]");
  assert.equal(f.calls.length, 2);
});

test("uncertain write locks edits and retries identical request bytes and ID", async (t) => {
  const f = fixture(t);
  await f.open();
  f.set("[name=seller_goal]", "Retain this exact objective");
  f.queue.push(() => {
    throw Error("offline");
  });
  f.submit("#review-form");
  await f.until(() => f.text().includes("connection is unavailable"));
  const first = f.calls.at(-1).options.body;
  assert.equal(f.get("#review-fields").disabled, true);
  f.queue.push(json({ created: false, revision: 2 }));
  const v = view();
  v.revision = 2;
  f.read(v);
  f.click("#retry");
  await f.until(() => f.text().includes("Review version 2"));
  assert.equal(
    f.calls.filter((c) => c.options.method === "POST")[1].options.body,
    first,
  );
});

test("refresh cannot discard an unresolved preparation or allow a new request ID", async (t) => {
  const f = fixture(t);
  await f.open();
  f.queue.push(() => {
    throw Error("lost response");
  });
  f.submit("[data-prepare]");
  await f.until(() => f.text().includes("connection is unavailable"));
  const original = f.calls.at(-1).options.body;
  f.read();
  f.click("#reconcile");
  await f.until(() => f.text().includes("pending request still needs"));
  assert.ok(f.doc.querySelector("#retry"));
  assert.equal(f.get("#review-fields").disabled, true);
  f.submit("[data-prepare]");
  assert.equal(f.calls.filter((c) => c.options.method === "POST").length, 1);
  f.queue.push(json({ package_id: ID(5), created: false }));
  const v = view();
  v.packages = [presentation()];
  f.read(v);
  f.click("#retry");
  await f.until(() => f.text().includes("Saved."));
  assert.equal(
    f.calls.filter((c) => c.options.method === "POST")[1].options.body,
    original,
  );
});

test("malformed acknowledgement remains unresolved and does not cause an automatic retry", async (t) => {
  const f = fixture(t);
  await f.open();
  f.queue.push(json({}));
  f.submit("[data-prepare]");
  await f.until(() => f.text().includes("incomplete or unsupported"));
  assert.ok(f.doc.querySelector("#retry"));
  assert.equal(f.calls.length, 3);
  assert.ok(!f.text().includes("Saved."));
});

test("validation rejection preserves editable values without claiming saved", async (t) => {
  const f = fixture(t);
  await f.open();
  f.set("[name=seller_goal]", "Retain invalid test draft");
  f.queue.push(json({ private: "must not display" }, 422));
  f.submit("#review-form");
  await f.until(() => f.text().includes("Check your entries"));
  assert.equal(f.get("[name=seller_goal]").value, "Retain invalid test draft");
  assert.equal(f.get("#review-fields").disabled, false);
  assert.equal(f.doc.querySelector("#retry"), null);
  assert.ok(!f.text().includes("must not display"));
  assert.ok(!f.text().includes("Saved."));
});

test("preparation includes only explicitly selected documents, never the full case", async (t) => {
  const f = fixture(t);
  await f.open();
  f.click("[data-prepare] input");
  f.queue.push(json({ created: true, package_id: ID(5) }));
  const v = view();
  v.packages = [presentation()];
  f.read(v);
  f.submit("[data-prepare]");
  await f.until(() => f.text().includes("Introduction to Fictional buyer"));
  const call = f.calls.find((c) => c.options.method === "POST");
  assert.equal(call.path, "/api/portal/dealflow/packages");
  assert.deepEqual(call.body.document_ids, [ID(4)]);
  assert.equal(call.body.buyer_id, ID(2));
  assert.deepEqual(Object.keys(call.body).sort(), [
    "buyer_id",
    "document_ids",
    "request_id",
    "revision",
  ]);
});

test("owner approval requires checked consent and binds to exact presentation digest", async (t) => {
  const f = fixture(t),
    v = view("owner");
  v.packages = [presentation()];
  await f.open(v);
  f.submit("[data-decision]");
  assert.equal(f.calls.length, 2);
  f.click("[name=consent]");
  f.queue.push(json({ created: true }));
  v.packages = [presentation("approved")];
  f.read(v);
  f.submit("[data-decision]");
  await f.until(() => f.doc.querySelector("[data-decision-action=revoked]"));
  const call = f.calls.find((c) => c.options.method === "POST");
  assert.equal(call.body.digest, "c".repeat(64));
  assert.equal(call.body.decision, "approved");
  assert.equal(call.path, `/api/portal/dealflow/packages/${ID(5)}/decision`);
  assert.ok(f.calls.every((c) => c.path.startsWith("/api/portal/")));
});

test("revocation and refusal send exact bound decision, while cancel sends nothing", async (t) => {
  const f = fixture(t),
    v = view("owner");
  v.packages = [presentation("approved")];
  await f.open(v);
  f.win.confirm = () => false;
  f.click("[data-decision-action=revoked]");
  assert.equal(f.calls.length, 2);
  f.win.confirm = () => true;
  f.queue.push(json({ created: true }));
  v.packages = [presentation("revoked")];
  f.read(v);
  f.click("[data-decision-action=revoked]");
  await f.until(() => f.text().includes("revoked"));
  assert.equal(
    f.calls.find((c) => c.options.method === "POST").body.decision,
    "revoked",
  );
  assert.equal(f.doc.querySelector("[data-decision]"), null);
});

for (const status of [401, 403, 404])
  test(`access loss ${status} clears private data`, async (t) => {
    const f = fixture(t);
    await f.open();
    f.queue.push(json({}, status));
    f.submit("#review-form");
    await f.until(() => f.text().includes("Workspace closed."));
    assert.ok(!f.text().includes("Fictional buyer"));
    assert.equal(f.doc.querySelector("#retry"), null);
  });

test("session expiry and pagehide clear evidence and pending work", async (t) => {
  const f = fixture(t);
  await f.open();
  for (const fire of [...f.timers]) fire();
  assert.match(f.text(), /session has expired/);
  assert.ok(!f.text().includes("Fictional buyer"));
  await f.open();
  f.win.dispatchEvent(new f.win.Event("pagehide"));
  assert.ok(!f.text().includes("Fictional buyer"));
  assert.equal(f.doc.querySelector("#review-form"), null);
});

test("logout during an outstanding save ignores late success and still attempts server logout", async (t) => {
  const f = fixture(t);
  await f.open();
  const pending = deferred();
  f.queue.push(() => pending.promise);
  f.submit("#review-form");
  f.queue.push(new Response(null, { status: 204 }));
  f.click("#deal-logout");
  pending.resolve(json({ created: true }));
  await f.until(() => f.calls.some((c) => c.options.method === "DELETE"));
  assert.match(f.text(), /Workspace closed/);
  assert.ok(!f.text().includes("Fictional buyer"));
  assert.ok(!f.text().includes("Saved."));
  assert.equal(
    f.calls.find((c) => c.options.method === "DELETE").options.signal.aborted,
    false,
  );
});

test("account changes do not silently replace the active case", async (t) => {
  const f = fixture(t);
  await f.open();
  f.queue.push(json({ ...workspace("reviewer"), workspace_id: ID(99) }));
  await f.app.load();
  assert.match(f.text(), /active case or account changed/);
  assert.equal(f.calls.length, 3);
});

test("double logout and page suspension preserve one navigation-safe revocation", async (t) => {
  const f = fixture(t);
  await f.open();
  const pending = deferred();
  f.queue.push(() => pending.promise);
  f.click("#deal-logout");
  f.click("#deal-logout");
  f.win.dispatchEvent(new f.win.Event("pagehide"));
  const deletes = f.calls.filter((c) => c.options.method === "DELETE");
  assert.equal(deletes.length, 1);
  assert.equal(deletes[0].options.signal.aborted, false);
  assert.equal(deletes[0].options.keepalive, true);
  assert.ok(!f.text().includes("Fictional buyer"));
  pending.resolve(new Response(null, { status: 204 }));
});

test("failed authoritative refresh never announces saved or restores old evidence", async (t) => {
  const f = fixture(t);
  await f.open();
  f.queue.push(json({ created: true, revision: 2 }), json({}, 403));
  f.submit("#review-form");
  await f.until(() => f.text().includes("Workspace closed."));
  assert.ok(!f.text().includes("Saved."));
  assert.ok(!f.text().includes("Fictional buyer"));
});

test("free text is escaped and stale/expired packages have no approval controls", () => {
  for (const state of ["stale", "expired", "revoked", "declined"]) {
    const p = presentation(state);
    p.payload.recipient.name = "<img src=x onerror=alert(1)>";
    p.payload.review_notes[0].note = "<script>bad()</script>";
    const markup = packageHtml(p, "owner");
    assert.ok(!markup.includes("<img"));
    assert.ok(!markup.includes("<script>"));
    assert.ok(!markup.includes("data-decision="));
    assert.ok(!markup.includes("data-decision-action="));
  }
});
