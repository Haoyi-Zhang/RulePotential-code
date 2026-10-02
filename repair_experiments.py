#!/usr/bin/env python3
"""One-worker, bounded offline evidence for fixed-proof minimum-offset repair.

Examples:
  python repair_tests.py -v
  python repair_experiments.py --out results/offset-repair.json
  python repair_experiments.py --out fresh.json --compare results/offset-repair.json
Published files are never overwritten. No external solver or data is used.
"""
import argparse
import itertools
import json
import resource
import sys
import time
from pathlib import Path
from run_environment import capture_environment
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from offset_repair import optimal_offsets
from optimality_check import check_optimality
from producer import Program, full, dred, certificate
from checker import Session
from reference_check import verify_all


def exact_cases():
    pairs=[(i,j) for i in range(3) for j in range(3) if i!=j]
    oldlist=list(itertools.product(range(-1,2), repeat=3))
    candidates=list(itertools.product(range(-3,4), repeat=3))
    counts={'graphs':0,'graph_target_pairs':0,'feasible_graphs':0,'feasible_pairs':0,
            'infeasible_pairs':0,'oracle_mismatches':0,'certificate_failures':0,
            'optimum_histogram':{str(i):0 for i in range(4)}}
    for weights in itertools.product([None,-1,0,1],repeat=6):
        es=[(i,j,w) for (i,j),w in zip(pairs,weights) if w is not None]
        # Deliberately independent: raw constraints evaluated on all 7^3 vectors.
        feasible=[v for v in candidates if all(v[j]-v[i]>=w for i,j,w in es)]
        counts['graphs']+=1;counts['feasible_graphs']+=bool(feasible)
        for old_tuple in oldlist:
            old=list(old_tuple);counts['graph_target_pairs']+=1
            try: answer=optimal_offsets(3,es,old)
            except ValueError:
                if feasible:raise AssertionError(('false infeasibility',es,old))
                counts['infeasible_pairs']+=1;continue
            if not feasible:raise AssertionError(('false feasibility',es,old))
            exact=min(sum(a!=b for a,b in zip(old,v)) for v in feasible)
            if answer['changed_fields']!=exact:raise AssertionError(('wrong optimum',es,old,answer,exact))
            if not check_optimality(3,es,old,answer['offsets'],answer['certificate']):
                raise AssertionError(('rejected producer certificate',es,old,answer))
            counts['feasible_pairs']+=1;counts['optimum_histogram'][str(exact)]+=1
    return counts


