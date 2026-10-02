"""Deterministic, benign finite Horn workloads. All updates are generated."""
import random


def exchange(length=32, grouped=True):
    """Two temporal chains with alternate cross-support at the first tick."""
    n = 2 * (length + 1)
    b0 = length + 1
    rules = []
    for start in [0, b0]:
        for t in range(1, length + 1):
            rules.append({"head": start + t, "body": [start + t - 1]})
    rules += [{"head": 1, "body": [b0 + length]},
              {"head": b0 + 1, "body": [length]}]
    return {"n": n, "rules": rules,
            "blocks": [int(i >= b0) for i in range(n)] if grouped else list(range(n)),
            "local": [i % b0 for i in range(n)] if grouped else [0] * n}, {0, b0}


def unary_program(n, mask):
    candidates = [{"head": h, "body": [b]} for h in range(n) for b in range(n)]
    return {"n": n, "rules": [r for i, r in enumerate(candidates) if mask & (1 << i)],
            "blocks": list(range(n)), "local": [0] * n}


def random_program(n, seed, width=3, density=3):
    rng = random.Random(seed)
    rules = []
    for _ in range(n * density):
        h = rng.randrange(n)
        bs = sorted(rng.sample(range(n), rng.randrange(min(width, n) + 1)))
        rules.append({"head": h, "body": bs})
    base = set(rng.sample(range(n), max(1, n // 4)))
    return {"n": n, "rules": rules, "blocks": list(range(n)), "local": [0] * n}, base


def fanin(length=32):
    # Deleting the only live support requires examining the alternative heads.
    h = length + 1
    return {"n": length + 2, "rules": [{"head": h, "body": [i]} for i in range(length + 1)],
            "blocks": list(range(length + 2)), "local": [0] * (length + 2)}, {0}


def all_subsets(n):
    for mask in range(1 << n):
        yield {i for i in range(n) if mask & (1 << i)}


def alternate_star(n):
    """Two seed alternatives for each head; witness repair is not compressible
    in the explicit one-entry-per-head interface even though truth delta is 1.
    """
    rules=[]
    for h in range(2,n+2):
        rules += [{'head':h,'body':[0]}, {'head':h,'body':[1]}]
    return {'n':n+2,'rules':rules,'blocks':[0,0]+[1]*n,
            'local':[0]*(n+2)}, {0,1}


def inactive_fanin(n):
    """Only the head is a seed. Its deletion visits n inactive alternative rules."""
    return {'n':n+1,'rules':[{'head':n,'body':[i]} for i in range(n)],
            'blocks':list(range(n+1)),'local':[0]*(n+1)}, {n}
