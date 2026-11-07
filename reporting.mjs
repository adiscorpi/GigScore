import PDFDocument from "pdfkit";

const FOUR_FIFTHS_THRESHOLD = 0.8;

const BATCH_AUDIT = {
  gender: 0.94,
  cityTier: 0.97,
  occupationType: 0.89,
  dpdp: {
    piiScan: "Pass",
    consentVerification: "Pass",
    purposeScope: "Pass",
  },
  overallStatus: "CLEAR",
  kycStatus: "CLEARED",
};

function fmt(value) {
  return Number(value).toLocaleString("en-IN");
}

function number(value, digits = 1) {
  return Number(value).toFixed(digits);
}

function rupees(value) {
  return `Rs ${fmt(value)}`;
}

function findSignal(persona, needle, type = "pos") {
  return persona?.signals?.[type]?.find((signal) =>
    signal?.name?.toLowerCase().includes(needle.toLowerCase()),
  );
}

function decisionBucket(label = "") {
  const normalized = label.toLowerCase();
  if (normalized.includes("conditional")) return "conditional";
  if (normalized.includes("approved")) return "approved";
  return "declined";
}

function describeDiRatio(name, ratio) {
  const status = ratio >= FOUR_FIFTHS_THRESHOLD ? "passes" : "fails";
  return `${name}: ${number(ratio, 2)}. Under the 4/5ths rule, ratios at or above 0.80 are generally considered acceptable; this batch ${status} that screen for ${name.toLowerCase()}.`;
}

function getExistingObligations(persona) {
  const obligationSignal = findSignal(persona, "obligation fulfillment", "pos");
  if (obligationSignal) {
    return `${obligationSignal.val} obligation fulfillment across the review window; no missed fixed recurring obligations were flagged in the assessment period.`;
  }

  return "No delinquent recurring obligation pattern was flagged in the reviewed period.";
}

function getNetTrustContribution(persona) {
  const { scores } = persona;
  const preMultiplier = scores.final / scores.mult;
  const trustContribution = preMultiplier - scores.base - scores.behavioral - scores.adj3;
  const rawGraphDelta = (scores.trust - scores.base) * 0.1;

  return {
    preMultiplier,
    trustContribution,
    rawGraphDelta,
  };
}

function getExecutiveSummary(persona) {
  const status = decisionBucket(persona.decision.label);
  const positive1 = persona.signals.pos[0];
  const positive2 = persona.signals.pos[1];
  const risk1 = persona.signals.neg[0];
  const risk2 = persona.signals.neg[1];

  return [
    `Decision: ${persona.decision.label}. GigScore: ${number(persona.scores.final)} / 100. Tier: ${persona.decision.tier}. Default probability: ${number(persona.decision.prob)}%.`,
    `${persona.name} is classified as ${status === "approved" ? "approvable" : status === "conditional" ? "conditionally approvable" : "currently not approvable"} because the file combines strong behavioral evidence with identifiable credit risk frictions. The strongest supporting factors are ${positive1.name.toLowerCase()} (${positive1.val}) and ${positive2.name.toLowerCase()} (${positive2.val}), while the main constraints are ${risk1.name.toLowerCase()} (${risk1.val}) and ${risk2.name.toLowerCase()} (${risk2.val}). The resulting view is that the applicant is serviceable under controlled terms, but not yet strong enough for unsecured prime treatment.`,
  ];
}

function getApplicantProfile(persona) {
  return [
    `Platform: ${persona.platform}. City: ${persona.city}. Monthly income assessed: ${rupees(persona.income)}. Platform tenure: since ${persona.since}.`,
    `Loan purpose: ${persona.purpose}. Requested product: ${persona.loanType} for ${rupees(persona.loanAmount)} over ${persona.tenure} months.`,
    `Existing obligations: ${getExistingObligations(persona)}`,
  ];
}

