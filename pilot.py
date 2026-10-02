import sys,time,json,resource
from pathlib import Path
p=Path(__file__).resolve().parent
sys.path.insert(0,str(p/'src'))
from cases import exchange,inactive_fanin,alternate_star
from producer import Program,full,dred,potentials,certificate
from checker import Session
from reference_check import verify_all
rows=[]
for group in [True,False]:
    raw,b=exchange(4096,group);pg=Program(raw)
    t=time.process_time();m,w,_=full(pg,b);o,e=potentials(pg,m,w)
    s=Session(raw,sorted(b),sorted(m),{str(h):r for h,r in w.items()},o);init=time.process_time()-t
    t=time.process_time();nm,nw,dc=dred(pg,m,w,b,{0},set());dp=time.process_time()-t
    t=time.process_time();packet,e=certificate(pg,m,w,o,nm,nw);pt=time.process_time()-t
    t=time.process_time();v=s.check([0],[],packet);ct=time.process_time()-t
    t=time.process_time();ok,fc=verify_all(raw,b-{0},nm,nw,s.offset);ft=time.process_time()-t
    if not (ok and v.accepted):
        raise RuntimeError('pilot verification failed')
    rows.append({'family':'exchange','length':4096,'partition':'block' if group else 'scalar','atoms':raw['n'],'rules':len(raw['rules']),
        'initialization_cpu_seconds':init,'dred_cpu_seconds':dp,'certificate_cpu_seconds':pt,'checker_cpu_seconds':ct,
        'full_check_cpu_seconds':ft,'certificate_bytes':len(json.dumps(packet,separators=(',',':')).encode()),
        'checker_counters':v.counters,'dred_counters':dc})
result={'cases':rows,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'process_cpu_seconds':time.process_time(),'status':'all_checks_accepted'}
(p/'results/e2e-pilot.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
