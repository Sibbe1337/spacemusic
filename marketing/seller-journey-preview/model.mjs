export const STORAGE_KEY = "space.seller-journey.preview.v1";
export const SCREENS = [
  "apply",
  "received",
  "catalog",
  "documents",
  "review",
  "status",
  "paused",
];
export const DISTRIBUTORS = ["DistroKid", "TuneCore", "Other", "Not sure"];
export const CURRENCIES = ["USD", "EUR", "GBP", "SEK", "Other"];
export const DOCUMENTS = Object.freeze({
  royalties: {
    id: "royalties",
    name: "DEMO-royalty-statement.csv",
    size: 64000,
    label: "Royalty statements",
  },
  tracks: {
    id: "tracks",
    name: "DEMO-track-list.csv",
    size: 4200,
    label: "Track and rights list",
  },
});
export const DEMO = Object.freeze({
  contact: {
    name: "Alex Example",
    email: "alex@example.com",
    artist: "Night Window",
  },
  details: {
    artistLink: "https://example.com/night-window",
    distributor: "DistroKid",
    tracks: "12",
    rights: "masters",
    owned: "100",
    offered: "100",
    cutoff: "2026-08-31",
    revenue: "4800",
    currency: "USD",
    periodStart: "2025-09",
    periodEnd: "2026-08",
    basis: "own-share",
    agreements: "unknown",
    exclusions: "Future recordings and compositions are excluded.",
  },
});
export function fresh() {
  return {
    version: 1,
    screen: "apply",
    returnScreen: "apply",
    progress: 0,
    status: "DRAFT",
    contact: { name: "", email: "", artist: "" },
    details: Object.fromEntries(
      Object.keys(DEMO.details).map((key) => [key, ""]),
    ),
    docs: [],
    reply: "",
    replied: false,
  };
}
export function validateContact(contact) {
  const errors = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email.trim()))
    errors.email = "Enter a complete email address, such as alex@example.com.";
  if (!contact.artist.trim())
    errors.artist = "Enter the artist or label name, not the distributor.";
  return errors;
}
const numeric = (value) =>
  value.trim() !== "" &&
  /^\d+(\.\d{1,2})?$/.test(value) &&
  Number.isFinite(Number(value));
