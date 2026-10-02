#!/usr/bin/env python3
"""Offline, serial, resumable campaign with independent per-chunk watchdog.

Default results are written to a NEW results directory, never silently replacing
published measurements. Existing outputs require --resume and successful log
records. Use --quick for the unit suite and a small end-to-end timing sample.
"""
import argparse,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
from run_environment import ensure_environment_file
ROOT=Path(__file__).resolve().parent

def jobs(quick):
    yield 'units',['units']
    if quick:
        yield 'exchange-16',['timing','--family','exchange','--size','16'];return
    for i in range(0,512,64):yield f'correct-{i:03d}',['correct','--start',str(i),'--stop',str(i+64)]
    for i in range(0,64,8):yield f'candidate-{i:02d}',['candidate','--start',str(i),'--stop',str(i+8)]
    for i in range(0,64,16):yield f'representation-{i:02d}',['representation','--start',str(i),'--stop',str(i+16)]
    yield 'selection',['selection']
    for family in ['exchange','star','fanin']:
        for n in [16,64,256,1024,4096,16384]:
            yield f'{family}-{n}',['timing','--family',family,'--size',str(n)]
    for f in range(3):
        for h in [8,16,32]:yield f'policy-{f}-{h}',['policy','--fixture',str(f),'--size',str(h)]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('reproduced-results'))
    p.add_argument('--quick',action='store_true');p.add_argument('--resume',action='store_true')
    p.add_argument('--max-jobs',type=int);args=p.parse_args();out=args.out.resolve()
    if out.exists() and any(out.iterdir()) and not args.resume:raise SystemExit('nonempty output; use a new --out or explicit --resume')
    out.mkdir(parents=True,exist_ok=True);(out/'logs').mkdir(exist_ok=True)
    environment=ensure_environment_file(out/'environment.json')
    accounting=out/'execution.json';records=json.loads(accounting.read_text()) if accounting.exists() else []
    spent=sum(x.get('cpu_seconds',0) for x in records);done=0
    for key,tail in jobs(args.quick):
        target=out/(key+'.json')
        if args.resume and target.exists() and any(x['case']==key and x['returncode']==0 for x in records):continue
        if args.max_jobs is not None and done>=args.max_jobs:break
        if spent>=21600:raise SystemExit('campaign budget exhausted; remaining quarter is reserved')
        cmd=[sys.executable,str(ROOT/'campaign.py'),*tail,'--out',str(target)]
        env=dict(os.environ);env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONHASHSEED='0')
        before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic()
        proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        timeout=False
        try:stdout,stderr=proc.communicate(timeout=40)
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(proc.pid,signal.SIGKILL);stdout,stderr=proc.communicate()
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu=(after.ru_utime-before.ru_utime)+(after.ru_stime-before.ru_stime);spent+=cpu
        (out/'logs'/(key+'.stdout.txt')).write_bytes(stdout);(out/'logs'/(key+'.stderr.txt')).write_bytes(stderr)
        row={'case':key,'command':['python','campaign.py',*tail,'--out',target.name],
             'environment_file':'environment.json','environment_recording_status':environment['recording_status'],
             'returncode':proc.returncode,'timeout':timeout,'wall_seconds':time.monotonic()-start,
             'cpu_seconds':cpu,'cumulative_cpu_seconds':spent}
        records.append(row);accounting.write_text(json.dumps(records,indent=2)+'\n')
        print(key,proc.returncode,f'{cpu:.3f}s CPU',flush=True);done+=1
        if proc.returncode!=0 or timeout:raise SystemExit('stopped on failed chunk; evidence retained')
    print('Completed selected chunks; run summarize.py on the output after all full-campaign jobs finish.')

if __name__=='__main__':main()