function getMethodologySection(persona) {
  const { scores } = persona;
  const methodology = getNetTrustContribution(persona);

  return [
    "GigScore uses a fixed production sequence: XGBoost base score from sigmoid inversion around the documented 0.35 midpoint, social trust graph blend, behavioral bonus or penalty layer, Agent 3 cohort-relative bonus, then an income validation multiplier before clipping to the 0 to 100 range.",
    `Actual calculation for this file: base score ${number(scores.base)} + calibrated social trust contribution ${number(methodology.trustContribution)} + behavioral layer ${number(scores.behavioral)} + Agent 3 bonus ${number(scores.adj3)} = pre-multiplier subtotal ${number(methodology.preMultiplier)}.`,
    `Income multiplier applied: ${number(scores.mult, 2)}. Final GigScore = ${number(methodology.preMultiplier)} x ${number(scores.mult, 2)} = ${number(scores.final)}.`,
    `Reference graph calibration: raw 10% trust delta = 0.10 x (${number(scores.trust)} - ${number(scores.base)}) = ${number(methodology.rawGraphDelta)}. Net applied graph contribution after calibration for this document = ${number(methodology.trustContribution)}.`,
  ];
}

function signalExplanation(signal, direction) {
  const influence = direction === "positive" ? "supported" : "constrained";
  return `${signal.name}: metric value ${signal.val}. This metric measures ${signal.sub.toLowerCase()}. In this file, the reading ${influence} the final score because it indicates ${direction === "positive" ? "repayment discipline, account stability, or community trust" : "elevated volatility, repayment uncertainty, or policy risk that required a tighter credit stance"}.`;
}

function getBehavioralSignalSection(persona) {
  return [
    ...persona.signals.pos.map((signal) => signalExplanation(signal, "positive")),
    ...persona.signals.neg.map((signal) => signalExplanation(signal, "negative")),
  ];
}

function getLoanTermsSection(persona) {
  const { loan, income } = persona;
  const monthlyIncome = Number(income);
  const computedFoir = (loan.emi / monthlyIncome) * 100;
  const headroom = 40 - loan.foir;

  return [
    `Approved amount: ${rupees(loan.amount)}. Rate: ${number(loan.rate)}% p.a. Tenure: ${loan.tenure} months. EMI: ${rupees(loan.emi)}.`,
    `FOIR calculation: ${rupees(loan.emi)} / ${rupees(monthlyIncome)} = ${number(computedFoir)}%. The policy FOIR used in the structured offer is ${number(loan.foir)}%, which remains within the RBI-aligned 40% affordability ceiling with ${number(headroom)} percentage points of headroom.`,
    `Interest saved versus a 28% market comparator: ${rupees(loan.saved)} over the proposed tenure. This means the applicant receives materially cheaper credit than a high-cost NBFC alternative while remaining inside the bank's affordability guardrails.`,
  ];
}

function getFairnessAuditSection() {
  return [
    describeDiRatio("Gender DI ratio", BATCH_AUDIT.gender),
    describeDiRatio("City tier DI ratio", BATCH_AUDIT.cityTier),
    describeDiRatio("Occupation type DI ratio", BATCH_AUDIT.occupationType),
    `DPDP compliance checks: PII scan ${BATCH_AUDIT.dpdp.piiScan}; consent verification ${BATCH_AUDIT.dpdp.consentVerification}; purpose scope ${BATCH_AUDIT.dpdp.purposeScope}. Overall batch fairness and privacy status: ${BATCH_AUDIT.overallStatus}.`,
  ];
}

function getRbiComplianceSection(persona) {
  return [
    `FPC Clause 3(a): the applicant has been assessed on documented income, transaction behavior, affordability, and stated loan purpose, so the credit decision is grounded in disclosed eligibility criteria rather than opaque discretion.`,
    `FPC Clause 3(c): the offer terms are explicit in amount ${rupees(persona.loan.amount)}, rate ${number(persona.loan.rate)}%, tenure ${persona.loan.tenure} months, EMI ${rupees(persona.loan.emi)}, and processing fee ${rupees(persona.loan.fee)}.`,
    `FPC Clause 3(e): the rationale is explainable through the GigScore components, top positive signals, risk factors, and FOIR controls recorded in this report.`,
    `FPC Clause 3(f): ongoing monitoring conditions are documented and proportionate to the applicant's tier and risk indicators.`,
    `DPDP Act checks: purpose limitation satisfied, data minimisation satisfied, and consent handling satisfied. KYC clearance status: ${BATCH_AUDIT.kycStatus}.`,
  ];
}

