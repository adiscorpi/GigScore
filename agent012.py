"""
GigScore — agents_012.py
========================
Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University

Combined Agent 0 + Agent 1 + Agent 2 pipeline.

TWO MODES:
----------
1. TRAINING MODE  — run once on Home Credit + UPI datasets to train the model
   python agents_012.py --mode train

2. INFERENCE MODE — score a single applicant from their bank statement
   python agents_012.py --mode score --persona raju_sharma

HARDCODED FOR DEMO:
-------------------
Persona : raju_sharma
PDF     : gigscore_statement_raju_sharma.pdf
Features: agent0_features.csv  (pre-computed by Agent 0)
"""

# ── Installs ──────────────────────────────────────────────────────────────
import subprocess, sys
for pkg in ['xgboost', 'optuna', 'shap', 'scikit-learn',
            'pandas', 'numpy', 'scipy', 'pdfplumber']:
    subprocess.run([sys.executable, '-m', 'pip', 'install', pkg,
                    '--break-system-packages', '-q'], capture_output=True)

# ── Imports ───────────────────────────────────────────────────────────────
import argparse, json, os, pickle, warnings
from pathlib import Path
from functools import reduce

import numpy as np
import pandas as pd
from scipy.stats import entropy, spearmanr

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────
# HARDCODED FILE NAMES
# ─────────────────────────────────────────────────────────────────────────
STATEMENT_PATH   = "gigscore_statement_raju_sharma.pdf"
FEATURES_CSV     = "agent0_features.csv"
MODEL_PKL        = "gigscore_model.pkl"
MODEL_JSON       = "gigscore_model.json"
MEDIANS_JSON     = "training_medians.json"
PREDICTIONS_CSV  = "GigScore_Predictions.csv"
SHAP_TOP3_CSV    = "GigScore_SHAP_Top3.csv"

# Home Credit + auxiliary datasets
HC_TRAIN_CSV     = "application_train.csv"
CRED_CSV         = "train.csv"
LOAN_CSV         = "Loan_default.csv"
UPI_CSV          = "upi_transactions_2024.csv"

# ── Colours ───────────────────────────────────────────────────────────────
NAVY  = "\033[34m"; GREEN = "\033[32m"; RED = "\033[31m"
BOLD  = "\033[1m";  RESET = "\033[0m"

def log(tag, msg):  print(f"{BOLD}{NAVY}[{tag}]{RESET} {msg}")
def ok(tag, msg):   print(f"{BOLD}{GREEN}[{tag}] ✅ {msg}{RESET}")
def err(tag, msg):  print(f"{BOLD}{RED}[{tag}] ❌ {msg}{RESET}"); sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════
# AGENT 0 — PDF PARSER + PII REDACTION
# ═════════════════════════════════════════════════════════════════════════

