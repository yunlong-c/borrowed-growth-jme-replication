"""Estimate recursive forecasts and comparisons; no allocation or presentation."""
import numpy as np
import pandas as pd

from .config import (
    CORE, END, FIRST_ORIGIN, GW, HA_START, HORIZONS, LABOUR,
    PREDICTORS, RESULTS, START,
)
from .ols import _ols_forecast
from .calendar_inference import cw_metrics, encompassing

DISCOUNT = 0.75
MINIMUM_MATURE = 12
OUTPUTS = (
    'forecast_ledger.csv', 'compound_targets.csv', 'oos_summary.csv',
    'encompassing.csv', 'paired_oos.csv', 'encompassing_observations.csv',
    'combination_ledger.csv', 'combination_summary.csv',
)


def recursive_forecasts(panel):
    dates = panel.index
    rm = panel.MARKET_SIMPLE_RETURN.to_numpy(float)
    rf = panel.RFREE.to_numpy(float)
    log = panel.MARKET_EXCESS_LOG_RETURN.to_numpy(float)
    if not np.isfinite(np.column_stack([rm, rf, log])).all():
        raise ValueError('The registered return calendar must be complete.')
    first = dates.get_loc(pd.Period(FIRST_ORIGIN, 'M'))
    train0 = dates.get_loc(pd.Period(START, 'M'))
    bench0 = dates.get_loc(pd.Period(HA_START, 'M'))
    rows, targets = [], []
    for h in HORIZONS:
        q = np.array([
            np.prod(1 + rm[s:s+h]) - np.prod(1 + rf[s:s+h])
            for s in range(len(panel)-h+1)
        ])
        ylog = np.array([np.mean(log[t+1:t+h+1]) for t in range(len(panel)-h)])
        for s in range(bench0, len(q)):
            targets.append(dict(
                horizon=h, target_start=str(dates[s]), target_end=str(dates[s+h-1]),
                market_gross=np.prod(1+rm[s:s+h]),
                riskfree_gross=np.prod(1+rf[s:s+h]), target=q[s],
            ))
        for t in range(first, len(panel)-h):
            origins = np.arange(train0, t-h+1)
            simple_history = q[bench0:t-h+2]
            variance_history = simple_history[-120:]
            log_benchmark = log[bench0:t+1].mean()
            for model in [v for v in PREDICTORS if v != 'E2E']:
                values = panel[model].to_numpy(float)
                take = origins[np.isfinite(values[origins])]
                xt = values[take]
                mean, sd = xt.mean(), xt.std(ddof=1)
                current = values[t]
                for kind, yy, actual, benchmark, bn in (
                    ('log', ylog[take], ylog[t], log_benchmark, t-bench0+1),
                    ('simple', q[take+1], q[t+1], simple_history.mean(), len(simple_history)),
                ):
                    if np.isfinite(current):
                        forecast, a, b = _ols_forecast(yy, (xt-mean)/sd, (current-mean)/sd)
                        status = 'OK'
                    else:
                        forecast = a = b = np.nan
                        status = 'MISSING_CURRENT_SIGNAL'
                    rows.append(dict(
                        model=model, horizon=h, target_type=kind,
                        forecast_origin=str(dates[t]), target_start=str(dates[t+1]),
                        target_end=str(dates[t+h]), training_origin_start=str(dates[take[0]]),
                        training_origin_end=str(dates[take[-1]]),
                        max_training_target_end=str(dates[take[-1]+h]), n_train=len(take),
                        zscore_mean=mean, zscore_sd=sd, current_predictor=current,
                        forecast=forecast, intercept=a, slope=b, actual=actual,
                        benchmark=benchmark, benchmark_start=HA_START, benchmark_n=bn,
                        benchmark_max_target_end=str(dates[t]),
                        variance=variance_history.var(ddof=1), variance_n=len(variance_history),
                        variance_first_target_start=str(dates[t-h+2-len(variance_history)]),
                        variance_last_target_start=str(dates[t-h+1]),
                        variance_max_target_end=str(dates[t]), status=status,
                        return_unit='DECIMAL', forecast_method='EXPANDING_OLS_MATURE_TARGETS',
                        variance_method='LAST_120_MATURE_OVERLAPPING_SIMPLE_TARGETS',
                    ))
        print('Recursive forecasts completed horizon', h, flush=True)
    return pd.DataFrame(rows), pd.DataFrame(targets)


def error_metrics(actual, forecast, benchmark):
    em, eb = actual-forecast, actual-benchmark
    mse = float(np.mean(em**2))
    bmse = float(np.mean(eb**2))
    return dict(n=len(actual), r2_os=100*(1-mse/bmse),
                model_msfe=mse, benchmark_msfe=bmse,
                model_sse=float(em@em), benchmark_sse=float(eb@eb))


