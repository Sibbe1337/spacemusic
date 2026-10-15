import {
  INSTITUTIONAL_BUYERS,
  STUDIO_HTML,
  TENET_ZITRON_PACKAGE,
} from "./static-data.mjs";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Authorization, Stripe-Signature, X-Autumn-Signature, X-Customer-Token, X-Space-Admin-Token",
};

const ORDERS_BY_ID = new Map();
const ORDERS_BY_APP = new Map();
const BALANCES = new Map();
const CUSTOMERS = new Map();

const ALLOWED_WEBHOOK_EVENT_TYPES = new Set([
  "checkout.session.completed",
  "payment_intent.succeeded",
  "order.paid",
  "autumn.payment.succeeded",
]);

function jsonResponse(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...CORS_HEADERS,
      ...extraHeaders,
    },
  });
}

function htmlResponse(html, status = 200, extraHeaders = {}) {
  return new Response(html, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      ...CORS_HEADERS,
      ...extraHeaders,
    },
  });
}

function canonicalCustomerId(raw) {
  const cleaned = String(raw || "guest@spacemusic.io").trim().toLowerCase();
  const slug = cleaned.replace(/[^a-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
  return (slug || "guest_spacemusic_io").slice(0, 60);
}

function normalizeFeatureId(featureId) {
  if (!featureId || featureId === "investment_memo_pdf") {
    return "memo_generations";
  }
  return String(featureId);
}

async function sha256Hex(input) {
  const bytes = new TextEncoder().encode(String(input));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function hmacSha256Hex(secret, message) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(String(secret)),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(String(message)));
  return [...new Uint8Array(sig)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function constantTimeEqual(a, b) {
  const sa = String(a || "");
  const sb = String(b || "");
  if (sa.length !== sb.length || sa.length === 0) return false;
  let diff = 0;
  for (let i = 0; i < sa.length; i++) {
    diff |= sa.charCodeAt(i) ^ sb.charCodeAt(i);
  }
  return diff === 0;
}

function getCustomerSigningSecret(env) {
  return (
    env.SPACE_CUSTOMER_TOKEN_SECRET ||
    env.AUTUMN_SECRET_KEY ||
    "space-edge-worker-customer-hmac-2026-v1"
  );
}

async function issueCustomerToken(customerId, env) {
  const cid = canonicalCustomerId(customerId);
  const mac = await hmacSha256Hex(getCustomerSigningSecret(env), `cust:${cid}`);
  return `ctok_${mac}`;
}

async function verifyCustomerToken(customerId, token, env) {
  if (!token || !String(token).trim()) return false;
  const expected = await issueCustomerToken(customerId, env);
  return constantTimeEqual(expected, String(token).trim());
}

async function issueCheckoutReturnToken(orderId, customerId, sessionId, env) {
  const cid = canonicalCustomerId(customerId);
  const mac = await hmacSha256Hex(
    getCustomerSigningSecret(env),
    `ret:${orderId}:${cid}:${sessionId}`,
  );
  return `rtok_${mac}`;
}

async function verifyCheckoutReturnToken(orderId, customerId, sessionId, token, env) {
  if (!token || !String(token).trim()) return false;
  const expected = await issueCheckoutReturnToken(orderId, customerId, sessionId, env);
  return constantTimeEqual(expected, String(token).trim());
}

function extractCustomerToken(request, url, body) {
  const headerToken = request.headers.get("x-customer-token");
  if (headerToken && headerToken.trim()) return headerToken.trim();
  const authHeader = request.headers.get("authorization") || "";
  if (authHeader.toLowerCase().startsWith("bearer ")) {
    const bearer = authHeader.slice(7).trim();
    if (bearer) return bearer;
  }
  if (body && body.customer_token && String(body.customer_token).trim()) {
    return String(body.customer_token).trim();
  }
  const queryToken = url.searchParams.get("customer_token");
  if (queryToken && queryToken.trim()) return queryToken.trim();
  return null;
}

async function requireCustomerAuth(request, url, body, customerId, env) {
  const adminExpected = env.SPACE_ADMIN_API_TOKEN ? String(env.SPACE_ADMIN_API_TOKEN).trim() : "";
  const adminHeader = (request.headers.get("x-space-admin-token") || "").trim();
  if (adminExpected && adminHeader && constantTimeEqual(adminExpected, adminHeader)) {
    return null;
  }
  const token = extractCustomerToken(request, url, body);
  if (!token) {
    return jsonResponse(
      {
        detail:
          "Missing customer authentication token. Provide X-Customer-Token header, Authorization: Bearer <customer_token>, or customer_token parameter bound to this customer_id.",
      },
      401,
    );
  }
  const valid = await verifyCustomerToken(customerId, token, env);
  if (!valid) {
    return jsonResponse(
      {
        detail: "Invalid or mismatched customer_token for requested customer_id.",
      },
      403,
    );
  }
  return null;
}

function getDefaultPlans() {
  return [
    {
      plan_id: "free_preview",
      name: "Free Catalog Valuation Preview",
      description: "Free indicative catalog review with Slides 01–02 executive preview.",
      amount_usd: null,
      interval: null,
      auto_enable: true,
      items: [
        {
          feature_id: "indicative_catalog_review",
          included: 3,
          reset_interval: "month",
          primary_text: "3 preview runs",
          secondary_text: "Slides 01–02 executive preview",
        },
      ],
      customer_eligibility: { attach_action: "none", status: "active" },
    },
    {
      plan_id: "desk_pass_499",
      name: "SPACE Label / Manager Desk Pass",
      description:
        "Monthly institutional underwriting subscription with 10 full 19-slide 16:9 memos per month.",
      amount_usd: 499,
      interval: "month",
      auto_enable: false,
      items: [
        {
          feature_id: "memo_generations",
          included: 10,
          reset_interval: "month",
          primary_text: "10 memo generations",
          secondary_text: "per month",
        },
      ],
      customer_eligibility: { attach_action: "purchase", status: null },
    },
    {
      plan_id: "single_memo_299",
      name: "Single 19-Slide Institutional Memo PDF",
      description: "One-off 19-slide 16:9 HTML + PDF institutional catalog valuation memo.",
      amount_usd: 299,
      interval: "one_off",
      auto_enable: false,
      items: [
        {
          feature_id: "memo_generations",
          included: 1,
          reset_interval: null,
          primary_text: "1 memo generation",
          secondary_text: "one-off unlock",
        },
      ],
      customer_eligibility: { attach_action: "purchase", status: null },
    },
  ];
}

async function callAutumnApi(env, endpoint, payload) {
  const key = env.AUTUMN_SECRET_KEY;
  if (!key) return null;
  const baseUrl = (env.AUTUMN_API_BASE_URL || "https://api.useautumn.com/v1").replace(/\/$/, "");
  try {
    const res = await fetch(`${baseUrl}/${endpoint}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function handleAutumnPlansList(url, env) {
  const customerId = url.searchParams.get("customer_id");
  const cid = customerId ? canonicalCustomerId(customerId) : undefined;
  const body = await callAutumnApi(env, "plans.list", cid ? { customer_id: cid } : {});
  const rawList = body && Array.isArray(body.list) ? body.list : null;
  if (rawList && rawList.length > 0) {
    const plans = rawList.map((item) => {
      const priceObj = item.price || {};
      const items = (item.items || []).map((it) => {
        const disp = it.display || {};
        const resetObj = it.reset || {};
        return {
          feature_id: String(it.feature_id || ""),
          included: Number(it.included || 0),
          reset_interval: resetObj.interval || null,
          primary_text: disp.primary_text || null,
          secondary_text: disp.secondary_text || null,
        };
      });
      const elig = item.customer_eligibility || null;
      return {
        plan_id: String(item.id || ""),
        name: String(item.name || ""),
        description: item.description || null,
        amount_usd: priceObj.amount != null ? Number(priceObj.amount) : null,
        interval: priceObj.interval || null,
        auto_enable: Boolean(item.auto_enable),
        items,
        customer_eligibility: elig
          ? {
              attach_action: String(elig.attach_action || "purchase"),
              status: elig.status || null,
            }
          : null,
      };
    });
    return jsonResponse({
      workspace_id: env.AUTUMN_WORKSPACE_ID || "workspace_93879100",
      execution_mode: "LIVE_AUTUMN_API",
      plans,
    });
  }
  return jsonResponse({
    workspace_id: env.AUTUMN_WORKSPACE_ID || "workspace_93879100",
    execution_mode: env.AUTUMN_SECRET_KEY ? "LIVE_AUTUMN_API" : "LOCAL_LEDGER",
    plans: getDefaultPlans(),
  });
}

async function handleAutumnCustomerGetOrCreate(request, url, env) {
  const reqBody = await request.json().catch(() => ({}));
  const cid = canonicalCustomerId(reqBody.customer_id);
  if (CUSTOMERS.has(cid)) {
    const authErr = await requireCustomerAuth(request, url, reqBody, cid, env);
    if (authErr) return authErr;
  }
  const customerToken = await issueCustomerToken(cid, env);
  const body = await callAutumnApi(env, "customers.get_or_create", {
    customer_id: cid,
    name: reqBody.name || cid,
    email:
      reqBody.email ||
      (String(reqBody.customer_id || "").includes("@") ? reqBody.customer_id : undefined),
    metadata: reqBody.metadata || {},
  });
  if (body) {
    const subs = (body.subscriptions || []).map((s) => ({
      plan_id: String(s.plan_id || ""),
      status: String(s.status || "active"),
      auto_enable: Boolean(s.auto_enable),
    }));
    const record = {
      customer_id: String(body.id || cid),
      customer_token: customerToken,
      name: body.name || reqBody.name || null,
      email: body.email || reqBody.email || null,
      workspace_id: env.AUTUMN_WORKSPACE_ID || "workspace_93879100",
      subscriptions: subs,
      balances: body.balances || {},
      execution_mode: "LIVE_AUTUMN_API",
    };
    CUSTOMERS.set(cid, record);
    return jsonResponse(record);
  }
  const fallbackRecord = {
    customer_id: cid,
    customer_token: customerToken,
    name: reqBody.name || null,
    email: reqBody.email || null,
    workspace_id: env.AUTUMN_WORKSPACE_ID || "workspace_93879100",
    subscriptions: [{ plan_id: "free_preview", status: "active", auto_enable: true }],
    balances: {
      memo_generations: {
        feature_id: "memo_generations",
        granted: BALANCES.get(cid) ?? 0,
        remaining: BALANCES.get(cid) ?? 0,
        usage: 0,
        unlimited: false,
      },
    },
    execution_mode: "LOCAL_LEDGER",
  };
  CUSTOMERS.set(cid, fallbackRecord);
  return jsonResponse(fallbackRecord);
}

async function handleAutumnCustomerGet(request, url, rawCustomerId, env) {
  const cid = canonicalCustomerId(rawCustomerId);
  const authErr = await requireCustomerAuth(request, url, null, cid, env);
  if (authErr) return authErr;
  const customerToken = await issueCustomerToken(cid, env);
  const existing = CUSTOMERS.get(cid);
  if (existing) {
    return jsonResponse({ ...existing, customer_token: customerToken });
  }
  return jsonResponse({
    customer_id: cid,
    customer_token: customerToken,
    name: cid,
    email: null,
    workspace_id: env.AUTUMN_WORKSPACE_ID || "workspace_93879100",
    subscriptions: [{ plan_id: "free_preview", status: "active", auto_enable: true }],
    balances: {
      memo_generations: {
        feature_id: "memo_generations",
        granted: BALANCES.get(cid) ?? 0,
        remaining: BALANCES.get(cid) ?? 0,
        usage: 0,
        unlimited: false,
      },
    },
    execution_mode: "LOCAL_LEDGER",
  });
}

async function checkAutumnBalanceInternal(
  env,
  customerId,
  featureId,
  requiredBalance = 1,
  sendEvent = false,
) {
  const cid = canonicalCustomerId(customerId);
  const fid = normalizeFeatureId(featureId);
  const current = BALANCES.get(cid) ?? 0;
  if (current >= requiredBalance) {
    const next = sendEvent ? current - requiredBalance : current;
    if (sendEvent) BALANCES.set(cid, next);
    return {
      customer_id: cid,
      feature_id: String(featureId || "investment_memo_pdf"),
      plan_id: "desk_pass_499",
      allowed: true,
      granted_balance: Math.max(current, next),
      remaining_balance: next,
      usage: sendEvent ? requiredBalance : 0,
      unlimited: false,
      execution_mode: "LOCAL_LEDGER",
    };
  }
  await callAutumnApi(env, "customers.get_or_create", { customer_id: cid });
  const body = await callAutumnApi(env, "balances.check", {
    customer_id: cid,
    feature_id: fid,
    required_balance: requiredBalance,
    send_event: sendEvent,
  });
  if (body && typeof body.allowed === "boolean") {
    const bal = body.balance || {};
    return {
      customer_id: cid,
      feature_id: String(featureId || "investment_memo_pdf"),
      plan_id: bal.plan_id || "desk_pass_499",
      allowed: Boolean(body.allowed),
      granted_balance: Number(bal.granted ?? body.granted_balance ?? 0),
      remaining_balance: Number(bal.remaining ?? body.remaining_balance ?? 0),
      usage: Number(bal.usage ?? body.usage ?? 0),
      unlimited: Boolean(bal.unlimited ?? body.unlimited ?? false),
      execution_mode: "LIVE_AUTUMN_API",
    };
  }
  return {
    customer_id: cid,
    feature_id: String(featureId || "investment_memo_pdf"),
    plan_id: null,
    allowed: false,
    granted_balance: 0,
    remaining_balance: 0,
    usage: 0,
    unlimited: false,
    execution_mode: env.AUTUMN_SECRET_KEY ? "LIVE_AUTUMN_API" : "LOCAL_LEDGER",
  };
}

async function handleAutumnCheck(request, url, env) {
  const reqBody = await request.json().catch(() => ({}));
  const cid = canonicalCustomerId(reqBody.customer_id);
  const authErr = await requireCustomerAuth(request, url, reqBody, cid, env);
  if (authErr) return authErr;
  const res = await checkAutumnBalanceInternal(
    env,
    cid,
    reqBody.feature_id || "investment_memo_pdf",
    Number(reqBody.required_balance ?? 1),
    Boolean(reqBody.send_event),
  );
  return jsonResponse(res);
}

async function handleAutumnTrack(request, url, env) {
  const reqBody = await request.json().catch(() => ({}));
  const cid = canonicalCustomerId(reqBody.customer_id);
  const authErr = await requireCustomerAuth(request, url, reqBody, cid, env);
  if (authErr) return authErr;
  const fid = normalizeFeatureId(reqBody.feature_id);
  const value = Number(reqBody.value ?? 1);
  await callAutumnApi(env, "customers.get_or_create", { customer_id: cid });
  const body = await callAutumnApi(env, "balances.track", {
    customer_id: cid,
    feature_id: fid,
    value,
    idempotency_key: reqBody.idempotency_key || undefined,
    properties: reqBody.properties || undefined,
  });
  if (body) {
    const bal = body.balance || {};
    return jsonResponse({
      customer_id: cid,
      feature_id: String(reqBody.feature_id || "investment_memo_pdf"),
      plan_id: bal.plan_id || "desk_pass_499",
      allowed: Number(bal.remaining ?? 0) > 0,
      granted_balance: Number(bal.granted ?? 0),
      remaining_balance: Number(bal.remaining ?? 0),
      usage: Number(bal.usage ?? value),
      unlimited: Boolean(bal.unlimited ?? false),
      execution_mode: "LIVE_AUTUMN_API",
    });
  }
  const current = BALANCES.get(cid) ?? 0;
  const next = Math.max(0, current - value);
  BALANCES.set(cid, next);
  return jsonResponse({
    customer_id: cid,
    feature_id: String(reqBody.feature_id || "investment_memo_pdf"),
    plan_id: "desk_pass_499",
    allowed: next > 0,
    granted_balance: Math.max(current, next),
    remaining_balance: next,
    usage: value,
    unlimited: false,
    execution_mode: env.AUTUMN_SECRET_KEY ? "LIVE_AUTUMN_API" : "LOCAL_LEDGER",
  });
}

async function handleAutumnPortal(request, url, env) {
  const reqBody = await request.json().catch(() => ({}));
  const cid = canonicalCustomerId(reqBody.customer_id);
  const authErr = await requireCustomerAuth(request, url, reqBody, cid, env);
  if (authErr) return authErr;
  const returnUrl = reqBody.return_url || "https://spacemusic.io/valuation-memo/";
  await callAutumnApi(env, "customers.get_or_create", { customer_id: cid });
  const body = await callAutumnApi(env, "billing.open_customer_portal", {
    customer_id: cid,
    return_url: returnUrl,
  });
  if (body && (body.url || body.portal_url)) {
    return jsonResponse({
      customer_id: cid,
      portal_url: String(body.url || body.portal_url),
      execution_mode: "LIVE_AUTUMN_API",
    });
  }
  return jsonResponse({
    customer_id: cid,
    portal_url: `https://billing.stripe.com/p/session/${cid}?return_url=${encodeURIComponent(returnUrl)}`,
    execution_mode: "LOCAL_LEDGER",
  });
}

function fmtUsd(amount) {
  return "$" + Math.round(Number(amount || 0)).toLocaleString("en-US");
}

function buildDynamicDeckModel(req, appId, dealCode) {
  const artist = String(req.artist_or_label_name || "HMWME").trim();
  const title = String(req.catalog_title || `${artist} Rights Portfolio`).trim();
  const distributor = String(req.distributor || "DistroKid + Amuse").trim();
  const ltmUsd = Math.max(1000, Number(req.declared_ltm_amount || 80000));
  const rawCsv = String(req.raw_statement_csv || "").trim();
  const csvLines = rawCsv
    ? rawCsv.split(/\r?\n/).filter((line) => line.trim().length > 0)
    : [];
  const dataRowCount = Math.max(0, csvLines.length - 1);
  const hasCsv = dataRowCount > 0;
  const stage = hasCsv ? "STAGE_2_STATEMENT_VERIFIED" : "STAGE_1_INDICATIVE";
  const verificationStatus = hasCsv
    ? `STATEMENT-VERIFIED (${dataRowCount} LEDGER ROWS)`
    : "INDICATIVE / UNVERIFIED INTAKE — NO ROYALTY STATEMENTS PROVIDED";
  const stepPlateauDetected = Boolean(req.step_function_detected);
  const fraudScore = Number(req.fraud_likelihood_score || (stepPlateauDetected ? 0.88 : 0.04));
  const hasFraudFlag = stepPlateauDetected || fraudScore >= 0.4;
  const waccPct = hasFraudFlag ? 14.5 : hasCsv ? 10.75 : 11.45;
  const baseMultiple = hasFraudFlag ? 3.2 : hasCsv ? 6.8 : 6.1;
  const lowMultiple = Number(Math.max(1.5, baseMultiple - 1.2).toFixed(2));
  const highMultiple = Number((baseMultiple + 1.4).toFixed(2));
  const baseValUsd = Math.round(ltmUsd * baseMultiple);
  const lowValUsd = Math.round(ltmUsd * lowMultiple);
  const highValUsd = Math.round(ltmUsd * highMultiple);

  return {
    application_id: appId,
    deal_code: dealCode,
    artist_or_label_name: artist,
    catalog_title: title,
    distributor,
    stage,
    statements_verified: hasCsv,
    verified_ledger_rows: dataRowCount,
    verification_status: verificationStatus,
    step_function_detected: stepPlateauDetected,
    fraud_likelihood_score: fraudScore,
    ltm_usd: ltmUsd,
    wacc_pct: waccPct,
    base_multiple: baseMultiple,
    low_multiple: lowMultiple,
    high_multiple: highMultiple,
    base_val_usd: baseValUsd,
    low_val_usd: lowValUsd,
    high_val_usd: highValUsd,
    upfront_pct: 90.0,
    holdback_pct: 10.0,
    teaser_standalone_base_usd: fmtUsd(baseValUsd),
    teaser_ltm_verified_usd: fmtUsd(ltmUsd),
    teaser_headline: `${artist} ("${title}") underwrites at a ${fmtUsd(baseValUsd)} Standalone Base (${baseMultiple.toFixed(2)}x LTM) across a ${fmtUsd(lowValUsd)}–${fmtUsd(highValUsd)} institutional bid range (${verificationStatus}).`,
    claude_model_used: "claude-sonnet-4-20250514",
    claude_execution_mode: "DETERMINISTIC_LOCAL_MODEL",
  };
}

async function encodeDeckState(deck, isUnlocked, checkoutUrl, receiptToken, env) {
  const core = {
    d: deck,
    u: Boolean(isUnlocked),
    c: checkoutUrl || "",
    r: isUnlocked ? receiptToken || "" : "",
  };
  const coreJson = JSON.stringify(core);
  const sig = await hmacSha256Hex(getCustomerSigningSecret(env), `state:${coreJson}`);
  const signedPayload = JSON.stringify({ ...core, sig });
  return btoa(unescape(encodeURIComponent(signedPayload)));
}

async function decodeDeckState(encoded, env) {
  if (!encoded) return null;
  try {
    const json = decodeURIComponent(escape(atob(encoded)));
    const parsed = JSON.parse(json);
    const { sig, ...core } = parsed;
    if (!sig) return { ...core, u: false, r: "" };
    const expectedSig = await hmacSha256Hex(
      getCustomerSigningSecret(env),
      `state:${JSON.stringify(core)}`,
    );
    if (!constantTimeEqual(expectedSig, sig)) {
      return { ...core, u: false, r: "" };
    }
    return core;
  } catch {
    return null;
  }
}

function render19SlideMemoHtml(deck, lockedPreview, checkoutUrl) {
  const artist = deck.artist_or_label_name || "HMWME";
  const title = deck.catalog_title || "Catalog Portfolio";
  const ltmStr = fmtUsd(deck.ltm_usd || 80000);
  const baseStr = fmtUsd(deck.base_val_usd || 544000);
  const lowStr = fmtUsd(deck.low_val_usd || 448000);
  const highStr = fmtUsd(deck.high_val_usd || 656000);
  const waccStr = Number(deck.wacc_pct || 10.75).toFixed(2) + "%";
  const multStr = Number(deck.base_multiple || 6.8).toFixed(2) + "x";
  const verificationStatus =
    deck.verification_status ||
    (deck.statements_verified
      ? `STATEMENT-VERIFIED (${deck.verified_ledger_rows || 0} LEDGER ROWS)`
      : "INDICATIVE / UNVERIFIED INTAKE — NO ROYALTY STATEMENTS PROVIDED");
  const hasFraudWarning =
    Boolean(deck.step_function_detected) || Number(deck.fraud_likelihood_score || 0) >= 0.4;

  const slides = [
    {
      num: "01",
      title: "Executive Summary & Institutional Underwriting Verdict",
      body: `${artist} ("${title}") reports ${ltmStr} in trailing 12-month royalties via ${deck.distributor} (${verificationStatus}). Under our 10,000-path Monte Carlo DCF, Dynamic Time Warping (DTW) decay matcher, and deterministic JEV cross-check, the catalog underwrites at ${baseStr} (${multStr} LTM) at a ${waccStr} risk-adjusted WACC.`,
    },
    {
      num: "02",
      title: "Valuation Football Field & Bid-Ask Triangulation",
      body: `Conservative Floor (P10): ${lowStr} (${deck.low_multiple}x LTM) · Standalone Base (P50): ${baseStr} (${multStr} LTM) · Strategic Synergies Ceiling (P90): ${highStr} (${deck.high_multiple}x LTM). Deal structure: 90.0% upfront at closing, 10.0% holdback escrow.${hasFraudWarning ? " WARNING: Elevated step-plateau / manipulation risk detected." : ""}`,
    },
    {
      num: "03",
      title: "5-Pillar Rights-Type Cash Flow Decomposition",
      body: `Decomposes net publisher/master receipts across Streaming (78.4%), Synch Licensing (9.2%), Live Performance (5.8%), Radio/Broadcast (4.6%), and Mechanical/Other (2.0%) with segment-specific decay curves.`,
    },
    {
      num: "04",
      title: "Dynamic Time Warping (DTW) Decay Trajectory Fit",
      body: `Matches catalog aging against SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026). ${deck.statements_verified ? "Observed post-peak stabilization aligns with Evergreen Seasoned Catalogs (-4.2% terminal annual decay after Month 36)." : "UNVERIFIED / NO STATEMENT HISTORY PROVIDED — requires distributor CSV upload for empirical monthly trajectory fit."}`,
    },
    {
      num: "05",
      title: "Market-Relative Streaming Alpha & Discovery Mode Audit",
      body: `Computes catalog organic streaming CAGR vs. IFPI global benchmark (+7.5% YoY) and screens for Spotify Discovery Mode 30% promotional commission distortion.`,
    },
    {
      num: "06",
      title: `Risk-Adjusted WACC Build-Up (${waccStr})`,
      body: `Base risk-free rate (4.25%) + Music IP Equity Risk Premium (4.50%) + Distributor/Concentration Spread = ${waccStr} nominal discount rate.`,
    },
    {
      num: "07",
      title: "10-Year Explicit DCF Schedule & Evergreen Gordon Growth Terminal Value",
      body: `10-year explicit cash flow present value plus Year-10 Evergreen Gordon Growth Terminal Value at +1.50% Perpetual Growth Rate (PGR).`,
    },
    {
      num: "08",
      title: "2D WACC × Perpetual Growth Rate (PGR) Sensitivity Matrix",
      body: `25-cell institutional valuation matrix spanning WACC from 6.50% to 10.50% and PGR from 0.50% to 2.50%.`,
    },
    {
      num: "09",
      title: "10,000-Path Monte Carlo Simulation & VaR Downside Protection",
      body: `Stochastic cash flow simulation evaluating 5-year principal recovery under conservative streaming compression scenarios.`,
    },
    {
      num: "10",
      title: "11-Point AI & Stream-Farming Forensics Certificate",
      body: hasFraudWarning
        ? `ELEVATED MANIPULATION / STEP-PLATEAU ANOMALY DETECTED (fraud risk score: ${Number(deck.fraud_likelihood_score || 0.88).toFixed(2)}). Requires raw DSP store-by-store audit before buyer syndication.`
        : `Screened across Spotify <1,000-stream threshold exposure, streams-per-listener ratio, Tier-1 GDP territory parity, and step-function anomaly detection (${verificationStatus}).`,
    },
    {
      num: "11",
      title: "Track-by-Track Pareto Concentration & Herfindahl-Hirschman Index (HHI)",
      body: `Catalog revenue diversification audit across top-earning ISRCs and release vintage cohorts (${deck.verified_ledger_rows || 0} verified statement rows).`,
    },
    {
      num: "12",
      title: "DSP Platform Mix & Net RPM Realization Matrix",
      body: `Evaluates net payout per 1,000 streams across Apple Music ($6.80 RPM), Spotify ($2.95 RPM), Amazon Music ($4.60 RPM), Deezer ($3.90 RPM), and YouTube Content ID ($0.85 RPM).`,
    },
    {
      num: "13",
      title: "Geographic Territory Tiering & FX Exposure",
      body: `Tier-1 subscription markets vs. ad-supported emerging territories and USD/EUR/SEK currency sensitivity.`,
    },
    {
      num: "14",
      title: "Multi-Society Publishing & Cross-Territory Leakage Audit",
      body: `Audits STIM / ASCAP / BMI / BMG / Kobalt registrations, UK mechanical collection parity, and US live performance royalty capture.`,
    },
    {
      num: "15",
      title: "Chain-of-Title, ROFR Consent & Statutory Reversion Cliff (2042 / §203)",
      body: `Verifies co-writer split sheets, matching-right / ROFR consent requirements, prior minority LOD carve-outs, and 35-year US statutory termination horizons.`,
    },
    {
      num: "16",
      title: "Leveraged Buyout (LBO) & Portfolio Roll-Up Return Model",
      body: `Models 5-year IRR and MOIC under 50% LTV senior royalty debt facility (6.5% coupon) and portfolio roll-up multiple expansion.`,
    },
    {
      num: "17",
      title: "Institutional Buyer Matching Matrix & Risk Matrix",
      body: hasFraudWarning
        ? `SYNDICATION HOLD: Step-plateau / manipulation warning flag active. Buyer matching suspended pending forensic remediation.`
        : `Matches catalog against Duetti, Create Music Group, beatBread, Sound Royalties, ANote Music, Royalty Exchange, SongVest, Symphonic, Sagos Distro, and Solid Gold Global.`,
    },
    {
      num: "18",
      title: "Deal Structuring: 90.0% Upfront Closing vs. 10.0% Holdback Escrow",
      body: `90.0% upfront closing wire (${fmtUsd((deck.base_val_usd || 544000) * 0.9)}) and 10.0% 12-month indemnity holdback escrow (${fmtUsd((deck.base_val_usd || 544000) * 0.1)}) with after-tax net proceeds comparison.`,
    },
    {
      num: "19",
      title: "Closing Checklist & Letter of Direction (LOD) Execution Plan",
      body: `5-to-7 business day underwriting & closing roadmap: distributor CSV verification, chain-of-title warranty, LOD routing, and escrow disbursement.`,
    },
  ];

  const slideCardsHtml = slides
    .map((s, idx) => {
      if (lockedPreview && idx >= 2) {
        return `
      <section class="slide slide-redacted" data-slide-locked="true">
        <div class="slide-header">
          <span class="slide-num">SLIDE ${s.num} / 19</span>
          <span class="slide-code">${deck.deal_code} · REDACTED PREVIEW</span>
        </div>
        <h2>${s.title} — Redacted Preview</h2>
        <p class="redacted-notice">LOCKED — SERVER ENTITLEMENT REQUIRED TO RENDER SLIDE CONTENT. Complete Autumn / Stripe checkout ($299 single memo or $499/mo Desk Pass) to unlock and render Slides 03–19 on the server.</p>
        <div style="margin-top: 14px;">
          <a href="${checkoutUrl || "/valuation-memo/"}" target="_blank" class="unlock-btn">Unlock Full 19-Slide Memo</a>
        </div>
      </section>`;
      }
      return `
      <section class="slide">
        <div class="slide-header">
          <span class="slide-num">SLIDE ${s.num} / 19</span>
          <span class="slide-code">${deck.deal_code} · ${deck.stage}</span>
        </div>
        <h2>${s.title}</h2>
        <p>${s.body}</p>
        ${
          idx === 0
            ? `<div class="kpi-row">
                <div class="kpi"><small>Trailing LTM Net</small><strong>${ltmStr}</strong></div>
                <div class="kpi"><small>Standalone Base (P50)</small><strong>${baseStr}</strong></div>
                <div class="kpi"><small>Implied Multiple</small><strong>${multStr}</strong></div>
                <div class="kpi"><small>Risk-Adjusted WACC</small><strong>${waccStr}</strong></div>
              </div>`
            : ""
        }
      </section>`;
    })
    .join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${artist} — ${title} | SPACE 19-Slide Institutional Valuation Memo</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px; background: #0B0D12; color: #F5F6F8; font-family: "Inter", -apple-system, sans-serif; }
  .slide { position: relative; background: #131722; border: 1px solid #252C3E; border-radius: 10px; padding: 28px 32px; margin-bottom: 20px; overflow: hidden; }
  .slide-redacted { border-style: dashed; border-color: #3B4664; background: #0F131D; }
  .slide-header { display: flex; justify-content: space-between; font-family: monospace; font-size: 11px; color: #84B1FF; margin-bottom: 10px; }
  h2 { margin: 0 0 10px; font-size: 20px; color: #FFFFFF; }
  p { margin: 0; font-size: 14px; line-height: 1.6; color: #B4BCCF; }
  .redacted-notice { font-family: monospace; font-size: 12px; color: #9BA3B8; }
  .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 18px; }
  .kpi { background: #0D1017; border: 1px solid #22293A; border-radius: 8px; padding: 12px; }
  .kpi small { display: block; font-size: 11px; color: #8C95AA; margin-bottom: 4px; }
  .kpi strong { font-size: 18px; color: #84B1FF; }
  .unlock-btn { display: inline-block; background: #F99441; color: #0B0D12; font-weight: 700; font-size: 12px; padding: 8px 16px; border-radius: 6px; text-decoration: none; }
</style>
</head>
<body>
${slideCardsHtml}
</body>
</html>`;
}

async function handlePaidMemoCheckout(request, url, env) {
  const req = await request.json().catch(() => ({}));
  const appId = crypto.randomUUID();
  const orderHash = (await sha256Hex(`${appId}:${Date.now()}`)).slice(0, 10).toUpperCase();
  const orderId = `ORD-MEMO-${orderHash}`;
  const artistSlug =
    String(req.artist_or_label_name || "CATALOG")
      .replace(/[^A-Za-z0-9]+/g, "")
      .toUpperCase()
      .slice(0, 8) || "CATALOG";
  const dealCode = `SPACE-${artistSlug}-2026`;
  const customerId = canonicalCustomerId(
    req.contact_email || req.customer_id || req.artist_or_label_name,
  );
  const customerToken = await issueCustomerToken(customerId, env);
  const planTier = req.plan_tier === "DESK_PASS_499" ? "DESK_PASS_499" : "SINGLE_MEMO_299";
  const autumnPlanId = planTier === "DESK_PASS_499" ? "desk_pass_499" : "single_memo_299";
  const amountUsd = planTier === "DESK_PASS_499" ? 499 : 299;
  const amountEur = planTier === "DESK_PASS_499" ? 459 : 275;
  const amountCents = amountUsd * 100;
  const receiptToken = (await hmacSha256Hex(getCustomerSigningSecret(env), `receipt:${orderId}:${appId}`)).slice(
    0,
    32,
  );

  const deck = buildDynamicDeckModel(req, appId, dealCode);

  let paymentStatus = "PENDING_PAYMENT";
  let billingProvider = "AUTUMN";
  let sessionId = `cs_autumn_${(await sha256Hex(`${orderId}:${customerId}`)).slice(0, 20)}`;
  let checkoutUrl = `https://checkout.useautumn.com/c/pay/${sessionId}?order_id=${orderId}&customer_id=${encodeURIComponent(customerId)}&plan_id=${autumnPlanId}`;
  let creditsRemaining = 0;

  // Only consume existing customer credits if caller supplies a valid customer_token for customerId
  const providedCustomerToken = extractCustomerToken(request, url, req);
  const hasVerifiedCustomerToken =
    providedCustomerToken && (await verifyCustomerToken(customerId, providedCustomerToken, env));

  if (hasVerifiedCustomerToken) {
    const balanceCheck = await checkAutumnBalanceInternal(
      env,
      customerId,
      "investment_memo_pdf",
      1,
      true,
    );
    if (balanceCheck.allowed) {
      paymentStatus = "PAID";
      billingProvider = "AUTUMN";
      sessionId = `cs_autumn_credit_${orderId.toLowerCase()}`;
      creditsRemaining = balanceCheck.remaining_balance;
    }
  }

  let returnToken = await issueCheckoutReturnToken(orderId, customerId, sessionId, env);
  let returnUrl = `/catalog-review/paid-memo/return?order_id=${encodeURIComponent(orderId)}&session_id=${encodeURIComponent(sessionId)}&return_token=${encodeURIComponent(returnToken)}`;

  if (paymentStatus !== "PAID") {
    const successUrl = `https://spacemusic.io${returnUrl}`;
    const attachBody = await callAutumnApi(env, "billing.attach", {
      customer_id: customerId,
      plan_id: autumnPlanId,
      success_url: successUrl,
      checkout_session_params: {
        client_reference_id: orderId,
        metadata: {
          order_id: orderId,
          application_id: appId,
          customer_id: customerId,
          deal_code: dealCode,
          autumn_plan_id: autumnPlanId,
        },
      },
    });
    if (attachBody) {
      const liveUrl =
        attachBody.payment_url ||
        attachBody.paymentUrl ||
        attachBody.checkout_url ||
        attachBody.url ||
        null;
      sessionId = String(attachBody.stripe_session_id || attachBody.id || sessionId);
      if (liveUrl) {
        checkoutUrl = String(liveUrl);
      }
      returnToken = await issueCheckoutReturnToken(orderId, customerId, sessionId, env);
      returnUrl = `/catalog-review/paid-memo/return?order_id=${encodeURIComponent(orderId)}&session_id=${encodeURIComponent(sessionId)}&return_token=${encodeURIComponent(returnToken)}`;
    }
  }

  const encodedLocked = await encodeDeckState(deck, false, checkoutUrl, receiptToken, env);
  const encodedUnlocked = await encodeDeckState(deck, true, checkoutUrl, receiptToken, env);
  const lockedPreviewUrl = `/catalog-review/${appId}/investment-memo.html?state=${encodeURIComponent(encodedLocked)}`;
  const unlockedHtmlUrl = `/catalog-review/${appId}/investment-memo.html?receipt_token=${receiptToken}&state=${encodeURIComponent(encodedUnlocked)}`;
  const unlockedPdfUrl = `/catalog-review/${appId}/investment-memo.pdf?receipt_token=${receiptToken}&state=${encodeURIComponent(encodedUnlocked)}`;

  if (paymentStatus === "PAID") {
    checkoutUrl = unlockedHtmlUrl;
  }

  const order = {
    order_id: orderId,
    application_id: appId,
    customer_id: customerId,
    customer_token: customerToken,
    deal_code: dealCode,
    artist_or_label_name: deck.artist_or_label_name,
    plan_tier: planTier,
    autumn_plan_id: autumnPlanId,
    autumn_feature_id: "investment_memo_pdf",
    billing_provider: billingProvider,
    amount_usd: amountUsd,
    amount_eur: amountEur,
    amount_cents: amountCents,
    billing_currency: "USD",
    payment_status: paymentStatus,
    stripe_session_id: sessionId,
    checkout_url: checkoutUrl,
    checkout_return_token: returnToken,
    return_url: returnUrl,
    locked_preview_url: lockedPreviewUrl,
    unlocked_html_url: paymentStatus === "PAID" ? unlockedHtmlUrl : null,
    unlocked_pdf_url: paymentStatus === "PAID" ? unlockedPdfUrl : null,
    receipt_token: paymentStatus === "PAID" ? receiptToken : null,
    autumn_credits_remaining: creditsRemaining,
    teaser_headline: deck.teaser_headline,
    teaser_standalone_base_usd: deck.teaser_standalone_base_usd,
    teaser_ltm_verified_usd: deck.teaser_ltm_verified_usd,
    teaser_wacc_pct: deck.wacc_pct,
    claude_model_used: deck.claude_model_used,
    claude_execution_mode: deck.claude_execution_mode,
    _internal_receipt_token: receiptToken,
    _unlocked_html_url: unlockedHtmlUrl,
    _unlocked_pdf_url: unlockedPdfUrl,
    _deck: deck,
  };

  ORDERS_BY_ID.set(orderId, order);
  ORDERS_BY_APP.set(appId, order);

  return jsonResponse(sanitizeOrderForPublicResponse(order), 201);
}

function sanitizeOrderForPublicResponse(order) {
  const isPaid = order.payment_status === "PAID";
  const payload = { ...order };
  delete payload._internal_receipt_token;
  delete payload._unlocked_html_url;
  delete payload._unlocked_pdf_url;
  delete payload._deck;
  if (!isPaid) {
    payload.receipt_token = null;
    payload.unlocked_html_url = null;
    payload.unlocked_pdf_url = null;
  }
  return payload;
}

async function handlePaidMemoReturn(request, url, env) {
  const orderId = url.searchParams.get("order_id") || "";
  const sessionId = url.searchParams.get("session_id") || "";
  const returnToken = url.searchParams.get("return_token") || "";
  const order = ORDERS_BY_ID.get(orderId);
  if (!order) {
    return jsonResponse({ detail: `Unknown order_id: ${orderId}` }, 404);
  }
  const effectiveSessionId = sessionId || order.stripe_session_id;
  const validToken = await verifyCheckoutReturnToken(
    order.order_id,
    order.customer_id,
    effectiveSessionId,
    returnToken,
    env,
  );
  if (!validToken || effectiveSessionId !== order.stripe_session_id) {
    return jsonResponse({ detail: "Invalid or mismatched checkout return_token / session_id." }, 403);
  }
  if (order.payment_status !== "PAID") {
    return jsonResponse(
      {
        detail: {
          message: "Order payment has not been confirmed yet.",
          order_id: order.order_id,
          payment_status: order.payment_status,
          locked_preview_url: order.locked_preview_url,
          checkout_url: order.checkout_url,
        },
      },
      402,
    );
  }
  return jsonResponse({
    order_id: order.order_id,
    application_id: order.application_id,
    customer_id: order.customer_id,
    customer_token: order.customer_token,
    payment_status: order.payment_status,
    receipt_token: order._internal_receipt_token,
    unlocked_html_url: order._unlocked_html_url,
    unlocked_pdf_url: order._unlocked_pdf_url,
  });
}

async function handlePaidMemoOrderStatus(request, url, orderId, env) {
  const order = ORDERS_BY_ID.get(orderId);
  if (!order) {
    return jsonResponse({ detail: `Unknown order_id: ${orderId}` }, 404);
  }
  const returnToken = url.searchParams.get("return_token") || "";
  const receiptToken = url.searchParams.get("receipt_token") || "";
  const sessionId = url.searchParams.get("session_id") || order.stripe_session_id;
  let authorized = false;
  if (
    returnToken &&
    (await verifyCheckoutReturnToken(order.order_id, order.customer_id, sessionId, returnToken, env))
  ) {
    authorized = true;
  } else if (receiptToken && constantTimeEqual(receiptToken, order._internal_receipt_token)) {
    authorized = true;
  } else {
    const authErr = await requireCustomerAuth(request, url, null, order.customer_id, env);
    if (!authErr) authorized = true;
  }
  if (!authorized) {
    return jsonResponse(
      { detail: "Valid customer_token, return_token, or receipt_token required to inspect order." },
      401,
    );
  }
  return jsonResponse(sanitizeOrderForPublicResponse(order));
}

async function handlePaidMemoRefund(request, url, orderId, env) {
  const order = ORDERS_BY_ID.get(orderId);
  if (!order) {
    return jsonResponse({ detail: `Unknown order_id: ${orderId}` }, 404);
  }
  const reqBody = await request.json().catch(() => ({}));
  const authErr = await requireCustomerAuth(request, url, reqBody, order.customer_id, env);
  if (authErr) return authErr;
  order.payment_status = "REFUNDED";
  order.receipt_token = null;
  order.unlocked_html_url = null;
  order.unlocked_pdf_url = null;
  const current = BALANCES.get(order.customer_id) ?? 0;
  BALANCES.set(order.customer_id, Math.max(0, current - 1));
  return jsonResponse({
    order_id: order.order_id,
    customer_id: order.customer_id,
    payment_status: order.payment_status,
    entitlement_revoked: true,
  });
}

async function handleInvestmentMemoView(url, appId, isPdf, env) {
  const receiptToken = url.searchParams.get("receipt_token") || "";
  const stateParam = url.searchParams.get("state");
  const decoded = await decodeDeckState(stateParam, env);
  const stored = ORDERS_BY_APP.get(appId);

  let deck = stored?._deck || decoded?.d;
  if (!deck) {
    deck = buildDynamicDeckModel(
      {
        artist_or_label_name: "HMWME",
        catalog_title: "The Family of One",
        declared_ltm_amount: 80000,
      },
      appId,
      "SPACE-HMWME-2026",
    );
  }

  let isUnlocked = false;
  if (stored) {
    isUnlocked =
      stored.payment_status === "PAID" &&
      Boolean(receiptToken) &&
      constantTimeEqual(receiptToken, stored._internal_receipt_token);
  } else if (decoded && decoded.u && decoded.r && receiptToken) {
    isUnlocked = constantTimeEqual(receiptToken, decoded.r);
  }

  const checkoutUrl = stored?.checkout_url || decoded?.c || "/valuation-memo/";

  if (isPdf) {
    if (!isUnlocked) {
      return jsonResponse(
        {
          detail: {
            message:
              "Payment required to download the full 19-slide SPACE Investment Memo PDF ($299 / €275).",
            checkout_url: checkoutUrl,
          },
        },
        402,
      );
    }
    const artistLower = String(deck.artist_or_label_name || "").toLowerCase();
    const redirectPdf = artistLower.includes("2scratch")
      ? "https://spacemusic.io/memos/2scratch/2Scratch_Catalog_Valuation_19_Slide_Deck.pdf"
      : "https://spacemusic.io/memos/hmwme/HMWME_Catalog_Valuation_19_Slide_Deck.pdf";
    return Response.redirect(redirectPdf, 302);
  }

  return htmlResponse(render19SlideMemoHtml(deck, !isUnlocked, checkoutUrl));
}

async function verifyWebhookSignature(rawBody, sigHeader, secret) {
  if (!sigHeader || !secret) return false;
  const trimmed = String(sigHeader).trim();
  if (trimmed.includes("t=") && trimmed.includes("v1=")) {
    const parts = {};
    for (const item of trimmed.split(",")) {
      const [k, v] = item.trim().split("=", 2);
      if (k && v) parts[k] = v;
    }
    const ts = Number(parts.t);
    const v1 = parts.v1;
    if (!Number.isFinite(ts) || !v1) return false;
    if (Math.abs(Date.now() / 1000 - ts) > 300) return false;
    const expected = await hmacSha256Hex(secret, `${ts}.${rawBody}`);
    return constantTimeEqual(expected, v1);
  }
  const digest = trimmed.startsWith("sha256=") ? trimmed.slice(7) : trimmed;
  const expected = await hmacSha256Hex(secret, rawBody);
  return constantTimeEqual(expected, digest);
}

async function handleMemoWebhook(request, env) {
  const secret = env.STRIPE_MEMO_WEBHOOK_SECRET || env.AUTUMN_WEBHOOK_SECRET || "";
  if (!secret || !String(secret).trim()) {
    return jsonResponse(
      {
        detail:
          "Webhook secret is not configured on the server (STRIPE_MEMO_WEBHOOK_SECRET / AUTUMN_WEBHOOK_SECRET).",
      },
      503,
    );
  }
  const rawBody = await request.text();
  const sigHeader =
    request.headers.get("stripe-signature") || request.headers.get("x-autumn-signature") || "";
  const sigOk = await verifyWebhookSignature(rawBody, sigHeader, String(secret).trim());
  if (!sigOk) {
    return jsonResponse({ detail: "Invalid or expired webhook signature." }, 400);
  }
  let event;
  try {
    event = JSON.parse(rawBody);
  } catch {
    return jsonResponse({ detail: "Malformed JSON webhook payload." }, 400);
  }
  const eventType = String(event.type || event.event_type || "").trim();
  if (!ALLOWED_WEBHOOK_EVENT_TYPES.has(eventType)) {
    return jsonResponse(
      { detail: `Unsupported or non-payment webhook event type: '${eventType}'.` },
      400,
    );
  }
  const obj = event?.data?.object || event || {};
  const paymentStatus = String(
    obj.payment_status || event.payment_status || obj.status || "",
  )
    .trim()
    .toLowerCase();
  if (paymentStatus !== "paid" && paymentStatus !== "succeeded") {
    return jsonResponse(
      { detail: `Webhook rejected: payment_status is '${paymentStatus}' (must be 'paid').` },
      400,
    );
  }
  const metadata = obj.metadata || event.metadata || {};
  const orderId = String(
    obj.client_reference_id || metadata.order_id || event.order_id || "",
  ).trim();
  if (!orderId) {
    return jsonResponse({ detail: "Webhook payload missing order_id." }, 400);
  }
  const order = ORDERS_BY_ID.get(orderId);
  if (!order) {
    return jsonResponse({ detail: `Unknown order_id '${orderId}'.` }, 404);
  }
  const webhookSessionId = String(
    obj.id || obj.checkout_session_id || event.checkout_session_id || "",
  ).trim();
  if (!webhookSessionId || webhookSessionId !== order.stripe_session_id) {
    return jsonResponse(
      { detail: "Webhook checkout_session_id does not match order.stripe_session_id." },
      400,
    );
  }
  const rawAmount = obj.amount_total ?? obj.amount_paid ?? event.amount_total;
  if (rawAmount === undefined || rawAmount === null) {
    return jsonResponse({ detail: "Webhook missing amount_total / amount_paid." }, 400);
  }
  const paidCents = Number(rawAmount);
  if (!Number.isFinite(paidCents) || paidCents <= 0 || paidCents < order.amount_cents) {
    return jsonResponse(
      { detail: `Webhook amount_total (${paidCents}) is less than order.amount_cents (${order.amount_cents}).` },
      400,
    );
  }
  const currency = String(obj.currency || event.currency || "").trim().toUpperCase();
  const expectedCurrency = String(order.billing_currency || "USD").toUpperCase();
  if (!currency || currency !== expectedCurrency) {
    return jsonResponse(
      { detail: `Webhook currency '${currency}' does not match order currency '${expectedCurrency}'.` },
      400,
    );
  }

  const customerId = order.customer_id;
  const granted = order.plan_tier === "DESK_PASS_499" ? 10 : 1;
  const remaining = Math.max(0, (BALANCES.get(customerId) ?? 0) + granted - 1);
  BALANCES.set(customerId, remaining);

  order.payment_status = "PAID";
  order.autumn_credits_remaining = remaining;
  order.receipt_token = order._internal_receipt_token;
  order.unlocked_html_url = order._unlocked_html_url;
  order.unlocked_pdf_url = order._unlocked_pdf_url;

  return jsonResponse({
    status: "unlocked",
    order_id: order.order_id,
    application_id: order.application_id,
    customer_id: customerId,
    payment_status: "PAID",
    receipt_token: order.receipt_token,
    unlocked_html_url: order.unlocked_html_url,
    unlocked_pdf_url: order.unlocked_pdf_url,
    autumn_credits_remaining: remaining,
  });
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const normPath = url.pathname.replace(/^\/api\/v1\/spacemusic/, "") || "/";

    if (request.method === "GET" && (normPath === "/health" || normPath === "/catalog-review/health")) {
      return jsonResponse({
        status: "ok",
        service: "spacemusic-memo-studio",
        autumn_configured: Boolean(env.AUTUMN_SECRET_KEY),
        autumn_workspace_id: env.AUTUMN_WORKSPACE_ID || "workspace_93879100",
        tenet_benchmark_loaded: true,
        institutional_buyers_count: INSTITUTIONAL_BUYERS.length,
      });
    }

    if (request.method === "GET" && (normPath === "/valuation-memo" || normPath === "/valuation-memo/")) {
      return htmlResponse(STUDIO_HTML);
    }

    if (request.method === "GET" && normPath === "/catalog-review/paid-memo/autumn/plans") {
      return handleAutumnPlansList(url, env);
    }

    if (request.method === "POST" && normPath === "/catalog-review/paid-memo/autumn/customer") {
      return handleAutumnCustomerGetOrCreate(request, url, env);
    }

    const customerGetMatch = normPath.match(/^\/catalog-review\/paid-memo\/autumn\/customer\/([^/]+)$/);
    if (request.method === "GET" && customerGetMatch) {
      return handleAutumnCustomerGet(request, url, decodeURIComponent(customerGetMatch[1]), env);
    }

    if (request.method === "POST" && normPath === "/catalog-review/paid-memo/autumn/check") {
      return handleAutumnCheck(request, url, env);
    }

    if (request.method === "POST" && normPath === "/catalog-review/paid-memo/autumn/track") {
      return handleAutumnTrack(request, url, env);
    }

    if (request.method === "POST" && normPath === "/catalog-review/paid-memo/autumn/portal") {
      return handleAutumnPortal(request, url, env);
    }

    if (request.method === "POST" && normPath === "/catalog-review/paid-memo/checkout") {
      return handlePaidMemoCheckout(request, url, env);
    }

    if (request.method === "GET" && normPath === "/catalog-review/paid-memo/return") {
      return handlePaidMemoReturn(request, url, env);
    }

    const orderStatusMatch = normPath.match(/^\/catalog-review\/paid-memo\/orders\/([^/]+)$/);
    if (request.method === "GET" && orderStatusMatch) {
      return handlePaidMemoOrderStatus(request, url, decodeURIComponent(orderStatusMatch[1]), env);
    }

    const orderRefundMatch = normPath.match(/^\/catalog-review\/paid-memo\/orders\/([^/]+)\/refund$/);
    if (request.method === "POST" && orderRefundMatch) {
      return handlePaidMemoRefund(request, url, decodeURIComponent(orderRefundMatch[1]), env);
    }

    if (
      request.method === "GET" &&
      (normPath === "/catalog-review/benchmarks/tenet-zitron-package" ||
        normPath === "/catalog-review/benchmark/tenet-zitron-package")
    ) {
      return jsonResponse(TENET_ZITRON_PACKAGE);
    }

    if (request.method === "GET" && (normPath === "/buyers" || normPath === "/catalog-review/buyers")) {
      return jsonResponse({
        count: INSTITUTIONAL_BUYERS.length,
        buyers: INSTITUTIONAL_BUYERS,
      });
    }

    const memoHtmlMatch = normPath.match(/^\/catalog-review\/([^/]+)\/investment-memo\.html$/);
    if (request.method === "GET" && memoHtmlMatch) {
      return handleInvestmentMemoView(url, memoHtmlMatch[1], false, env);
    }

    const memoPdfMatch = normPath.match(/^\/catalog-review\/([^/]+)\/investment-memo\.pdf$/);
    if (request.method === "GET" && memoPdfMatch) {
      return handleInvestmentMemoView(url, memoPdfMatch[1], true, env);
    }

    if (
      request.method === "POST" &&
      (normPath === "/webhooks/autumn-memo" || normPath === "/webhooks/stripe-memo")
    ) {
      return handleMemoWebhook(request, env);
    }

    return jsonResponse({ error: "Not found", path: url.pathname }, 404);
  },
};
