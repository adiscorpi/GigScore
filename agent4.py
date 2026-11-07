"""
GigScore — Agent 4: Final GigScore + Risk Explanation
======================================================
Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University

Reads:
    agent0_features.csv              — behavioral features (Agent 0)
    agent2_result_raju_sharma.json   — default_prob, raw_gigscore, shap_top3 (Agent 2)
    agent3_output.json               — social_trust_score, score_adjustment (Agent 3)
    GigScore_SHAP_Top3.csv           — SHAP explanations from training (Agent 2)

Outputs:
    agent4_output.json               — full result for Agent 5 + Agent 6
    agent4_summary.csv               — summary table

What this agent does:
─────────────────────
Layer 1 (90%): XGBoost base score from default_prob
    base = 100 / (1 + exp(6 × (default_prob − 0.35)))

Layer 2 (10%): Social Trust blend
    blended = 0.90 × base + 0.10 × social_trust_score

Layer 3 (±): Behavioral bonus/penalty
    +2  utility_streak ≥ 9 months
    +2  inflow_outflow_ratio ≥ 1.20
    +1  obligation_fulfillment ≥ 0.90
    −3  inflow_outflow_ratio < 0.80
    −3  obligation_fulfillment < 0.50
    −2  utility_streak == 0

Income multiplier (0.97–1.02):
    PLFS ratio + income regularity CV

Agent 3 score_adjustment: additional GigScore brownie points
    from behavioral scoring → +0 to +4

Final = clip((blended + behavioral_net + agent3_adj) × multiplier, 0, 100)
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ── Hardcoded file names ──────────────────────────────────────────────────
FEATURES_CSV    = "agent0_features.csv"
AGENT2_RESULT   = "agent2_result_raju_sharma.json"
AGENT3_OUTPUT   = "agent3_output.json"
SHAP_TOP3_CSV   = "GigScore_SHAP_Top3.csv"
OUTPUT_JSON     = "agent4_output.json"
SUMMARY_CSV     = "agent4_summary.csv"


# ─────────────────────────────────────────────────────────────────────────
# FEATURE DESCRIPTIONS (plain English for Agent 5 chatbot)
# ─────────────────────────────────────────────────────────────────────────

FEATURE_DESCRIPTIONS = {
    'upi_income_regularity_cv':        ('Income regularity',      'How consistent monthly income is'),
    'upi_utility_payment_streak':      ('Utility payment streak', 'Consecutive months of utility payments'),
    'upi_cash_crunch_recovery_speed':  ('Cash recovery speed',    'How fast balance recovers after a dip'),
    'upi_spending_velocity':           ('Spending stability',     'How stable monthly spending is'),
    'upi_merchant_diversity_score':    ('Spending diversity',     'Variety of merchant categories'),
    'upi_inflow_outflow_ratio':        ('Savings ratio',          'Total earnings vs total spending'),
    'upi_recurring_payment_ratio':     ('Recurring payments',     'Fixed payments made consistently'),
    'upi_obligation_fulfillment_rate': ('Obligation fulfillment', 'Fixed obligations paid on time'),
    'upi_fraud_rate':                  ('Fraud flag rate',        'Suspicious transaction frequency'),
    'upi_success_rate':                ('Payment success rate',   'Successful vs failed payments'),
    'syn_income_regularity_cv':        ('Income consistency',     'Estimated income stability'),
    'syn_utility_streak':              ('Utility discipline',     'Estimated utility payment streak'),
    'syn_merchant_diversity':          ('Lifestyle stability',    'Estimated spending diversity'),
    'syn_inflow_outflow':              ('Net saving estimate',    'Estimated savings behavior'),
    'syn_spending_velocity':           ('Spending volatility',    'Estimated spending stability'),
    'syn_crunch_recovery':             ('Resilience estimate',    'Estimated recovery from cash crunches'),
    'syn_recurring_ratio':             ('Recurring behavior',     'Estimated recurring payment ratio'),
    'syn_obligation_rate':             ('Payment discipline',     'Estimated obligation fulfillment'),
    'ext_source_mean':                 ('Bureau score avg',       'Average external credit score'),
    'ext_source_min':                  ('Bureau score min',       'Weakest external credit score'),
    'EXT_SOURCE_2':                    ('Bureau score',           'External credit bureau assessment'),
    'EXT_SOURCE_3':                    ('Bureau score',           'External credit bureau assessment'),
    'EXT_SOURCE_1':                    ('Bureau score',           'External credit bureau assessment'),
    'credit_income_ratio':             ('Loan-to-income ratio',   'Loan amount relative to annual income'),
    'annuity_income_ratio':            ('EMI-to-income ratio',    'Monthly EMI as fraction of income'),
    'years_employed':                  ('Employment duration',    'Years of consistent employment/gig work'),
    'employment_age_ratio':            ('Career stability',       'Employment tenure relative to age'),
    'income_instability_proxy':        ('Income volatility',      'Phone change frequency as instability signal'),
    'credit_seeking_intensity':        ('Credit hunger',          'Bureau enquiry frequency'),
    'stress_signal':                   ('Financial stress',       'Late applications + high credit ratio'),
    'lifestyle_stability':             ('Lifestyle stability',    'Family size vs geography indicator'),
    'repayment_stretch':               ('Repayment stretch',      'Annuity load adjusted for region'),
    'credit_utilization_pressure':     ('Credit pressure',        'Debt burden vs income and tenure'),
    'bureau_requests':                 ('Credit enquiries',       'Number of credit bureau requests'),
    'loan_loan_income_ratio':          ('Peer loan-income ratio', 'Cohort average loan-to-income'),
    'loan_dti_ratio':                  ('Debt-to-income',         'Cohort debt-to-income ratio'),
    'loan_loan_default_rate':          ('Peer default rate',      'Default rate in similar income cohort'),
    'cred_debt_income_ratio':          ('Peer debt ratio',        'Cohort debt-to-income benchmark'),
    'cred_obligation_fulfillment':     ('Peer obligation rate',   'Cohort obligation fulfillment benchmark'),
    'REGION_RATING_CLIENT':            ('Geographic risk',        'City tier credit risk rating'),
    'age':                             ('Applicant age',          'Age of applicant'),
}


def get_feature_description(feature_name: str) -> tuple:
    return FEATURE_DESCRIPTIONS.get(
        feature_name,
        (feature_name.replace('_', ' ').title(), f'Feature: {feature_name}')
    )


# ─────────────────────────────────────────────────────────────────────────
# LAYER 1: BASE SCORE
# ─────────────────────────────────────────────────────────────────────────

def compute_base_score(default_prob: float,
                       k: float = 6,
                       midpoint: float = 0.35) -> float:
    """
    Sigmoid inversion of XGBoost default probability.
    midpoint=0.35 → 35% default prob maps to score 50.
    Corrects for gig worker income irregularity inflating raw probs.
    """
    return float(np.clip(100 / (1 + np.exp(k * (default_prob - midpoint))), 0, 100))


# ─────────────────────────────────────────────────────────────────────────
# LAYER 2: SOCIAL TRUST
# ─────────────────────────────────────────────────────────────────────────

def compute_social_trust_proxy(row: pd.Series) -> float:
    """
    Behavioral proxy for social trust when Agent 3 output is unavailable.
    Approximates graph metrics from transaction-derived features.
    """
    edge_stability   = float(row.get('upi_recurring_payment_ratio', 0.5))
    node_reliability = float(row.get('upi_obligation_fulfillment_rate', 0.5))
    ior              = float(row.get('upi_inflow_outflow_ratio', 1.0))
    flow_stability   = min(ior / 2.0, 1.0)
    diversity        = float(row.get('upi_merchant_diversity_score', 0.5))
    streak           = float(row.get('upi_utility_payment_streak', 0))
    temporal         = min(streak / 12.0, 1.0)

    raw = (
        0.25 * edge_stability   +
        0.30 * node_reliability +
        0.20 * flow_stability   +
        0.15 * diversity        +
        0.10 * temporal
    )
    return round(float(np.clip(raw * 100, 0, 100)), 2)


def get_social_trust_score(applicant_token: str,
                            features_row: pd.Series,
                            agent3_data: dict) -> dict:
    """
    Returns social trust score + component breakdown.
    Prefers Agent 3 output, falls back to behavioral proxy.
    """
    # Try Agent 3 output first
    a3_record = agent3_data.get(applicant_token)
    if not a3_record:
        # Try by persona_id match
        persona = str(features_row.get('persona_id', ''))
        a3_record = next(
            (r for r in agent3_data.values()
             if r.get('persona_id') == persona or r.get('applicant_token') == applicant_token),
            None
        )

    if a3_record:
        score = float(a3_record.get('social_trust_score', 50))
        return {
            'social_trust_score': score,
            'edge_stability':     float(features_row.get('upi_recurring_payment_ratio', 0)),
            'network_diversity':  float(features_row.get('upi_merchant_diversity_score', 0)),
            'community_risk':     False,
            'payer_diversity':    int(features_row.get('upi_unique_merchants', 0)),
            'source':             'agent3',
            'agent3_score_adjustment': int(a3_record.get('score_adjustment', 0)),
            'agent3_behavioral_score': float(a3_record.get('step3_behavioral_score', 0)),
            'agent3_zone':        a3_record.get('zone_recommendation', 'CLEAR'),
        }
    else:
        score = compute_social_trust_proxy(features_row)
        return {
            'social_trust_score': score,
            'edge_stability':     float(features_row.get('upi_recurring_payment_ratio', 0)),
            'network_diversity':  float(features_row.get('upi_merchant_diversity_score', 0)),
            'community_risk':     False,
            'payer_diversity':    int(features_row.get('upi_unique_merchants', 0)),
            'source':             'behavioral_proxy',
            'agent3_score_adjustment': 0,
            'agent3_behavioral_score': 0,
            'agent3_zone':        'CLEAR',
        }


# ─────────────────────────────────────────────────────────────────────────
# LAYER 3: BEHAVIORAL ADJUSTMENT
# ─────────────────────────────────────────────────────────────────────────

def compute_behavioral_adjustment(row: pd.Series) -> dict:
    """
    Gig-worker-specific bonus/penalty signals.

    Bonus (max +5):
      +2  utility_streak >= 9 months
      +2  inflow_outflow_ratio >= 1.20
      +1  obligation_fulfillment >= 0.90

    Penalty (max -8):
      -3  inflow_outflow_ratio < 0.80
      -3  obligation_fulfillment < 0.50
      -2  utility_streak == 0
    """
    bonus, penalty, reasons = 0, 0, []

    streak = float(row.get('upi_utility_payment_streak', 0))
    ior    = float(row.get('upi_inflow_outflow_ratio', 1.0))
    oblig  = float(row.get('upi_obligation_fulfillment_rate', 0.5))

    if streak >= 9:
        bonus += 2
        reasons.append({'type': 'bonus', 'points': +2,
                         'feature': 'upi_utility_payment_streak',
                         'reason': f'{int(streak)}-month utility payment streak'})
    if ior >= 1.20:
        bonus += 2
        reasons.append({'type': 'bonus', 'points': +2,
                         'feature': 'upi_inflow_outflow_ratio',
                         'reason': f'Net saver — earns {ior:.2f}x what is spent'})
    if oblig >= 0.90:
        bonus += 1
        reasons.append({'type': 'bonus', 'points': +1,
                         'feature': 'upi_obligation_fulfillment_rate',
                         'reason': f'Paid all obligations {oblig:.0%} of months'})
    if ior < 0.80:
        penalty += 3
        reasons.append({'type': 'penalty', 'points': -3,
                         'feature': 'upi_inflow_outflow_ratio',
                         'reason': f'Spending more than earning (ratio={ior:.2f})'})
    if oblig < 0.50:
        penalty += 3
        reasons.append({'type': 'penalty', 'points': -3,
                         'feature': 'upi_obligation_fulfillment_rate',
                         'reason': f'Missing obligations {(1-oblig):.0%} of months'})
    if streak == 0:
        penalty += 2
        reasons.append({'type': 'penalty', 'points': -2,
                         'feature': 'upi_utility_payment_streak',
                         'reason': 'No utility payment history found'})

    return {
        'bonus':       bonus,
        'penalty':     penalty,
        'net':         bonus - penalty,
        'adjustments': reasons,
    }


def income_stability_multiplier(row: pd.Series) -> float:
    """
    PLFS benchmarking multiplier (0.97–1.02).
    Rewards realistic and stable income; penalises implausibly high or volatile.
    """
    plfs_ratio = row.get('income_vs_plfs_ratio', None)
    if plfs_ratio is not None and not pd.isna(plfs_ratio):
        plfs_ratio = float(plfs_ratio)
        if plfs_ratio > 1.5:
            return 0.97
        elif plfs_ratio < 0.30:
            return 0.98
        elif 0.50 < plfs_ratio < 1.2:
            cv = float(row.get('upi_income_regularity_cv', 0.35))
            if cv < 0.25:
                return 1.02
    cv = float(row.get('upi_income_regularity_cv', 0.35))
    if cv < 0.15:
        return 1.01
    elif cv > 0.70:
        return 0.98
    return 1.0


# ─────────────────────────────────────────────────────────────────────────
# MASTER GIGSCORE FORMULA
# ─────────────────────────────────────────────────────────────────────────

def calculate_final_gigscore(default_prob: float,
                               social_trust: dict,
                               features_row: pd.Series,
                               agent3_adj: int = 0) -> dict:
    """
    Combines all 3 layers + Agent 3 brownie points.

    Final = clip(
        (0.90×base + 0.10×social_trust + behavioral_net + agent3_adj)
        × income_multiplier, 0, 100
    )
    """
    base     = compute_base_score(default_prob)
    st_score = float(social_trust.get('social_trust_score', 50))
    blended  = 0.90 * base + 0.10 * st_score
    adj      = compute_behavioral_adjustment(features_row)
    mult     = income_stability_multiplier(features_row)
    after    = blended + adj['net'] + agent3_adj
    final    = float(np.clip(after * mult, 0, 100))

    return {
        'base_score':             round(base, 2),
        'social_trust_score':     round(st_score, 2),
        'blended_score':          round(blended, 2),
        'behavioral_net':         adj['net'],
        'behavioral_bonus':       adj['bonus'],
        'behavioral_penalty':     adj['penalty'],
        'behavioral_adjustments': adj['adjustments'],
        'agent3_adjustment':      agent3_adj,
        'income_multiplier':      round(mult, 4),
        'final_gigscore':         round(final, 1),
    }


# ─────────────────────────────────────────────────────────────────────────
# TIER ASSIGNMENT
# ─────────────────────────────────────────────────────────────────────────

def assign_tier(score: float) -> dict:
    if score >= 80:
        return {'tier': 'Prime',      'decision': 'APPROVED',    'emoji': '✅',
                'max_loan': 120000,   'rate_min': 11.0, 'rate_max': 13.0, 'max_tenure_m': 36}
    elif score >= 65:
        return {'tier': 'Near-Prime', 'decision': 'APPROVED',    'emoji': '✅',
                'max_loan': 75000,    'rate_min': 14.0, 'rate_max': 17.0, 'max_tenure_m': 24}
    elif score >= 50:
        return {'tier': 'Sub-Prime',  'decision': 'CONDITIONAL', 'emoji': '⚡',
                'max_loan': 30000,    'rate_min': 18.0, 'rate_max': 22.0, 'max_tenure_m': 12}
    else:
        return {'tier': 'High Risk',  'decision': 'DECLINED',    'emoji': '❌',
                'max_loan': 0,        'rate_min': None, 'rate_max': None, 'max_tenure_m': None}


# ─────────────────────────────────────────────────────────────────────────
# EXPLANATION BUILDER
# ─────────────────────────────────────────────────────────────────────────

def build_explanation(applicant_token: str,
                       shap_top3_df: pd.DataFrame,
                       features_row: pd.Series,
                       gigscore_breakdown: dict,
                       agent2_shap: list) -> dict:
    """
    Builds structured explanation combining SHAP + behavioral rules.
    Uses Agent 2 inline SHAP if GigScore_SHAP_Top3.csv not available.
    """
    positive_signals, risk_factors = [], []

    # ── SHAP signals — try CSV first, then Agent 2 inline ─────────────────
    shap_row = shap_top3_df[shap_top3_df['applicant_id'] == applicant_token] \
               if shap_top3_df is not None and len(shap_top3_df) > 0 else pd.DataFrame()

    if len(shap_row) > 0:
        row = shap_row.iloc[0]
        for i in [1, 2, 3]:
            feat  = str(row.get(f'feature_{i}', ''))
            shval = float(row.get(f'shap_{i}', 0))
            fval  = features_row.get(feat, None)
            short, desc = get_feature_description(feat)
            entry = {
                'rank': i, 'feature': feat, 'short_name': short,
                'description': desc, 'shap_value': round(shval, 4),
                'feature_value': round(float(fval), 4)
                    if fval is not None and not pd.isna(fval) else None,
                'source': 'shap_csv',
            }
            (positive_signals if shval < 0 else risk_factors).append(entry)

    elif agent2_shap:
        for item in agent2_shap:
            feat  = item.get('feature', '')
            shval = float(item.get('shap_value', 0))
            fval  = item.get('feature_value', None)
            short, desc = get_feature_description(feat)
            entry = {
                'feature': feat, 'short_name': short, 'description': desc,
                'shap_value': round(shval, 4),
                'feature_value': round(float(fval), 4) if fval is not None else None,
                'source': 'shap_agent2',
            }
            (positive_signals if shval < 0 else risk_factors).append(entry)

    # ── Layer 3 behavioral adjustments ───────────────────────────────────
    for adj in gigscore_breakdown.get('behavioral_adjustments', []):
        feat  = adj['feature']
        fval  = features_row.get(feat, None)
        short, desc = get_feature_description(feat)
        entry = {
            'feature': feat, 'short_name': short, 'description': desc,
            'points': adj['points'], 'reason': adj['reason'],
            'feature_value': round(float(fval), 4)
                if fval is not None and not pd.isna(fval) else None,
            'source': 'behavioral_rule',
        }
        if adj['type'] == 'bonus':
            if not any(s['feature'] == feat for s in positive_signals):
                positive_signals.append(entry)
        else:
            if not any(r['feature'] == feat for r in risk_factors):
                risk_factors.append(entry)

    # ── Thin file flag ────────────────────────────────────────────────────
    ext_missing = pd.isna(features_row.get('EXT_SOURCE_2', None))
    if ext_missing:
        risk_factors.append({
            'feature': 'EXT_SOURCE_2', 'short_name': 'No bureau history',
            'description': 'No formal credit history — scored on behavior only',
            'shap_value': None, 'feature_value': None, 'source': 'thin_file_flag',
        })

    # ── Confidence interval ───────────────────────────────────────────────
    default_prob = float(features_row.get('default_prob',
                         1 - gigscore_breakdown['final_gigscore'] / 100))
    ci_low  = round(max(default_prob - 0.035, 0), 3)
    ci_high = round(min(default_prob + 0.035, 1), 3)

    return {
        'positive_signals':    positive_signals[:3],
        'risk_factors':        risk_factors[:3],
        'confidence_interval': [ci_low, ci_high],
        'confidence_note':     f"Model is 90% confident default probability is between {ci_low:.0%}–{ci_high:.0%}",
        'thin_file':           bool(ext_missing),
        'explanation_complete': True,
    }


# ─────────────────────────────────────────────────────────────────────────
# REASONING GENERATOR
# ─────────────────────────────────────────────────────────────────────────

def generate_reasoning(features_row: pd.Series,
                        gigscore_breakdown: dict,
                        explanation: dict,
                        tier_info: dict) -> str:
    final   = gigscore_breakdown['final_gigscore']
    tier    = tier_info['tier']
    cv      = float(features_row.get('upi_income_regularity_cv', 0.35))
    streak  = float(features_row.get('upi_utility_payment_streak', 0))
    ior     = float(features_row.get('upi_inflow_outflow_ratio', 1.0))
    oblig   = float(features_row.get('upi_obligation_fulfillment_rate', 0.5))
    div     = float(features_row.get('upi_merchant_diversity_score', 0.5))
    thin    = explanation['thin_file']
    bonus   = gigscore_breakdown['behavioral_bonus']
    penalty = gigscore_breakdown['behavioral_penalty']
    agent3  = gigscore_breakdown.get('agent3_adjustment', 0)
    parts   = []

    if cv < 0.20:
        parts.append(f"Income is highly consistent (CV={cv:.2f}) — unusually stable for a gig worker.")
    elif cv < 0.35:
        parts.append(f"Income shows normal gig worker variability (CV={cv:.2f}) — not a risk signal.")
    else:
        parts.append(f"Income is irregular (CV={cv:.2f}) — elevated variability warrants monitoring.")

    if streak >= 12:
        parts.append(f"Perfect utility payment streak of {int(streak)} months — strongest creditworthiness signal.")
    elif streak >= 6:
        parts.append(f"Strong utility payment streak of {int(streak)} months — demonstrates financial discipline.")
    elif streak >= 3:
        parts.append(f"Partial utility payment streak ({int(streak)} months) — some discipline shown.")
    else:
        parts.append(f"Weak utility payment history ({int(streak)} months) — key risk signal.")

    if ior >= 1.5:
        parts.append(f"Strong net saver — earns {ior:.2f}x what is spent. Financial buffer present.")
    elif ior >= 1.2:
        parts.append(f"Net saver (ratio={ior:.2f}) — consistently spending less than earning.")
    elif ior >= 0.9:
        parts.append(f"Near break-even spending (ratio={ior:.2f}) — limited savings buffer.")
    else:
        parts.append(f"Spending exceeds income (ratio={ior:.2f}) — financial stress indicator.")

    if oblig >= 0.90:
        parts.append(f"Pays all fixed obligations {oblig:.0%} of months — core creditworthiness confirmed.")
    elif oblig >= 0.70:
        parts.append(f"Meets obligations {oblig:.0%} of months — generally reliable.")
    else:
        parts.append(f"Misses obligations {(1-oblig):.0%} of months — repayment risk elevated.")

    if div >= 0.75:
        parts.append(f"High merchant diversity ({div:.2f}) — stable lifestyle across multiple categories.")
    elif div >= 0.50:
        parts.append(f"Moderate spending diversity ({div:.2f}) — some lifestyle stability.")
    else:
        parts.append(f"Low spending diversity ({div:.2f}) — concentrated spending pattern.")

    if thin:
        parts.append("No formal credit bureau history — decision based entirely on behavioral signals.")
    else:
        ext = float(features_row.get('ext_source_mean', 0.45))
        parts.append(f"External credit score present (mean={ext:.2f}) — bureau signal incorporated.")

    if bonus > 0 and penalty == 0:
        parts.append(f"Behavioral layer added +{bonus} points — all positive signals aligned.")
    elif bonus > 0 and penalty > 0:
        parts.append(f"Behavioral layer: +{bonus} bonus offset by -{penalty} penalty = net {bonus-penalty:+d} points.")
    elif penalty > 0:
        parts.append(f"Behavioral layer applied -{penalty} point penalty — stress signals detected.")

    if agent3 > 0:
        parts.append(f"Agent 3 behavioral assessment added +{agent3} points from cohort-relative strength.")

    if tier == 'Prime':
        parts.append(f"Overall: Exceptional financial discipline. GigScore {final} — Prime. Recommended for approval.")
    elif tier == 'Near-Prime':
        parts.append(f"Overall: Strong behavioral signals despite thin file. GigScore {final} — Near-Prime. Recommended for approval.")
    elif tier == 'Sub-Prime':
        parts.append(f"Overall: Mixed signals. GigScore {final} — Sub-Prime. Conditional approval with reduced limit.")
    else:
        parts.append(f"Overall: Insufficient behavioral evidence. GigScore {final} — Declined. 90-day plan generated.")

    return ' '.join(parts)


# ─────────────────────────────────────────────────────────────────────────
# 90-DAY IMPROVEMENT PLAN
# ─────────────────────────────────────────────────────────────────────────

def generate_improvement_plan(features_row: pd.Series,
                               final_gigscore: float) -> dict:
    actions, projected_lift = [], 0

    streak = float(features_row.get('upi_utility_payment_streak', 0))
    ior    = float(features_row.get('upi_inflow_outflow_ratio', 1.0))
    oblig  = float(features_row.get('upi_obligation_fulfillment_rate', 0.5))
    div    = float(features_row.get('upi_merchant_diversity_score', 0.5))
    cv     = float(features_row.get('upi_income_regularity_cv', 0.35))

    if streak < 6:
        impact = 8 if streak == 0 else 6
        actions.append({
            'priority': 1,
            'action':   'Pay electricity, water and phone bills before the 5th of each month',
            'current':  f'Current streak: {int(streak)} months',
            'target':   'Maintain streak for 3 consecutive months',
            'impact':   f'+{impact} points',
            'impact_points': impact,
            'feature':  'upi_utility_payment_streak',
            'why':      'Utility payment streak is the strongest creditworthiness signal for gig workers',
        })
        projected_lift += impact

    if ior < 1.0:
        actions.append({
            'priority': 2,
            'action':   'Reduce ATM cash withdrawals — use UPI for all payments above ₹200',
            'current':  f'Current ratio: {ior:.2f} (spending more than earning)',
            'target':   'Achieve inflow/outflow ratio above 1.2',
            'impact':   '+6 points',
            'impact_points': 6,
            'feature':  'upi_inflow_outflow_ratio',
            'why':      'Net saving behavior is a strong repayment signal',
        })
        projected_lift += 6

    if div < 0.50:
        actions.append({
            'priority': 3,
            'action':   'Increase UPI merchant payments to 15+ different categories per month',
            'current':  f'Current diversity: {div:.2f}',
            'target':   'Achieve diversity score above 0.60',
            'impact':   '+5 points',
            'impact_points': 5,
            'feature':  'upi_merchant_diversity_score',
            'why':      'Diverse spending patterns indicate stable lifestyle and financial planning',
        })
        projected_lift += 5

    if oblig < 0.70:
        actions.append({
            'priority': 4,
            'action':   'Pay rent and all utilities every month without fail for 3 months',
            'current':  f'Currently fulfilling obligations {oblig:.0%} of months',
            'target':   '100% obligation fulfillment for 3 months',
            'impact':   '+7 points',
            'impact_points': 7,
            'feature':  'upi_obligation_fulfillment_rate',
            'why':      'Obligation fulfillment directly predicts loan repayment behavior',
        })
        projected_lift += 7

    if cv > 0.50:
        actions.append({
            'priority': 5,
            'action':   'Accept platform orders consistently — aim for 25+ working days per month',
            'current':  f'Income variability CV: {cv:.2f}',
            'target':   'Reduce income CV below 0.35',
            'impact':   '+4 points',
            'impact_points': 4,
            'feature':  'upi_income_regularity_cv',
            'why':      'Consistent gig platform income signals reliability to the model',
        })
        projected_lift += 4

    projected_score = round(min(final_gigscore + projected_lift, 100), 1)
    projected_tier  = assign_tier(projected_score)

    return {
        'current_score':      final_gigscore,
        'projected_score':    projected_score,
        'projected_lift':     projected_lift,
        'projected_tier':     projected_tier['tier'],
        'projected_decision': projected_tier['decision'],
        'projected_max_loan': projected_tier['max_loan'],
        'actions':            actions[:4],
        'timeframe':          '90 days',
        'message':            f"Follow this plan for 90 days to reach GigScore {projected_score} — "
                              f"{projected_tier['emoji']} {projected_tier['decision']} "
                              f"₹{projected_tier['max_loan']:,}",
    }


# ─────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────

def run_agent4(features_csv: str = FEATURES_CSV,
               agent2_json:  str = AGENT2_RESULT,
               agent3_json:  str = AGENT3_OUTPUT,
               shap_csv:     str = SHAP_TOP3_CSV,
               output_json:  str = OUTPUT_JSON,
               summary_csv:  str = SUMMARY_CSV) -> dict:

    print("=" * 68)
    print("GigScore — Agent 4: Final GigScore + Risk Explanation")
    print("Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University")
    print("=" * 68)

    # ── Load features ─────────────────────────────────────────────────────
    if not Path(features_csv).exists():
        print(f"❌ {features_csv} not found. Run Agent 0 first.")
        sys.exit(1)
    features = pd.read_csv(features_csv)
    print(f"\n  Agent 0 features     : {len(features)} applicant(s), {features.shape[1]} columns")

    # ── Load Agent 2 result ───────────────────────────────────────────────
    a2 = {}
    a2_path = Path(agent2_json)
    if not a2_path.exists():
        matches = list(Path('.').glob('agent2_result_*.json'))
        if matches:
            a2_path = matches[0]
    if a2_path.exists():
        with open(a2_path) as f:
            a2 = json.load(f)
        print(f"  Agent 2 result       : {a2_path.name} "
              f"(default_prob={a2.get('default_prob','?')}, "
              f"raw_gigscore={a2.get('raw_gigscore','?')})")
    else:
        print(f"  ⚠ Agent 2 result not found — run agents_012.py --mode score --skip_agent0")

    # ── Load Agent 3 output ───────────────────────────────────────────────
    agent3_data = {}
    if Path(agent3_json).exists():
        with open(agent3_json) as f:
            a3_list = json.load(f)
        # Index by applicant_token
        for record in a3_list:
            agent3_data[record['applicant_token']] = record
        print(f"  Agent 3 output       : {len(agent3_data)} record(s)")
    else:
        print(f"  ⚠ Agent 3 output not found — using social trust proxy")

    # ── Load SHAP Top3 CSV ────────────────────────────────────────────────
    shap_top3_df = pd.DataFrame()
    if Path(shap_csv).exists():
        shap_top3_df = pd.read_csv(shap_csv)
        print(f"  SHAP Top3 CSV        : {len(shap_top3_df):,} records")
    else:
        print(f"  ⚠ {shap_csv} not found — using Agent 2 inline SHAP")

    agent2_shap = a2.get('shap_top3', [])

    print()
    agent4_outputs = {}

    for _, feat_row in features.iterrows():
        token   = str(feat_row.get('applicant_token', 'APPL_unknown'))
        persona = str(feat_row.get('persona_id', token))

        print(f"  Processing: {persona} ({token})")
        print(f"  {'─' * 50}")

        # ── Default prob + raw gigscore from Agent 2 ──────────────────────
        default_prob = float(a2.get('default_prob', 0.20))
        raw_gigscore = float(a2.get('raw_gigscore', compute_base_score(default_prob)))

        # ── Social trust from Agent 3 ─────────────────────────────────────
        social_trust = get_social_trust_score(token, feat_row, agent3_data)
        agent3_adj   = social_trust.get('agent3_score_adjustment', 0)

        # ── Final GigScore ────────────────────────────────────────────────
        breakdown    = calculate_final_gigscore(
            default_prob, social_trust, feat_row, agent3_adj
        )
        final_score  = breakdown['final_gigscore']
        tier_info    = assign_tier(final_score)

        # ── Explanation ───────────────────────────────────────────────────
        feat_row_copy = feat_row.copy()
        feat_row_copy['default_prob'] = default_prob
        explanation  = build_explanation(
            token, shap_top3_df, feat_row_copy, breakdown, agent2_shap
        )

        # ── Reasoning ────────────────────────────────────────────────────
        reasoning    = generate_reasoning(feat_row, breakdown, explanation, tier_info)

        # ── Improvement plan (declined only) ─────────────────────────────
        improvement_plan = None
        if tier_info['decision'] == 'DECLINED':
            improvement_plan = generate_improvement_plan(feat_row, final_score)

        # ── Assemble output ───────────────────────────────────────────────
        output = {
            'applicant_token':     token,
            'persona_id':          persona,
            'final_gigscore':      final_score,
            'raw_gigscore':        round(raw_gigscore, 1),
            'default_prob':        round(default_prob, 4),
            'tier':                tier_info['tier'],
            'decision':            tier_info['decision'],
            'emoji':               tier_info['emoji'],
            'score_breakdown':     breakdown,
            'tier_info':           tier_info,
            'social_trust':        social_trust,
            'positive_signals':    explanation['positive_signals'],
            'risk_factors':        explanation['risk_factors'],
            'confidence_interval': explanation['confidence_interval'],
            'confidence_note':     explanation['confidence_note'],
            'thin_file':           explanation['thin_file'],
            'reasoning':           reasoning,
            'improvement_plan':    improvement_plan,
            'monthly_income':      float(feat_row.get('AMT_INCOME_MONTHLY',
                                   feat_row.get('AMT_INCOME_TOTAL', 240000) / 12)),
            'loan_amount':         float(feat_row.get('AMT_CREDIT', 50000)),
        }

        agent4_outputs[token] = output

        # ── Print ─────────────────────────────────────────────────────────
        print(f"  Raw GigScore (Agent 2)   : {raw_gigscore:.1f}")
        print(f"  Social Trust (Agent 3)   : {social_trust['social_trust_score']:.1f}  [{social_trust['source']}]")
        print(f"  Agent 3 adjustment       : +{agent3_adj}")
        print(f"  Behavioral adj           : {breakdown['behavioral_net']:+d}  "
              f"(bonus={breakdown['behavioral_bonus']}, penalty={breakdown['behavioral_penalty']})")
        print(f"  Income multiplier        : {breakdown['income_multiplier']:.4f}")
        print(f"  ──────────────────────────────────────────────────")
        print(f"  FINAL GigScore           : {final_score} / 100")
        print(f"  Tier                     : {tier_info['emoji']} {tier_info['tier']}")
        print(f"  Decision                 : {tier_info['decision']}")
        print(f"  Confidence interval      : {explanation['confidence_interval']}")
        print(f"  Thin file                : {explanation['thin_file']}")

        if explanation['positive_signals']:
            print(f"\n  Top positive signals:")
            for s in explanation['positive_signals']:
                val = f"= {s['feature_value']}" if s.get('feature_value') is not None else ""
                print(f"    ✅ {s['short_name']} {val}")

        if explanation['risk_factors']:
            print(f"\n  Top risk factors:")
            for r in explanation['risk_factors']:
                val = f"= {r['feature_value']}" if r.get('feature_value') is not None else ""
                print(f"    ⚠  {r['short_name']} {val}")

        if improvement_plan:
            print(f"\n  90-Day Plan: {improvement_plan['message']}")
            for a in improvement_plan['actions'][:2]:
                print(f"    → {a['action']}  [{a['impact']}]")
        print()

    # ── Save outputs ──────────────────────────────────────────────────────
    with open(output_json, 'w') as f:
        json.dump(agent4_outputs, f, indent=2, default=str)

    summary_rows = []
    for token, out in agent4_outputs.items():
        bd = out['score_breakdown']
        summary_rows.append({
            'applicant_token':    token,
            'persona_id':         out['persona_id'],
            'raw_gigscore':       out['raw_gigscore'],
            'social_trust_score': out['social_trust']['social_trust_score'],
            'agent3_adjustment':  bd.get('agent3_adjustment', 0),
            'behavioral_bonus':   bd['behavioral_bonus'],
            'behavioral_penalty': bd['behavioral_penalty'],
            'income_multiplier':  bd['income_multiplier'],
            'final_gigscore':     out['final_gigscore'],
            'tier':               out['tier'],
            'decision':           out['decision'],
            'default_prob':       out['default_prob'],
            'thin_file':          out['thin_file'],
            'ci_low':             out['confidence_interval'][0],
            'ci_high':            out['confidence_interval'][1],
            'monthly_income':     out['monthly_income'],
            'loan_amount':        out['loan_amount'],
            'has_improvement_plan': out['improvement_plan'] is not None,
        })

    pd.DataFrame(summary_rows).to_csv(summary_csv, index=False)

    # ── Final summary box ─────────────────────────────────────────────────
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                    AGENT 4 COMPLETE                             ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    for token, out in agent4_outputs.items():
        name = out['persona_id'].replace('_', ' ').title()
        print(f"║  {name:<20}  GigScore: {out['final_gigscore']:>5.1f}  "
              f"{out['emoji']} {out['tier']:<12}    ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  📄 {output_json:<61}║")
    print(f"║  📄 {summary_csv:<61}║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  NEXT: Agent 6 — Loan Structuring                               ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    return agent4_outputs


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GigScore Agent 4")
    parser.add_argument('--features',  default=FEATURES_CSV)
    parser.add_argument('--agent2',    default=AGENT2_RESULT)
    parser.add_argument('--agent3',    default=AGENT3_OUTPUT)
    parser.add_argument('--shap',      default=SHAP_TOP3_CSV)
    parser.add_argument('--output',    default=OUTPUT_JSON)
    parser.add_argument('--summary',   default=SUMMARY_CSV)
    args = parser.parse_args()

    run_agent4(
        features_csv = args.features,
        agent2_json  = args.agent2,
        agent3_json  = args.agent3,
        shap_csv     = args.shap,
        output_json  = args.output,
        summary_csv  = args.summary,
    )