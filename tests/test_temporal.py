import copy
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from temporal import ground,exchange_spec,coalesce
import semantic_check
from semantic_check import elaborate
from producer import Program,full,dred,potentials,certificate
from checker import Session

class TemporalTests(unittest.TestCase):
    def test_two_expanders_and_tuple_fixed_point_scope(self):
        for n in [1,2,4,8,17]:
            spec=exchange_spec(n)
            raw,base,atoms=ground(spec)
            cr,cb,ca,_,_=elaborate(spec)
            self.assertEqual((raw,base,atoms),(cr,cb,ca))
            m,w,_=full(Program(raw),base)
            with patch.object(semantic_check, 'elaborate', wraps=semantic_check.elaborate) as reused:
                tuple_model=semantic_check.direct_model(spec)
            self.assertEqual(reused.call_count,1)
            self.assertEqual({atoms[i] for i in m},tuple_model)
            changed=copy.deepcopy(spec);changed['facts']=changed['facts'][1:]
            nr,nb,na=ground(changed)
            nm,nw,_=dred(Program(raw),m,w,base,base-nb,nb-base)
            with patch.object(semantic_check, 'elaborate', wraps=semantic_check.elaborate) as reused:
                changed_tuple_model=semantic_check.direct_model(changed)
            self.assertEqual(reused.call_count,1)
            self.assertEqual({atoms[i] for i in nm},changed_tuple_model)
            self.assertEqual(raw,nr)
            o,_=potentials(Program(raw),m,w)
            s=Session(cr,sorted(cb),sorted(m),{str(i):r for i,r in w.items()},o)
            c,_=certificate(Program(raw),m,w,o,nm,nw)
            self.assertTrue(s.check(sorted(base-nb),sorted(nb-base),c).accepted)

    def test_overlap_empty_intervals_and_coalescing(self):
        s=exchange_spec(5)
        s['facts']=[{'pred':'hold','args':['a'],'start':0,'stop':3},
                    {'pred':'hold','args':['a'],'start':2,'stop':5},
                    {'pred':'hold','args':['b'],'start':2,'stop':2}]
        raw,b,atoms=ground(s)
        _,cb,_,_,_=elaborate(s)
        self.assertEqual(b,cb)
        self.assertEqual(len(b),5)
        self.assertEqual(coalesce(atoms,b),[{'pred':'hold','args':['a'],'start':0,'stop':5}])
        s['facts']=coalesce(atoms,b)
        self.assertEqual(ground(s)[1],b)

    def test_guard_and_shift_boundaries(self):
        s=exchange_spec(4)
        s['guards']['chains']['rows']=[['a']]
        s['rules']=s['rules'][:1]
        s['rules'][0]['start']=0 # shift -1 at zero drops the instance
        raw,b,a=ground(s)
        self.assertEqual(len(raw['rules']),4)
        self.assertEqual((raw,b,a),elaborate(s)[:3])

    def test_type_and_interval_rejections(self):
        s=exchange_spec(2)
        variants=[]
        z=copy.deepcopy(s);z['horizon']=True;variants.append(z)
        z=copy.deepcopy(s);z['facts'][0]['stop']=4;variants.append(z)
        z=copy.deepcopy(s);z['facts'][0]['args']=['c'];variants.append(z)
        z=copy.deepcopy(s);z['rules'][0]['body'][0]['terms']=['?missing'];variants.append(z)
        z=copy.deepcopy(s);z['guards']['chains']['rows'].append(['a']);variants.append(z)
        z=copy.deepcopy(s);z['rules'][0]['head']['shift']=1;variants.append(z)
        for z in variants:
            for f in [ground,elaborate]:
                with self.assertRaises(ValueError):f(z)

if __name__=='__main__':unittest.main()
