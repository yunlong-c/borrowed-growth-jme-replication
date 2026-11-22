"""Recompute manuscript cash-flow and economic channels from local source inputs."""
from pathlib import Path
import importlib.util
import json
import sys
import numpy as np
import pandas as pd
from scipy.stats import norm, t as student

E = Path(__file__).resolve().parents[1]
I, O, B = E/'data/processed', E/'results', E/'logs'
RAW=E/'data/raw/channels'
from channel_support.calendar_inference import cw_metrics
from channel_support import regression as legacy
from channel_support.prepare import prepare_sources
from channel_support.return_decomposition import decompose_returns
END = pd.Period('2025-12', freq='M')
SPECS, LEDGERS, COVARIANCE, PARAMS, FAILURES, SOURCES = [], [], [], [], [], []

def write(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format='%.17g', encoding='utf-8-sig')

def read(path):
    SOURCES.append(dict(source=str(path.relative_to(E)), access='read_only'))
    return pd.read_csv(path)

def dated(df, column='date', freq='M'):
    out = df.copy()
    out.index = pd.PeriodIndex(out[column], freq=freq)
    return out

def scale(s):
    return float(s.mean()), float(s.std(ddof=1))

def at(s, ix, offset=0):
    return s.reindex(ix+offset).to_numpy(float)

def execute(g, model_id, terms, lag, normal=False, correction=True, contrasts=None, **meta):
    g = g.replace([np.inf, -np.inf], np.nan).dropna(subset=['y', *terms]).sort_index().copy()
    g['date'], g['ordinal'] = g.index.astype(str), g.index.asi8
    spec = dict(id=model_id, terms=terms, lag=lag, normal=normal, correction=correction,
                contrasts=contrasts or {}, **meta)
    SPECS.append(spec)
    try:
        rr, ll, cv = legacy.regression(g, spec)
        for r in rr:
            r.update(meta, normal=normal, correction=correction, ee_lag=0)
        PARAMS.extend(rr)
        LEDGERS.append(ll.assign(**{k:v for k,v in meta.items() if np.isscalar(v)}))
        COVARIANCE.extend(cv)
        return next((r for r in rr if r['term']=='EE'), rr[1])
    except (ValueError, np.linalg.LinAlgError) as exc:
        row = dict(model=model_id, term='EE', status='FAILED', reason=str(exc), n=len(g), **meta)
        PARAMS.append(row); FAILURES.append(row)
        return row

def growth_panel(ee, y, h, offset, step, mu, sd, common=None):
    endpoint = END if step==12 else pd.Period('2025Q4',freq='Q')
    ix = ee.index[ee.index+h<=endpoint] if common is None else common
    g = pd.DataFrame(dict(const=1., ee_raw=at(ee,ix), EE=(at(ee,ix)-mu)/sd,
                         level_start=at(y,ix,offset), level_end=at(y,ix,h),
                         level_current=at(y,ix), level_past=at(y,ix,-step)),index=ix)
    g['y'] = 100*np.log(g.level_end.where(g.level_end>0)/g.level_start.where(g.level_start>0))
    g['past_growth'] = 100*np.log(g.level_current.where(g.level_current>0)/g.level_past.where(g.level_past>0))
    g['target_start'] = (ix+offset).astype(str)
    g['first_growth_month'] = (ix+offset+1).astype(str)
    g['target_end'] = (ix+h).astype(str)
    return g.dropna(subset=['ee_raw','y','past_growth'])


