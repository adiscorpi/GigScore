import { useState, useEffect, useRef } from "react";
import Agent5CreditStory from "./Agent5CreditStory.jsx";

const GIGSCORE_LOGO_DARK = "/assets/logo-dark.png";
const GIGSCORE_LOGO_LIGHT = "/assets/logogig-white.png";
const BARCLAYS_LOGO = "/assets/barclays-logo-trimmed.png";
const BODY_FONT = "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif";
const HEADING_FONT = "'Francy', Georgia, serif";
const HEADING_TRACKING = "2px";

const NAVY        = "#083B59";
const NAVY_DARK   = "#062E45";
const NAVY_SOFT   = "#0B4F74";
const BLUE        = "#00AEEF";
const BLUE_BG     = "#D9F3FB";
const PAGE_BG     = "#EAF4F8";
const PAGE_BG_ALT = "#DCECF4";
const PANEL       = "#FFFFFF";
const PANEL_ALT   = "#F4FAFD";
const PANEL_LINE  = "#BFD7E4";
const TEXT        = "#0A3046";
const TEXT_MUTED  = "#58798D";
const TEXT_FAINT  = "#88A8BA";
const TEXT_ON_DARK = "#F6FBFE";
const MUTED_ON_DARK = "#A5C8D8";
const RED         = "#C65B56";
const RED_BG      = "#FBE5E2";
const GREEN       = "#187E70";
const GREEN_BG    = "#D9F1EC";
const AMBER       = "#B6781D";
const AMBER_BG    = "#FFF1D8";
const PANEL_SHADOW = "0 20px 50px rgba(6, 46, 69, 0.08)";

const PERSONAS = {
  raju: {
    id: "raju", appNo: "GS-2026-00847",
    name: "Raju Sharma", role: "Delivery Partner", platform: "Swiggy",
    city: "Mumbai, Tier 1", since: "March 2019", income: 53552,
    loanType: "Vehicle Loan", loanAmount: 45000, tenure: 18,
    purpose: "Honda Activa 6G for delivery operations",
    note: "Sub-Prime candidate with strong behavioral signals",
    scores: { base: 53.3, trust: 81.2, adj3: 3, behavioral: 3, mult: 0.97, final: 60.2 },
    decision: { tier: "Sub-Prime", label: "CONDITIONAL APPROVAL", prob: 32.8, thin: true },
    signals: {
      pos: [
        { name: "Utility payment streak", val: "18 months", sub: "Perfect consecutive record, strongest creditworthiness signal" },
        { name: "Obligation fulfillment",  val: "100%",      sub: "All fixed obligations met every month in the assessment period" },
        { name: "Social trust score",      val: "81.2 / 100",sub: "43 unique VPA counterparties, embedded community payment network" },
      ],
      neg: [
        { name: "No bureau history",      val: "Thin file",  sub: "No formal CIBIL score, assessed entirely on behavioral signals" },
        { name: "Inflow / outflow ratio", val: "0.86",       sub: "Marginal net outflow on current CSV, resolves to 1.72 with corrected parser" },
        { name: "Credit annuity ratio",   val: "12.0",       sub: "Above cohort benchmark, flagged for monitoring" },
      ],
    },
    loan: { amount: 45000, rate: 17.0, tenure: 18, emi: 2850, foir: 10.7, saved: 4328, fee: 1125, total: 51300 },
  },
  anita: {
    id: "anita", appNo: "GS-2026-01203",
    name: "Anita Kumari", role: "Home Services Worker", platform: "Urban Company",
    city: "Delhi, Tier 1", since: "August 2020", income: 11671,
    loanType: "Personal Loan", loanAmount: 15000, tenure: 12,
    purpose: "Working capital for beauty services equipment",
    note: "High-risk profile with two confirmed red flags",
    scores: { base: 65.2, trust: 58.4, adj3: 0, behavioral: 0, mult: 0.98, final: 57.8 },
    decision: { tier: "Sub-Prime", label: "CONDITIONAL APPROVAL", prob: 24.5, thin: true },
    signals: {
      pos: [
        { name: "Obligation fulfillment", val: "100%",      sub: "All fixed obligations met consistently across the assessment window" },
        { name: "Payment success rate",   val: "100%",      sub: "Zero failed UPI payments, strong payment infrastructure usage" },
        { name: "Merchant diversity",     val: "0.64",      sub: "Moderate spending diversification across household categories" },
      ],
      neg: [
        { name: "Gambling transactions",  val: "Confirmed", sub: "Dream11 and MPL transactions detected, confirmed red flag" },
        { name: "Net outflow detected",   val: "IOR 0.35",  sub: "Spending significantly exceeds income in the period" },
        { name: "Low monthly income",     val: "Rs 11,671", sub: "Below PLFS benchmark for Urban Company workers in Delhi" },
      ],
    },
    loan: { amount: 15000, rate: 22.0, tenure: 12, emi: 1402, foir: 12.0, saved: 980, fee: 375, total: 16824 },
  },
  deepak: {
    id: "deepak", appNo: "GS-2026-02891",
    name: "Deepak Verma", role: "Delivery and Logistics", platform: "Swiggy / Zomato",
    city: "Bengaluru, Tier 1", since: "January 2019", income: 26667,
    loanType: "Vehicle Loan", loanAmount: 40000, tenure: 24,
    purpose: "Electric two-wheeler upgrade for delivery efficiency",
    note: "Near-Prime candidate with strong platform tenure",
    scores: { base: 71.3, trust: 72.8, adj3: 3, behavioral: 2, mult: 0.98, final: 68.4 },
    decision: { tier: "Near-Prime", label: "APPROVED", prob: 19.8, thin: false },
    signals: {
      pos: [
        { name: "Platform tenure",        val: "6+ years",  sub: "Consistent multi-platform income since January 2019" },
        { name: "Social trust score",     val: "72.8 / 100",sub: "Stable payment network with consistent counterparties" },
        { name: "Merchant diversity",     val: "0.72",      sub: "High spending diversification, stable lifestyle signal" },
      ],
      neg: [
        { name: "Gambling transactions",  val: "Confirmed", sub: "MPL transactions detected in statement, confirmed flag" },
        { name: "Net outflow detected",   val: "IOR 0.74",  sub: "Slightly below breakeven, manageable with income trajectory" },
        { name: "Bureau history",         val: "Thin file", sub: "Limited bureau data, decision weighted toward behavioral signals" },
      ],
    },
    loan: { amount: 40000, rate: 15.0, tenure: 24, emi: 1940, foir: 7.3, saved: 6200, fee: 1000, total: 46560 },
  },
};

const APP_NO_MAP = {
  "GS-2026-00847": "raju",
  "GS-2026-01203": "anita",
  "GS-2026-02891": "deepak",
};

