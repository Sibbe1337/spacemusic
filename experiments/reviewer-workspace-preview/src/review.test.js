import { describe, it, expect } from "vitest";
import {
  cases,
  initialCase,
  caseReducer as reduce,
  makeDraft,
  canReviewDraft,
  draftIsStale,
} from "./review.js";

const start = () => initialCase(cases[0]);
const prepared = () =>
  reduce(reduce(start(), { type: "confirm" }), { type: "prepare" });

describe("review state boundaries", () => {
  it("starts unreviewed and never pre-generates a message", () => {
    expect(start().reviewStatus).toBe("pending");
    expect(start().draft).toBeNull();
  });
  it("blocks drafting until a human decision", () => {
    expect(reduce(start(), { type: "prepare" })).toEqual(start());
  });
  it("does not mutate source fixtures or original state", () => {
    const s = start();
    reduce(s, { type: "field", field: "rights", value: "Publishing" });
    expect(s.fields.rights).toBe("Masters");
    expect(cases[0].rights).toBe("Masters");
    expect(Object.isFrozen(cases[0])).toBe(true);
  });
  it("rejects unknown fields and values", () => {
    const s = start();
    expect(
      reduce(s, { type: "field", field: "rights", value: "verified" }),
    ).toBe(s);
    expect(reduce(s, { type: "field", field: "__proto__", value: "x" })).toBe(
      s,
    );
  });
  it("invalidates confirmation on a changed field", () => {
    const s = reduce(reduce(start(), { type: "confirm" }), {
      type: "field",
      field: "structure",
      value: "Full sale",
    });
    expect(s.reviewStatus).toBe("pending");
  });
  it("does not invalidate an unchanged value", () => {
    const s = prepared();
    expect(
      reduce(s, { type: "field", field: "rights", value: "Masters" }),
    ).toBe(s);
  });
  it("keeps ambiguous publishing scope unclear", () => {
    const s = reduce(initialCase(cases[1]), { type: "confirm" });
    expect(s.reviewStatus).toBe("unclear");
    expect(s.fields.structure).toBe("Unclear");
  });
  it("allows a clarification draft for an unclear case", () => {
    const s = reduce(reduce(start(), { type: "unclear" }), { type: "prepare" });
    expect(canReviewDraft(s)).toBe(true);
    expect(s.draft.text).toContain("Are you offering master rights");
  });
  it("preserves edited text but marks it stale when classification changes", () => {
    const s = reduce(
      reduce(prepared(), { type: "edit", text: "My edited draft" }),
      { type: "field", field: "rights", value: "Publishing" },
    );
    expect(s.draft.text).toBe("My edited draft");
    expect(draftIsStale(s)).toBe(true);
    expect(canReviewDraft(reduce(s, { type: "confirm" }))).toBe(false);
  });
  it("refreshes only after an explicit prepare operation", () => {
    let s = reduce(prepared(), {
      type: "field",
      field: "rights",
      value: "Publishing",
    });
    s = reduce(reduce(s, { type: "confirm" }), { type: "prepare" });
    expect(draftIsStale(s)).toBe(false);
    expect(s.draft.text).toContain("publishing interests");
  });
  it("blocks empty and whitespace-only drafts", () => {
    for (const text of ["", "  \n "])
      expect(canReviewDraft(reduce(prepared(), { type: "edit", text }))).toBe(
        false,
      );
  });
  it("limits draft text to 6000 characters", () => {
    const s = prepared();
    expect(reduce(s, { type: "edit", text: "a".repeat(6001) })).toBe(s);
    expect(
      reduce(s, { type: "edit", text: "a".repeat(6000) }).draft.text.length,
    ).toBe(6000);
  });
  it("requires re-review after draft editing", () => {
    const s = reduce(reduce(prepared(), { type: "reviewed" }), {
      type: "edit",
      text: "Revision",
    });
    expect(s.draft.reviewed).toBe(false);
  });
  it("cannot approve a stale draft", () => {
    const s = reduce(prepared(), {
      type: "field",
      field: "rights",
      value: "Unclear",
    });
    expect(reduce(s, { type: "reviewed" }).draft.reviewed).toBe(false);
  });
  it("blocks copying/reviewing while classification is reopened", () => {
    const s = reduce(reduce(prepared(), { type: "reviewed" }), {
      type: "reopen",
    });
    expect(canReviewDraft(s)).toBe(false);
  });
  it("always asks about documents, currency, period, gross/net and exclusions", () => {
    const text = makeDraft(start().fields);
    for (const required of [
      "documents",
      "currency",
      "period",
      "gross or net",
      "excluded",
    ])
      expect(text).toContain(required);
  });
});