def run_agent0(pdf_path: str = STATEMENT_PATH,
               loan_amount: float = 45000,
               application_hour: int = 10,
               region_rating: int = 2) -> dict:
    """
    Parse bank statement PDF using agent0_parser.py.
    Outputs: agent0_features.csv, agent0_output.json
    """
    log("Agent 0", f"Parsing {pdf_path}...")

    # Use agent0_parser.py directly — it handles everything cleanly
    import importlib.util
    parser_path = Path(__file__).parent / "agent0_parser.py"

    if not parser_path.exists():
        err("Agent 0", f"agent0_parser.py not found in {Path(__file__).parent}")

    spec = importlib.util.spec_from_file_location("agent0_parser", parser_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result, features = mod.run(pdf_path)

    ok("Agent 0", f"{len(result['transactions']):,} txns parsed → {FEATURES_CSV}")
    return result


# ═════════════════════════════════════════════════════════════════════════
# AGENT 1 — FEATURE ENGINEERING (TRAINING MODE)
# ═════════════════════════════════════════════════════════════════════════

def _engineer_home_credit(home: pd.DataFrame, gig_df: pd.DataFrame) -> pd.DataFrame:
    """Extract and engineer features from Home Credit dataset."""
    BASE_COLS = [
        'TARGET',
        'AMT_INCOME_TOTAL', 'AMT_CREDIT', 'AMT_ANNUITY', 'AMT_GOODS_PRICE',
        'DAYS_EMPLOYED', 'DAYS_BIRTH', 'CNT_CHILDREN', 'CNT_FAM_MEMBERS',
        'REGION_RATING_CLIENT', 'REGION_RATING_CLIENT_W_CITY',
        'REG_CITY_NOT_WORK_CITY', 'REG_CITY_NOT_LIVE_CITY', 'LIVE_CITY_NOT_WORK_CITY',
        'FLAG_EMP_PHONE', 'FLAG_WORK_PHONE', 'FLAG_CONT_MOBILE', 'FLAG_EMAIL',
        'DAYS_LAST_PHONE_CHANGE', 'EXT_SOURCE_1', 'EXT_SOURCE_2', 'EXT_SOURCE_3',
        'AMT_REQ_CREDIT_BUREAU_DAY', 'AMT_REQ_CREDIT_BUREAU_WEEK',
        'AMT_REQ_CREDIT_BUREAU_MON', 'AMT_REQ_CREDIT_BUREAU_YEAR',
        'HOUR_APPR_PROCESS_START', 'ORGANIZATION_TYPE',
    ]
    hf = gig_df[[c for c in BASE_COLS if c in gig_df.columns]].copy()
    eps = 1e-6

    hf['age']            = hf['DAYS_BIRTH'].abs() / 365.25
    hf['years_employed'] = hf['DAYS_EMPLOYED'].abs() / 365.25
    hf.loc[hf['DAYS_EMPLOYED'].abs() > 50_000, 'years_employed'] = 0.0

    hf['credit_income_ratio']   = hf['AMT_CREDIT']      / (hf['AMT_INCOME_TOTAL'] + eps)
    hf['annuity_income_ratio']  = hf['AMT_ANNUITY']     / (hf['AMT_INCOME_TOTAL'] + eps)
    hf['goods_income_ratio']    = hf['AMT_GOODS_PRICE']  / (hf['AMT_INCOME_TOTAL'] + eps)
    hf['credit_annuity_ratio']  = hf['AMT_CREDIT']      / (hf['AMT_ANNUITY'] + eps)
    hf['income_annuity_ratio']  = hf['AMT_INCOME_TOTAL'] / (hf['AMT_ANNUITY'] + eps)
    hf['income_credit_ratio']   = hf['AMT_INCOME_TOTAL'] / (hf['AMT_CREDIT'] + eps)
    hf['children_ratio']        = hf['CNT_CHILDREN']    / (hf['CNT_FAM_MEMBERS'] + eps)
    hf['income_per_person']     = hf['AMT_INCOME_TOTAL'] / (hf['CNT_FAM_MEMBERS'] + eps)
    hf['employment_age_ratio']  = hf['years_employed']  / (hf['age'] + eps)
    hf['phone_change_ratio']    = hf['DAYS_LAST_PHONE_CHANGE'].abs() / (hf['age'] * 365.25 + eps)

    hf['bureau_requests'] = (
        hf['AMT_REQ_CREDIT_BUREAU_DAY'].fillna(0) +
        hf['AMT_REQ_CREDIT_BUREAU_WEEK'].fillna(0) +
        hf['AMT_REQ_CREDIT_BUREAU_MON'].fillna(0) +
        hf['AMT_REQ_CREDIT_BUREAU_YEAR'].fillna(0)
    )

    hf['ext_source_mean'] = hf[['EXT_SOURCE_1','EXT_SOURCE_2','EXT_SOURCE_3']].mean(axis=1)
    hf['ext_source_std']  = hf[['EXT_SOURCE_1','EXT_SOURCE_2','EXT_SOURCE_3']].std(axis=1)
    hf['ext_source_min']  = hf[['EXT_SOURCE_1','EXT_SOURCE_2','EXT_SOURCE_3']].min(axis=1)

    hf['late_application_flag'] = (
        (hf['HOUR_APPR_PROCESS_START'] >= 22) |
        (hf['HOUR_APPR_PROCESS_START'] <= 5)
    ).astype(int)

    hf.drop(['DAYS_BIRTH', 'DAYS_EMPLOYED'], axis=1, inplace=True, errors='ignore')
    return hf


def _merge_credit_score(hf: pd.DataFrame, cred: pd.DataFrame) -> pd.DataFrame:
    """Merge credit score dataset features via income quartile."""
    eps = 1e-6
    CRED_NUMERIC = ['Delay_from_due_date', 'Num_of_Delayed_Payment',
                    'Outstanding_Debt', 'Annual_Income',
                    'Total_EMI_per_month', 'Amount_invested_monthly']
    for col in CRED_NUMERIC:
        cred[col] = pd.to_numeric(cred[col], errors='coerce')

    cred['payment_discipline']      = 1 / (cred['Delay_from_due_date'].fillna(0) + 1)
    cred['obligation_fulfillment']  = 1 - (cred['Num_of_Delayed_Payment'].fillna(0) /
                                           (cred['Num_of_Delayed_Payment'].fillna(0).max() + 1))
    cred['savings_ratio']           = cred['Amount_invested_monthly'] / (cred['Annual_Income'] + eps)
    cred['debt_income_ratio']       = cred['Outstanding_Debt'] / (cred['Annual_Income'] + eps)
    cred['emi_income_ratio']        = cred['Total_EMI_per_month'] / (cred['Annual_Income'] + eps)
    cred['income_quartile']         = pd.qcut(
        cred['Annual_Income'].clip(lower=0), q=4,
        labels=['Q1','Q2','Q3','Q4'], duplicates='drop'
    )

    CRED_FEATURES = ['payment_discipline', 'obligation_fulfillment',
                     'savings_ratio', 'debt_income_ratio', 'emi_income_ratio']
    cred_by_q = (
        cred.groupby('income_quartile', observed=True)[CRED_FEATURES]
        .mean()
        .rename(columns=lambda c: f'cred_{c}')
    )
    cred_by_q.replace([np.inf, -np.inf], np.nan, inplace=True)
    cred_by_q.fillna(cred_by_q.median(), inplace=True)

    hf['income_quartile'] = pd.qcut(
        hf['AMT_INCOME_TOTAL'].clip(lower=0), q=4,
        labels=['Q1','Q2','Q3','Q4'], duplicates='drop'
    )
    hf = hf.merge(cred_by_q, on='income_quartile', how='left')
    return hf


def _merge_loan_default(hf: pd.DataFrame, loan: pd.DataFrame) -> pd.DataFrame:
    """Merge loan default dataset features via income quartile."""
    eps = 1e-6
    loan_gig = loan[loan['EmploymentType'] == 'Self-employed'].copy()
    loan_gig['loan_income_ratio']   = loan_gig['LoanAmount'] / (loan_gig['Income'] + eps)
    loan_gig['dti_ratio']           = loan_gig['DTIRatio']
    loan_gig['dti_flag']            = (loan_gig['DTIRatio'] > 0.40).astype(int)
    loan_gig['employment_years']    = loan_gig['MonthsEmployed'] / 12
    loan_gig['high_interest_flag']  = (loan_gig['InterestRate'] > 15).astype(int)
    loan_gig['loan_default_rate']   = loan_gig['Default']
    loan_gig['income_quartile']     = pd.qcut(
        loan_gig['Income'].clip(lower=0), q=4,
        labels=['Q1','Q2','Q3','Q4'], duplicates='drop'
    )

    LOAN_FEATURES = ['loan_income_ratio', 'dti_ratio', 'dti_flag',
                     'employment_years', 'high_interest_flag', 'loan_default_rate']
    loan_by_q = (
        loan_gig.groupby('income_quartile', observed=True)[LOAN_FEATURES]
        .mean()
        .rename(columns=lambda c: f'loan_{c}')
    )
    hf = hf.merge(loan_by_q, on='income_quartile', how='left')
    return hf


def _compute_upi_features(upi: pd.DataFrame) -> pd.DataFrame:
    """Compute all 8 behavioral velocity features from UPI transaction data."""
    upi.columns = (upi.columns.str.lower().str.strip()
                   .str.replace(' ', '_', regex=False)
                   .str.replace('(', '', regex=False)
                   .str.replace(')', '', regex=False))

    upi['timestamp']  = pd.to_datetime(upi['timestamp'], errors='coerce')
    upi['month']      = upi['timestamp'].dt.to_period('M')
    upi['is_success'] = upi['transaction_status'].str.upper() == 'SUCCESS'
    upi['is_p2m']     = upi['transaction_type'].str.upper() == 'P2M'
    upi['is_p2p']     = upi['transaction_type'].str.upper() == 'P2P'
    if 'is_weekend' not in upi.columns:
        upi['is_weekend'] = upi['timestamp'].dt.dayofweek >= 5
    if 'fraud_flag' not in upi.columns:
        upi['fraud_flag'] = 0

    # Income quartile + org proxy for fine-grained join
    upi['income_quartile'] = pd.qcut(
        upi['amount_inr'].clip(lower=0), q=4,
        labels=['Q1','Q2','Q3','Q4'], duplicates='drop'
    )
    ORG_PROXY_MAP = {
        'Transport':'Transport: type 2', 'Taxi':'Taxi / driver',
        'Driver':'Taxi / driver', 'Food':'Trade: type 1',
        'Grocery':'Trade: type 1', 'Retail':'Trade: type 2',
        'Shopping':'Trade: type 2', 'Services':'Self-employed',
        'Utility':'Self-employed', 'Electronics':'Trade: type 1',
        'Healthcare':'Self-employed', 'Education':'Self-employed',
    }
    def map_org(cat):
        if pd.isna(cat): return 'Self-employed'
        for k, v in ORG_PROXY_MAP.items():
            if k.lower() in str(cat).lower(): return v
        return 'Self-employed'
    upi['org_proxy'] = upi['merchant_category'].apply(map_org)

    GROUP_KEYS = ['sender_state', 'income_quartile', 'org_proxy']

    # Feature 1: income_regularity_cv
    monthly_flow = (
        upi[upi['is_p2p']]
        .groupby(GROUP_KEYS + ['month'])
        .agg(total_inflow=('amount_inr', 'sum'), txn_count=('transaction_id', 'count'))
        .reset_index()
    )
    income_cv = (
        monthly_flow.groupby(GROUP_KEYS)['total_inflow']
        .agg(lambda x: x.std() / (x.mean() + 1e-6))
        .rename('income_regularity_cv').reset_index()
    )

    # Feature 2: utility_payment_streak
    monthly_p2m = (
        upi[upi['is_p2m']].groupby(GROUP_KEYS + ['month']).size().gt(0)
        .reset_index(name='has_p2m')
    )
    def max_streak(s):
        streak, best = 0, 0
        for v in s:
            streak = streak + 1 if v else 0
            best   = max(best, streak)
        return best
    utility_streak = (
        monthly_p2m.sort_values(GROUP_KEYS + ['month'])
        .groupby(GROUP_KEYS)['has_p2m']
        .apply(max_streak).rename('utility_payment_streak').reset_index()
    )

    # Feature 3: cash_crunch_recovery_speed
    state_med = monthly_flow.groupby(GROUP_KEYS)['txn_count'].transform('median')
    monthly_flow['crunch'] = (monthly_flow['txn_count'] < state_med).astype(int)
    mf_sorted = monthly_flow.sort_values(GROUP_KEYS + ['month'])
    mf_sorted['next_txn'] = mf_sorted.groupby(GROUP_KEYS)['txn_count'].shift(-1)
    crunch_rows = mf_sorted[mf_sorted['crunch'] == 1].copy()
    crunch_rows['recovery_ratio'] = crunch_rows['next_txn'] / (crunch_rows['txn_count'] + 1e-6)
    crunch_recovery = (
        crunch_rows.groupby(GROUP_KEYS)['recovery_ratio']
        .mean().rename('cash_crunch_recovery_speed').reset_index()
    )

    # Feature 4: spending_velocity
    monthly_spend = (
        upi[upi['is_p2m']].groupby(GROUP_KEYS + ['month'])['amount_inr']
        .sum().reset_index()
    )
    spending_velocity = (
        monthly_spend.groupby(GROUP_KEYS)['amount_inr']
        .agg(lambda x: x.std() / (x.mean() + 1e-6))
        .rename('spending_velocity').reset_index()
    )

    # Feature 5: merchant_diversity_score
    def shannon_diversity(s):
        counts = s.value_counts(normalize=True)
        if len(counts) <= 1: return 0.0
        raw = entropy(counts)
        mx  = np.log(len(counts))
        return raw / mx if mx > 0 else 0.0
    merchant_diversity = (
        upi[upi['is_p2m']].groupby(GROUP_KEYS)['merchant_category']
        .apply(shannon_diversity).rename('merchant_diversity_score').reset_index()
    )

    # Feature 6: inflow_outflow_ratio
    state_totals = (
        upi.groupby(GROUP_KEYS + ['transaction_type'])['amount_inr']
        .sum().unstack(fill_value=0).reset_index()
    )
    state_totals.columns = [c.lower() if isinstance(c, str) else c for c in state_totals.columns]
    if 'p2p' not in state_totals.columns: state_totals['p2p'] = 0
    if 'p2m' not in state_totals.columns: state_totals['p2m'] = 0
    state_totals['inflow_outflow_ratio'] = state_totals['p2p'] / (state_totals['p2m'] + 1e-6)
    inflow_outflow = state_totals[GROUP_KEYS + ['inflow_outflow_ratio']].copy()

    # Feature 7: recurring_payment_ratio
    p2m_txns = upi[upi['is_p2m']].copy()
    recurring_records = []
    for keys, grp in p2m_txns.groupby(GROUP_KEYS):
        months = sorted(grp['month'].unique())
        if len(months) < 2:
            recurring_records.append((*keys, 0.0)); continue
        recurring_cats = set()
        for i in range(len(months) - 1):
            c_now  = set(grp[grp['month'] == months[i]]['merchant_category'])
            c_next = set(grp[grp['month'] == months[i+1]]['merchant_category'])
            recurring_cats |= (c_now & c_next)
        total_cats = len(grp['merchant_category'].unique())
        recurring_records.append((*keys, len(recurring_cats) / (total_cats + 1e-6)))
    recurring_payment_ratio = pd.DataFrame(
        recurring_records, columns=GROUP_KEYS + ['recurring_payment_ratio']
    )

    # Feature 8: obligation_fulfillment_rate
    def _str_keys(df):
        df = df.copy()
        for col in GROUP_KEYS: df[col] = df[col].astype(str)
        return df

    months_p2m = _str_keys(
        upi[upi['is_p2m']].groupby(GROUP_KEYS + ['month']).size().gt(0)
        .reset_index(name='has_p2m')
    )
    months_p2p = _str_keys(
        upi[upi['is_p2p']].groupby(GROUP_KEYS + ['month']).size().gt(0)
        .reset_index(name='has_p2p')
    )
    oblig_df = months_p2m.merge(months_p2p, on=GROUP_KEYS + ['month'], how='outer')
    oblig_df['has_p2m'] = oblig_df['has_p2m'].fillna(False)
    oblig_df['has_p2p'] = oblig_df['has_p2p'].fillna(False)
    oblig_df['both']    = oblig_df['has_p2m'] & oblig_df['has_p2p']
    obligation_fulfillment_rate = (
        oblig_df.groupby(GROUP_KEYS)['both']
        .mean().rename('obligation_fulfillment_rate').reset_index()
    )

    # Base UPI stats
    txn_id_col = 'transaction_id' if 'transaction_id' in upi.columns else upi.columns[0]
    upi_base = (
        upi.groupby(GROUP_KEYS).agg(
            upi_total_txns       =(txn_id_col,           'count'),
            upi_avg_amount       =('amount_inr',          'mean'),
            upi_success_rate     =('is_success',          'mean'),
            upi_fraud_rate       =('fraud_flag',           'mean'),
            upi_weekend_ratio    =('is_weekend',           'mean'),
            upi_unique_merchants =('merchant_category',   'nunique'),
        ).reset_index()
    )

    # Merge all 8 features
    feature_dfs = [
        income_cv, utility_streak, crunch_recovery, spending_velocity,
        merchant_diversity, inflow_outflow[GROUP_KEYS + ['inflow_outflow_ratio']],
        recurring_payment_ratio, obligation_fulfillment_rate,
    ]
    upi_features = reduce(
        lambda l, r: pd.merge(l, r, on=GROUP_KEYS, how='outer'), feature_dfs
    )
    upi_profile = upi_features.merge(upi_base, on=GROUP_KEYS, how='left')

    # Rename with upi_ prefix
    bv_features = [
        'income_regularity_cv', 'utility_payment_streak', 'cash_crunch_recovery_speed',
        'spending_velocity', 'merchant_diversity_score', 'inflow_outflow_ratio',
        'recurring_payment_ratio', 'obligation_fulfillment_rate'
    ]
    rename_map = {c: f'upi_{c}' for c in bv_features}
    upi_profile = upi_profile.rename(columns=rename_map)
    return upi_profile


def _merge_upi_features(hf: pd.DataFrame, upi_profile: pd.DataFrame) -> pd.DataFrame:
    """Join UPI features to gig worker cohort via region × quartile × org proxy."""
    TIER_MAP = {
        1: ['Maharashtra', 'Karnataka', 'Delhi', 'Tamil Nadu', 'Telangana', 'Gujarat'],
        2: ['Rajasthan', 'Madhya Pradesh', 'Uttar Pradesh', 'Punjab', 'Haryana',
            'Kerala', 'West Bengal'],
        3: ['Bihar', 'Odisha', 'Chhattisgarh', 'Jharkhand', 'Assam',
            'Himachal Pradesh', 'Uttarakhand', 'Goa'],
    }
    ORG_PROXY_MAP = {
        'Transport':'Transport: type 2', 'Taxi':'Taxi / driver',
        'Driver':'Taxi / driver', 'Food':'Trade: type 1',
        'Grocery':'Trade: type 1', 'Retail':'Trade: type 2',
        'Shopping':'Trade: type 2', 'Services':'Self-employed',
        'Utility':'Self-employed', 'Electronics':'Trade: type 1',
        'Healthcare':'Self-employed', 'Education':'Self-employed',
    }

    upi_states = upi_profile['sender_state'].unique()
    GROUP_KEYS = ['sender_state', 'income_quartile', 'org_proxy']

    UPI_FEATURE_COLS = [c for c in upi_profile.columns if c.startswith('upi_')]

    def org_to_proxy(org_type):
        if pd.isna(org_type): return 'Self-employed'
        for k, v in ORG_PROXY_MAP.items():
            if k.lower() in str(org_type).lower(): return v
        return org_type if org_type in upi_profile['org_proxy'].unique() else 'Self-employed'

    hf_reset = hf.reset_index(drop=True)
    assigned_states = []
    for idx, row in hf_reset.iterrows():
        tier       = int(row['REGION_RATING_CLIENT']) if 'REGION_RATING_CLIENT' in row else 2
        tier_states= [s for s in TIER_MAP.get(tier, []) if s in upi_states]
        if not tier_states: tier_states = list(upi_states)[:1]
        assigned_states.append(tier_states[idx % len(tier_states)])

    hf_reset['_assigned_state']  = assigned_states
    hf_reset['_org_proxy']       = hf_reset.get('ORGANIZATION_TYPE', pd.Series(['Self-employed']*len(hf_reset))).apply(org_to_proxy)

    hf_merged = hf_reset.merge(
        upi_profile[GROUP_KEYS + UPI_FEATURE_COLS],
        left_on  =['_assigned_state', 'income_quartile', '_org_proxy'],
        right_on =GROUP_KEYS,
        how='left'
    )
    for col in UPI_FEATURE_COLS:
        hf[col] = hf_merged[col].values
    hf.drop(columns=['_assigned_state', '_org_proxy', 'sender_state', 'org_proxy'],
            errors='ignore', inplace=True)
    return hf


def _add_synthetic_proxies(hf: pd.DataFrame) -> pd.DataFrame:
    """Add synthetic per-applicant behavioral proxy features (Step 7.5)."""
    eps = 1e-6
    hf['income_instability_proxy']   = (hf['DAYS_LAST_PHONE_CHANGE'].abs() /
                                         (hf['age'] * 365.25 + eps)).clip(upper=5)
    hf['credit_seeking_intensity']   = (hf['bureau_requests'] /
                                         (hf['years_employed'] + 1)).clip(upper=20)
    hf['stress_signal']              = (hf['late_application_flag'] *
                                         hf['credit_income_ratio']).clip(upper=20)
    hf['lifestyle_stability']        = (hf['CNT_FAM_MEMBERS'] /
                                         (hf['REGION_RATING_CLIENT_W_CITY'] + eps))
    hf['repayment_stretch']          = (hf['AMT_ANNUITY'] /
                                         (hf['AMT_INCOME_TOTAL'] + eps) *
                                         hf['REGION_RATING_CLIENT']).clip(upper=10)
    hf['credit_utilization_pressure']= (hf['AMT_CREDIT'] /
                                         (hf['AMT_INCOME_TOTAL'] *
                                          (hf['years_employed'] + 1) + eps)).clip(upper=50)
    hf['digital_engagement_proxy']   = (hf['FLAG_WORK_PHONE'].fillna(0) +
                                         hf['FLAG_CONT_MOBILE'].fillna(0))
    return hf


def _add_synthetic_upi_scores(hf: pd.DataFrame) -> pd.DataFrame:
    """Add synthetic per-applicant UPI behavioral scores anchored to creditworthiness."""
    np.random.seed(42)
    n = len(hf)
    eps = 1e-6

    creditworth = hf['ext_source_mean'].fillna(hf['ext_source_mean'].median()).clip(0, 1)
    stability   = hf['employment_age_ratio'].fillna(0).clip(0, 1)
    emp_signal  = (hf['years_employed'].fillna(0).clip(0, 15) / 15)
    income_sig  = hf['AMT_INCOME_TOTAL'].rank(pct=True)
    debt_burden = (hf['credit_income_ratio'].fillna(3).clip(0, 10) / 10).clip(0, 1)
    load        = hf['annuity_income_ratio'].fillna(0.3).clip(0, 1)
    late        = hf['late_application_flag'].fillna(0)
    bureau      = (hf['bureau_requests'].fillna(0).clip(0, 20) / 20).clip(0, 1)
    emp_years   = hf['years_employed'].fillna(0).clip(0, 20) / 20

    hf['syn_income_regularity_cv'] = (
        0.45 - 0.20 * emp_signal - 0.15 * income_sig + 0.25 * debt_burden
        - 0.05 * creditworth + np.random.normal(0, 0.06, n)
    ).clip(0.05, 0.90)

    hf['syn_utility_streak'] = (
        3.0 + 5.0 * emp_signal + 3.0 * stability - 3.0 * debt_burden
        + 1.0 * creditworth + np.random.normal(0, 1.2, n)
    ).clip(0, 12).round(1)

    hf['syn_merchant_diversity'] = (
        0.30 + 0.35 * income_sig + 0.20 * emp_signal
        - 0.20 * debt_burden + 0.05 * creditworth + np.random.normal(0, 0.07, n)
    ).clip(0.05, 0.99)

    hf['syn_inflow_outflow'] = (
        0.80 + 0.40 * income_sig - 0.40 * load
        - 0.25 * debt_burden + 0.05 * creditworth + np.random.normal(0, 0.10, n)
    ).clip(0.40, 2.50)

    hf['syn_spending_velocity'] = (
        0.45 - 0.25 * emp_signal + 0.25 * debt_burden
        + 0.15 * late + 0.05 * creditworth + np.random.normal(0, 0.06, n)
    ).clip(0.05, 0.90)

    hf['syn_crunch_recovery'] = (
        0.85 + 0.20 * emp_signal + 0.15 * income_sig
        - 0.25 * bureau - 0.10 * debt_burden + np.random.normal(0, 0.05, n)
    ).clip(0.50, 1.50)

    hf['syn_recurring_ratio'] = (
        0.35 + 0.40 * emp_years + 0.20 * stability
        - 0.20 * debt_burden + np.random.normal(0, 0.07, n)
    ).clip(0.05, 0.99)

    hf['syn_obligation_rate'] = (
        0.50 + 0.30 * emp_signal + 0.20 * income_sig
        - 0.30 * load - 0.10 * debt_burden + 0.10 * emp_years
        + np.random.normal(0, 0.07, n)
    ).clip(0.05, 1.00)

    return hf


def run_agent1_training() -> tuple:
    """
    Full Agent 1 training pipeline.
    Loads all 4 datasets, engineers features, saves train/test splits.
    Returns: X_train, X_test, y_train, y_test, strong_features
    """
    log("Agent 1", "Loading datasets...")

    for path, name in [(HC_TRAIN_CSV, "Home Credit"), (CRED_CSV, "Credit Score"),
                       (LOAN_CSV, "Loan Default"), (UPI_CSV, "UPI Transactions")]:
        if not Path(path).exists():
            err("Agent 1", f"{name} dataset not found: {path}")

    home = pd.read_csv(HC_TRAIN_CSV)
    cred = pd.read_csv(CRED_CSV, low_memory=False)
    loan = pd.read_csv(LOAN_CSV)
    upi  = pd.read_csv(UPI_CSV)

    ok("Agent 1", f"Loaded — Home:{len(home):,} Cred:{len(cred):,} Loan:{len(loan):,} UPI:{len(upi):,}")

    # ── Step 2: Filter gig worker cohort ─────────────────────────────────
    GIG_ORG_TYPES = ['Self-employed', 'Taxi / driver',
                     'Transport: type 1', 'Transport: type 2',
                     'Trade: type 1', 'Trade: type 2',
                     'Low-skill Laborers', 'Drivers']
    income_cap = home['AMT_INCOME_TOTAL'].quantile(0.90)
    gig_mask   = (
        home['NAME_INCOME_TYPE'].isin(['Self-employed', 'Working']) &
        home['ORGANIZATION_TYPE'].isin(GIG_ORG_TYPES) &
        (home['AMT_INCOME_TOTAL'] < income_cap)
    )
    gig_df = home[gig_mask].copy()
    log("Agent 1", f"Gig cohort: {len(gig_df):,} ({len(gig_df)/len(home):.1%}) | default rate: {gig_df['TARGET'].mean():.2%}")

    # ── Steps 3-7: Feature engineering ───────────────────────────────────
    log("Agent 1", "Engineering features...")
    hf = _engineer_home_credit(home, gig_df)
    hf = _merge_credit_score(hf, cred)
    hf = _merge_loan_default(hf, loan)

    log("Agent 1", "Computing 8 UPI behavioral features...")
    upi_profile = _compute_upi_features(upi)
    hf = _merge_upi_features(hf, upi_profile)
    hf = _add_synthetic_proxies(hf)
    hf = _add_synthetic_upi_scores(hf)

    # ── Income features (Agent 2 Step 1.5) ───────────────────────────────
    eps = 1e-6
    hf['log_income']       = np.log1p(hf['AMT_INCOME_TOTAL'])
    hf['income_percentile']= hf['AMT_INCOME_TOTAL'].rank(pct=True)
    if 'AMT_CREDIT' in hf.columns:
        hf['income_adequacy']  = hf['AMT_INCOME_TOTAL'] / (hf['AMT_CREDIT'] + eps)
    if 'AMT_ANNUITY' in hf.columns:
        hf['monthly_income_vs_emi'] = (hf['AMT_INCOME_TOTAL'] / 12) / (hf['AMT_ANNUITY'] + eps)
    if 'years_employed' in hf.columns and 'age' in hf.columns:
        hf['income_stability_score'] = (
            np.log1p(hf['AMT_INCOME_TOTAL']) * hf['years_employed'] / (hf['age'] + eps)
        )

    # ── Step 10: Train/test split ─────────────────────────────────────────
    from sklearn.model_selection import train_test_split

    DROP_COLS = ['ORGANIZATION_TYPE', 'income_quartile', 'plfs_benchmark_income']
    hf.drop(columns=DROP_COLS, errors='ignore', inplace=True)
    hf = hf.select_dtypes(include=[np.number])

    # Drop all-null + constant columns
    null_cols    = [c for c in hf.columns if hf[c].isna().all()]
    hf.drop(columns=null_cols, inplace=True)
    hf.replace([np.inf, -np.inf], np.nan, inplace=True)
    const_cols   = [c for c in hf.columns if hf[c].nunique() <= 1]
    hf.drop(columns=const_cols, inplace=True)
    hf.fillna(hf.median(numeric_only=True), inplace=True)

    X_all = hf.drop('TARGET', axis=1)
    y_all = hf['TARGET']

    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_all, y_all, test_size=0.20, random_state=42, stratify=y_all
    )

    # ── Step 11: Spearman filter on train only ────────────────────────────
    SPEARMAN_THRESHOLD = 0.005
    train_full = X_train_raw.copy(); train_full['TARGET'] = y_train.values
    spearman_scores = {}
    for col in X_train_raw.columns:
        rho, _ = spearmanr(train_full[col], train_full['TARGET'], nan_policy='omit')
        spearman_scores[col] = abs(rho) if not np.isnan(rho) else 0.0
    strong_features = [c for c, rho in spearman_scores.items() if rho >= SPEARMAN_THRESHOLD]
    weak_features   = [c for c, rho in spearman_scores.items() if rho <  SPEARMAN_THRESHOLD]

    X_train = X_train_raw[strong_features].copy()
    X_test  = X_test_raw[strong_features].copy()

    log("Agent 1", f"Features retained: {len(strong_features)} | dropped: {len(weak_features)}")

    # ── Save ──────────────────────────────────────────────────────────────
    X_train.to_csv("X_train.csv", index=True)
    X_test.to_csv("X_test.csv",   index=True)
    y_train.to_csv("y_train.csv", index=True)
    y_test.to_csv("y_test.csv",   index=True)

    # Save training medians for inference
    medians = X_train.median().to_dict()
    with open(MEDIANS_JSON, 'w') as f:
        json.dump(medians, f, indent=2)

    ok("Agent 1", f"Train:{X_train.shape} Test:{X_test.shape} | Medians saved → {MEDIANS_JSON}")
    return X_train, X_test, y_train, y_test, strong_features


