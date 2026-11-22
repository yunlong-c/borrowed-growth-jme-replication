"""Source-level preparation for cash-flow, production and economic channels.
Historical serialization precision is retained where it was part of the source chain.
"""
from pathlib import Path
from io import StringIO
import numpy as np
import pandas as pd
from .pricing import build_market_pricing_panel
E=Path(__file__).resolve().parents[2]
RAW=E/'data/raw/channels';SHARED=E/'data/raw/descriptive';I=E/'data/processed'

def roundtrip(a,precision=15):
    return pd.read_csv(StringIO(a.to_csv(index=False,float_format=f'%.{precision}g')))

def write(a,name):
    a.to_csv(I/name,index=False,float_format='%.17g')

def gw_data():
    g=pd.read_excel(SHARED/'PredictorData_updated.xlsx',sheet_name='Monthly')
    g.index=pd.to_datetime(g.yyyymm.astype(str),format='%Y%m').dt.to_period('M')
    return g

def prepare_sources():
    I.mkdir(parents=True,exist_ok=True)
    pub=pd.read_excel(SHARED/'e2e-2026-08.xlsx',sheet_name='Data')
    pub=pub.loc[pd.to_numeric(pub.year,errors='coerce').notna() & pd.to_numeric(pub.month,errors='coerce').notna()].copy()
    pub['economic_month']=pd.to_datetime(dict(year=pub.year,month=pub.month,day=1)).dt.to_period('M').astype(str)
    pub=pub.loc[pub.economic_month.between('1995-10','2025-12')]
    # E015 serializes the published input with %.17g.
    pub=roundtrip(pub,17)
    gw=gw_data();levels=[]
    for name in ['E12','D12']:
        # E007 monthly source levels were stored at 15 significant digits.
        a=roundtrip(pd.DataFrame({'date':gw.index.astype(str),'level':gw[name].to_numpy()}))
        a=a[a.date<='2025-12'];a.insert(0,'frequency','M');a.insert(0,'target',name);levels.append(a)
    for name in ['COMPNFB','OPHNFB','ULCNFB']:
        a=pd.read_csv(RAW/(name+'.csv'))
        a=pd.DataFrame({'target':name,'frequency':'Q','date':pd.to_datetime(a.observation_date).dt.to_period('Q').astype(str),'level':a[name]})
        levels.append(a[a.date<='2025Q4'])
    write(pd.concat(levels), 'channel_source_levels.csv')
    sce=pd.DataFrame()
    for name,sheet in [('JF','Job finding expectations'),('JL','Job separation expectation')]:
        x=pd.read_excel(RAW/'frbny-sce-data.xlsx',sheet_name=sheet,header=3)
        dates=pd.to_datetime(pd.to_numeric(x.iloc[:,0],errors='coerce').astype('Int64').astype(str),format='%Y%m',errors='coerce');valid=dates.notna()
        sce[name]=pd.Series(pd.to_numeric(x.loc[valid].iloc[:,1],errors='coerce').to_numpy(),index=pd.PeriodIndex(dates[valid],freq='M'))
    sce=sce.loc[:'2025-12']
    write(roundtrip(sce.rename_axis('date').reset_index()),'channel_sce_levels.csv')
    # External pricing panel originally passed through 12-digit source CSV,
    # then E007's 15-digit snapshot. Preserve both before standardization.
    pricing=roundtrip(roundtrip(build_market_pricing_panel(),12),15)
    write(pricing,'channel_pricing_levels.csv')
    return pub