const AGENTS = [
  { name: "Application Parser",     sub: "Loan form PDF parsed, personal and loan details extracted",       fn: (p) => `${p.name} · ${p.loanType} · Rs ${fmt(p.loanAmount)}` },
  { name: "Statement Analysis",     sub: "Agent 0: 151 pages, PII redaction, MCC categorisation",          fn: () => "7,358 transactions · 83 features extracted" },
  { name: "Feature Engineering",    sub: "Agent 1: cohort median imputation, income signal features",      fn: () => "80+ features · training_medians.json applied" },
  { name: "XGBoost Scoring",        sub: "Agent 2: Optuna 60-trial tuning + SHAP per-applicant",           fn: (p) => `default_prob = ${(p.decision.prob/100).toFixed(3)} · raw_gigscore = ${p.scores.base}` },
  { name: "Social Trust Graph",     sub: "Agent 3: 3-group behavioral score vs cohort baseline",           fn: (p) => `trust = ${p.scores.trust} · adj = +${p.scores.adj3} · zone = CLEAR` },
  { name: "GigScore Formula",       sub: "Agent 4: 3-layer blend + income multiplier + explanation",       fn: (p) => `final = ${p.scores.final} · ${p.decision.tier} · ${p.decision.label}` },
  { name: "Loan Structuring",       sub: "Agent 6: FOIR check + band lookup + EMI + market comparison",    fn: (p) => `Rs ${fmt(p.loan.amount)} @ ${p.loan.rate}% · EMI Rs ${fmt(p.loan.emi)} · FOIR ${p.loan.foir}%` },
];

function fmt(n) { return Number(n).toLocaleString("en-IN"); }
function tierColor(s) { return s >= 75 ? GREEN : s >= 60 ? NAVY : s >= 45 ? AMBER : RED; }
function tierLabel(s) { return s >= 75 ? "Prime" : s >= 60 ? "Near-Prime" : s >= 45 ? "Sub-Prime" : s >= 30 ? "High Risk" : "No Product"; }
function tierStyle(s) {
  if (s >= 75) return { bg: GREEN_BG, color: GREEN, border: "#9FDCCF" };
  if (s >= 60) return { bg: BLUE_BG, color: NAVY, border: "#96D8F3" };
  if (s >= 45) return { bg: AMBER_BG, color: AMBER, border: "#F1D08C" };
  return { bg: RED_BG, color: RED, border: "#F0B0AB" };
}

function pillStyle(bg, color, border, { padding = "4px 16px", fontSize = 12 } = {}) {
  return {
    background: bg,
    color,
    padding,
    borderRadius: 999,
    fontSize,
    fontWeight: 500,
    border: `1px solid ${border}`,
    display: "inline-block",
    maxWidth: "100%",
    lineHeight: 1.25,
    textAlign: "center",
    boxSizing: "border-box",
    whiteSpace: "normal",
    overflowWrap: "anywhere",
  };
}

function BrandLockup({
  gigHeight = 28,
  barclaysHeight = 20,
  dividerColor = "rgba(255,255,255,0.18)",
  darkSurface = false,
}) {
  const gigLogo = darkSurface ? GIGSCORE_LOGO_LIGHT : GIGSCORE_LOGO_DARK;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
      <img src={gigLogo} alt="GigScore" style={{ height: gigHeight, width: "auto", display: "block" }} />
      <div style={{ width: 1, height: Math.max(gigHeight, barclaysHeight) + 4, background: dividerColor, flexShrink: 0 }} />
      <img src={BARCLAYS_LOGO} alt="Barclays" style={{ height: barclaysHeight, width: "auto", display: "block" }} />
    </div>
  );
}

function buildSystemPrompt(p) {
  return `You are a senior credit risk officer at Barclays reviewing a GigScore AI credit assessment. Be concise, analytical, and direct. Cite specific data. No filler phrases. You are a professional reviewing a credit file.

APPLICANT: ${p.name} | App: ${p.appNo} | ${p.platform} | ${p.city} | since ${p.since}
MONTHLY INCOME: Rs ${fmt(p.income)}

GIGSCORE: ${p.scores.final} / 100 | ${p.decision.tier} | ${p.decision.label}
DEFAULT PROBABILITY: ${p.decision.prob}%
BASE SCORE: ${p.scores.base} | SOCIAL TRUST: ${p.scores.trust} | BEHAVIORAL ADJ: +${p.scores.behavioral} | AGENT 3 BONUS: +${p.scores.adj3} | MULTIPLIER: ${p.scores.mult}

POSITIVE: ${p.signals.pos.map(s => `${s.name} ${s.val}`).join("; ")}
RISK: ${p.signals.neg.map(s => `${s.name} ${s.val}`).join("; ")}

LOAN: Rs ${fmt(p.loan.amount)} ${p.loanType} @ ${p.loan.rate}% · ${p.loan.tenure}m · EMI Rs ${fmt(p.loan.emi)} · FOIR ${p.loan.foir}% vs 40% limit · saved Rs ${fmt(p.loan.saved)} vs 28% market rate

GigScore pipeline: 7 LangGraph agents, XGBoost trained on 22K+ gig workers, SHAP attribution, DPDP Act 2023 compliant, RBI Fair Practices Code aligned.`;
}

function ScoreRing({ score, size = 180, animate = false }) {
  const [disp, setDisp] = useState(animate ? 0 : score);
  useEffect(() => {
    if (!animate) { setDisp(score); return; }
    let raf, t0 = null;
    const dur = 1600;
    const tick = (ts) => {
      if (!t0) t0 = ts;
      const prog = Math.min((ts - t0) / dur, 1);
      const ease = 1 - Math.pow(1 - prog, 3);
      setDisp(parseFloat((score * ease).toFixed(1)));
      if (prog < 1) raf = requestAnimationFrame(tick);
    };
    const id = setTimeout(() => { raf = requestAnimationFrame(tick); }, 400);
    return () => { clearTimeout(id); cancelAnimationFrame(raf); };
  }, [animate, score]);
  const cx = size / 2, cy = size / 2, r = size / 2 - 16;
  const circ = 2 * Math.PI * r;
  const filled = (disp / 100) * circ;
  const col = tierColor(disp);
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ position: "absolute" }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={PANEL_LINE} strokeWidth={14} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={col} strokeWidth={14}
          strokeDasharray={`${filled} ${circ - filled}`} strokeLinecap="round"
          style={{ transform: "rotate(-90deg)", transformOrigin: "center" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontFamily: HEADING_FONT, fontSize: size * 0.21, fontWeight: 400, color: col, lineHeight: 1 }}>
          {disp.toFixed(1)}
        </span>
        <span style={{ fontSize: 11, color: TEXT_FAINT, marginTop: 2 }}>out of 100</span>
      </div>
    </div>
  );
}

function Nav({ page, onNav, persona }) {
  const tabs = [
    { id: "home",     label: "Applicants",  disabled: false },
    { id: "pipeline", label: "Pipeline",    disabled: !persona },
    { id: "results",  label: "Assessment",  disabled: !persona },
    { id: "chat",     label: "Risk Officer",disabled: !persona },
  ];
  return (
    <div style={{ background: `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 62%, ${NAVY_SOFT} 100%)`, height: 72, display: "flex", alignItems: "center",
                  padding: "0 2rem", position: "sticky", top: 0, zIndex: 100,
                  borderBottom: `1px solid rgba(255,255,255,0.12)`, boxShadow: "0 14px 40px rgba(6,46,69,0.22)" }}>
      <div style={{ marginRight: 40, flexShrink: 0 }}>
        <BrandLockup gigHeight={30} barclaysHeight={18} darkSurface />
      </div>
      <div style={{ display: "flex", flex: 1, gap: 4 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => !t.disabled && onNav(t.id)} style={{
            background: page === t.id ? "rgba(255,255,255,0.1)" : "none",
            border: "none", borderRadius: 999, cursor: t.disabled ? "default" : "pointer",
            padding: "0 18px", height: 40, alignSelf: "center",
            color: t.disabled ? "rgba(255,255,255,0.28)" : page === t.id ? "#fff" : "rgba(255,255,255,0.72)",
            fontSize: 13, fontWeight: page === t.id ? 500 : 400,
            transition: "color 0.2s, background 0.2s",
          }}>{t.label}</button>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: BLUE, boxShadow: `0 0 0 6px ${BLUE}22` }} />
        <span style={{ color: "rgba(255,255,255,0.72)", fontSize: 12 }}>System Online</span>
      </div>
    </div>
  );
}

