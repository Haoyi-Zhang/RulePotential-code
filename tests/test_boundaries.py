import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from producer import Program,full,dred,potentials,certificate
from checker import Session,BOUND
from obstruction_check import check_obstruction
from cases import alternate_star,inactive_fanin,exchange

class BoundaryTests(unittest.TestCase):
    def test_positive_cycle_certificate_and_false_weight(self):
        raw={'n':4,'rules':[{'head':2,'body':[1]},{'head':0,'body':[3]}],
             'blocks':[0,0,1,1],'local':[0,1,0,1]}
        p=Program(raw);m,w,_=full(p,{1,3});o,e=potentials(p,m,w)
        self.assertIsNone(o);self.assertTrue(check_obstruction(raw,m,w,e))
        bad=copy.deepcopy(e);bad['cycle'][0]['weight']+=1
        self.assertFalse(check_obstruction(raw,m,w,bad))
        bad=copy.deepcopy(e);bad['cycle']=bad['cycle'][:-1]
        self.assertFalse(check_obstruction(raw,m,w,bad))

    def test_internal_obstruction(self):
        raw={'n':2,'rules':[{'head':1,'body':[0]}],'blocks':[0,0],'local':[1,0]}
        p=Program(raw);m,w,_=full(p,{0});o,e=potentials(p,m,w)
        self.assertIsNone(o);self.assertTrue(check_obstruction(raw,m,w,e))

    def test_witness_and_closure_frontier_costs(self):
        for factory,n in [(alternate_star,40),(inactive_fanin,40)]:
            raw,b=factory(n);p=Program(raw);m,w,_=full(p,b);o,_=potentials(p,m,w)
            rem={0} if factory==alternate_star else {n}
            nm,nw,_=dred(p,m,w,b,rem,set());packet,_=certificate(p,m,w,o,nm,nw)
            s=Session(raw,sorted(b),sorted(m),{str(h):r for h,r in w.items()},o)
            v=s.check(sorted(rem),[],packet);self.assertTrue(v.accepted,v.reason)
            self.assertEqual(len(packet['delete']),1)
            if factory==alternate_star:self.assertEqual(len(packet['witness']),n)
            else:self.assertEqual(v.counters['closure_rules'],n)

    def test_offset_rebase_at_transport_bound(self):
        raw,b=exchange(5);p=Program(raw);m,w,_=full(p,b);o=[BOUND,BOUND]
        s=Session(raw,sorted(b),sorted(m),{str(h):r for h,r in w.items()},o)
        nm,nw,_=dred(p,m,w,b,{0},set());packet,e=certificate(p,m,w,o,nm,nw)
        self.assertTrue(e['rebased'])
        self.assertTrue(s.check([0],[],packet).accepted)

if __name__=='__main__':unittest.main()
