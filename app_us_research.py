from __future__ import annotations
import json
import pandas as pd
import streamlit as st
import yfinance as yf
from analytics import adjusted_close, calculate_indicators, calculate_position_risk, calculate_research_score, calculate_risk_reward, prepare_ema_chart, run_ema_backtest
from scoring_engine import build_governance_snapshot
from storage import initialize_database, save_decision, get_decisions

BENCHMARK = '^GSPC'
st.set_page_config(page_title='US Equity Research Desk V4', page_icon='📊', layout='wide')

@st.cache_data(ttl=900)
def fetch(ticker):
    eq = yf.Ticker(ticker); bh = yf.Ticker(BENCHMARK)
    h = eq.history(period='max', auto_adjust=False); b = bh.history(period='max', auto_adjust=False); info = eq.info or {}
    def n(k):
        try: return float(info[k]) if info.get(k) is not None else None
        except: return None
    f = {k: n(k) for k in ['trailingPE','priceToBook','freeCashflow','returnOnEquity','operatingMargins','revenueGrowth','trailingEps','totalDebt']}
    c = adjusted_close(h)
    return h, b, f, info, c.iloc[-1] if not c.empty else None

def research_page():
    st.title('US Equity Research Desk V4')
    st.caption('Investment Governance — Data → Evidence → Analysis → Risk → Early Warning → Decision → Audit')
    ticker = st.sidebar.text_input('Ticker', 'KHC').strip().upper()
    try:
        h, b, f, info, price = fetch(ticker)
    except Exception as ex:
        st.error(f'Market data request failed: {ex}'); return
    if h.empty:
        st.error('No usable market history returned.'); return

    i = calculate_indicators(h, b)
    research = calculate_research_score(i, f)
    st.subheader(info.get('longName') or ticker)
    st.caption(f'{ticker} · {info.get("sector", "N/A")} · Benchmark {BENCHMARK}')

    cols = st.columns(6)
    vals = [
        ('Last price', f'${price:,.2f}' if price else 'N/A'),
        ('Short-term regime', i.get('short_term_regime', 'N/A')),
        ('Long-term regime', i.get('long_term_regime', 'N/A')),
        ('Volatility', f'{i["volatility"]:.1f}%' if i.get('volatility') is not None else 'N/A'),
        ('Beta', f'{i["beta"]:.2f}x' if i.get('beta') is not None else 'N/A'),
        ('Evidence Coverage', f'{research["coverage"]:.0%}'),
    ]
    for c, (a, v) in zip(cols, vals): c.metric(a, v)

    st.subheader('Risk / Reward Plan')
    st.caption('Risk/reward is an explicit planning input. The system does not manufacture a 2.0x ratio.')
    c = st.columns(4)
    with c[0]: entry = st.number_input('Entry price', min_value=.01, value=float(price or 1), step=.01)
    with c[1]: stop = st.number_input('Stop loss', min_value=.01, value=round(float(price or 1) * .95, 2), step=.01)
    with c[2]: target = st.number_input('Target price', min_value=.01, value=round(float(price or 1) * 1.15, 2), step=.01)
    with c[3]: account = st.number_input('Account value', min_value=0., value=100000., step=1000.)
    rr = calculate_risk_reward(entry, stop, target)
    if rr['valid']:
        st.write(f'Risk/share: **${rr["risk_per_share"]:.2f}** · Reward/share: **${rr["reward_per_share"]:.2f}** · R/R: **{rr["rr_ratio"]:.2f}x**')
        if rr['rr_ratio'] >= 2: st.success('Risk/reward passes the minimum 2.0x governance threshold.')
        else: st.warning('Risk/reward is below the minimum 2.0x governance threshold.')
    else:
        st.error('Invalid plan: Stop loss must be below Entry and Target must be above Entry.')

    pos = calculate_position_risk(account_value=account, risk_budget_pct=1, entry_price=entry, stop_price=stop, returns=adjusted_close(h).pct_change())
    st.write(f'Max shares: **{pos["max_shares"]:,}** · Position value: **${pos["position_value"]:,.0f}** · Loss at stop: **${pos["loss_at_stop"]:,.0f}** · CVaR: **{pos["historical_cvar_5"]:.2f}%**' if pos['historical_cvar_5'] is not None else 'CVaR: N/A')

    st.subheader('Technical Evidence')
    st.dataframe(pd.DataFrame({'Metric':['Price','EMA20','EMA50','EMA100','EMA200','RSI14','ATR14'],'Value':[i.get('current_price'),i.get('ema20'),i.get('ema50'),i.get('ema100'),i.get('ema200'),i.get('rsi14'),i.get('atr14')]}), hide_index=True, use_container_width=True)
    st.subheader('Price & EMA Evidence')
    tf = st.selectbox('Timeframe', ['Daily','Weekly','Monthly'])
    chart = prepare_ema_chart(h, tf, [20,50,100,200])
    if not chart.empty: st.line_chart(chart)

    st.subheader('Fundamental & Valuation Evidence')
    st.dataframe(pd.DataFrame({'Metric':list(f.keys()),'Value':list(f.values())}), hide_index=True, use_container_width=True)

    st.subheader('Governance Controls')
    c = st.columns(3)
    with c[0]: verified = st.checkbox('Primary-source data verified'); chart_ok = st.checkbox('Chart reviewed')
    with c[1]: event = st.checkbox('Pending material event'); calendar = st.checkbox('Event calendar reviewed'); cool = st.checkbox('Cooling-off complete')
    with c[2]: thesis = st.selectbox('Investment thesis', ['INTACT','UNDER REVIEW','INVALIDATED']); emotion = st.checkbox('Decision is not emotion-driven')
    notes = st.text_area('Governance notes')

    # One canonical snapshot. Dashboard and final status use the same state.
    snap = build_governance_snapshot(
        i, f,
        event_level=2 if event else 0,
        position_loss_pct=(pos['loss_at_stop'] / account * 100 if account else None),
        thesis_status=thesis,
        risk_reward=rr['rr_ratio'],
    )

    st.subheader('Governance Dashboard')
    cols = st.columns(7)
    vals = [
        ('Research Evidence', f'{snap["research_evidence"]["score"]:.1f}/100'),
        ('Evidence Coverage', f'{snap["research_evidence"]["coverage"]:.0%}'),
        ('Risk', f'{snap["risk"]["score"]:.1f}/100'),
        ('Early Warning', snap['early_warning']['status']),
        ('Short-term Regime', snap['regime']['short_term']),
        ('Long-term Regime', snap['regime']['long_term']),
        ('Decision', snap['decision']['decision']),
    ]
    for c, (a, v) in zip(cols, vals): c.metric(a, v)

    st.info('No single score can authorize an investment. ' + snap['decision']['reason'])
    if snap['early_warning']['critical_signals']:
        st.error('Critical: ' + ' · '.join(snap['early_warning']['critical_signals']))
    if snap['early_warning']['warning_signals']:
        st.warning('Warning signals: ' + ' · '.join(snap['early_warning']['warning_signals']))

    # Process readiness is separate from the investment decision.
    process_checks = {
        'Primary-source verification': verified,
        'Chart review': chart_ok,
        'Event calendar review': calendar,
        'Cooling-off complete': cool,
        'No pending material event': not event,
        'Emotion control': emotion,
        'Governance notes present': bool(notes.strip()),
        'Valid risk/reward plan': rr['valid'],
        'Risk/reward >= 2.0x': rr['rr_ratio'] >= 2,
        'Evidence coverage >= 60%': snap['research_evidence']['coverage'] >= .60,
    }
    process_ready = all(process_checks.values())
    st.subheader('Governance Process Status')
    st.write('**READY FOR HUMAN REVIEW**' if process_ready else '**PROCESS INCOMPLETE**')
    st.dataframe(pd.DataFrame({'Control':list(process_checks.keys()), 'Passed':list(process_checks.values())}), hide_index=True, use_container_width=True)

    if st.button('Save Governance Decision', type='primary'):
        audit = {'snapshot': snap, 'process_checks': process_checks, 'notes': notes}
        rid = save_decision(ticker=ticker, current_price=price, entry_price=entry, stop_loss=stop, target_price=target, risk_reward=rr['rr_ratio'], decision=snap['decision']['decision'], notes=json.dumps(audit, default=str))
        st.success(f'Saved audit ID: {rid}')

    with st.expander('Governance snapshot'):
        st.json(snap)

def journal_page():
    st.title('Governance Journal'); rows = get_decisions()
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True) if rows else st.info('No records yet.')

def methodology():
    st.title('V4 Methodology')
    st.markdown('''### Architecture\n**Data → Evidence → Analysis → Risk → Early Warning → Governance → Decision → Audit**\n\n### Governance outputs\n- **Research Evidence Score** — evidence usability/completeness; not a Buy Rating.\n- **Evidence Coverage** — completeness of observable inputs.\n- **Risk Score** — higher means higher risk.\n- **Early Warning** — current warning status; future versions can add time-series deterioration detection.\n- **Short-term Regime** — EMA20/EMA50.\n- **Long-term Regime** — EMA50/EMA200.\n- **Risk/Reward** — explicit Entry/Stop/Target inputs; minimum governance threshold 2.0x.\n- **Process Status** — operational readiness is separate from the investment decision.\n\n> **No single score can authorize an investment.**''')

initialize_database(); page = st.sidebar.radio('Desk', ['Research','Governance Journal','Methodology'])
if page == 'Research': research_page()
elif page == 'Governance Journal': journal_page()
else: methodology()
