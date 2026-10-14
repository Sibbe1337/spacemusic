// Deliberately fictional fixtures. This preview never calls a model or customer API.
export const cases = Object.freeze([
  Object.freeze({
    id: "CR-024",
    name: "Example Recordings",
    received: "24 Sep 2026",
    request: "Catalog sale",
    rights: "Masters",
    structure: "Partial sale",
    intro: "We would like to explore selling ",
    highlight: "50% of our master rights",
    after:
      " for the recordings in the attached catalog. Publishing is not included.",
    ending:
      "We have attached royalty statements and a track list. Please let us know what else you need for an initial review.",
    noteTitle: "Publishing excluded",
    note: "The applicant explicitly excludes publishing. Confirm this when reviewing agreements.",
  }),
  Object.freeze({
    id: "CR-025",
    name: "Example Songworks",
    received: "24 Sep 2026",
    request: "Catalog sale",
    rights: "Publishing",
    structure: "Unclear",
    intro: "We are interested in ",
    highlight: "selling our publishing interests, but keeping the masters",
    after:
      ". We may offer all of our publishing share or only part of it. We have not decided yet.",
    ending:
      "We have attached royalty statements and a track list. Can you explain what information you need?",
    noteTitle: "Scope needs clarification",
    note: "The applicant has not decided between a full or partial sale. Do not infer the share being offered.",
  }),
]);
export const choices = Object.freeze({
  rights: Object.freeze([
    "Masters",
    "Publishing",
    "Masters and publishing",
    "Unclear",
  ]),
  structure: Object.freeze([
    "Full sale",
    "Partial sale",
    "Fixed term",
    "Unclear",
  ]),
});
export function initialCase(item) {
  return {
    fields: { rights: item.rights, structure: item.structure },
    reviewStatus: "pending",
    revision: 0,
    draft: null,
  };
}
export function draftIsStale(state) {
  return Boolean(state.draft && state.draft.revision !== state.revision);
}
export function questionsFor(fields) {
  const rightsDescription = {
    Masters: "master rights",
    Publishing: "publishing interests",
    "Masters and publishing": "master rights and publishing interests",
  }[fields.rights];
  return [
    {
      title: "Catalog scope",
      detail: "Confirm the exact assets, share and term.",
      text:
        fields.structure === "Unclear"
          ? "Which recordings or works, what share, and what term would you like us to consider?"
          : "Which recordings or works are included, and what exact share and term would you like us to consider?",
    },
    {
      title: "Rights",
      detail: "Ownership has not been established.",
      text:
        fields.rights === "Unclear"
          ? "Are you offering master rights, publishing interests, or both? What documents show the rights you control and any restrictions?"
          : `What documents show the ${rightsDescription} you control, and are there any existing agreements or restrictions?`,
    },
    {
      title: "Revenue context",
      detail: "Currency and gross/net basis are not established.",
      text: "What currency and reporting period do the statements cover, and are the amounts gross or net?",
    },
  ];
}
export function makeDraft(fields) {
  return `Hello,\n\nThank you for sharing your catalog and the supporting files.\n\nTo continue the initial review, could you clarify:\n\n${questionsFor(
    fields,
  )
    .map((q, i) => `${i + 1}. ${q.text}`)
    .join(
      "\n\n",
    )}\n\nPlease also confirm which rights and future releases should be excluded from any discussion.\n\nBest,\nSPACE`;
}
export function canReviewDraft(state) {
  return (
    state.reviewStatus !== "pending" &&
    Boolean(state.draft?.text.trim()) &&
    !draftIsStale(state)
  );
}
export function caseReducer(state, action) {
  switch (action.type) {
    case "field":
      if (
        !Object.hasOwn(choices, action.field) ||
        !choices[action.field].includes(action.value) ||
        state.fields[action.field] === action.value
      )
        return state;
      return {
        ...state,
        fields: { ...state.fields, [action.field]: action.value },
        reviewStatus: "pending",
        revision: state.revision + 1,
      };
    case "unclear":
      return {
        ...state,
        fields: { rights: "Unclear", structure: "Unclear" },
        reviewStatus: "unclear",
        revision: state.revision + 1,
      };
    case "confirm":
      return {
        ...state,
        reviewStatus: Object.values(state.fields).includes("Unclear")
          ? "unclear"
          : "confirmed",
      };
    case "reopen":
      return { ...state, reviewStatus: "pending" };
    case "prepare":
      if (state.reviewStatus === "pending") return state;
      return {
        ...state,
        draft: {
          text: makeDraft(state.fields),
          revision: state.revision,
          reviewed: false,
          edited: false,
        },
      };
    case "edit":
      if (
        !state.draft ||
        typeof action.text !== "string" ||
        action.text.length > 6000
      )
        return state;
      return {
        ...state,
        draft: {
          ...state.draft,
          text: action.text,
          edited: true,
          reviewed: false,
        },
      };
    case "reviewed":
      if (!canReviewDraft(state)) return state;
      return { ...state, draft: { ...state.draft, reviewed: true } };
    default:
      return state;
  }
}
