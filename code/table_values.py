"""Explicit exhibit-to-result bindings. No estimation or reference-file reads."""
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
H=[1,3,6,12]
LAB=['PAYROLL','UNEMP','LFPR','JPR_PRIVATE_LONG','LMT_VU_LONG','HIRES_PRIVATE_LONG','QUITS_PRIVATE_LONG','LIG_JW','CLAIMS_INTENSITY']
GW=['DP','DY','EP','DE','BM','NTIS','TBL','LTY','TMS','DFY','LTR','DFR','SVAR','INFL']
SCEN=['baseline','oos2005','oos2015','train2000','rolling120','simple','nonnegative']
CACHE={}
def cell(file,field,p=None,scale=1,**key):
    if file not in CACHE:CACHE[file]=pd.read_csv(ROOT/'results'/file,low_memory=False)
    d=CACHE[file]
    for k,v in key.items():d=d[d[k].eq(v)]
    assert len(d)==1,(file,key,len(d))
    r=d.iloc[0]
    return dict(source=file,key=key,field=field,scale=scale,p_field=p,value=float(r[field])*scale,probability=float(r[p]) if p else None)
def cells(file,fields,**key):
    return [cell(file,f[0],f[1],**key) if isinstance(f,tuple) else cell(file,f,**key) for f in fields]
def cash(target,window,h,model='EE',fields=(('beta','p_formal'),'t_nw','p_formal','r2')):
    return cells('aligned/is_results.csv',fields,target=target,window=window,horizon=h,model=model,term='past_growth' if model=='PAST' else 'EE')
def coos(window,h,model='EE',benchmark='HA',fields=('r2_os',('cw','p_cw'),'p_cw')):
    return cells('aligned/oos_comparisons.csv',fields,target='D12',window=window,horizon=h,model=model,benchmark=benchmark)