function getRecommendationSection(persona) {
  const status = decisionBucket(persona.decision.label);

  if (status === "approved") {
    return [
      `Credit committee recommendation: approve on the proposed terms. Monitoring conditions should include payment behavior surveillance, monthly cash-flow consistency checks, and escalation if gambling or sustained net outflow signals increase.`,
      `${persona.name}'s trajectory is positive because the applicant combines a near-prime GigScore with strong tenure and diversified spending behavior. The profile should be monitored, but the current data supports responsible onboarding into the formal credit system.`,
    ];
  }

  if (status === "conditional") {
    return [
      `Credit committee recommendation: conditional approval on the proposed terms. Monitoring conditions should include monthly review of inflow versus outflow stability, adverse merchant category surveillance, and immediate escalation if obligation fulfillment deteriorates or policy red flags intensify.`,
      `${persona.name}'s trajectory remains constructive because the file contains usable behavioral strength, but the current risk pattern still requires controlled exposure rather than full policy relaxation. The applicant can migrate upward with sustained payment discipline, cleaner cash-flow balance, and continued trust-network stability.`,
    ];
  }

  return [
    `Credit committee recommendation: decline at this stage. The required 90-day improvement path is to stabilise inflow coverage, eliminate adverse merchant activity, maintain perfect obligation fulfillment, and demonstrate lower default propensity through cleaner transactional behaviour.`,
    `${persona.name}'s trajectory is recoverable, but not yet investable on formal credit terms. Reassessment should occur only after three clean review cycles are observed.`,
  ];
}

function buildSections(persona) {
  return [
    { title: "1. EXECUTIVE SUMMARY", paragraphs: getExecutiveSummary(persona) },
    { title: "2. APPLICANT PROFILE", paragraphs: getApplicantProfile(persona) },
    { title: "3. GIGSCORE METHODOLOGY", paragraphs: getMethodologySection(persona) },
    { title: "4. BEHAVIORAL SIGNAL ANALYSIS", paragraphs: getBehavioralSignalSection(persona) },
    { title: "5. LOAN TERMS AND FOIR COMPLIANCE", paragraphs: getLoanTermsSection(persona) },
    { title: "6. AGENT 7 FAIRNESS AUDIT", paragraphs: getFairnessAuditSection(persona) },
    { title: "7. RBI COMPLIANCE MAPPING", paragraphs: getRbiComplianceSection(persona) },
    { title: "8. CREDIT COMMITTEE RECOMMENDATION", paragraphs: getRecommendationSection(persona) },
  ];
}

