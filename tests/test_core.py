import copy
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from checker import Session, strict_loads
from producer import Program, full, dred, potentials, certificate
from oracle import least_model
from cases import exchange, random_program


def setup(raw, base):
    p = Program(raw)
    model, witness, _ = full(p, base)
    offsets, why = potentials(p, model, witness)
    assert offsets is not None, why
    state = Session(raw, sorted(base), sorted(model), {str(h): r for h, r in witness.items()}, offsets)
    return p, model, witness, offsets, state


class CoreTests(unittest.TestCase):
    def test_exchange_constant_block_patch(self):
        for n in [1, 2, 17, 200]:
            raw, b = exchange(n)
            p, m, w, o, s = setup(raw, b)
            nm, nw, _ = dred(p, m, w, b, {0}, set())
            packet, _ = certificate(p, m, w, o, nm, nw)
            self.assertEqual(packet['delete'], [0])
            self.assertEqual(len(packet['witness']), 1)
            self.assertEqual(len(packet['offset']), 1)
            got = s.check([0], [], packet)
            self.assertTrue(got.accepted, got.reason)
            self.assertEqual(got.counters['pair_checks'], 1)
            self.assertEqual(s.model, nm)

    def test_scalar_patch_grows(self):
        raw, b = exchange(30, False)
        p, m, w, o, s = setup(raw, b)
        nm, nw, _ = dred(p, m, w, b, {0}, set())
        packet, _ = certificate(p, m, w, o, nm, nw)
        self.assertEqual(len(packet['offset']), 30)
        self.assertTrue(s.check([0], [], packet).accepted)

    def test_unsupported_cycle_is_not_a_proof(self):
        raw = {'n': 3, 'rules': [{'head': 1, 'body': [0]},
                               {'head': 2, 'body': [1]}, {'head': 1, 'body': [2]}],
               'blocks': [0, 1, 2], 'local': [0, 0, 0]}
        _, m, w, o, s = setup(raw, {0})
        bad = {'delete': [0], 'insert': [], 'witness': {'1': 2}, 'offset': {}}
        before = s.inspect()
        self.assertFalse(s.check([0], [], bad).accepted)
        self.assertEqual(before, s.inspect())
        self.assertEqual(least_model(raw, []), set())

    def test_rejections_rollback_and_valid_followup(self):
        raw, base = exchange(12)
        p, m, w, o, s = setup(raw, base)
        nm, nw, _ = dred(p, m, w, base, {0}, set())
        good, _ = certificate(p, m, w, o, nm, nw)
        mutations = []
        for key in ['offset', 'witness']:
            z = copy.deepcopy(good); z[key] = {}; mutations.append(z)
        z = copy.deepcopy(good); z['delete'].append(0); mutations.append(z)
        z = copy.deepcopy(good); z['witness']['1'] = -1; mutations.append(z)
        z = copy.deepcopy(good); z['offset']['0'] = -100; mutations.append(z)
        z = copy.deepcopy(good); z['delete'] = [0, 2]; mutations.append(z)
        z = copy.deepcopy(good); z['extra'] = []; mutations.append(z)
        z = copy.deepcopy(good); z['offset'] = {'00': 100}; mutations.append(z)
        z = copy.deepcopy(good); z['insert'] = [True]; mutations.append(z)
        before = s.inspect()
        for packet in mutations:
            v = s.check([0], [], packet)
            self.assertFalse(v.accepted, packet)
            self.assertEqual(before, s.inspect(), packet)
        self.assertTrue(s.check([0], [], good).accepted)
        self.assertEqual(s.model, nm)

    def test_empty_body_and_base_reclassification(self):
        raw = {'n': 2, 'rules': [{'head': 0, 'body': []}, {'head': 1, 'body': [0]}],
               'blocks': [0, 1], 'local': [0, 0]}
        p, m, w, o, s = setup(raw, {0})
        nm, nw, _ = dred(p, m, w, {0}, {0}, set())
        packet, _ = certificate(p, m, w, o, nm, nw)
        self.assertEqual(packet['delete'], [])
        self.assertTrue(s.check([0], [], packet).accepted)
        self.assertEqual(s.witness[0], 0)

    def test_arbitrary_packet_not_model_annotation(self):
        # An omitted consequence is rejected even if every listed witness is valid.
        raw = {'n': 2, 'rules': [{'head': 1, 'body': [0]}],
               'blocks': [0, 1], 'local': [0, 0]}
        p, m, w, o, s = setup(raw, set())
        packet = {'delete': [], 'insert': [0], 'witness': {'0': -1}, 'offset': {}}
        self.assertFalse(s.check([], [0], packet).accepted)

    def test_partition_can_be_incomplete_for_an_acyclic_proof(self):
        raw = {'n': 4, 'rules': [{'head': 2, 'body': [1]}, {'head': 0, 'body': [3]}],
               'blocks': [0, 0, 1, 1], 'local': [0, 1, 0, 1]}
        p = Program(raw); m, w, _ = full(p, {1, 3})
        o, reason = potentials(p, m, w)
        self.assertIsNone(o)
        self.assertEqual(reason['kind'], 'positive_cycle')
        self.assertGreater(reason['weight_sum'], 0)
        self.assertEqual(m, set(range(4)))

    def test_random_mixed_sequences(self):
        import random
        for seed in range(30):
            raw, base = random_program(7, seed)
            p, m, w, o, s = setup(raw, base)
            rng = random.Random(seed + 99)
            for _ in range(12):
                newbase = {i for i in range(7) if rng.randrange(3) == 0}
                remove, add = base - newbase, newbase - base
                nm, nw, _ = dred(p, m, w, base, remove, add)
                self.assertEqual(nm, least_model(raw, newbase))
                packet, _ = certificate(p, m, w, o, nm, nw)
                v = s.check(sorted(remove), sorted(add), packet)
                self.assertTrue(v.accepted, v.reason)
                self.assertEqual(s.model, nm)
                m, w, o, base = nm, nw, list(s.offset), newbase

    def test_json_duplicate_and_nonfinite_rejected(self):
        for text in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.assertRaises(ValueError): strict_loads(text)

    def test_redundant_patch_and_no_commit(self):
        raw, b = exchange(4)
        _, m, w, o, s = setup(raw, b)
        no_op = {'delete': [], 'insert': [], 'witness': {str(h): r for h,r in w.items()},
                 'offset': {str(i): v for i,v in enumerate(o)}}
        before = s.inspect()
        self.assertTrue(s.check([], [], no_op, commit=False).accepted)
        self.assertEqual(before, s.inspect())


if __name__ == '__main__':
    unittest.main()
