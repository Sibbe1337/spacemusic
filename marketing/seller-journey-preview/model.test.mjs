import test from "node:test";
import assert from "node:assert/strict";
import {
  fresh,
  DEMO,
  DOCUMENTS,
  validateContact,
  validateCatalog,
  validateDemoFile,
  addDemoDocument,
  missingDocuments,
  submitPackage,
  requestClarification,
  sendReply,
  restore,
} from "./model.mjs";

function prepared() {
  return {
    ...fresh(),
    contact: { ...DEMO.contact },
    details: { ...DEMO.details },
    status: "SUBMITTED",
    progress: 2,
    screen: "documents",
  };
}
function reviewed() {
  const state = prepared();
  addDemoDocument(state, "royalties");
  addDemoDocument(state, "tracks");
  submitPackage(state);
  return state;
}
test("initial and sample states have no real customer data", () => {
  assert.equal(fresh().status, "DRAFT");
  assert.deepEqual(validateContact(DEMO.contact), {});
  assert.deepEqual(validateCatalog(DEMO.details), {});
  assert.match(DEMO.contact.email, /@example\.com$/);
  assert.deepEqual(restore(JSON.stringify(fresh())), fresh());
});
test("contact errors retain user input", () => {
  const c = { name: "", email: "bad@", artist: " " };
  assert.deepEqual(Object.keys(validateContact(c)), ["email", "artist"]);
  assert.equal(c.email, "bad@");
});
test("required fields reject blanks", () => {
  const errors = validateCatalog(fresh().details);
  assert.deepEqual(
    Object.keys(errors).sort(),
    [
      "distributor",
      "tracks",
      "rights",
      "owned",
      "offered",
      "revenue",
      "currency",
      "periodStart",
      "periodEnd",
      "basis",
      "agreements",
    ].sort(),
  );
  assert.equal(errors.artistLink, undefined);
  assert.equal(errors.cutoff, undefined);
});
for (const key of ["owned", "offered"]) {
  test(`${key}: percentage bounds and non-numeric input`, () => {
    for (const value of [
      "0",
      "-1",
      "100.01",
      "",
      "NaN",
      "Infinity",
      "1e2",
      "0.001",
    ])
      assert(validateCatalog({ ...DEMO.details, [key]: value })[key], value);
    for (const value of ["0.01", "50", "100"])
      assert.equal(
        validateCatalog({ ...DEMO.details, [key]: value })[key],
        undefined,
      );
  });
}
test("zero reported income accepted; negative, blank and excessive amounts rejected", () => {
  assert.equal(
    validateCatalog({ ...DEMO.details, revenue: "0" }).revenue,
    undefined,
  );
  for (const revenue of ["", "-1", "1.123", "1000000001", "NaN", "Infinity"])
    assert(validateCatalog({ ...DEMO.details, revenue }).revenue);
});
test("record count, months and calendar dates validated", () => {
  for (const tracks of ["0", "1.5", "1000001", "abc"])
    assert(validateCatalog({ ...DEMO.details, tracks }).tracks);
  assert(validateCatalog({ ...DEMO.details, periodEnd: "2025-08" }).periodEnd);
  assert(
    validateCatalog({ ...DEMO.details, periodStart: "2025-13" }).periodStart,
  );
  assert(validateCatalog({ ...DEMO.details, cutoff: "2026-02-30" }).cutoff);
  assert.equal(
    validateCatalog({
      ...DEMO.details,
      periodStart: "2026-08",
      periodEnd: "2026-08",
    }).periodEnd,
    undefined,
  );
});
test("unknown rights, splits and currency stay review questions, not rejections", () => {
  assert.deepEqual(
    validateCatalog({
      ...DEMO.details,
      rights: "unsure",
      agreements: "unknown",
      currency: "Other",
      basis: "unsure",
      distributor: "Not sure",
    }),
    {},
  );
  assert(
    validateCatalog({ ...DEMO.details, artistLink: "javascript:alert(1)" })
      .artistLink,
  );
  assert.equal(
    validateCatalog({ ...DEMO.details, artistLink: "" }).artistLink,
    undefined,
  );
});
test("synthetic file metadata validation and duplicate prevention", () => {
  for (const name of ["a.csv", "a.tsv", "a.PDF", "a.xlsx"])
    assert.equal(validateDemoFile({ name, size: 1 }), "");
  for (const size of [0, -1, NaN, Infinity, 25 * 1024 * 1024 + 1])
    assert(validateDemoFile({ name: "a.csv", size }));
  assert(validateDemoFile({ name: "a.exe", size: 1 }));
  const state = prepared();
  assert.throws(() => addDemoDocument(fresh(), "royalties"));
  assert.throws(() => addDemoDocument(state, "__proto__"));
  addDemoDocument(state, "royalties");
  addDemoDocument(state, "royalties");
  assert.deepEqual(state.docs, ["royalties"]);
  assert.deepEqual(missingDocuments(state), ["tracks"]);
  assert(DOCUMENTS.royalties.name.startsWith("DEMO-"));
});
test("package requires complete evidence and cannot submit twice", () => {
  assert.throws(() => submitPackage(prepared()));
  const state = reviewed();
  assert.equal(state.status, "UNDER_REVIEW");
  assert.equal(state.progress, 4);
  assert.throws(() => submitPackage(state));
  assert.equal("valuation" in state, false);
  assert.equal("verified" in state, false);
});
test("clarification requires a valid stage and a meaningful reply", () => {
  assert.throws(() => requestClarification(fresh()));
  const state = reviewed();
  assert.throws(() => sendReply(state, "Not yet requested"));
  requestClarification(state);
  assert.throws(() => sendReply(state, "   "));
  assert.throws(() => sendReply(state, "a".repeat(1501)));
  sendReply(state, "  Fictional own share.  ");
  assert.equal(state.reply, "Fictional own share.");
  assert.equal(state.status, "UNDER_REVIEW");
  assert.throws(() => requestClarification(state));
  assert.deepEqual(restore(JSON.stringify(state)), state);
});
test("restore supports incomplete catalog and paused sessions", () => {
  const state = prepared();
  state.progress = 1;
  state.screen = "catalog";
  state.details.revenue = "";
  assert.deepEqual(restore(JSON.stringify(state)), state);
  state.returnScreen = state.screen;
  state.screen = "paused";
  assert.deepEqual(restore(JSON.stringify(state)), state);
});
test("restore rejects malformed, oversized and inconsistent sessions", () => {
  for (const raw of [null, "", "{broken", "a".repeat(20001), "null"])
    assert.equal(restore(raw), null);
  for (const overrides of [
    { version: 2 },
    { screen: "not-real" },
    { progress: 9 },
    { docs: ["royalties", "royalties"] },
    { docs: ["__proto__"] },
    { reply: "a".repeat(1501) },
    { status: "PAID" },
    { screen: "review", progress: 1 },
    { screen: "status" },
    { status: "SUBMITTED", progress: 4 },
    { replied: true },
    { screen: "paused", returnScreen: "paused" },
  ])
    assert.equal(
      restore(JSON.stringify({ ...prepared(), ...overrides })),
      null,
      JSON.stringify(overrides),
    );
});
