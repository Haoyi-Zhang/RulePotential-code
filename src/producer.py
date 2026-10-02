"""Ground-Horn reference producers; no checker code is imported.

The full engine uses rule counters. DRed is a fresh, transparent ground-level
implementation of delete/rederive, not RDFox, MeTeoR, or an upstream benchmark.
Potential synthesis is deliberately separate and reports incompatibility.
"""
from collections import deque


class Program:
    def __init__(self, raw):
        self.n = raw["n"]
        self.rules = [(r["head"], tuple(sorted(set(r["body"])))) for r in raw["rules"]]
        self.body = [[] for _ in range(self.n)]
        self.head = [[] for _ in range(self.n)]
        for i, (h, bs) in enumerate(self.rules):
            self.head[h].append(i)
            for b in bs:
                self.body[b].append(i)
        self.blocks = list(raw["blocks"])
        self.local = list(raw["local"])
        self.k = max(self.blocks) + 1


def full(program, base):
    known = set(base)
    why = {x: -1 for x in known}
    todo = deque(sorted(known))
    remaining = [len(body) for _, body in program.rules]
    fires = 0
    incidences = 0
    for i, (h, body) in enumerate(program.rules):
        if not body and h not in known:
            known.add(h)
            why[h] = i
            todo.append(h)
            fires += 1
    while todo:
        x = todo.popleft()
        for i in program.body[x]:
            incidences += 1
            remaining[i] -= 1
            h = program.rules[i][0]
            if remaining[i] == 0 and h not in known:
                known.add(h)
                why[h] = i
                todo.append(h)
                fires += 1
    return known, why, {"rule_initializations": len(program.rules),
                         "body_incidence_visits": incidences, "new_firings": fires}


def dred(program, old, oldwhy, base, removed, added):
    """Conservative DRed, including cyclic overdeletion and alternate proofs."""
    doomed = set(removed)
    todo = deque(sorted(doomed))
    inspected = set()
    checks = 0
    literals = 0
    while todo:
        b = todo.popleft()
        for i in program.body[b]:
            if i in inspected:
                continue
            inspected.add(i)
            h, body = program.rules[i]
            checks += 1
            literals += len(body)
            if h not in doomed and all(v in old for v in body):
                doomed.add(h)
                todo.append(h)
    known = set(old) - doomed
    why = {h: oldwhy[h] for h in known}
    newbase = (set(base) - set(removed)) | set(added)
    todo = deque()
    for h in sorted(newbase - known):
        known.add(h)
        why[h] = -1
        todo.append(h)
    # One-step rederivation examines every rule with an overdeleted head.
    # Subsequent discoveries, including inserted seeds, trigger forward work.
    for h in sorted(doomed):
        for i in program.head[h]:
            rh, body = program.rules[i]
            checks += 1
            literals += len(body)
            if rh not in known and all(v in known for v in body):
                known.add(rh)
                why[rh] = i
                todo.append(rh)
    while todo:
        b = todo.popleft()
        for i in program.body[b]:
            h, body = program.rules[i]
            checks += 1
            literals += len(body)
            if h not in known and all(v in known for v in body):
                known.add(h)
                why[h] = i
                todo.append(h)
    return known, why, {"overdeleted": len(doomed), "rule_checks": checks,
                         "body_tests_upper_bound": literals}


def potentials(program, model, why, old_offsets=None):
    """Longest-path relaxation of block constraints; return a cycle witness.

A positive block cycle or internal-order violation means this chosen proof is
not representable with this fixed partition. It does not mean non-entailment.
"""
    weights = {}
    representatives = {}
    for h in sorted(model):
        r = why[h]
        if r < 0:
            continue
        for b in program.rules[r][1]:
            u, v = program.blocks[b], program.blocks[h]
            w = program.local[b] - program.local[h] + 1
            if u == v:
                if w > 0:
                    return None, {"kind": "internal_order", "rule": r,
                                  "premise": b, "head": h}
            elif w > weights.get((u, v), -(1 << 100)):
                weights[u, v] = w
                representatives[u, v] = [r, b, h]
    offsets = [0] * program.k if old_offsets is None else list(old_offsets)
    parent = {}
    last = None
    relaxations = 0
    for iteration in range(program.k):
        last = None
        for (u, v), w in sorted(weights.items()):
            if offsets[v] < offsets[u] + w:
                offsets[v] = offsets[u] + w
                parent[v] = u
                last = v
                relaxations += 1
        if last is None:
            # Long update sequences need not accumulate unbounded translations.
            # Rebase from zero only when the bounded transport format needs it.
            if old_offsets is not None and any(abs(x) > (1 << 62) for x in offsets):
                rebased, info = potentials(program, model, why, None)
                info = dict(info, rebased=True, initial_relaxations=relaxations)
                return rebased, info
            return offsets, {"kind": "feasible", "pairs": len(weights),
                              "passes": iteration + 1, "relaxations": relaxations,
                              "rebased": False}
    v = last
    for _ in range(program.k):
        v = parent[v]
    start = v
    cycle = []
    while True:
        u = parent[v]
        cycle.append({"left": u, "right": v, "weight": weights[u, v],
                      "edge": representatives[u, v]})
        v = u
        if v == start:
            break
    return None, {"kind": "positive_cycle", "cycle": cycle,
                  "weight_sum": sum(e["weight"] for e in cycle)}


def certificate(program, old, oldwhy, oldoffset, new, newwhy):
    newoffset, evidence = potentials(program, new, newwhy, oldoffset)
    if newoffset is None:
        return None, evidence
    return {"delete": sorted(old - new), "insert": sorted(new - old),
            "witness": {str(h): newwhy[h] for h in sorted(new)
                        if h not in old or newwhy[h] != oldwhy[h]},
            "offset": {str(b): value for b, value in enumerate(newoffset)
                       if value != oldoffset[b]}}, evidence