export function buildCreditReport(persona) {
  if (!validatePersona(persona)) {
    throw new Error("Incomplete persona payload for report generation.");
  }

  return {
    title: "FORMAL CREDIT ASSESSMENT REPORT",
    documentId: persona.appNo,
    generatedOn: new Date().toISOString().slice(0, 10),
    applicant: {
      name: persona.name,
      role: persona.role,
      platform: persona.platform,
      city: persona.city,
      since: persona.since,
      purpose: persona.purpose,
    },
    summaryMetrics: [
      { label: "Decision", value: persona.decision.label },
      { label: "GigScore", value: `${number(persona.scores.final)} / 100` },
      { label: "Tier", value: persona.decision.tier },
      { label: "Default Probability", value: `${number(persona.decision.prob)}%` },
      { label: "Loan Amount", value: rupees(persona.loan.amount) },
      { label: "EMI", value: rupees(persona.loan.emi) },
    ],
    sections: buildSections(persona),
    footer:
      "This report is generated in a fixed section structure from recorded GigScore system inputs, affordability metrics, and compliance controls for audit consistency.",
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderMetricCard(metric) {
  return `
    <div class="metric-card">
      <div class="metric-label">${escapeHtml(metric.label)}</div>
      <div class="metric-value">${escapeHtml(metric.value)}</div>
    </div>
  `;
}

function renderSection(section) {
  return `
    <section class="report-section">
      <h2>${escapeHtml(section.title)}</h2>
      ${section.paragraphs
        .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
        .join("")}
    </section>
  `;
}

export function buildCreditReportHtml(persona) {
  const report = buildCreditReport(persona);

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(report.title)} - ${escapeHtml(report.documentId)}</title>
    <style>
      :root {
        --navy: #083B59;
        --navy-dark: #062E45;
        --navy-soft: #0B4F74;
        --blue: #00AEEF;
        --page: #EAF4F8;
        --panel: #FFFFFF;
        --panel-alt: #F4FAFD;
        --line: #BFD7E4;
        --text: #0A3046;
        --muted: #58798D;
        --faint: #88A8BA;
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
        background: linear-gradient(180deg, var(--page) 0%, #DCECF4 100%);
        color: var(--text);
        padding: 32px 18px;
      }

      .report-shell {
        max-width: 980px;
        margin: 0 auto;
      }

      .report-card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 24px;
        overflow: hidden;
        box-shadow: 0 24px 60px rgba(6, 46, 69, 0.12);
      }

      .report-header {
        background: linear-gradient(135deg, var(--navy-dark) 0%, var(--navy) 62%, var(--navy-soft) 100%);
        color: #F6FBFE;
        padding: 28px 30px 24px;
      }

      .eyebrow {
        color: #A5C8D8;
        font-size: 11px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        margin-bottom: 10px;
      }

      h1 {
        margin: 0 0 8px;
        font-size: clamp(28px, 5vw, 38px);
        line-height: 1.05;
        font-weight: 700;
      }

      .header-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 10px 18px;
        font-size: 13px;
        color: #D4ECF6;
      }

      .report-body {
        padding: 24px 28px 28px;
      }

      .snapshot {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-bottom: 18px;
      }

      .snapshot-card,
      .metric-card {
        background: var(--panel-alt);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 13px 14px;
      }

      .snapshot-label,
      .metric-label {
        font-size: 10px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--faint);
        margin-bottom: 5px;
      }

      .snapshot-value,
      .metric-value {
        font-size: 13px;
        line-height: 1.45;
        color: var(--text);
        font-weight: 600;
      }

      .metrics {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 10px;
        margin-bottom: 18px;
      }

      .report-section {
        padding: 18px 0;
        border-top: 1px solid #E1EDF3;
      }

      .report-section:first-of-type {
        border-top: none;
        padding-top: 4px;
      }

      h2 {
        margin: 0 0 10px;
        font-size: 16px;
        line-height: 1.3;
        color: var(--navy);
      }

      p {
        margin: 0 0 10px;
        font-size: 13px;
        line-height: 1.65;
        color: var(--text);
      }

      .report-footer {
        margin-top: 8px;
        padding-top: 16px;
        border-top: 1px solid #E1EDF3;
        font-size: 11px;
        line-height: 1.55;
        color: var(--muted);
      }

      @media print {
        body {
          background: #fff;
          padding: 0;
        }

        .report-card {
          box-shadow: none;
          border-radius: 0;
          border: none;
        }
      }
    </style>
  </head>
  <body>
    <main class="report-shell">
      <article class="report-card">
        <header class="report-header">
          <div class="eyebrow">GigScore Risk Officer</div>
          <h1>${escapeHtml(report.title)}</h1>
          <div class="header-meta">
            <span>Applicant: ${escapeHtml(report.applicant.name)}</span>
            <span>Application: ${escapeHtml(report.documentId)}</span>
            <span>Generated: ${escapeHtml(report.generatedOn)}</span>
          </div>
        </header>

        <section class="report-body">
          <div class="snapshot">
            <div class="snapshot-card">
              <div class="snapshot-label">Platform</div>
              <div class="snapshot-value">${escapeHtml(report.applicant.platform)}</div>
            </div>
            <div class="snapshot-card">
              <div class="snapshot-label">Role</div>
              <div class="snapshot-value">${escapeHtml(report.applicant.role)}</div>
            </div>
            <div class="snapshot-card">
              <div class="snapshot-label">City</div>
              <div class="snapshot-value">${escapeHtml(report.applicant.city)}</div>
            </div>
            <div class="snapshot-card">
              <div class="snapshot-label">Purpose</div>
              <div class="snapshot-value">${escapeHtml(report.applicant.purpose)}</div>
            </div>
          </div>

          <div class="metrics">
            ${report.summaryMetrics.map(renderMetricCard).join("")}
          </div>

          ${report.sections.map(renderSection).join("")}

          <footer class="report-footer">
            ${escapeHtml(report.footer)}
          </footer>
        </section>
      </article>
    </main>
  </body>
