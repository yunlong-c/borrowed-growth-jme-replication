"""Recompute manuscript returns, comparisons and economic value from native data.

Source logic: E006 in-sample/OOS, E015 v2 SA3MA IS, and E016 allocation.
No reference results are read by this module.
"""
from pathlib import Path
import json
import time
import numpy as np
import pandas as pd
from return_support.config import GW, LABOUR, PREDICTORS, LAGS, START, END, B, SEED
from return_support.calendar_inference import fit, hac_many
from return_support.conditional_in_sample import monthly_wild_innovations, overlapping_innovations
from return_support import oos, robustness

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'
PROCESSED=ROOT/'data/processed'
H=[1,3,6,12]

def save(df,name,folder=RESULTS):
    folder.mkdir(parents=True,exist_ok=True)
    df.to_csv(folder/name,index=False,encoding='utf-8-sig',float_format='%.17g')

def read_native():
    p=pd.read_csv(PROCESSED/'native_measures.csv')
    p.index=pd.PeriodIndex(p.pop('date'),freq='M')
    return p

def prepare():
    native=read_native()
    dates=pd.period_range(START,END,freq='M')
    p=pd.DataFrame(index=dates)
    timing=[]
    for v in PREDICTORS+['MARKET_EXCESS_LOG_RETURN','MARKET_SIMPLE_RETURN','RFREE']:
        lag=LAGS.get(v,0)
        p[v]=native[v].reindex(dates-lag).to_numpy()
        timing.extend(dict(variable=v,origin=str(d),reference_month=str(d-lag),lag=lag,value=value) for d,value in p[v].items())
    save(p.rename_axis('date').reset_index(),'return_comparison_panel.csv',PROCESSED)
    save(pd.DataFrame(timing),'return_timing_ledger.csv',PROCESSED)
    # Keep the original CSV round-trip, which is part of the frozen computation.
    p=pd.read_csv(PROCESSED/'return_comparison_panel.csv')
    p.index=pd.PeriodIndex(p.pop('date'),freq='M')
    scale=pd.DataFrame(dict(variable=PREDICTORS,mean=p[PREDICTORS].mean().to_numpy(),sd=p[PREDICTORS].std(ddof=1).to_numpy(),n=p[PREDICTORS].count().to_numpy()))
    save(scale,'return_standardization.csv',PROCESSED)
    risk=native.loc['1994-02':END,['MARKET_SIMPLE_RETURN','RFREE']].copy()
    save(risk.rename_axis('date').reset_index(),'return_risk_returns.csv',PROCESSED)
    targets=[]
    for h in H:
        for k in range(len(risk)-h+1):
            block=risk.iloc[k:k+h]
            mg=float(np.prod(1+block.MARKET_SIMPLE_RETURN.to_numpy()))
            fg=float(np.prod(1+block.RFREE.to_numpy()))
            targets.append(dict(horizon=h,target_start=str(block.index[0]),target_end=str(block.index[-1]),market_gross=mg,riskfree_gross=fg,target=mg-fg))
    targets=pd.DataFrame(targets)
    save(targets,'return_compound_targets.csv',PROCESSED)
    return native,p,targets

