"""Demeaned VAR(1) return-news decomposition and component projections.

The conventions follow the verified CSU C01 recipe; input mappings and the
PCA information set are explicit arguments. This module never writes files.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
from scipy.stats import norm


def decompose_returns(panel: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame]:
    """Estimate the registered systems and component projections.

    Optional system_ids selects and orders systems from BASE, the supplied
    additional states, and PC3. Optional measure_standardization supplies
    a frozen mean and sd; otherwise the input sample defines the scale.
    Optional systems supplies explicit id/label/states entries, including
    multivariate economic information sets. State names use r, dp and the
    registered additional_states (or generated PC names).
    Optional rho_rule is author_dp (default) or monthly_dp. The latter converts
    the annual dividend yield to a monthly yield only in the rho formula; the
    native dp state is unchanged. Default output schemas remain unchanged.
    """
    date, market, measure, dp = (config[k] for k in ['date_column','market_column','measure_column','dp_column'])
    required=list(dict.fromkeys([date,market,measure,dp,*config['pca_inputs'],*config['additional_states']]))
    frame=panel[required].copy().reset_index(drop=True)
    months=pd.PeriodIndex(frame[date],freq='M')
    if not months.equals(pd.period_range(config['sample_start'],config['sample_end'],freq='M')):
        raise ValueError('Registered decomposition calendar differs from input')
    # Candidate economic states may have source gaps. Core financial states and
    # the projection measure must remain complete; missingness is system-local.
    if frame[[market,measure,dp,*config['pca_inputs']]].isna().any().any():
        raise ValueError('Missing core financial or measure input')
    returns=np.log1p(frame[market].to_numpy(float))
    m=frame[measure].to_numpy(float)
    scaling=config.get('measure_standardization')
    mz=(m-m.mean())/m.std(ddof=1) if scaling is None else (m-float(scaling['mean']))/float(scaling['sd'])
    rho_rule=config.get('rho_rule','author_dp')
    if rho_rule not in ('author_dp','monthly_dp'):
        raise ValueError('rho_rule must be author_dp or monthly_dp')
    rho_divisor=12. if rho_rule=='monthly_dp' else 1.
    inputs=frame[config['pca_inputs']].to_numpy(float)
    pm=inputs.mean(0); ps=inputs.std(0,ddof=1); pz=(inputs-pm)/ps
    _,_,vt=np.linalg.svd(pz,full_matrices=False)
    loadings=vt[:config['pca_components']].T
    pcs=pz@loadings
    pl=[{'variable':v,'mean':pm[i],'sd_ddof1':ps[i],'pc':j+1,'loading':loadings[i,j]} for i,v in enumerate(config['pca_inputs']) for j in range(config['pca_components'])]
    pc=pd.DataFrame(pcs,columns=[f'PC{i+1}' for i in range(config['pca_components'])]);pc.insert(0,'month',months.astype(str))
    base={'r':returns,'dp':frame[dp].to_numpy(float)}
    systems=[('BASE','r, DP',['r','dp'])]
    for state in config['additional_states']:
        base[state]=frame[state].to_numpy(float)
        systems.append((state,'r, DP, '+config['state_labels'][state],['r','dp',state]))
    for j in range(config['pca_components']): base[f'PC{j+1}']=pcs[:,j]
    systems.append(('PC3','r, DP, PC',['r','dp',*[f'PC{j+1}' for j in range(config['pca_components'])]]))
    if 'systems' in config:
        systems=[(s['id'],s['label'],s['states']) for s in config['systems']]
    if 'system_ids' in config:
        available={item[0]:item for item in systems}
        systems=[available[sid] for sid in config['system_ids']]
    registry=[];params=[];loads=[];observations=[];components=[];estimates=[];projections=[];hac=[];identities=[]
    for order,(sid,label,states) in enumerate(systems):
        all_y=np.column_stack([base[s] for s in states])
        valid=np.isfinite(all_y).all(axis=1)
        y=all_y[valid]; smonths=months[valid]; sm=m[valid]; smz=mz[valid]
        left=np.flatnonzero(np.diff(smonths.asi8)==1);right=left+1
        mean=y.mean(0);z=y-mean
        rho=float(1/(1+np.exp(y[:,1].mean())/rho_divisor))
        a=np.linalg.lstsq(z[left],z[right],rcond=None)[0].T
        rank=int(np.linalg.matrix_rank(z[left]));radius=float(max(abs(np.linalg.eigvals(rho*a))))
        record={'system':sid,'system_order':order,'var_label':label,'states':json.dumps(states),'n_states':len(states),'state_rows':len(y),'n':len(left),'sample_start':str(smonths[0]),'sample_end':str(smonths[-1]),'rho':rho,'rank':rank,'discounted_spectral_radius':radius,'var_order':1,'var_intercept':False,'status':'OK'}
        for j,s in enumerate(states):
            params.append({'system':sid,'kind':'mean','row_state':s,'column_state':'','value':mean[j]})
            for k,t in enumerate(states): params.append({'system':sid,'kind':'transition','row_state':s,'column_state':t,'value':a[j,k]})
            observations.extend({'system':sid,'month':str(smonths[i]),'state':s,'value':y[i,j],'demeaned':z[i,j]} for i in range(len(y)))
        if rank!=len(states) or radius>=1:
            record['status']='FAILED_RANK' if rank!=len(states) else 'FAILED_DISCOUNTED_STABILITY'
            registry.append(record)
            estimates.extend({'system':sid,'component':c,'status':record['status']} for c in ['expected','cash_flow','discount_rate'])
            continue
        selector=np.eye(len(states))[0]
        dr=np.linalg.solve((np.eye(len(states))-rho*a).T,(rho*(selector@a)).T)
        cf=selector+dr
        fitted=z[left]@a.T;u=z[right]-fitted
        er=fitted[:,0]+mean[0];dn=u@dr;cn=u@cf;real=y[right,0]
        for j,s in enumerate(states):loads.append({'system':sid,'state':s,'DR_loading':dr[j],'CF_loading':cf[j]})
        for i in range(len(real)):
            components.append({'system':sid,'origin':str(smonths[left[i]]),'outcome_month':str(smonths[right[i]]),'measure_raw':sm[left[i]],'measure_z':smz[left[i]],'realized_return':real[i],'expected_return':er[i],'return_innovation':u[i,0],'cash_flow_news':cn[i],'discount_rate_news':dn[i],'identity_error':real[i]-er[i]-cn[i]+dn[i]})
        betas={}
        for name,outcome in [('expected',er),('cash_flow',cn),('discount_rate',dn)]:
            intercept=config['projection_intercepts'][name]
            x=np.column_stack([np.ones(len(real)),smz[left]]) if intercept else smz[left,None]
            yy=100*outcome;b=np.linalg.lstsq(x,yy,rcond=None)[0];fit=x@b;res=yy-fit
            scores=x*res[:,None];bread=np.linalg.inv(x.T@x);meat=scores.T@scores
            for lag in range(config['hac_lag']+1):
                if lag==0:
                    g=scores.T@scores
                else:
                    ords=smonths[left].asi8
                    prior=np.searchsorted(ords,ords-lag)
                    paired=(prior<len(ords))&(ords[np.minimum(prior,len(ords)-1)]==ords-lag)
                    g=scores[paired].T@scores[prior[paired]]
                weight=1-lag/(config['hac_lag']+1)
                if lag:meat+=weight*(g+g.T)
                for j in range(x.shape[1]):
                    for k in range(x.shape[1]):hac.append({'system':sid,'component':name,'lag':lag,'row':j,'column':k,'weight':weight,'score_cross_sum':g[j,k]})
            correction=len(yy)/(len(yy)-x.shape[1]) if config['finite_sample_correction'] else 1.
            cov=bread@meat@bread*correction;se=float(np.sqrt(cov[-1,-1]));beta=float(b[-1]);t=beta/se
            betas[name]=beta
            estimates.append({'system':sid,'system_order':order,'var_label':label,'component':name,'n':len(real),'origin_start':str(smonths[left[0]]),'origin_end':str(smonths[left[-1]]),'target_start':str(smonths[right[0]]),'target_end':str(smonths[right[-1]]),'beta':beta,'hac_se':se,'t_stat':t,'p_two_sided_normal':2*norm.sf(abs(t)),'intercept':intercept,'alpha':float(b[0]) if intercept else 0.,'display_scale':100,'kernel':'Bartlett','bandwidth':config['hac_lag'],'finite_sample_correction':config['finite_sample_correction'],'status':'OK'})
            for i in range(len(real)):projections.append({'system':sid,'component':name,'origin':str(smonths[left[i]]),'outcome_month':str(smonths[right[i]]),'measure_z':smz[left[i]],'intercept':intercept,'outcome_percentage_points':yy[i],'fitted':fit[i],'residual':res[i],'score_measure':scores[i,-1]})
        common=np.column_stack([np.ones(len(real)),smz[left]])
        common_b=np.linalg.lstsq(common,100*np.column_stack([real,er,cn,dn]),rcond=None)[0][1]
        identities.append({'system':sid,'return_identity_max_error':float(max(abs(real-er-cn+dn))),'news_identity_max_error':float(max(abs(u[:,0]-cn+dn))),'common_design_slope_identity_error':float(common_b[0]-common_b[1]-common_b[2]+common_b[3]),'formal_mixed_design_slope_difference':float(common_b[0]-betas['expected']-betas['cash_flow']+betas['discount_rate']),'status':'OK'})
        registry.append(record)
    return {name:pd.DataFrame(rows) for name,rows in {
        'var_systems.csv':registry,'var_parameters.csv':params,'news_loadings.csv':loads,'var_observations.csv':observations,
        'return_components.csv':components,'return_decomposition_estimates.csv':estimates,'projection_observations.csv':projections,
        'hac_components.csv':hac,'decomposition_validation.csv':identities,'pca_loadings.csv':pl,'pca_scores.csv':pc,
    }.items()}