def workload(family,n):
    if family=='fanout':
        rules=[{'head':1,'body':[0]}]+[{'head':j,'body':[1]} for j in range(2,n)]
        local=[1,1]+[2]*(n-2);base={0,1};removed={1}
    elif family=='tree':
        # A full binary conjunction tree stays within the original width-16 guard.
        height=(n+1).bit_length()-2
        rules=[{'head':i,'body':[2*i+1,2*i+2]} for i in range(n//2)]
        local=[height-((i+1).bit_length()-1) for i in range(n)]
        local[0]-=1
        base=set(range(n//2,n))|{0};removed={0}
    elif family=='ordered':
        rules=[{'head':j,'body':[j-1]} for j in range(1,n)]
        local=[0]*n;base=set(range(n));removed=set(range(1,n))
    else:raise ValueError('unknown workload')
    return {'n':n,'rules':rules,'blocks':list(range(n)),'local':local},base,removed


def selected_edges(raw,model,witness):
    # Read the complete supplied proof, not the optimizer's graph or distances.
    weights={}
    for h in sorted(model):
        r=witness[h]
        if r==-1:continue
        rule=raw['rules'][r]
        if rule['head']!=h or not set(rule['body'])<=model:raise ValueError('bad selected proof')
        for b in rule['body']:
            i,j=raw['blocks'][b],raw['blocks'][h]
            w=raw['local'][b]-raw['local'][h]+1
            weights[i,j]=max(weights.get((i,j),w),w)
    return [(i,j,w) for (i,j),w in sorted(weights.items())]


def timed(f,*args,**kw):
    start=time.perf_counter_ns();ans=f(*args,**kw)
    return ans,(time.perf_counter_ns()-start)/1e9


def workload_cases():
    rows=[]
    for family in ('fanout','tree','ordered'):
        for n in (3,7,15,31,63,127):
            raw,base,removed=workload(family,n);pg=Program(raw)
            model,witness,_=full(pg,base);old=[0]*n
            session=Session(raw,sorted(base),sorted(model),{str(h):r for h,r in witness.items()},old)
            nm,nw,_=dred(pg,model,witness,base,removed,set());es=selected_edges(raw,nm,nw)
            for repetition in range(-1,7):
                (monotone,info),baseline_time=timed(certificate,pg,model,witness,old,nm,nw)
                if monotone is None:raise AssertionError(info)
                ans,opt_time=timed(optimal_offsets,n,es,old)
                packet={**monotone,'offset':{str(i):v for i,v in enumerate(ans['offsets']) if v!=old[i]}}
                vc,proof_time=timed(check_optimality,n,es,old,ans['offsets'],ans['certificate'])
                if not vc:raise AssertionError('bad optimality proof')
                verdict,check_time=timed(session.check,sorted(removed),[],packet,commit=False)
                if not verdict.accepted:raise AssertionError(verdict.reason)
                baseline_verdict=session.check(sorted(removed),[],monotone,commit=False)
                if not baseline_verdict.accepted:raise AssertionError('baseline packet invalid')
                if not verify_all(raw,base-removed,nm,nw,ans['offsets'])[0]:raise AssertionError('full check failed')
                if repetition<0:continue
                encode=lambda x:len(json.dumps(x,sort_keys=True,separators=(',',':')).encode())
                rows.append({'family':family,'blocks':n,'repetition':repetition,
                             'base_deletions':len(removed),'truth_edits':len(monotone['delete'])+len(monotone['insert']),
                             'witness_edits':len(monotone['witness']),
                             'monotone_offset_fields':len(monotone['offset']),
                             'optimal_offset_fields':ans['changed_fields'],
                             'monotone_packet_bytes':encode(monotone),'optimal_packet_bytes':encode(packet),
                             'optimality_certificate_bytes':encode(ans['certificate']),
                             'monotone_synthesis_seconds':baseline_time,'optimal_synthesis_seconds':opt_time,
                             'optimality_check_seconds':proof_time,'local_check_seconds':check_time,
                             'accepted':True})
    return rows


def deterministic(value):
    if isinstance(value,dict):
        return {k:deterministic(v) for k,v in value.items() if not k.endswith('_seconds') and k not in ('peak_rss_kib','environment')}
    if isinstance(value,list):return [deterministic(v) for v in value]
    return value


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--compare',type=Path)
    args=p.parse_args()
    if args.out.exists():raise SystemExit('output exists; select a new path')
    resource.setrlimit(resource.RLIMIT_CPU,(35,35))
    resource.setrlimit(resource.RLIMIT_AS,(3500000000,3500000000))
    environment=capture_environment()
    t=time.process_time();wall=time.monotonic()
    data={'scope':'fixed-proof unbounded-integer minimum offset fields; no witness or partition optimization',
          'environment':environment,
          'oracle':exact_cases(),'workload_rows':workload_cases(),
          'warmups_per_setting':1,'repetitions_per_setting':7}
    data.update(cpu_seconds=time.process_time()-t,wall_seconds=time.monotonic()-wall,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if args.compare and deterministic(data)!=deterministic(json.loads(args.compare.read_text())):
        raise AssertionError('deterministic reproduction mismatch')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
    print(json.dumps({**data['oracle'],'workload_rows':len(data['workload_rows']),
                      'cpu_seconds':data['cpu_seconds'],'peak_rss_kib':data['peak_rss_kib'],
                      'deterministic_comparison':'matched' if args.compare else 'not requested'},indent=2))

if __name__=='__main__':main()
