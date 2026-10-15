"""Same-packet full and ordinary local controls, without block-pair maxima.

Both consume the exact compressed offset packet used by Session. The local
control reuses Head/Body, selected consumers and active boundary incidences, but
checks individual rank edges instead of maintaining maximum trees. Unchanged
internal edges are translation-invariant in this control too. This is an ablation
of boundary aggregation, not an external engine or independent implementation
of the input schema: schema helpers and Verdict come from checker.
"""
from checker import BOUND, Verdict, idset, imap, integer
from reference_check import verify_all


class OrdinarySession:
    def __init__(self, raw, base, model, witness, offsets, strategy="local"):
        if strategy not in ("local", "full"):
            raise ValueError("unknown ordinary strategy")
        if type(raw) is not dict or set(raw) != {"n", "rules", "blocks", "local"}:
            raise ValueError("invalid program object")
        self.n = integer(raw["n"], 1, 200000)
        if type(raw["rules"]) is not list or len(raw["rules"]) > 1000000:
            raise ValueError("invalid rule list")
        self.rules = []
        for row in raw["rules"]:
            if type(row) is not dict or set(row) != {"head", "body"}:
                raise ValueError("invalid rule")
            h = integer(row["head"], 0, self.n - 1)
            bs = idset(row["body"], self.n)
            if len(bs) > 16:
                raise ValueError("body width exceeds 16")
            self.rules.append((h, tuple(sorted(bs))))
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
        # Own canonical immutable rules/labels, not a mutable caller reference.
        self.raw = {"n": self.n,
                    "rules": [{"head": h, "body": list(bs)} for h, bs in self.rules],
                    "blocks": self.block, "local": self.local}
        if not verify_all(self.raw, self.base, self.model, self.witness, self.offset)[0]:
            raise ValueError("invalid full initial certificate")
        self.strategy = strategy
        if strategy == "local":
            self.head_index = [[] for _ in range(self.n)]
            self.body_index = [[] for _ in range(self.n)]
            self.boundary = [set() for _ in range(self.k)]
            self.consumers = [set() for _ in range(self.n)]
            for r, (h, bs) in enumerate(self.rules):
                self.head_index[h].append(r)
                for b in bs:
                    self.body_index[b].append(r)
            for h, r in self.witness.items():
                if r >= 0:
                    for b in self.rules[r][1]:
                        self.consumers[b].add(h)
                        if self.block[b] != self.block[h]:
                            edge = (h, r, b)
                            self.boundary[self.block[b]].add(edge)
                            self.boundary[self.block[h]].add(edge)

    def check(self, removed, added, packet, commit=True):
        c = {k: 0 for k in ("truth_fields", "offset_fields", "witness_heads",
                            "witness_literals", "closure_rules", "closure_literals",
                            "rank_heads", "rank_literals", "boundary_incidence_visits",
                            "consumer_visits")}
        try:
            minus, plus = idset(removed, self.n), idset(added, self.n)
            if not minus <= self.base or plus & self.base or minus & plus:
                raise ValueError("update is not an exact disjoint base delta")
            if type(packet) is not dict or set(packet) != {"delete", "insert", "witness", "offset"}:
                raise ValueError("invalid certificate fields")
            deleted, inserted = idset(packet["delete"], self.n), idset(packet["insert"], self.n)
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

            if any(not present(h) for h in patch) or not inserted <= patch.keys():
                raise ValueError("witness patch has invalid domain")
            if any(not present(x) for x in plus) or any(seed(x) for x in deleted):
                raise ValueError("new base not included")

            if self.strategy == "full":
                nb = (self.base - minus) | plus
                nm = (self.model - deleted) | inserted
                nw = {h: r for h, r in self.witness.items() if h not in deleted}
                nw.update(patch)
                no = list(self.offset)
                for b, value in opatch.items():
                    no[b] = value
                ok, vc = verify_all(self.raw, nb, nm, nw, no)
                c.update(vc)
                if not ok:
                    raise ValueError("full ranked-model check failed")
                if commit:
                    self.base, self.model, self.witness, self.offset = nb, nm, nw, no
                return Verdict(True, "accepted", c)

            needs = set(patch) | inserted
            needs.update(h for h in minus if self.witness.get(h) == -1)
            for b in deleted:
                needs.update(self.consumers[b])
                c["consumer_visits"] += len(self.consumers[b])
            for h in sorted(needs):
                if not present(h):
                    continue
                c["witness_heads"] += 1
                r = witness_for(h)
                if r is None:
                    raise ValueError("missing witness")
                if r == -1:
                    if not seed(h):
                        raise ValueError("invalid seed witness")
                else:
                    rh, bs = self.rules[r]
                    if rh != h:
                        raise ValueError("wrong witness head")
                    for b in bs:
                        c["witness_literals"] += 1
                        if not present(b):
                            raise ValueError("missing witness premise")
            closure = set()
            for h in deleted:
                closure.update(self.head_index[h])
            for b in inserted:
                closure.update(self.body_index[b])
            for r in sorted(closure):
                h, bs = self.rules[r]
                c["closure_rules"] += 1
                active = True
                for b in bs:
                    c["closure_literals"] += 1
                    if not present(b):
                        active = False
                        break
                if active and not present(h):
                    raise ValueError("new model is not closed")

            # Same partition information as Session: unchanged internal edges
            # cancel their offset. A direct active-incidence index avoids a scan
            # of either the full blocks or inactive potential boundary slots.
            rank_edges = set()
            for h in set(patch) | inserted:
                r = witness_for(h)
                if r is not None and r >= 0:
                    rank_edges.update((h, r, b) for b in self.rules[r][1])
            for group in opatch:
                for h, r, b in self.boundary[group]:
                    c["boundary_incidence_visits"] += 1
                    if present(h) and witness_for(h) == r:
                        rank_edges.add((h, r, b))
            c["rank_heads"] = len({h for h, _, _ in rank_edges})
            for h, _, b in sorted(rank_edges):
                c["rank_literals"] += 1
                rh = opatch.get(self.block[h], self.offset[self.block[h]]) + self.local[h]
                rb = opatch.get(self.block[b], self.offset[self.block[b]]) + self.local[b]
                if rb >= rh:
                    raise ValueError("rank inequality violated")
            if commit:
                for h in deleted | set(patch):
                    old, new = self.witness.get(h), None if h in deleted else patch[h]
                    if old != new:
                        if old is not None and old >= 0:
                            for b in self.rules[old][1]:
                                self.consumers[b].discard(h)
                                if self.block[b] != self.block[h]:
                                    edge = (h, old, b)
                                    self.boundary[self.block[b]].discard(edge)
                                    self.boundary[self.block[h]].discard(edge)
                        if new is not None and new >= 0:
                            for b in self.rules[new][1]:
                                self.consumers[b].add(h)
                                if self.block[b] != self.block[h]:
                                    edge = (h, new, b)
                                    self.boundary[self.block[b]].add(edge)
                                    self.boundary[self.block[h]].add(edge)
                self.base.difference_update(minus)
                self.base.update(plus)
                self.model.difference_update(deleted)
                self.model.update(inserted)
                for h in deleted:
                    del self.witness[h]
                self.witness.update(patch)
                for b, value in opatch.items():
                    self.offset[b] = value
            return Verdict(True, "accepted", c)
        except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
            # No persistent value is touched before acceptance in either mode.
            return Verdict(False, str(exc), c)
