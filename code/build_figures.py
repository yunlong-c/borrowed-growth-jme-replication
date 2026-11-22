"""Presentation only: read computed empirical results, write LaTeX, CSV and figures."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.dates import YearLocator, DateFormatter

HERE = Path(__file__).resolve().parents[1]
RES = HERE / 'results'
FIG = HERE / 'output/figures'
NUM = HERE / 'output/numerical'
NUM.mkdir(parents=True, exist_ok=True)
HS = [1,3,6,12]
LAB = ['PAYROLL','UNEMP','LFPR','JPR_PRIVATE_LONG','LMT_VU_LONG','HIRES_PRIVATE_LONG','QUITS_PRIVATE_LONG','LIG_JW','CLAIMS_INTENSITY']
GW = ['DP','DY','EP','DE','BM','NTIS','TBL','LTY','TMS','DFY','LTR','DFR','SVAR','INFL']

def read(name): return pd.read_csv(RES/name,low_memory=False)


def one(df, **kw):
    for k,v in kw.items(): df=df[df[k]==v]
    if len(df)!=1: raise ValueError((kw,len(df)))
    return df.iloc[0]


def save(df,name): df.to_csv(NUM/name,index=False)


def shade(ax,df,date):
    active=False;start=None
    for dt,rec in zip(date,df.USREC.fillna(0)):
        if rec and not active:start=dt;active=True
        if not rec and active:ax.axvspan(start,dt,color='#c9dce9',alpha=.6,lw=0);active=False
    if active:ax.axvspan(start,date.iloc[-1],color='#c9dce9',alpha=.6,lw=0)


def endpoints(ax,date):
    first,last=date.iloc[0],date.iloc[-1]
    ticks=[first]+[pd.Timestamp(year=y,month=1,day=1) for y in range((first.year//5+1)*5,last.year,5)]+[last]
    ax.set_xticks(ticks);ax.set_xticklabels([str(x.year) for x in ticks]);ax.set_xlim(first,last)


def figures():
    # Match the original full-manuscript figure fonts, framed axes and fine rules.
    rc={'font.family':'serif','font.serif':['Times New Roman','STIXGeneral'],
        'mathtext.fontset':'stix','font.size':10,'axes.titlesize':11,
        'axes.labelsize':10,'axes.edgecolor':'#666666','axes.linewidth':.65,
        'xtick.direction':'in','ytick.direction':'in','xtick.top':True,
        'ytick.right':True,'pdf.fonttype':42}
    blue,gray='#07086D','#9399A3'
    def framed(ax):
        ax.grid(axis='y',color='#E5E5E5',lw=.45)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=9,direction='in',top=True,right=True,width=.65)
        for spine in ax.spines.values(): spine.set_visible(True)
    def export(fig,name):
        fig.savefig(FIG/f'{name}.pdf')
        fig.savefig(FIG/f'{name}.png',dpi=300)
        plt.close(fig)
    with plt.rc_context(rc):
        a,b=read('data_figure_monthly.csv'),read('data_figure_quarterly.csv')
        fig,axs=plt.subplots(2,1,figsize=(6.5,5.25))
        dt=pd.to_datetime(a.date)
        axs[0].plot(dt,a.EE_percent,color=blue,lw=1.35)
        shade(axs[0],a,dt);framed(axs[0]);endpoints(axs[0],dt)
        axs[0].set_title('Panel A. Employer-to-employer mobility',pad=8)
        axs[0].set_ylabel('EE (%)')
        dt=pd.to_datetime(b.plot_date);right=axs[1].twinx()
        line1=axs[1].plot(dt,b.EE_z,color=blue,lw=1.35,label='EE (left)')[0]
        line2=right.plot(dt,b.LEHD_EEHireR_z,color=gray,lw=1.15,ls='--',label='LEHD (right)')[0]
        shade(axs[1],b,dt);framed(axs[1]);endpoints(axs[1],dt)
        right.tick_params(labelsize=9,direction='in',width=.65)
        axs[1].set_title('Panel B. Employer transitions',pad=27)
        axs[1].set_ylabel('EE (standard deviations)')
        right.set_ylabel('LEHD (standard deviations)',fontsize=10)
        axs[1].set_ylim(-3.2,4.2);right.set_ylim(-3.2,4.2)
        axs[1].set_yticks([-2,0,2,4]);right.set_yticks([-2,0,2,4])
        axs[1].set_xlabel('Year')
        axs[1].legend([line1,line2],['EE (left)','LEHD (right)'],frameon=False,
            fontsize=9,ncol=2,loc='lower center',bbox_to_anchor=(.5,1.0),
            borderaxespad=.2,handlelength=2,handletextpad=.45,columnspacing=1.2)
        fig.subplots_adjust(left=.105,right=.885,bottom=.095,top=.93,hspace=.5)
        export(fig,'figure_1')
        f=read('return_forecasts.csv');o=read('return_oos.csv')
        monthly=read('data_figure_monthly.csv')[['date','USREC']].assign(date=lambda x:pd.to_datetime(x.date))
        fig,axs=plt.subplots(2,2,figsize=(6.5,5.5));audit=[]
        for i,(h,ax) in enumerate(zip(HS,axs.ravel())):
            sub=f[f.model.eq('E2E')&f.horizon.eq(h)&f.target_type.eq('log')&f.status.eq('OK')].sort_values('target_end').copy()
            if sub.forecast_origin.duplicated().any() or sub.target_end.duplicated().any():
                raise ValueError(f'Figure 2 has duplicate log forecast dates, h={h}')
            dt=pd.to_datetime(sub.target_end)
            if not ((pd.PeriodIndex(sub.forecast_origin,freq='M')+h).astype(str)==sub.target_end.to_numpy()).all():
                raise ValueError(f'Figure 2 completion dates differ from log target windows, h={h}')
            loss=((sub.actual-sub.benchmark)**2-(sub.actual-sub.forecast)**2)*10000
            benchmark_sse=float(((sub.actual-sub.benchmark)**2).sum())
            model_sse=float(((sub.actual-sub.forecast)**2).sum())
            r2=100*(1-model_sse/benchmark_sse);z=one(o,model='E2E',horizon=h)
            if len(sub)!=int(z.n) or not np.isclose(r2,z.r2_os,rtol=1e-12,atol=1e-12):
                raise ValueError(f'Figure 2 log records do not reconstruct Table 1 R2, h={h}')
            rec=pd.DataFrame({'date':dt}).merge(monthly,on='date',how='left',validate='one_to_one')
            shade(ax,rec,rec.date);ax.axhline(0,color='#707070',lw=.6)
            ax.plot(dt,loss.cumsum(),color=blue,lw=1.4)
            framed(ax);endpoints(ax,dt)
            ax.set_title(f'Panel {"ABCD"[i]}. {h}-month horizon',pad=8)
            ax.set_xlabel('Target completion year')
            ax.set_ylabel('Cumulative squared-error gain')
            ax.text(.045,.96,rf'$R^2_{{OS}}={r2:.2f}\%$',transform=ax.transAxes,
                va='top',ha='left',fontsize=9,color='#333333')
            save(pd.DataFrame({'forecast_origin':sub.forecast_origin,'target_start':sub.target_start,
                'target_end':sub.target_end,'target_type':'log','loss_gain_pp2':loss,
                'cumulative_gain_pp2':loss.cumsum()}),f'figure_2_h{h}.csv')
            audit.append(dict(horizon=h,target_type='log',n=len(sub),
                target_start=sub.target_start.min(),target_end=sub.target_end.max(),
                cumulative_gain_pp2=float(loss.sum()),r2_os_reconstructed=r2,
                r2_os_table=float(z.r2_os),status='PASS'))
        fig.subplots_adjust(left=.105,right=.95,bottom=.095,top=.94,wspace=.34,hspace=.4)
        export(fig,'figure_2')
        save(pd.DataFrame(audit),'figure_2_source_check.csv')


def wage_figure():
    a=read('data_figure_wages.csv');dt=pd.to_datetime(a.plot_date)
    rc={'font.family':'serif','font.serif':['Times New Roman','STIXGeneral'],'mathtext.fontset':'stix','font.size':10,'axes.labelsize':10,'axes.edgecolor':'#666666','axes.linewidth':.65,'xtick.direction':'in','ytick.direction':'in','pdf.fonttype':42}
    with plt.rc_context(rc):
        fig,ax=plt.subplots(figsize=(6.5,3.5))
        right=ax.twinx()
        lines=[]
        for axis,col,color,ls,lab in [(ax,'EE_z','#07086D','-','EE (left)'),(right,'WGT_SWITCHER_z','#9399A3','--','Switchers (right)'),(right,'WGT_STAYER_z','#4656A6','-.','Stayers (right)')]:
            lines.append(axis.plot(dt,a[col],color=color,ls=ls,lw=1.25,label=lab)[0])
        flag=a.USREC.eq(1).to_numpy();begin=None
        for i,on in enumerate(flag):
            if on and begin is None:begin=i
            if begin is not None and (not on or i==len(flag)-1):
                end=dt.iloc[i] if not on else dt.iloc[i]+pd.offsets.MonthBegin(1)
                ax.axvspan(dt.iloc[begin],end,color='#DCEAF2',alpha=.65,lw=0,zorder=0);begin=None
        ax.set_axisbelow(True);ax.grid(axis='y',color='#E5E5E5',lw=.45)
        ax.set_xlim(dt.iloc[0],dt.iloc[-1])
        for axis in [ax,right]:
            axis.set_ylim(-2.5,3.5);axis.set_yticks(range(-2,4))
        years=[1997,2000,2005,2010,2015,2020,2025]
        ax.set_xticks([dt.iloc[0],*[pd.Timestamp(y,1,1) for y in years[1:-1]],dt.iloc[-1]],labels=[str(y) for y in years])
        ax.tick_params(labelsize=9,direction='in',top=True,right=True,width=.65)
        right.tick_params(labelsize=9,direction='in',width=.65)
        ax.set_xlabel('Year');ax.set_ylabel('EE (standard deviations)')
        right.set_ylabel('Wages (standard deviations)')
        ax.legend(lines,[line.get_label() for line in lines],frameon=False,ncol=3,fontsize=9,loc='lower center',bbox_to_anchor=(.5,1.02),handlelength=2.5,columnspacing=1.8)
        fig.subplots_adjust(left=.105,right=.885,bottom=.145,top=.85)
        fig.savefig(FIG/'figure_A1.pdf');fig.savefig(FIG/'figure_A1.png',dpi=300);plt.close(fig)

if __name__=="__main__":
    figures()
    wage_figure()
