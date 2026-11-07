"""
GigScore — Agent 0: Bank Statement Parser
==========================================
Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University

Hardcoded for: gigscore_statement_raju_sharma.pdf
Format:        IndiaFirst Bank — 151 pages
               5-column transaction table: Date | Narration | Debit | Credit | Balance

Outputs:
    agent0_output.json      — clean transactions + audit log
    agent0_features.csv     — all behavioral features for Agent 1

FIXES APPLIED:
    1. monthly_avg     — median of non-zero earning months (not mean over 18m)
    2. income_cv       — all monthly credits CV (not just platform trips)
    3. inflow_outflow  — platform_inflow / total_debits (gig earnings vs spending)
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import pandas as pd
import numpy as np
from scipy.stats import entropy as scipy_entropy

# ── Hardcoded file names ──────────────────────────────────────────────────
PDF_PATH     = "gigscore_statement_raju_sharma.pdf"
OUTPUT_JSON  = "agent0_output.json"
FEATURES_CSV = "agent0_features.csv"
PII_SALT     = "gigscore_demo_salt_barclays_2026"

# ── Loan application defaults for Raju ───────────────────────────────────
LOAN_AMOUNT      = 45000
APPLICATION_HOUR = 10
REGION_RATING    = 2  # Tier 2 city


# ─────────────────────────────────────────────────────────────────────────
# PII HASHING
# ─────────────────────────────────────────────────────────────────────────

def _hash(raw: str, prefix: str) -> str:
    digest = hashlib.sha256(
        f"{PII_SALT}:{raw.strip().lower()}".encode()
    ).hexdigest()[:12]
    return f"{prefix}_{digest}"


# ─────────────────────────────────────────────────────────────────────────
# MCC CATEGORY MAP
# ─────────────────────────────────────────────────────────────────────────

NARRATION_KEYWORDS = [
    # TRIP PAYMENT first — catches swiggy.settlement before INFORMAL_LOAN
    (re.compile(r"\bTRIP\s+PAYMENT\b", re.I),                                                         "PLATFORM_INCOME"),
    (re.compile(r"\bSWIGGY\b|\bZOMATO\b|\bUBER\b|\bOLA\b|\bRAPIDO\b|\bBLINKIT\b|\bDUNZO\b|\bDELIVERY\b", re.I), "PLATFORM_INCOME"),
    (re.compile(r"\bURBAN\s*COMPANY\b|\bURBANCOMPANY\b|\bSERVICE\s+PAYMENT\b",                        re.I), "PLATFORM_INCOME"),
    (re.compile(r"\bSALARY\b|\bSTIPEND\b|\bWAGES\b|\bSETTLEMENT\b",                                  re.I), "PLATFORM_INCOME"),
    (re.compile(r"\bPM[\s\-]KISAN\b|\bDBT\b|\bMNREGA\b|\bSVANIDHI\b|\bGOVT\b",                       re.I), "GOVT_TRANSFER"),
    (re.compile(r"\bRENT\b|\bLEASE\b|\bHOUSE\s+RENT\b",                                               re.I), "RENT"),
    (re.compile(r"\bPETROL\b|\bDIESEL\b|\bFUEL\b|\bBPCL\b|\bIOCL\b|\bHP\s*PETROL\b",                re.I), "FUEL"),
    (re.compile(r"\bELECTRICITY\b|\bBESCOM\b|\bTNEB\b|\bBSES\b|\bMSEB\b|\bPOWER\b|\bLPG\b|\bGAS\b|\bINDANE\b", re.I), "UTILITY"),
    (re.compile(r"\bAIRTEL\b|\bJIO\b|\bBSNL\b|\bVI\b|\bRECHARGE\b|\bMOBILE\b|\bWATER\s+CAN\b|\bWATER\s+BILL\b", re.I), "TELECOM"),
    (re.compile(r"\bSCHOOL\b|\bCOLLEGE\b|\bFEES\b|\bTUITION\b|\bEDUCATION\b",                       re.I), "EDUCATION"),
    (re.compile(r"\bHOSPITAL\b|\bCLINIC\b|\bPHARMACY\b|\bDOCTOR\b|\bMEDIC\b|\bCHEMIST\b",          re.I), "MEDICAL"),
    (re.compile(r"\bINSURANCE\b|\bLIC\b|\bPREMIUM\b|\bPOLICY\b",                                     re.I), "INSURANCE"),
    (re.compile(r"\bEMI\b|\bLOAN\s+REPAY\b|\bNBFC\b|\bFAMILY\s+LOAN\b|\bNACH\b|\bECS\b",            re.I), "EMI_LOAN"),
    (re.compile(r"\bSIP\b|\bMUTUAL\s+FUND\b|\bRD\b|\bRECURRING\s+DEPOSIT\b|\bFD\b|\bPPF\b",         re.I), "SAVINGS"),
    (re.compile(r"\bCHIT\s+FUND\b|\bROSCA\b|\bCHIT\b",                                               re.I), "CHIT_FUND"),
    (re.compile(r"\bTEMPLE\b|\bMOSQUE\b|\bCHURCH\b|\bTRUST\b|\bDONATION\b|\bDAAN\b|\bRAKHI\b",     re.I), "RELIGIOUS_DONATION"),
    (re.compile(r"\bNETFLIX\b|\bHOTSTAR\b|\bSPOTIFY\b|\bCINEMA\b|\bMOVIE\b|\bSTREAMING\b|\bDREAM11\b", re.I), "ENTERTAINMENT"),
    (re.compile(r"\bRESTAURANT\b|\bCAFE\b|\bDHABA\b|\bFOOD\s+ORDER\b|\bSWEETS\b",                   re.I), "DINING"),
    (re.compile(r"\bGROCERY\b|\bKIRANA\b|\bVEGETABLE\b|\bSUPERMARKET\b|\bBIGBASKET\b|\bDMART\b",   re.I), "GROCERY"),
    (re.compile(r"\bTRAIN\b|\bIRCTC\b|\bBUS\b|\bFLIGHT\b|\bMETRO\b|\bAUTO\s+FARE\b|\bCAB\b",       re.I), "TRANSPORT"),
    (re.compile(r"\bFAMILY\s+TRANSFER\b|\bSEND\s+HOME\b|\bFAMILY\b",                                 re.I), "FAMILY_TRANSFER"),
    (re.compile(r"\bMEESHO\b|\bMYNTRA\b|\bNYKAA\b|\bAJIO\b|\bFASHION\b|\bCLOTHING\b",              re.I), "FASHION"),
    (re.compile(r"\bDIWALI\b|\bHOLI\b|\bCRACKER\b|\bGIFT\b|\bRAKSHABANDHAN\b",                     re.I), "FESTIVAL_SPEND"),
    (re.compile(r"\bLOAN\s+ADV\b|\bLOAN\s+ADVANCE\b",                                                re.I), "INFORMAL_LOAN"),
    (re.compile(r"\bATM\b|\bCASH\s+WITH",                                                             re.I), "ATM_CASH"),
    (re.compile(r"\bWALLET\b|\bPARKING\b|\bSTATIONARY\b|\bTEA\b|\bSNACKS\b|\bLAUNDRY\b|\bMILK\b",  re.I), "DAILY_EXPENSE"),
]

VPA_PATTERN = re.compile(
    r"\b[\w.\-]+@(?:okicici|oksbi|okhdfcbank|okaxis|ybl|paytm|upi|"
    r"ibl|aubank|kotak|rbl|icici|hdfc|sbi|axis|pnb|axisbank|"
    r"hdfcbank|sbibank|indus|federal|idbi|barodampay)\b",
    re.IGNORECASE,
)


def resolve_category(narration: str) -> str:
    for pattern, category in NARRATION_KEYWORDS:
        if pattern.search(narration):
            return category
    return "OTHER"


def parse_amount(s: str) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def parse_date(s: str) -> str:
    s = (s or "").strip()
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return s


def is_txn_header(row: list) -> bool:
    if not row or len(row) < 5:
        return False
    joined = " ".join(str(c or "").lower() for c in row)
    return "date" in joined and "narration" in joined and "balance" in joined


def is_txn_row(row: list) -> bool:
    if not row or len(row) < 5:
        return False
    return bool(re.match(r"\d{2}/\d{2}/\d{4}", str(row[0] or "").strip()))


# ─────────────────────────────────────────────────────────────────────────
# STEP 1: PARSE PDF
# ─────────────────────────────────────────────────────────────────────────

def parse_pdf(pdf_path: str) -> tuple:
    HEADER_MAP = {
        "customer id": "customer_id",       "account id": "account_number",
        "statement period": "statement_period", "customer name": "name",
        "address": "address",               "email": "email",
        "phone": "phone",                   "pan": "kyc_id",
        "aadhaar": "kyc_id",               "branch": "branch",
        "ifsc": "ifsc",                     "micr": "micr",
        "account type": "account_type",     "account status": "account_status",
        "currency": "currency",
    }

    header, raw_txns = {}, []
    print(f"  Parsing {pdf_path}...")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"  Total pages: {total_pages}")

        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                if not table:
                    continue
                # 2-column = header table
                if len(table[0]) == 2 and not is_txn_header(table[0]):
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        key = str(row[0] or "").strip().lower()
                        val = str(row[1] or "").strip()
                        if key in HEADER_MAP and val:
                            header[HEADER_MAP[key]] = val
                # 5-column = transaction table
                elif len(table[0]) >= 5:
                    for row in table:
                        if is_txn_header(row) or not is_txn_row(row):
                            continue
                        debit  = parse_amount(str(row[2] or ""))
                        credit = parse_amount(str(row[3] or ""))
                        direction, amount = ("CR", credit) if credit > 0 and debit == 0 \
                                            else ("DR", debit)
                        if amount == 0:
                            continue
                        raw_txns.append({
                            "date":            parse_date(str(row[0] or "")),
                            "amount":          amount,
                            "direction":       direction,
                            "narration":       str(row[1] or "").strip(),
                            "running_balance": parse_amount(str(row[4] or "")),
                        })

    print(f"  Parsed {len(raw_txns):,} transactions from {total_pages} pages")
    return header, raw_txns


# ─────────────────────────────────────────────────────────────────────────
# STEP 2: PII REDACTION
# ─────────────────────────────────────────────────────────────────────────

def redact_and_categorize(header: dict, raw_txns: list) -> dict:
    raw_account     = header.get("account_number", "")
    applicant_token = _hash(raw_account or datetime.now(timezone.utc).isoformat(), "APPL")

    vpa_cache, clean_txns = {}, []

    for txn in raw_txns:
        narration = txn["narration"]
        vpa_match = VPA_PATTERN.search(narration)
        raw_vpa   = vpa_match.group(0) if vpa_match else ""

        if raw_vpa:
            if raw_vpa not in vpa_cache:
                vpa_cache[raw_vpa] = _hash(raw_vpa, "NODE")
            counterparty = vpa_cache[raw_vpa]
        else:
            counterparty = "NODE_atm_cash_sentinel"

        clean_txns.append({
            "date":               txn["date"],
            "amount":             txn["amount"],
            "direction":          txn["direction"],
            "narration_clean":    VPA_PATTERN.sub("[VPA]", narration).strip(),
            "mcc_category":       resolve_category(narration),
            "running_balance":    txn["running_balance"],
            "counterparty_token": counterparty,
        })

    return {
        "applicant_token": applicant_token,
        "transactions":    clean_txns,
        "audit_log": {
            "applicant_token":      applicant_token,
            "total_transactions":   len(clean_txns),
            "unique_vpa_nodes":     len(vpa_cache),
            "dpdp_compliant":       True,
            "processing_timestamp": datetime.now(timezone.utc).isoformat(),
            "fields_redacted":      ["name", "account_number", "ifsc", "phone",
                                     "email", "address", "kyc_id"],
            "pseudonymisation":     "SHA-256 salted 12-char hex",
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# STEP 3: BEHAVIORAL FEATURE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────

def extract_features(transactions: list,
                     loan_amount:      float = LOAN_AMOUNT,
                     application_hour: int   = APPLICATION_HOUR,
                     region_rating:    int   = REGION_RATING) -> dict:
    eps = 1e-6

    if not transactions:
        return {}

    df = pd.DataFrame(transactions)
    df['date']  = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    credits = df[df['direction'] == 'CR'].copy()
    debits  = df[df['direction'] == 'DR'].copy()

    # ── Income estimation ─────────────────────────────────────────────────
    platform_cr = credits[credits['mcc_category'] == 'PLATFORM_INCOME']
    monthly_pl  = platform_cr.groupby('month')['amount'].sum()
    n_months    = max(df['month'].nunique(), 1)

    # FIX 1: median of non-zero earning months avoids 18-month dilution
    # (gives ₹53K not ₹26K for Raju)
    nonzero    = monthly_pl[monthly_pl > 0]
    monthly_avg = float(nonzero.median()) if len(nonzero) > 0 \
                  else (credits['amount'].sum() / n_months)

    amt_income_annual = monthly_avg * 12
    total_credits     = credits['amount'].sum()
    total_debits      = debits['amount'].sum()
    platform_inflow   = platform_cr['amount'].sum()

    # Employment duration from first gig credit
    if len(platform_cr) > 0:
        days_employed = max((df['date'].max() - platform_cr['date'].min()).days, 1)
    else:
        days_employed = 180
    years_employed = days_employed / 365.25
    age_days       = 32 * 365
    age_years      = age_days / 365.25

    # ── Feature 1: income_regularity_cv ──────────────────────────────────
    # FIX 2: all monthly credits CV — platform micro-trips too uniform → CV=0
    monthly_all_cr = credits.groupby('month')['amount'].sum()
    upi_income_regularity_cv = (
        monthly_all_cr.std() / (monthly_all_cr.mean() + eps)
        if len(monthly_all_cr) >= 2 else 0.35
    )

    # ── Feature 2: utility_payment_streak ────────────────────────────────
    utility_cats = {'UTILITY', 'TELECOM'}
    all_months   = pd.period_range(df['month'].min(), df['month'].max(), freq='M')
    has_utility  = (
        df[df['mcc_category'].isin(utility_cats)]
        .groupby('month').size().gt(0)
        .reindex(all_months, fill_value=False)
    )
    streak = best_streak = 0
    for has in has_utility:
        streak = streak + 1 if has else 0
        best_streak = max(best_streak, streak)
    upi_utility_payment_streak = best_streak

    # ── Feature 3: cash_crunch_recovery_speed ────────────────────────────
    monthly_cnt = df.groupby('month').size()
    median_cnt  = monthly_cnt.median()
    months_list = list(monthly_cnt.index)
    recovery_ratios = []
    for m in monthly_cnt[monthly_cnt < median_cnt].index:
        idx = months_list.index(m)
        if idx + 1 < len(months_list):
            recovery_ratios.append(monthly_cnt.iloc[idx + 1] / (monthly_cnt[m] + eps))
    upi_cash_crunch_recovery_speed = float(np.mean(recovery_ratios)) if recovery_ratios else 1.2

    # ── Feature 4: spending_velocity ─────────────────────────────────────
    monthly_spend = debits.groupby('month')['amount'].sum()
    upi_spending_velocity = (
        monthly_spend.std() / (monthly_spend.mean() + eps)
        if len(monthly_spend) >= 2 else 0.20
    )

    # ── Feature 5: merchant_diversity_score ──────────────────────────────
    cat_counts = debits['mcc_category'].value_counts(normalize=True)
    if len(cat_counts) > 1:
        raw_ent = scipy_entropy(cat_counts)
        max_ent = np.log(len(cat_counts))
        upi_merchant_diversity_score = raw_ent / max_ent if max_ent > 0 else 0.0
    else:
        upi_merchant_diversity_score = 0.0

    # ── Feature 6: inflow_outflow_ratio ──────────────────────────────────
    # FIX 3: platform_inflow / total_debits
    # (gig earnings vs total spending — matches original model training)
    upi_inflow_outflow_ratio = platform_inflow / (total_debits + eps)

    # ── Feature 7: recurring_payment_ratio ───────────────────────────────
    sorted_months  = sorted(df['month'].unique())
    recurring_cats = set()
    for i in range(len(sorted_months) - 1):
        now = set(debits[debits['month'] == sorted_months[i]]['mcc_category'])
        nxt = set(debits[debits['month'] == sorted_months[i + 1]]['mcc_category'])
        recurring_cats |= (now & nxt)
    upi_recurring_payment_ratio = len(recurring_cats) / (debits['mcc_category'].nunique() + eps)

    # ── Feature 8: obligation_fulfillment_rate ────────────────────────────
    rent_months = set(df[df['mcc_category'] == 'RENT']['month'])
    util_months = set(df[df['mcc_category'].isin(utility_cats)]['month'])
    upi_obligation_fulfillment_rate = len(rent_months & util_months) / max(n_months, 1)

    # ── Derived ratios ────────────────────────────────────────────────────
    credit_income_ratio  = loan_amount / (monthly_avg + eps)
    annuity_income_ratio = (loan_amount / 12) / (monthly_avg + eps)
    late_flag            = 1 if application_hour >= 22 or application_hour <= 5 else 0

    # ── Proxy behavioral features (Agent 1 Cell 24) ──────────────────────
    income_instability_proxy    = min(0 / (age_days + eps), 5)
    credit_seeking_intensity    = min(0 / (years_employed + 1), 20)
    stress_signal               = min(late_flag * credit_income_ratio, 20)
    lifestyle_stability         = 3 / (region_rating + eps)
    repayment_stretch           = min(annuity_income_ratio * region_rating, 10)
    credit_utilization_pressure = min(loan_amount / (monthly_avg * (years_employed + 1) + eps), 50)
    digital_engagement_proxy    = 2

    return {
        # ── Metadata ─────────────────────────────────────────────────────
        'persona_id':       'raju_sharma',
        'applicant_token':  '',

        # ── Home Credit proxy columns (Agent 1 Cell 8) ───────────────────
        'AMT_INCOME_TOTAL':               round(amt_income_annual, 2),
        'AMT_INCOME_MONTHLY':             round(monthly_avg, 2),
        'AMT_CREDIT':                     loan_amount,
        'AMT_ANNUITY':                    round(loan_amount / 12, 2),
        'AMT_GOODS_PRICE':                round(loan_amount * 0.9, 2),
        'DAYS_EMPLOYED':                  -days_employed,
        'DAYS_BIRTH':                     -age_days,
        'CNT_CHILDREN':                   0,
        'CNT_FAM_MEMBERS':                3,
        'REGION_RATING_CLIENT':           region_rating,
        'REGION_RATING_CLIENT_W_CITY':    region_rating,
        'REG_CITY_NOT_WORK_CITY':         0,
        'REG_CITY_NOT_LIVE_CITY':         0,
        'LIVE_CITY_NOT_WORK_CITY':        0,
        'FLAG_EMP_PHONE':                 0,
        'FLAG_WORK_PHONE':                1,
        'FLAG_CONT_MOBILE':               1,
        'FLAG_EMAIL':                     0,
        'DAYS_LAST_PHONE_CHANGE':         0,
        'HOUR_APPR_PROCESS_START':        application_hour,
        'AMT_REQ_CREDIT_BUREAU_DAY':      0,
        'AMT_REQ_CREDIT_BUREAU_WEEK':     0,
        'AMT_REQ_CREDIT_BUREAU_MON':      0,
        'AMT_REQ_CREDIT_BUREAU_YEAR':     0,
        'EXT_SOURCE_1':                   None,
        'EXT_SOURCE_2':                   None,
        'EXT_SOURCE_3':                   None,

        # ── Engineered ratios (Agent 1 Cell 9) ───────────────────────────
        'age':                            round(age_years, 2),
        'years_employed':                 round(years_employed, 2),
        'credit_income_ratio':            round(credit_income_ratio, 4),
        'annuity_income_ratio':           round(annuity_income_ratio, 4),
        'goods_income_ratio':             round((loan_amount * 0.9) / (amt_income_annual + eps), 4),
        'credit_annuity_ratio':           round(loan_amount / (loan_amount / 12 + eps), 4),
        'income_annuity_ratio':           round(monthly_avg / (loan_amount / 12 + eps), 4),
        'income_credit_ratio':            round(amt_income_annual / (loan_amount + eps), 4),
        'employment_age_ratio':           round(years_employed / (age_years + eps), 4),
        'phone_change_ratio':             0.0,
        'bureau_requests':                0,
        'ext_source_mean':                None,
        'ext_source_std':                 None,
        'ext_source_min':                 None,
        'late_application_flag':          late_flag,
        'children_ratio':                 0.0,
        'income_per_person':              round(amt_income_annual / (3 + eps), 2),

        # ── Proxy behavioral features (Agent 1 Cell 24) ──────────────────
        'income_instability_proxy':       round(income_instability_proxy, 4),
        'credit_seeking_intensity':       round(credit_seeking_intensity, 4),
        'stress_signal':                  round(stress_signal, 4),
        'lifestyle_stability':            round(lifestyle_stability, 4),
        'repayment_stretch':              round(repayment_stretch, 4),
        'credit_utilization_pressure':    round(credit_utilization_pressure, 4),
        'digital_engagement_proxy':       digital_engagement_proxy,

        # ── 8 UPI behavioral velocity features ───────────────────────────
        'upi_income_regularity_cv':        round(float(upi_income_regularity_cv), 4),
        'upi_utility_payment_streak':      int(upi_utility_payment_streak),
        'upi_cash_crunch_recovery_speed':  round(upi_cash_crunch_recovery_speed, 4),
        'upi_spending_velocity':           round(float(upi_spending_velocity), 4),
        'upi_merchant_diversity_score':    round(float(upi_merchant_diversity_score), 4),
        'upi_inflow_outflow_ratio':        round(float(upi_inflow_outflow_ratio), 4),
        'upi_recurring_payment_ratio':     round(float(upi_recurring_payment_ratio), 4),
        'upi_obligation_fulfillment_rate': round(upi_obligation_fulfillment_rate, 4),

        # ── Additional UPI stats ──────────────────────────────────────────
        'upi_total_txns':                 len(df),
        'upi_avg_amount':                 round(df['amount'].mean(), 2),
        'upi_success_rate':               1.0,
        'upi_fraud_rate':                 0.0,
        'upi_weekend_ratio':              round(float((df['date'].dt.dayofweek >= 5).mean()), 4),
        'upi_unique_merchants':           df['mcc_category'].nunique(),

        # ── Agent 2 income signal features (Cell 6) ──────────────────────
        'log_income':                     round(float(np.log1p(amt_income_annual)), 4),
        'income_percentile':              0.5,
        'income_adequacy':                round(amt_income_annual / (loan_amount + eps), 4),
        'monthly_income_vs_emi':          round(monthly_avg / (loan_amount / 12 + eps), 4),
        'income_stability_score':         round(
                                              np.log1p(amt_income_annual) *
                                              years_employed / (age_years + eps), 4),

        # ── PLFS income validation (Agent 1 Cell 28) ─────────────────────
        'plfs_benchmark_income':          180000,
        'income_vs_plfs_ratio':           round(amt_income_annual / (180000 + eps), 4),
        'income_inflation_flag':          1 if amt_income_annual > 360000 else 0,
        'income_underreport_flag':        1 if amt_income_annual < 90000  else 0,

        # ── Transaction-level behavioral counts ──────────────────────────
        'monthly_spend_avg':              round(float(monthly_spend.mean()) if len(monthly_spend) > 0 else 0, 2),
        'monthly_credit_avg':             round(float(monthly_all_cr.mean()) if len(monthly_all_cr) > 0 else 0, 2),
        'rent_payment_count':             int((df['mcc_category'] == 'RENT').sum()),
        'emi_loan_count':                 int((df['mcc_category'] == 'EMI_LOAN').sum()),
        'savings_txn_count':              int((df['mcc_category'] == 'SAVINGS').sum()),
        'platform_income_txn_count':      int((df['mcc_category'] == 'PLATFORM_INCOME').sum()),
        'fuel_txn_count':                 int((df['mcc_category'] == 'FUEL').sum()),
    }


# ─────────────────────────────────────────────────────────────────────────
# STEP 4: PRINT SUMMARY
# ─────────────────────────────────────────────────────────────────────────

def print_summary(result: dict, features: dict):
    from collections import Counter
    txns   = result['transactions']
    audit  = result['audit_log']
    cr_sum = sum(t['amount'] for t in txns if t['direction'] == 'CR')
    dr_sum = sum(t['amount'] for t in txns if t['direction'] == 'DR')
    cats   = Counter(t['mcc_category'] for t in txns)

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║              AGENT 0 COMPLETE — RAJU SHARMA                     ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Applicant token     : {result['applicant_token']:<41}║")
    print(f"║  Total transactions  : {len(txns):>5,}                                      ║")
    print(f"║  Total credits       : ₹{cr_sum:>12,.2f}                            ║")
    print(f"║  Total debits        : ₹{dr_sum:>12,.2f}                            ║")
    print(f"║  Unique VPA nodes    : {audit['unique_vpa_nodes']:>5}                                      ║")
    print(f"║  DPDP compliant      : {audit['dpdp_compliant']}                                        ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  TOP TRANSACTION CATEGORIES                                      ║")
    for cat, count in cats.most_common(6):
        pct = count / len(txns) * 100
        print(f"║  {cat:<25} {count:>5} txns ({pct:>4.1f}%)                  ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  8 BEHAVIORAL VELOCITY FEATURES                                  ║")
    print(f"║  income_regularity_cv        : {features['upi_income_regularity_cv']:<10.4f}                   ║")
    print(f"║  utility_payment_streak      : {features['upi_utility_payment_streak']:<10}                   ║")
    print(f"║  cash_crunch_recovery_speed  : {features['upi_cash_crunch_recovery_speed']:<10.4f}                   ║")
    print(f"║  spending_velocity           : {features['upi_spending_velocity']:<10.4f}                   ║")
    print(f"║  merchant_diversity_score    : {features['upi_merchant_diversity_score']:<10.4f}                   ║")
    print(f"║  inflow_outflow_ratio        : {features['upi_inflow_outflow_ratio']:<10.4f}                   ║")
    print(f"║  recurring_payment_ratio     : {features['upi_recurring_payment_ratio']:<10.4f}                   ║")
    print(f"║  obligation_fulfillment_rate : {features['upi_obligation_fulfillment_rate']:<10.4f}                   ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Monthly income (gig)        : ₹{features['AMT_INCOME_MONTHLY']:>10,.2f}                     ║")
    print(f"║  Annual income               : ₹{features['AMT_INCOME_TOTAL']:>10,.2f}                     ║")
    print(f"║  inflow_outflow_ratio        : {features['upi_inflow_outflow_ratio']:<10.4f}                   ║")
    print(f"║  income_vs_plfs_ratio        : {features['income_vs_plfs_ratio']:<10.4f}                   ║")
    print(f"║  income_stability_score      : {features['income_stability_score']:<10.4f}                   ║")
    print(f"║  platform_income_txns        : {features['platform_income_txn_count']:<10}                   ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  📄 {OUTPUT_JSON:<61}║")
    print(f"║  📄 {FEATURES_CSV:<61}║")
    print("╚══════════════════════════════════════════════════════════════════╝")


# ─────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────

def run(pdf_path: str = PDF_PATH):
    if not Path(pdf_path).exists():
        print(f"❌ PDF not found: {pdf_path}")
        sys.exit(1)

    print("=" * 68)
    print("GigScore — Agent 0: Bank Statement Parser")
    print("Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University")
    print("=" * 68)

    header, raw_txns = parse_pdf(pdf_path)

    print("\n  Redacting PII and categorizing transactions...")
    result = redact_and_categorize(header, raw_txns)

    print("  Computing 8 behavioral velocity features...")
    features = extract_features(
        result['transactions'],
        loan_amount      = LOAN_AMOUNT,
        application_hour = APPLICATION_HOUR,
        region_rating    = REGION_RATING,
    )
    features['applicant_token'] = result['applicant_token']
    result['agent1_features']   = features

    with open(OUTPUT_JSON, 'w') as f:
        json.dump(result, f, indent=2, default=str)

    pd.DataFrame([features]).to_csv(FEATURES_CSV, index=False)

    print_summary(result, features)
    return result, features


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else PDF_PATH
    run(pdf)