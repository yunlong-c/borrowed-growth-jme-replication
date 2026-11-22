"""Portable E016 return robustness and allocation, recomputed from source forecasts."""
import numpy as np
import pandas as pd
from .ols import _ols_forecast
from .calendar_inference import cw_metrics
from .allocation import gross_horizon_allocation_ledger,summarize_gross_horizon_allocation
from .config import RESULTS
H=[1,3,6,12]
SCENARIOS=['baseline','oos2005','oos2015','train2000','train2005','rolling120','simple','nonnegative']
def save(frame,name):
    RESULTS.mkdir(parents=True,exist_ok=True)
    frame.to_csv(RESULTS/name,index=False,encoding='utf-8-sig',float_format='%.17g')

def recursive(panel, targets, scenario='baseline', kind='log', first=None):
    dates = panel.index
    signal = panel.E2E.to_numpy(float)
    rlog = panel.MARKET_EXCESS_LOG_RETURN.to_numpy(float)
    rsimple = (panel.MARKET_SIMPLE_RETURN-panel.RFREE).to_numpy(float)
    start = f'{scenario[-4:]}-01' if scenario.startswith('train') else '1995-11'
    ha_start = f'{scenario[-4:]}-02' if scenario.startswith('train') else '1995-12'
    train0 = dates.get_loc(pd.Period(start, 'M'))
    bench0 = dates.get_loc(pd.Period(ha_start, 'M'))
    first = first or ('2004-12' if scenario == 'oos2005' else '2009-12')
    rows = []
    for h in H:
        target = targets[targets.horizon.eq(h)].set_index('target_start', drop=False)
        r = rsimple if kind == 'simple_average' else rlog
        y = np.array([r[t+1:t+h+1].mean() for t in range(len(panel)-h)])
        for t in range(dates.get_loc(pd.Period(first, 'M')), len(panel)-h):
            lo = t-h-119 if scenario == 'rolling120' else train0
            take = np.arange(lo, t-h+1)
            take = take[np.isfinite(signal[take])]
            x = signal[take]
            mean, sd = x.mean(), x.std(ddof=1)
            ys = target.loc[(dates[take]+1).astype(str), 'target'].to_numpy(float) if kind == 'simple' else y[take]
            f, a, b = _ols_forecast(ys, (x-mean)/sd, (signal[t]-mean)/sd)
            mature = target[target.target_end.le(str(dates[t]))]
            risk = mature.tail(120)
            if kind == 'simple':
                history = mature[mature.target_start.ge(ha_start)]
                if scenario == 'rolling120':
                    history = history.tail(120)
                benchmark = history.target.mean()
                bn, bs = len(history), history.target_start.iloc[0]
                actual = target.loc[str(dates[t]+1), 'target']
            else:
                b0 = t-119 if scenario == 'rolling120' else bench0
                benchmark = r[b0:t+1].mean()
                bn, bs, actual = t-b0+1, str(dates[b0]), y[t]
            rows.append(dict(model='E2E', horizon=h, scenario=scenario, target_type=kind,
                forecast_origin=str(dates[t]), reference_month=str(dates[t]-1),
                target_start=str(dates[t]+1), target_end=str(dates[t]+h),
                training_origin_start=str(dates[take[0]]), training_origin_end=str(dates[take[-1]]),
                max_training_target_end=str(dates[take[-1]]+h), n_train=len(take),
                zscore_mean=mean, zscore_sd=sd, current_predictor=signal[t],
                forecast=f, intercept=a, slope=b, actual=actual, benchmark=benchmark,
                benchmark_n=bn, benchmark_start=bs, benchmark_max_target_end=str(dates[t]),
                variance=risk.target.var(ddof=1), variance_n=len(risk),
                variance_first_target_start=risk.target_start.iloc[0],
                variance_last_target_start=risk.target_start.iloc[-1], variance_max_target_end=risk.target_end.max(),
                status='OK', return_unit='DECIMAL', provenance='E016_RECURSIVE_MATURE_OLS',
                target_definition={'simple':'compounded_simple_excess', 'log':'average_monthly_log_excess', 'simple_average':'average_monthly_simple_excess'}[kind]))
    return pd.DataFrame(rows)


