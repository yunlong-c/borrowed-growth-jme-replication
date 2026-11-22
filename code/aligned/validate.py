"""Read-only reconstruction of E022 identities. JSON is written by shell redirection."""
from config import *
from scipy.stats import t as student
from pandas.testing import assert_frame_equal
CHECKS=[]

def check(name,reason,action,operation):
    operation()
    CHECKS.append(dict(check=name,status='PASS',failure_detected=reason,action_if_failed=action))

def close(a,b,label='',atol=1e-9):
    if not np.allclose(a,b,rtol=2e-9,atol=atol,equal_nan=True):
        raise AssertionError(label+' numerical mismatch')

def independent_ols(y,x,dates,lag):
    n,k=x.shape
    beta=np.linalg.lstsq(x,y,rcond=None)[0];u=y-x@beta
    scores=x*u[:,None];meat=scores.T@scores
    for l in range(1,lag+1):
        lookup={d:i for i,d in enumerate(dates)}
        pairs=[(i,lookup[d-l]) for i,d in enumerate(dates) if d-l in lookup]
        if pairs:
            right,left=np.array(pairs).T
            a=scores[right].T@scores[left]
            meat+=(1-l/(lag+1))*(a+a.T)
    bread=np.linalg.inv(x.T@x);cov=bread@meat@bread*n/(n-k)
    se=np.sqrt(np.diag(cov));r2=100*(1-u@u/np.sum((y-y.mean())**2))
    return beta,se,beta/se,r2,cov

