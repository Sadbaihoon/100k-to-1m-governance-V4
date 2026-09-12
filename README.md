# 100K → 1M Investment Governance V4

Institutional-style US equity research prototype.

## Architecture
Data → Evidence → Analysis → Risk → Early Warning → Governance → Decision → Audit

## Separate outputs
- Research Evidence Score: evidence strength, not a Buy Rating.
- Evidence Coverage: completeness of observable inputs.
- Risk Score: severity of risk; higher is worse.
- Early Warning: emerging risk/problem status.
- Short-term Regime: EMA20 / EMA50.
- Long-term Regime: EMA50 / EMA200.
- Risk/Reward: minimum governance threshold 2.0x.

## Core rule
No single score can authorize an investment.

## Run
`python -m streamlit run app_us_research.py`

## Limitations
Early Warning is a first-pass current-state rules engine. True deterioration detection requires storing periodic snapshots and comparing them over time. SQLite on Streamlit Cloud may not provide durable historical persistence across restarts/redeployments.