def run_agent1_inference(features_csv: str = FEATURES_CSV) -> pd.DataFrame:
    """
    Agent 1 inference mode — take Agent 0 features CSV,
    fill missing columns with training medians, return aligned feature row.
    """
    log("Agent 1", f"Loading features from {features_csv}...")

    if not Path(features_csv).exists():
        err("Agent 1", f"{features_csv} not found. Run Agent 0 first.")

    features = pd.read_csv(features_csv)

    # Load training medians
    if Path(MEDIANS_JSON).exists():
        with open(MEDIANS_JSON) as f:
            medians = json.load(f)
        log("Agent 1", f"Loaded {len(medians)} training medians")
    else:
        log("Agent 1", "No training_medians.json — using hardcoded gig worker medians", )
        medians = {
            'EXT_SOURCE_1':   0.4637, 'EXT_SOURCE_2':   0.5143,
            'EXT_SOURCE_3':   0.5297, 'ext_source_mean':0.4987,
            'ext_source_std': 0.1823, 'ext_source_min': 0.3641,
        }

    # Fill EXT_SOURCE and other NaN with medians
    for col, val in medians.items():
        if col in features.columns:
            features[col] = pd.to_numeric(features[col], errors='coerce').fillna(val)
        else:
            features[col] = val

    # Add income signal features — match Agent 2 Cell 6 exactly
    # Only add if not already in CSV (agent0_parser.py may have pre-computed them)
    eps = 1e-6
    if 'AMT_INCOME_TOTAL' in features.columns:
        if 'log_income' not in features.columns:
            features['log_income'] = np.log1p(features['AMT_INCOME_TOTAL'])
        # income_percentile: 0.5 is the correct inference approximation
        # (can't compute true rank without full training cohort)
        if 'income_percentile' not in features.columns:
            features['income_percentile'] = 0.5
    if 'AMT_CREDIT' in features.columns and 'AMT_INCOME_TOTAL' in features.columns:
        if 'income_adequacy' not in features.columns:
            features['income_adequacy'] = features['AMT_INCOME_TOTAL'] / (features['AMT_CREDIT'] + eps)
    if 'AMT_ANNUITY' in features.columns and 'AMT_INCOME_TOTAL' in features.columns:
        if 'monthly_income_vs_emi' not in features.columns:
            features['monthly_income_vs_emi'] = (features['AMT_INCOME_TOTAL'] / 12) / (features['AMT_ANNUITY'] + eps)
    if 'years_employed' in features.columns and 'age' in features.columns:
        if 'income_stability_score' not in features.columns:
            features['income_stability_score'] = (
                np.log1p(features['AMT_INCOME_TOTAL']) *
                features['years_employed'] / (features['age'] + eps)
            )

    # Drop metadata columns
    drop_cols = ['persona_id', 'applicant_token', 'AMT_INCOME_MONTHLY', 'TARGET']
    features  = features.drop(columns=drop_cols, errors='ignore')

    # Replace inf / nan
    features.replace([np.inf, -np.inf], np.nan, inplace=True)
    for col in features.columns:
        if features[col].isna().any():
            features[col] = features[col].fillna(medians.get(col, 0))

    ok("Agent 1", f"Feature row ready: {features.shape[1]} columns")
    return features


