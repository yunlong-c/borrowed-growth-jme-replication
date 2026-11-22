"""Reconstruct native economic observations from the supplied frozen provider files.

Adapted from Data/Paper_Measures_2026-09-23/build_measures.py.
No forecast alignments occur here. Missing calendar periods remain missing.
"""
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'data/raw/descriptive'
OUT=ROOT/'data/processed'

def series(values,dates,freq='M'):
    return pd.Series(pd.to_numeric(pd.Series(values),errors='coerce').to_numpy(),index=pd.PeriodIndex(dates,freq=freq),dtype=float).sort_index()
def calendar(s):
    return s.reindex(pd.period_range(s.index.min(),s.index.max(),freq=s.index.freq))
def fred(sid,freq='M'):
    d=pd.read_csv(RAW/(sid+'.csv'))
    return calendar(series(d[sid],pd.to_datetime(d.iloc[:,0]),freq))
def book(name,sheet):
    w=load_workbook(RAW/name,read_only=True,data_only=True)
    rows=list(w[sheet].values);w.close();return rows
def growth(s,lag):
    s=calendar(s);return 100*(np.log(s)-np.log(s.shift(lag)))
def write(d,name):
    OUT.mkdir(parents=True,exist_ok=True)
    d=d.copy();d.index.name='date';d.to_csv(OUT/name,float_format='%.17g')

