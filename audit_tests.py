#!/usr/bin/env python3
"""Independent deterministic property audits for the delivered reference code.

These tests deliberately reimplement their small oracles instead of importing
producer closure, optimizer closure, or matching helpers.  They are finite
checks, not mechanized proofs of the paper's general theorems.
"""
from __future__ import annotations

import copy
import itertools
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from bounded_offset_repair import optimal_bounded_offsets
from bounded_optimality_check import check_bounded_optimality
from checker import Session, strict_loads
from offset_repair import optimal_offsets
from optimality_check import check_optimality
from producer import Program, certificate, dred, full, potentials
from selection import (
    extend_values,
    horn_to_maxatom,
    maxatom_to_horn,
    satisfies,
    selected_witness,
)

UNBOUNDED_CASES = 3_000
BOUNDED_CASES = 3_000
CHECKER_PROGRAMS = 100
CHECKER_UPDATES_PER_PROGRAM = 20
MAXATOM_SYSTEMS = 250
MAXATOM_ASSIGNMENTS_PER_SYSTEM = 49


def _independent_fixed_point(raw: dict, base: set[int]) -> set[int]:
    model = set(base)
    while True:
        nxt = model | {
            r["head"] for r in raw["rules"] if set(r["body"]) <= model
        }
        if nxt == model:
            return model
        model = nxt


def _pin_feasible(n: int, edges: list[tuple[int, int, int]], old: list[int], pin: list[int]) -> bool:
    """Bellman-Ford feasibility test for reduced constraints plus y_i=0 pins."""
    anchor = n
    strongest: dict[tuple[int, int], int] = {}
    for u, v, w in edges:
        reduced = w + old[u] - old[v]
        strongest[u, v] = max(strongest.get((u, v), reduced), reduced)
    for i in pin:
        strongest[anchor, i] = max(strongest.get((anchor, i), 0), 0)
        strongest[i, anchor] = max(strongest.get((i, anchor), 0), 0)
    constraints = [(u, v, w) for (u, v), w in strongest.items()]
    value = [0] * (n + 1)
    for _ in range(n + 1):
        changed = False
        for u, v, w in constraints:
            if value[v] < value[u] + w:
                value[v] = value[u] + w
                changed = True
        if not changed:
            return True
    return False


def _independent_unbounded_optimum(n: int, edges: list[tuple[int, int, int]], old: list[int]) -> int | None:
    largest_unchanged = -1
    for mask in range(1 << n):
        pin = [i for i in range(n) if mask & (1 << i)]
        if len(pin) > largest_unchanged and _pin_feasible(n, edges, old, pin):
            largest_unchanged = len(pin)
    return None if largest_unchanged < 0 else n - largest_unchanged


def _random_program(seed: int, n: int = 8, m: int = 32) -> tuple[dict, set[int], random.Random]:
    rng = random.Random(seed)
    rules = []
    for _ in range(m):
        head = rng.randrange(n)
        body_size = rng.randrange(0, 4)
        body = sorted(rng.sample(range(n), body_size))
        rules.append({"head": head, "body": body})
    raw = {"n": n, "rules": rules, "blocks": list(range(n)), "local": [0] * n}
    base = {i for i in range(n) if rng.random() < 0.3}
    return raw, base, rng