def bindings():
    out={}
    def add(label,rows):out['tab:'+label]=rows
    for label,models in [('predictability',LAB+['E2E']),('B_gw',GW)]:
        rows=[]
        for m in models:
            first=[];second=[]
            for h in H:
                if m=='E2E':
                    first+=cells('aligned/is_results.csv',[('beta','p_formal'),'r2'],target='return',term='EE',horizon=h)
                    second+=cells('aligned/is_results.csv',['t_nw'],target='return',term='EE',horizon=h)
                else:
                    first+=cells('return_is.csv',[('beta','p_is'),'r2'],model=m,horizon=h)
                    second+=cells('return_is.csv',['t_nw'],model=m,horizon=h)
            for h in H:
                first+=cells('return_oos.csv',[('r2_os','p_cw')],model=m,horizon=h)
                second+=cells('return_oos.csv',['cw'],model=m,horizon=h)
            rows += [first,second]
        add(label,rows)
    add('economicvalue',[[cell('portfolio_summary.csv',metric,model=m,horizon=h) for h in H] for metric in ['utility_gain_pp','sharpe'] for m in ['E2E','HA','BUY_HOLD']])
    rows=[[cell('return_robustness.csv','r2_os','p_cw',scenario=s,horizon=h) for h in H] for s in SCEN]
    rows += [[cell('portfolio_robustness.csv','cer_gain_pp',scenario=s,model='E2E',horizon=h) for h in H] for s in ['baseline','gamma5','risk60','cost50','cost100']]
    add('robustness',rows)
    rows=[]
    for target,window,hs in [('E12','cumulative',[1,3,6,12,24,36,48,60]),('D12','cumulative',[1,3,6,12,24,36,48,60]),('D12','post',[24,36,48,60])]:
        for h in hs:
            row=cash(target,window,h,fields=[('beta','p_formal'),'t_nw','r2'])
            if target=='D12':row+=coos(window,h,fields=['r2_os',('cw','p_cw')])
            rows.append(row)
    add('cashflow',rows)
    outcomes=['LEHD_EEHireR','LFPR','EPR','CPS_UE','WGT_SWITCHER','WGT_STAYER','WGT_SPREAD','LS_NFB_INDEX']
    for label,targets in [('A_relations',outcomes),('laborinputs',outcomes[-4:])]:
        rows=[]
        for target in targets:
            first=[];second=[]
            for spec in (['contemporaneous','next'] if label=='A_relations' else ['contemporaneous']):
                first+=cells('data_relations.csv',[('beta','p'),'r2'],target=target,specification=spec)
                second+=cells('data_relations.csv',['t_nw'],target=target,specification=spec)
            for h in ([3,6,12] if target in ['LEHD_EEHireR','LS_NFB_INDEX'] else H):
                first+=cells('data_relations.csv',[('beta','p')],target=target,specification='conditional',horizon_months=h)
                second+=cells('data_relations.csv',['t_nw'],target=target,specification='conditional',horizon_months=h)
            rows += [first,second]
        if label=='laborinputs':
            for target in ['COMPNFB','OPHNFB','ULCNFB']:
                rows.append([cell('channel_production.csv','beta','p',target=target,window='short',variant=v,horizon=h) for v in ['baseline','controlled'] for h in [1,2,4]])
                rows.append([cell('channel_production.csv','t',target=target,window='short',variant=v,horizon=h) for v in ['baseline','controlled'] for h in [1,2,4]])
        add(label,rows)
    systems=['BASE','DY','EP','BM','NTIS','TBL','LTY','TERM','DFY','LTR','DFR','SVAR','INFL','PC3']+LAB
    add('decomposition',[[v for comp in ['ER','CF','DR'] for v in cells('channel_var.csv',[(f'beta_{comp}',f'p_{comp}'),f't_{comp}'],system=s)] for s in systems])
    multipliers={m:100 for m in ['LMT_VU_LONG','NTIS','TBL','LTY','TMS','DFY','LTR','DFR','INFL']}
    multipliers['SVAR']=10000
    add('A_summary',[[cell('data_descriptive.csv',f,scale=multipliers.get(m,1) if f in ['mean','median','p01','p99','sd'] else 1,variable=m) for f in ['n','mean','median','p01','p99','sd','ac1','corr_e2e']] for m in ['E2E']+LAB+GW+['MARKET_EXCESS_LOG_RETURN']])
    add('B_encompassing',[[v for base in [m,'E2E'] for h in H for v in cells('return_encompassing.csv',[('lambda_display','p_mhln'),'mhln'],partner=m,base=base,horizon=h)] for m in GW+LAB])
    add('B_combination',[[v for method in ['EW','DMSFE'] for h in H for v in cells('return_combinations.csv',[('r2_os','p_cw'),'cw'],partner=m,method=method,horizon=h)] for m in GW+LAB])
    add('B_portfolios',[[cell('portfolio_summary.csv',metric,model=m,horizon=h) for metric in ['utility_gain_pp','sharpe'] for h in H] for m in GW+LAB+['E2E','HA','BUY_HOLD']])
    add('B_forecast_robust',[[cell('return_robustness.csv',field,'p_cw' if field=='r2_os' else None,scenario=s,horizon=h) for h in H] for s in SCEN for field in ['r2_os','cw']])
    add('B_portfolio_robust',[[cell('portfolio_robustness.csv',metric,scenario=s,model=m,horizon=h) for metric in ['cer_gain_pp','sharpe','annualized_turnover'] for h in H] for s in ['baseline','gamma5','risk60','cost50','cost100']+SCEN[1:] for m in ['E2E','HA']])
    add('C_cash_controls',[cash('E12','cumulative',h,m)+cash('D12','cumulative',h,m)+cash('D12','cumulative',h,m,fields=['n']) for h in H for m in ['EE','PAST','JOINT']])
    add('C_cash_long',[cash('E12',w,h,m)+cash('D12',w,h,m)+cash('D12',w,h,m,fields=['n']) for w in ['cumulative','post'] for h in [24,36,48,60] for m in ['EE','JOINT']])
    add('C_cash_annual',[cash(t,'annual',12*y,m) for t in ['E12','D12'] for y in range(1,6) for m in ['EE','JOINT']])
    add('C_cash_oos',[coos(w,h,fields=['n'])+[v for m,b in [('EE','HA'),('PAST','HA'),('JOINT','HA'),('JOINT','PAST')] for v in coos(w,h,m,b)] for w,hs in [('cumulative',[1,3,6,12,24,36,48,60]),('post',[24,36,48,60])] for h in hs])
    rows=[]
    for window,hs in [('cumulative',[1,2,4,8,12,16,20]),('annual',[1,2,3,4,5])]:
        for h in hs:
            for v in ['baseline','controlled']:
                row=[]
                for t in ['COMPNFB','OPHNFB','ULCNFB']:
                    key=dict(target=t,variant=v,window='short' if window=='cumulative' and h<4 else window)
                    key['year' if window=='annual' else 'horizon']=h
                    row+=cells('channel_production.csv',[('beta','p'),'t','p','r2','n'],**key)
                rows.append(row)
    add('C_production',rows)
    add('C_var_details',[[cell('channel_var.csv','n',system=s)]+[v for c in ['total','ER','CF','DR'] for v in [cell('channel_var.csv','r2_'+c,scale=100,system=s),cell('channel_var.csv','p_'+c,system=s)]] for s in systems])
    add('C_sce',[cells('channel_sce.csv',[('beta','p'),'t','p','r2','n'],target=t,horizon=h) for t in ['JF','JL'] for h in [0,1,3,6,12]])
    add('C_pricing',[cells('channel_pricing.csv',[('beta','p'),'t','p','r2','n'],target=t) for t in ['FED_ERP','BEX_UNC','SKEW']])
    return out
