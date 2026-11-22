import numpy as np
import pandas as pd

def gross_horizon_allocation_ledger(forecasts, targets, *, models, path_start,
                                    fixed_weights=None, risk_aversion=3.,
                                    weight_bounds=(-.5,1.5)):
    """Gross-only allocations; fixed_weights supplies strategies such as buy-and-hold."""
    q=targets.set_index(["horizon","target_start"])
    base=pd.Period(path_start,"M")
    rows=[]
    for h in sorted(forecasts.horizon.unique()):
        selected=forecasts.loc[forecasts.horizon.eq(h)]
        reference=selected.loc[selected.model.eq(models[0])]
        strategies=[(m,selected.loc[selected.model.eq(m)],None) for m in models]
        strategies += [(m,reference,w) for m,w in (fixed_weights or {}).items()]
        for model,frame,fixed in strategies:
            for r in frame.sort_values("forecast_origin").itertuples(index=False):
                s=pd.Period(r.target_start,"M")
                if s<base or (s.ordinal-base.ordinal)%h:continue
                item=q.loc[(h,r.target_start)]
                signal=float(r.forecast) if fixed is None else np.nan
                w=float(np.clip(signal/(risk_aversion*r.variance),*weight_bounds)) if fixed is None else float(fixed)
                gross=w*item.market_gross+(1-w)*item.riskfree_gross-1
                rows.append(dict(model=model,horizon=int(h),forecast_origin=r.forecast_origin,
                    target_start=r.target_start,target_end=r.target_end,
                    forecast_simple_excess=signal,variance=r.variance,variance_n=r.variance_n,
                    variance_first_target_start=r.variance_first_target_start,
                    variance_last_target_start=r.variance_last_target_start,
                    variance_max_target_end=r.variance_max_target_end,
                    weight=w,risk_aversion=risk_aversion,weight_lower=weight_bounds[0],
                    weight_upper=weight_bounds[1],market_gross=item.market_gross,
                    riskfree_gross=item.riskfree_gross,gross_return=gross))
    return pd.DataFrame(rows)


def summarize_gross_horizon_allocation(ledger, ha_summary):
    """Annual CER and excess-return Sharpe, relative to a supplied common HA."""
    reference=ha_summary.set_index("horizon")
    rows=[]
    for (model,h),g in ledger.groupby(["model","horizon"],sort=False):
        r=g.gross_return.to_numpy()
        excess=r-(g.riskfree_gross.to_numpy()-1)
        gamma=float(g.risk_aversion.iloc[0])
        cer=12/h*(r.mean()-.5*gamma*r.var(ddof=1))
        sharpe=np.sqrt(12/h)*excess.mean()/excess.std(ddof=1)
        ha=reference.loc[h]
        rows.append(dict(model=model,horizon=int(h),start=g.target_start.min(),
            end=g.target_end.max(),n=len(g),cer=float(cer),sharpe=float(sharpe),
            ha_cer=float(ha.cer),ha_sharpe=float(ha.sharpe),
            utility_gain_pp=float(100*(cer-ha.cer))))
    return pd.DataFrame(rows)
