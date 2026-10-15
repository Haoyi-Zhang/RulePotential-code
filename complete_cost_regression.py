"""Untimed tests for same-information controls and complete-cost accounting."""
import copy
import itertools
import unittest
from unittest.mock import patch

import complete_cost as study
from cases import exchange, unary_program
from checker import Session
from ordinary_check import OrdinarySession
from producer import Program, certificate, dred, full, potentials


def oracle(raw, base):
    common = set(range(raw["n"]))
    for bits in itertools.product((False, True), repeat=raw["n"]):
        candidate = {a for a, bit in enumerate(bits) if bit}
        if base <= candidate and all(not set(r["body"]) <= candidate or r["head"] in candidate
                                     for r in raw["rules"]):
            common &= candidate
    return common


class CompleteCostRegression(unittest.TestCase):
    def test_complete_untimed_traces(self):
        for case in study.cases(True):
            result = study.trace(case, 0, study.Clock(False))
            self.assertEqual(len(result["updates"]), 12)
            self.assertTrue(all(c["accepted"] for r in result["updates"] for c in r["checks"].values()))
            self.assertTrue(all(c["check_commit_ns"] is None for r in result["updates"]
                                for c in r["checks"].values()))
        result = study.fallback_trial(0, study.Clock(False))
        self.assertEqual(result["obstruction"]["weight_sum"], 4)
        self.assertEqual(set(result["consumers"]), set(study.MODES))

    def test_candidate_packets_against_closed_intersections(self):
        # Every two-atom unary program, old/new base and candidate truth set;
        # every applicable witness/seed choice and offsets in {0,1,2}^2.
        # Invalid witnesses remain in the search, not filtered by the oracle.
        count = accepted = 0
        sets = [{a for a in range(2) if mask >> a & 1} for mask in range(4)]
        for mask in range(16):
            raw = unary_program(2, mask)
            pg = Program(raw)
            for base in sets:
                m, w, _ = full(pg, base)
                self.assertEqual(m, oracle(raw, base))
                o, _ = potentials(pg, m, w)
                sessions = [study.make_session(mode, raw, base, m, w, o) for mode in study.MODES]
                before = [study.signature(s) for s in sessions]
                for nb in sets:
                    expected = oracle(raw, nb)
                    for nm in sets:
                        heads = sorted(nm)
                        choices = [[-1] + [r for r, row in enumerate(raw["rules"]) if row["head"] == h]
                                   for h in heads]
                        for selected in itertools.product(*choices):
                            for no in itertools.product(range(3), repeat=2):
                                packet = {"delete": sorted(m - nm), "insert": sorted(nm - m),
                                          "witness": {str(h): r for h, r in zip(heads, selected)},
                                          "offset": {str(b): x for b, x in enumerate(no)}}
                                statuses = [s.check(sorted(base - nb), sorted(nb - base), packet,
                                                    commit=False).accepted for s in sessions]
                                self.assertEqual(len(set(statuses)), 1)
                                if statuses[0]:
                                    self.assertEqual(nm, expected)
                                    accepted += 1
                                count += 1
                self.assertEqual(before, [study.signature(s) for s in sessions])
        # Sum over each head's two possible rules: 2+2*3+4=12;
        # 12^2 programs/choices * 16 base transitions * 9 offset vectors.
        self.assertEqual(count, 20736)
        self.assertGreater(accepted, 0)

    def test_translated_premise_rechecks_unchanged_consumer(self):
        raw = {"n": 3, "rules": [{"head": 1, "body": [0]}, {"head": 2, "body": [1]}],
               "blocks": [0, 1, 2], "local": [0, 0, 0]}
        pg = Program(raw)
        m, w, _ = full(pg, {0})
        for mode in study.MODES:
            s = study.make_session(mode, raw, {0}, m, w, [0, 1, 2])
            before = study.signature(s)
            packet = {"delete": [], "insert": [], "witness": {}, "offset": {"1": 5}}
            self.assertFalse(s.check([], [], packet).accepted)
            self.assertEqual(before, study.signature(s))
            packet["offset"]["2"] = 6
            self.assertTrue(s.check([], [], packet).accepted)

    def test_boundary_multiplicity_not_block_population_drives_ablation(self):
        for family in ("exchange", "boundary"):
            case = {"family": family, "size": 8, "partition": "native"}
            row = study.trace(case, 0, study.Clock(False))["updates"][0]
            plain = row["checks"]["ordinary-local"]["counters"]
            block = row["checks"]["block"]["counters"]
            self.assertEqual(row["offset_fields"], 1)
            self.assertEqual(plain["rank_literals"], 1 if family == "exchange" else 9)
            self.assertEqual(block["pair_checks"], 1 if family == "exchange" else 2)

    def test_rejection_restores_all_tree_values_and_valid_followup(self):
        raw, base = exchange(5)
        pg = Program(raw)
        m, w, _ = full(pg, base)
        o, _ = potentials(pg, m, w)
        nm, nw, _ = dred(pg, m, w, base, {0}, set())
        good, _ = certificate(pg, m, w, o, nm, nw)
        bad, kind = study.rank_mutation(raw, good, nm, nw)
        self.assertEqual(kind, "rank-after-provisional-changes")
        for mode in study.MODES:
            s = study.make_session(mode, raw, base, m, w, o)
            before = study.signature(s)
            self.assertFalse(s.check([0], [], bad).accepted)
            self.assertEqual(before, study.signature(s))
            self.assertTrue(s.check([0], [], good).accepted)
            self.assertEqual(s.model, nm)

    def test_policy_noops_and_real_changes_are_not_mixed(self):
        for case in study.cases(True):
            t = study.trace(case, 0, study.Clock(False))
            noops = [r for r in t["updates"] if r["semantic_noop"]]
            self.assertEqual(len(noops), 3 if case["family"] == "policy" else 1)
            self.assertTrue(all(r["truth_fields"] == 0 for r in noops))
            if case["family"] == "policy":
                self.assertTrue(all(r["offset_fields"] == 0 for r in t["updates"]))

    def test_initial_schema_contract_and_caller_isolation(self):
        raw, base = exchange(3)
        pg = Program(raw)
        m, w, _ = full(pg, base)
        o, _ = potentials(pg, m, w)
        for mode in study.MODES:
            bad = copy.deepcopy(raw)
            bad["rules"][0]["body"] = [False]
            with self.assertRaises(ValueError):
                study.make_session(mode, bad, base, m, w, o)
            s = study.make_session(mode, raw, base, m, w, o)
            old = study.signature(s)
            packet = {"delete": [], "insert": [], "witness": {}, "offset": {"00": 0}}
            self.assertFalse(s.check([], [], packet).accepted)
            self.assertEqual(study.signature(s), old)
        saved = copy.deepcopy(raw)
        for strategy in ("local", "full"):
            s = OrdinarySession(raw, sorted(base), sorted(m), {str(h): r for h, r in w.items()}, o, strategy)
            s.raw["rules"][0]["body"].append(999)
            self.assertEqual(raw, saved)

    def test_check_mode_does_not_read_a_clock(self):
        with patch.object(study.time, "perf_counter_ns", side_effect=RuntimeError("timer called")):
            study.trace(study.cases(True)[0], 0, study.Clock(False))
            study.fallback_trial(0, study.Clock(False))


if __name__ == "__main__":
    unittest.main()
