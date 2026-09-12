from __future__ import annotations
import math

def _num(v):
    try:
        if v is None or isinstance(v,bool):return None
        x=float(v);return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None

def _clamp(x):return max(0,min(100,float(x)))
def _coverage(keys,d):return 100*sum(_num(d.get(k)) is not None for k in keys)/len(keys)
def _avg(x):
    x=[v for v in x if v is not None];return sum(x)/len(x) if x else 50

def fundamental_evidence_score(f):return _coverage(['revenueGrowth','operatingMargins','freeCashflow','returnOnEquity','trailingEps','totalDebt'],f)
def technical_evidence_score(i):return _coverage(['ema20','ema50','ema100','ema200','rsi14','atr14'],i)
def relative_performance_score(i):return _coverage(['relativeReturn63d','beta'],i)
def valuation_evidence_score(f):return _coverage(['trailingPE','priceToBook','freeCashflow'],f)
def risk_evidence_score(i):return _coverage(['volatility','maxDrawdown','beta'],i)
def data_quality_score(i,f):return _avg([fundamental_evidence_score(f),technical_evidence_score(i),relative_performance_score(i)])

def calculate_research_evidence_score(i,f):
    c={'fundamental_evidence':fundamental_evidence_score(f),'technical_evidence':technical_evidence_score(i),'relative_performance':relative_performance_score(i),'valuation_evidence':valuation_evidence_score(f),'risk_evidence':risk_evidence_score(i),'data_quality':data_quality_score(i,f)}
    w={'fundamental_evidence':.30,'technical_evidence':.20,'relative_performance':.10,'valuation_evidence':.10,'risk_evidence':.15,'data_quality':.15}
    cov=_coverage(['revenueGrowth','operatingMargins','freeCashflow','returnOnEquity','trailingEps','totalDebt','trailingPE','priceToBook','ema20','ema50','ema100','ema200','rsi14','atr14','relativeReturn63d','beta','volatility','maxDrawdown'],{**f,**i})/100
    return {'score':round(_clamp(sum(c[k]*w[k] for k in w)),1),'coverage':round(cov,3),'components':{k:round(v,1) for k,v in c.items()},'weights':w,'interpretation':'Evidence strength and data coverage. Not a Buy Rating.'}

def volatility_risk(v):
    x=_num(v)
    if x is None:return 50
    return 10 if x<=20 else 25 if x<=30 else 45 if x<=45 else 65 if x<=60 else 80 if x<=80 else 95
def beta_risk(v):
    x=_num(v)
    if x is None:return 50
    return 15 if x<.8 else 30 if x<=1.2 else 50 if x<=1.5 else 70 if x<=2 else 85 if x<=3 else 95
def drawdown_risk(v):
    x=_num(v)
    if x is None:return 50
    p=abs(x*100) if abs(x)<=1 else abs(x);return 10 if p<=10 else 25 if p<=20 else 45 if p<=30 else 65 if p<=40 else 80 if p<=50 else 95
def fundamental_risk(f):
    r=[];x=_num(f.get('revenueGrowth'))
    if x is not None:r.append(15 if x>=.2 else 30 if x>=.1 else 50 if x>=0 else 75 if x>=-.1 else 90)
    x=_num(f.get('operatingMargins'))
    if x is not None:r.append(20 if x>=.2 else 35 if x>=.1 else 55 if x>=0 else 80)
    x=_num(f.get('freeCashflow'))
    if x is not None:r.append(20 if x>0 else 80)
    x=_num(f.get('returnOnEquity'))
    if x is not None:r.append(20 if x>=.15 else 40 if x>=.08 else 60 if x>=0 else 80)
    return _avg(r)
def valuation_risk(f):
    r=[];x=_num(f.get('trailingPE'))
    if x is not None and x>0:r.append(20 if x<=20 else 40 if x<=30 else 60 if x<=50 else 80 if x<=100 else 95)
    x=_num(f.get('priceToBook'))
    if x is not None and x>0:r.append(20 if x<=2 else 40 if x<=4 else 60 if x<=7 else 80 if x<=12 else 95)
    return _avg(r)
def event_risk(level=0):return {0:10,1:40,2:70,3:90}.get(int(level),50)
def position_risk(v):
    x=_num(v)
    if x is None:return 50
    p=abs(x);return 10 if p<=1 else 30 if p<=2 else 50 if p<=3 else 75 if p<=5 else 95

