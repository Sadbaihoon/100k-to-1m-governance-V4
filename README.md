# 100K → 1M Investment Governance V4 — Governance Hardened

US Equity Research Desk prototype focused on disciplined, auditable investment decisions.

## Architecture

**Data → Evidence → Analysis → Risk → Early Warning → Governance → Decision → Audit**

## Governance corrections in this build

1. **Risk/Reward is no longer manufactured by the governance engine.** Entry, Stop Loss, and Target are explicit planning inputs. The 2.0x threshold is a gate, not a generated outcome.
2. **Evidence Coverage is separate from Research Evidence Score.** Coverage measures completeness of required inputs. Research Evidence Score measures evidence usability/completeness and is explicitly not a Buy Rating or expected-return score.
3. **Short-term and long-term regimes remain separate.** Short-term uses EMA20/EMA50; long-term uses EMA50/EMA200.
4. **One canonical governance snapshot** is used for the dashboard, decision, and saved audit record, avoiding inconsistent pre-control and post-control states.
5. **Process readiness is separate from Investment Decision.** A process can be incomplete even when the analytical decision is WATCH or ELIGIBLE FOR REVIEW.
6. **Debt is acknowledged in Fundamental Risk** while avoiding a false leverage judgment from absolute debt alone. A future version can add debt/equity, net debt/EBITDA, and interest coverage.

## Core rule

> **No single score can authorize an investment.**

## Files

- `app_us_research.py` — Streamlit UI and governance workflow
- `analytics.py` — deterministic market analytics
- `scoring_engine.py` — evidence, risk, early-warning, and governance rules
- `storage.py` — decision journal storage
- `requirements.txt` — Python dependencies

## Run

```bash
python -m streamlit run app_us_research.py
```

The market data source is Yahoo Finance through `yfinance`. Data may be delayed or incomplete and should be independently verified before real-world use.
