import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowCounterClockwise,
  Check,
  FileText,
  Table,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import {
  cases,
  choices,
  initialCase,
  caseReducer,
  questionsFor,
  draftIsStale,
  canReviewDraft,
} from "./review.js";

const steps = ["Overview", "Review", "Follow-up"];
const sources = [
  { id: "application", label: "Application", Icon: FileText },
  { id: "royalties", label: "royalty-statements.csv", Icon: Table },
  { id: "catalog", label: "catalog-list.xlsx", Icon: Table },
];

function Modal({ title, onClose, children, focusAfterClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const previouslyFocused = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    dialog.querySelector("button")?.focus();
    return () => {
      const returnTarget = focusAfterClose?.current || previouslyFocused;
      if (focusAfterClose) focusAfterClose.current = null;
      dialog.close();
      queueMicrotask(() => {
        if (returnTarget?.isConnected) returnTarget.focus();
      });
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby="modal-title"
      onCancel={onClose}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = [
          ...ref.current.querySelectorAll(
            'button:not(:disabled), [href], select, textarea, [tabindex="0"]',
          ),
        ];
        const first = controls[0];
        const last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        if (
          e.target === e.currentTarget &&
          (e.clientX < rect.left ||
            e.clientX > rect.right ||
            e.clientY < rect.top ||
            e.clientY > rect.bottom)
        )
          onClose();
      }}
    >
      <div className="modal-header">
        <h2 id="modal-title">{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={22} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function SourceViewer({ item, source, setSource }) {
  const titles = {
    application: "Original application",
    royalties: "Royalty statement",
    catalog: "Catalog list",
  };
  return (
    <section className="source-column" aria-label="Source evidence">
      <div className="source-surface">
        <div className="source-heading">
          <h2>{titles[source]}</h2>
          <span className="tag">Read-only</span>
        </div>
        <div className="source-paper" id="source-content">
          {source === "application" ? (
            <div className="letter">
              <p>Hello SPACE,</p>
              <p>
                {item.intro}
                <mark>{item.highlight}</mark>
                {item.after}
              </p>
              <p>{item.ending}</p>
              <p className="signature">{item.name}</p>
            </div>
          ) : source === "royalties" ? (
            <div className="file-preview">
              <p className="eyebrow">FICTIONAL FILE PREVIEW</p>
              <h3>royalty-statements.csv</h3>
              <p>
                This mock file demonstrates a document that still needs
                clarification.
              </p>
              <dl className="document-facts">
                <div>
                  <dt>Reporting period</dt>
                  <dd>Not established</dd>
                </div>
                <div>
                  <dt>Currency</dt>
                  <dd>Not established</dd>
                </div>
                <div>
                  <dt>Gross or net</dt>
                  <dd>Not established</dd>
                </div>
              </dl>
              <p className="small muted">
                No financial amounts or valuation are calculated in this
                preview.
              </p>
            </div>
          ) : (
            <div className="file-preview">
              <p className="eyebrow">FICTIONAL FILE PREVIEW</p>
              <h3>catalog-list.xlsx</h3>
              <div
                className="table-scroll"
                tabIndex={0}
                role="region"
                aria-label="Fictional catalog list"
              >
                <table>
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Rights claimed</th>
                      <th>Ownership evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Example Track A</td>
                      <td>{item.rights}</td>
                      <td>Not provided</td>
                    </tr>
                    <tr>
                      <td>Example Track B</td>
                      <td>{item.rights}</td>
                      <td>Not provided</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="small muted">
                A catalog list describes an applicant's claim. It does not
                establish ownership.
              </p>
            </div>
          )}
        </div>
      </div>
      <p className="source-disclaimer">
        Applicant statements have not been independently verified.
      </p>
      <h3 className="source-label">Source files</h3>
      <div
        className="source-switcher"
        role="group"
        aria-label="Choose source file"
      >
        {sources.map(({ id, label, Icon }) => (
          <button
            key={id}
            aria-pressed={source === id}
            aria-controls="source-content"
            onClick={() => setSource(id)}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </div>
    </section>
  );
}

export function App() {
  const [caseId, setCaseId] = useState(cases[0].id);
  const [caseStates, setCaseStates] = useState(() =>
    Object.fromEntries(cases.map((c) => [c.id, initialCase(c)])),
  );
  const [screen, setScreen] = useState("Overview");
  const [source, setSource] = useState("application");
  const [modal, setModal] = useState(null);
  const [announcement, setAnnouncement] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const copyOperation = useRef(0);
  const heading = useRef(null);
  const rightsSelect = useRef(null);
  const draftInput = useRef(null);
  const dialogReturnTarget = useRef(null);
  const item = cases.find((c) => c.id === caseId);
  const state = caseStates[caseId];
  const stale = draftIsStale(state);
  const classificationLabel =
    state.reviewStatus === "pending"
      ? "Needs review"
      : state.reviewStatus === "unclear"
        ? "Clarification needed"
        : "Classification reviewed";

  function dispatch(action) {
    copyOperation.current += 1;
    setCaseStates((all) => ({
      ...all,
      [caseId]: caseReducer(all[caseId], action),
    }));
    setCopyStatus("");
  }
  function go(next) {
    copyOperation.current += 1;
    setScreen(next);
    setAnnouncement("");
    setCopyStatus("");
  }
  function openModal(kind, event) {
    event.currentTarget.focus();
    setModal(kind);
  }
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    heading.current?.focus({ preventScroll: true });
  }, [screen, caseId]);
  function confirm() {
    dispatch({ type: "confirm" });
    setAnnouncement(
      "Classification saved in this preview. Ownership is not verified.",
    );
  }
  function openSource(id) {
    setSource(id);
    go("Review");
  }
  function prepare() {
    if (state.draft) {
      go("Follow-up");
      return;
    }
    dispatch({ type: "prepare" });
    go("Follow-up");
  }
  function switchCase(id) {
    setCaseId(id);
    setSource("application");
    go("Overview");
    setModal(null);
  }
  async function copyDraft() {
    if (!canReviewDraft(state) || !state.draft?.reviewed) return;
    const operation = ++copyOperation.current;
    try {
      await navigator.clipboard.writeText(state.draft.text);
      if (operation === copyOperation.current)
        setCopyStatus("Draft copied. Nothing has been sent.");
    } catch {
      if (operation === copyOperation.current)
        setCopyStatus(
          "Clipboard is unavailable. Select and copy the draft text instead.",
        );
    }
  }

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to review
      </a>
      <div className="preview-notice">
        <strong>Interactive preview</strong>
        <span>Fictional cases only. No AI calls, uploads or emails.</span>
        <button onClick={(event) => openModal("reset", event)}>
          <ArrowCounterClockwise size={15} />
          Reset demo
        </button>
      </div>
      <header className="masthead shell">
        <button
          className="brand"
          onClick={() => go("Overview")}
          aria-label="SPACE review overview"
        >
          <img
            src="/assets/space-wordmark.svg"
            width="112"
            height="23"
            alt="SPACE"
          />
        </button>
        <span className="product-label">Catalog review</span>
        <button
          className="workspace-label"
          onClick={(event) => openModal("about", event)}
        >
          Reviewer workspace
        </button>
      </header>
      <main id="main" className="shell" tabIndex={-1}>
        <div className="context-row">
          <div className="breadcrumb">
            <button onClick={(event) => openModal("cases", event)}>
              Cases
            </button>
            <span>/</span>
            <span>{item.name}</span>
            <span className="case-id">{item.id}</span>
          </div>
          <nav className="step-nav" aria-label="Review steps">
            {steps.map((step, i) => (
              <button
                key={step}
                aria-current={screen === step ? "step" : undefined}
                onClick={() => go(step)}
              >
                <span>{String(i + 1).padStart(2, "0")}</span>
                {step}
                {step === "Review" && state.reviewStatus !== "pending" ? (
                  <Check size={16} aria-label="Classification reviewed" />
                ) : null}
              </button>
            ))}
          </nav>
        </div>
        <div className="page-heading">
          <h1 ref={heading} tabIndex={-1}>
            {screen === "Overview"
              ? item.name
              : screen === "Review"
                ? "Review the source. Then decide."
                : "Make the next step clear."}
          </h1>
          <p className="subtitle">
            {screen === "Overview"
              ? "One case. The original evidence. A clear next step."
              : screen === "Review"
                ? "Check each suggestion against the original application."
                : "A suggested follow-up, ready for your review."}
          </p>
        </div>
        {screen === "Overview" && (
          <div className="overview-grid">
            <section>
              <div className="section-heading">
                <h2>What this applicant wants</h2>
                <span
                  className={`tag ${state.reviewStatus === "confirmed" ? "reviewed" : ""}`}
                >
                  {classificationLabel}
                </span>
              </div>
              <p className="small muted">
                {state.reviewStatus === "pending"
                  ? "Illustrative AI suggestions. Not reviewed."
                  : "Your classification, not a verification of rights or income."}
              </p>
              <dl className="summary-list">
                <div>
                  <dt>Request</dt>
                  <dd>
                    {item.request}
                    <span className="small muted">Applicant intent</span>
                  </dd>
                </div>
                <div>
                  <dt>Rights offered</dt>
                  <dd>
                    {state.fields.rights}
                    <button onClick={() => openSource("application")}>
                      View source
                    </button>
                  </dd>
                </div>
                <div>
                  <dt>Sale structure</dt>
                  <dd>
                    {state.fields.structure}
                    <button onClick={() => openSource("application")}>
                      View source
                    </button>
                  </dd>
                </div>
              </dl>
              <blockquote>
                <span className="small muted">
                  Original application excerpt
                </span>
                <p>
                  {item.intro}
                  <mark>{item.highlight}</mark>
                  {item.after}
                </p>
              </blockquote>
              <div className="evidence-heading">
                <h2>Evidence received</h2>
                <span className="small muted">2 fictional files</span>
              </div>
              <div className="evidence-list">
                {sources.slice(1).map(({ id, label, Icon }) => (
                  <button key={id} onClick={() => openSource(id)}>
                    <Icon size={23} />
                    <span>
                      <strong>{label}</strong>
                      <small>
                        {id === "royalties"
                          ? "Suggested type: royalty statement"
                          : "Suggested type: catalog list"}
                      </small>
                    </span>
                    <span className="tag">Received</span>
                    <ArrowRight size={18} />
                  </button>
                ))}
              </div>
              <p className="small muted">
                Received does not mean verified. Original documents remain
                unchanged.
              </p>
            </section>
            <aside className="next-panel">
              <p className="eyebrow">BEFORE A COMMERCIAL REVIEW</p>
              <h2>Still to establish</h2>
              <ol className="question-list">
                {questionsFor(state.fields).map((q) => (
                  <li key={q.title}>
                    <h3>{q.title}</h3>
                    <p>{q.detail}</p>
                  </li>
                ))}
              </ol>
              <div className="quiet-note">
                <h3>Your decision stays yours.</h3>
                <p>
                  Check the source, correct suggestions and leave uncertain
                  details open.
                </p>
              </div>
              <button className="primary" onClick={() => go("Review")}>
                {state.reviewStatus === "pending"
                  ? "Review suggestions"
                  : "Continue review"}
                <ArrowRight size={18} />
              </button>
              <p className="small muted">
                No automatic valuation or outbound messages.
              </p>
            </aside>
          </div>
        )}
        {screen === "Review" && (
          <div className="review-grid">
            <SourceViewer item={item} source={source} setSource={setSource} />
            <section
              className="review-panel"
              aria-label="Classification review"
            >
              <p
                className={`eyebrow status-label ${state.reviewStatus === "confirmed" ? "approved-label" : ""}`}
              >
                {state.reviewStatus === "pending"
                  ? state.revision > 0
                    ? "YOUR CHANGES · NOT REVIEWED"
                    : "AI SUGGESTIONS · NOT REVIEWED"
                  : state.reviewStatus === "unclear"
                    ? "REVIEWED · CLARIFICATION NEEDED"
                    : "CLASSIFICATION · REVIEWED BY YOU"}
              </p>
              <label htmlFor="rights">Rights offered</label>
              <select
                id="rights"
                ref={rightsSelect}
                value={state.fields.rights}
                onChange={(e) =>
                  dispatch({
                    type: "field",
                    field: "rights",
                    value: e.target.value,
                  })
                }
              >
                {choices.rights.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
              <p className="field-help">
                Compare with the{" "}
                <button onClick={() => setSource("application")}>
                  original application
                </button>
                .
              </p>
              <label htmlFor="structure">Sale structure</label>
              <select
                id="structure"
                value={state.fields.structure}
                onChange={(e) =>
                  dispatch({
                    type: "field",
                    field: "structure",
                    value: e.target.value,
                  })
                }
              >
                {choices.structure.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
              <div className="caution">
                <WarningCircle size={22} />
                <div>
                  <h3>{item.noteTitle}</h3>
                  <p>{item.note}</p>
                </div>
              </div>
              <button
                className="text-link unclear-action"
                onClick={() => {
                  dispatch({ type: "unclear" });
                  setAnnouncement(
                    "Both fields marked unclear. Clarification is required.",
                  );
                }}
              >
                Mark both fields unclear
              </button>
              {state.reviewStatus === "pending" ? (
                <>
                  <button className="primary" onClick={confirm}>
                    Confirm these two fields
                  </button>
                  <p className="button-help">
                    Confirms your classification only, not legal ownership.
                  </p>
                  <button
                    className="text-link edit-action"
                    onClick={() => rightsSelect.current?.focus()}
                  >
                    Edit suggestions
                  </button>
                </>
              ) : (
                <>
                  <div className="confirmation">
                    <Check size={19} />
                    <span>
                      {state.reviewStatus === "unclear"
                        ? "Uncertainty recorded. Ask for clarification."
                        : "Classification reviewed. Ownership is not verified."}
                    </span>
                  </div>
                  <button
                    className="text-link edit-action"
                    onClick={() => {
                      dispatch({ type: "reopen" });
                      rightsSelect.current?.focus();
                    }}
                  >
                    Reopen classification
                  </button>
                </>
              )}
              <div className="next-step">
                <p>Next: ask for the missing information</p>
                <button
                  className={
                    state.reviewStatus === "pending" ? "secondary" : "primary"
                  }
                  disabled={state.reviewStatus === "pending"}
                  onClick={prepare}
                >
                  {state.draft ? "Open follow-up draft" : "Prepare follow-up"}
                  <ArrowRight size={18} />
                </button>
                {state.reviewStatus === "pending" && (
                  <p className="small muted">
                    Confirm the fields or mark them unclear first.
                  </p>
                )}
              </div>
            </section>
          </div>
        )}
        {screen === "Follow-up" && (
          <>
            <div className="classification-strip">
              <div>
                <span>Request</span>
                <strong>{item.request}</strong>
              </div>
              <div>
                <span>Reviewed rights</span>
                <strong>
                  {state.reviewStatus === "pending"
                    ? "Not confirmed"
                    : state.fields.rights}
                </strong>
              </div>
              <div>
                <span>Reviewed structure</span>
                <strong>
                  {state.reviewStatus === "pending"
                    ? "Not confirmed"
                    : state.fields.structure}
                </strong>
              </div>
            </div>
            {!state.draft ? (
              <section className="empty-state">
                <FileText size={32} />
                <h2>
                  {state.reviewStatus === "pending"
                    ? "Review the classification first."
                    : "Ready to prepare your questions."}
                </h2>
                <p>
                  {state.reviewStatus === "pending"
                    ? "Confirm the suggested fields or mark them unclear. Uncertainty is a valid review outcome."
                    : "Create a template-based draft for the missing information. You stay in control of every word."}
                </p>
                <button
                  className="primary"
                  onClick={
                    state.reviewStatus === "pending"
                      ? () => go("Review")
                      : prepare
                  }
                >
                  {state.reviewStatus === "pending"
                    ? "Go to review"
                    : "Prepare follow-up"}
                  <ArrowRight size={18} />
                </button>
              </section>
            ) : (
              <div className="follow-grid">
                <section>
                  <div className="section-heading">
                    <h2>Suggested reply</h2>
                    <span className="tag">
                      {state.draft.reviewed &&
                      !stale &&
                      state.reviewStatus !== "pending"
                        ? "Reviewed draft"
                        : "Draft"}{" "}
                      · Nothing sent
                    </span>
                  </div>
                  {(stale || state.reviewStatus === "pending") && (
                    <div className="stale-note" role="alert">
                      <WarningCircle size={21} />
                      <div>
                        <h3>
                          {stale
                            ? "The classification has changed."
                            : "Classification review is open."}
                        </h3>
                        <p>
                          Your edited draft is preserved. Review the
                          classification before continuing.
                        </p>
                        <button
                          className="text-link"
                          onClick={() => go("Review")}
                        >
                          Return to review
                        </button>
                        {stale && state.reviewStatus !== "pending" && (
                          <button
                            className="text-link"
                            onClick={(event) => openModal("regenerate", event)}
                          >
                            Replace with updated draft
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                  <label className="sr-only" htmlFor="reply">
                    Follow-up draft
                  </label>
                  <textarea
                    id="reply"
                    ref={draftInput}
                    maxLength={6000}
                    value={state.draft.text}
                    onChange={(e) =>
                      dispatch({ type: "edit", text: e.target.value })
                    }
                    spellCheck="false"
                  />
                  <div className="draft-help">
                    <span>Template-based suggestion. Review before use.</span>
                    <span>
                      {state.draft.text.length.toLocaleString("en-US")} / 6,000
                    </span>
                  </div>
                  {!state.draft.text.trim() && (
                    <p className="form-error" role="alert">
                      Add a message before reviewing the draft.
                    </p>
                  )}
                  <div className="draft-actions">
                    <button
                      className="primary"
                      disabled={!canReviewDraft(state)}
                      onClick={(event) => openModal("review-message", event)}
                    >
                      Review message
                      <ArrowRight size={18} />
                    </button>
                    <button
                      className="text-link"
                      onClick={() => draftInput.current?.focus()}
                    >
                      Edit draft
                    </button>
                  </div>
                  {state.draft.reviewed && canReviewDraft(state) && (
                    <div className="copy-area">
                      <p>
                        <Check size={18} />
                        Draft reviewed in this preview. Nothing has been sent.
                      </p>
                      <button className="secondary" onClick={copyDraft}>
                        Copy reviewed draft
                      </button>
                    </div>
                  )}
                  {copyStatus && (
                    <p className="small" role="status">
                      {copyStatus}
                    </p>
                  )}
                </section>
                <aside className="follow-context">
                  <h2>Why these questions?</h2>
                  <ol className="question-list">
                    {questionsFor(state.fields).map((q) => (
                      <li key={q.title}>
                        <h3>{q.title}</h3>
                        <p>{q.detail}</p>
                      </li>
                    ))}
                  </ol>
                  <h3 className="source-label">Received</h3>
                  <div className="context-files">
                    {sources.slice(1).map(({ id, label, Icon }) => (
                      <button key={id} onClick={() => openSource(id)}>
                        <Icon size={20} />
                        {label}
                      </button>
                    ))}
                  </div>
                  <button
                    className="text-link"
                    onClick={() => openSource("application")}
                  >
                    View original application
                    <ArrowRight size={18} />
                  </button>
                </aside>
              </div>
            )}
          </>
        )}
        <p
          className="sr-only"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {announcement}
        </p>
      </main>
      <footer className="shell">
        <span>SPACE Catalog Review</span>
        <span className="footer-note">
          Preview changes disappear on refresh.
        </span>
        <button onClick={(event) => openModal("about", event)}>
          About this preview
        </button>
      </footer>
      {modal === "cases" && (
        <Modal title="Fictional review cases" onClose={() => setModal(null)}>
          <p className="muted">
            Try a clear application or one with an undecided sale structure.
            Each keeps its own review while this page stays open.
          </p>
          <div className="case-list">
            {cases.map((c) => (
              <button key={c.id} onClick={() => switchCase(c.id)}>
                <span className="small muted">{c.id}</span>
                <strong>{c.name}</strong>
                <span>
                  {c.id === "CR-024"
                    ? "Partial master sale"
                    : "Publishing sale · Scope unclear"}
                </span>
                <ArrowRight size={20} />
              </button>
            ))}
          </div>
        </Modal>
      )}
      {modal === "about" && (
        <Modal
          title="A preview, not a customer portal"
          onClose={() => setModal(null)}
        >
          <p>
            This demonstrates a source-led review with fictional cases and
            prewritten suggestions. It does not call Jev or any other AI
            service.
          </p>
          <ul>
            <li>No customer information, uploads or API connections.</li>
            <li>
              No valuation, verification of ownership or automatic messages.
            </li>
            <li>Your changes stay in page memory and disappear on refresh.</li>
            <li>Copying a reviewed draft only places it on your clipboard.</li>
          </ul>
          <button className="primary" onClick={() => setModal(null)}>
            Back to the preview
          </button>
        </Modal>
      )}
      {modal === "reset" && (
        <Modal
          title="Reset the fictional cases?"
          onClose={() => setModal(null)}
        >
          <p>
            This clears classifications and edited drafts for both demo cases.
            Nothing has been saved outside this page.
          </p>
          <div className="modal-actions">
            <button className="secondary" onClick={() => setModal(null)}>
              Keep working
            </button>
            <button
              className="primary"
              onClick={() => {
                setCaseStates(
                  Object.fromEntries(cases.map((c) => [c.id, initialCase(c)])),
                );
                switchCase(cases[0].id);
                setAnnouncement("Demo reset.");
              }}
            >
              Reset demo
            </button>
          </div>
        </Modal>
      )}
      {modal === "regenerate" && (
        <Modal
          title="Replace your current draft?"
          focusAfterClose={dialogReturnTarget}
          onClose={() => setModal(null)}
        >
          <p>
            Your edits will be replaced by a fresh template using the current
            classification. No message will be sent.
          </p>
          <div className="modal-actions">
            <button className="secondary" onClick={() => setModal(null)}>
              Keep my draft
            </button>
            <button
              className="primary"
              onClick={() => {
                dialogReturnTarget.current = draftInput.current;
                dispatch({ type: "prepare" });
                setModal(null);
                setAnnouncement("Draft updated. Review it before use.");
              }}
            >
              Replace draft
            </button>
          </div>
        </Modal>
      )}
      {modal === "review-message" && (
        <Modal
          title="Check the message before use"
          focusAfterClose={dialogReturnTarget}
          onClose={() => setModal(null)}
        >
          <p className="muted">
            For {item.name}. This is a fictional draft and cannot be sent from
            this preview.
          </p>
          <div className="message-preview">{state.draft.text}</div>
          <p className="small muted">
            Confirm the wording, requested documents and excluded rights. This
            does not approve a transaction.
          </p>
          <div className="modal-actions">
            <button
              className="secondary"
              onClick={() => {
                dialogReturnTarget.current = draftInput.current;
                setModal(null);
              }}
            >
              Back to editing
            </button>
            <button
              className="primary"
              onClick={() => {
                dispatch({ type: "reviewed" });
                setModal(null);
                setAnnouncement(
                  "Draft marked reviewed. Nothing has been sent.",
                );
              }}
            >
              Mark draft reviewed
              <Check size={18} />
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