def summarize(ledger, keys):
    rows=[]
    for key, group in ledger[ledger.status.eq('OK')].groupby(keys, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        h = int(group.horizon.iloc[0])
        rows.append(dict(zip(keys, key)) | dict(target_start=group.target_start.min(), target_end=group.target_end.max(),
            **cw_metrics(group.actual.to_numpy(), group.forecast.to_numpy(), group.benchmark.to_numpy(), pd.PeriodIndex(group.forecast_origin,freq='M').asi8,h),status='OK'))
    return pd.DataFrame(rows)


def forecast_robustness(p, targets, frozen_log, baseline_simple):
    logs, simple = [], []
    for scenario in SCENARIOS:
        if scenario in ['baseline','oos2015','nonnegative']:
            lg, si = frozen_log.copy(), baseline_simple.copy()
            if scenario == 'oos2015':
                lg, si = lg[lg.target_start.ge('2015-01')].copy(), si[si.target_start.ge('2015-01')].copy()
            if scenario == 'nonnegative':
                for frame in [lg, si]:
                    frame['unrestricted_forecast'] = frame.forecast
                    frame['forecast'] = frame.forecast.clip(lower=0)
        elif scenario == 'simple':
            lg = recursive(p, targets, kind='simple_average')
            si = baseline_simple.copy()
        elif scenario == 'oos2005':
            early = recursive(p, targets, scenario, kind='log')
            lg = pd.concat([early[early.forecast_origin.lt('2009-12')], frozen_log], ignore_index=True)
            si = recursive(p, targets, scenario, kind='simple')
        else:
            lg = recursive(p, targets, scenario, kind='log')
            si = recursive(p, targets, scenario, kind='simple')
        lg['scenario'], si['scenario'] = scenario, scenario
        logs.append(lg)
        ha = si.copy()
        ha['model'], ha['forecast'] = 'HA', ha.benchmark
        simple.extend([si, ha])
    logs = pd.concat(logs, ignore_index=True)
    logs['model_error'] = logs.actual-logs.forecast
    logs['benchmark_error'] = logs.actual-logs.benchmark
    save(logs, 'return_robustness_forecasts.csv')
    save(summarize(logs,['scenario','horizon']), 'return_robustness.csv')
    return pd.concat(simple, ignore_index=True)


def allocation(forecasts, targets, comparison_allocation):
    old = comparison_allocation.copy()
    ee = forecasts[forecasts.scenario.eq('baseline') & forecasts.model.eq('E2E')].copy()
    base = pd.concat([old,ee], ignore_index=True)
    holdings = gross_horizon_allocation_ledger(base,targets,models=list(old.model.unique())+['E2E'],path_start='2010-01',fixed_weights={'BUY_HOLD':1.},risk_aversion=3.,weight_bounds=(-.5,1.5))
    ref=[]
    for h,g in holdings[holdings.model.eq('HA')].groupby('horizon'):
        r=g.gross_return.to_numpy(); ex=r-g.riskfree_gross.to_numpy()+1
        ref.append(dict(horizon=h,cer=12/h*(r.mean()-1.5*r.var(ddof=1)),sharpe=np.sqrt(12/h)*ex.mean()/ex.std(ddof=1)))
    summary = summarize_gross_horizon_allocation(holdings,pd.DataFrame(ref))
    summary['status']='OK'
    save(base, 'return_allocation_forecasts.csv')
    save(holdings, 'portfolio_ledger.csv')
    save(summary, 'portfolio_summary.csv')
    specs=[('baseline',3,120,0),('gamma5',5,120,0),('risk60',3,60,0),('cost50',3,120,50),('cost100',3,120,100)]
    ledger=[]
    for scenario,gamma,window,bps in specs + [(s,3,120,0) for s in SCENARIOS if s!='baseline']:
        source = 'baseline' if scenario in ['gamma5','risk60','cost50','cost100'] else scenario
        selected=forecasts[forecasts.scenario.eq(source)].copy()
        phase=pd.Period({'oos2005':'2005-01','oos2015':'2015-01'}.get(source,'2010-01'),'M').ordinal
        for (model,h),group in selected.groupby(['model','horizon']):
            before,wealth=0.,1.
            for row in group.sort_values('target_start').itertuples(index=False):
                if (pd.Period(row.target_start,'M').ordinal-phase)%h: continue
                mature=targets[targets.horizon.eq(h)&targets.target_end.le(row.forecast_origin)].tail(window)
                variance=mature.target.var(ddof=1)
                w=float(np.clip(row.forecast/(gamma*variance),-.5,1.5))
                k=bps/10000; direction=np.sign(w-before)
                fee=k*abs(w-before)/(1+k*w*direction)
                trade=w*(1-fee)-before
                target=targets[targets.horizon.eq(h)&targets.target_start.eq(row.target_start)].iloc[0]
                growth=w*target.market_gross+(1-w)*target.riskfree_gross
                net=(1-fee)*growth
                after=w*target.market_gross/growth
                ledger.append(dict(scenario=scenario,model=model,horizon=h,gamma=gamma,variance_window=window,cost_bps=bps,
                    forecast_origin=row.forecast_origin,target_start=row.target_start,target_end=row.target_end,
                    forecast_simple_excess=row.forecast,variance=variance,variance_n=len(mature),
                    variance_first_target_start=mature.target_start.iloc[0],variance_max_target_end=mature.target_end.max(),
                    weight=w,pretrade_weight=before,postreturn_weight=after,signed_trade=trade,turnover=abs(trade),fee_fraction=fee,
                    market_gross=target.market_gross,riskfree_gross=target.riskfree_gross,gross_return=growth-1,net_return=net-1,
                    wealth_before=wealth,wealth_after=wealth*net,status='OK'))
                before,wealth=after,wealth*net
    ledger=pd.DataFrame(ledger)
    rows=[]
    for (scenario,model,h),g in ledger.groupby(['scenario','model','horizon'],sort=False):
        r=g.net_return.to_numpy(); ex=r-g.riskfree_gross.to_numpy()+1; gamma=g.gamma.iloc[0]
        rows.append(dict(scenario=scenario,model=model,horizon=h,gamma=gamma,variance_window=g.variance_window.iloc[0],cost_bps=g.cost_bps.iloc[0],
            cer=12/h*(r.mean()-gamma/2*r.var(ddof=1)),sharpe=np.sqrt(12/h)*ex.mean()/ex.std(ddof=1),n=len(g),
            annualized_turnover=12/h*g.turnover.mean(),target_start=g.target_start.min(),target_end=g.target_end.max(),status='OK'))
    summary=pd.DataFrame(rows)
    ha=summary[summary.model.eq('HA')][['scenario','horizon','cer','sharpe']].rename(columns={'cer':'ha_cer','sharpe':'ha_sharpe'})
    summary=summary.merge(ha,on=['scenario','horizon'],validate='many_to_one')
    summary['cer_gain_pp']=100*(summary.cer-summary.ha_cer)
    save(forecasts,'return_economic_robustness_forecasts.csv')
    save(ledger,'portfolio_robustness_ledger.csv')
    save(summary,'portfolio_robustness.csv')