def main():
    p=read_panel();rs=pd.read_csv(R/'is_results.csv');ss=pd.read_csv(R/'regression_samples.csv');tl=pd.read_csv(R/'target_ledger.csv')
    bi=pd.read_csv(R/'bootstrap_inference.csv');fixed=pd.read_csv(I/'fixed_scale.csv').iloc[0]
    objects=np.load(R/'ols_hac_objects.npz');fc=pd.read_csv(R/'oos_forecasts.csv');tr=pd.read_csv(R/'oos_training_ledger.csv')
    members=pd.read_csv(R/'oos_training_membership.csv.gz');comp=pd.read_csv(R/'oos_comparisons.csv')

    def sources():
        gw=pd.read_excel(WB,sheet_name='Monthly',usecols=['yyyymm','CRSP_SPvw','Rfree','D12','E12'])
        gw.index=pd.PeriodIndex(pd.to_datetime(gw.pop('yyyymm').astype(str),format='%Y%m'),freq='M')
        ee=pd.read_excel(EE,sheet_name='Data',usecols=['year','month','FMP_SA_3MA']);ee=ee[ee.year.notna()&ee.month.notna()]
        ee.index=pd.PeriodIndex(ee.year.astype(int).astype(str)+'-'+ee.month.astype(int).astype(str).str.zfill(2),freq='M')
        assert not gw.index.duplicated().any() and not ee.index.duplicated().any()
        close(p[['CRSP_SPvw','Rfree','D12','E12']],gw.reindex(p.index)[['CRSP_SPvw','Rfree','D12','E12']],'GW source values')
        close(p.published_SA3MA,ee.FMP_SA_3MA.reindex(p.index),'Published SA3MA')
        close(p.x,p.published_SA3MA.shift(1),'EE previous month')
        close(p.r_excess,np.log1p(p.CRSP_SPvw)-np.log1p(p.Rfree),'Excess log return')
        x=p.loc['1996-01':'2025-12','x'].dropna()
        close([fixed['mean'],fixed.sd],[x.mean(),x.std(ddof=1)],'Fixed scale')
        assert fixed.n==360 and fixed.ddof==1
        close(p.EE,(p.x-fixed['mean'])/fixed.sd,'Standardized predictor')
    check('source_columns_units_and_no_resmoothing','Wrong source column, scaling or repeated smoothing','Correct input preparation before estimating a new result vintage',sources)

    def targets():
        for (target,window,h),g in tl.groupby(['target','window','horizon'],sort=False):
            ix=pd.PeriodIndex(g.origin,freq='M');end=pd.PeriodIndex(g.target_end,freq='M')
            offset=h-12 if window=='annual' else 12 if window=='post' else 0
            assert np.all(ix>=pd.Period('1996-01',freq='M')) and np.all(end<=pd.Period('2025-12',freq='M'))
            assert np.all(end==ix+h)
            assert np.all(pd.PeriodIndex(g.ee_source_month,freq='M')==ix-1)
            assert np.all(pd.PeriodIndex(g.growth_base_month,freq='M')==ix+offset)
            assert np.all(pd.PeriodIndex(g.first_growth_month,freq='M')==ix+offset+1)
            close(g.x_raw,p.published_SA3MA.reindex(ix-1),'EE source dates')
            if target=='return':
                y=sum(p.r_excess.reindex(ix+j).to_numpy() for j in range(1,h+1))*100/h
            else:
                y=100*np.log(p[target].reindex(ix+h).to_numpy()/p[target].reindex(ix+offset).to_numpy())
                past=100*np.log(p[target].reindex(ix).to_numpy()/p[target].reindex(ix-12).to_numpy())
                close(g.past_growth,past,'Original pp past growth')
            close(g.y,y,'Target endpoints and units')
    check('target_ledger_and_EE_source_month','Shifted EE dates, wrong growth bases or incomplete targets','Repair target construction and rerun affected estimates in a new output directory',targets)

    def common():
        for key,g in ss.query("target!='return' and window!='annual'").groupby(['target','window','horizon']):
            lists=[a.origin.tolist() for _,a in g.groupby('model')]
            assert all(lists[0]==z for z in lists)
        for target,g in ss.query("window=='annual'").groupby('target'):
            lists=[a.origin.tolist() for _,a in g.groupby(['horizon','model'])]
            assert all(lists[0]==z for z in lists)
            assert len(lists[0])==300
        inc=pd.read_csv(R/'incremental_r2.csv')
        for _,q in inc.iterrows():
            v=rs.query('target==@q.target and window==@q.window and horizon==@q.horizon')
            close(q.incremental_r2_pp,v.query("model=='JOINT'").r2.iloc[0]-v.query("model=='PAST'").r2.iloc[0])
    check('common_control_and_five_year_samples','Unequal origins change model or year comparisons','Use the registered common sample for the affected comparison',common)

    def regressions():
        for rid,g in ss.groupby('regression_id',sort=False):
            row=rs[rs.regression_id==rid];model=row.model.iloc[0];x=g[TERMS[model]].to_numpy();y=g.y.to_numpy()
            b,se,tt,r2,cov=independent_ols(y,x,g.ordinal.to_numpy(),int(row.lag.iloc[0]))
            close(row.beta,b,rid);close(row.se_nw,se,rid);close(row.t_nw,tt,rid);close(row.r2,r2,rid)
            close(objects[rid+'__cov'],cov,rid+' covariance')
            close(objects[rid+'__beta'],b);close(objects[rid+'__se'],se)
            close(g.fitted,x@b);close(g.residual,y-x@b)
            close(row.p_nw_student,2*student.sf(abs(tt),len(g)-len(TERMS[model])))
        rr=rs.query("target=='return'")
        close(rr.beta_cumulative,rr.horizon*rr.beta,'Cumulative beta')
        close(rr.se_cumulative,rr.horizon*rr.se_nw,'Cumulative SE')
        for _,q in rs.query("term!='const'").iterrows():
            assert (q.stars if isinstance(q.stars,str) else '')==stars(q.p_formal)
    check('OLS_calendar_HAC_and_unit_identities','Coefficient, HAC, degrees of freedom or horizon scaling error','Correct only the identified numerical component before refreezing results',regressions)

    def bootstrap():
        rng=np.random.RandomState(20261006)
        for target in ['D12','E12']:
            for h in HRET:
                g=ss.query("target==@target and window=='cumulative' and horizon==@h and model=='JOINT'")
                n=len(g);a=np.load(R/'bootstrap'/f'{target}_cumulative_{h}.npz')
                starts=rng.randint(0,n-12+1,size=(20000,(n+11)//12))
                assert np.array_equal(a['block_starts'],starts)
                assert starts.min()>=0 and starts.max()<=n-12
                for model in ['EE','PAST','JOINT']:
                    rid=f'{target}_cumulative_{h}_{model}'
                    original=rs[rs.regression_id==rid]
                    close(a[model+'_t_centered'],(a[model+'_beta']-original.beta.to_numpy())/a[model+'_se'])
                    for draw in [0,9999,19999]:
                        take=(starts[draw,:,None]+np.arange(12)).reshape(-1)[:n]
                        bb,se,tt,_,_=independent_ols(g.y.to_numpy()[take],g[TERMS[model]].to_numpy()[take],np.arange(n),12)
                        close(a[model+'_beta'][draw],bb);close(a[model+'_se'][draw],se)
                    for j,term in enumerate(TERMS[model][1:],1):
                        q=bi.query('regression_id==@rid and term==@term').iloc[0]
                        td=a[model+'_t_centered'][:,j]
                        assert np.all(np.isfinite(td))
                        count=np.count_nonzero(abs(td)>=abs(q.observed_t))
                        assert count==q.extreme_count and q.replications==20000
                        close(q.p_formal,(count+1)/20001)
        innovations=np.load(FROZEN/'reconstructed_monthly_innovations.npz')['innovations']
        sink=pd.read_csv(I/'frozen_return_bootstrap_sink.csv')
        assert innovations.shape==(10000,361)
        close(innovations[0],np.random.RandomState(20260925).standard_normal(361)*sink.residual.to_numpy())
        cal=pd.PeriodIndex(sink.return_month,freq='M')
        for h in HRET:
            rid=f'return_return_{h}_EE';g=ss[ss.regression_id==rid];a=np.load(R/'bootstrap'/f'{rid}.npz')
            take=cal.get_indexer(pd.PeriodIndex(g.first_growth_month,freq='M'))
            assert np.array_equal(take,a['innovation_first_columns'])
            for draw in [0,4999,9999]:
                yy=g.y.mean()+np.array([100*innovations[draw,j:j+h].mean() for j in take])
                _,_,tt,_,_=independent_ols(yy,g[['const','EE']].to_numpy(),g.ordinal.to_numpy(),h)
                close(a['t_draws'][draw],tt[1])
            q=bi[bi.regression_id==rid].iloc[0]
            count=np.count_nonzero(abs(a['t_draws'])>=abs(q.observed_t))
            assert q.extreme_count==count and q.replications==10000
            close(q.p_formal,(count+1)/10001)
        for _,q in bi.iterrows():
            row=rs.query('regression_id==@q.regression_id and term==@q.term').iloc[0]
            close(row.p_formal,q.p_formal)
            assert q.failed_draws==0
    check('bootstrap_saved_draws_seed_counts_and_probabilities','Wrong innovations, block pairing, centering, studentization or tail probabilities','Correct bootstrap generation or date mask without changing registered inference',bootstrap)

    def oos():
        assert np.all(pd.PeriodIndex(members.target_end,freq='M')<=pd.PeriodIndex(members.forecast_origin,freq='M'))
        assert np.all(pd.PeriodIndex(fc.ee_source_month,freq='M')==pd.PeriodIndex(fc.forecast_origin,freq='M')-1)
        assert np.all(pd.PeriodIndex(fc.target_end,freq='M')<=pd.Period('2025-12',freq='M'))
        assert (fc.forecast_origin.min()=='2009-12')
        groups={key:a for key,a in members.groupby('training_id',sort=False)}
        for _,q in tr.iterrows():
            a=groups[q.training_id];mu=a.x_raw.mean();sd=a.x_raw.std(ddof=1)
            assert len(a)==q.n_train and a.target_end.max()==q.max_training_target_end
            assert a.origin.iloc[0]==q.training_origin_start and a.origin.iloc[-1]==q.training_origin_end
            eligible=tl.query('target==@q.target and window==@q.window and horizon==@q.horizon and target_end<=@q.forecast_origin')
            assert a.origin.tolist()==eligible.origin.tolist()
            close([mu,sd],[q.mean_x,q.sd_x])
            now=p.loc[q.forecast_origin]
            close(q.x_raw,now.x);close(q.x_z,(now.x-mu)/sd)
            xx=np.ones((len(a),len(TERMS[q.model])));xt=[1.]
            for j,term in enumerate(TERMS[q.model][1:],1):
                xx[:,j]=(a.x_raw-mu)/sd if term=='EE' else a.past_growth
                xt.append(q.x_z if term=='EE' else q.past_growth)
            beta=np.linalg.lstsq(xx,a.y.to_numpy(),rcond=None)[0]
            if q.model=='HA' and q.target=='return':
                history=p.loc['1995-12':q.forecast_origin,'r_excess']
                assert q.ha_n==len(history) and q.ha_history_end==q.forecast_origin
                predicted=100*history.mean()
            else:
                predicted=np.array(xt)@beta
                close(q.intercept,beta[0])
                if q.model in ['EE','JOINT']:close(q.beta_EE,beta[1])
                if q.model in ['PAST','JOINT']:close(q.beta_past,beta[-1])
            forecast=fc.query('training_id==@q.training_id and model==@q.model').iloc[0]
            close(predicted,forecast.forecast)
            close(forecast.error,forecast.actual-forecast.forecast)
        for _,q in comp.iterrows():
            a=fc.query('target==@q.target and window==@q.window and horizon==@q.horizon and model==@q.model').sort_values('forecast_origin')
            b=fc.query('target==@q.target and window==@q.window and horizon==@q.horizon and model==@q.benchmark').sort_values('forecast_origin')
            assert a.forecast_origin.tolist()==b.forecast_origin.tolist()
            y=a.actual.to_numpy();fa=a.forecast.to_numpy();fb=b.forecast.to_numpy();ea=y-fa;eb=y-fb;n=len(y)
            d=eb**2-ea**2+(fb-fa)**2;u=d-d.mean();dates=pd.PeriodIndex(a.forecast_origin,freq='M').asi8
            kernel=np.maximum(1-np.abs(dates[:,None]-dates[None,:])/(q.horizon+1),0)
            lrv=float(u@kernel@u/n);cw=d.mean()/np.sqrt(lrv/n)
            close([q.cw,q.cw_lrv,q.cw_se],[cw,lrv,np.sqrt(lrv/n)])
            close(q.p_cw,student.sf(cw,n-2));assert q.n==n
            close([q.model_msfe,q.benchmark_msfe,q.rmsfe,q.r2_os],[np.mean(ea**2),np.mean(eb**2),np.sqrt(np.mean(ea**2)),100*(1-np.sum(ea**2)/np.sum(eb**2))])
            ledger=pd.read_csv(R/'cw'/f'{q.target}_{q.window}_{q.horizon}_{q.model}_vs_{q.benchmark}.csv')
            close(ledger.cw_d,d);close(ledger.cw_centered,u)
            assert (q.stars if isinstance(q.stars,str) else '')==stars(q.p_cw)
    check('OOS_maturity_scales_HA_forecasts_R2_CW','Unmatured training target, look-ahead scale, wrong HA or forecast comparison','Repair the affected forecast or comparison component and refreeze it',oos)

    print(json.dumps(dict(status='PASS',experiment='E022',checks=CHECKS,regressions=ss.regression_id.nunique(),bootstrap_tests=len(bi),oos_predictions=len(fc),oos_comparisons=len(comp)),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