def build():
    m={};q={}
    rr=book('e2e-2026-08.xlsx','Data');header=list(rr[0]);rr=[r for r in rr[1:] if isinstance(r[0],(int,float))]
    dates=[f'{int(r[0])}-{int(r[1]):02d}' for r in rr]
    for key in ['FMP_NSA','FMP_SA','FMP_SA_3MA']:
        j=header.index(key);m[key]=calendar(series([r[j] for r in rr],dates))
    m['E2E']=m['FMP_SA']
    pay=fred('PAYEMS');u=fred('UNEMPLOY');m['PAYROLL']=growth(pay,1)
    for key,sid in [('UNEMP','UNRATE'),('LFPR','CIVPART'),('EPR','EMRATIO')]:m[key]=fred(sid)
    income=calendar((fred('PI')-fred('PDI'))/fred('POPTHM'))
    m['LIG_JW']=100*((income+income.shift(1))/(income.shift(1)+income.shift(2))-1)
    d=pd.read_csv(RAW/'IC4WSA.csv');dates=pd.to_datetime(d.iloc[:,0]);vals=pd.to_numeric(d.IC4WSA,errors='coerce')
    claim=pd.Series(vals.to_numpy(),index=dates)
    claims=claim.groupby(claim.index.to_period('M')).agg(lambda x:x.iloc[-1])
    last=dates.max().to_period('M') if dates.max().is_month_end else dates.max().to_period('M')-1
    claims=claims.loc[:last];m['CLAIMS_INTENSITY']=(100*claims/(1000*fred('CE16OV').shift(1))).reindex(claims.index)
    rr=[r for r in book('barnichon_composite_hwi.xlsx','Sheet1')[8:] if isinstance(r[0],(int,float))]
    dates=[]
    for r in rr:
        y=int(r[0]+1e-8);month=round((r[0]-y)*12)+1;dates.append(f'{y}-{month:02d}')
    bv=series([r[1] for r in rr],dates);cut=pd.Period('2000-12','M')
    v=fred('JTSJOL');pv=fred('JTS1000JOL');pe=fred('USPRIV')
    vl=pd.concat([bv.loc[bv.index<cut],v.loc[v.index>=cut]])
    private_scale=pv.loc[cut]/bv.loc[cut]
    pl=pd.concat([bv.loc[bv.index<cut]*private_scale,pv.loc[pv.index>=cut]])
    vu=calendar(np.log(vl/u)).reindex(vl.index)
    m['LOG_VU_LONG']=vu;m['LMT_VU_LONG']=vu.diff()
    m['JPR_PRIVATE_LONG']=(100*pl/(pe+pl)).reindex(pl.index)
    rr=[r for r in book('DFH XS TS Synthetic JOLTS Series (1990-2010).xlsx','Data')[1:] if isinstance(r[0],(int,float))]
    dates=[str(int(r[0]))[:4]+'Q'+str(int(r[0]))[-1] for r in rr]
    splices=[dict(variable='JPR_PRIVATE_LONG',parameter='private_vacancy_scale',value=private_scale,anchor='2000-12')]
    for base,j,sid in [('HIRES',3,'JTS1000HIR'),('QUITS',5,'JTS1000QUR')]:
        qs=series([r[j] for r in rr],dates,'Q');mi=pd.period_range(qs.index.min().asfreq('M','start'),qs.index.max().asfreq('M','end'),freq='M')
        mapped=pd.Series([qs.loc[t.asfreq('Q')]/3 for t in mi],index=mi)
        jolts=fred(sid);offset=jolts.loc[cut]-mapped.loc[cut]
        m[base+'_PRIVATE_LONG']=pd.concat([mapped.loc[mapped.index<cut]+offset,jolts.loc[jolts.index>=cut]])
        splices.append(dict(variable=base+'_PRIVATE_LONG',parameter='level_shift',value=offset,anchor='2000-12'))
    flows=[fred('LNS'+s+'00000') for s in ['171','175','179']]
    m['CPS_UE']=100*flows[0]/(flows[0]+flows[1]+flows[2])
    d=pd.read_csv(RAW/'j2jr_us_d_f_gn_n_oslp_s.csv.gz',dtype=str)
    selectors={'geography':'00','industry':'00','ownercode':'A00','sex':'0','agegrp':'A00','race':'A0','ethnicity':'A0','education':'E0','firmage':'0','firmsize':'0'}
    for col,val in selectors.items():d=d.loc[d[col]==val]
    flag=pd.to_numeric(d.sEEHireR);values=pd.to_numeric(d.EEHireR,errors='coerce').where(flag.isin([1,6,7,9,10,12]))
    q['LEHD_EEHireR']=series(values,d.year+'Q'+d.quarter,'Q')
    rr=[r for r in book('wage-growth-data.xlsx','data_overall') if isinstance(r[0],datetime)]
    st=series([r[8] for r in rr],[r[0] for r in rr]);sw=series([r[9] for r in rr],[r[0] for r in rr])
    m.update(WGT_STAYER=st,WGT_SWITCHER=sw,WGT_SPREAD=sw-st)
    for key,sid in [('COMP_GROWTH','COMPNFB'),('PRODUCTIVITY_GROWTH','OPHNFB'),('ULC_GROWTH','ULCNFB'),('LS_NFB_INDEX','PRS85006173')]:
        raw=fred(sid,'Q');q[key]=raw if key=='LS_NFB_INDEX' else growth(raw,4)
    rr=book('PredictorData_updated.xlsx','Monthly');d=pd.DataFrame(rr[1:],columns=rr[0]);d=d.loc[pd.to_numeric(d.iloc[:,0],errors='coerce').notna()]
    dates=[f'{int(v)//100}-{int(v)%100:02d}' for v in d.iloc[:,0]]
    s={c:calendar(series(d[c],dates)) for c in d.columns[1:] if c}
    m.update(DP=np.log(s['D12'])-np.log(s['Index']),DY=np.log(s['D12'])-np.log(s['Index'].shift()),EP=np.log(s['E12'])-np.log(s['Index']),DE=np.log(s['D12'])-np.log(s['E12']),BM=s['b/m'],NTIS=s['ntis'],TBL=s['tbl'],LTY=s['lty'],TMS=s['lty']-s['tbl'],DFY=s['BAA']-s['AAA'],LTR=s['ltr'],DFR=s['corpr']-s['ltr'],SVAR=s['svar'],INFL=s['infl'])
    m['MARKET_EXCESS_LOG_RETURN']=np.log1p(s['CRSP_SPvw'])-np.log1p(s['Rfree'])
    m['MARKET_SIMPLE_RETURN']=s['CRSP_SPvw'];m['RFREE']=s['Rfree'];m['D12']=s['D12'];m['E12']=s['E12'];m['USREC']=fred('USREC')
    # Preserve native histories so each downstream specification selects its own sample.
    monthly=pd.concat(m,axis=1).sort_index();quarterly=pd.concat(q,axis=1).sort_index()
    write(monthly,'native_measures.csv');write(quarterly,'native_quarterly.csv')
    pd.DataFrame(splices).to_csv(OUT/'data_splice_parameters.csv',index=False)
    return monthly,quarterly