const month = (value) => /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
export function validateCatalog(d) {
  const errors = {};
  if (d.artistLink) {
    try {
      if (!["https:", "http:"].includes(new URL(d.artistLink).protocol))
        throw new Error();
    } catch {
      errors.artistLink =
        "Use a complete http or https music link, or leave this optional field empty.";
    }
  }
  if (!DISTRIBUTORS.includes(d.distributor))
    errors.distributor = "Choose your distributor, Other, or Not sure.";
  if (
    !/^\d+$/.test(d.tracks) ||
    Number(d.tracks) < 1 ||
    Number(d.tracks) > 1000000
  )
    errors.tracks =
      "Enter the number of recordings you want reviewed (at least 1).";
  if (!["masters", "unsure"].includes(d.rights))
    errors.rights = "Choose recording rights, or Not sure yet.";
  for (const key of ["owned", "offered"]) {
    if (!numeric(d[key]) || Number(d[key]) <= 0 || Number(d[key]) > 100)
      errors[key] = "Enter a percentage greater than 0 and no more than 100.";
  }
  if (
    d.cutoff &&
    (!/^\d{4}-\d{2}-\d{2}$/.test(d.cutoff) ||
      Number.isNaN(Date.parse(d.cutoff)) ||
      new Date(d.cutoff).toISOString().slice(0, 10) !== d.cutoff)
  )
    errors.cutoff =
      "Choose a valid date, or leave it for the reviewer to confirm.";
  if (!numeric(d.revenue) || Number(d.revenue) > 1000000000)
    errors.revenue =
      "Enter the reported royalties for the period. Zero is allowed; do not annualize a partial period.";
  if (!CURRENCIES.includes(d.currency))
    errors.currency = "Select the currency shown on your statement.";
  if (!month(d.periodStart))
    errors.periodStart = "Select the first statement month.";
  if (!month(d.periodEnd))
    errors.periodEnd = "Select the last statement month.";
  if (month(d.periodStart) && month(d.periodEnd) && d.periodStart > d.periodEnd)
    errors.periodEnd =
      "The last month must be the same as or later than the first month.";
  if (!["own-share", "catalog-total", "unsure"].includes(d.basis))
    errors.basis = "Tell us whose income this is, or choose Not sure.";
  if (!["none-known", "shared", "unknown"].includes(d.agreements))
    errors.agreements =
      "Choose an answer. Not sure is fine; it stays an open review question.";
  return errors;
}
export function validateDemoFile(file) {
  if (!file || !/\.(csv|tsv|pdf|xlsx)$/i.test(file.name || ""))
    return "Use a CSV, TSV, PDF or XLSX file.";
  if (
    !Number.isFinite(file.size) ||
    file.size <= 0 ||
    file.size > 25 * 1024 * 1024
  )
    return "Each file must be non-empty and no larger than 25 MB.";
  return "";
}
export function addDemoDocument(state, kind) {
  if (
    !Object.hasOwn(DOCUMENTS, kind) ||
    state.status !== "SUBMITTED" ||
    state.progress < 2
  )
    throw new Error("Document cannot be added in this state.");
  const error = validateDemoFile(DOCUMENTS[kind]);
  if (error) throw new Error(error);
  if (!state.docs.includes(kind)) state.docs.push(kind);
}
export function missingDocuments(state) {
  return Object.keys(DOCUMENTS).filter((key) => !state.docs.includes(key));
}
export function submitPackage(state) {
  if (
    state.status !== "SUBMITTED" ||
    state.progress < 2 ||
    Object.keys(validateCatalog(state.details)).length ||
    missingDocuments(state).length
  )
    throw new Error("Complete the catalog and both evidence items first.");
  state.status = "UNDER_REVIEW";
  state.screen = "status";
  state.progress = 4;
}
export function requestClarification(state) {
  if (state.status !== "UNDER_REVIEW" || state.replied)
    throw new Error("Follow-up is not available.");
  state.status = "DATA_REQUIRED";
}
export function sendReply(state, reply) {
  if (state.status !== "DATA_REQUIRED" || !reply.trim() || reply.length > 1500)
    throw new Error("Write a short clarification before sending.");
  state.reply = reply.trim();
  state.replied = true;
  state.status = "UNDER_REVIEW";
}
// Storage is a local prototype convenience, never an authentication or review authority.
export function restore(raw) {
  try {
    if (!raw || raw.length > 20000) return null;
    const saved = JSON.parse(raw),
      state = fresh();
    if (
      saved.version !== 1 ||
      !SCREENS.includes(saved.screen) ||
      !SCREENS.includes(saved.returnScreen)
    )
      return null;
    if (
      !["DRAFT", "SUBMITTED", "UNDER_REVIEW", "DATA_REQUIRED"].includes(
        saved.status,
      )
    )
      return null;
    if (
      !Number.isInteger(saved.progress) ||
      saved.progress < 0 ||
      saved.progress > 4
    )
      return null;
    for (const group of ["contact", "details"]) {
      for (const key of Object.keys(state[group])) {
        const value = saved[group]?.[key];
        if (typeof value !== "string" || value.length > 1500) return null;
        state[group][key] = value;
      }
    }
    if (
      !Array.isArray(saved.docs) ||
      saved.docs.some((key) => !Object.hasOwn(DOCUMENTS, key)) ||
      new Set(saved.docs).size !== saved.docs.length
    )
      return null;
    if (
      typeof saved.reply !== "string" ||
      saved.reply.length > 1500 ||
      typeof saved.replied !== "boolean"
    )
      return null;
    Object.assign(state, {
      screen: saved.screen,
      returnScreen: saved.returnScreen,
      status: saved.status,
      progress: saved.progress,
      docs: saved.docs,
      reply: saved.reply,
      replied: saved.replied,
    });
    if (
      state.progress > 0 &&
      Object.keys(validateContact(state.contact)).length
    )
      return null;
    if (
      state.progress >= 2 &&
      Object.keys(validateCatalog(state.details)).length
    )
      return null;
    if (
      ["UNDER_REVIEW", "DATA_REQUIRED"].includes(state.status) &&
      (state.progress !== 4 || missingDocuments(state).length)
    )
      return null;
    if (state.status === "DRAFT" && state.progress !== 0) return null;
    if (
      state.status === "SUBMITTED" &&
      (state.progress < 1 || state.progress > 3)
    )
      return null;
    if (state.progress === 3 && missingDocuments(state).length) return null;
    if (
      state.replied &&
      (state.status !== "UNDER_REVIEW" || !state.reply.trim())
    )
      return null;
    const activeScreen =
      state.screen === "paused" ? state.returnScreen : state.screen;
    const allowed =
      state.status === "DRAFT"
        ? ["apply"]
        : state.status === "SUBMITTED"
          ? [
              "received",
              "catalog",
              ...(state.progress >= 2 ? ["documents"] : []),
              ...(state.progress >= 3 ? ["review"] : []),
            ]
          : ["status"];
    if (!allowed.includes(activeScreen)) return null;
    return state;
  } catch {
    return null;
  }
}
