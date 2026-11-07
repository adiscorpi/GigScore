# GigScore

**Alternative credit scoring for India's gig workers.** Built for Barclays Hack-O-Hire 2026 by Team GigScore (Plaksha University).

Gig workers (delivery riders, drivers, freelancers) often have no formal credit history, so traditional bureau scores shut them out of loans. GigScore reads an applicant's bank statement instead, turns UPI and platform payout behaviour into credit signals, and produces an explainable 0–100 score with a lender-ready credit report.

## How it works

A multi-agent pipeline wired together with **LangGraph** (`pipeline.py`). Each agent is a graph node and state flows from one to the next:

| Agent | File | Role |
|---|---|---|
| 0: Parser + PII gate | `agent0_parser.py`, `agent0_pii_redaction.py` | Parses a 150-page bank statement PDF into transactions and behavioural features. Redacts PII before anything moves downstream, in line with India's DPDP Act 2023: salted SHA-256 tokens replace counterparty VPAs, and holder details are stripped. |
| 1 + 2: Model | `agent012.py`, notebooks | XGBoost default-probability model trained on Home Credit and UPI transaction data, with Optuna tuning, SMOTE class balancing and SHAP explanations (top 3 drivers per applicant). |
| 3: Social trust graph | `agent3.py` | Behavioural score from rootedness, obligations and payment velocity. Flags gambling, rent stress and net outflow from transaction narrations. |
| 4: Final GigScore | `agent4.py` | Blends the model score (90%) with social trust (10%), then applies behavioural bonuses and penalties to get a final score, risk tier and explanation. |
| 5: Credit story | `Agent5CreditStory.jsx` | LLM-generated plain-language credit narrative for the applicant and the lender. |
| 6: Loan decision | `agent6.py` | Parses the loan application PDF and matches it against the GigScore assessment. |

**Web app:** a React + Vite frontend (`GigScoreApp-2.jsx`, `src/`) served by an Express server (`server.mjs`) that runs the pipeline and builds HTML/PDF credit reports (`reporting.mjs`, PDFKit). It uses Groq, or OpenAI as a fallback.

## Results

The model evaluation charts are in the repo root: `chart_roc_comparison.png`, `chart_ensemble_roc.png`, `chart_shap_global.png`, `chart_shap_profiles.png`, `chart_gigscore_tiers.png`, `chart_learning_curve.png`, `chart_optuna.png` and `chart_agent4_dashboard.png`.

The demo applicants (for example `raju_sharma`) are **synthetic personas** made by the project's own data generator.

## Running it

```bash
# Python pipeline
python -m venv .venv && source .venv/bin/activate
pip install langgraph langchain-core xgboost optuna shap scikit-learn pandas numpy scipy pdfplumber
python pipeline.py --skip_agent0 --app raju_sharma_loan_application.pdf

# Web app
npm install
cp .env.example .env.local   # add a Groq (or OpenAI) API key
npm run dev                   # http://127.0.0.1:5173
```

### Datasets

The raw training data isn't included because of its size and licensing. Download it from Kaggle and put the files in the repo root:
- [Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk): `application_train.csv`, `HomeCredit_columns_description.csv`
- A loan default dataset (`Loan_default.csv`) and a UPI transactions dataset (`upi_transactions_2024.csv`)

## Tech

Python · XGBoost · Optuna · SHAP · scikit-learn · LangGraph · React · Vite · Node/Express · PDFKit · Groq/OpenAI
