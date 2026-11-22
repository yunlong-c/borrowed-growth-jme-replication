"""E022 estimation only. Results are frozen once; presentation imports no estimator."""
import sys
import time
from scipy.stats import t as student
from config import *
sys.path.insert(0,str(ROOT/"code"))
from aligned_hac import fit,hac_many

ROWS,SAMPLES,BOOT,OBJECTS,TARGETS=[],[],[],{},[]
FORECASTS,TRAINING,MEMBERS,COMPARISONS=[],[],[],[]

def covariance(x,u,months,lag):
    scores=x*u[:,None]
    meat=scores.T@scores
    for j in range(1,lag+1):
        left=np.searchsorted(months,months-j)
        ok=(left<len(months))&(months[np.minimum(left,len(months)-1)]==months-j)
        cross=scores[ok].T@scores[left[ok]]
        meat+=(1-j/(lag+1))*(cross+cross.T)
    bread=np.linalg.inv(x.T@x)
    return bread,meat,bread@meat@bread*len(x)/(len(x)-x.shape[1])

def moving_pair_boot(g,models,seed_rng):
    """Paired non-circular blocks; bootstrap NW uses the concatenated draw calendar."""
    n=len(g);b=20000;length=12;m=(n+length-1)//length
    starts=seed_rng.randint(0,n-length+1,size=(b,m)).astype(np.int32)
    out={'block_starts':starts,'block_length':np.array(length),'n':np.array(n)}
    y=g.y.to_numpy()
    allx=g[['const','EE','past_growth']].to_numpy()
    for model in models:
        positions=[['const','EE','past_growth'].index(z) for z in TERMS[model]]
        original=fit(y,allx[:,positions],g.ordinal.to_numpy(),12)
        beta=np.empty((b,len(positions)));se=np.empty_like(beta)
        for a in range(0,b,250):
            z=min(a+250,b)
            take=(starts[a:z,:,None]+np.arange(length)).reshape(z-a,-1)[:,:n]
            xx=allx[take][:,:,positions];yy=y[take]
            bread=np.linalg.inv(np.einsum('bni,bnj->bij',xx,xx))
            bb=np.einsum('bij,bnj,bn->bi',bread,xx,yy)
            residual=yy-np.einsum('bni,bi->bn',xx,bb)
            influence=np.einsum('bni,bij->bnj',xx,bread)
            score=residual[:,:,None]*influence
            vv=np.sum(score**2,axis=1)
            for lag in range(1,13):
                vv+=2*(1-lag/13)*np.sum(score[:,lag:]*score[:,:-lag],axis=1)
            beta[a:z]=bb;se[a:z]=np.sqrt(vv*n/(n-len(positions)))
        out[model+'_beta']=beta;out[model+'_se']=se
        out[model+'_t_centered']=(beta-original['beta'])/se
    return out

def register(g,model,lag,formal,boot=None):
    target,window,h,year=g.iloc[0][['target','window','horizon','year']]
    rid=f'{target}_{window}_{h}_{model}'
    x=g[TERMS[model]].to_numpy();y=g.y.to_numpy();months=g.ordinal.to_numpy()
    f=fit(y,x,months,lag)
    bread,meat,cov=covariance(x,f['residual'],months,lag)
    for name,a in [('beta',f['beta']),('se',f['se']),('t',f['t']),('bread',bread),('meat',meat),('cov',cov)]:
        OBJECTS[rid+'__'+name]=a
    n,k=x.shape
    ss=g.copy();ss['regression_id']=rid;ss['model']=model
    ss['fitted']=y-f['residual'];ss['residual']=f['residual']
    SAMPLES.append(ss.reset_index(drop=True))
    for j,term in enumerate(TERMS[model]):
        count=np.nan;pb=np.nan
        pn=float(2*student.sf(abs(f['t'][j]),n-k))
        if j>0 and boot is not None:
            td=boot[model+'_t_centered'][:,j]
            count=int(np.count_nonzero(np.abs(td)>=abs(f['t'][j])))
            pb=(count+1)/(len(td)+1)
            BOOT.append(dict(regression_id=rid,term=term,observed_t=f['t'][j],extreme_count=count,replications=len(td),p_formal=pb,seed=20261006,block_length=12,method=formal,failed_draws=int(np.count_nonzero(~np.isfinite(td)))))
        pf=pb if j>0 and boot is not None else pn
        ROWS.append(dict(regression_id=rid,target=target,window=window,horizon=h,year=year,model=model,term=term,n=n,k=k,origin_start=g.origin.iloc[0],origin_end=g.origin.iloc[-1],first_growth_month=g.first_growth_month.iloc[0],last_target_end=g.target_end.iloc[-1],ee_source_start=g.ee_source_month.iloc[0],ee_source_end=g.ee_source_month.iloc[-1],beta=f['beta'][j],se_nw=f['se'][j],t_nw=f['t'][j],p_nw_student=pn,p_boot=pb,p_formal=pf,stars=stars(pf) if j else '',r2=100*f['r2'],adj_r2=100*(1-(1-f['r2'])*(n-1)/(n-k)),lag=lag,correction=n/(n-k),formal_inference=formal if j else 'Student-t intercept diagnostic',extreme_count=count,beta_cumulative=h*f['beta'][j] if target=='return' else np.nan,se_cumulative=h*f['se'][j] if target=='return' else np.nan,status='OK'))
    return rid,f

