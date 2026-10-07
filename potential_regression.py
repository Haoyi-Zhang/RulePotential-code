"""Untimed public fixed-proof regressions; run explicitly, not in the old suite.

No files, network, timers, historical implementation copies or private paths.
References enumerate simple paths, a finite offset box, and interpretations.
"""
import copy
import itertools
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import producer
from checker import BOUND, Session
from obstruction_check import check_obstruction
from reference_check import verify_all
from cases import alternate_star, exchange, inactive_fanin


def graph_program(k, edges):
    """Fresh seed/head atoms for every edge avoid fact-level proof cycles."""
    raw = {"n": k, "rules": [], "blocks": list(range(k)), "local": [0] * k}
    base = set(range(k))
    for u, v, w in edges:
        b = raw["n"]
        h = b + 1
        raw["n"] += 2
        raw["blocks"].extend([u, v])
        raw["local"].extend([max(w - 1, 0), max(1 - w, 0)])
        raw["rules"].append({"head": h, "body": [b]})
        base.add(b)
    return raw, base


def proof_fixtures():
    specs = [
        (1, []), (4, []),
        (4, [(0, 1, 1), (1, 2, 1), (2, 3, 1)]),
        (4, [(3, 2, 1), (2, 1, 1), (1, 0, 1)]),
        (3, [(0, 1, -2), (1, 2, -1)]),
        (2, [(0, 1, 0), (1, 0, 0)]),
        (2, [(0, 1, 1), (1, 0, -1)]),
        (2, [(0, 1, -1), (1, 0, -1)]),
        (2, [(0, 1, 1), (1, 0, 1)]),
        (3, [(0, 1, 1), (1, 2, 0), (2, 0, 0)]),
        (1, [(0, 0, 1)]), (1, [(0, 0, 0)]),
        (2, [(0, 1, 1), (0, 1, 3)]),
        (2, [(0, 1, 2), (0, 1, 2)]),
        (5, [(0, 1, 2), (3, 4, 1)]),
        (5, [(0, 1, 1), (0, 2, 2), (1, 3, 1), (2, 3, 0)]),
        (3, [(2, 1, 3), (1, 0, -1), (0, 2, -2)]),
        (3, [(2, 1, 3), (1, 0, -1), (0, 2, -1)]),
        (2, [(0, 1, 1 << 31)]),
        (3, [(2, 1, 1 << 31), (1, 0, 1 << 31)]),
        (2, [(0, 1, 1), (0, 1, 1), (1, 0, 0)]),
        (2, [(0, 1, 1)]), (2, [(1, 0, 1)]),
        (8, [(i, i - 1, 1) for i in range(7, 0, -1)]),
    ]
    result = []
    for i, (k, edges) in enumerate(specs):
        raw, base = graph_program(k, edges)
        old = [BOUND] * k if i == 21 else [-BOUND] * k if i == 22 else None
        result.append((raw, base, old))
    return result


def path_reference(raw, model, witness, old=None):
    """Raw selected simple paths/cycles, without pair maxima or relaxation."""
    k = max(raw["blocks"]) + 1
    adjacency = [[] for _ in range(k)]
    for h in model:
        if witness[h] < 0:
            continue
        for b in set(raw["rules"][witness[h]]["body"]):
            u, v = raw["blocks"][b], raw["blocks"][h]
            weight = raw["local"][b] - raw["local"][h] + 1
            if u == v:
                if weight > 0:
                    return None, "internal_order"
            else:
                adjacency[u].append((v, weight))
    values = [0] * k if old is None else list(old)
    positive = False
    for start in range(k):
        def visit(u, seen, total):
            nonlocal positive
            values[u] = max(values[u], (0 if old is None else old[start]) + total)
            for v, weight in adjacency[u]:
                if v == start:
                    positive |= total + weight > 0
                elif v not in seen:
                    visit(v, seen | {v}, total + weight)
        visit(start, {start}, 0)
    if positive:
        return None, "positive_cycle"
    if old is not None and any(abs(value) > BOUND for value in values):
        return path_reference(raw, model, witness)
    return values, "feasible"


def interpretation_reference(raw, base):
    """Closed-superset intersection, confined to at most eight atoms."""
    if raw["n"] > 8:
        raise ValueError("finite interpretation reference bound")
    common = set(range(raw["n"]))
    for mask in range(1 << raw["n"]):
        x = {i for i in range(raw["n"]) if mask >> i & 1}
        if set(base) <= x and all(not set(r["body"]) <= x or r["head"] in x
                                 for r in raw["rules"]):
            common &= x
    return common


def update_fixtures():
    result = []
    for grouped in (True, False):
        raw, base = exchange(3, grouped)
        result.append((raw, base, [{0}, {4}, {0, 4}, set()]))
    raw, base = alternate_star(3)
    result.append((raw, base, [{0}, {1}, set()]))
    raw, base = inactive_fanin(3)
    result.append((raw, base, [set(), {3}, set()]))
    raw = {"n": 3, "rules": [{"head": 0, "body": []},
                            {"head": 1, "body": [0]},
                            {"head": 2, "body": [1]}],
           "blocks": [0, 1, 2], "local": [0, 0, 0]}
    result.append((raw, {0}, [set(), {2}, {0}]))
    return result


def snapshot(session):
    return (copy.deepcopy(session.inspect()),
            {pair: list(tree.values) for pair, tree in session.trees.items()})


