from pathlib import Path
import json
import os
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
I, R = ROOT/'data/processed/aligned', ROOT/'results/aligned'
WB = ROOT/'data/raw/descriptive/PredictorData_updated.xlsx'
EE = ROOT/'data/raw/descriptive/e2e-2026-08.xlsx'
FROZEN = ROOT/'results'
HRET = [1,3,6,12]
HCUM = [1,3,6,12,24,36,48,60]
HPOST = [24,36,48,60]
TERMS = {'EE':['const','EE'], 'PAST':['const','past_growth'], 'JOINT':['const','EE','past_growth'], 'HA':['const']}

def save(df, path):
    path.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(path,index=False,float_format='%.17g',encoding='utf-8-sig')

def write_json(obj,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def read_panel():
    p=pd.read_csv(I/'analysis_panel.csv')
    p.index=pd.PeriodIndex(p.pop('origin'),freq='M')
    return p

def stars(p):
    if not np.isfinite(p): return ''
    return '***' if p<.01 else '**' if p<.05 else '*' if p<.10 else ''

def windows():
    return [('cumulative',h,0,0) for h in HCUM]+[('post',h,12,0) for h in HPOST]

def target_panel(p,target,window,h,offset=0,year=0):
    ix=p.loc['1996-01':].index
    c=p[target] if target!='return' else pd.Series(np.nan,index=p.index)
    g=pd.DataFrame(index=ix)
    g['x_raw']=p.x.reindex(ix)
    g['EE']=p.EE.reindex(ix)
    g['const']=1.
    g['level_current']=c.reindex(ix)
    g['level_past']=c.reindex(ix-12).to_numpy()
    g['level_base']=c.reindex(ix+offset).to_numpy()
    g['level_end']=c.reindex(ix+h).to_numpy()
    g['past_growth']=100*np.log(g.level_current.where(g.level_current>0)/g.level_past.where(g.level_past>0))
    if target=='return':
        g['y']=sum(p.r_excess.shift(-j) for j in range(1,h+1)).reindex(ix)*100/h
    else:
        g['y']=100*np.log(g.level_end.where(g.level_end>0)/g.level_base.where(g.level_base>0))
    g['ee_source_month']=(ix-1).astype(str)
    g['growth_base_month']=(ix+offset).astype(str)
    g['first_growth_month']=(ix+offset+1).astype(str)
    g['target_end']=(ix+h).astype(str)
    required=['x_raw','EE','y']+([] if target=='return' else ['past_growth'])
    g=g.dropna(subset=required)
    if window=='annual':
        common=np.ones(len(g),bool)
        for j in range(6):
            values=c.reindex(g.index+12*j).to_numpy()
            common &= np.isfinite(values)&(values>0)
        g=g[common & (g.index+60<=pd.Period('2025-12',freq='M'))]
    g['origin']=g.index.astype(str)
    g['ordinal']=g.index.asi8
    g['target']=target;g['window']=window;g['horizon']=h;g['year']=year
    return g
