import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { sourceMetadata, trackApplication } from "./funnel";

const API_BASE = (import.meta.env.VITE_SPACEMUSIC_API_URL || "").replace(/\/$/, "");
const FORM_ENDPOINT = (import.meta.env.VITE_FORM_ENDPOINT || "").trim();
const SUBMISSIONS_ENABLED = Boolean(API_BASE || FORM_ENDPOINT);
const BENCHMARK_VERSION = import.meta.env.VITE_BENCHMARK_VERSION || "";
const BENCHMARK_LOW = Number(import.meta.env.VITE_BENCHMARK_LOW || 0);
const BENCHMARK_MEDIAN = Number(import.meta.env.VITE_BENCHMARK_MEDIAN || 0);
const BENCHMARK_HIGH = Number(import.meta.env.VITE_BENCHMARK_HIGH || 0);

function savedSession(key: string) {
  try { return sessionStorage.getItem(key) || ""; }
  catch { return ""; }
}

type Status = "SUBMITTED" | "DATA_REQUIRED" | "UNDER_REVIEW" | "OFFER_READY" | "ACCEPTED" | "PAID" | "REJECTED";
type DocumentStatus = "PENDING_UPLOAD" | "UPLOADED" | "VERIFIED" | "REJECTED";

type Offer = {
  id: string;
  sale_percentage: 50 | 75 | 100;
  cash_low_cents: number;
  cash_median_cents: number;
  cash_high_cents: number;
  currency_code: string;
  rights_transferred: Record<string, number>;
  rights_retained: Record<string, number>;
  payment_date: string;
  valuation_range: Record<string, number>;
  risk_adjustments: string[];
  exceptions: string[];
  valid_until: string;
};

type Application = {
  id: string;
  contact_email: string;
  seller_name?: string;
  status: Status;
  catalog_passport: {
    artist_label: string;
    territories: string[];
    tracks: { title: string; isrc?: string; iswc?: string }[];
    revenue_history: { gross_cents: number; currency_code: string; verified: boolean }[];
    metadata_completeness: number;
    rights_ownership_share: number;
  };
  offers: Offer[];
  accepted_offer_id?: string;
};

type Document = {
  id: string;
  document_type: string;
  original_filename: string;
  status: DocumentStatus;
  version: number;
};

type Payout = {
  id: string;
  status: string;
  amount_cents: number;
  currency_code: string;
  receipt_url?: string;
};

type Report = { id: string; period_start: string; period_end: string; amount_cents: number; status: string };
type Termsheet = { version: string; offer: Offer; requires_legal_review: boolean };

async function request<T>(path: string, options: RequestInit = {}, sellerToken = ""): Promise<T> {
  if (!API_BASE) {
    throw new Error("Seller API is not configured for this environment.");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(sellerToken ? { "X-Seller-Token": sellerToken } : {}),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : "Request failed");
  }
  return payload as T;
}

function formatMoney(cents: number, currency = "EUR") {
  return new Intl.NumberFormat("en", { style: "currency", currency, maximumFractionDigits: 0 }).format(cents / 100);
}

function statusLabel(status: Status) {
  return {
    SUBMITTED: "Application received",
    DATA_REQUIRED: "More information needed",
    UNDER_REVIEW: "Under review",
    OFFER_READY: "Offer ready",
    ACCEPTED: "Offer accepted",
    PAID: "Paid",
    REJECTED: "Closed",
  }[status];
}

function monthRange(months: number, monthlyCents: number) {
  const now = new Date();
  return Array.from({ length: months }, (_, index) => {
    const month = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - months + index + 1, 1));
    const next = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth() + 1, 0));
    return {
      period_start: month.toISOString().slice(0, 10),
      period_end: next.toISOString().slice(0, 10),
      gross_cents: monthlyCents,
      adjustments_cents: 0,
      currency_code: "EUR",
      source: "DISTRIBUTOR",
      verified: false,
    };
  });
}

