"""Supplementary tests for fixed-proof minimum-field repair (not the old suite)."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from offset_repair import optimal_offsets
from optimality_check import check_optimality
from bounded_offset_repair import optimal_bounded_offsets
from bounded_optimality_check import check_bounded_optimality

class OffsetRepairTests(unittest.TestCase):
    def check(self, n, edges, old):
        result = optimal_offsets(n, edges, old)
        self.assertTrue(check_optimality(n, edges, old, result['offsets'], result['certificate']))
        return result

    def test_lowering_avoids_forward_cascade(self):
        for n in (3, 9, 32):
            es = [(0, 1, 1)] + [(1, j, 0) for j in range(2, n)]
            r = self.check(n, es, [0] * n)
            self.assertEqual(r['changed_fields'], 1)
            self.assertEqual(r['offsets'], [-1] + [0] * (n - 1))

    def test_chain_needs_all_but_one_fields(self):
        for n in (2, 7, 23):
            r = self.check(n, [(i, i+1, 1) for i in range(n-1)], [0]*n)
            self.assertEqual(r['changed_fields'], n-1)

    def test_zero_cycle_is_not_an_obstruction(self):
        self.assertEqual(self.check(3, [(0,1,1),(1,2,-1),(2,0,0)], [0,0,0])['changed_fields'], 1)
        self.assertEqual(self.check(3, [(0,1,0),(1,0,0)], [5,5,-7])['changed_fields'], 0)

    def test_positive_cycle_rejected(self):
        for es in ([(0,1,1),(1,0,0)], [(0,0,1)]):
            with self.assertRaises(ValueError): optimal_offsets(2, es, [0,0])

    def test_disconnected_and_large_integers(self):
        z=10**80
        self.assertEqual(self.check(4, [(0,1,2)], [z,z,-z,-z])['changed_fields'], 1)
        self.assertEqual(self.check(1, [], [z])['changed_fields'], 0)

    def test_adversarial_chain_covers(self):
        n=4; es=[(0,1,1),(1,2,1),(2,3,1)]; old=[0]*n
        r=self.check(n,es,old); good=r['certificate']; mutated=[]
        z=copy.deepcopy(good); z['chains'][0]['blocks'].pop();z['chains'][0]['paths'].pop();mutated.append(z)
        z=copy.deepcopy(good);z['chains'].append(copy.deepcopy(z['chains'][0]));mutated.append(z)
        z=copy.deepcopy(good);z['chains'][0]['paths'][0]=[0,2,1];mutated.append(z)
        z=copy.deepcopy(good);z['chains'][0]['paths'][0]=[0,0,1];mutated.append(z)
        z=copy.deepcopy(good);z['chains'][0]['blocks'][0]=True;mutated.append(z)
        z=copy.deepcopy(good);z['chains'][0]['paths'][0]=[0,1,0,1];mutated.append(z)
        z=copy.deepcopy(good);z['trusted_optimum']=3;mutated.append(z)
        z={'chains':[{'blocks':[i],'paths':[]} for i in range(n)]};mutated.append(z)
        for bad in mutated:
            self.assertFalse(check_optimality(n,es,old,r['offsets'],bad))
        self.assertFalse(check_optimality(n,es,old,old,good))

    def test_nonpositive_path_and_wrong_cost_rejected(self):
        cert={'chains':[{'blocks':[0,1],'paths':[[0,1]]}]}
        self.assertFalse(check_optimality(2,[(0,1,0)],[0,0],[0,1],cert))
        r=self.check(2,[(0,1,1)],[0,0])
        self.assertFalse(check_optimality(2,[(0,1,1)],[0,0],[1,2],r['certificate']))

    def test_domain_validation(self):
        for n, es, old in [(True, [], [0]), (0,[],[]), (257,[],[0]*257), (2,[(0,2,1)],[0,0]), (2,[(0,1,True)],[0,0])]:
            with self.assertRaises(ValueError): optimal_offsets(n, es, old)
        self.assertFalse(check_optimality(2,[],[0,False],[0,0],{'chains':[]}))


class BoundedOffsetRepairTests(unittest.TestCase):
    def check(self, n, edges, old, lower, upper):
        result = optimal_bounded_offsets(n, edges, old, lower, upper)
        self.assertTrue(check_bounded_optimality(
            n, edges, old, lower, upper, result['offsets'], result['certificate']))
        return result

    def test_loose_bounds_recover_unbounded_optimum(self):
        cases = [
            (3, [(0, 1, 1), (1, 2, 0)], [0, 0, 0]),
            (4, [(0, 1, 2), (0, 2, 2), (2, 3, -1)], [5, 5, -2, 4]),
            (3, [(0, 1, 1), (1, 2, -1), (2, 0, 0)], [0, 0, 0]),
        ]
        for n, edges, old in cases:
            unbounded = optimal_offsets(n, edges, old)
            bounded = self.check(n, edges, old, [-100] * n, [100] * n)
            self.assertEqual(bounded['changed_fields'], unbounded['changed_fields'])

    def test_bounds_can_force_old_coordinates(self):
        r = self.check(3, [], [-2, 0, 4], [0, -1, 0], [1, 1, 3])
        self.assertEqual(r['offsets'], [0, 0, 3])
        self.assertEqual(r['changed_fields'], 2)
        self.assertEqual({x['block'] for x in r['certificate']['forced']}, {0, 2})

    def test_anchor_paths_capture_indirect_bound_conflict(self):
        # o0 >= 0 and o1-o0 >= 2 force o1>old1 even though old1 is in its box.
        r = self.check(2, [(0, 1, 2)], [0, 0], [0, -3], [3, 3])
        self.assertEqual(r['changed_fields'], 1)
        self.assertEqual(r['offsets'][0], 0)
        self.assertGreaterEqual(r['offsets'][1], 2)

    def test_bounded_problem_can_be_infeasible(self):
        with self.assertRaises(ValueError):
            optimal_bounded_offsets(2, [(0, 1, 2)], [0, 0], [0, 0], [0, 1])
        with self.assertRaises(ValueError):
            optimal_bounded_offsets(1, [], [0], [2], [1])

    def test_singleton_and_large_integers(self):
        z = 10**80
        self.assertEqual(self.check(1, [], [z], [z], [z])['changed_fields'], 0)
        r = self.check(1, [], [z], [-z], [0])
        self.assertEqual(r['offsets'], [0])
        self.assertEqual(r['changed_fields'], 1)

    def test_bounded_certificate_mutations_rejected(self):
        n = 3; edges = [(0, 1, 1), (1, 2, 1)]
        old = [0, 0, 0]; lower = [0, -2, -2]; upper = [0, 3, 3]
        r = self.check(n, edges, old, lower, upper)
        cert = r['certificate']; bad = []
        z = copy.deepcopy(cert); z['forced'][0]['path'] = list(reversed(z['forced'][0]['path'])); bad.append(z)
        z = copy.deepcopy(cert); z['forced'][0]['direction'] = 'sideways'; bad.append(z)
        z = copy.deepcopy(cert); z['forced'][0]['block'] = True; bad.append(z)
        z = copy.deepcopy(cert); z['forced'].append(copy.deepcopy(z['forced'][0])); bad.append(z)
        z = copy.deepcopy(cert); z['chains'].append({'blocks':[0], 'paths':[]}); bad.append(z)
        z = copy.deepcopy(cert); z['trusted_optimum'] = r['changed_fields']; bad.append(z)
        for c in bad:
            self.assertFalse(check_bounded_optimality(n, edges, old, lower, upper, r['offsets'], c))
        wrong = list(r['offsets']); wrong[0] = 1
        self.assertFalse(check_bounded_optimality(n, edges, old, lower, upper, wrong, cert))

    def test_bounded_domain_validation(self):
        malformed = [
            (True, [], [0], [0], [0]),
            (0, [], [], [], []),
            (2, [(0, 2, 1)], [0, 0], [0, 0], [1, 1]),
            (2, [(0, 1, True)], [0, 0], [0, 0], [1, 1]),
            (1, [], [0], [False], [1]),
        ]
        for args in malformed:
            with self.assertRaises(ValueError):
                optimal_bounded_offsets(*args)
        self.assertFalse(check_bounded_optimality(
            1, [], [0], [0], [1], [False], {'chains':[{'blocks':[0],'paths':[]}], 'forced':[]}))

if __name__ == '__main__': unittest.main()
