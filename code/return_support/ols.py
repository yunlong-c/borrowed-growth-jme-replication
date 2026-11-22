import numpy as np

def _ols_forecast(y,x,current):
    design=np.column_stack([np.ones(len(x)),np.asarray(x,float)])
    params=np.linalg.lstsq(design,np.asarray(y,float),rcond=None)[0]
    return float(params[0]+params[1]*current),float(params[0]),float(params[1])