def production(ee):
    groups=ee.groupby(ee.index.asfreq('Q'));eq=groups.mean().where(groups.count()==3).dropna();mu,sd=scale(eq)
    levels=read(I/'channel_source_levels.csv');rows=[]
    for target in ['COMPNFB','OPHNFB','ULCNFB']:
        a=levels.query('target==@target');y=pd.Series(a.level.to_numpy(float),index=pd.PeriodIndex(a.date,freq='Q'))
        for window,hs in [('short',[1,2,4]),('cumulative',[4,8,12,16,20])]:
            for h in hs:
                g=growth_panel(eq,y,h,0,4,mu,sd)
                for name,terms in [('baseline',['const','EE']),('controlled',['const','EE','past_growth'])]:
                    row=execute(g,f'PROD_{target}_{window}_h{h}_{name}',terms,4 if window=='short' else h,target=target,window=window,horizon=h,year=h//4 if window=='cumulative' else 0,variant=name,frequency='Q',ee_mean=mu,ee_sd=sd)
                    rows.append(dict(row,r2=100*row.get('r2',np.nan)))
        ix=eq.index[eq.index+20<=pd.Period('2025Q4')];ok=np.isfinite(at(eq,ix))&(at(y,ix,-4)>0)
        for j in range(6):ok&=np.isfinite(at(y,ix,4*j))&(at(y,ix,4*j)>0)
        ix=ix[ok]
        for year in range(1,6):
            h=4*year;g=growth_panel(eq,y,h,h-4,4,mu,sd,common=ix)
            for name,terms in [('baseline',['const','EE']),('controlled',['const','EE','past_growth'])]:
                row=execute(g,f'PROD_{target}_annual_y{year}_{name}',terms,20,target=target,window='annual',horizon=h,year=year,variant=name,frequency='Q',ee_mean=mu,ee_sd=sd)
                rows.append(dict(row,r2=100*row.get('r2',np.nan)))
    write(pd.DataFrame(rows),O/'channel_production.csv')
    write(pd.DataFrame({'date':eq.index.astype(str),'EE_raw':eq.to_numpy(),'EE':(eq.to_numpy()-mu)/sd}),I/'channel_quarterly_ee.csv')

def other_channels(ee):
    sce=dated(read(I/'channel_sce_levels.csv'));sce['ee_raw']=ee.reindex(sce.index);sm,ss=scale(sce.ee_raw)
    rows=[]
    for target in ['JF','JL']:
        for h in [0,1,3,6,12]:
            ix=sce.index[sce.index+h<=END]
            g=pd.DataFrame({'const':1.,'ee_raw':at(sce.ee_raw,ix),'EE':(at(sce.ee_raw,ix)-sm)/ss,'y':at(sce[target],ix,h),'Z_now':at(sce[target],ix),'target_end':(ix+h).astype(str)},index=ix)
            row=execute(g,f'SCE_{target}_h{h}',['const','EE'] if h==0 else ['const','EE','Z_now'],12,target=target,horizon=h,variant='concurrent' if h==0 else 'controlled',ee_mean=sm,ee_sd=ss)
            rows.append(dict(row,r2=100*row.get('r2',np.nan)))
    write(pd.DataFrame(rows),O/'channel_sce.csv')
    pricing=dated(read(I/'channel_pricing_levels.csv'),'month');pricing['ee_raw']=ee.reindex(pricing.index);pm,ps=scale(pricing.ee_raw);rows=[]
    for target,col in [('FED_ERP','fed_equity_premium_pp'),('BEX_UNC','bex_uncertainty_variance'),('SKEW','skew')]:
        ym,ys=scale(pricing[col]);g=pd.DataFrame({'const':1.,'ee_raw':pricing.ee_raw,'EE':(pricing.ee_raw-pm)/ps,'y':(pricing[col]-ym)/ys,'y_raw':pricing[col]},index=pricing.index)
        row=execute(g,f'PRICING_{target}',['const','EE'],12,target=target,horizon=0,variant='concurrent',ee_mean=pm,ee_sd=ps,y_mean=ym,y_sd=ys)
        rows.append(dict(row,r2=100*row.get('r2',np.nan)))
    write(pd.DataFrame(rows),O/'channel_pricing.csv')

def var(ee):
    config=json.loads((E/'config/channels_var.json').read_text())
    panel=read(I/'return_comparison_panel.csv')
    # Legacy EE is needed only for the engine's auxiliary projection ledger.
    # Return states, PCA and VAR estimates do not use this measure as a VAR state.
    decomposition=decompose_returns(panel,config)
    order={s['id']:i for i,s in enumerate(config['systems'])}
    for name,frame in decomposition.items():
        if 'system' in frame:frame['system_order']=frame.system.map(order)
        write(frame,O/name)
    components=decomposition['return_components.csv'];meta={s['id']:s for s in config['systems']}
    rows=[];identities=[];dated_components=[]
    for system,q in components.groupby('system',sort=False):
        q=dated(q,'origin');q['EE_raw']=ee.reindex(q.index);q=q.dropna(subset=['EE_raw']);mu,sd=scale(q.EE_raw);q['EE']=(q.EE_raw-mu)/sd
        wide=dict(system=system,system_order=q.system_order.iloc[0],label=meta[system]['label'],group=meta[system]['group'],n=len(q),start=str(q.index[0]),end=str(q.index[-1]),ee_mean=mu,ee_sd=sd,ee_lag=0)
        for key,col in [('total','realized_return'),('ER','expected_return'),('CF','cash_flow_news'),('DR','discount_rate_news')]:
            g=pd.DataFrame({'const':1.,'EE':q.EE,'ee_raw':q.EE_raw,'y':100*q[col]},index=q.index)
            r=execute(g,f'VAR_{system}_{key}',['const','EE'],1,normal=True,correction=False,system=system,component=key,ee_mean=mu,ee_sd=sd)
            for field in ['beta','se','t','p','r2']:wide[field+'_'+key]=r[field]
        wide['slope_identity_error']=wide['beta_total']-wide['beta_ER']-wide['beta_CF']+wide['beta_DR'];rows.append(wide)
        identities.append(dict(system=system,slope_identity_error=wide['slope_identity_error'],component_identity_max=float(abs(q.realized_return-q.expected_return-q.cash_flow_news+q.discount_rate_news).max()),n=len(q)))
        dated_components.append(q.rename_axis('economic_month').reset_index())
    write(pd.DataFrame(rows),O/'channel_var.csv');write(pd.DataFrame(identities),O/'channel_var_identity.csv');write(pd.concat(dated_components),O/'channel_var_components.csv')

def main():
    SPECS.clear();LEDGERS.clear();COVARIANCE.clear();PARAMS.clear();FAILURES.clear();SOURCES.clear()
    for d in [I,O,B]:d.mkdir(parents=True,exist_ok=True)
    published=prepare_sources()
    ee=pd.Series(published.FMP_SA_3MA.to_numpy(float),index=pd.PeriodIndex(published.economic_month,freq='M')).loc[:END].dropna()
    write(pd.DataFrame({'economic_month':ee.index.astype(str),'EE_raw':ee.to_numpy()}),I/'channel_ee.csv')
    production(ee);other_channels(ee);var(ee)
    write(pd.DataFrame(PARAMS),O/'channel_coefficients.csv');write(pd.DataFrame(COVARIANCE),O/'channel_covariance.csv')
    pd.concat(LEDGERS,ignore_index=True).to_parquet(O/'channel_regression_ledger.parquet',index=False)
    (I/'channel_specifications.json').write_text(json.dumps(SPECS,indent=2),encoding='utf-8')
    write(pd.DataFrame(SOURCES).drop_duplicates(),I/'channel_sources.csv')
    report=dict(status='ESTIMATED',models=len(SPECS),coefficients=len(PARAMS),failed_models=FAILURES,ee_start=str(ee.index[0]),ee_end=str(ee.index[-1]),var_systems=23,var_components='all 23 VAR systems and PCA re-estimated from source state fields',non_ee_sources='source levels for retained JME economic channels',timing='economic-month EE in preserved non-cash-flow channels')
    (B/'channel_run_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