function HomePage({ onStart, selectedId, setSelectedId }) {
  const [search,   setSearch]   = useState("");
  const [result,   setResult]   = useState(null);
  const [errMsg,   setErrMsg]   = useState("");
  const [searched, setSearched] = useState(false);

  const runSearch = () => {
    const key = search.trim().toUpperCase();
    const pid = APP_NO_MAP[key];
    setSearched(true);
    if (pid) { setResult(PERSONAS[pid]); setErrMsg(""); }
    else     { setResult(null); setErrMsg("Application not found. Sample: GS-2026-00847"); }
  };

  const loadFromSearch = (id) => {
    setSelectedId(id);
    setSearch(""); setResult(null); setSearched(false); setErrMsg("");
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "4rem 2rem 3rem" }}>
      <div style={{ marginBottom: "3rem", background: `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 64%, ${NAVY_SOFT} 100%)`,
                    borderRadius: 28, padding: "2.4rem 2.5rem", boxShadow: "0 30px 70px rgba(6,46,69,0.18)",
                    border: "1px solid rgba(255,255,255,0.08)", position: "relative", overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap", marginBottom: 18 }}>
          <BrandLockup gigHeight={36} barclaysHeight={24} darkSurface />
          <div style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase",
                        color: MUTED_ON_DARK, fontWeight: 500 }}>
            AI Credit Intelligence Platform
          </div>
        </div>
        <h1 style={{ fontFamily: HEADING_FONT, fontSize: "clamp(2rem, 4vw, 3rem)",
                     letterSpacing: HEADING_TRACKING,
                     fontWeight: 400, color: TEXT_ON_DARK, margin: "0 0 20px", lineHeight: 1.15 }}>
          Addressing India&apos;s<br />Next Lending Opportunity
        </h1>
        <p style={{ fontSize: 15, color: "rgba(246,251,254,0.84)", maxWidth: 620, lineHeight: 1.75, margin: "0 0 12px" }}>
          An explainable credit intelligence platform designed to help banks and NBFCs responsibly underwrite thin-file and gig-economy borrowers.
        </p>
        <p style={{ fontSize: 13, color: MUTED_ON_DARK, maxWidth: 560, lineHeight: 1.65, margin: 0 }}>
          While traditional credit bureaus serve a large portion of formal borrowers, millions of financially active individuals remain under-assessed by legacy models. GigScore uses consented transaction behavior to generate transparent, auditable risk indicators that fit within institutional credit processes and support scalable, compliant lending expansion.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2.5rem",
                    marginBottom: "3rem", alignItems: "start" }}>

        <div style={{ background: PANEL_ALT, border: `1px solid ${PANEL_LINE}`, borderRadius: 24,
                      padding: "1.5rem", boxShadow: PANEL_SHADOW }}>
          <div style={{ fontFamily: HEADING_FONT, fontSize: 11, fontWeight: 500, color: TEXT_MUTED, marginBottom: 10,
                        textTransform: "uppercase", letterSpacing: `calc(0.08em + ${HEADING_TRACKING})` }}>
            Search by Application Number
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <input value={search}
              onChange={e => { setSearch(e.target.value); setSearched(false); setErrMsg(""); setResult(null); }}
              onKeyDown={e => e.key === "Enter" && runSearch()}
              placeholder="GS-2026-XXXXX"
              style={{ flex: 1, border: `1.5px solid ${PANEL_LINE}`, borderRadius: 10,
                       padding: "12px 14px", fontSize: 14, outline: "none", color: TEXT,
                       background: PANEL, fontFamily: "monospace", letterSpacing: "0.03em" }} />
            <button onClick={runSearch} style={{
              background: `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 100%)`, color: "#fff", border: "none", borderRadius: 10,
              padding: "12px 20px", fontSize: 13, fontWeight: 500, cursor: "pointer",
              boxShadow: "0 10px 22px rgba(6,46,69,0.18)",
            }}>Search</button>
          </div>
          {errMsg && (
            <div style={{ fontSize: 12, color: RED, padding: "10px 12px", background: RED_BG,
                           borderRadius: 10, border: `1px solid ${tierStyle(0).border}`, marginBottom: 8 }}>
              {errMsg}
            </div>
          )}
          {result && (
            <div style={{ background: PANEL, border: `1px solid ${PANEL_LINE}`, borderRadius: 18, padding: "16px",
                          boxShadow: "0 18px 40px rgba(6,46,69,0.06)" }}>
              <div style={{ fontSize: 10, color: BLUE, fontWeight: 500, textTransform: "uppercase",
                             letterSpacing: "0.08em", marginBottom: 8 }}>Application Found</div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div>
                  <div style={{ fontWeight: 500, fontSize: 14, color: TEXT }}>{result.name}</div>
                  <div style={{ fontSize: 12, color: TEXT_MUTED }}>{result.role} · {result.platform}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontFamily: "monospace", fontSize: 11, color: TEXT_FAINT }}>{result.appNo}</div>
                  <div style={{ fontSize: 12, fontWeight: 500, color: TEXT }}>{result.loanType} · Rs {fmt(result.loanAmount)}</div>
                </div>
              </div>
              <button onClick={() => loadFromSearch(result.id)} style={{
                background: `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 100%)`, color: "#fff", border: "none", borderRadius: 10,
                padding: "10px 20px", fontSize: 13, fontWeight: 500, cursor: "pointer", width: "100%",
              }}>Load Applicant</button>
            </div>
          )}
          {!searched && (
            <div style={{ fontSize: 11, color: TEXT_FAINT, lineHeight: 1.6, marginTop: 6 }}>
              Or select from the application cards. Each represents a distinct gig work category and credit profile.
            </div>
          )}
          {searched && !result && !errMsg && (
            <div style={{ fontSize: 11, color: TEXT_FAINT, marginTop: 4 }}>
              Sample numbers: GS-2026-00847 · GS-2026-01203 · GS-2026-02891
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10, background: PANEL_ALT,
                      border: `1px solid ${PANEL_LINE}`, borderRadius: 24, padding: "1.5rem", boxShadow: PANEL_SHADOW }}>
          <div style={{ fontFamily: HEADING_FONT, fontSize: 11, fontWeight: 500, color: TEXT_MUTED, marginBottom: 2,
                        textTransform: "uppercase", letterSpacing: `calc(0.08em + ${HEADING_TRACKING})` }}>Active Applications</div>
          {Object.values(PERSONAS).map(p => {
            const ts = tierStyle(p.scores.final);
            const sel = selectedId === p.id;
            return (
              <div key={p.id} onClick={() => setSelectedId(p.id)} style={{
                background: sel ? BLUE_BG : PANEL, borderRadius: 18, padding: "14px 16px", cursor: "pointer",
                border: `1.5px solid ${sel ? BLUE : PANEL_LINE}`,
                boxShadow: sel ? `0 0 0 4px ${BLUE}18` : "none",
                transition: "border-color 0.18s, box-shadow 0.18s",
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 38, height: 38, borderRadius: "50%", flexShrink: 0,
                                 background: sel ? NAVY : PAGE_BG,
                                 display: "flex", alignItems: "center", justifyContent: "center",
                                 fontSize: 13, fontWeight: 500, color: sel ? "#fff" : TEXT_MUTED,
                                 transition: "background 0.18s, color 0.18s" }}>
                    {p.name.split(" ").map(w => w[0]).join("")}
                  </div>
                  <div>
                    <div style={{ fontWeight: 500, fontSize: 14, color: TEXT }}>{p.name}</div>
                    <div style={{ fontSize: 12, color: TEXT_MUTED }}>{p.role} · {p.platform}</div>
                    <div style={{ fontFamily: "monospace", fontSize: 11, color: TEXT_FAINT, marginTop: 1 }}>{p.appNo}</div>
                  </div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ fontFamily: HEADING_FONT, fontSize: 22, color: tierColor(p.scores.final), fontWeight: 400 }}>
                    {p.scores.final}
                  </div>
                  <span style={pillStyle(ts.bg, ts.color, ts.border, { padding: "3px 10px", fontSize: 11 })}>
                    {tierLabel(p.scores.final)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: "4rem" }}>
        <button onClick={onStart} disabled={!selectedId} style={{
          background: selectedId ? `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 100%)` : TEXT_FAINT, color: "#fff", border: "none",
          borderRadius: 12, padding: "12px 32px", fontSize: 14, fontWeight: 500,
          cursor: selectedId ? "pointer" : "not-allowed", transition: "background 0.2s",
          boxShadow: selectedId ? "0 12px 26px rgba(6,46,69,0.18)" : "none",
        }}>
          Run GigScore Assessment
        </button>
        <span style={{ fontSize: 13, color: TEXT_FAINT }}>
          {selectedId ? `Selected: ${PERSONAS[selectedId].name} · ${PERSONAS[selectedId].appNo}` : "Select an applicant to continue"}
        </span>
      </div>

    </div>
  );
}