def calculate_risk_score(i,f,*,event_level=0,position_loss_pct=None):
    c={'volatility_risk':volatility_risk(i.get('volatility')),'beta_risk':beta_risk(i.get('beta')),'drawdown_risk':drawdown_risk(i.get('maxDrawdown')),'fundamental_risk':fundamental_risk(f),'valuation_risk':valuation_risk(f),'event_risk':event_risk(event_level),'position_risk':position_risk(position_loss_pct)}
    w={'volatility_risk':.2,'beta_risk':.15,'drawdown_risk':.15,'fundamental_risk':.15,'valuation_risk':.15,'event_risk':.1,'position_risk':.1}
    return {'score':round(_clamp(sum(c[k]*w[k] for k in w)),1),'components':{k:round(v,1) for k,v in c.items()},'weights':w,'direction':'Higher = Higher Risk'}

def evaluate_early_warning(*,indicators,fundamentals,risk_score,critical_signals=None,warning_signals=None):
    critical=list(critical_signals or []); warning=list(warning_signals or []);p=_num(indicators.get('current_price'));e20=_num(indicators.get('ema20'));e50=_num(indicators.get('ema50'));e200=_num(indicators.get('ema200'));rsi=_num(indicators.get('rsi14'));vol=_num(indicators.get('volatility'))
    if p is not None and e200 is not None and p<e200:warning.append('Price below EMA200')
    if e20 is not None and e50 is not None and e20<e50:warning.append('Short-term trend below EMA50')
    if rsi is not None and rsi<40:warning.append('Momentum weakening (RSI14 < 40)')
    if vol is not None and vol>60:warning.append('Elevated volatility')
    if _num(fundamentals.get('freeCashflow')) is not None and fundamentals.get('freeCashflow')<0:warning.append('Negative free cash flow')
    if _num(fundamentals.get('revenueGrowth')) is not None and fundamentals.get('revenueGrowth')<0:warning.append('Negative revenue growth')
    warning=list(dict.fromkeys(warning));critical=list(dict.fromkeys(critical))
    status='CRITICAL' if critical or risk_score>=80 else 'WARNING' if risk_score>=60 or len(warning)>=3 else 'WATCH' if risk_score>=40 or warning else 'NORMAL'
    return {'status':status,'critical_signals':critical,'warning_signals':warning,'override':bool(critical) or risk_score>=80}

def determine_investment_decision(*,research_score,risk_score,early_warning_status,thesis_status='INTACT',short_term_regime='NEUTRAL',long_term_regime='NEUTRAL',risk_reward=0):
    if thesis_status=='INVALIDATED':return {'decision':'EXIT REVIEW','reason':'Investment thesis is invalidated.','governance_principle':'No single score can authorize an investment.'}
    if early_warning_status=='CRITICAL' or risk_score>=80:return {'decision':'DO NOT INITIATE','reason':'Critical risk requires a governance stop.','governance_principle':'No single score can authorize an investment.'}
    if early_warning_status=='WARNING' or risk_score>=60:return {'decision':'HOLD / WAIT','reason':'Elevated risk requires further review.','governance_principle':'No single score can authorize an investment.'}
    if risk_reward<2:return {'decision':'HOLD / WAIT','reason':'Risk/reward is below the minimum 2.0x threshold.','governance_principle':'No single score can authorize an investment.'}
    if early_warning_status=='WATCH' or risk_score>=40:return {'decision':'WATCH','reason':'Risk or emerging-warning conditions require monitoring.','governance_principle':'No single score can authorize an investment.'}
    if research_score>=75 and thesis_status=='INTACT' and long_term_regime!='BEARISH':
        if short_term_regime=='BEARISH':return {'decision':'WATCH','reason':'Long-term evidence is acceptable, but short-term regime is bearish.','governance_principle':'No single score can authorize an investment.'}
        return {'decision':'ELIGIBLE FOR REVIEW','reason':'Evidence is strong and no major governance block is active.','governance_principle':'No single score can authorize an investment.'}
    return {'decision':'WATCH','reason':'Evidence is not sufficient for active review.','governance_principle':'No single score can authorize an investment.'}

def build_governance_snapshot(i,f,*,event_level=0,position_loss_pct=None,critical_signals=None,warning_signals=None,thesis_status='INTACT',short_term_regime=None,long_term_regime=None,risk_reward=0):
    st=short_term_regime or i.get('short_term_regime','NEUTRAL');lt=long_term_regime or i.get('long_term_regime','NEUTRAL');e=calculate_research_evidence_score(i,f);r=calculate_risk_score(i,f,event_level=event_level,position_loss_pct=position_loss_pct);w=evaluate_early_warning(indicators=i,fundamentals=f,risk_score=r['score'],critical_signals=critical_signals,warning_signals=warning_signals);d=determine_investment_decision(research_score=e['score'],risk_score=r['score'],early_warning_status=w['status'],thesis_status=thesis_status,short_term_regime=st,long_term_regime=lt,risk_reward=risk_reward)
    return {'research_evidence':e,'risk':r,'early_warning':w,'decision':d,'regime':{'short_term':st,'long_term':lt},'risk_reward':risk_reward}
