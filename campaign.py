#!/usr/bin/env python3
"""Bounded deterministic evidence chunks. Use reproduce.py for the full campaign."""
import argparse,copy,csv,itertools,json,resource,sys,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from checker import Session,strict_loads
from producer import Program,full,dred,potentials,certificate
from oracle import least_model
from cases import exchange,alternate_star,inactive_fanin,unary_program,all_subsets
from obstruction_check import check_obstruction
from reference_check import verify_all
from selection import maxatom_to_horn,horn_to_maxatom,satisfies,selected_witness,extend_values


def require(condition, detail='campaign invariant failed'):
    if not condition:
        raise RuntimeError(detail)


def initialize(raw,base):
    p=Program(raw);m,w,_=full(p,base);o,e=potentials(p,m,w)
    require(o is not None,e)
    return p,m,w,o,Session(raw,sorted(base),sorted(m),{str(h):v for h,v in w.items()},o)


def correct_updates(start,stop):
    total=0;counts={'deletions':0,'insertions':0,'mixed':0,'no_base_change':0}
    for mask in range(start,stop):
        raw=unary_program(3,mask); oracle={tuple(sorted(b)):least_model(raw,b) for b in all_subsets(3)}
        for b in all_subsets(3):
            p,m,w,o,s=initialize(raw,b)
            require(m==oracle[tuple(sorted(b))],('initial oracle mismatch',mask,b))
            for nb in all_subsets(3):
                minus,plus=b-nb,nb-b;nm,nw,_=dred(p,m,w,b,minus,plus)
                require(nm==oracle[tuple(sorted(nb))],('update oracle mismatch',mask,b,nb))
                packet,e=certificate(p,m,w,o,nm,nw);require(packet is not None,e)
                before=s.inspect();v=s.check(sorted(minus),sorted(plus),packet,commit=False)
                require(v.accepted,v.reason)
                require(s.inspect()==before,'rollback mismatch')
                total+=1
                kind='mixed' if minus and plus else 'deletions' if minus else 'insertions' if plus else 'no_base_change'
                counts[kind]+=1
    return {'program_start':start,'program_stop':stop,'transitions':total,'oracle_mismatches':0,'rollback_mismatches':0,**counts}


def candidate_space(start,stop):
    candidates=[{'head':h,'body':list(bs)} for h in range(2) for bs in [(0,),(1,),(0,1)]]
    total=accepted=wrong=correct_pairs=0
    for mask in range(start,stop):
        raw={'n':2,'rules':[x for i,x in enumerate(candidates) if mask>>i&1],
             'blocks':[0,1],'local':[0,0]}
        om={tuple(sorted(b)):least_model(raw,b) for b in all_subsets(2)}
        for b in all_subsets(2):
            p,m,w,o,s=initialize(raw,b);before=s.inspect()
            for nb in all_subsets(2):
                got_correct=False;minus,plus=sorted(b-nb),sorted(nb-b)
                target=om[tuple(sorted(nb))]
                for cand in all_subsets(2):
                    heads=sorted(cand)
                    choices=[[-1]+[i for i,r in enumerate(raw['rules']) if r['head']==h] for h in heads]
                    for witness_values in itertools.product(*choices):
                        wp={str(h):v for h,v in zip(heads,witness_values)}
                        for offsets in itertools.product(range(3),repeat=2):
                            pack={'delete':sorted(m-cand),'insert':sorted(cand-m),'witness':wp,
                                  'offset':{str(i):v for i,v in enumerate(offsets)}}
                            v=s.check(minus,plus,pack,commit=False);total+=1
                            if v.accepted:
                                accepted+=1
                                if cand!=target:wrong+=1
                                else:got_correct=True
                require(got_correct,(mask,b,nb))
                correct_pairs+=1
                require(s.inspect()==before,'rollback mismatch')
    require(wrong==0,wrong)
    return {'program_start':start,'program_stop':stop,'candidate_packets':total,'accepted_packets':accepted,
            'wrong_models_accepted':wrong,'old_new_pairs_with_certificate':correct_pairs,'rollback_mismatches':0}


def representation(start,stop):
    partitions=[(0,0,0),(0,0,1),(0,1,0),(0,1,1),(0,1,2)]
    edges=[(b,h) for b in range(3) for h in range(3) if b!=h]
    counts={'cases':0,'feasible':0,'internal_order':0,'positive_cycle':0,'checked_obstructions':0}
    for mask in range(start,stop):
        bodies=[[] for _ in range(3)]
        for ei,(b,h) in enumerate(edges):
            if mask>>ei&1:bodies[h].append(b)
        rules=[{'head':h,'body':bodies[h]} for h in range(3)]
        for part in partitions:
            k=max(part)+1
            for local in itertools.product(range(3),repeat=3):
                raw={'n':3,'rules':rules,'blocks':list(part),'local':list(local)}
                m={0,1,2};w={i:i for i in m};p=Program(raw)
                offsets,e=potentials(p,m,w)
                def valid(os):
                    ranks=[os[part[i]]+local[i] for i in range(3)]
                    return all(ranks[b]<ranks[h] for h in range(3) for b in bodies[h])
                exact=any(valid(os) for os in itertools.product(range((k-1)*3+1),repeat=k))
                require((offsets is not None)==exact,(mask,part,local,e))
                counts['cases']+=1
                if exact:
                    require(valid(offsets),'invalid constructed offsets');counts['feasible']+=1
                else:
                    require(check_obstruction(raw,m,w,e),(raw,e))
                    counts[e['kind']]+=1;counts['checked_obstructions']+=1
    return {'pattern_start':start,'pattern_stop':stop,**counts,'oracle_mismatches':0}