def returns_is(p):
    innovations=np.load(FROZEN/'reconstructed_monthly_innovations.npz')['innovations']
    calendar=pd.PeriodIndex(pd.read_csv(I/'frozen_return_bootstrap_sink.csv').return_month,freq='M')
    cs=np.column_stack([np.zeros(len(innovations)),np.cumsum(innovations,axis=1)])
    samples={}
    for h in HRET:
        g=target_panel(p,'return','return',h)
        rid,f=register(g,'EE',h,'original monthly wild bootstrap (two-sided studentized; +1)')
        take=calendar.get_indexer(pd.PeriodIndex(g.first_growth_month,freq='M'))
        if np.any(take<0):raise ValueError('Innovation calendar does not cover target starts.')
        shocks=100*(cs[:,take+h]-cs[:,take])/h
        xx=g[TERMS['EE']].to_numpy();td=np.empty(len(innovations))
        for a in range(0,len(td),500):
            td[a:a+500]=hac_many(g.y.mean()+shocks[a:a+500],xx,g.ordinal.to_numpy(),h)[2][:,1]
        count=int(np.count_nonzero(abs(td)>=abs(f['t'][1])));prob=(count+1)/(len(td)+1)
        row=ROWS[-1];row.update(p_boot=prob,p_formal=prob,stars=stars(prob),extreme_count=count)
        BOOT.append(dict(regression_id=rid,term='EE',observed_t=f['t'][1],extreme_count=count,replications=len(td),p_formal=prob,seed=20260925,block_length=np.nan,method=row['formal_inference'],failed_draws=int(np.count_nonzero(~np.isfinite(td)))))
        np.savez_compressed(R/'bootstrap'/f'{rid}.npz',t_draws=td,innovation_first_columns=take,months=g.ordinal.to_numpy(),null_mean=np.array(g.y.mean()))
        TARGETS.append(g.reset_index(drop=True));samples[h]=g
        print('Return IS',h,'beta',row['beta'],'p',prob,flush=True)
    return samples

def cash_is(p):
    rng=np.random.RandomState(20261006);samples={}
    for target in ['D12','E12']:
        for window,h,offset,year in windows()+[('annual',k*12,(k-1)*12,k) for k in range(1,6)]:
            g=target_panel(p,target,window,h,offset,year)
            models=['EE','JOINT'] if window=='annual' else ['EE','PAST','JOINT']
            short=window=='cumulative' and h<=12
            lag=60 if window=='annual' else 12 if short else h
            boot=moving_pair_boot(g,models,rng) if short else None
            formal='paired MBB(12), centered studentized two-sided +1' if short else 'two-sided Student-t(N-K)'
            if boot is not None:np.savez_compressed(R/'bootstrap'/f'{target}_{window}_{h}.npz',**boot)
            for model in models:register(g,model,lag,formal,boot)
            TARGETS.append(g.reset_index(drop=True))
            if target=='D12' and window!='annual':samples[(window,h)]=g
            print('Cash IS',target,window,h,len(g),flush=True)
    return samples

def recursive(g,p,target,window,h):
    for origin,current in g.loc['2009-12':].iterrows():
        tr=g[g.target_end<=str(origin)]
        train_id=f'{target}_{window}_{h}_{origin}'
        mu=float(tr.x_raw.mean());sd=float(tr.x_raw.std(ddof=1));z=(tr.x_raw-mu)/sd
        base=dict(training_id=train_id,target=target,window=window,horizon=h,forecast_origin=str(origin),ee_source_month=current.ee_source_month,growth_base_month=current.growth_base_month,first_growth_month=current.first_growth_month,target_end=current.target_end,n_train=len(tr),training_origin_start=tr.origin.iloc[0],training_origin_end=tr.origin.iloc[-1],max_training_target_end=tr.target_end.max(),mean_x=mu,sd_x=sd,x_raw=current.x_raw,x_z=(current.x_raw-mu)/sd,past_growth=current.past_growth,actual=current.y)
        member=tr[['origin','ee_source_month','growth_base_month','first_growth_month','target_end','x_raw','y','past_growth']].copy()
        member['training_id']=train_id;member['forecast_origin']=str(origin)
        MEMBERS.append(member)
        models=['EE','HA'] if target=='return' else ['EE','PAST','JOINT','HA']
        for model in models:
            terms=TERMS[model]
            xx=tr[terms].copy()
            if 'EE' in terms:xx['EE']=z
            yy=tr.y.to_numpy();beta=np.linalg.lstsq(xx.to_numpy(),yy,rcond=None)[0]
            now={'const':1.,'EE':base['x_z'],'past_growth':current.past_growth}
            ha_start='';ha_end='';ha_n=np.nan
            if model=='HA' and target=='return':
                history=p.loc['1995-12':str(origin),'r_excess'].dropna()
                prediction=float(100*history.mean());beta=np.array([prediction])
                ha_start=str(history.index[0]);ha_end=str(history.index[-1]);ha_n=len(history)
            else:prediction=float(np.array([now[z] for z in terms])@beta)
            fits=dict(base,model=model,intercept=beta[0],beta_EE=beta[terms.index('EE')] if 'EE' in terms else np.nan,beta_past=beta[terms.index('past_growth')] if 'past_growth' in terms else np.nan,ha_history_start=ha_start,ha_history_end=ha_end,ha_n=ha_n,status='OK')
            TRAINING.append(fits)
            FORECASTS.append(dict(fits,forecast=prediction,error=current.y-prediction))

