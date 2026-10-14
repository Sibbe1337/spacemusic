import test from "node:test";
import assert from "node:assert/strict";
import {
  economics,
  planningAssumptions,
  scenario,
  syntheticRows,
  summarize,
  sampleDefinition,
} from "./model.mjs";
const months = sampleDefinition.monthlyEuros.map(
  (_, i) => `2025-${String(i + 1).padStart(2, "0")}`,
);
const near = (a, b) => assert(Math.abs(a - b) < 0.000001, `${a} != ${b}`);

test("Synthetic totals tie to every breakdown and 216 unique source rows", () => {
  const rows = syntheticRows(),
    result = summarize(rows, months);
  assert.equal(rows.length, 216);
  assert.equal(result.totalCents, 1200000);
  for (const values of [result.monthly, result.tracks, result.platforms])
    assert.equal(
      Object.values(values).reduce((a, b) => a + b, 0),
      1200000,
    );
  assert.equal(result.tracks["DEMO-A"], 480000);
  assert.equal(result.tracks["DEMO-F"], 72000);
  assert.equal(result.platforms["Platform A"], 720000);
  assert.equal(result.firstQuarter, 330000);
  assert.equal(result.lastQuarter, 270000);
  near(result.quarterChange, -0.181818181818);
  assert.equal(result.concentrationAvailable, true);
});
test("Missing months are not zeros and disable trend/concentration", () => {
  const result = summarize(
    syntheticRows().filter((r) => r.month !== "2025-05"),
    months,
  );
  assert.deepEqual(result.missingMonths, ["2025-05"]);
  assert.equal(result.monthly["2025-05"], null);
  assert.equal(result.quarterChange, null);
  assert.equal(result.concentrationAvailable, false);
});
test("Explicit zero revenue is valid but no ratio or market value is invented", () => {
  const result = summarize(
    syntheticRows().map((r) => ({ ...r, netCents: 0 })),
    months,
  );
  assert.equal(result.totalCents, 0);
  assert.equal(result.missingMonths.length, 0);
  assert.equal(result.quarterChange, null);
  assert.equal(result.concentrationAvailable, false);
  assert.equal(scenario(0, 4, 50), 0);
});
test("Signed adjustments are retained; concentration withheld", () => {
  const rows = syntheticRows();
  rows.push({ ...rows[0], id: "ADJUSTMENT-1", netCents: -5000 });
  const result = summarize(rows, months);
  assert.equal(result.totalCents, 1195000);
  assert.equal(result.negativeRows, 1);
  assert.equal(result.concentrationAvailable, false);
});
test("Reject duplicate references, mixed currency, out-of-scope periods and fractional cents", () => {
  const rows = syntheticRows();
  assert.throws(() => summarize([...rows, rows[0]], months), /duplicate/);
  for (const change of [
    { currency: "USD" },
    { month: "2024-12" },
    { netCents: 0.2 },
    { netCents: NaN },
    { track: "" },
  ]) {
    assert.throws(() =>
      summarize([{ ...rows[0], ...change }, ...rows.slice(1)], months),
    );
  }
  assert.throws(() => summarize(rows, [...months, months[0]]));
});
test("Scenarios apply the share once to the stated income base", () => {
  assert.equal(scenario(1000 * 100 * 12, 4, 50), 2400000);
  assert.equal(scenario(1200000, 4, 0), 0);
  assert.equal(scenario(1200000, 4, 100), 4800000);
  for (const args of [
    [-1, 4, 50],
    [1200000, 0, 50],
    [1200000, 4, 101],
    [1200000, 4, -1],
    [1200000, NaN, 50],
    [1200000, "", 50],
    [Number.MAX_SAFE_INTEGER, 100, 100],
  ])
    assert.throws(() => scenario(...args));
});
test("Inclusive tax, gross payment fees, reserve and all labor are separated", () => {
  const r = economics(planningAssumptions);
  near(r.revenue, 79.2);
  near(r.fees, 3.77);
  near(r.reserve, 3.96);
  near(r.labor, 56.25);
  near(r.contribution, 10.22);
  near(economics({ ...planningAssumptions, minutes: 60 }).contribution, 21.47);
  near(economics({ ...planningAssumptions, minutes: 90 }).contribution, -1.03);
  near(
    economics({ ...planningAssumptions, gross: 149, minutes: 90 }).contribution,
    35.22,
  );
  near(r.breakEvenMinutes, 88.6266666667);
  near(r.revenue - r.fees - r.reserve - r.labor - r.otherCost, r.contribution);
});
test("Invalid economic inputs fail rather than fabricate a zero", () => {
  for (const key of Object.keys(planningAssumptions))
    for (const value of ["", NaN, Infinity, -1])
      assert.throws(() => economics({ ...planningAssumptions, [key]: value }));
  assert.throws(() => economics({ ...planningAssumptions, taxPercent: 101 }));
  assert.equal(
    economics({ ...planningAssumptions, hourlyCost: 0 }).breakEvenMinutes,
    null,
  );
  assert(economics({ ...planningAssumptions, gross: 0 }).contribution < 0);
});
test("Quarter windows must be chronological, complete and consecutive", () => {
  assert.throws(
    () => summarize(syntheticRows(), [...months].reverse()),
    /consecutive/,
  );
  assert.throws(
    () =>
      summarize(
        syntheticRows(),
        months.filter((m) => m !== "2025-05"),
      ),
    /consecutive/,
  );
});
test("Impossible break-even, exact zero budget and free labor are distinct", () => {
  const impossible = economics({
    ...planningAssumptions,
    gross: 1,
    minutes: 0,
  });
  near(impossible.contribution, -4.58);
  assert.equal(impossible.breakEvenState, "unreachable");
  assert.equal(impossible.breakEvenMinutes, null);
  const zero = economics({
    gross: 5,
    taxPercent: 0,
    feePercent: 0,
    fixedFee: 0,
    reservePercent: 0,
    minutes: 0,
    hourlyCost: 45,
    otherCost: 5,
  });
  assert.equal(zero.breakEvenState, "available");
  assert.equal(zero.breakEvenMinutes, 0);
  assert.equal(
    economics({ ...planningAssumptions, hourlyCost: 0 }).breakEvenState,
    "no-hourly-cost",
  );
  assert.equal(
    economics({ ...planningAssumptions, gross: 1, hourlyCost: 0 })
      .breakEvenState,
    "unreachable",
  );
});
test("Grouping keys do not inherit object properties", () => {
  const result = summarize(
    syntheticRows().map((r) => ({
      ...r,
      track: "__proto__",
      platform: "constructor",
    })),
    months,
  );
  assert.equal(result.tracks.__proto__, 1200000);
  assert.equal(result.platforms.constructor, 1200000);
});
