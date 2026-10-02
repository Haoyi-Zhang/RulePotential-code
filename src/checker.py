"""Independent checker for finite Horn update certificates.

No producer, fixed-point engine or workload generator is imported here.  A
session is initialized by checking a complete closed, ranked materialisation.
Subsequent updates use trusted incidence indexes and reversible maximum trees.
The input universe, rules, partition, and local labels are fixed per session.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable
import json

NEG = -(1 << 100)
BOUND = 1 << 62


def integer(x: Any, lo: int, hi: int) -> int:
    if type(x) is not int or not lo <= x <= hi:
        raise ValueError("integer out of range or wrong type")
    return x


def idset(xs: Any, n: int) -> set[int]:
    if type(xs) is not list:
        raise ValueError("expected a list")
    out = {integer(x, 0, n - 1) for x in xs}
    if len(out) != len(xs):
        raise ValueError("duplicate identifier")
    return out


def imap(obj: Any, n: int, vlo: int, vhi: int) -> dict[int, int]:
    if type(obj) is not dict:
        raise ValueError("expected an object")
    out = {}
    for key, value in obj.items():
        if type(key) is not str or not key.isascii() or not key.isdecimal():
            raise ValueError("non-canonical map key")
        i = int(key)
        if str(i) != key:
            raise ValueError("non-canonical map key")
        integer(i, 0, n - 1)
        out[i] = integer(value, vlo, vhi)
    return out


def strict_loads(text: str) -> Any:
    """Reject duplicate object keys, non-finite constants and oversized packets."""
    if type(text) is not str:
        raise ValueError("JSON packet must be text")
    if len(text.encode("utf-8")) > 64 * 1024 * 1024:
        raise ValueError("packet exceeds 64 MiB")
    def pairs(rows):
        out = {}
        for k, v in rows:
            if k in out:
                raise ValueError("duplicate object key")
            out[k] = v
        return out
    def bad_constant(_):
        raise ValueError("non-finite JSON constant")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant)


class MaximumTree:
    """Static slots, reversible point changes; no lazy garbage or hash trust."""
    def __init__(self, length: int):
        self.size = 1
        while self.size < length:
            self.size *= 2
        self.values = [NEG] * (2 * self.size)

    def assign(self, slot: int, value: int) -> tuple[int, int]:
        p = self.size + slot
        old = self.values[p]
        self.values[p] = value
        steps = 1
        p //= 2
        while p:
            self.values[p] = max(self.values[2 * p], self.values[2 * p + 1])
            p //= 2
            steps += 1
        return old, steps

    @property
    def maximum(self) -> int:
        return self.values[1]


@dataclass
class Verdict:
    accepted: bool
    reason: str
    counters: dict[str, int] = field(default_factory=dict)


class Session:
    def __init__(self, raw: dict, base: list[int], model: list[int],
                 witness: dict[str, int], offsets: list[int]):
        if type(raw) is not dict or set(raw) != {"n", "rules", "blocks", "local"}:
            raise ValueError("invalid program object")
        self.n = integer(raw["n"], 1, 200000)
        if type(raw["rules"]) is not list or len(raw["rules"]) > 1000000:
            raise ValueError("invalid rule list")
        self.rules: list[tuple[int, tuple[int, ...]]] = []
        self.head_index = [[] for _ in range(self.n)]
        self.body_index = [[] for _ in range(self.n)]
        for r, row in enumerate(raw["rules"]):
            if type(row) is not dict or set(row) != {"head", "body"}:
                raise ValueError("invalid rule")
            head = integer(row["head"], 0, self.n - 1)
            body = idset(row["body"], self.n)
            if len(body) > 16:
                raise ValueError("body width exceeds 16")
            terms = tuple(sorted(body))
            self.rules.append((head, terms))
            self.head_index[head].append(r)
            for b in terms:
                self.body_index[b].append(r)
        if type(raw["blocks"]) is not list or type(raw["local"]) is not list:
            raise ValueError("invalid partition")
        if len(raw["blocks"]) != self.n or len(raw["local"]) != self.n:
            raise ValueError("partition length mismatch")
        self.block = [integer(b, 0, self.n - 1) for b in raw["blocks"]]
        self.k = max(self.block) + 1
        if set(self.block) != set(range(self.k)):
            raise ValueError("blocks must be contiguous and nonempty")
        self.local = [integer(v, 0, (1 << 31) - 1) for v in raw["local"]]
        if type(offsets) is not list or len(offsets) != self.k:
            raise ValueError("offset length mismatch")
        self.offset = [integer(v, -BOUND, BOUND) for v in offsets]
        self.base = idset(base, self.n)
        self.model = idset(model, self.n)
        self.witness = imap(witness, self.n, -1, len(self.rules) - 1)
        if set(self.witness) != self.model or not self.base <= self.model:
            raise ValueError("incomplete initialization")
        for head in self.model:
            r = self.witness[head]
            if r == -1:
                if head not in self.base:
                    raise ValueError("unsupported base witness")
            else:
                rh, body = self.rules[r]
                if rh != head or not set(body) <= self.model:
                    raise ValueError("invalid initialization witness")
                rank_h = self.offset[self.block[head]] + self.local[head]
                for b in body:
                    if self.offset[self.block[b]] + self.local[b] >= rank_h:
                        raise ValueError("initialization is not well founded")
        for head, body in self.rules:
            if all(b in self.model for b in body) and head not in self.model:
                raise ValueError("initialization is not closed")

        # Universe-level slots are constructed by the checker, not accepted from
        # a certificate. Selected proof edges, not all rule edges, are active.
        slots = defaultdict(list)
        for r, (head, body) in enumerate(self.rules):
            for j, b in enumerate(body):
                pair = self.block[b], self.block[head]
                if pair[0] != pair[1]:
                    weight = self.local[b] - self.local[head] + 1
                    slots[pair].append((r, j, weight))
        self.trees: dict[tuple[int, int], MaximumTree] = {}
        self.rule_slots = [[] for _ in self.rules]
        for pair, rows in slots.items():
            tree = MaximumTree(len(rows))
            self.trees[pair] = tree
            for slot, (r, _, weight) in enumerate(rows):
                self.rule_slots[r].append((pair, slot, weight))
                head = self.rules[r][0]
                if self.witness.get(head) == r:
                    tree.values[tree.size + slot] = weight
            # Bottom-up initialization is linear in the static slot count.
            for node in range(tree.size - 1, 0, -1):
                tree.values[node] = max(tree.values[2 * node], tree.values[2 * node + 1])
        self.active_neighbours = [set() for _ in range(self.k)]
        for pair, tree in self.trees.items():
            if tree.maximum != NEG:
                self.active_neighbours[pair[0]].add(pair)
                self.active_neighbours[pair[1]].add(pair)
        self.consumers = [set() for _ in range(self.n)]
        for h, r in self.witness.items():
            if r >= 0:
                for b in self.rules[r][1]:
                    self.consumers[b].add(h)

    def inspect(self) -> dict:
        """Full diagnostic export, NOT called in the timed update path."""
        return {"base": sorted(self.base), "model": sorted(self.model),
                "witness": {str(h): r for h, r in sorted(self.witness.items())},
                "offset": list(self.offset),
                "maxima": [[*p, t.maximum] for p, t in sorted(self.trees.items())],
                "consumers": [sorted(s) for s in self.consumers],
                "active": [sorted(s) for s in self.active_neighbours]}

    def check(self, removed: list[int], added: list[int], packet: dict,
              commit: bool = True) -> Verdict:
        c = {key: 0 for key in ["truth_fields", "witness_heads", "witness_literals",
             "closure_rules", "closure_literals", "offset_fields", "pair_checks",
             "segment_updates", "segment_steps"]}
        undo: list[tuple[tuple[int, int], int, int]] = []
        def rollback():
            for pair, slot, old in reversed(undo):
                self.trees[pair].assign(slot, old)
        try:
            minus, plus = idset(removed, self.n), idset(added, self.n)
            if not minus <= self.base or plus & self.base or minus & plus:
                raise ValueError("update is not an exact disjoint base delta")
            if type(packet) is not dict or set(packet) != {"delete", "insert", "witness", "offset"}:
                raise ValueError("invalid certificate fields")
            deleted = idset(packet["delete"], self.n)
            inserted = idset(packet["insert"], self.n)
            patch = imap(packet["witness"], self.n, -1, len(self.rules) - 1)
            opatch = imap(packet["offset"], self.k, -BOUND, BOUND)
            c["truth_fields"] = len(deleted) + len(inserted)
            c["offset_fields"] = len(opatch)
            if not deleted <= self.model or inserted & self.model or deleted & inserted:
                raise ValueError("invalid truth delta")
            def present(x):
                return x in inserted or (x in self.model and x not in deleted)
            def seed(x):
                return x in plus or (x in self.base and x not in minus)
            def witness_for(x):
                return patch[x] if x in patch else self.witness.get(x)
            if any(not present(x) for x in patch) or not inserted <= patch.keys():
                raise ValueError("witness patch has invalid domain")
            if any(not present(x) for x in plus) or any(seed(x) for x in deleted):
                raise ValueError("new base not included")
            needs = set(patch) | inserted
            for x in minus:
                if self.witness.get(x) == -1:
                    needs.add(x)
            for x in deleted:
                needs.update(self.consumers[x])
            for h in sorted(needs):
                if not present(h):
                    continue
                c["witness_heads"] += 1
                r = witness_for(h)
                if r is None:
                    raise ValueError("missing witness")
                if r == -1:
                    if not seed(h):
                        raise ValueError("revoked or invented seed witness")
                    continue
                rh, body = self.rules[r]
                if rh != h:
                    raise ValueError("wrong witness head")
                for b in body:
                    c["witness_literals"] += 1
                    if not present(b):
                        raise ValueError("missing witness premise")
                    if self.block[b] == self.block[h] and self.local[b] >= self.local[h]:
                        raise ValueError("infeasible internal block edge")

            closure = set()
            for h in deleted:
                closure.update(self.head_index[h])
            for b in inserted:
                closure.update(self.body_index[b])
            for r in sorted(closure):
                h, body = self.rules[r]
                c["closure_rules"] += 1
                active = True
                for b in body:
                    c["closure_literals"] += 1
                    if not present(b):
                        active = False
                        break
                if active and not present(h):
                    raise ValueError("new model is not closed")

            changes = {}
            for h in deleted:
                changes[h] = (self.witness[h], None)
            for h, r in patch.items():
                old = self.witness.get(h)
                if old != r:
                    changes[h] = (old, r)
            touched = set()
            for h, (old, new) in sorted(changes.items()):
                for r, enabled in [(old, False), (new, True)]:
                    if r is None or r < 0:
                        continue
                    for pair, slot, weight in self.rule_slots[r]:
                        before, steps = self.trees[pair].assign(slot, weight if enabled else NEG)
                        undo.append((pair, slot, before))
                        touched.add(pair)
                        c["segment_updates"] += 1
                        c["segment_steps"] += steps
            pairs_to_check = set(touched)
            for b in opatch:
                pairs_to_check.update(self.active_neighbours[b])
            for left, right in sorted(pairs_to_check):
                weight = self.trees[(left, right)].maximum
                if weight == NEG:
                    continue
                c["pair_checks"] += 1
                lhs = opatch.get(right, self.offset[right]) - opatch.get(left, self.offset[left])
                if lhs < weight:
                    raise ValueError("rank inequality violated")
            if not commit:
                rollback()
                return Verdict(True, "accepted without commit", c)

            # The public state changes only after all checks succeeded.
            # The maximum-tree journal has already performed exactly the
            # selected-edge updates. A rejected packet rolls it back in full.
            for h, (old, new) in changes.items():
                if old is not None and old >= 0:
                    for b in self.rules[old][1]:
                        self.consumers[b].discard(h)
                if new is not None and new >= 0:
                    for b in self.rules[new][1]:
                        self.consumers[b].add(h)
            self.model.difference_update(deleted)
            self.model.update(inserted)
            self.base.difference_update(minus)
            self.base.update(plus)
            for h in deleted:
                del self.witness[h]
            self.witness.update(patch)
            for b, value in opatch.items():
                self.offset[b] = value
            for pair in touched:
                for b in pair:
                    if self.trees[pair].maximum == NEG:
                        self.active_neighbours[b].discard(pair)
                    else:
                        self.active_neighbours[b].add(pair)
            return Verdict(True, "accepted", c)
        except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
            rollback()
            return Verdict(False, str(exc), c)
