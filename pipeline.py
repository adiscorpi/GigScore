"""
GigScore — LangGraph Pipeline
==============================
Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University

Wires all agents into a single LangGraph pipeline.
Each agent is a node. State flows between them.

Usage:
    # Full pipeline from PDF + loan application
    python pipeline.py --pdf gigscore_statement_raju_sharma.pdf \
                       --app raju_sharma_loan_application.pdf

    # Skip Agent 0 (use existing agent0_features.csv)
    python pipeline.py --skip_agent0 \
                       --app raju_sharma_loan_application.pdf

    # Stream mode (shows each agent firing live)
    python pipeline.py --stream

Install:
    pip install langgraph langchain-core
"""

import argparse
import importlib.util
import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings('ignore')

# ── Check langgraph installed ─────────────────────────────────────────────
try:
    from langgraph.graph import StateGraph, END
    from typing import TypedDict, Optional, List
except ImportError:
    print("❌ LangGraph not installed.")
    print("   Run: pip install langgraph langchain-core")
    sys.exit(1)

# ── Colour helpers ────────────────────────────────────────────────────────
BOLD  = "\033[1m"
GREEN = "\033[92m"
BLUE  = "\033[94m"
NAVY  = "\033[34m"
RED   = "\033[91m"
RESET = "\033[0m"

def log(agent, msg, colour=BLUE):
    print(f"{colour}{BOLD}[{agent}]{RESET} {msg}")

def ok(agent, msg):
    print(f"{GREEN}{BOLD}[{agent}] ✅ {msg}{RESET}")


# ─────────────────────────────────────────────────────────────────────────
# STATE DEFINITION
# Every field that flows between agents lives here.
# ─────────────────────────────────────────────────────────────────────────

class GigScoreState(TypedDict):
    # ── Inputs ───────────────────────────────────────────────────────────
    pdf_path:            str    # bank statement PDF
    loan_app_pdf:        str    # loan application PDF
    persona_id:          str
    loan_type:           str
    loan_amount:         float
    skip_agent0:         bool

    # ── Loan application (parsed) ─────────────────────────────────────────
    applicant_name:      str
    tenure_preference_m: int
    loan_purpose:        str
    ev_preference:       bool
    monthly_expense_est: float
    has_existing_loan:   bool

    # ── Agent 0 outputs ───────────────────────────────────────────────────
    applicant_token:     str
    features_csv:        str    # path to agent0_features.csv
    transactions_count:  int

    # ── Agent 2 outputs ───────────────────────────────────────────────────
    default_prob:        float
    raw_gigscore:        float
    shap_top3:           list
    monthly_income:      float
    features:            dict   # full feature row — used by Agent 3 + 4

    # ── Agent 3 outputs ───────────────────────────────────────────────────
    social_trust_score:  float
    score_adjustment:    int
    agent3_zone:         str
    behavioral_score:    float

    # ── Agent 4 outputs ───────────────────────────────────────────────────
    final_gigscore:      float
    tier:                str
    decision:            str
    reasoning:           str
    positive_signals:    list
    risk_factors:        list
    improvement_plan:    Optional[dict]
    thin_file:           bool

    # ── Agent 6 outputs ───────────────────────────────────────────────────
    loan_offer:          Optional[dict]

    # ── Pipeline metadata ─────────────────────────────────────────────────
    errors:              list
    elapsed_times:       dict


# ─────────────────────────────────────────────────────────────────────────
# HELPER — load local module by file path
# ─────────────────────────────────────────────────────────────────────────

