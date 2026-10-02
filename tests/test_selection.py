import sys,unittest,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from selection import maxatom_to_horn,horn_to_maxatom,satisfies,selected_witness,extend_values
from producer import Program,full,potentials
from checker import Session

class SelectionTests(unittest.TestCase):
    def test_forward_signs_and_self_variables(self):
        checked=0
        for z,u,v,c in itertools.product(range(2),range(2),range(2),range(-2,3)):
            a=[(z,u,v,c)];raw,b,m,_=maxatom_to_horn(2,a)
            self.assertEqual(full(Program(raw),b)[0],m)
            for x in itertools.product(range(-2,3),repeat=2):
                w=selected_witness(raw,b,m,[-xx for xx in x])
                self.assertEqual(w is not None,satisfies(x,a));checked+=1
        self.assertEqual(checked,1000)

    def test_reverse_auxiliary_encoding(self):
        # Conjunction, >2 alternatives, empty-body and base-head bypass, cycles.
        raw={'n':4,'blocks':[0,0,1,1],'local':[1,2,0,2],
             'rules':[{'head':2,'body':[0,1]},{'head':2,'body':[3]},
                      {'head':2,'body':[0]},{'head':3,'body':[]},
                      {'head':1,'body':[2]}]}
        b={0};m=full(Program(raw),b)[0];k,atoms=horn_to_maxatom(raw,b,m)
        for x in itertools.product(range(-3,4),repeat=2):
            ext=extend_values(raw,b,m,x)
            self.assertEqual(len(ext),k)
            self.assertEqual(satisfies(ext,atoms),selected_witness(raw,b,m,[-v for v in x]) is not None)

    def test_zero_weight_block_cycle_is_allowed(self):
        # Two independent selected edges make a zero block cycle, not a proof cycle.
        raw={'n':4,'blocks':[0,0,1,1],'local':[0,1,0,1],
             'rules':[{'head':3,'body':[0]},{'head':1,'body':[2]}]}
        b={0,2};p=Program(raw);m,w,_=full(p,b);o,e=potentials(p,m,w)
        self.assertIsNotNone(o,e)
        s=Session(raw,sorted(b),sorted(m),{str(h):r for h,r in w.items()},o)
        self.assertTrue(s.check([],[],{'delete':[],'insert':[],'witness':{},'offset':{}}).accepted)

if __name__=='__main__':unittest.main()
