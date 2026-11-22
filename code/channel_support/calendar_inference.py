"""Date-aware counterparts of the measure-lab fixed-design calculations.

Missing observations are omitted from OLS, not from the monthly calendar.
Complete calendars dispatch to the existing shared multivariate HAC routine.
"""
import numpy as np
from scipy.stats import t as student
from .conditional_in_sample import multivariate_hac_many

def hac_many(y, x, months, lag, correction=True):
    y=np.atleast_2d(np.asarray(y,float)); x=np.asarray(x,float)
    months=np.asarray(months,int)
    n,k=x.shape
    if np.linalg.matrix_rank(x)!=k: raise ValueError('Singular registered design')
    if correction and np.all(np.diff(months)==1):
        return multivariate_hac_many(y,x,lag)
    bread=np.linalg.inv(x.T@x)
    beta=y@x@bread
    residual=y-beta@x.T
    influence=x@bread
    variance=np.empty((len(y),k))
    for j in range(k):
        scores=residual*influence[:,j]
        v=np.sum(scores*scores,axis=1)
        for l in range(1,lag+1):
            left=np.searchsorted(months,months-l)
            valid=(left<n)&(months[np.minimum(left,n-1)]==months-l)
            v+=2*(1-l/(lag+1))*np.sum(scores[:,valid]*scores[:,left[valid]],axis=1)
        variance[:,j]=v*(n/(n-k) if correction else 1.)
    se=np.sqrt(variance)
    return beta,se,beta/se

def fit(y,x,months,lag,correction=True):
    b,se,t=hac_many(y,x,months,lag,correction)
    residual=np.asarray(y)-x@b[0]
    r2=1-float(residual@residual)/float(np.sum((y-np.mean(y))**2))
    return dict(beta=b[0],se=se[0],t=t[0],residual=residual,r2=r2)

def conditional_bootstrap(y,x,months,shocks,lag,columns,batch=500):
    observed=hac_many(y,x,months,lag)[2][0]
    rows=[]
    for c in columns:
        nuisance=np.delete(x,c,axis=1)
        fitted=nuisance@np.linalg.lstsq(nuisance,y,rcond=None)[0]
        count=0; sample=[]
        for a in range(0,len(shocks),batch):
            ts=hac_many(fitted[None,:]+shocks[a:a+batch],x,months,lag)[2][:,c]
            count+=int(np.count_nonzero(np.abs(ts)>=abs(observed[c])))
            sample.extend(ts[:min(3,len(ts))] if a==0 else [])
        rows.append(dict(column=c,observed_t=observed[c],extreme_count=count,
                         p_boot=count/len(shocks),first_three_t=sample))
    return rows

def mean_test(values, months, lag):
    values=np.asarray(values,float)
    return float(hac_many(values,np.ones((len(values),1)),months,lag,False)[2][0,0])

def cw_metrics(actual, forecast, benchmark, months, horizon):
    ea=actual-forecast; eb=actual-benchmark
    d=eb**2-ea**2+(benchmark-forecast)**2
    stat=mean_test(d,months,horizon)
    return dict(n=len(actual),r2_os=100*(1-np.sum(ea**2)/np.sum(eb**2)),
                cw=stat,p_cw=float(student.sf(stat,len(actual)-2)),model_msfe=np.mean(ea**2),
                benchmark_msfe=np.mean(eb**2))

def encompassing(actual,base,added,months,h):
    eb=actual-base; ea=actual-added; delta=added-base
    lam=float(delta@eb/(delta@delta))
    n=len(actual)
    factor=np.sqrt((n+1-2*h+h*(h-1)/n)/n)
    stat=factor*mean_test(eb*(eb-ea),months,h)
    return dict(n=n,lambda_raw=lam,lambda_display=float(np.clip(lam,0,1)),
                mhln=stat,p_mhln=float(student.sf(stat,n-1)),hln_factor=factor)

