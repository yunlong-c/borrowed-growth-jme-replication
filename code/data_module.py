"""Prepare SA3MA data exhibits and estimate the approved 46 labor relations."""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import t as student

UNIT = Path(__file__).resolve().parents[1]
from data_support.calendar_inference import fit
from data_support.native import build
INPUT, RESULTS, BUILD = [UNIT / p for p in ['data/processed', 'results', 'config']]
TARGETS = [('LEHD_EEHireR', 'Q', 'A'), ('LFPR', 'M', 'B'), ('EPR', 'M', 'B'),
           ('CPS_UE', 'M', 'B'), ('WGT_SWITCHER', 'M', 'C'),
           ('WGT_STAYER', 'M', 'C'), ('WGT_SPREAD', 'M', 'C'), ('LS_NFB_INDEX', 'Q', 'C')]
MULTIPLIERS = {v: 100 for v in ['LMT_VU_LONG', 'NTIS', 'TBL', 'LTY', 'LTR', 'INFL', 'TMS', 'DFY', 'DFR']}
MULTIPLIERS['SVAR'] = 10000


def save(frame, name, directory=RESULTS):
    directory.mkdir(parents=True, exist_ok=True)
    frame.to_csv(directory / name, index=False, encoding='utf-8-sig', float_format='%.17g')


def prepare():
    native,native_q=build()
    columns=['PAYROLL','UNEMP','LFPR','JPR_PRIVATE_LONG','LMT_VU_LONG','HIRES_PRIVATE_LONG','QUITS_PRIVATE_LONG','LIG_JW','CLAIMS_INTENSITY','DP','DY','EP','DE','BM','NTIS','TBL','LTY','TMS','DFY','LTR','DFR','SVAR','INFL','MARKET_EXCESS_LOG_RETURN','EPR','LOG_VU_LONG','CPS_UE','WGT_SWITCHER','WGT_STAYER','WGT_SPREAD','USREC']
    monthly=native.reindex(pd.period_range('1995-10','2025-12',freq='M'))[columns].copy()
    monthly['MARKET_EXCESS_LOG_RETURN']*=100
    monthly['EE']=native.FMP_SA_3MA.reindex(monthly.index)
    quarterly=native_q.reindex(pd.period_range('1995Q4','2025Q4',freq='Q'))[['LEHD_EEHireR','LS_NFB_INDEX']].copy()
    quarterly['LEHD_EEHireR']*=100
    grouped=monthly.EE.groupby(monthly.index.asfreq('Q'))
    quarterly['EE']=grouped.mean().where(grouped.count().eq(3)).reindex(quarterly.index)
    quarterly['USREC']=monthly.USREC.groupby(monthly.index.asfreq('Q')).max().reindex(quarterly.index)
    return monthly,quarterly


def descriptive(monthly):
    frozen = pd.read_csv(UNIT / 'config/data_descriptive_registry.csv')
    rows = []
    for record in frozen.to_dict('records'):
        variable = record['variable']
        series = monthly.EE * 100 if variable == 'E2E' else monthly[variable]
        own = series.dropna()
        pair = pd.concat([monthly.EE.rename('EE'), series.rename('value')], axis=1).dropna()
        record.update(n=len(own), start=str(own.index[0]), end=str(own.index[-1]),
                      mean=own.mean(), median=own.median(), p01=own.quantile(.01),
                      p99=own.quantile(.99), sd=own.std(ddof=1),
                      ac1=series.corr(series.shift(1)), ac12=series.corr(series.shift(12)),
                      corr_e2e=pair.EE.corr(pair.value), corr_n=len(pair),
                      corr_start=str(pair.index[0]), corr_end=str(pair.index[-1]),
                      report_multiplier=MULTIPLIERS.get(variable, 1), status='OK')
        rows.append(record)
    return pd.DataFrame(rows)


