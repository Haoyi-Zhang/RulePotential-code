#!/usr/bin/env python3
"""Small owned toy: reject a missing rank repair, then accept the right update."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from cases import exchange
from checker import Session,strict_loads
from producer import Program,full,dred,potentials,certificate

def main():
    raw,base=exchange(4,True)
    p=Program(raw);model,witness,_=full(p,base);offsets,reason=potentials(p,model,witness)
    if offsets is None: raise RuntimeError(reason)
    s=Session(raw,sorted(base),sorted(model),{str(k):v for k,v in witness.items()},offsets)
    nm,nw,_=dred(p,model,witness,base,{0},set())
    packet,reason=certificate(p,model,witness,offsets,nm,nw)
    if packet is None: raise RuntimeError(reason)
    before=s.inspect()
    bad=dict(packet);bad['offset']={}
    rejected=s.check([0],[],bad)
    if rejected.accepted or s.inspect()!=before: raise AssertionError('negative control or rollback failed')
    text=json.dumps(packet,separators=(',',':'),sort_keys=True)
    accepted=s.check([0],[],strict_loads(text))
    if not accepted.accepted or set(s.inspect()['model'])!=nm: raise AssertionError(accepted.reason)
    print(json.dumps({'negative_control':rejected.reason,'accepted':accepted.accepted,
                      'packet':packet,'counters':accepted.counters,'remaining_atoms':len(nm)},indent=2))
if __name__=='__main__':main()
