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
