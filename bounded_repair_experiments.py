#!/usr/bin/env python3
"""Exact bounded-integer oracle for minimum changed offset fields.

The campaign uses all 4^6 directed three-block graphs with edge weights in
{-1,0,1} or absent, all 27 old vectors in {-1,0,1}^3, and three fixed interval
profiles.  The oracle enumerates every vector in each finite box and evaluates
raw inequalities; it imports neither the optimizer nor its closure/matching
logic.  Published outputs are never overwritten.
"""
import argparse
import itertools
import json
import resource
import sys
import time
from pathlib import Path
from run_environment import capture_environment

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from bounded_offset_repair import optimal_bounded_offsets
from bounded_optimality_check import check_bounded_optimality

PROFILES = [
    ('symmetric', [-1, -1, -1], [1, 1, 1]),
    ('upper-skew', [0, -1, 0], [1, 0, 1]),
    ('lower-skew', [-1, 0, -1], [0, 1, 0]),
]


def deterministic_view(data):
    return {k: v for k, v in data.items() if k not in {'cpu_seconds', 'wall_seconds', 'peak_rss_kib', 'environment'}}


def campaign():
    started_wall = time.monotonic()
    started_cpu = time.process_time()
    pairs = [(i, j) for i in range(3) for j in range(3) if i != j]
    old_vectors = [list(v) for v in itertools.product(range(-1, 2), repeat=3)]
    candidates = {
        name: [list(v) for v in itertools.product(*(range(lo, hi + 1) for lo, hi in zip(lower, upper)))]
        for name, lower, upper in PROFILES
    }
    counts = {
        'graphs': 0,
        'interval_profiles': len(PROFILES),
        'graph_profile_pairs': 0,
        'graph_profile_feasible': 0,
        'cases': 0,
        'feasible_cases': 0,
        'infeasible_cases': 0,
        'optimizer_mismatches': 0,
        'certificate_failures': 0,
        'optimum_histogram': {str(i): 0 for i in range(4)},
        'profile_counts': {
            name: {'cases': 0, 'feasible_cases': 0, 'infeasible_cases': 0,
                   'optimum_histogram': {str(i): 0 for i in range(4)}}
            for name, _, _ in PROFILES
        },
    }
    for weights in itertools.product([None, -1, 0, 1], repeat=6):
        edges = [(i, j, w) for (i, j), w in zip(pairs, weights) if w is not None]
        counts['graphs'] += 1
        for name, lower, upper in PROFILES:
            feasible = [v for v in candidates[name]
                        if all(v[j] - v[i] >= w for i, j, w in edges)]
            counts['graph_profile_pairs'] += 1
            counts['graph_profile_feasible'] += bool(feasible)
            profile = counts['profile_counts'][name]
            for old in old_vectors:
                counts['cases'] += 1
                profile['cases'] += 1
                try:
                    answer = optimal_bounded_offsets(3, edges, old, lower, upper)
                except ValueError:
                    if feasible:
                        raise AssertionError(('false bounded infeasibility', edges, old, lower, upper))
                    counts['infeasible_cases'] += 1
                    profile['infeasible_cases'] += 1
                    continue
                if not feasible:
                    raise AssertionError(('false bounded feasibility', edges, old, lower, upper, answer))
                exact = min(sum(a != b for a, b in zip(old, v)) for v in feasible)
                if answer['changed_fields'] != exact:
                    counts['optimizer_mismatches'] += 1
                    raise AssertionError(('wrong bounded optimum', edges, old, lower, upper, answer, exact))
                if not check_bounded_optimality(
                        3, edges, old, lower, upper, answer['offsets'], answer['certificate']):
                    counts['certificate_failures'] += 1
                    raise AssertionError(('bounded certificate rejected', edges, old, lower, upper, answer))
                counts['feasible_cases'] += 1
                profile['feasible_cases'] += 1
                counts['optimum_histogram'][str(exact)] += 1
                profile['optimum_histogram'][str(exact)] += 1
    usage = resource.getrusage(resource.RUSAGE_SELF)
    counts['cpu_seconds'] = time.process_time() - started_cpu
    counts['wall_seconds'] = time.monotonic() - started_wall
    counts['peak_rss_kib'] = usage.ru_maxrss
    return counts


def main():
    # Match the standalone repair campaign's explicit resource envelope.
    resource.setrlimit(resource.RLIMIT_CPU, (35, 35))
    resource.setrlimit(resource.RLIMIT_AS, (3_500_000_000, 3_500_000_000))
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('output exists; choose a fresh path')
    environment = capture_environment()
    result = campaign()
    result['environment'] = environment
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    if args.compare:
        expected = json.loads(args.compare.read_text())
        if deterministic_view(result) != deterministic_view(expected):
            raise SystemExit('deterministic bounded-oracle comparison failed')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