class IndependentAuditTests(unittest.TestCase):

    def test_strict_input_contracts(self) -> None:
        with self.assertRaises(ValueError):
            strict_loads(b"{}")
        with self.assertRaises(ValueError):
            strict_loads('{"x": 1, "x": 2}')
        raw = {"n": 1, "rules": [], "blocks": [0], "local": [0]}
        Session(raw, [0], [0], {"0": -1}, [0])
        bad = dict(raw)
        bad["producer_hint"] = []
        with self.assertRaises(ValueError):
            Session(bad, [0], [0], {"0": -1}, [0])

    def test_malformed_optimizer_inputs_raise_value_error(self) -> None:
        malformed_unbounded = [
            (2, None, [0, 0]),
            (2, [7], [0, 0]),
            (2, [(0, 1, 1)], None),
        ]
        for args in malformed_unbounded:
            with self.assertRaises(ValueError):
                optimal_offsets(*args)
        malformed_bounded = [
            (2, None, [0, 0], [0, 0], [1, 1]),
            (2, [7], [0, 0], [0, 0], [1, 1]),
            (2, [], None, [0, 0], [1, 1]),
            (2, [], [0, 0], None, [1, 1]),
        ]
        for args in malformed_bounded:
            with self.assertRaises(ValueError):
                optimal_bounded_offsets(*args)

    def test_unbounded_optimizer_against_subset_oracle(self) -> None:
        rng = random.Random(20260916)
        checked = 0
        for _ in range(UNBOUNDED_CASES):
            n = 4
            edges = [
                (u, v, rng.randint(-3, 3))
                for u in range(n)
                for v in range(n)
                if rng.random() < 0.22
            ]
            old = [rng.randint(-3, 3) for _ in range(n)]
            optimum = _independent_unbounded_optimum(n, edges, old)
            try:
                result = optimal_offsets(n, edges, old)
            except ValueError:
                self.assertIsNone(optimum)
            else:
                self.assertIsNotNone(optimum)
                self.assertEqual(result["changed_fields"], optimum)
                self.assertTrue(
                    check_optimality(
                        n, edges, old, result["offsets"], result["certificate"]
                    )
                )
            checked += 1
        self.assertEqual(checked, UNBOUNDED_CASES)

    def test_bounded_optimizer_against_box_enumeration(self) -> None:
        rng = random.Random(20260917)
        checked = 0
        for _ in range(BOUNDED_CASES):
            n = 4
            edges = [
                (u, v, rng.randint(-2, 2))
                for u in range(n)
                for v in range(n)
                if rng.random() < 0.18
            ]
            old = [rng.randint(-2, 2) for _ in range(n)]
            lower, upper = [], []
            for _i in range(n):
                lo = rng.randint(-2, 1)
                hi = rng.randint(lo, 2)
                lower.append(lo)
                upper.append(hi)
            optimum: int | None = None
            domains = [range(lo, hi + 1) for lo, hi in zip(lower, upper)]
            for vector in itertools.product(*domains):
                if all(vector[v] - vector[u] >= w for u, v, w in edges):
                    changes = sum(vector[i] != old[i] for i in range(n))
                    optimum = changes if optimum is None else min(optimum, changes)
            try:
                result = optimal_bounded_offsets(n, edges, old, lower, upper)
            except ValueError:
                self.assertIsNone(optimum)
            else:
                self.assertIsNotNone(optimum)
                self.assertEqual(result["changed_fields"], optimum)
                self.assertTrue(
                    check_bounded_optimality(
                        n,
                        edges,
                        old,
                        lower,
                        upper,
                        result["offsets"],
                        result["certificate"],
                    )
                )
            checked += 1
        self.assertEqual(checked, BOUNDED_CASES)

    def test_random_multibody_updates_and_transactional_rejection(self) -> None:
        updates = 0
        for seed in range(CHECKER_PROGRAMS):
            raw, base, rng = _random_program(seed)
            program = Program(raw)
            model, witness, _ = full(program, base)
            self.assertEqual(model, _independent_fixed_point(raw, base))
            offsets, error = potentials(program, model, witness)
            self.assertIsNotNone(offsets, error)
            session = Session(
                raw,
                sorted(base),
                sorted(model),
                {str(head): rule for head, rule in witness.items()},
                offsets,
            )
            for _step in range(CHECKER_UPDATES_PER_PROGRAM):
                new_base = {i for i in range(raw["n"]) if rng.random() < 0.3}
                removed, added = base - new_base, new_base - base
                new_model, new_witness, _ = dred(
                    program, model, witness, base, removed, added
                )
                truth = _independent_fixed_point(raw, new_base)
                self.assertEqual(new_model, truth)
                packet, error = certificate(
                    program, model, witness, offsets, new_model, new_witness
                )
                self.assertIsNotNone(packet, error)

                before = session.inspect()
                bad = copy.deepcopy(packet)
                if bad["delete"]:
                    bad["delete"] = bad["delete"][:-1]
                elif bad["insert"]:
                    bad["insert"] = bad["insert"][:-1]
                else:
                    bad["unexpected"] = 0
                verdict = session.check(sorted(removed), sorted(added), bad)
                self.assertFalse(verdict.accepted)
                self.assertEqual(session.inspect(), before)

                verdict = session.check(sorted(removed), sorted(added), packet)
                self.assertTrue(verdict.accepted, verdict.reason)
                self.assertEqual(session.model, truth)
                base, model, witness, offsets = (
                    new_base,
                    new_model,
                    new_witness,
                    list(session.offset),
                )
                updates += 1
        self.assertEqual(updates, CHECKER_PROGRAMS * CHECKER_UPDATES_PER_PROGRAM)

    def test_random_maxatom_forward_and_reverse_equivalence(self) -> None:
        rng = random.Random(20260918)
        assignments = 0
        for _ in range(MAXATOM_SYSTEMS):
            atoms = [
                (
                    rng.randrange(2),
                    rng.randrange(2),
                    rng.randrange(2),
                    rng.randint(-2, 2),
                )
                for _j in range(rng.randint(1, 3))
            ]
            raw, base, model, _ = maxatom_to_horn(2, atoms)
            self.assertEqual(full(Program(raw), base)[0], model)
            variable_count, reverse = horn_to_maxatom(raw, base, model)
            for values in itertools.product(range(-3, 4), repeat=2):
                expected = all(
                    values[z] <= max(values[u], values[v]) + c
                    for z, u, v, c in atoms
                )
                self.assertEqual(satisfies(values, atoms), expected)
                witness = selected_witness(raw, base, model, [-x for x in values])
                self.assertEqual(witness is not None, expected)
                extended = extend_values(raw, base, model, list(values))
                self.assertEqual(len(extended), variable_count)
                self.assertEqual(satisfies(extended, reverse), expected)
                assignments += 1
        self.assertEqual(
            assignments, MAXATOM_SYSTEMS * MAXATOM_ASSIGNMENTS_PER_SYSTEM
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
