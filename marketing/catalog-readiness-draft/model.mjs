// Pure illustrative arithmetic. This does not read customer files or appraise rights.
const number = (value, label, min, max = Number.MAX_SAFE_INTEGER) => {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < min ||
    value > max
  ) {
    throw new RangeError(
      `${label} must be a finite number between ${min} and ${max}`,
    );
  }
  return value;
};

export function economics({
  gross,
  taxPercent,
  feePercent,
  fixedFee,
  reservePercent,
  minutes,
  hourlyCost,
  otherCost,
}) {
  number(gross, "Price", 0, 1000000);
  number(taxPercent, "Illustrative tax", 0, 100);
  number(feePercent, "Fee buffer", 0, 100);
  number(fixedFee, "Fixed fee", 0, 1000000);
  number(reservePercent, "Refund reserve", 0, 100);
  number(minutes, "Minutes", 0, 100000);
  number(hourlyCost, "Hourly cost", 0, 100000);
  number(otherCost, "Other cost", 0, 1000000);
  // Round each modeled money line to cents so the visible components reconcile.
  const cents = (amount) => {
    const scaled = amount * 100;
    return Math.round(
      scaled + Number.EPSILON * Math.max(1, Math.abs(scaled)) * 4,
    );
  };
  const revenueCents = cents(gross / (1 + taxPercent / 100));
  const feeCents = cents((gross * feePercent) / 100 + fixedFee);
  const reserveCents = Math.round((revenueCents * reservePercent) / 100);
  const laborCents = cents((minutes / 60) * hourlyCost);
  const otherCents = cents(otherCost);
  const availableCents = revenueCents - feeCents - reserveCents - otherCents;
  const breakEvenState =
    availableCents < 0
      ? "unreachable"
      : hourlyCost === 0
        ? "no-hourly-cost"
        : "available";
  const breakEvenMinutes =
    breakEvenState === "available"
      ? (availableCents / 100 / hourlyCost) * 60
      : null;
  return {
    revenue: revenueCents / 100,
    fees: feeCents / 100,
    reserve: reserveCents / 100,
    labor: laborCents / 100,
    otherCost: otherCents / 100,
    contribution: (availableCents - laborCents) / 100,
    breakEvenState,
    breakEvenMinutes,
  };
}

export const planningAssumptions = Object.freeze({
  gross: 99,
  taxPercent: 25,
  feePercent: 3.5,
  fixedFee: 0.3,
  reservePercent: 5,
  minutes: 75,
  hourlyCost: 45,
  otherCost: 5,
});

export function scenario(annualCents, multiple, sharePercent) {
  number(annualCents, "Annual income", 0);
  if (!Number.isSafeInteger(annualCents))
    throw new RangeError("Use integer cents");
  number(multiple, "Assumed multiple", Number.MIN_VALUE, 100);
  number(sharePercent, "Share", 0, 100);
  const amount = Math.round((annualCents * multiple * sharePercent) / 100);
  if (!Number.isSafeInteger(amount))
    throw new RangeError("Scenario exceeds safe precision");
  return amount;
}

export const sampleDefinition = Object.freeze({
  id: "SYNTHETIC-001",
  currency: "EUR",
  year: 2025,
  monthlyEuros: [
    1200, 1100, 1000, 1050, 950, 1000, 1000, 1000, 1000, 950, 900, 850,
  ],
  tracks: [
    { id: "DEMO-A", name: "Recording A", percent: 40, identifierPresent: true },
    { id: "DEMO-B", name: "Recording B", percent: 22, identifierPresent: true },
    { id: "DEMO-C", name: "Recording C", percent: 14, identifierPresent: true },
    { id: "DEMO-D", name: "Recording D", percent: 10, identifierPresent: true },
    { id: "DEMO-E", name: "Recording E", percent: 8, identifierPresent: true },
    { id: "DEMO-F", name: "Recording F", percent: 6, identifierPresent: false },
  ],
  platforms: [
    { id: "Platform A", percent: 60 },
    { id: "Platform B", percent: 25 },
    { id: "Other platforms", percent: 15 },
  ],
});