function PipelinePage({ persona, onDone }) {
  const [step, setStep] = useState(-1);
  const [done, setDone] = useState([]);
  useEffect(() => {
    const timers = [];
    let delay = 500;
    AGENTS.forEach((_, i) => {
      timers.push(setTimeout(() => setStep(i), delay));
      timers.push(setTimeout(() => { setDone(d => [...d, i]); setStep(-1); }, delay + 680));
      delay += 880;
    });
    timers.push(setTimeout(onDone, delay + 300));
    return () => timers.forEach(clearTimeout);
  }, []);

  const progress = done.length / AGENTS.length;
  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "3rem 2rem" }}>
      <div style={{ marginBottom: "2.5rem", background: `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 64%, ${NAVY_SOFT} 100%)`,
                    borderRadius: 24, padding: "1.8rem 1.9rem", boxShadow: "0 28px 60px rgba(6,46,69,0.16)" }}>
        <div style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase",
                      color: BLUE, marginBottom: 10, fontWeight: 500 }}>
          LangGraph Pipeline · {persona.appNo}
        </div>
        <h2 style={{ fontFamily: HEADING_FONT, fontSize: 26, letterSpacing: HEADING_TRACKING, fontWeight: 400, color: TEXT_ON_DARK, margin: "0 0 6px" }}>
          Assessing {persona.name}
        </h2>
        <p style={{ fontSize: 13, color: MUTED_ON_DARK, margin: "0 0 20px" }}>
          {persona.role} · {persona.platform} · {persona.city}
        </p>
        <div style={{ background: "rgba(255,255,255,0.14)", borderRadius: 999, height: 6, overflow: "hidden" }}>
          <div style={{ height: "100%", background: BLUE, width: `${progress * 100}%`,
                         transition: "width 0.5s ease", borderRadius: 4 }} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8,
                      fontSize: 12, color: MUTED_ON_DARK }}>
          <span>{done.length} of {AGENTS.length} agents complete</span>
          <span>{Math.round(progress * 100)}%</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", background: PANEL_ALT, border: `1px solid ${PANEL_LINE}`,
                    borderRadius: 24, padding: "1.5rem 1.25rem", boxShadow: PANEL_SHADOW }}>
        {AGENTS.map((a, i) => {
          const isDone = done.includes(i), isRunning = step === i, isPending = !isDone && !isRunning;
          return (
            <div key={i} style={{ display: "flex" }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 40 }}>
                <div style={{ width: 30, height: 30, borderRadius: "50%", flexShrink: 0,
                               display: "flex", alignItems: "center", justifyContent: "center",
                               background: isDone ? NAVY : isRunning ? BLUE : PAGE_BG,
                               border: `2px solid ${isDone ? NAVY : isRunning ? BLUE : PANEL_LINE}`,
                               fontSize: 12, fontWeight: 500,
                               color: (isDone || isRunning) ? "#fff" : TEXT_FAINT,
                               transition: "background 0.3s, border-color 0.3s" }}>
                  {isDone ? "+" : isRunning ? (
                    <div style={{ width: 9, height: 9, borderRadius: "50%",
                                   border: "1.5px solid rgba(255,255,255,0.3)",
                                   borderTopColor: "#fff", animation: "spin 0.8s linear infinite" }} />
                  ) : i + 1}
                </div>
                {i < AGENTS.length - 1 && (
                  <div style={{ width: 2, flex: 1, minHeight: 20,
                                 background: isDone ? NAVY : PANEL_LINE, transition: "background 0.3s" }} />
                )}
              </div>
              <div style={{ flex: 1, paddingLeft: 16, paddingBottom: i < AGENTS.length - 1 ? 20 : 0,
                             paddingTop: 4, opacity: isPending ? 0.32 : 1, transition: "opacity 0.3s" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                  <span style={{ fontWeight: 500, fontSize: 14, color: TEXT }}>{a.name}</span>
                  {isRunning && <span style={{ fontSize: 10, background: `${BLUE}18`, color: BLUE,
                                               padding: "2px 8px", borderRadius: 999, fontWeight: 500, border: `1px solid ${BLUE}44` }}>Running</span>}
                  {isDone    && <span style={{ fontSize: 10, background: BLUE_BG, color: NAVY,
                                               padding: "2px 8px", borderRadius: 999, border: `1px solid ${PANEL_LINE}` }}>Complete</span>}
                </div>
                <div style={{ fontSize: 12, color: TEXT_MUTED, marginBottom: isDone ? 6 : 0 }}>{a.sub}</div>
                {isDone && (
                  <div style={{ fontSize: 11, fontFamily: "monospace", color: NAVY, background: BLUE_BG,
                                 padding: "5px 10px", borderRadius: 999, display: "inline-block",
                                 border: `1px solid ${PANEL_LINE}` }}>
                    {a.fn(persona)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function ResultsPage({ persona, onChat }) {
  const { scores, decision, signals, loan } = persona;
  const ts = tierStyle(scores.final);
  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "3rem 2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start",
                    marginBottom: "2.5rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase",
                        color: BLUE, marginBottom: 8, fontWeight: 500 }}>App No: {persona.appNo}</div>
          <h2 style={{ fontFamily: HEADING_FONT, fontSize: 26, letterSpacing: HEADING_TRACKING, fontWeight: 400, color: NAVY, margin: "0 0 4px" }}>
            {persona.name}
          </h2>
          <span style={{ fontSize: 13, color: TEXT_MUTED }}>{persona.platform} · {persona.city} · since {persona.since}</span>
        </div>
        <button onClick={onChat} style={{
          background: `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 100%)`, color: "#fff", border: "none", borderRadius: 12,
          padding: "10px 24px", fontSize: 13, fontWeight: 500, cursor: "pointer", boxShadow: "0 12px 26px rgba(6,46,69,0.18)",
        }}>Open Risk Officer</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(250px, 280px) minmax(0, 1fr)", gap: "2rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, background: PANEL_ALT,
                      border: `1px solid ${PANEL_LINE}`, borderRadius: 24, padding: "1.5rem", boxShadow: PANEL_SHADOW }}>
          <ScoreRing score={scores.final} size={200} animate />
          <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%" }}>
            <div style={{ textAlign: "center" }}>
              <span style={pillStyle(ts.bg, ts.color, ts.border)}>
                {tierLabel(scores.final)}
              </span>
            </div>
            <div style={{ textAlign: "center" }}>
              <span style={pillStyle(
                decision.label === "APPROVED" ? GREEN_BG : AMBER_BG,
                decision.label === "APPROVED" ? GREEN : AMBER,
                decision.label === "APPROVED" ? "#9FDCCF" : "#F1D08C",
              )}>{decision.label}</span>
            </div>
          </div>
          {decision.thin && (
            <div style={{ fontSize: 11, color: TEXT_FAINT, textAlign: "center", lineHeight: 1.5,
                           borderTop: `1px solid ${PANEL_LINE}`, paddingTop: 10, width: "100%" }}>
              Thin file assessment<br />scored on behavioral signals
            </div>
          )}
        </div>

        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: "1rem" }}>
            {[
              { label: "Default Prob",   val: `${decision.prob}%`,      sub: "XGBoost output" },
              { label: "Social Trust",   val: `${scores.trust}`,        sub: "Agent 3, out of 100" },
              { label: "Behavioral Adj", val: `+${scores.behavioral}`,  sub: "Layer 3 bonus" },
              { label: "Agent 3 Bonus",  val: `+${scores.adj3}`,        sub: "Delta vs cohort" },
            ].map(m => (
              <div key={m.label} style={{ background: PANEL_ALT, borderRadius: 16, padding: "14px 14px",
                                           border: `1px solid ${PANEL_LINE}`, boxShadow: PANEL_SHADOW }}>
                <div style={{ fontSize: 10, color: TEXT_FAINT, marginBottom: 6, textTransform: "uppercase",
                               letterSpacing: "0.06em" }}>{m.label}</div>
                <div style={{ fontFamily: HEADING_FONT, fontSize: 22, color: NAVY, fontWeight: 400 }}>{m.val}</div>
                <div style={{ fontSize: 10, color: TEXT_FAINT, marginTop: 3 }}>{m.sub}</div>
              </div>
            ))}
          </div>
          <div style={{ background: PANEL_ALT, borderRadius: 20, border: `1px solid ${PANEL_LINE}`, padding: "14px 16px", boxShadow: PANEL_SHADOW }}>
            <div style={{ fontFamily: HEADING_FONT, fontSize: 10, color: TEXT_FAINT, marginBottom: 10, textTransform: "uppercase",
                           letterSpacing: `calc(0.06em + ${HEADING_TRACKING})` }}>Score Decomposition</div>
            {[
              { label: "XGBoost base (90%)",       val: scores.base,              note: "sigmoid inversion, midpoint 0.35" },
              { label: "Social trust blend",        val: "+2.5 approx",            note: `0.10 x (${scores.trust} minus ${scores.base})` },
              { label: "Behavioral adjustment",     val: `+${scores.behavioral}`,  note: "streak and obligation bonuses" },
              { label: "Agent 3 bonus",             val: `+${scores.adj3}`,        note: "behavioral delta vs cohort 3.55" },
              { label: "Income multiplier",         val: `x${scores.mult}`,        note: "PLFS income validation" },
              { label: "Final GigScore",            val: scores.final,             note: "clip(0,100)", bold: true },
            ].map(r => (
              <div key={r.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 12,
                                           padding: `${r.bold ? "8px 0 4px" : "4px 0"}`,
                                           borderTop: r.bold ? `1px solid ${PANEL_LINE}` : "none",
                                           marginTop: r.bold ? 4 : 0 }}>
                <span style={{ color: r.bold ? TEXT : TEXT_MUTED, fontWeight: r.bold ? 500 : 400 }}>{r.label}</span>
                <span style={{ fontFamily: "monospace", color: r.bold ? NAVY : TEXT,
                                fontWeight: r.bold ? 600 : 400, fontSize: r.bold ? 13 : 12 }}>{r.val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        <div style={{ background: PANEL, borderRadius: 20, border: `1px solid ${PANEL_LINE}`, overflow: "hidden", boxShadow: PANEL_SHADOW }}>
          <div style={{ padding: "14px 20px", borderBottom: `1px solid ${PANEL_LINE}` }}>
            <span style={{ fontFamily: HEADING_FONT, letterSpacing: HEADING_TRACKING, fontWeight: 500, fontSize: 14, color: TEXT }}>Behavioral Signals</span>
          </div>
          <div style={{ padding: "0 20px" }}>
            <div style={{ padding: "10px 0 6px", fontSize: 10, textTransform: "uppercase",
                           letterSpacing: "0.08em", color: GREEN, fontWeight: 500 }}>Supporting Factors</div>
            {signals.pos.map(s => (
              <div key={s.name} style={{ paddingBottom: 12, borderBottom: `1px solid ${PAGE_BG}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                  <span style={{ fontSize: 13, color: TEXT, fontWeight: 500 }}>{s.name}</span>
                  <span style={{ fontSize: 12, color: GREEN, fontFamily: "monospace" }}>{s.val}</span>
                </div>
                <span style={{ fontSize: 11, color: TEXT_FAINT }}>{s.sub}</span>
              </div>
            ))}
            <div style={{ padding: "10px 0 6px", fontSize: 10, textTransform: "uppercase",
                           letterSpacing: "0.08em", color: RED, fontWeight: 500 }}>Risk Factors</div>
            {signals.neg.map(s => (
              <div key={s.name} style={{ paddingBottom: 12, borderBottom: `1px solid ${PAGE_BG}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                  <span style={{ fontSize: 13, color: TEXT, fontWeight: 500 }}>{s.name}</span>
                  <span style={{ fontSize: 12, color: RED, fontFamily: "monospace" }}>{s.val}</span>
                </div>
                <span style={{ fontSize: 11, color: TEXT_FAINT }}>{s.sub}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ background: PANEL, borderRadius: 20, border: `1px solid ${PANEL_LINE}`, overflow: "hidden", boxShadow: PANEL_SHADOW }}>
          <div style={{ padding: "14px 20px", borderBottom: `1px solid ${PANEL_LINE}`,
                        display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontFamily: HEADING_FONT, letterSpacing: HEADING_TRACKING, fontWeight: 500, fontSize: 14, color: TEXT }}>Loan Offer</span>
            <span style={pillStyle(
              decision.label === "APPROVED" ? GREEN_BG : BLUE_BG,
              decision.label === "APPROVED" ? GREEN : NAVY,
              decision.label === "APPROVED" ? "#9FDCCF" : "#96D8F3",
              { padding: "3px 10px" },
            )}>{decision.label}</span>
          </div>
          <div style={{ padding: "16px 20px" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: "1.5rem" }}>
              <span style={{ fontFamily: HEADING_FONT, fontSize: 30, color: NAVY, fontWeight: 400 }}>
                Rs {fmt(loan.amount)}
              </span>
              <span style={{ fontSize: 13, color: TEXT_MUTED }}>{persona.loanType}</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
              {[
                { label: "Interest rate",   val: `${loan.rate}% p.a.` },
                { label: "Tenure",          val: `${loan.tenure} months` },
                { label: "Monthly EMI",     val: `Rs ${fmt(loan.emi)}` },
                { label: "Processing fee",  val: `Rs ${fmt(loan.fee)}` },
                { label: "Total repayment", val: `Rs ${fmt(loan.total)}` },
                { label: "FOIR used",       val: `${loan.foir}% of 40%` },
              ].map(r => (
                <div key={r.label}>
                  <div style={{ fontSize: 11, color: TEXT_FAINT, marginBottom: 3 }}>{r.label}</div>
                  <div style={{ fontSize: 14, fontWeight: 500, color: TEXT }}>{r.val}</div>
                </div>
              ))}
            </div>
            <div style={{ background: GREEN_BG, border: "1px solid #9FDCCF", borderRadius: 14, padding: "12px 16px" }}>
              <div style={{ fontSize: 10, color: GREEN, textTransform: "uppercase",
                             letterSpacing: "0.08em", marginBottom: 4 }}>
                Interest Saved vs Market Rate (28%)
              </div>
              <div style={{ fontFamily: HEADING_FONT, fontSize: 22, color: GREEN }}>Rs {fmt(loan.saved)}</div>
              <div style={{ fontSize: 11, color: TEXT_MUTED, marginTop: 2 }}>
                over {loan.tenure} months vs KreditBee or NBFC rate
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function isReportIntent(text) {
  const normalized = text.toLowerCase();
  const asksForReport = /(generate|create|prepare|show|download|formal|pdf|html)/.test(normalized);
  const mentionsReport = /(report|credit assessment)/.test(normalized);
  return asksForReport && mentionsReport;
}

function ReportPreviewCard({ report, onOpenHtml, openingHtml, onDownload, downloading }) {
  return (
    <div style={{
      width: "min(100%, 860px)",
      background: PANEL,
      border: `1px solid ${PANEL_LINE}`,
      borderRadius: 20,
      boxShadow: PANEL_SHADOW,
      overflow: "hidden",
    }}>
      <div style={{
        padding: "18px 20px",
        background: `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 64%, ${NAVY_SOFT} 100%)`,
        color: TEXT_ON_DARK,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontFamily: HEADING_FONT, letterSpacing: HEADING_TRACKING, fontSize: 20, lineHeight: 1.2, marginBottom: 6 }}>
              {report.title}
            </div>
            <div style={{ fontSize: 12, color: MUTED_ON_DARK }}>
              {report.applicant.name} · {report.documentId} · {report.generatedOn}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button onClick={onOpenHtml} disabled={openingHtml} style={{
              background: openingHtml ? "rgba(255,255,255,0.28)" : "rgba(255,255,255,0.14)",
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.22)",
              borderRadius: 10,
              padding: "10px 14px",
              fontSize: 12,
              fontWeight: 600,
              cursor: openingHtml ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
            }}>
              {openingHtml ? "Opening HTML..." : "Open HTML"}
            </button>
            <button onClick={onDownload} disabled={downloading} style={{
              background: downloading ? TEXT_FAINT : "#fff",
              color: downloading ? "#fff" : NAVY,
              border: "none",
              borderRadius: 10,
              padding: "10px 14px",
              fontSize: 12,
              fontWeight: 600,
              cursor: downloading ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
            }}>
              {downloading ? "Generating PDF..." : "Download PDF"}
            </button>
          </div>
        </div>
      </div>

      <div style={{ padding: "18px 20px" }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 10,
          marginBottom: 18,
        }}>
          {report.summaryMetrics.map((metric) => (
            <div key={metric.label} style={{
              background: PANEL_ALT,
              border: `1px solid ${PANEL_LINE}`,
              borderRadius: 14,
              padding: "12px 14px",
            }}>
              <div style={{ fontSize: 10, color: TEXT_FAINT, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                {metric.label}
              </div>
              <div style={{ color: TEXT, fontWeight: 600, fontSize: 13, lineHeight: 1.35 }}>
                {metric.value}
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginBottom: 18, padding: "14px 16px", background: PANEL_ALT, border: `1px solid ${PANEL_LINE}`, borderRadius: 16 }}>
          <div style={{ fontFamily: HEADING_FONT, letterSpacing: HEADING_TRACKING, color: NAVY, fontSize: 13, marginBottom: 10 }}>
            Applicant Snapshot
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
            {[
              ["Platform", report.applicant.platform],
              ["Role", report.applicant.role],
              ["City", report.applicant.city],
              ["Tenure", `Since ${report.applicant.since}`],
              ["Purpose", report.applicant.purpose],
            ].map(([label, value]) => (
              <div key={label}>
                <div style={{ fontSize: 10, color: TEXT_FAINT, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3 }}>
                  {label}
                </div>
                <div style={{ fontSize: 12.5, color: TEXT, lineHeight: 1.45 }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {report.sections.map((section) => (
            <section key={section.title} style={{ paddingBottom: 14, borderBottom: `1px solid ${PAGE_BG}` }}>
              <div style={{ fontFamily: HEADING_FONT, letterSpacing: HEADING_TRACKING, color: NAVY, fontSize: 14, marginBottom: 8 }}>
                {section.title}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {section.paragraphs.map((paragraph, index) => (
                  <p key={`${section.title}-${index}`} style={{ margin: 0, color: TEXT, fontSize: 12.5, lineHeight: 1.6 }}>
                    {paragraph}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </div>

        <div style={{ marginTop: 16, fontSize: 11, lineHeight: 1.5, color: TEXT_FAINT }}>
          {report.footer}
        </div>
      </div>
    </div>
  );
}

function ChatPage({ persona }) {
  const [messages, setMessages] = useState([{
    kind: "text",
    role: "assistant",
    content: `I have reviewed the GigScore assessment for ${persona.name} (${persona.appNo}). The system has issued a ${persona.decision.label.toLowerCase()} at Rs ${fmt(persona.loanAmount)} with a final GigScore of ${persona.scores.final}. The default probability is ${persona.decision.prob}%. What would you like to examine?`
  }]);
  const [input,   setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingReportPreview, setLoadingReportPreview] = useState(false);
  const [openingHtmlReport, setOpeningHtmlReport] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [serviceStatus, setServiceStatus] = useState({ configured: null, model: null, provider: null });
  const bottomRef             = useRef(null);
  const isConfigured = serviceStatus.configured === true;
  const isChecking = serviceStatus.configured === null;

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    let active = true;

    const loadStatus = async () => {
      try {
        const res = await fetch("/api/health");
        const data = await res.json();
        if (!active) return;
        setServiceStatus({
          configured: Boolean(data.configured),
          model: data.model || null,
          provider: data.provider || null,
        });
      } catch {
        if (!active) return;
        setServiceStatus({ configured: false, model: null, provider: null });
      }
    };

    loadStatus();
    return () => { active = false; };
  }, []);

  const downloadReportPdf = async () => {
    if (downloadingReport) return;

    setDownloadingReport(true);
    try {
      const res = await fetch("/api/risk-officer/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Unable to generate the PDF report.");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${persona.appNo}-credit-assessment-report.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setMessages((prev) => [
        ...prev,
        {
          kind: "text",
          role: "assistant",
          content: `The formal credit assessment PDF for ${persona.name} has been generated and downloaded with the fixed eight-section report structure.`,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          kind: "text",
          role: "assistant",
          content: error?.message || "Unable to generate the PDF report.",
        },
      ]);
    } finally {
      setDownloadingReport(false);
    }
  };

  const generateReportPreview = async () => {
    if (loadingReportPreview) return;

    setLoadingReportPreview(true);
    try {
      const res = await fetch("/api/risk-officer/report-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Unable to generate the report preview.");
      }

      const report = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          kind: "report",
          role: "assistant",
          report,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          kind: "text",
          role: "assistant",
          content: error?.message || "Unable to generate the report preview.",
        },
      ]);
    } finally {
      setLoadingReportPreview(false);
    }
  };

  const openReportHtml = async () => {
    if (openingHtmlReport) return;

    setOpeningHtmlReport(true);
    try {
      const res = await fetch("/api/risk-officer/report-html", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Unable to open the HTML report.");
      }

      const html = await res.text();
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const url = window.URL.createObjectURL(blob);
      const win = window.open(url, "_blank", "noopener,noreferrer");

      if (!win) {
        window.URL.revokeObjectURL(url);
        throw new Error("The browser blocked the HTML report popup. Allow popups and try again.");
      }

      window.setTimeout(() => {
        window.URL.revokeObjectURL(url);
      }, 30000);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          kind: "text",
          role: "assistant",
          content: error?.message || "Unable to open the HTML report.",
        },
      ]);
    } finally {
      setOpeningHtmlReport(false);
    }
  };

  const send = async () => {
    if (!input.trim() || loading || loadingReportPreview || openingHtmlReport || downloadingReport) return;
    const userMsg = { kind: "text", role: "user", content: input.trim() };
    const next    = [...messages, userMsg];
    setMessages(next);
    setInput("");

    if (isReportIntent(userMsg.content)) {
      await generateReportPreview();
      return;
    }

    setLoading(true);
    try {
      const res  = await fetch("/api/risk-officer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          systemPrompt: buildSystemPrompt(persona),
          messages: next
            .filter((message) => (message.kind || "text") === "text")
            .map((message) => ({ role: message.role, content: message.content })),
        }),
      });
      const data = await res.json();
      const text = res.ok ? data.content : data.error || "Unable to retrieve response.";
      setMessages(p => [...p, { kind: "text", role: "assistant", content: text }]);
    } catch {
      setMessages(p => [...p, { kind: "text", role: "assistant", content: "Connection error. Please retry." }]);
    } finally {
      setLoading(false);
    }
  };

  const suggested = [
    `Why was ${persona.decision.label.toLowerCase()} issued rather than a full approval?`,
    `What specific behavioral signals drove the score to ${persona.scores.final}?`,
    `How does the social trust score of ${persona.scores.trust} affect this decision?`,
    `What actions would move this applicant to ${persona.decision.tier === "Near-Prime" ? "Prime" : "Near-Prime"} tier?`,
  ];

  return (
    <div className="chat-shell" style={{ maxWidth: 1360, margin: "0 auto", padding: "2rem",
                  display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.5rem",
                  height: "calc(100vh - 120px)" }}>
      <div style={{ background: PANEL_ALT, borderRadius: 20, border: `1px solid ${PANEL_LINE}`,
                    padding: "1.5rem", overflowY: "auto", display: "flex", flexDirection: "column", boxShadow: PANEL_SHADOW }}>
        <div style={{ fontFamily: HEADING_FONT, fontSize: 10, textTransform: "uppercase", letterSpacing: `calc(0.1em + ${HEADING_TRACKING})`,
                      color: TEXT_FAINT, marginBottom: 14 }}>Credit File Context</div>
        {[
          { s: "Assessment", items: [
            { l: "GigScore",      v: `${persona.scores.final} / 100` },
            { l: "Tier",          v: tierLabel(persona.scores.final) },
            { l: "Decision",      v: persona.decision.label },
            { l: "Default prob",  v: `${persona.decision.prob}%` },
          ]},
          { s: "Behavioral", items: [
            { l: "Social trust",  v: `${persona.scores.trust} / 100` },
            { l: "Agent 3 bonus", v: `+${persona.scores.adj3}` },
            { l: "Beh. adj",      v: `+${persona.scores.behavioral}` },
            { l: "Multiplier",    v: `${persona.scores.mult}` },
          ]},
          { s: "Loan Offer", items: [
            { l: "Amount",        v: `Rs ${fmt(persona.loan.amount)}` },
            { l: "Rate",          v: `${persona.loan.rate}% p.a.` },
            { l: "EMI",           v: `Rs ${fmt(persona.loan.emi)}` },
            { l: "FOIR",          v: `${persona.loan.foir}% of 40%` },
          ]},
          { s: "Profile", items: [
            { l: "Platform",      v: persona.platform },
            { l: "Income",        v: `Rs ${fmt(persona.income)}/mo` },
            { l: "City",          v: persona.city },
            { l: "Since",         v: persona.since },
          ]},
        ].map(g => (
          <div key={g.s} style={{ marginBottom: "1.25rem" }}>
            <div style={{ fontFamily: HEADING_FONT, fontSize: 10, color: BLUE, fontWeight: 500, textTransform: "uppercase",
                           letterSpacing: `calc(0.08em + ${HEADING_TRACKING})`, marginBottom: 8 }}>{g.s}</div>
            {g.items.map(i => (
              <div key={i.l} style={{ display: "flex", justifyContent: "space-between",
                                       fontSize: 12, paddingBottom: 5 }}>
                <span style={{ color: TEXT_FAINT }}>{i.l}</span>
                <span style={{ color: TEXT, fontWeight: 500 }}>{i.v}</span>
              </div>
            ))}
          </div>
        ))}
        <div style={{ borderTop: `1px solid ${PANEL_LINE}`, paddingTop: 12, marginTop: "auto" }}>
          <div style={{ fontSize: 10, color: TEXT_FAINT, marginBottom: 8 }}>Suggested questions</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {suggested.map(q => (
              <button key={q} onClick={() => setInput(q)} style={{
                background: PANEL, border: `1px solid ${PANEL_LINE}`, borderRadius: 10,
                padding: "8px 10px", fontSize: 11, color: TEXT_MUTED, cursor: "pointer",
                textAlign: "left", lineHeight: 1.45,
              }}>{q}</button>
            ))}
            <button onClick={generateReportPreview} disabled={loadingReportPreview} style={{
              background: loadingReportPreview ? TEXT_FAINT : NAVY,
              color: "#fff",
              border: "none",
              borderRadius: 10,
              padding: "8px 10px",
              fontSize: 11,
              cursor: loadingReportPreview ? "not-allowed" : "pointer",
              textAlign: "left",
              lineHeight: 1.45,
              width: "100%",
              marginTop: 8,
              fontWeight: 500,
            }}>
              {loadingReportPreview ? "Generating HTML Report..." : "Preview Full HTML Report"}
            </button>
            <button onClick={openReportHtml} disabled={openingHtmlReport} style={{
              background: openingHtmlReport ? TEXT_FAINT : NAVY_SOFT,
              color: "#fff",
              border: "none",
              borderRadius: 10,
              padding: "8px 10px",
              fontSize: 11,
              cursor: openingHtmlReport ? "not-allowed" : "pointer",
              textAlign: "left",
              lineHeight: 1.45,
              width: "100%",
              fontWeight: 500,
            }}>
              {openingHtmlReport ? "Opening Standalone HTML Report..." : "Open Standalone HTML Report"}
            </button>
            <button onClick={downloadReportPdf} disabled={downloadingReport} style={{
              background: downloadingReport ? TEXT_FAINT : NAVY_DARK,
              color: "#fff",
              border: "none",
              borderRadius: 10,
              padding: "8px 10px",
              fontSize: 11,
              cursor: downloadingReport ? "not-allowed" : "pointer",
              textAlign: "left",
              lineHeight: 1.45,
              width: "100%",
              fontWeight: 500,
            }}>
              {downloadingReport ? "Generating Credit Report PDF..." : "Download Full Credit Report PDF"}
            </button>
          </div>
        </div>
      </div>

      <div className="chat-main-panels" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(340px, 0.95fr)", gap: "1rem", minHeight: 0 }}>
        <div style={{ background: PANEL, borderRadius: 20, border: `1px solid ${PANEL_LINE}`,
                    display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: PANEL_SHADOW }}>
        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${PANEL_LINE}`,
                      display: "flex", alignItems: "center", gap: 12 }}>
          <div>
            <BrandLockup gigHeight={26} barclaysHeight={18} dividerColor={PANEL_LINE} />
            <div style={{ fontSize: 12, color: TEXT_FAINT, marginTop: 6 }}>
              Risk Officer Desk · {serviceStatus.provider || "provider"} · {serviceStatus.model || "LLM"} · {persona.appNo}
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: isChecking ? TEXT_FAINT : isConfigured ? BLUE : RED }} />
            <span style={{ fontSize: 12, color: TEXT_MUTED }}>
              {isChecking ? "Checking" : isConfigured ? "Online" : "Setup Required"}
            </span>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "1.5rem" }}>
          {messages.map((m, i) => (
            m.kind === "report" ? (
              <div key={i} style={{ display: "flex", justifyContent: "flex-start", marginBottom: 16 }}>
                <ReportPreviewCard
                  report={m.report}
                  onOpenHtml={openReportHtml}
                  openingHtml={openingHtmlReport}
                  onDownload={downloadReportPdf}
                  downloading={downloadingReport}
                />
              </div>
            ) : (
              <div key={i} style={{ display: "flex",
                                     justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                                     marginBottom: 14 }}>
                <div style={{
                  maxWidth: "72%", fontSize: 14, lineHeight: 1.65,
                  background: m.role === "user" ? NAVY : PANEL_ALT,
                  color:      m.role === "user" ? "#fff" : TEXT,
                  borderRadius: m.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                  padding: "12px 16px",
                  border: m.role !== "user" ? `1px solid ${PANEL_LINE}` : "none",
                }}>{m.content}</div>
              </div>
            )
          ))}
          {(loading || loadingReportPreview) && (
            <div style={{ display: "flex", gap: 4, padding: "12px 16px", background: PANEL_ALT,
                           borderRadius: 12, width: "fit-content", border: `1px solid ${PANEL_LINE}` }}>
              {[0,1,2].map(i => (
                <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: TEXT_FAINT,
                                       animation: `bounce 1.2s ${i*0.2}s infinite` }} />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div style={{ padding: "14px 20px", borderTop: `1px solid ${PANEL_LINE}`, display: "flex", gap: 10 }}>
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
            placeholder="Ask about the credit assessment..."
            style={{ flex: 1, border: `1px solid ${PANEL_LINE}`, borderRadius: 10,
                     padding: "10px 14px", fontSize: 14, outline: "none", color: TEXT, background: PANEL_ALT }} />
          <button onClick={send} disabled={!input.trim() || loading || loadingReportPreview || openingHtmlReport || downloadingReport} style={{
            background: input.trim() && !loading && !loadingReportPreview && !openingHtmlReport && !downloadingReport ? `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 100%)` : TEXT_FAINT, color: "#fff",
            border: "none", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 500,
            cursor: input.trim() && !loading && !loadingReportPreview && !openingHtmlReport && !downloadingReport ? "pointer" : "not-allowed",
          }}>Send</button>
        </div>
        </div>
        <Agent5CreditStory persona={persona} />
      </div>
      <style>{`
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }

        @media (max-width: 1180px) {
          .chat-shell {
            grid-template-columns: minmax(0, 1fr) !important;
            height: auto !important;
          }

          .chat-main-panels {
            grid-template-columns: minmax(0, 1fr) !important;
          }
        }
      `}</style>
    </div>
  );
}

export default function App() {
  const [page,       setPage]       = useState("home");
  const [selectedId, setSelectedId] = useState(null);
  const [opacity,    setOpacity]    = useState(1);

  const nav = (p) => {
    setOpacity(0);
    setTimeout(() => { setPage(p); setOpacity(1); }, 250);
  };

  const persona = selectedId ? PERSONAS[selectedId] : null;

  return (
    <div style={{ fontFamily: BODY_FONT,
                  minHeight: "100vh", background: `linear-gradient(180deg, ${PAGE_BG} 0%, ${PAGE_BG_ALT} 100%)`, color: TEXT }}>
      <style>{`
        @font-face {
          font-family: 'Francy';
          src: url('/fonts/Francy.woff2') format('woff2');
          font-style: normal;
          font-weight: 400;
          font-display: swap;
        }
      `}</style>
      <Nav page={page} onNav={nav} persona={persona} />
      <div style={{ opacity, transition: "opacity 0.25s ease" }}>
        {page === "home"     && <HomePage onStart={() => nav("pipeline")} selectedId={selectedId} setSelectedId={setSelectedId} />}
        {page === "pipeline" && persona && <PipelinePage persona={persona} onDone={() => nav("results")} />}
        {page === "results"  && persona && <ResultsPage  persona={persona} onChat={() => nav("chat")} />}
        {page === "chat"     && persona && <ChatPage     persona={persona} />}
      </div>
    </div>
  );
}