# ═════════════════════════════════════════════════════════════════════════
# AGENT 2 — XGBOOST + SHAP + GIGSCORE
# ═════════════════════════════════════════════════════════════════════════

def prob_to_gigscore(prob: float, k: float = 6, midpoint: float = 0.35) -> float:
    return float(np.clip(100 / (1 + np.exp(k * (prob - midpoint))), 0, 100))


def assign_tier(score: float) -> str:
    if score >= 80:   return 'Prime'
    elif score >= 65: return 'Near-Prime'
    elif score >= 50: return 'Sub-Prime'
    else:             return 'Decline'


def run_agent2_training(X_train, X_test, y_train, y_test):
    """Train XGBoost model with Optuna, save model + predictions."""
    from xgboost import XGBClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    import shap, pickle

    log("Agent 2", "Starting Optuna hyperparameter search (60 trials)...")

    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()

    # Income signal engineering on train/test
    # Matches Agent 2 notebook Cell 6 exactly — all 5 features
    eps = 1e-6
    for df in [X_train, X_test]:
        if 'AMT_INCOME_TOTAL' in df.columns:
            if 'log_income' not in df.columns:
                df['log_income'] = np.log1p(df['AMT_INCOME_TOTAL'])
            if 'income_percentile' not in df.columns:
                df['income_percentile'] = df['AMT_INCOME_TOTAL'].rank(pct=True)
        if 'AMT_CREDIT' in df.columns and 'income_adequacy' not in df.columns:
            df['income_adequacy'] = df['AMT_INCOME_TOTAL'] / (df['AMT_CREDIT'] + eps)
        if 'AMT_ANNUITY' in df.columns and 'monthly_income_vs_emi' not in df.columns:
            df['monthly_income_vs_emi'] = (df['AMT_INCOME_TOTAL'] / 12) / (df['AMT_ANNUITY'] + eps)
        if 'years_employed' in df.columns and 'age' in df.columns:
            if 'income_stability_score' not in df.columns:
                df['income_stability_score'] = (
                    np.log1p(df['AMT_INCOME_TOTAL']) *
                    df['years_employed'] / (df['age'] + eps)
                )
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.fillna(df.median(), inplace=True)

    def objective(trial):
        params = {
            'n_estimators':     trial.suggest_int('n_estimators', 200, 1000),
            'max_depth':        trial.suggest_int('max_depth', 2, 5),
            'learning_rate':    trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
            'subsample':        trial.suggest_float('subsample', 0.6, 0.9),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 0.9),
            'min_child_weight': trial.suggest_int('min_child_weight', 5, 30),
            'gamma':            trial.suggest_float('gamma', 0.1, 5.0),
            'reg_alpha':        trial.suggest_float('reg_alpha', 0.1, 3.0),
            'reg_lambda':       trial.suggest_float('reg_lambda', 1.0, 8.0),
            'scale_pos_weight': scale_pos_weight,
            'random_state':     42, 'eval_metric': 'auc', 'verbosity': 0,
        }
        model = XGBClassifier(**params)
        cv    = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        score = cross_val_score(model, X_train, y_train, cv=cv,
                                scoring='roc_auc', n_jobs=-1)
        return score.mean()

    study = optuna.create_study(
        direction='maximize',
        sampler=optuna.samplers.TPESampler(seed=42)
    )
    study.optimize(objective, n_trials=60, show_progress_bar=True)
    best_params = study.best_params
    log("Agent 2", f"Best CV AUC: {study.best_value:.4f}")

    # Train with early stopping
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=0.15, random_state=42, stratify=y_train
    )
    final_params = {
        **best_params,
        'scale_pos_weight':    scale_pos_weight,
        'random_state':        42,
        'eval_metric':         'auc',
        'verbosity':           0,
        'early_stopping_rounds': 50,
    }
    final_params.pop('use_label_encoder', None)

    model = XGBClassifier(**final_params)
    model.fit(X_tr, y_tr, eval_set=[(X_tr, y_tr), (X_val, y_val)], verbose=False)

    y_prob_train = model.predict_proba(X_train)[:, 1]
    y_prob_test  = model.predict_proba(X_test)[:, 1]
    auc_train    = roc_auc_score(y_train, y_prob_train)
    auc_test     = roc_auc_score(y_test,  y_prob_test)

    ok("Agent 2", f"Train AUC: {auc_train:.4f} | Test AUC: {auc_test:.4f} | Gap: {auc_train-auc_test:.4f}")

    # GigScore mapping
    gigscore_test  = prob_to_gigscore(y_prob_test)
    tiers_test     = pd.Series([assign_tier(s) for s in gigscore_test], index=X_test.index)

    # SHAP
    log("Agent 2", "Computing SHAP values...")
    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)

    # Save predictions
    scores_df = pd.DataFrame({
        'applicant_id':    X_test.index,
        'gigscore':        gigscore_test,
        'default_prob':    y_prob_test,
        'tier':            tiers_test.values,
        'actual_default':  y_test.values,
    })
    scores_df.to_csv(PREDICTIONS_CSV, index=False)

    # Save SHAP top3
    top3 = []
    for i in range(len(X_test)):
        sv      = shap_values[i]
        top_idx = np.abs(sv).argsort()[::-1][:3]
        top3.append({
            'applicant_id': X_test.index[i],
            'gigscore':     gigscore_test[i],
            'tier':         tiers_test.iloc[i],
            'feature_1':    X_test.columns[top_idx[0]], 'shap_1': sv[top_idx[0]],
            'feature_2':    X_test.columns[top_idx[1]], 'shap_2': sv[top_idx[1]],
            'feature_3':    X_test.columns[top_idx[2]], 'shap_3': sv[top_idx[2]],
        })
    pd.DataFrame(top3).to_csv(SHAP_TOP3_CSV, index=False)

    # Save model
    with open(MODEL_PKL, 'wb') as f:
        pickle.dump(model, f)
    model.save_model(MODEL_JSON)

    ok("Agent 2", f"Model saved → {MODEL_PKL} | Predictions → {PREDICTIONS_CSV}")
    return model, auc_test


