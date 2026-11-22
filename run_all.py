"""Reproduce the current JME empirical tables and figures from recipient-supplied data."""
from pathlib import Path
import argparse, csv, json, os, subprocess, sys, time, platform, importlib.metadata
ROOT=Path(__file__).resolve().parent
MODULES={
    'data':['code/data_module.py'],
    'returns':['code/returns_module.py'],
    'channels':['code/channels_module.py'],
    'aligned':['code/aligned/prepare_inputs.py','code/aligned/estimate.py']}

def check_inputs(names):
    with (ROOT/'documentation/data_acquisition.csv').open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f))
    required=[r for r in rows if r['stage']=='data' or 'channels' in names]
    missing=[r for r in required if not (ROOT/r['path']).is_file()]
    if missing:
        print('Required external input files are missing. No estimation was started.',file=sys.stderr)
        for r in missing:
            print(f"  {r['path']}\n    Provider: {r['provider']}\n    Download: {r['url']}\n    Vintage: {r['vintage']}\n    Sheet: {r['sheet'] or '(CSV/HTML)'}; date: {r['date_fields']}; values: {r['value_fields']}",file=sys.stderr)
        print('Follow README.md and documentation/data_acquisition.csv. Obtain the recorded versions under provider terms; no inputs are downloaded automatically.',file=sys.stderr)
        return False
    return True

def run(script):
    start=time.perf_counter()
    name=script.removeprefix('code/').replace('/','_').replace('.py','')
    with (ROOT/'logs'/f'{name}.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen([sys.executable,str(ROOT/script)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'})
        for line in proc.stdout:
            print(line,end='',flush=True);log.write(line.replace(str(ROOT),'<PACKAGE>'))
        status=proc.wait()
    if status:raise RuntimeError(f'{script} failed; see logs/{name}.log')
    return dict(script=script,seconds=round(time.perf_counter()-start,3))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['all','estimate','presentation','validate'],default='all')
    parser.add_argument('--module',choices=list(MODULES))
    args=parser.parse_args()
    if args.module and args.stage in ['presentation','validate']:parser.error('--module applies to estimation only')
    names=list(MODULES)
    if args.module:names=names[:names.index(args.module)+1]
    if args.stage in ['all','estimate'] and not check_inputs(names):return 2
    if args.stage in ['presentation','validate'] and not (ROOT/'results/aligned/is_results.csv').is_file():
        parser.error('Computed results are missing. Obtain the inputs and run python run_all.py first.')
    for d in ['data/processed','results','output/numerical','output/tables','output/figures','logs','validation']:
        (ROOT/d).mkdir(parents=True,exist_ok=True)
    timings=[]
    if args.stage in ['all','estimate']:
        for name in names:
            for script in MODULES[name]:timings.append(run(script))
    if not args.module and args.stage in ['all','presentation']:
        for script in ['code/build_exhibits.py','code/build_figures.py']:timings.append(run(script))
    if not args.module and args.stage in ['all','validate']:
        for script in ['code/aligned/validate.py','code/validate_outputs.py']:timings.append(run(script))
    (ROOT/'logs/runtime.json').write_text(json.dumps(timings,indent=2),encoding='utf-8')
    packages={n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','matplotlib','openpyxl','pyarrow']}
    (ROOT/'logs/environment.json').write_text(json.dumps(dict(python=platform.python_version(),system=platform.platform(),packages=packages),indent=2),encoding='utf-8')
    print('Requested empirical replication stages completed.')
    return 0
if __name__=='__main__':sys.exit(main())