def in_sample(native,p):
    scale=pd.read_csv(PROCESSED/'return_standardization.csv').set_index('variable')
    z=(p[PREDICTORS]-scale['mean'])/scale['sd']
    r=p.MARKET_EXCESS_LOG_RETURN.to_numpy(float)
    gw12=[v for v in GW if v not in ['DE','TMS']]
    # Comparison stars retain the E006 lagged E2E residual-generating regression.
    # The current EE stars use the E015 v2 contemporaneous FMP_SA regression.
    sinks={'comparison':z[['E2E']+gw12]}
    eevalues=p[gw12].copy()
    eevalues.insert(0,'FMP_SA',native.E2E.reindex(p.index))
    sinks['E2E']=(eevalues-eevalues.mean())/eevalues.std(ddof=1)
    ee=native.FMP_SA_3MA.reindex(p.index)
    zee=(ee-ee.mean())/ee.std(ddof=1)
    cells=[];observations=[];inference=[]
    for group,values in sinks.items():
        d=np.column_stack([np.ones(len(p)-1),values.to_numpy()[:-1]])
        b=np.linalg.lstsq(d,r[1:],rcond=None)[0]
        resid=r[1:]-d@b
        save(pd.DataFrame(dict(origin=p.index[:-1].astype(str),return_month=p.index[1:].astype(str),actual=r[1:],fitted=d@b,residual=resid)),f'return_bootstrap_sink_{group}.csv')
        save(pd.DataFrame(dict(variable=['constant']+list(values.columns),coefficient=b)),f'return_bootstrap_coefficients_{group}.csv')
        innovations=monthly_wild_innovations(resid,B,SEED)
        if group=='E2E':
            np.savez_compressed(RESULTS/'reconstructed_monthly_innovations.npz',innovations=innovations)
        models=[v for v in PREDICTORS if v!='E2E'] if group=='comparison' else []
        for h in H:
            ys=100*np.array([r[t+1:t+h+1].mean() for t in range(len(p)-h)])
            shocks=overlapping_innovations(innovations,h,scale=100)
            for model in models:
                xraw=(zee if model=='E2E' else z[model]).to_numpy()[:len(ys)]
                valid=np.isfinite(xraw)
                dates=p.index[:len(ys)][valid];y=ys[valid]
                x=np.column_stack([np.ones(len(y)),xraw[valid]])
                f=fit(y,x,dates.asi8,h)
                draw=np.empty(B);draw_r2=np.empty(B)
                for j in range(0,B,500):
                    sim=y.mean()+shocks[j:j+500,valid]
                    beta,_,t=hac_many(sim,x,dates.asi8,h)
                    draw[j:j+500]=t[:,1]
                    err=sim-beta@x.T
                    draw_r2[j:j+500]=1-np.sum(err**2,axis=1)/np.sum((sim-sim.mean(axis=1,keepdims=True))**2,axis=1)
                count=int(np.count_nonzero(abs(draw)>=abs(f['t'][1])))
                prob=(count+1)/(B+1)
                v=ee if model=='E2E' else p[model]
                rho=float(v.corr(v.shift(1)))
                cells.append(dict(model=model,horizon=h,n=len(y),origin_start=str(dates[0]),origin_end=str(dates[-1]),target_start=str(dates[0]+1),target_end=str(dates[-1]+h),beta=f['beta'][1],intercept=f['beta'][0],se=f['se'][1],se_nw=f['se'][1],t_nw=f['t'][1],p_is=prob,p_r2=(1+int(np.count_nonzero(draw_r2>=f['r2'])))/(B+1),r2=100*f['r2'],rho=rho,standardization_mean=v.mean(),standardization_sd=v.std(ddof=1),status='OK',measure_identity='FMP_SA_3MA' if model=='E2E' else model))
                inference.append(dict(model=model,horizon=h,extreme_count=count,p_is=prob,replications=B,seed=SEED,sink=group))
                observations.append(pd.DataFrame(dict(model=model,horizon=h,origin=dates.astype(str),target_start=(dates+1).astype(str),target_end=(dates+h).astype(str),target=y,predictor_z=x[:,1],fitted=y-f['residual'],residual=f['residual'])))
            print(f'Return IS {group} h={h} complete',flush=True)
    table=pd.DataFrame(cells)
    ee_rows=table.model.eq('E2E')
    table.loc[~ee_rows,'se_nw']=np.nan
    save(table,'return_is.csv')
    save(pd.DataFrame(inference),'return_bootstrap_inference.csv')
    save(pd.concat(observations,ignore_index=True),'return_regression_observations.csv')

def main():
    started=time.perf_counter()
    native,p,targets=prepare()
    in_sample(native,p)
    comparison,oldtargets=oos.recursive_forecasts(p)
    # Original comparison allocations retain their E006 1995-12 risk history.
    simple=comparison[comparison.target_type.eq('simple')].copy()
    missing=simple.forecast.isna()
    simple['used_historical_mean']=missing
    simple.loc[missing,'forecast']=simple.loc[missing,'benchmark']
    ha=simple[simple.model.eq('DP')].copy()
    ha['model']='HA';ha['forecast']=ha.benchmark;ha['used_historical_mean']=False
    old_alloc=pd.concat([simple[~simple.model.eq('E2E')],ha],ignore_index=True)
    old=comparison[~comparison.model.eq('E2E')].copy()
    p['E2E']=native.FMP_SA_3MA.reindex(p.index-1).to_numpy()
    save(p.rename_axis('date').reset_index(),'return_panel.csv',PROCESSED)
    ee=robustness.recursive(p,targets,kind='log')
    ee[['variance','variance_n','variance_first_target_start','variance_last_target_start','variance_max_target_end']]=np.nan
    compound=robustness.recursive(p,targets,kind='simple')
    ledger=pd.concat([old,ee,compound],ignore_index=True)
    ledger['measure_identity']=np.where(ledger.model.eq('E2E'),'FMP_SA_3MA',ledger.model)
    save(ledger,'return_forecasts.csv')
    outputs=oos.comparisons(ledger)
    mapping={'oos_summary.csv':'return_oos.csv','encompassing.csv':'return_encompassing.csv','paired_oos.csv':'return_paired_oos.csv','encompassing_observations.csv':'return_encompassing_observations.csv','combination_ledger.csv':'return_combination_ledger.csv'}
    for oldname,newname in mapping.items():save(outputs[oldname],newname)
    save(robustness.summarize(outputs['combination_ledger.csv'].assign(status='OK'),['partner','horizon','method']),'return_combinations.csv')
    forecasts=robustness.forecast_robustness(p,targets,ee,compound)
    robustness.allocation(forecasts,targets,old_alloc)
    (ROOT/'logs').mkdir(exist_ok=True)
    (ROOT/'logs/returns_runtime.json').write_text(json.dumps(dict(seconds=time.perf_counter()-started,bootstrap_replications=B,seed=SEED),indent=2),encoding='utf-8')
    print('Returns and allocation complete',flush=True)

if __name__=='__main__':main()