def load_module(name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────────
# NODE 0 — Parse loan application PDF
# ─────────────────────────────────────────────────────────────────────────

def parse_loan_app_node(state: GigScoreState) -> GigScoreState:
    t0 = time.time()

    # ── Fallback: use existing loan_application.json if PDF parse fails ──
    def load_from_existing_json():
        if Path('loan_application.json').exists():
            with open('loan_application.json') as f:
                data = json.load(f)
            persona_id = list(data.keys())[0]
            app        = data[persona_id]
            elapsed    = round(time.time() - t0, 2)
            ok("LoanApp", f"Using existing loan_application.json | {elapsed}s")
            return {
                **state,
                'persona_id':          persona_id,
                'applicant_name':      app.get('applicant_name', persona_id.replace('_', ' ').title()),
                'loan_type':           app.get('loan_type', state.get('loan_type', 'vehicle')),
                'loan_amount':         float(app.get('requested_amount', state.get('loan_amount', 45000))),
                'tenure_preference_m': app.get('tenure_preference_m', 18),
                'loan_purpose':        app.get('loan_purpose_detail', ''),
                'ev_preference':       app.get('ev_preference', False),
                'monthly_expense_est': app.get('monthly_expense_est', 0.0),
                'has_existing_loan':   app.get('has_existing_loan', False),
                'elapsed_times':       {**state.get('elapsed_times', {}), 'loan_app': elapsed},
            }
        return None

    log("LoanApp", f"Parsing {state['loan_app_pdf']}...")
    try:
        mod = load_module("parse_loan_application", "parse_loan_application.py")
        app = mod.parse_loan_application(state['loan_app_pdf'])

        agent6_format = {
            app['persona_id']: {
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
        with open('loan_application.json', 'w') as f:
            json.dump(agent6_format, f, indent=2)

        elapsed = round(time.time() - t0, 2)
        ok("LoanApp", f"{app['applicant_name']} | {app['loan_type']} ₹{app['requested_amount']:,} | {elapsed}s")

        return {
            **state,
            'persona_id':          app['persona_id'],
            'applicant_name':      app['applicant_name'],
            'loan_type':           app['loan_type'],
            'loan_amount':         float(app['requested_amount']),
            'tenure_preference_m': app['tenure_preference_m'],
            'loan_purpose':        app['loan_purpose_detail'],
            'ev_preference':       app['ev_preference'],
            'monthly_expense_est': app['monthly_expense_est'],
            'has_existing_loan':   app['has_existing_loan'],
            'elapsed_times':       {**state.get('elapsed_times', {}), 'loan_app': elapsed},
        }
    except Exception as e:
        log("LoanApp", f"PDF parse failed ({e}) — trying loan_application.json fallback", RED)
        fallback = load_from_existing_json()
        if fallback:
            return fallback
        return {**state, 'errors': state.get('errors', []) + [f"LoanApp: {e}"]}


# ─────────────────────────────────────────────────────────────────────────
# NODE 1 — Agent 0: Parse bank statement + extract features
# ─────────────────────────────────────────────────────────────────────────

def agent0_node(state: GigScoreState) -> GigScoreState:
    t0 = time.time()

    if state.get('skip_agent0') and Path('agent0_features.csv').exists():
        log("Agent 0", "Using existing agent0_features.csv (skip_agent0=True)")
        # Build minimal result
        df = pd.read_csv('agent0_features.csv')
        token = str(df.get('applicant_token', pd.Series(['APPL_unknown']))[0]) \
                if 'applicant_token' in df.columns else 'APPL_unknown'
        ok("Agent 0", f"Loaded existing features | token={token}")
        return {
            **state,
            'applicant_token':    token,
            'features_csv':       'agent0_features.csv',
            'transactions_count': 0,
            'elapsed_times': {**state.get('elapsed_times', {}), 'agent0': 0},
        }

    log("Agent 0", f"Parsing {state['pdf_path']}...")
    try:
        mod    = load_module("agent0_parser", "agent0_parser.py")
        result, features = mod.run(state['pdf_path'])
        elapsed = round(time.time() - t0, 2)
        ok("Agent 0", f"{len(result['transactions']):,} txns | token={result['applicant_token']} | {elapsed}s")

        return {
            **state,
            'applicant_token':    result['applicant_token'],
            'features_csv':       'agent0_features.csv',
            'transactions_count': len(result['transactions']),
            'elapsed_times': {**state.get('elapsed_times', {}), 'agent0': elapsed},
        }
    except Exception as e:
        log("Agent 0", f"Error: {e}", RED)
        return {**state, 'errors': state.get('errors', []) + [f"Agent0: {e}"]}


# ─────────────────────────────────────────────────────────────────────────
# NODE 2 — Agents 1+2: Feature engineering + XGBoost scoring
# ─────────────────────────────────────────────────────────────────────────

def agents_012_node(state: GigScoreState) -> GigScoreState:
    t0 = time.time()
    log("Agent 1+2", "Feature engineering + scoring...")

    def load_from_existing_json(persona_id):
        """Fall back to agent2_result_*.json if already exists on disk."""
        a2_path = Path(f'agent2_result_{persona_id}.json')
        if not a2_path.exists():
            matches = list(Path('.').glob('agent2_result_*.json'))
            if matches:
                a2_path = matches[0]
        if a2_path.exists():
            with open(a2_path) as f:
                a2 = json.load(f)
            log("Agent 1+2", f"Using cached {a2_path.name} "
                             f"(default_prob={a2.get('default_prob','?')})")
            return a2
        return None

    try:
        mod      = load_module("agents_012", "agents_012.py")
        features = mod.run_agent1_inference(state.get('features_csv', 'agent0_features.csv'))
        a2       = mod.run_agent2_inference(features)

        df = pd.read_csv(state.get('features_csv', 'agent0_features.csv'))
        monthly_income = float(df['AMT_INCOME_MONTHLY'].iloc[0]) \
                         if 'AMT_INCOME_MONTHLY' in df.columns else 45000.0

        persona_id = state.get('persona_id', 'raju_sharma')
        result = {
            'persona_id':      persona_id,
            'applicant_token': state.get('applicant_token', 'APPL_unknown'),
            **a2,
            'monthly_income':  monthly_income,
            'features':        features.iloc[0].to_dict(),
        }
        with open(f'agent2_result_{persona_id}.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)

        elapsed = round(time.time() - t0, 2)
        ok("Agent 1+2", f"default_prob={a2['default_prob']:.3f} | raw_gigscore={a2['raw_gigscore']} | {elapsed}s")

        return {
            **state,
            'default_prob':   a2['default_prob'],
            'raw_gigscore':   a2['raw_gigscore'],
            'shap_top3':      a2.get('shap_top3', []),
            'monthly_income': monthly_income,
            'features':       features.iloc[0].to_dict(),
            'elapsed_times':  {**state.get('elapsed_times', {}), 'agents_012': elapsed},
        }

    except Exception as e:
        log("Agent 1+2", f"Error: {e} — trying cached result", RED)
        # Fall back to existing agent2_result json
        persona_id = state.get('persona_id', 'raju_sharma')
        a2 = load_from_existing_json(persona_id)
        if a2:
            elapsed = round(time.time() - t0, 2)
            # Also read monthly income from CSV
            monthly_income = 45000.0
            try:
                df = pd.read_csv(state.get('features_csv', 'agent0_features.csv'))
                if 'AMT_INCOME_MONTHLY' in df.columns:
                    monthly_income = float(df['AMT_INCOME_MONTHLY'].iloc[0])
            except Exception:
                pass

            ok("Agent 1+2", f"default_prob={a2.get('default_prob',0):.3f} | "
                            f"raw_gigscore={a2.get('raw_gigscore',0)} | {elapsed}s (cached)")
            return {
                **state,
                'default_prob':   float(a2.get('default_prob', 0.20)),
                'raw_gigscore':   float(a2.get('raw_gigscore', 50.0)),
                'shap_top3':      a2.get('shap_top3', []),
                'monthly_income': float(a2.get('monthly_income', monthly_income)),
                'features':       a2.get('features', {}),
                'elapsed_times':  {**state.get('elapsed_times', {}), 'agents_012': elapsed},
            }
        return {**state, 'errors': state.get('errors', []) + [f"Agents012: {e}"]}


# ─────────────────────────────────────────────────────────────────────────
# NODE 3 — Agent 3: Social trust + behavioral scoring
# ─────────────────────────────────────────────────────────────────────────

def agent3_node(state: GigScoreState) -> GigScoreState:
    t0 = time.time()
    log("Agent 3", "Social trust + behavioral scoring...")

    try:
        mod     = load_module("agent3", "agent3.py")
        results = mod.run_agent3()
        record  = results[0] if results else {}

        elapsed = round(time.time() - t0, 2)
        ok("Agent 3", f"trust={record.get('social_trust_score', 0):.1f} | "
                      f"adj=+{record.get('score_adjustment', 0)} | "
                      f"zone={record.get('zone_recommendation', 'N/A')} | {elapsed}s")

        return {
            **state,
            'social_trust_score': float(record.get('social_trust_score', 50)),
            'score_adjustment':   int(record.get('score_adjustment', 0)),
            'agent3_zone':        record.get('zone_recommendation', 'CLEAR'),
            'behavioral_score':   float(record.get('step3_behavioral_score', 0)),
            'elapsed_times':      {**state.get('elapsed_times', {}), 'agent3': elapsed},
        }
    except Exception as e:
        log("Agent 3", f"Error: {e} — using proxy", RED)
        # Fallback: proxy social trust from features
        return {
            **state,
            'social_trust_score': 50.0,
            'score_adjustment':   0,
            'agent3_zone':        'CLEAR',
            'behavioral_score':   0.0,
            'errors': state.get('errors', []) + [f"Agent3: {e}"],
        }


# ─────────────────────────────────────────────────────────────────────────
# NODE 4 — Agent 4: Final GigScore + explanation
# ─────────────────────────────────────────────────────────────────────────

def agent4_node(state: GigScoreState) -> GigScoreState:
    t0 = time.time()
    log("Agent 4", "Computing final GigScore + explanation...")

    try:
        mod     = load_module("agent4", "agent4.py")
        outputs = mod.run_agent4()

        # Read from saved agent4_output.json
        with open('agent4_output.json') as f:
            a4_data = json.load(f)
        record = list(a4_data.values())[0]

        elapsed = round(time.time() - t0, 2)
        ok("Agent 4", f"GigScore={record['final_gigscore']} | "
                      f"{record['emoji']} {record['tier']} | "
                      f"{record['decision']} | {elapsed}s")

        return {
            **state,
            'final_gigscore':  record['final_gigscore'],
            'tier':            record['tier'],
            'decision':        record['decision'],
            'reasoning':       record['reasoning'],
            'positive_signals':record.get('positive_signals', []),
            'risk_factors':    record.get('risk_factors', []),
            'improvement_plan':record.get('improvement_plan'),
            'thin_file':       record.get('thin_file', True),
            'elapsed_times':   {**state.get('elapsed_times', {}), 'agent4': elapsed},
        }
    except Exception as e:
        log("Agent 4", f"Error: {e}", RED)
        return {**state, 'errors': state.get('errors', []) + [f"Agent4: {e}"]}


# ─────────────────────────────────────────────────────────────────────────
# NODE 5 — Agent 6: Loan structuring
# ─────────────────────────────────────────────────────────────────────────

def agent6_node(state: GigScoreState) -> GigScoreState:
    t0 = time.time()
    log("Agent 6", "Structuring loan offer...")

    try:
        # Use agent6.py from same directory as pipeline.py
        agent6_path = Path(__file__).parent / "agent6.py"
        mod         = load_module("agent6", str(agent6_path))
        mod.run_agent6()

        with open('agent6_output.json') as f:
            a6_data = json.load(f)
        offer   = list(a6_data.values())[0]
        elapsed = round(time.time() - t0, 2)

        if offer['decision'] == 'DECLINED':
            ok("Agent 6", f"❌ DECLINED | GigScore={offer['gigscore']:.0f} | {elapsed}s")
        else:
            ok("Agent 6", f"{offer['emoji']} ₹{offer['approved_amount']:,} @ "
                          f"{offer['interest_rate_pct']}% | "
                          f"EMI ₹{offer['monthly_emi']:,.0f} | {elapsed}s")

        return {
            **state,
            'loan_offer':    offer,
            'elapsed_times': {**state.get('elapsed_times', {}), 'agent6': elapsed},
        }
    except Exception as e:
        log("Agent 6", f"Error: {e}", RED)
        # Try reading existing output before giving up
        if Path('agent6_output.json').exists():
            try:
                with open('agent6_output.json') as f:
                    a6_data = json.load(f)
                offer = list(a6_data.values())[0]
                log("Agent 6", "Using existing agent6_output.json")
                return {**state, 'loan_offer': offer,
                        'elapsed_times': {**state.get('elapsed_times', {}), 'agent6': 0}}
            except Exception:
                pass
        return {**state, 'errors': state.get('errors', []) + [f"Agent6: {e}"]}
    except Exception as e:
        log("Agent 6", f"Error: {e}", RED)
        return {**state, 'errors': state.get('errors', []) + [f"Agent6: {e}"]}


# ─────────────────────────────────────────────────────────────────────────
# BUILD GRAPH
# ─────────────────────────────────────────────────────────────────────────

def build_pipeline():
    graph = StateGraph(GigScoreState)

    graph.add_node("parse_loan_app", parse_loan_app_node)
    graph.add_node("agent0",         agent0_node)
    graph.add_node("agents_012",     agents_012_node)
    graph.add_node("agent3",         agent3_node)
    graph.add_node("agent4",         agent4_node)
    graph.add_node("agent6",         agent6_node)

    graph.add_edge("parse_loan_app", "agent0")
    graph.add_edge("agent0",         "agents_012")
    graph.add_edge("agents_012",     "agent3")
    graph.add_edge("agent3",         "agent4")
    graph.add_edge("agent4",         "agent6")
    graph.add_edge("agent6",         END)

    graph.set_entry_point("parse_loan_app")
    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────
# PRINT FINAL RESULT
# ─────────────────────────────────────────────────────────────────────────

def print_result(state: GigScoreState):
    offer = state.get('loan_offer', {})
    times = state.get('elapsed_times', {})
    total = sum(times.values())

    # If raw_gigscore wasn't propagated in state, read from agent4_output.json
    raw_gigscore = state.get('raw_gigscore', 0)
    applicant_name = state.get('applicant_name', '')
    if (raw_gigscore == 0 or not applicant_name) and Path('agent4_output.json').exists():
        try:
            with open('agent4_output.json') as f:
                a4 = json.load(f)
            rec = list(a4.values())[0]
            raw_gigscore   = rec.get('raw_gigscore', raw_gigscore)
            applicant_name = applicant_name or rec.get('persona_id', '?').replace('_', ' ').title()
        except Exception:
            pass

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║              GIGSCORE PIPELINE COMPLETE                         ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Applicant       : {applicant_name:<46}║")
    print(f"║  Persona ID      : {state.get('persona_id','?'):<46}║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Raw GigScore    : {raw_gigscore:<46}║")
    print(f"║  Social Trust    : {state.get('social_trust_score', 0):<46}║")
    print(f"║  Agent 3 Adj     : +{state.get('score_adjustment', 0):<45}║")
    print(f"║  FINAL GigScore  : {state.get('final_gigscore', 0):<46}║")
    print(f"║  Tier            : {state.get('tier','?'):<46}║")
    print(f"║  Decision        : {state.get('decision','?'):<46}║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    if offer and offer.get('decision') != 'DECLINED':
        print(f"║  Loan Type       : {offer.get('loan_type','?').title():<46}║")
        print(f"║  Approved        : ₹{offer.get('approved_amount',0):>10,}                             ║")
        print(f"║  Rate            : {offer.get('interest_rate_pct','?')}% p.a.                                     ║")
        print(f"║  Tenure          : {offer.get('tenure_months','?')} months                                        ║")
        print(f"║  Monthly EMI     : ₹{offer.get('monthly_emi',0):>10,.2f}                             ║")
        print(f"║  FOIR Used       : {offer.get('foir_used_pct','?')}% / 40%                                  ║")
        saved = offer.get('interest_saved_vs_market', 0)
        print(f"║  Interest Saved  : ₹{saved:>10,.0f} vs 28% market                ║")
    elif offer and offer.get('decision') == 'DECLINED':
        print(f"║  ❌ DECLINED — {offer.get('reason','')[:50]:<52}║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  TIMING                                                          ║")
    for node, t in times.items():
        print(f"║    {node:<20} : {t:.1f}s                                      ║")
    print(f"║    {'TOTAL':<20} : {total:.1f}s                                      ║")
    if state.get('errors'):
        print("╠══════════════════════════════════════════════════════════════════╣")
        print("║  ⚠ ERRORS                                                        ║")
        for e in state['errors']:
            print(f"║    {e[:64]:<64}║")
    print("╚══════════════════════════════════════════════════════════════════╝")


# ─────────────────────────────────────────────────────────────────────────
# STREAM MODE — shows each agent firing live
# ─────────────────────────────────────────────────────────────────────────

def run_streaming(pipeline, initial_state: dict):
    print(f"\n{BOLD}Streaming pipeline...{RESET}\n")

    # Accumulate state across all chunks — stream returns per-node diffs only
    accumulated = dict(initial_state)

    for chunk in pipeline.stream(initial_state):
        node_name  = list(chunk.keys())[0]
        node_state = chunk[node_name]

        # Merge this node's output into accumulated state
        accumulated.update(node_state)

        # Print what this node produced
        if node_name == "parse_loan_app":
            name = accumulated.get('applicant_name', '?')
            lt   = accumulated.get('loan_type', '?')
            amt  = accumulated.get('loan_amount', 0)
            print(f"  📋 {node_name:<20} → {name} | {lt} ₹{amt:,.0f}")

        elif node_name == "agent0":
            txns = accumulated.get('transactions_count', 0)
            tok  = accumulated.get('applicant_token', '?')
            skip = '(existing CSV)' if txns == 0 else f'{txns:,} txns'
            print(f"  📄 {node_name:<20} → {skip} | token={tok}")

        elif node_name == "agents_012":
            dp  = accumulated.get('default_prob', 0)
            rgs = accumulated.get('raw_gigscore', 0)
            print(f"  🤖 {node_name:<20} → default_prob={dp:.3f} | raw_gigscore={rgs:.1f}")

        elif node_name == "agent3":
            trust = accumulated.get('social_trust_score', 0)
            adj   = accumulated.get('score_adjustment', 0)
            zone  = accumulated.get('agent3_zone', '?')
            print(f"  🕸  {node_name:<20} → trust={trust:.1f} | adj=+{adj} | zone={zone}")

        elif node_name == "agent4":
            gs  = accumulated.get('final_gigscore', 0)
            tier= accumulated.get('tier', '?')
            dec = accumulated.get('decision', '?')
            print(f"  🎯 {node_name:<20} → GigScore={gs} | {tier} | {dec}")

        elif node_name == "agent6":
            offer = accumulated.get('loan_offer', {})
            if offer and offer.get('decision') != 'DECLINED':
                print(f"  🏦 {node_name:<20} → {offer.get('emoji','')} "
                      f"₹{offer.get('approved_amount',0):,} "
                      f"@ {offer.get('interest_rate_pct','?')}% | "
                      f"EMI ₹{offer.get('monthly_emi',0):,.0f}")
            else:
                reason = (offer or {}).get('reason', 'check errors')
                print(f"  🏦 {node_name:<20} → ❌ DECLINED | {reason[:40]}")

        # Print any errors from this node immediately
        errors = node_state.get('errors', [])
        for err in errors:
            print(f"  {RED}⚠  {err}{RESET}")

    return accumulated


# ─────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GigScore LangGraph Pipeline")
    parser.add_argument('--pdf',         default="gigscore_statement_raju_sharma.pdf",
                        help="Bank statement PDF")
    parser.add_argument('--app',         default="raju_sharma_loan_application.pdf",
                        help="Loan application PDF")
    parser.add_argument('--persona',     default="raju_sharma")
    parser.add_argument('--loan_type',   default="vehicle")
    parser.add_argument('--amount',      type=float, default=45000)
    parser.add_argument('--skip_agent0', action='store_true',
                        help="Skip Agent 0, use existing agent0_features.csv")
    parser.add_argument('--stream',      action='store_true',
                        help="Stream mode — print each agent as it fires")
    args = parser.parse_args()

    print("=" * 68)
    print("GigScore — LangGraph Pipeline")
    print("Barclays Hack-O-Hire 2026 · Team GigScore · Plaksha University")
    print("=" * 68)
    print()

    # Build pipeline
    pipeline = build_pipeline()

    # Initial state
    initial_state = {
        "pdf_path":            args.pdf,
        "loan_app_pdf":        args.app,
        "persona_id":          args.persona,
        "loan_type":           args.loan_type,
        "loan_amount":         args.amount,
        "skip_agent0":         args.skip_agent0,
        "applicant_name":      "",
        "tenure_preference_m": 18,
        "loan_purpose":        "",
        "ev_preference":       False,
        "monthly_expense_est": 0.0,
        "has_existing_loan":   False,
        "applicant_token":     "",
        "features_csv":        "agent0_features.csv",
        "transactions_count":  0,
        "default_prob":        0.0,
        "raw_gigscore":        0.0,
        "shap_top3":           [],
        "monthly_income":      0.0,
        "features":            {},
        "social_trust_score":  50.0,
        "score_adjustment":    0,
        "agent3_zone":         "CLEAR",
        "behavioral_score":    0.0,
        "final_gigscore":      0.0,
        "tier":                "",
        "decision":            "",
        "reasoning":           "",
        "positive_signals":    [],
        "risk_factors":        [],
        "improvement_plan":    None,
        "thin_file":           True,
        "loan_offer":          None,
        "errors":              [],
        "elapsed_times":       {},
    }

    t_total = time.time()

    if args.stream:
        final_state = run_streaming(pipeline, initial_state)
    else:
        print(f"  Running pipeline for: {args.persona}")
        print(f"  PDF:  {args.pdf}")
        print(f"  App:  {args.app}")
        print()
        final_state = pipeline.invoke(initial_state)

    total_elapsed = round(time.time() - t_total, 1)

    print_result(final_state)
    print(f"\n  Total pipeline time: {total_elapsed}s")

    # Save final state
    with open('pipeline_result.json', 'w') as f:
        # Remove non-serializable items
        save_state = {k: v for k, v in final_state.items() if k != 'features'}
        json.dump(save_state, f, indent=2, default=str)
    print(f"  Full result saved → pipeline_result.json")


if __name__ == "__main__":
    main()
