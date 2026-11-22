"""Read only the two authorised workbooks and required frozen numerical slices."""
from config import *

def main():
    gw=pd.read_excel(WB,sheet_name='Monthly',usecols=['yyyymm','CRSP_SPvw','Rfree','D12','E12'])
    gw.index=pd.PeriodIndex(pd.to_datetime(gw.pop('yyyymm').astype(str),format='%Y%m'),freq='M')
    ee=pd.read_excel(EE,sheet_name='Data',usecols=['year','month','FMP_SA_3MA'])
    ee=ee[ee.year.notna()&ee.month.notna()]
    ee.index=pd.PeriodIndex(ee.year.astype(int).astype(str)+'-'+ee.month.astype(int).astype(str).str.zfill(2),freq='M')
    p=gw.reindex(pd.period_range('1995-01','2025-12',freq='M')).copy()
    p['published_SA3MA']=ee.FMP_SA_3MA.reindex(p.index)
    p['x']=p.published_SA3MA.shift(1)
    p['r_excess']=np.log1p(p.CRSP_SPvw)-np.log1p(p.Rfree)
    eligible=p.loc['1996-01':'2025-12','x'].dropna()
    mu,sd=float(eligible.mean()),float(eligible.std(ddof=1))
    p['EE']=(p.x-mu)/sd
    save(p.rename_axis('origin').reset_index(),I/'analysis_panel.csv')
    save(pd.DataFrame([dict(mean=mu,sd=sd,ddof=1,n=len(eligible),start=str(eligible.index[0]),end=str(eligible.index[-1]),source='FMP_SA_3MA',timing='origin_minus_1')]),I/'fixed_scale.csv')
    sink=pd.read_csv(FROZEN/'return_bootstrap_sink_E2E.csv')
    save(sink,I/'frozen_return_bootstrap_sink.csv')
    source=[]
    for col,unit in [('CRSP_SPvw','decimal simple return'),('Rfree','decimal simple return'),('D12','nominal TTM dividend level'),('E12','nominal TTM earnings level')]:
        v=gw[col].reindex(p.index).dropna()
        source.append(dict(source_file=WB.relative_to(ROOT).as_posix(),sheet='Monthly',column=col,unit=unit,transformation='none',n=len(v),start=str(v.index[0]),end=str(v.index[-1]),min=float(v.min()),max=float(v.max())))
    v=ee.FMP_SA_3MA.reindex(p.index).dropna()
    source.append(dict(source_file=EE.relative_to(ROOT).as_posix(),sheet='Data',column='FMP_SA_3MA',unit='fraction of employment per month',transformation='published 3MA; no additional smoothing; x at origin uses previous month',n=len(v),start=str(v.index[0]),end=str(v.index[-1]),min=float(v.min()),max=float(v.max())))
    save(pd.DataFrame(source),I/'source_registry.csv')
    write_json(dict(experiment='E022',gw=WB.relative_to(ROOT).as_posix(),ee=EE.relative_to(ROOT).as_posix(),frozen_innovations=(FROZEN/'reconstructed_monthly_innovations.npz').relative_to(ROOT).as_posix(),innovation_calendar=sink.return_month.tolist(),innovation_generator='original contemporaneous SA plus fourteen GW predictor regression residuals times RandomState(20260925) normal multipliers; innovations reused unchanged',bootstrap_replications=10000,bootstrap_seed=20260925,source_access='read_only',oos_design='current-vintage recursive OOS',fixed_scale=dict(mean=mu,sd=sd,n=len(eligible),ddof=1)),I/'metadata.json')
    print(pd.DataFrame(source).to_string(index=False),flush=True)
    print('Fixed lagged scale',mu,sd,len(eligible),flush=True)

if __name__=='__main__':main()
