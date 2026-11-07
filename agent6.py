"""
GigScore — Loan Application PDF Parser
=======================================
Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University

Parses the GigScore Loan Application Form PDF into a clean JSON dict
that Agent 6 reads directly — no hardcoded synthetic data needed.

Sections parsed:
    A. Personal Details
    B. KYC & Contact
    C. Employment & Income
    D. Loan Details
    E. Bank Account Details
    F. GigScore Credit Assessment (behavioral signals)
    G. Loan Decision (if pre-filled by system)

Usage:
    python parse_loan_application.py raju_sharma_loan_application.pdf
    python parse_loan_application.py raju_sharma_loan_application.pdf --out loan_application.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber

# ── Default output ────────────────────────────────────────────────────────
DEFAULT_PDF = "raju_sharma_loan_application.pdf"
DEFAULT_OUT = "loan_application.json"


# ─────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────

def clean_amount(s: str) -> float:
    """Extract numeric amount from strings like 'INR 45,000' or '₹45,000'."""
    if not s:
        return 0.0
    s = re.sub(r'[INRinr₹,\s]', '', str(s))
    try:
        return float(s)
    except ValueError:
        return 0.0


def clean_text(s: str) -> str:
    return str(s or "").strip()


def extract_between(text: str, start: str, end: str) -> str:
    """Extract text between two markers."""
    try:
        s = text.index(start) + len(start)
        e = text.index(end, s)
        return text[s:e].strip()
    except ValueError:
        return ""


def find_value(text: str, label: str, stop_patterns: list = None) -> str:
    """
    Find value after a label in raw PDF text.
    Stops at any of the stop_patterns or end of line.
    """
    pattern = re.escape(label)
    m = re.search(pattern + r'\s*(.+?)(?:\n|$)', text)
    if not m:
        return ""
    val = m.group(1).strip()
    if stop_patterns:
        for sp in stop_patterns:
            m2 = re.search(re.escape(sp), val)
            if m2:
                val = val[:m2.start()].strip()
    return val


def parse_inr(text: str, label: str) -> float:
    """Find 'INR X,XXX' after a label."""
    m = re.search(re.escape(label) + r'.*?INR\s*([\d,]+)', text, re.IGNORECASE)
    if m:
        return clean_amount(m.group(1))
    return 0.0


# ─────────────────────────────────────────────────────────────────────────
# SECTION PARSERS
# ─────────────────────────────────────────────────────────────────────────

def parse_personal(text: str) -> dict:
    name_m   = re.search(r'Full Name\s+([A-Z ]+?)\s+Date of Birth', text)
    dob_m    = re.search(r'Date of Birth\s+(\d{2}\s*/\s*\d{2}\s*/\s*\d{4})', text)
    gender_m = re.search(r'Gender\s+(Male|Female|Other)', text, re.I)
    dep_m    = re.search(r'No\. of Dependants\s+(\d+)', text)
    marital_m= re.search(r'Marital Status\s+(Single|Married|Divorced|Widowed)', text, re.I)

    return {
        'full_name':      name_m.group(1).title().strip() if name_m else "",
        'date_of_birth':  dob_m.group(1).replace(' ', '') if dob_m else "",
        'gender':         gender_m.group(1).title() if gender_m else "",
        'dependants':     int(dep_m.group(1)) if dep_m else 0,
        'marital_status': marital_m.group(1).title() if marital_m else "",
    }


def parse_kyc(text: str) -> dict:
    pan_m    = re.search(r'PAN Card\s+([A-Z0-9]+)', text)
    mobile_m = re.search(r'Mobile\s+([\d\s]+?)(?:\s+Email|\n)', text)
    email_m  = re.search(r'Email\s+([\w.@]+)', text)
    addr_m   = re.search(r'Residence\s*\n?Address\s+(.+?)(?:\nResidence Type|\Z)', text, re.S)
    res_m    = re.search(r'Residence Type\s+(Rented|Owned|Family)', text, re.I)
    yrs_m    = re.search(r'Years at Address\s+(\d+)', text)

    return {
        'pan':              pan_m.group(1) if pan_m else "",
        'mobile':           clean_text(mobile_m.group(1)) if mobile_m else "",
        'email':            email_m.group(1) if email_m else "",
        'address':          clean_text(addr_m.group(1)) if addr_m else "",
        'residence_type':   res_m.group(1).title() if res_m else "",
        'years_at_address': int(yrs_m.group(1)) if yrs_m else 0,
    }


def parse_employment(text: str) -> dict:
    emp_m      = re.search(r'Employment Type\s+(.+?)(?:Platform|\n)', text)
    platform_m = re.search(r'Platform\s+(.+?)(?:\n|$)', text)
    income_m   = re.search(r'(?:Monthly Platform|Monthly\s*\n?Income)[^\n]*?INR\s*([\d,]+)', text, re.S | re.I)
    if not income_m:
        income_m = re.search(r'INR\s*([\d,]+)\s+Income Proof', text, re.I)
    since_m    = re.search(r'Working Since\s+(.+?)(?:City|\n)', text)
    city_m     = re.search(r'City\s*/\s*Tier\s+(.+?)(?:\n|$)', text)
    emi_m      = re.search(r'Existing EMI\s*\n?Obligations\s+(NIL|[\d,]+)', text, re.I | re.S)
    expense_m  = re.search(r'Monthly Living\s*\n?Expenses.*?INR\s*([\d,]+)', text, re.S)

    return {
        'employment_type': clean_text(emp_m.group(1)) if emp_m else "Gig Worker",
        'platform':        clean_text(platform_m.group(1)) if platform_m else "",
        'monthly_income':  clean_amount(income_m.group(1)) if income_m else 0.0,
        'working_since':   clean_text(since_m.group(1)) if since_m else "",
        'city_tier':       clean_text(city_m.group(1)) if city_m else "",
        'existing_emi':    0.0 if (emi_m and 'nil' in emi_m.group(1).lower()) else
                           clean_amount(emi_m.group(1)) if emi_m else 0.0,
        'monthly_expenses':clean_amount(expense_m.group(1)) if expense_m else 0.0,
    }


def parse_loan_details(text: str) -> dict:
    # Loan type
    lt_m = re.search(r'Loan Type\s+(.+?)(?:Purpose|\n)', text)
    raw_lt = clean_text(lt_m.group(1)) if lt_m else ""
    if 'vehicle' in raw_lt.lower() or 'two' in raw_lt.lower() or 'bike' in raw_lt.lower():
        loan_type = 'vehicle'
    else:
        loan_type = 'personal'

    purpose_m   = re.search(r'Purpose\s+(.+?)(?:\n|Vehicle Make)', text)
    make_m      = re.search(r'Vehicle Make\s*/\s*Model\s+(.+?)(?:Vehicle On-Road|\n)', text)
    price_m     = re.search(r'Vehicle On-Road\s*\n?Price\s+INR\s*([\d,]+)', text, re.S | re.I)
    down_m      = re.search(r'Down Payment\s+INR\s*([\d,]+)', text, re.I)
    req_m       = re.search(r'Loan Requested\s+INR\s*([\d,]+)', text, re.I)
    tenure_m    = re.search(r'Preferred Tenure\s+(\d+)\s*Months', text, re.I)
    ev_m        = re.search(r'EV Preference\s+(No|Yes)', text, re.I)
    new_used_m  = re.search(r'New\s*/\s*Used Vehicle\s+(New|Used)', text, re.I)

    return {
        'loan_type':           loan_type,
        'loan_type_raw':       raw_lt,
        'purpose':             clean_text(purpose_m.group(1)) if purpose_m else "",
        'vehicle_model':       clean_text(make_m.group(1)) if make_m else "",
        'vehicle_price':       clean_amount(price_m.group(1)) if price_m else 0.0,
        'down_payment':        clean_amount(down_m.group(1)) if down_m else 0.0,
        'requested_amount':    int(clean_amount(req_m.group(1))) if req_m else 0,
        'tenure_preference_m': int(tenure_m.group(1)) if tenure_m else 12,
        'ev_preference':       ev_m.group(1).lower() == 'yes' if ev_m else False,
        'new_or_used':         new_used_m.group(1) if new_used_m else "New",
    }


def parse_bank_details(text: str) -> dict:
    bank_m   = re.search(r'Bank Name\s+(.+?)(?:Account Type|\n)', text)
    acc_m    = re.search(r'Account Number\s+([\d\s]+?)(?:IFSC|\n)', text)
    ifsc_m   = re.search(r'IFSC Code\s+([A-Z0-9]+)', text)
    branch_m = re.search(r'Branch\s+(.+?)(?:Account Since|\n)', text)
    since_m  = re.search(r'Account Since\s+(.+?)(?:\n|$)', text)

    return {
        'bank_name':       clean_text(bank_m.group(1)) if bank_m else "",
        'account_number':  clean_text(acc_m.group(1)) if acc_m else "",
        'ifsc':            ifsc_m.group(1) if ifsc_m else "",
        'branch':          clean_text(branch_m.group(1)) if branch_m else "",
        'account_since':   clean_text(since_m.group(1)) if since_m else "",
    }


def parse_gigscore_section(text: str) -> dict:
    """Parse Section F — GigScore behavioral signals."""
    oblig_m  = re.search(r'Obligation fulfillment rate\s+([\d.]+)', text)
    streak_m = re.search(r'Utility payment streak\s+(\d+)', text)
    cv_m     = re.search(r'Income regularity.*?CV\)\s+([\d.]+)', text)
    ior_m    = re.search(r'Inflow\s*/\s*outflow ratio\s+([\d.]+)', text)
    div_m    = re.search(r'Merchant diversity score\s+([\d.]+)', text)
    crunch_m = re.search(r'Cash crunch recovery speed\s+([\d.]+)', text)
    trust_m  = re.search(r'Social Trust Graph score\s+([\d.]+)', text)
    nodes_m  = re.search(r'Social Trust Graph score.*?\((\d+)\s+unique nodes\)', text)
    score_m  = re.search(r'GigScore\s+([\d.]+)\s*/\s*100', text)
    band_m   = re.search(r'Band\s+([\d\s–-]+)\s*\((.+?)\)', text)
    cibil_m  = re.search(r'CIBIL Equivalent\s+([\d\s–-]+)', text)

    # Social trust: PDF stores as 0–1 scale, convert to 0–100
    raw_trust = float(trust_m.group(1)) if trust_m else None
    if raw_trust is not None and raw_trust <= 1.0:
        social_trust_score = round(raw_trust * 100, 1)
    elif raw_trust is not None:
        social_trust_score = round(raw_trust, 1)
    else:
        social_trust_score = None

    return {
        'obligation_fulfillment': float(oblig_m.group(1)) if oblig_m else None,
        'utility_payment_streak': int(streak_m.group(1)) if streak_m else None,
        'income_regularity_cv':   float(cv_m.group(1)) if cv_m else None,
        'inflow_outflow_ratio':   float(ior_m.group(1)) if ior_m else None,
        'merchant_diversity':     float(div_m.group(1)) if div_m else None,
        'crunch_recovery_speed':  float(crunch_m.group(1)) if crunch_m else None,
        'social_trust_score':     social_trust_score,   # 0–100 scale
        'unique_trust_nodes':     int(nodes_m.group(1)) if nodes_m else None,
        'gigscore':               float(score_m.group(1)) if score_m else None,
        'gigscore_band':          clean_text(band_m.group(1)) if band_m else None,
        'gigscore_tier':          clean_text(band_m.group(2)) if band_m else None,
        'cibil_equivalent':       clean_text(cibil_m.group(1)) if cibil_m else None,
    }


def parse_decision_section(text: str) -> dict:
    """Parse Section G — pre-filled loan decision (if any)."""
    decision_m  = re.search(r'(CONDITIONALLY APPROVED|APPROVED|DECLINED)', text, re.I)
    approved_m  = re.search(r'Approved Loan Amount\s+INR\s*([\d,]+)', text, re.I)
    rate_m      = re.search(r'Interest Rate\s+([\d.]+)%', text)
    tenure_m    = re.search(r'Tenure\s+(\d+)\s*Months', text)
    emi_m       = re.search(r'Monthly EMI\s+INR\s*([\d,]+)', text, re.I)
    fee_m       = re.search(r'Processing Fee.*?INR\s*([\d,]+)', text, re.I)
    interest_m  = re.search(r'Total Interest Payable\s+INR\s*([\d,]+)', text, re.I)
    total_m     = re.search(r'Total Repayment\s+INR\s*([\d,]+)', text, re.I)
    foir_m      = re.search(r'FOIR Used\s+([\d.]+)%', text)
    saved_m     = re.search(r'Interest Saved.*?INR\s*([\d,]+)', text, re.I)

    return {
        'decision':          clean_text(decision_m.group(1)).upper() if decision_m else None,
        'approved_amount':   int(clean_amount(approved_m.group(1))) if approved_m else None,
        'interest_rate_pct': float(rate_m.group(1)) if rate_m else None,
        'tenure_months':     int(tenure_m.group(1)) if tenure_m else None,
        'monthly_emi':       clean_amount(emi_m.group(1)) if emi_m else None,
        'processing_fee':    clean_amount(fee_m.group(1)) if fee_m else None,
        'total_interest':    clean_amount(interest_m.group(1)) if interest_m else None,
        'total_repayment':   clean_amount(total_m.group(1)) if total_m else None,
        'foir_used_pct':     float(foir_m.group(1)) if foir_m else None,
        'interest_saved_vs_market': clean_amount(saved_m.group(1)) if saved_m else None,
    }


# ─────────────────────────────────────────────────────────────────────────
# MAIN PARSER
# ─────────────────────────────────────────────────────────────────────────

def parse_loan_application(pdf_path: str) -> dict:
    """
    Parse GigScore Loan Application PDF → clean structured dict.
    """
    if not Path(pdf_path).exists():
        print(f"❌ PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"  Parsing: {pdf_path}")
    full_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += "\n" + text

    # Extract app number and date
    appno_m = re.search(r'App No[:\s]+([A-Z0-9-]+)', full_text)
    date_m  = re.search(r'Date:\s*(\d{1,2}\s+\w+\s+\d{4})', full_text)

    # Parse all sections
    personal   = parse_personal(full_text)
    kyc        = parse_kyc(full_text)
    employment = parse_employment(full_text)
    loan       = parse_loan_details(full_text)
    bank       = parse_bank_details(full_text)
    gigscore   = parse_gigscore_section(full_text)
    decision   = parse_decision_section(full_text)

    # Build persona_id from name
    persona_id = personal['full_name'].lower().replace(' ', '_') if personal['full_name'] \
                 else Path(pdf_path).stem

    # Build the application dict Agent 6 expects
    application = {
        # Metadata
        'app_number':       appno_m.group(1) if appno_m else "",
        'application_date': date_m.group(1) if date_m else "",
        'persona_id':       persona_id,

        # What Agent 6 needs directly
        'applicant_name':      personal['full_name'],
        'loan_type':           loan['loan_type'],
        'requested_amount':    loan['requested_amount'],
        'tenure_preference_m': loan['tenure_preference_m'],
        'loan_purpose_detail': loan['purpose'],
        'has_existing_loan':   employment['existing_emi'] > 0,
        'monthly_expense_est': employment['monthly_expenses'],
        'ev_preference':       loan['ev_preference'],

        # Full personal details
        'personal':    personal,
        'kyc':         kyc,
        'employment':  employment,
        'loan_details':loan,
        'bank':        bank,

        # GigScore signals from form (cross-check with Agent 2 output)
        'gigscore_from_form':  gigscore,

        # Pre-filled decision (if system already ran)
        'pre_filled_decision': decision,
    }

    return application


# ─────────────────────────────────────────────────────────────────────────
# PRINT SUMMARY
# ─────────────────────────────────────────────────────────────────────────

def print_summary(app: dict):
    p  = app['personal']
    e  = app['employment']
    l  = app['loan_details']
    gs = app['gigscore_from_form']
    d  = app['pre_filled_decision']

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║          LOAN APPLICATION PARSED — GIGSCORE                     ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  App Number      : {app['app_number']:<46}║")
    print(f"║  Applicant       : {p['full_name']:<46}║")
    print(f"║  Platform        : {e['platform']:<46}║")
    print(f"║  Monthly Income  : ₹{e['monthly_income']:>10,.2f}                             ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Loan Type       : {l['loan_type_raw']:<46}║")
    print(f"║  Purpose         : {l['purpose'][:45]:<46}║")
    print(f"║  Requested       : ₹{l['requested_amount']:>10,}                             ║")
    print(f"║  Tenure          : {l['tenure_preference_m']} months                                         ║")
    print(f"║  EV Preference   : {'Yes' if l['ev_preference'] else 'No':<46}║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    if gs.get('gigscore'):
        tier_str   = str(gs.get('gigscore_tier') or 'N/A')
        trust_val  = gs.get('social_trust_score')
        trust_str  = f"{trust_val:.1f} / 100" if trust_val is not None else "N/A"
        streak_val = gs.get('utility_payment_streak')
        streak_str = str(streak_val) if streak_val is not None else "N/A"
        nodes_val  = gs.get('unique_trust_nodes')
        nodes_str  = f" ({nodes_val} nodes)" if nodes_val else ""
        print(f"║  GigScore (form) : {gs['gigscore']:.1f} / 100  ({tier_str}){'':>18}║")
        print(f"║  Social Trust    : {trust_str}{nodes_str:<38}║")
        print(f"║  Utility Streak  : {streak_str} months{'':>38}║")
    if d.get('decision'):
        print("╠══════════════════════════════════════════════════════════════╣")
        print(f"║  Decision        : {d['decision']:<46}║")
        if d.get('approved_amount'):
            print(f"║  Approved        : ₹{d['approved_amount']:>10,} @ {d.get('interest_rate_pct','?')}%               ║")
            print(f"║  EMI             : ₹{d.get('monthly_emi',0):>10,.2f}                             ║")
            print(f"║  FOIR Used       : {d.get('foir_used_pct','?')}%                                           ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  persona_id      : {app['persona_id']:<46}║")
    print("╚══════════════════════════════════════════════════════════════════╝")


# ─────────────────────────────────────────────────────────────────────────
# SAVE FOR AGENT 6
# ─────────────────────────────────────────────────────────────────────────

def save_for_agent6(app: dict, output_path: str = DEFAULT_OUT):
    """
    Save in the format Agent 6 expects:
    { "raju_sharma": { applicant_name, loan_type, requested_amount, ... } }
    """
    persona_id = app['persona_id']

    agent6_format = {
        persona_id: {
            'applicant_name':      app['applicant_name'],
            'loan_type':           app['loan_type'],
            'requested_amount':    app['requested_amount'],
            'tenure_preference_m': app['tenure_preference_m'],
            'loan_purpose_detail': app['loan_purpose_detail'],
            'has_existing_loan':   app['has_existing_loan'],
            'monthly_expense_est': app['monthly_expense_est'],
            'ev_preference':       app['ev_preference'],
        }
    }

    with open(output_path, 'w') as f:
        json.dump(agent6_format, f, indent=2)

    # Also save full parsed application for reference
    full_path = output_path.replace('.json', '_full.json')
    with open(full_path, 'w') as f:
        json.dump(app, f, indent=2, default=str)

    print(f"\n  📄 Agent 6 input  → {output_path}")
    print(f"  📄 Full parsed    → {full_path}")


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse GigScore Loan Application PDF → loan_application.json"
    )
    parser.add_argument('pdf',   nargs='?', default=DEFAULT_PDF,
                        help='Path to loan application PDF')
    parser.add_argument('--out', default=DEFAULT_OUT,
                        help='Output JSON path (default: loan_application.json)')
    args = parser.parse_args()

    print("=" * 68)
    print("GigScore — Loan Application PDF Parser")
    print("Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University")
    print("=" * 68)

    app = parse_loan_application(args.pdf)
    print_summary(app)
    save_for_agent6(app, args.out)

    print(f"\n  ✅ Done. Run Agent 6:")
    print(f"     python3 agent6.py --app {args.out}")