def selection_space():
    atoms=list(itertools.product(range(2),range(2),range(2),range(-1,2)))
    systems=assignments=satisfying=0
    for length in (1,2):
        for chosen in itertools.product(atoms,repeat=length):
            raw,b,m,_=maxatom_to_horn(2,chosen)
            require(full(Program(raw),b)[0]==m,'forward reduction model mismatch')
            nv,reverse=horn_to_maxatom(raw,b,m)
            for x in itertools.product(range(-2,3),repeat=2):
                expected=satisfies(x,chosen)
                witness=selected_witness(raw,b,m,[-v for v in x])
                extended=extend_values(raw,b,m,x)
                require(len(extended)==nv,'reverse reduction variable count mismatch')
                require((witness is not None)==expected,'forward reduction assignment mismatch')
                require(satisfies(extended,reverse)==expected,'reverse reduction assignment mismatch')
                assignments+=1;satisfying+=int(expected)
            systems+=1
    return {'maxatom_systems':systems,'assignments':assignments,'satisfying_assignments':satisfying,
            'forward_mismatches':0,'reverse_mismatches':0,
            'scope':'finite assignment equivalence checks, not an unbounded decision procedure'}


def clock(f,*args,**kwargs):
    start=time.perf_counter_ns();value=f(*args,**kwargs)
    return value,(time.perf_counter_ns()-start)/1e9


def timing(family,n):
    rows=[]
    parts=['block','scalar'] if family=='exchange' else ['block' if family=='star' else 'scalar']
    for part in parts:
        for repetition in range(-1,7):
            if family=='exchange':raw,b=exchange(n,part=='block');minus={0}
            elif family=='star':raw,b=alternate_star(n);minus={0}
            else:raw,b=inactive_fanin(n);minus={n}
            plus=set();nb=b-minus
            pg=Program(raw)
            t=time.perf_counter_ns();m,w,_=full(pg,b);o,e=potentials(pg,m,w)
            require(o is not None,e)
            session=Session(raw,sorted(b),sorted(m),{str(h):v for h,v in w.items()},o)
            setup=(time.perf_counter_ns()-t)/1e9
            # No diagnostic full-state copy occurs in the incremental timed call.
            (fm,fw,fc),full_cpu=clock(full,pg,nb)
            (nm,nw,dc),dred_cpu=clock(dred,pg,m,w,b,minus,plus)
            require(nm==fm,'DRed/fresh materialisation mismatch')
            (packet,info),synthesis_cpu=clock(certificate,pg,m,w,o,nm,nw)
            require(packet is not None,info)
            text,serialize_cpu=clock(json.dumps,packet,separators=(',',':'),sort_keys=True)
            parsed,parse_cpu=clock(strict_loads,text)
            verdict,local_cpu=clock(session.check,sorted(minus),[],parsed)
            require(verdict.accepted,verdict.reason)
            (ok,vc),full_check_cpu=clock(verify_all,raw,nb,nm,nw,session.offset)
            require(ok,'full reference check failed')
            if repetition>=0:
                row={'family':family,'size':n,'partition':part,'repetition':repetition,
                     'atoms':raw['n'],'rules':len(raw['rules']),'premise_incidences':sum(len(r['body']) for r in raw['rules']),
                     'setup_wall_seconds':setup,'full_materialize_wall_seconds':full_cpu,'dred_wall_seconds':dred_cpu,
                     'synthesis_wall_seconds':synthesis_cpu,'serialize_wall_seconds':serialize_cpu,
                     'parse_wall_seconds':parse_cpu,'local_check_wall_seconds':local_cpu,'full_check_wall_seconds':full_check_cpu,
                     'packet_bytes':len(text.encode()),'accepted':True}
                row.update({'local_'+k:v for k,v in verdict.counters.items()})
                row.update({'dred_'+k:v for k,v in dc.items()})
                row.update({'full_'+k:v for k,v in fc.items()})
                row.update({'verify_'+k:v for k,v in vc.items()})
                rows.append(row)
    return {'family':family,'size':n,'warmups_per_setting':1,'clock':'time.perf_counter_ns; single operation per repetition','rows':rows}