def run_agent2_inference(features: pd.DataFrame) -> dict:
    """Score a single applicant using pre-trained model."""
    import pickle, shap

    if not Path(MODEL_PKL).exists() and not Path(MODEL_JSON).exists():
        err("Agent 2", f"No trained model found. Run: python agents_012.py --mode train")

    log("Agent 2", "Loading pre-trained GigScore model...")

    if Path(MODEL_PKL).exists():
        with open(MODEL_PKL, 'rb') as f:
            model = pickle.load(f)
    else:
        from xgboost import XGBClassifier
        model = XGBClassifier()
        model.load_model(MODEL_JSON)

    # Align features to model's expected columns
    model_cols = model.get_booster().feature_names
    if model_cols:
        for col in model_cols:
            if col not in features.columns:
                features[col] = 0.0
        try:
            features = features[model_cols]
        except Exception:
            features = features.reindex(columns=model_cols, fill_value=0.0)

    features.replace([np.inf, -np.inf], np.nan, inplace=True)
    features.fillna(0, inplace=True)

    # Score
    default_prob = float(model.predict_proba(features)[0][1])
    raw_gigscore = round(prob_to_gigscore(default_prob), 1)
    tier         = assign_tier(raw_gigscore)

    # SHAP top 3
    try:
        explainer   = shap.TreeExplainer(model)
        shap_vals   = explainer.shap_values(features)[0]
        shap_series = pd.Series(shap_vals, index=features.columns)
        top3_idx    = shap_series.abs().nlargest(3).index
        shap_top3   = [
            {
                'feature':       col,
                'shap_value':    round(float(shap_series[col]), 4),
                'feature_value': round(float(features[col].iloc[0]), 4),
                'direction':     'positive' if shap_series[col] < 0 else 'negative',
            }
            for col in top3_idx
        ]
    except Exception as e:
        log("Agent 2", f"SHAP skipped: {e}")
        shap_top3 = []

    result = {
        'default_prob': round(default_prob, 4),
        'raw_gigscore': raw_gigscore,
        'tier':         tier,
        'shap_top3':    shap_top3,
    }

    ok("Agent 2", f"default_prob={default_prob:.3f} → GigScore={raw_gigscore} ({tier})")
    return result