export function syntheticRows() {
  const rows = [];
  for (const [index, euros] of sampleDefinition.monthlyEuros.entries()) {
    for (const track of sampleDefinition.tracks) {
      for (const platform of sampleDefinition.platforms) {
        const cents = (euros * track.percent * platform.percent) / 100;
        if (!Number.isSafeInteger(cents))
          throw new Error("Synthetic allocation must reconcile exactly");
        rows.push({
          id: `DEMO-${String(rows.length + 1).padStart(3, "0")}`,
          month: `2025-${String(index + 1).padStart(2, "0")}`,
          track: track.id,
          platform: platform.id,
          currency: "EUR",
          netCents: cents,
        });
      }
    }
  }
  return rows;
}

export function summarize(rows, expectedMonths) {
  if (
    !Array.isArray(rows) ||
    !rows.length ||
    !Array.isArray(expectedMonths) ||
    !expectedMonths.length
  )
    throw new Error("Rows and expected periods are required");
  if (
    new Set(expectedMonths).size !== expectedMonths.length ||
    expectedMonths.some((m) => !/^\d{4}-(0[1-9]|1[0-2])$/.test(m))
  )
    throw new Error("Invalid expected periods");
  const indexes = expectedMonths.map(
    (m) => Number(m.slice(0, 4)) * 12 + Number(m.slice(5)),
  );
  if (indexes.some((value, i) => i > 0 && value !== indexes[i - 1] + 1))
    throw new Error("Expected periods must be consecutive and ordered");
  const ids = new Set();
  const currency = rows[0].currency;
  const monthly = Object.fromEntries(expectedMonths.map((m) => [m, null]));
  const tracks = Object.create(null),
    platforms = Object.create(null);
  let totalCents = 0,
    negativeRows = 0;
  for (const row of rows) {
    if (!row.id || ids.has(row.id))
      throw new Error("Missing or duplicate source line ID");
    ids.add(row.id);
    if (!/^[A-Z]{3}$/.test(row.currency) || row.currency !== currency)
      throw new Error("Single explicit currency required");
    if (!Object.hasOwn(monthly, row.month))
      throw new Error("Source period is outside scope");
    if (!row.track || !row.platform || !Number.isSafeInteger(row.netCents))
      throw new Error("Invalid source row");
    if (row.netCents < 0) negativeRows++;
    totalCents += row.netCents;
    if (!Number.isSafeInteger(totalCents))
      throw new Error("Total exceeds safe precision");
    monthly[row.month] = (monthly[row.month] ?? 0) + row.netCents;
    tracks[row.track] = (tracks[row.track] ?? 0) + row.netCents;
    platforms[row.platform] = (platforms[row.platform] ?? 0) + row.netCents;
  }
  for (const values of [monthly, tracks, platforms]) {
    if (
      Object.values(values).some((v) => v !== null && !Number.isSafeInteger(v))
    )
      throw new Error("Breakdown exceeds safe precision");
  }
  const missingMonths = expectedMonths.filter((m) => monthly[m] === null);
  const first = expectedMonths.slice(0, 3).map((m) => monthly[m]);
  const last = expectedMonths.slice(-3).map((m) => monthly[m]);
  const trendAvailable =
    expectedMonths.length >= 6 &&
    !missingMonths.length &&
    first.every((v) => v !== null) &&
    last.every((v) => v !== null);
  const firstQuarter = trendAvailable ? first.reduce((a, b) => a + b, 0) : null;
  const lastQuarter = trendAvailable ? last.reduce((a, b) => a + b, 0) : null;
  return {
    currency,
    totalCents,
    monthly,
    tracks,
    platforms,
    missingMonths,
    negativeRows,
    concentrationAvailable:
      totalCents > 0 && negativeRows === 0 && !missingMonths.length,
    quarterChange: firstQuarter > 0 ? lastQuarter / firstQuarter - 1 : null,
    firstQuarter,
    lastQuarter,
  };
}
