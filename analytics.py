from __future__ import annotations
import math
import pandas as pd
TRADING_DAYS=252

def _num(v):
    try:
        if v is None or isinstance(v,bool): return None
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def as_number(v, default=None):
    x=_num(v); return default if x is None else x

def _col(df,name):
    if df is None or df.empty: return pd.Series(dtype='float64')
    if name in df.columns:
        s=df[name]
        if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
        return pd.to_numeric(s,errors='coerce')
    if isinstance(df.columns,pd.MultiIndex):
        for c in df.columns:
            if name in [str(x) for x in c]:
                s=df[c]
                if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
                return pd.to_numeric(s,errors='coerce')
    return pd.Series(index=df.index,dtype='float64')

def adjusted_close(history):
    s=_col(history,'Adj Close');
    if s.dropna().empty: s=_col(history,'Close')
    s=s.dropna().copy(); s.index=pd.to_datetime(s.index); s=s[~s.index.duplicated(keep='last')]
    return s.sort_index().astype(float)

def _ema(s,n): return s.ewm(span=n,adjust=False,min_periods=n).mean()
def _rsi(s,n=14):
    d=s.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
    ag=g.ewm(alpha=1/n,adjust=False,min_periods=n).mean(); al=l.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    return 100-100/(1+ag/al.replace(0,float('nan')))
def _dd(s):
    s=s.dropna(); return None if s.empty else float((s/s.cummax()-1).min())
def _regime(s,fast,slow):
    if len(s)<slow:return 'INSUFFICIENT DATA'
    p=s.iloc[-1]; a=_ema(s,fast).iloc[-1]; b=_ema(s,slow).iloc[-1]
    if any(pd.isna(x) for x in [p,a,b]):return 'INSUFFICIENT DATA'
    return 'BULLISH' if p>a>b else 'BEARISH' if p<a<b else 'NEUTRAL'

def calculate_indicators(history,benchmark_history=None):
    s=adjusted_close(history)
    if s.empty:return {'current_price':None,'short_term_regime':'INSUFFICIENT DATA','long_term_regime':'INSUFFICIENT DATA','regime':'INSUFFICIENT DATA'}
    ret=s.pct_change().dropna(); h=_col(history,'High').reindex(s.index); l=_col(history,'Low').reindex(s.index); pc=s.shift(1)
    tr=pd.concat([(h-l).abs(),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    vol=ret.std()*math.sqrt(TRADING_DAYS)*100 if len(ret)>20 else None
    beta=rel=None
    if benchmark_history is not None:
        b=adjusted_close(benchmark_history); br=b.pct_change()
        j=pd.concat([ret.rename('a'),br.rename('b')],axis=1).dropna()
        if len(j)>=30 and j.b.var()>0: beta=j.a.cov(j.b)/j.b.var()
        if len(s)>=64 and len(b)>=64: rel=(s.iloc[-1]/s.iloc[-64]-1)-(b.iloc[-1]/b.iloc[-64]-1)
    st=_regime(s,20,50); lt=_regime(s,50,200)
    regime='BULLISH' if st==lt=='BULLISH' else 'BEARISH' if st==lt=='BEARISH' else 'MIXED'
    return {'current_price':float(s.iloc[-1]),'ema20':_num(_ema(s,20).iloc[-1]),'ema50':_num(_ema(s,50).iloc[-1]),'ema100':_num(_ema(s,100).iloc[-1]),'ema200':_num(_ema(s,200).iloc[-1]),'rsi14':_num(_rsi(s).iloc[-1]),'atr14':_num(tr.rolling(14).mean().iloc[-1]),'volatility':_num(vol),'maxDrawdown':_num(_dd(s)),'beta':_num(beta),'relativeReturn63d':_num(rel),'short_term_regime':st,'long_term_regime':lt,'regime':regime,'data_points':len(s)}

def prepare_ema_chart(history,timeframe,periods=(20,50,100,200)):
    s=adjusted_close(history)
    if s.empty:return pd.DataFrame()
    t=timeframe.lower()
    if t.startswith('week'): s=s.resample('W-FRI').last().dropna(); years=5
    elif t.startswith('month'): s=s.resample('MS').last().dropna(); years=20
    else: years=2
    out=pd.DataFrame({'Price':s})
    for n in periods: out[f'EMA {n}']=_ema(s,n)
    start=out.index.max()-pd.DateOffset(years=years)
    return out.loc[out.index>=start]

def calculate_risk_reward(entry,stop,target):
    e,s,t=map(_num,(entry,stop,target));
    if None in (e,s,t):return {'valid':False,'risk_per_share':0,'reward_per_share':0,'rr_ratio':0}
    r=e-s; w=t-e; return {'valid':r>0 and w>0,'risk_per_share':r,'reward_per_share':w,'rr_ratio':w/r if r>0 else 0}

def calculate_position_risk(*,account_value,risk_budget_pct,entry_price,stop_price,returns=None):
    a=_num(account_value) or 0; b=_num(risk_budget_pct) or 0; e=_num(entry_price); s=_num(stop_price); r=(e-s) if e is not None and s is not None else 0; budget=a*b/100
    shares=math.floor(budget/r) if r>0 else 0; var=cvar=None
    if returns is not None:
        x=pd.Series(returns).dropna()
        if len(x)>=30:
            q=x.quantile(.05); var=q*100; tail=x[x<=q]; cvar=tail.mean()*100 if not tail.empty else var
    return {'risk_budget_value':budget,'max_shares':shares,'position_value':shares*e if e else 0,'loss_at_stop':shares*r,'historical_var_5':var,'historical_cvar_5':cvar,'risk_per_share':r}

def run_ema_backtest(history,transaction_cost_bps=10):
    s=adjusted_close(history)
    if len(s)<220:return {'available':False,'reason':'Insufficient price history.'}
    sig=(_ema(s,20)>_ema(s,50)).astype(int).shift(1).fillna(0); ret=s.pct_change().fillna(0); cost=sig.diff().abs().fillna(0)*transaction_cost_bps/10000; sr=sig*ret-cost; eq=(1+sr).cumprod(); bm=(1+ret).cumprod()
    years=(eq.index[-1]-eq.index[0]).days/365.25; ar=(eq.iloc[-1]/eq.iloc[0])**(1/years)-1 if years>0 else None; av=sr.std()*math.sqrt(TRADING_DAYS); sh=ar/av if av else None
    return {'available':True,'annual_return':ar,'annual_volatility':av,'max_drawdown':_dd(eq),'sharpe':sh,'trades':int(sig.diff().abs().sum()),'benchmark_return':(bm.iloc[-1]/bm.iloc[0])**(1/years)-1 if years>0 else None}

def calculate_research_score(indicators,fundamentals):
    from scoring_engine import calculate_research_evidence_score
    r=calculate_research_evidence_score(indicators,fundamentals); return {'evidence':r['score'],'coverage':r['coverage'],**r}