class PotentialRegression(unittest.TestCase):
    def test_selected_proofs_against_simple_paths(self):
        self.assertEqual(len(proof_fixtures()), 24)
        for raw, base, old in proof_fixtures():
            pg = producer.Program(raw)
            m, w, _ = producer.full(pg, base)
            expected, kind = path_reference(raw, m, w, old)
            actual, info = producer.potentials(pg, m, w, old)
            self.assertEqual(actual, expected)
            self.assertEqual(info["kind"], kind)
            if actual is None:
                self.assertTrue(check_obstruction(raw, m, w, info))
            else:
                self.assertTrue(verify_all(raw, base, m, w, actual)[0])

    def test_small_offset_box_is_independent(self):
        options = [(0, 1, -1), (0, 1, 1), (1, 0, -1), (1, 0, 1)]
        for mask in range(16):
            raw, base = graph_program(2, [e for i, e in enumerate(options) if mask >> i & 1])
            pg = producer.Program(raw)
            m, w, _ = producer.full(pg, base)
            def valid(os):
                ranks = [os[b] + l for b, l in zip(raw["blocks"], raw["local"])]
                return all(ranks[b] < ranks[h] for h in m if w[h] >= 0
                           for b in raw["rules"][w[h]]["body"])
            # Maximum positive weight 1: normalized two-block offsets fit [0,1].
            feasible = any(valid(os) for os in itertools.product(range(2), repeat=2))
            self.assertEqual(producer.potentials(pg, m, w)[0] is not None, feasible)

    def test_one_edge_sort_per_invocation_and_two_on_rebase(self):
        for i in (0, 3, 8, 21):
            raw, base, old = proof_fixtures()[i]
            pg = producer.Program(raw)
            m, w, _ = producer.full(pg, base)
            calls = []
            def counted(xs, *args, **kwargs):
                if type(xs).__name__ == "dict_items":
                    calls.append(1)
                return sorted(xs, *args, **kwargs)
            with patch.object(producer, "sorted", counted, create=True):
                producer.potentials(pg, m, w, old)
            self.assertEqual(len(calls), 2 if i == 21 else 1)

    def test_order_and_equal_maximum_representative(self):
        raw, base = graph_program(2, [(0, 1, 1), (0, 1, 1), (1, 0, 0)])
        pg = producer.Program(raw)
        m, w, _ = producer.full(pg, base)
        _, info = producer.potentials(pg, m, w)
        representative = next(row["edge"] for row in info["cycle"]
                              if (row["left"], row["right"]) == (0, 1))
        self.assertEqual(representative, [0, 2, 3])
        raw, base = graph_program(4, [(3, 2, 1), (2, 1, 1), (1, 0, 1)])
        pg = producer.Program(raw)
        m, w, _ = producer.full(pg, base)
        self.assertEqual(producer.potentials(pg, m, w),
                         ([3, 2, 1, 0], {"kind": "feasible", "pairs": 3,
                                         "passes": 4, "relaxations": 6, "rebased": False}))

    def test_packets_counters_and_tree_rollback(self):
        for raw, base, targets in update_fixtures():
            pg = producer.Program(raw)
            m, w, _ = producer.full(pg, base)
            o, _ = producer.potentials(pg, m, w)
            s = Session(raw, sorted(base), sorted(m), {str(h): r for h, r in w.items()}, o)
            for nb in targets:
                removed, added = base - nb, nb - base
                nm, nw, _ = producer.dred(pg, m, w, base, removed, added)
                self.assertEqual(nm, interpretation_reference(raw, nb))
                packet, info = producer.certificate(pg, m, w, o, nm, nw)
                self.assertIsNotNone(packet, info)
                before = snapshot(s)
                bad = copy.deepcopy(packet)
                bad["extra"] = True
                self.assertFalse(s.check(sorted(removed), sorted(added), bad).accepted)
                self.assertEqual(before, snapshot(s))
                if packet["offset"]:
                    bad = copy.deepcopy(packet)
                    bad["offset"] = {key: -BOUND for key in bad["offset"]}
                    self.assertFalse(s.check(sorted(removed), sorted(added), bad).accepted)
                    self.assertEqual(before, snapshot(s))
                tentative = s.check(sorted(removed), sorted(added), packet, commit=False)
                self.assertTrue(tentative.accepted, tentative.reason)
                self.assertEqual(before, snapshot(s))
                committed = s.check(sorted(removed), sorted(added), packet)
                self.assertTrue(committed.accepted, committed.reason)
                self.assertEqual(tentative.counters, committed.counters)
                self.assertTrue(verify_all(raw, nb, nm, nw, s.offset)[0])
                base, m, w, o = set(nb), nm, nw, list(s.offset)

    def test_no_input_mutation_or_cross_call_state(self):
        raw, base, old = proof_fixtures()[21]
        pg = producer.Program(raw)
        m, w, _ = producer.full(pg, base)
        saved = copy.deepcopy((raw, pg.__dict__, m, w, old))
        first = producer.potentials(pg, m, w, old)
        other = producer.Program({"n": 1, "rules": [], "blocks": [0], "local": [0]})
        producer.potentials(other, set(), {})
        self.assertEqual(first, producer.potentials(pg, m, w, old))
        self.assertEqual(saved, (raw, pg.__dict__, m, w, old))


if __name__ == "__main__":
    unittest.main()