def relations(monthly, quarterly):
    summaries, ledgers = [], []
    for target, frequency, panel in TARGETS:
        data = monthly if frequency == 'M' else quarterly
        horizons = [1, 3, 6, 12] if frequency == 'M' else [1, 2, 4]
        lag = 12 if frequency == 'M' else 4
        for specification, h in [('contemporaneous', 0), ('next', 1)] + [('conditional', h) for h in horizons]:
            conditional = specification == 'conditional'
            valid = pd.DataFrame({'ee_raw': data.EE, 'outcome_raw': data[target].shift(-h),
                                  'current_raw': data[target]}).dropna(
                                      subset=['ee_raw','outcome_raw']+(['current_raw'] if conditional else []))
            dates = valid.index
            scale = {}
            for field in ['ee', 'outcome', 'current']:
                if field == 'current' and not conditional:
                    scale.update(current_mean=np.nan,current_sd=np.nan)
                    valid['current_z'] = np.nan
                    continue
                raw = valid[field + '_raw']
                scale[field + '_mean'], scale[field + '_sd'] = raw.mean(), raw.std(ddof=1)
                valid[field + '_z'] = (raw - raw.mean()) / raw.std(ddof=1)
            x = np.column_stack([np.ones(len(valid)), valid.ee_z] + ([valid.current_z] if conditional else []))
            fitted = fit(valid.outcome_z.to_numpy(), x, dates.asi8, lag)
            n, k = x.shape
            record = dict(target=target, frequency=frequency, panel=panel, horizon=h,
                          horizon_months=h * (3 if frequency == 'Q' else 1), specification=specification,
                          beta=fitted['beta'][1], t_nw=fitted['t'][1],
                          p=2 * student.sf(abs(fitted['t'][1]), n-k), r2=100*fitted['r2'],
                          n=n, start=str(dates[0]), end=str(dates[-1]),
                          target_start=str(dates[0]+h), target_end=str(dates[-1]+h),
                          intercept=fitted['beta'][0], se_nw=fitted['se'][1],
                          gamma=fitted['beta'][2] if conditional else np.nan,
                          gamma_t_nw=fitted['t'][2] if conditional else np.nan,
                          gamma_p=2*student.sf(abs(fitted['t'][2]), n-k) if conditional else np.nan,
                          hac_lag=lag, k=k, df=n-k, correction=n/(n-k),
                          adj_r2=100*(1-(1-fitted['r2'])*(n-1)/(n-k)), status='OK', **scale)
            if conditional:
                y = valid.outcome_z.to_numpy()
                sx = np.column_stack([np.ones(n), valid.current_z])
                ex = x[:, :2]
                sse_current = np.sum((y-sx@np.linalg.lstsq(sx,y,rcond=None)[0])**2)
                sse_ee = np.sum((y-ex@np.linalg.lstsq(ex,y,rcond=None)[0])**2)
                total = np.sum((y-y.mean())**2)
                record.update(current_only_r2=100*(1-sse_current/total),
                              ee_only_r2=100*(1-sse_ee/total),
                              incremental_r2=100*(sse_current-np.sum(fitted['residual']**2))/total,
                              partial_r2=100*(sse_current-np.sum(fitted['residual']**2))/sse_current)
            summaries.append(record)
            ledger = valid.reset_index(names='origin')
            ledger['origin'] = ledger.origin.astype(str)
            ledger['ordinal'] = dates.asi8
            ledger['outcome_date'] = (dates+h).astype(str)
            ledger['target'], ledger['frequency'], ledger['horizon'] = target, frequency, h
            ledger['specification'] = specification
            ledger['fitted'] = valid.outcome_z.to_numpy()-fitted['residual']
            ledger['residual'] = fitted['residual']
            ledgers.append(ledger)
    return pd.DataFrame(summaries), pd.concat(ledgers, ignore_index=True)


def figure_panel(data, series, frequency):
    valid = data[series].notna().all(axis=1)
    display = data.loc[valid.index[valid][0]:valid.index[valid][-1], series+['USREC']].copy()
    display['available'] = display[series].notna().all(axis=1)
    for field in series:
        common = display.loc[display.available, field]
        display[field + '_z'] = ((display[field]-common.mean())/common.std(ddof=1)).where(display.available)
    display['EE_percent'] = 100*display.EE
    display['plot_date'] = display.index.to_timestamp(how='start')
    return display.reset_index(names='date').assign(date=lambda x: x.date.astype(str))


def main():
    monthly, quarterly = prepare()
    description = descriptive(monthly)
    estimates, ledger = relations(monthly, quarterly)
    if len(estimates) != 46 or estimates.specification.eq('conditional').sum() != 30:
        raise AssertionError('Approved relation registry must have 16 basic and 30 conditional models.')
    fig_a = monthly.loc[monthly.EE.notna(), ['EE', 'USREC']].copy()
    fig_a['EE_percent'] = 100*fig_a.EE
    fig_a = fig_a.reset_index(names='date').assign(date=lambda x: x.date.astype(str))
    fig_b = figure_panel(quarterly, ['EE', 'LEHD_EEHireR'], 'Q')
    fig_c = figure_panel(monthly, ['EE', 'WGT_SWITCHER', 'WGT_STAYER'], 'M')
    save(monthly.reset_index(names='date').assign(date=lambda x:x.date.astype(str)), 'data_monthly.csv', INPUT)
    save(quarterly.reset_index(names='date').assign(date=lambda x:x.date.astype(str)), 'data_quarterly.csv', INPUT)
    for frame, name in [(description,'data_descriptive.csv'), (estimates,'data_relations.csv'),
                        (ledger,'data_relation_ledger.csv'), (fig_a,'data_figure_monthly.csv'),
                        (fig_b,'data_figure_quarterly.csv'), (fig_c,'data_figure_wages.csv')]:
        save(frame,name)
    BUILD.mkdir(parents=True,exist_ok=True)
    (BUILD/'data_method.json').write_text(json.dumps(dict(measure='FMP_SA_3MA', vintage='2026-08',
        input_measure_unit='DECIMAL_PROBABILITY', figure_EE_percent_multiplier=100,
        complete_quarter_months=3, first_complete_quarter=str(quarterly.EE.first_valid_index()),
        descriptive_rows=len(description), relations=len(estimates),
        bivariate=16, conditional=30, standardization='within each regression; sample SD ddof=1',
        inference='calendar Bartlett NW12 monthly / NW4 quarterly; N/(N-K); two-sided Student-t(N-K)',
        contemporaneous_measure_lag=0),indent=2),encoding='utf-8')
    print(json.dumps(dict(descriptive_rows=len(description),relations=len(estimates),
                         ledger_rows=len(ledger),figure_months=len(fig_a),
                         figure_quarters=len(fig_b),wage_common_n=int(fig_c.available.sum())),indent=2))


if __name__ == '__main__':
    main()