def comparisons(ledger):
    logs = ledger.loc[ledger.target_type.eq('log') & ledger.status.eq('OK')]
    summary, enc, paired, differences = [], [], [], []
    combination_rows, combination_summary = [], []
    for (model, h), g in logs.groupby(['model', 'horizon'], sort=False):
        months = pd.PeriodIndex(g.forecast_origin, freq='M').asi8
        summary.append(dict(
            model=model, horizon=h, start=g.forecast_origin.min(), end=g.forecast_origin.max(),
            target_start=g.target_start.min(), target_end=g.target_end.max(),
            **cw_metrics(g.actual.to_numpy(), g.forecast.to_numpy(), g.benchmark.to_numpy(), months, int(h)),
            cw_method='CENTERED_CALENDAR_BARTLETT_H_NO_CORRECTION_SIGNED_T_N_MINUS_2',
        ))
    primary = CORE[0]
    for partner in LABOUR + GW:
        for h in HORIZONS:
            a = logs.loc[logs.model.eq(primary) & logs.horizon.eq(h)].set_index('forecast_origin')
            b = logs.loc[logs.model.eq(partner) & logs.horizon.eq(h)].set_index('forecast_origin')
            ix = a.index.intersection(b.index).sort_values()
            a, b = a.loc[ix], b.loc[ix]
            if not (np.array_equal(a.actual, b.actual) and np.array_equal(a.benchmark, b.benchmark)):
                raise ValueError(f'Paired targets or HA differ: {partner}, h={h}')
            months = pd.PeriodIndex(ix, freq='M').asi8
            for name, g in ((primary, a), (partner, b)):
                paired.append(dict(
                    core=primary, partner=partner, model=name, horizon=h,
                    start=ix.min(), end=ix.max(),
                    **cw_metrics(g.actual.to_numpy(), g.forecast.to_numpy(), g.benchmark.to_numpy(), months, h),
                ))
            for base, added, bf, af in ((partner, primary, b, a), (primary, partner, a, b)):
                enc.append(dict(
                    core=primary, partner=partner, base=base, added=added, horizon=h,
                    start=ix.min(), end=ix.max(),
                    **encompassing(bf.actual.to_numpy(), bf.forecast.to_numpy(), af.forecast.to_numpy(), months, h),
                    method='CENTERED_CALENDAR_BARTLETT_H_HLN_FACTOR_SIGNED_T_N_MINUS_1',
                ))
                for date, eb, ea in zip(ix, bf.actual-bf.forecast, af.actual-af.forecast):
                    differences.append(dict(
                        core=primary, partner=partner, base=base, added=added,
                        horizon=h, origin=date, base_error=eb, added_error=ea,
                        differential=eb*(eb-ea),
                    ))
            y, fa, fb, ha = (a.actual.to_numpy(), a.forecast.to_numpy(),
                              b.forecast.to_numpy(), a.benchmark.to_numpy())
            ends = pd.PeriodIndex(a.target_end, freq='M').asi8
            ea, eb = y-fa, y-fb
            n = len(ix)
            ew = (fa+fb)/2
            dynamic = np.empty(n)
            for i, origin in enumerate(ix):
                mature = np.flatnonzero((ends <= months[i]) & (np.arange(n) < i))
                wa, sa, sb = 0.5, np.nan, np.nan
                rule = 'EQUAL_BEFORE_12_MATURE_PAIRS'
                if len(mature) >= MINIMUM_MATURE:
                    weights = DISCOUNT**np.arange(len(mature)-1, -1, -1)
                    sa = float(weights@(ea[mature]**2)/weights.sum())
                    sb = float(weights@(eb[mature]**2)/weights.sum())
                    wa = sb/(sa+sb)
                    rule = 'INVERSE_DISCOUNTED_MSFE'
                dynamic[i] = wa*fa[i]+(1-wa)*fb[i]
                for method, weight, prediction in (('EW', 0.5, ew[i]), ('DMSFE', wa, dynamic[i])):
                    combination_rows.append(dict(
                        core=primary, partner=partner, horizon=h, method=method,
                        forecast_origin=origin, target_start=a.target_start.iloc[i],
                        target_end=a.target_end.iloc[i], actual=y[i], benchmark=ha[i],
                        forecast_primary=fa[i], forecast_partner=fb[i], forecast=prediction,
                        weight_primary=weight, weight_partner=1-weight,
                        primary_error=y[i]-fa[i], partner_error=y[i]-fb[i],
                        error=y[i]-prediction, benchmark_error=y[i]-ha[i],
                        mature_pair_count=len(mature),
                        max_weight_error_target_end=(str(pd.Period(ordinal=int(ends[mature[-1]]), freq='M')) if len(mature) else ''),
                        score_primary=sa if method == 'DMSFE' else np.nan,
                        score_partner=sb if method == 'DMSFE' else np.nan,
                        discount_factor=DISCOUNT if method == 'DMSFE' else np.nan,
                        minimum_mature_errors=MINIMUM_MATURE if method == 'DMSFE' else 0,
                        weight_rule=rule if method == 'DMSFE' else 'FIXED_ONE_HALF',
                        discount_clock='MATURE_PAIRED_OBSERVATION_ORDER' if method == 'DMSFE' else '',
                    ))
            reference_a = error_metrics(y, fa, ha)
            reference_b = error_metrics(y, fb, ha)
            for method, forecast in (('EW', ew), ('DMSFE', dynamic)):
                combination_summary.append(dict(
                    core=primary, partner=partner, horizon=h, method=method,
                    start=ix.min(), end=ix.max(), **error_metrics(y, forecast, ha),
                    primary_r2_os=reference_a['r2_os'], partner_r2_os=reference_b['r2_os'],
                    primary_msfe=reference_a['model_msfe'], partner_msfe=reference_b['model_msfe'],
                    inference='DESCRIPTIVE_NO_CW_TEST',
                ))
    return {
        'oos_summary.csv': pd.DataFrame(summary),
        'encompassing.csv': pd.DataFrame(enc), 'paired_oos.csv': pd.DataFrame(paired),
        'encompassing_observations.csv': pd.DataFrame(differences),
        'combination_ledger.csv': pd.DataFrame(combination_rows),
        'combination_summary.csv': pd.DataFrame(combination_summary),
    }