# ═════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═════════════════════════════════════════════════════════════════════════

def run_training_pipeline():
    """Full training pipeline — run once to train model."""
    print(f"\n{'='*60}")
    print("GigScore — TRAINING MODE")
    print(f"{'='*60}\n")

    X_train, X_test, y_train, y_test, strong_features = run_agent1_training()
    model, auc = run_agent2_training(X_train, X_test, y_train, y_test)

    print(f"\n{'='*60}")
    print("TRAINING COMPLETE")
    print(f"  Model AUC       : {auc:.4f}")
    print(f"  Model saved     : {MODEL_PKL}")
    print(f"  Medians saved   : {MEDIANS_JSON}")
    print(f"{'='*60}\n")


def run_inference_pipeline(persona_id: str = "raju_sharma",
                            pdf_path:   str  = STATEMENT_PATH,
                            loan_amount: float = 45000,
                            skip_agent0: bool  = False) -> dict:
    """
    Inference pipeline for a single applicant.
    Returns full result dict ready for Agent 4.
    """
    print(f"\n{'='*60}")
    print(f"GigScore — INFERENCE MODE: {persona_id}")
    print(f"{'='*60}\n")

    t0 = __import__('time').time()

    # Agent 0 — parse PDF or use existing files
    if not skip_agent0 and Path(pdf_path).exists():
        agent0_result = run_agent0(pdf_path, loan_amount)
    elif Path(FEATURES_CSV).exists():
        log("Agent 0", f"Using existing {FEATURES_CSV} (skip_agent0=True)")
        if Path("agent0_output.json").exists():
            with open("agent0_output.json") as f:
                agent0_result = json.load(f)
        else:
            # Build minimal result from CSV — agent0_output.json not required
            df_tmp = pd.read_csv(FEATURES_CSV)
            agent0_result = {
                "applicant_token": str(df_tmp.get("applicant_token", pd.Series(["APPL_unknown"]))[0]),
                "transactions":    [],
                "audit_log":       {"dpdp_compliant": True},
            }
            log("Agent 0", "agent0_output.json not found — built minimal result from CSV")
    else:
        err("Agent 0", f"No PDF found at {pdf_path} and no {FEATURES_CSV} found.")

    # Agent 1 — feature engineering
    features = run_agent1_inference(FEATURES_CSV)

    # Agent 2 — score
    agent2_result = run_agent2_inference(features)

    # Read monthly income from features CSV
    df_tmp = pd.read_csv(FEATURES_CSV)
    monthly_income = float(df_tmp['AMT_INCOME_MONTHLY'].iloc[0]) \
                     if 'AMT_INCOME_MONTHLY' in df_tmp.columns else 45000.0

    # Combine full result
    result = {
        'persona_id':      persona_id,
        'applicant_token': agent0_result.get('applicant_token', 'APPL_unknown'),
        **agent2_result,
        'monthly_income':  monthly_income,
        'features':        features.iloc[0].to_dict(),  # full feature row for Agent 4
    }

    # Save
    out_path = f"agent2_result_{persona_id}.json"
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)

    elapsed = __import__('time').time() - t0

    print(f"\n{'='*60}")
    print(f"INFERENCE COMPLETE — {elapsed:.1f}s")
    print(f"  Persona         : {persona_id}")
    print(f"  Default Prob    : {result['default_prob']:.3f}")
    print(f"  Raw GigScore    : {result['raw_gigscore']}")
    print(f"  Tier            : {result['tier']}")
    print(f"  Saved to        : {out_path}")
    print(f"{'='*60}\n")

    return result


# ═════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GigScore agents_012 pipeline")
    parser.add_argument('--mode',       choices=['train', 'score'], default='score')
    parser.add_argument('--persona',    default='raju_sharma')
    parser.add_argument('--pdf',        default=STATEMENT_PATH)
    parser.add_argument('--amount',     type=float, default=45000)
    parser.add_argument('--skip_agent0',action='store_true',
                        help='Skip Agent 0 parsing, use existing agent0_features.csv')
    args = parser.parse_args()

    if args.mode == 'train':
        run_training_pipeline()
    else:
        result = run_inference_pipeline(
            persona_id   = args.persona,
            pdf_path     = args.pdf,
            loan_amount  = args.amount,
            skip_agent0  = args.skip_agent0,
        )
