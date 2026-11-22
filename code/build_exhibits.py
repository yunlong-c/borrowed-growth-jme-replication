"""Build the current manuscript's empirical cells from computed results only."""
from pathlib import Path
import json,re,shutil
import pandas as pd
from table_values import bindings,ROOT

NUMBER=re.compile(r'^(\s*)(\(?)(-?\d+(?:\.\d+)?)(\\sym\{\*+\})?(\)?)(\s*)(?=\\\\|$)')
def stars(p):
    return '' if p is None or pd.isna(p) else '***' if p<.01 else '**' if p<.05 else '*' if p<.1 else ''
def render(source,values):
    label=None;counts={k:0 for k in values};audit=[];lines=[]
    for lineno,line in enumerate(source.splitlines(True),1):
        m=re.search(r'\\label\{(tab:[^}]+)\}',line)
        if m:label=m[1]
        parts=line.split('&');matches=[(j,NUMBER.match(part)) for j,part in enumerate(parts) if j>0]
        matches=[(j,m) for j,m in matches if m]
        if label in values and matches:
            row=counts[label];cells=values[label][row]
            assert len(cells)==len(matches),(label,row,len(cells),len(matches),line)
            for (j,m),c in zip(matches,cells):
                old=m[3]+(m[4] or '')
                decimals=len(m[3].split('.')[1]) if '.' in m[3] else 0
                value=c['value'];value=0 if abs(value)<.5*10**(-decimals) else value
                display=f'{value:.{decimals}f}'
                st=stars(c['probability'])
                if st:display+=r'\sym{'+st+'}'
                parts[j]=m[1]+m[2]+display+m[5]+m[6]+parts[j][m.end():]
                audit.append(dict(table=label,row=row,column=j,line=lineno,**c,display=display,template_display=old,decimals=decimals))
            counts[label]+=1
        lines.append('&'.join(parts))
        if r'\end{table}' in line:label=None
    assert counts=={k:len(v) for k,v in values.items()},counts
    return ''.join(lines),audit
def main():
    values=bindings();audits=[]
    for label,rows in values.items():
        path=ROOT/'layouts'/f'{label.replace(":", "_")}.tex'
        source=path.read_text(encoding='utf-8')
        text,audit=render(source,{label:rows})
        for cell in audit:
            cell.pop('template_display',None)
        audits.extend(audit)
        (ROOT/'output/tables'/path.name).write_text(text,encoding='utf-8')
    frame=pd.DataFrame(audits)
    frame['key']=frame.key.map(lambda k:json.dumps(k,sort_keys=True))
    frame.to_csv(ROOT/'output/numerical/display_cells.csv',index=False,float_format='%.17g')
    for table,d in frame.groupby('table',sort=False):
        d.to_csv(ROOT/'output/numerical'/f'{table.replace(":","_")}.csv',index=False,float_format='%.17g')
    print(json.dumps(dict(status='BUILT',tables=len(values),cells=len(frame),estimator_called=False)))
if __name__=='__main__':main()