async function digest(file: File) {
  const buffer = await file.arrayBuffer();
  const hash = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export default function App() {
  const [applicationId, setApplicationId] = useState(() => savedSession("spacemusic.application"));
  const [sellerToken, setSellerToken] = useState(() => savedSession("spacemusic.token"));
  const [application, setApplication] = useState<Application | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [termsheet, setTermsheet] = useState<Termsheet | null>(null);
  const [busy, setBusy] = useState(false);
  const intakePending = useRef(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const confirmation = useRef<HTMLElement>(null);
  const [showPortal, setShowPortal] = useState(Boolean(applicationId && sellerToken));

  const [intake, setIntake] = useState({ email: "", name: "", artist: "", territories: "EU, US", referralId: "", marketing: false });
  const [passport, setPassport] = useState({ artist: "", track: "", months: "12", monthly: "0", ownership: "100", metadata: "100" });
  const [payoutToken, setPayoutToken] = useState("");
  const [report, setReport] = useState({ year: String(new Date().getFullYear()), amount: "", source: "DISTRIBUTOR" });

  async function refresh() {
    if (!applicationId || !sellerToken) return;
    try {
      const [app, docs, payoutData, reportData] = await Promise.all([
        request<Application>(`/seller/applications/${applicationId}`, {}, sellerToken),
        request<{ documents: Document[] }>(`/seller/applications/${applicationId}/documents`, {}, sellerToken),
        request<{ payouts: Payout[] }>(`/seller/applications/${applicationId}/payouts`, {}, sellerToken),
        request<{ reports: Report[] }>(`/seller/applications/${applicationId}/royalty-reports`, {}, sellerToken),
      ]);
      setApplication(app);
      setDocuments(docs.documents);
      setPayouts(payoutData.payouts);
      setReports(reportData.reports);
      setTermsheet(app.accepted_offer_id
        ? await request<Termsheet>(`/seller/applications/${applicationId}/termsheet`, {}, sellerToken)
        : null);
      setPassport((current) => ({
        ...current,
        artist: app.catalog_passport.artist_label,
        track: app.catalog_passport.tracks[0]?.title || current.track,
        ownership: String(Math.round(app.catalog_passport.rights_ownership_share * 100)),
        metadata: String(Math.round(app.catalog_passport.metadata_completeness * 100)),
      }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load application");
    }
  }

  useEffect(() => {
    if (showPortal) void refresh();
  }, [showPortal, applicationId, sellerToken]);

  useEffect(() => {
    if (notice && !showPortal) confirmation.current?.focus();
  }, [notice, showPortal]);

  async function submitIntake(event: FormEvent) {
    event.preventDefault();
    if (intakePending.current || !SUBMISSIONS_ENABLED) return;
    intakePending.current = true;
    trackApplication('application_started');
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!API_BASE && FORM_ENDPOINT) {
        const form = new FormData();
        form.set("firstName", intake.name || intake.artist);
        form.set("email", intake.email);
        form.set("artistLabel", intake.artist);
        form.set("territories", intake.territories);
        form.set("referralId", intake.referralId);
        form.set("consentMarketing", String(intake.marketing));
        form.set("source", "SpaceMusic seller review");
        for (const [key, value] of Object.entries(sourceMetadata())) form.set(key, value);
        form.set("_subject", `New SpaceMusic review — ${intake.artist}`);
        const response = await fetch(FORM_ENDPOINT, { method: "POST", body: form, headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error("Could not send review request");
        trackApplication('application_submitted');
        setNotice("Review request sent.");
        setIntake({ email: "", name: "", artist: "", territories: "EU, US", referralId: "", marketing: false });
        return;
      }
      const result = await request<{ application: Application; seller_token: string }>("/seller/applications", {
        method: "POST",
        body: JSON.stringify({
          contact_email: intake.email,
          seller_name: intake.name || undefined,
          artist_label: intake.artist,
          consent_version: "seller-terms-v1",
          consent_marketing: intake.marketing,
          referral_id: intake.referralId || undefined,
          territories: intake.territories.split(",").map((item) => item.trim()).filter(Boolean),
          royalty_sources: ["DISTRIBUTOR"],
        }),
      });
      trackApplication('application_submitted');
      sessionStorage.setItem("spacemusic.application", result.application.id);
      sessionStorage.setItem("spacemusic.token", result.seller_token);
      setApplicationId(result.application.id);
      setSellerToken(result.seller_token);
      setShowPortal(true);
      setNotice("Application saved. Keep this browser session to return to your review.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not submit application");
    } finally {
      intakePending.current = false;
      setBusy(false);
    }
  }

  async function savePassport(event: FormEvent) {
    event.preventDefault();
    if (!application) return;
    setBusy(true);
    setError("");
    try {
      await request(`/seller/applications/${application.id}/passport`, {
        method: "PUT",
        body: JSON.stringify({
          artist_label: passport.artist,
          tracks: passport.track ? [{ title: passport.track, master_rights_share: Number(passport.ownership) / 100, publishing_rights_share: Number(passport.ownership) / 100, writer_share: Number(passport.ownership) / 100, neighboring_rights_share: Number(passport.ownership) / 100 }] : [],
          territories: intake.territories.split(",").map((item) => item.trim()).filter(Boolean),
          royalty_sources: ["DISTRIBUTOR"],
          revenue_history: monthRange(Math.min(36, Math.max(1, Number(passport.months) || 1)), Math.max(0, Number(passport.monthly) || 0) * 100),
          metadata_completeness: Number(passport.metadata) / 100,
          anti_fraud_status: "PENDING",
          rights_ownership_share: Number(passport.ownership) / 100,
        }),
      }, sellerToken);
      setNotice("Catalog Passport updated. Upload source documents so SPACE can verify it.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update passport");
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !application) return;
    setBusy(true);
    setError("");
    try {
      const fileHash = await digest(file);
      const upload = await request<{ upload_url: string }>(`/seller/applications/${application.id}/documents`, {
        method: "POST",
        body: JSON.stringify({ document_type: "ROYALTY_STATEMENT", original_filename: file.name, content_type: file.type || "application/octet-stream", size_bytes: file.size, sha256: fileHash }),
      }, sellerToken);
      const response = await fetch(new URL(upload.upload_url, `${API_BASE}/`).toString(), { method: "PUT", headers: { "X-Seller-Token": sellerToken }, body: file });
      if (!response.ok) throw new Error("Upload failed");
      setNotice("Document uploaded. A reviewer will verify the source before valuation.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not upload document");
    } finally {
      event.target.value = "";
      setBusy(false);
    }
  }

  async function calculate() {
    if (!application || !BENCHMARK_VERSION || !BENCHMARK_LOW || !BENCHMARK_MEDIAN || !BENCHMARK_HIGH) return;
    setBusy(true);
    setError("");
    try {
      await request(`/seller/applications/${application.id}/valuation`, {
        method: "POST",
        body: JSON.stringify({ benchmark_version: BENCHMARK_VERSION, benchmark_multiple_low: BENCHMARK_LOW, benchmark_multiple_median: BENCHMARK_MEDIAN, benchmark_multiple_high: BENCHMARK_HIGH }),
      }, sellerToken);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Valuation is not ready");
    } finally {
      setBusy(false);
    }
  }

  async function acceptOffer(offerId: string) {
    if (!application) return;
    setBusy(true);
    setError("");
    try {
      await request(`/seller/applications/${application.id}/offers/${offerId}/accept`, { method: "POST" }, sellerToken);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not accept offer");
    } finally {
      setBusy(false);
    }
  }

  async function requestPayout(event: FormEvent) {
    event.preventDefault();
    if (!application?.accepted_offer_id || !payoutToken) return;
    setBusy(true);
    setError("");
    try {
      await request(`/seller/applications/${application.id}/payout`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ offer_id: application.accepted_offer_id, recipient_token: payoutToken }) }, sellerToken);
      await refresh();
      setNotice("Payout completed in test mode. The receipt is ready below.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not request payout");
    } finally {
      setBusy(false);
    }
  }

  async function submitReport(event: FormEvent) {
    event.preventDefault();
    if (!application) return;
    const year = Number(report.year);
    setBusy(true);
    setError("");
    try {
      await request(`/seller/applications/${application.id}/royalty-reports`, { method: "POST", body: JSON.stringify({ period_start: `${year}-01-01`, period_end: `${year}-12-31`, amount_cents: Math.max(0, Number(report.amount) || 0) * 100, currency_code: "EUR", source: report.source }) }, sellerToken);
      await refresh();
      setNotice("Royalty report submitted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not submit report");
    } finally {
      setBusy(false);
    }
  }

  const activeStatus = application?.status || "SUBMITTED";
  const progress: Status[] = ["SUBMITTED", "UNDER_REVIEW", "OFFER_READY", "ACCEPTED", "PAID"];
  const progressIndex = progress.indexOf(activeStatus) < 0 ? 0 : progress.indexOf(activeStatus);
  const canRequestValuation = activeStatus === "SUBMITTED"
    && documents.length > 0
    && documents.every((document) => document.status === "VERIFIED")
    && Boolean(application?.catalog_passport.revenue_history.length)
    && Boolean(BENCHMARK_VERSION);

  if (!showPortal) {
    return (
      <main className="shell landing-shell">
        <header className="masthead"><a className="wordmark" href="/" aria-label="SPACE home">SPACE</a><div className="eyebrow">CATALOG ACQUISITIONS</div></header>
        <section className="hero">
          <div className="hero-copy"><p className="kicker">For independent catalog owners</p><h1>We buy your music catalog.</h1><p className="hero-lede">SPACE reviews revenue-generating catalogs directly across genres. Ambient, sleep, focus, meditation, wellness, lo-fi and electronic music are examples. Every catalog is assessed individually.</p><div className="proof-row"><span>Direct buyer</span><span>Free evaluation</span><span>No obligation</span></div></div>
          <div className="intake-column">
          {notice ? <section className="intake-card confirmation" role="status" tabIndex={-1} ref={confirmation} aria-labelledby="review-sent">
            <div className="card-label">Your next step</div>
            <h2 id="review-sent">{notice}</h2>
            <p>We will follow up at the email address you provided to confirm the information needed for your catalog review.</p>
            <p className="muted">If your catalog is a fit, an initial offer typically follows within 5-7 business days after we receive the relevant information. This request is not an offer or a commitment to sell.</p>
            <h3>Prepare while you wait</h3>
            <p className="muted">Keep your royalty statements, track list and rights agreements together. Do not send passwords or publish private documents.</p>
            <p><a href="/blog/music-catalog-sale-documents-checklist/">Read the seller document checklist</a></p>
            <p className="muted">Need to correct something? Contact <a href="mailto:hello@spacemusic.io">hello@spacemusic.io</a> rather than submitting the same catalog again.</p>
            <button type="button" className="secondary" onClick={() => setNotice("")}>Request a review for another catalog</button>
          </section> : <>
          <form className="intake-card" onSubmit={submitIntake} onChangeCapture={() => trackApplication('application_started')}>
            {Object.entries(sourceMetadata()).map(([name, value]) => <input key={name} type="hidden" name={name} value={value} />)}
            <div className="card-label">Start a confidential review</div><h2>Tell us what you own.</h2><p className="muted">Start with your email and artist or label name. We request the relevant income and rights documents privately by email after you apply. No upload is needed now.</p>
            {error && <div className="alert error" role="alert">{error}. Your details are still here. Please try again, or contact <a href="mailto:hello@spacemusic.io">hello@spacemusic.io</a>.</div>}
            <label>Email<input required name="email" autoComplete="email" type="email" value={intake.email} onChange={(event) => setIntake({ ...intake, email: event.target.value })} placeholder="you@example.com" /></label><label>Artist or label<input required name="artistLabel" value={intake.artist} onChange={(event) => setIntake({ ...intake, artist: event.target.value })} placeholder="Catalog name" /></label><label>Your name <span className="optional">optional</span><input name="firstName" autoComplete="name" value={intake.name} onChange={(event) => setIntake({ ...intake, name: event.target.value })} placeholder="Name" /></label><label>Referral ID <span className="optional">optional</span><input name="referralId" value={intake.referralId} onChange={(event) => setIntake({ ...intake, referralId: event.target.value })} placeholder="If a partner referred you" /></label><label className="check"><input type="checkbox" checked={intake.marketing} onChange={(event) => setIntake({ ...intake, marketing: event.target.checked })} /> Send me occasional SPACE updates</label><button className="primary wide" disabled={busy || !SUBMISSIONS_ENABLED}>{busy ? "Sending..." : SUBMISSIONS_ENABLED ? "Request a free catalog review" : "Preview only"}<span aria-hidden="true">→</span></button>
            <p className="tiny">{SUBMISSIONS_ENABLED ? <>Submitting requests a free review, not a sale. Read our <a href="/pricing.md" target="_blank" rel="noopener noreferrer">pricing and offer policy (new tab)</a> and <a href="/privacy/" target="_blank" rel="noopener noreferrer">privacy notice (new tab)</a>.</> : "Preview mode: submissions stay disabled until the seller API or lead form is configured."}</p>
          </form>
          </>}
          </div>
        </section>
        <section className="three-up"><article><b>01</b><h3>Tell us about your catalog</h3><p>Share the basics about the music and rights you own. It takes a few minutes.</p></article><article><b>02</b><h3>We review the evidence</h3><p>We check ownership, rights, metadata, and royalty history through a private process.</p></article><article><b>03</b><h3>Get a clear next move</h3><p>If the catalog is a fit, we return a structured offer with no obligation to accept.</p></article></section>
      </main>
    );
  }

  return (
    <main className="shell portal-shell">
      <header className="masthead"><div className="wordmark">SPACE</div><button className="text-button" onClick={() => { sessionStorage.clear(); setShowPortal(false); setApplication(null); setTermsheet(null); }}>Start over</button></header>
      {error && <div className="alert error">{error}</div>}{notice && <div className="alert notice">{notice}</div>}
      <section className="portal-head"><div><p className="kicker">Seller workspace</p><h1>{application ? application.catalog_passport.artist_label : "Your catalog review"}</h1><p className="muted">{application?.contact_email}</p></div><div className={`status-pill status-${activeStatus.toLowerCase()}`}>{statusLabel(activeStatus)}</div></section>
      <nav className="progress" aria-label="Application progress">{progress.map((item, index) => <div key={item} className={`progress-step ${index <= progressIndex ? "done" : ""} ${item === activeStatus ? "current" : ""}`}><span>{index + 1}</span><small>{statusLabel(item)}</small></div>)}</nav>
      <section className="portal-grid">
        <article className="panel passport-panel"><div className="panel-heading"><div><p className="card-label">Catalog Passport</p><h2>What we are reviewing</h2></div><span className="version">v{application?.catalog_passport ? "current" : "1"}</span></div><form onSubmit={savePassport}><label>Artist or label<input required value={passport.artist} onChange={(event) => setPassport({ ...passport, artist: event.target.value })} /></label><div className="two-col"><label>Primary track<input value={passport.track} onChange={(event) => setPassport({ ...passport, track: event.target.value })} placeholder="Track title" /></label><label>Territories<input value={intake.territories} onChange={(event) => setIntake({ ...intake, territories: event.target.value })} /></label></div><div className="three-col"><label>Months of history<input type="number" min="1" max="36" value={passport.months} onChange={(event) => setPassport({ ...passport, months: event.target.value })} /></label><label>Avg. EUR / month<input type="number" min="0" value={passport.monthly} onChange={(event) => setPassport({ ...passport, monthly: event.target.value })} /></label><label>Owned share %<input type="number" min="0" max="100" value={passport.ownership} onChange={(event) => setPassport({ ...passport, ownership: event.target.value })} /></label></div><label>Metadata completeness %<input type="number" min="0" max="100" value={passport.metadata} onChange={(event) => setPassport({ ...passport, metadata: event.target.value })} /></label><button className="secondary" disabled={busy}>Save Passport</button></form></article>
        <article className="panel documents-panel"><div className="panel-heading"><div><p className="card-label">Evidence</p><h2>Upload statements</h2></div><span className="lock">Private</span></div><p className="muted">Accepted evidence is checked by a reviewer before a commercial valuation is prepared.</p><label className="upload-box"><input type="file" accept=".csv,.pdf,.xlsx,.xls" onChange={uploadDocument} disabled={busy} /><strong>Drop a royalty statement here</strong><span>CSV, PDF, or spreadsheet up to 25 MB</span></label><div className="doc-list">{documents.length ? documents.map((document) => <div className="doc-row" key={document.id}><span className="doc-icon">↗</span><div><b>{document.original_filename}</b><small>Version {document.version} · {document.document_type.replaceAll("_", " ").toLowerCase()}</small></div><span className={`doc-status doc-${document.status.toLowerCase()}`}>{document.status.replaceAll("_", " ")}</span></div>) : <p className="empty">No documents uploaded yet.</p>}</div></article>
      </section>
      <section className="panel review-panel"><div className="panel-heading"><div><p className="card-label">Review status</p><h2>{activeStatus === "DATA_REQUIRED" ? "A few details are still needed" : activeStatus === "OFFER_READY" ? "Your offer is ready" : activeStatus === "UNDER_REVIEW" ? "Your catalog is under review" : "Your file is in the queue"}</h2></div>{activeStatus === "SUBMITTED" && <button className="secondary" onClick={calculate} disabled={busy || !canRequestValuation}>{canRequestValuation ? "Request valuation" : "Awaiting verified documents"}</button>}{activeStatus === "UNDER_REVIEW" && <span className="lock">Review in progress</span>}{activeStatus === "DATA_REQUIRED" && <span className="lock">Action required</span>}</div><p className="muted">{activeStatus === "DATA_REQUIRED" ? "Review the evidence list above and upload the missing source files." : activeStatus === "UNDER_REVIEW" ? "We are checking ownership, rights chain, metadata, and the supplied royalty history. We will show an offer when this review is complete." : "We use verified royalty evidence and an explicit benchmark. No audience metrics are used to set the offer."}</p></section>
      {activeStatus === "OFFER_READY" && <section className="offer-section"><div className="section-intro"><p className="kicker">Offer comparison</p><h2>Choose how much to sell.</h2><p className="muted">Each option uses the same reviewed valuation. Review the rights transferred and retained before accepting.</p></div><div className="offers">{application?.offers.map((offer) => <article className={`offer-card ${offer.sale_percentage === 75 ? "featured" : ""}`} key={offer.id}>{offer.sale_percentage === 75 && <div className="recommended">Most flexible</div>}<div className="offer-percent">{offer.sale_percentage}%</div><p className="muted">of defined rights</p><div className="offer-price">{formatMoney(offer.cash_median_cents, offer.currency_code)}</div><small className="range">{formatMoney(offer.cash_low_cents, offer.currency_code)} - {formatMoney(offer.cash_high_cents, offer.currency_code)}</small><dl><div><dt>Transferred</dt><dd>{Object.entries(offer.rights_transferred).map(([key, value]) => `${key} ${Math.round(value * 100)}%`).join(" · ")}</dd></div><div><dt>Payment date</dt><dd>{offer.payment_date}</dd></div><div><dt>Valid until</dt><dd>{offer.valid_until}</dd></div></dl><button className={offer.sale_percentage === 75 ? "primary wide" : "secondary wide"} onClick={() => acceptOffer(offer.id)} disabled={busy}>Accept {offer.sale_percentage}% <span>→</span></button></article>)}</div></section>}
      {activeStatus === "ACCEPTED" && <><section className="panel termsheet-panel"><div className="panel-heading"><div><p className="card-label">Draft termsheet</p><h2>Review the selected offer</h2></div><span className="version">{termsheet?.version || "Loading"}</span></div>{termsheet && <><p className="muted">This is a structured commercial summary, not a final legal agreement. Legal review is required before a rights transfer.</p><div className="termsheet-summary"><strong>{termsheet.offer.sale_percentage}% of defined rights</strong><span>{formatMoney(termsheet.offer.cash_median_cents, termsheet.offer.currency_code)} median cash amount</span><small>{termsheet.requires_legal_review ? "Exceptions require review" : "No exceptions recorded in this draft"}</small></div></>}</section><section className="panel payout-panel"><div><p className="card-label">Next step</p><h2>Prepare your payout</h2><p className="muted">In local development this uses a deterministic test adapter. No money moves.</p></div><form onSubmit={requestPayout}><label>Recipient token<input required minLength={8} value={payoutToken} onChange={(event) => setPayoutToken(event.target.value)} placeholder="Secure payout destination token" /></label><button className="primary" disabled={busy}>Run test payout <span>→</span></button></form></section></>}
      {activeStatus === "PAID" && <section className="portal-grid"><article className="panel payout-panel"><p className="card-label">Completed</p><h2>Payment record</h2>{payouts.map((payout) => <div className="payout-record" key={payout.id}><strong>{formatMoney(payout.amount_cents, payout.currency_code)}</strong><span>{payout.status}</span>{payout.receipt_url && <a href={`${API_BASE}${payout.receipt_url}`} target="_blank" rel="noreferrer">Download receipt ↗</a>}</div>)}</article><article className="panel"><div className="panel-heading"><div><p className="card-label">After closing</p><h2>Royalty reporting</h2></div></div><form onSubmit={submitReport}><div className="two-col"><label>Year<input required type="number" value={report.year} onChange={(event) => setReport({ ...report, year: event.target.value })} /></label><label>Royalty EUR<input required type="number" min="0" value={report.amount} onChange={(event) => setReport({ ...report, amount: event.target.value })} /></label></div><label>Source<select value={report.source} onChange={(event) => setReport({ ...report, source: event.target.value })}><option value="DISTRIBUTOR">Distributor</option><option value="PUBLISHER">Publisher</option><option value="PRO">PRO</option><option value="DIRECT_LICENSE">Direct license</option></select></label><button className="secondary" disabled={busy}>Submit report</button></form>{reports.length > 0 && <div className="report-list">{reports.map((item) => <div key={item.id}><span>{item.period_start.slice(0, 4)}</span><b>{formatMoney(item.amount_cents)}</b><small>{item.status}</small></div>)}</div>}</article></section>}
      <footer className="portal-footer"><span>SPACE seller workspace</span><span>Need help? Use the support channel shared in your application email.</span></footer>
    </main>
  );
}