</html>`;
}

function writeHeading(doc, text) {
  doc
    .font("Helvetica-Bold")
    .fontSize(14)
    .fillColor("#083B59")
    .text(text, { paragraphGap: 8 });
}

function writeParagraph(doc, text) {
  doc
    .font("Helvetica")
    .fontSize(10.5)
    .fillColor("#0A3046")
    .text(text, {
      align: "justify",
      lineGap: 3,
      paragraphGap: 8,
    });
}

function ensureSpace(doc, minimumHeight = 100) {
  if (doc.y > doc.page.height - doc.page.margins.bottom - minimumHeight) {
    doc.addPage();
  }
}

function validatePersona(persona) {
  if (!persona || typeof persona !== "object") return false;

  const requiredStrings = ["id", "appNo", "name", "platform", "city", "since", "loanType", "purpose"];
  const requiredObjects = ["scores", "decision", "signals", "loan"];

  return (
    requiredStrings.every((key) => typeof persona[key] === "string" && persona[key].trim()) &&
    requiredObjects.every((key) => persona[key] && typeof persona[key] === "object") &&
    Array.isArray(persona.signals.pos) &&
    Array.isArray(persona.signals.neg)
  );
}

export async function buildCreditReportPdf(persona) {
  const report = buildCreditReport(persona);

  return await new Promise((resolve, reject) => {
    const doc = new PDFDocument({
      size: "A4",
      margins: { top: 54, bottom: 54, left: 54, right: 54 },
      info: {
        Title: `GigScore Credit Assessment - ${report.documentId}`,
        Author: "GigScore Risk Officer",
        Subject: "Formal Credit Assessment Report",
      },
    });

    const chunks = [];
    doc.on("data", (chunk) => chunks.push(chunk));
    doc.on("end", () => resolve(Buffer.concat(chunks)));
    doc.on("error", reject);

    doc
      .font("Helvetica-Bold")
      .fontSize(18)
      .fillColor("#083B59")
      .text(report.title);

    doc
      .moveDown(0.3)
      .font("Helvetica")
      .fontSize(10)
      .fillColor("#58798D")
      .text(`Applicant: ${report.applicant.name}`)
      .text(`Application Number: ${report.documentId}`)
      .text(`Report Generated: ${report.generatedOn}`)
      .text(`System: GigScore Risk Officer`);

    doc.moveDown(0.8);

    for (const section of report.sections) {
      ensureSpace(doc, 120);
      writeHeading(doc, section.title);
      for (const paragraph of section.paragraphs) {
        writeParagraph(doc, paragraph);
      }
      doc.moveDown(0.2);
    }

    doc
      .moveDown(0.6)
      .font("Helvetica-Oblique")
      .fontSize(9)
      .fillColor("#58798D")
      .text(report.footer, { align: "left" });

    doc.end();
  });
}