def compare_forecasts():
    fc=pd.DataFrame(FORECASTS)
    for (target,window,h),g in fc.groupby(['target','window','horizon'],sort=False):
        pairs=[('EE','HA')] if target=='return' else [('EE','HA'),('PAST','HA'),('JOINT','HA'),('JOINT','PAST')]
        for model,benchmark in pairs:
            a=g[g.model==model].sort_values('forecast_origin');bb=g[g.model==benchmark].set_index('forecast_origin').loc[a.forecast_origin,'forecast'].to_numpy()
            yy=a.actual.to_numpy();ff=a.forecast.to_numpy();em=yy-ff;eb=yy-bb
            d=eb**2-em**2+(bb-ff)**2;n=len(d);center=d-d.mean()
            months=pd.PeriodIndex(a.forecast_origin,freq='M').asi8
            lrv=float(center@center/n)
            for j in range(1,int(h)+1):
                left=np.searchsorted(months,months-j);ok=(left<n)&(months[np.minimum(left,n-1)]==months-j)
                lrv+=2*(1-j/(h+1))*float(center[ok]@center[left[ok]])/n
            se=np.sqrt(lrv/n);cw=d.mean()/se;pcw=float(student.sf(cw,n-2))
            msfe=float(np.mean(em**2));bmsfe=float(np.mean(eb**2))
            COMPARISONS.append(dict(target=target,window=window,horizon=h,model=model,benchmark=benchmark,n=n,origin_start=a.forecast_origin.iloc[0],origin_end=a.forecast_origin.iloc[-1],first_growth_month=a.first_growth_month.iloc[0],last_target_end=a.target_end.iloc[-1],r2_os=100*(1-msfe/bmsfe),model_msfe=msfe,benchmark_msfe=bmsfe,rmsfe=np.sqrt(msfe),benchmark_rmsfe=np.sqrt(bmsfe),cw=cw,p_cw=pcw,stars=stars(pcw),cw_mean=float(d.mean()),cw_lrv=lrv,cw_se=se,cw_lag=h,cw_correction=1,cw_df=n-2,status='OK'))
            save(pd.DataFrame(dict(forecast_origin=a.forecast_origin,model_error=em,benchmark_error=eb,model_forecast=ff,benchmark_forecast=bb,actual=yy,cw_adjustment=(bb-ff)**2,cw_d=d,cw_centered=center)),R/'cw'/f'{target}_{window}_{h}_{model}_vs_{benchmark}.csv')
    save(fc,R/'oos_forecasts.csv')
    save(pd.DataFrame(TRAINING),R/'oos_training_ledger.csv')
    save(pd.concat(MEMBERS,ignore_index=True),R/'oos_training_membership.csv.gz')
    save(pd.DataFrame(COMPARISONS),R/'oos_comparisons.csv')


def main():
    for name in ['bootstrap','cw']:(R/name).mkdir(parents=True,exist_ok=True)
    started=time.time();p=read_panel()
    rr=returns_is(p);cc=cash_is(p)
    for h,g in rr.items():recursive(g,p,'return','return',h)
    for (window,h),g in cc.items():recursive(g,p,'D12',window,h)
    compare_forecasts()
    results=pd.DataFrame(ROWS)
    inc=[]
    for (target,window,h),g in results.query("target!='return' and window!='annual'").groupby(['target','window','horizon']):
        joint=g[g.model=='JOINT'].iloc[0];past=g[g.model=='PAST'].iloc[0]
        inc.append(dict(target=target,window=window,horizon=h,n=joint.n,r2_joint=joint.r2,r2_past=past.r2,incremental_r2_pp=joint.r2-past.r2))
    save(results,R/'is_results.csv');save(pd.DataFrame(inc),R/'incremental_r2.csv')
    save(pd.concat(SAMPLES,ignore_index=True),R/'regression_samples.csv')
    save(pd.concat(TARGETS,ignore_index=True),R/'target_ledger.csv')
    save(pd.DataFrame(BOOT),R/'bootstrap_inference.csv')
    np.savez_compressed(R/'ols_hac_objects.npz',**OBJECTS)
    write_json(dict(status='FROZEN',experiment='E022',regressions=len(SAMPLES),coefficients=len(results),bootstrap_tests=len(BOOT),oos_predictions=len(FORECASTS),oos_comparisons=len(COMPARISONS),failed_regressions=0,elapsed_seconds=time.time()-started),R/'freeze.json')
    print('FROZEN',time.time()-started,'seconds',flush=True)

if __name__=='__main__':main()
