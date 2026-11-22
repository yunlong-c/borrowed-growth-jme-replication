from pathlib import Path
import sys, json
import numpy as np
import pandas as pd
from scipy.stats import t as student, norm
from .calendar_inference import fit as shared_fit

def hac_cov(x,res,ordinal,lag,correction=True):
    n,k=x.shape;bread=np.linalg.inv(x.T@x);score=x*res[:,None];meat=score.T@score
    for l in range(1,lag+1):
        prev=np.searchsorted(ordinal,ordinal-l);mask=(prev<n)&(ordinal[np.minimum(prev,n-1)]==ordinal-l)
        a=score[mask].T@score[prev[mask]];meat+=(1-l/(lag+1))*(a+a.T)
    return bread@meat@bread*(n/(n-k) if correction else 1)
def regression(frame,spec):
    terms=spec['terms'];x=frame[terms].to_numpy(float);y=frame.y.to_numpy(float)
    ordinal=frame.ordinal.to_numpy(int);lag=spec['lag'];correction=spec.get('correction',True)
    a=shared_fit(y,x,ordinal,lag,correction);cov=hac_cov(x,a['residual'],ordinal,lag,correction)
    b=a['beta'];se=np.sqrt(np.diag(cov));stat=b/se;n,k=x.shape
    p=2*(norm.sf(abs(stat)) if spec.get('normal',False) else student.sf(abs(stat),n-k))
    rows=[dict(model=spec['id'],term=t,beta=b[i],se=se[i],t=stat[i],p=p[i],n=n,k=k,r2=a['r2'],start=frame.date.iloc[0],end=frame.date.iloc[-1],lag=lag,status='OK') for i,t in enumerate(terms)]
    for name,weights in spec.get('contrasts',{}).items():
        v=np.array([weights.get(t,0) for t in terms]);value=float(v@b);ss=float(np.sqrt(v@cov@v));tt=value/ss
        rows.append(dict(model=spec['id'],term=name,beta=value,se=ss,t=tt,p=float(2*student.sf(abs(tt),n-k)),n=n,k=k,r2=a['r2'],start=frame.date.iloc[0],end=frame.date.iloc[-1],lag=lag,status='OK'))
    ledger=frame.copy();ledger['model']=spec['id'];ledger['fitted']=x@b;ledger['residual']=a['residual']
    cv=[dict(model=spec['id'],row=t,column=u,value=cov[i,j]) for i,t in enumerate(terms) for j,u in enumerate(terms)]
    return rows,ledger,cv
