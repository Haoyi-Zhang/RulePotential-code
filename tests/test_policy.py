import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from policy_cases import make_policy,snapshots,FIXTURES
from temporal import ground
from semantic_check import elaborate,direct_model
from producer import Program,full,dred,potentials,certificate
from checker import Session
from reference_check import verify_all

class PolicyTests(unittest.TestCase):
    def test_all_source_records_and_twelve_updates(self):
        counts=[]
        for name in FIXTURES:
            spec=make_policy(name,4);counts.append(len(spec['facts']))
            raw,b,atoms=ground(spec);r2,b2,a2,_,_=elaborate(spec)
            self.assertEqual((raw,b,atoms),(r2,b2,a2))
            p=Program(raw);m,w,_=full(p,b);o,e=potentials(p,m,w);self.assertIsNotNone(o,e)
            session=Session(r2,sorted(b),sorted(m),{str(h):r for h,r in w.items()},o)
            states=snapshots(spec);self.assertEqual(len(states),13)
            for label,nextspec in states[1:]:
                nr,nb,_=ground(nextspec);self.assertEqual(nr,raw)
                nm,nw,_=dred(p,m,w,b,b-nb,nb-b)
                self.assertEqual({atoms[i] for i in nm},direct_model(nextspec),label)
                packet,e=certificate(p,m,w,o,nm,nw);self.assertIsNotNone(packet,e)
                v=session.check(sorted(b-nb),sorted(nb-b),packet);self.assertTrue(v.accepted,v.reason)
                self.assertTrue(verify_all(raw,nb,nm,nw,session.offset)[0])
                if label.startswith('overlap-'):
                    self.assertEqual(m,nm,label)
                b,m,w,o=nb,nm,nw,list(session.offset)
        self.assertEqual(counts,[5,6,6])

    def test_independent_substitution_budget(self):
        # One guard tuple is tiny, but type enumeration can still explode.
        s=make_policy(FIXTURES[0],4)
        s['types']['subject']=[str(i) for i in range(30)]
        # Reject immediately on malformed facts or allocation preflight, not enumerate.
        for f in (ground,elaborate):
            with self.assertRaises(ValueError):f(s)

if __name__=='__main__':unittest.main()