def policy(fixture,horizon):
    from policy_cases import make_policy,snapshots,FIXTURES
    from temporal import ground
    from semantic_check import elaborate,direct_model
    name=FIXTURES[fixture];spec=make_policy(name,horizon);rows=[]
    for part in ['temporal','singleton']:
        # Every snapshot is re-elaborated independently; this front-end cost is
        # intentionally charged separately from resident update verification.
        (raw,b,atoms),gc=clock(ground,spec,part)
        (r2,b2,a2,_,_),ic=clock(elaborate,spec,part)
        require((raw,b,atoms)==(r2,b2,a2),'second temporal expander mismatch at initialization')
        p,m,w,o,s=initialize(raw,b)
        require({atoms[i] for i in m}==direct_model(spec),'initial tuple fixed-point mismatch over second-expander output')
        for label,nextspec in snapshots(spec)[1:]:
            (nr,nb,na),front_cpu=clock(ground,nextspec,part)
            (ir,ib,ia,_,_),independent_cpu=clock(elaborate,nextspec,part)
            require(nr==raw==ir and nb==ib and na==atoms==ia,'second temporal expander mismatch after update')
            minus,plus=b-nb,nb-b
            (nm,nw,dc),dred_cpu=clock(dred,p,m,w,b,minus,plus)
            (fm,fw,fc),full_cpu=clock(full,p,nb);require(nm==fm,'policy DRed/fresh mismatch')
            direct,oracle_cpu=clock(direct_model,nextspec)
            require({atoms[i] for i in nm}==direct,'policy tuple fixed-point mismatch over second-expander output')
            (pack,reason),synth_cpu=clock(certificate,p,m,w,o,nm,nw)
            fallback=False;check_cpu=0.0;counter={}
            if pack is None:
                # This outcome must not disappear; first-proof incompatibility
                # is not a proof of impossibility for all alternative witnesses.
                rows.append({'fixture':name,'horizon':horizon,'partition':part,'update':label,
                             'status':'incompatible_first_proof','reason':reason,'atoms':raw['n'],'rules':len(raw['rules'])})
                break
            text=json.dumps(pack,separators=(',',':'),sort_keys=True)
            verdict,check_cpu=clock(s.check,sorted(minus),sorted(plus),strict_loads(text))
            require(verdict.accepted,verdict.reason)
            require(verify_all(raw,nb,nm,nw,s.offset)[0],'policy full ranked-model check failed')
            row={'fixture':name,'horizon':horizon,'partition':part,'update':label,'status':'accepted',
                 'atoms':raw['n'],'rules':len(raw['rules']),'source_records':len(spec['facts']),
                 'old_model':len(m),'new_model':len(nm),'base_deleted':len(minus),'base_inserted':len(plus),
                 'ground_wall_seconds':front_cpu,'independent_ground_wall_seconds':independent_cpu,
                 'direct_oracle_wall_seconds':oracle_cpu,'dred_wall_seconds':dred_cpu,
                 'full_materialize_wall_seconds':full_cpu,'synthesis_wall_seconds':synth_cpu,
                 'local_check_wall_seconds':check_cpu,'packet_bytes':len(text.encode())}
            row.update(verdict.counters);rows.append(row)
            b,m,w,o=nb,nm,nw,list(s.offset)
    return {'fixture':name,'horizon':horizon,'clock':'time.perf_counter_ns; descriptive per-update elapsed time','rows':rows,'oracle_mismatches':0}


def units():
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise RuntimeError('unit tests failed')
    return {'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)}


def main():
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['units','correct','candidate','representation','selection','timing','policy'])
    a.add_argument('--start',type=int,default=0);a.add_argument('--stop',type=int,default=64)
    a.add_argument('--family',choices=['exchange','star','fanin'],default='exchange')
    a.add_argument('--size',type=int,default=16);a.add_argument('--fixture',type=int,default=0)
    a.add_argument('--out',type=Path,required=True);args=a.parse_args()
    # Bound memory without changing the host or enabling swap.
    resource.setrlimit(resource.RLIMIT_AS,(int(3.5*1024**3),int(3.5*1024**3)))
    resource.setrlimit(resource.RLIMIT_CPU,(38,39))
    start=time.monotonic();cpu=time.process_time()
    if args.mode=='units':data=units()
    elif args.mode=='correct':data=correct_updates(args.start,args.stop)
    elif args.mode=='candidate':data=candidate_space(args.start,args.stop)
    elif args.mode=='representation':data=representation(args.start,args.stop)
    elif args.mode=='selection':data=selection_space()
    elif args.mode=='timing':data=timing(args.family,args.size)
    else:data=policy(args.fixture,args.size)
    data['run']={'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,
                 'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    temp=args.out.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(args.out)
    print(json.dumps({'mode':args.mode,'status':'passed',**data['run']}))

if __name__=='__main__':main()
