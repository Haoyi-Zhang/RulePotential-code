"""Exact minimum-field repair for a FIXED feasible block-constraint graph.

This is a bounded reference specialization of violator-order / L0 isotonic
methods, not a solver for choosing witnesses or partitions. All integers are
mathematical Python integers; callers must check transport bounds separately.
"""
from collections import deque
from typing import Sequence

Edge = tuple[int, int, int]
MAX_BLOCKS = 256


def _input(n: int, edges: Sequence[Edge], old: Sequence[int]) -> list[Edge]:
    if type(n) is not int or not 1 <= n <= MAX_BLOCKS:
        raise ValueError('block count outside reference bound')
    if not isinstance(old, (tuple, list)) or len(old) != n or any(type(x) is not int for x in old):
        raise ValueError('invalid old offsets')
    pairs: dict[tuple[int, int], int] = {}
    if not isinstance(edges, (tuple, list)):
        raise ValueError('invalid edge collection')
    for e in edges:
        if not isinstance(e, (tuple, list)) or len(e) != 3 or any(type(x) is not int for x in e):
            raise ValueError('invalid edge')
        u, v, w = e
        if not 0 <= u < n or not 0 <= v < n:
            raise ValueError('edge outside blocks')
        pairs[u, v] = max(pairs.get((u, v), w), w)
    return [(u, v, w) for (u, v), w in sorted(pairs.items())]


def optimal_offsets(n: int, edges: Sequence[Edge], old: Sequence[int]) -> dict:
    """Return feasible offsets, maximum pinned set and a chain-cover certificate.

    Raises ValueError for infeasible constraints or malformed/beyond-bound input.
    Runtime O(n^3 + n*m), memory O(n^2 + m); no external solver is used.
    The certificate can be checked by optimality_check.py without this module.
    """
    es = _input(n, edges, old)
    reduced = [(u, v, w + old[u] - old[v]) for u, v, w in es]
    dist: list[list[int | None]] = [[None] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0
    for u, v, w in reduced:
        if dist[u][v] is None or w > dist[u][v]:
            dist[u][v] = w
    # Max-plus Floyd closure. A positive diagonal rejects the fixed graph.
    for mid in range(n):
        for i in range(n):
            a = dist[i][mid]
            if a is None:
                continue
            for j in range(n):
                b = dist[mid][j]
                if b is not None and (dist[i][j] is None or a + b > dist[i][j]):
                    dist[i][j] = a + b
        if any(dist[i][i] > 0 for i in range(n)):
            raise ValueError('positive cycle: chosen proof not representable')
    order = [[j for j in range(n) if dist[i][j] is not None and dist[i][j] > 0]
             for i in range(n)]
    # Bipartite maximum matching, using augmenting paths in the strict order.
    right = [-1] * n
    def augment(u: int, seen: set[int]) -> bool:
        for v in order[u]:
            if v in seen:
                continue
            seen.add(v)
            if right[v] == -1 or augment(right[v], seen):
                right[v] = u
                return True
        return False
    for i in range(n):
        augment(i, set())
    left = [-1] * n
    for v, u in enumerate(right):
        if u != -1:
            left[u] = v
    # Alternating reachability gives a maximum antichain in the order.
    zl = {u for u in range(n) if left[u] == -1}
    zr: set[int] = set()
    queue = deque(sorted(zl))
    while queue:
        u = queue.popleft()
        for v in order[u]:
            if left[u] == v or v in zr:
                continue
            zr.add(v)
            if right[v] != -1 and right[v] not in zl:
                zl.add(right[v]); queue.append(right[v])
    pinned = sorted(zl - zr)
    # Anchor at zero in reduced coordinates. Longest paths from a fresh
    # zero-connected source are realized by initializing every distance at zero.
    anchor = n
    augmented = reduced + [(anchor, f, 0) for f in pinned] + [(f, anchor, 0) for f in pinned]
    potential = [0] * (n + 1)
    for _ in range(n + 1):
        changed = False
        for u, v, w in augmented:
            if potential[v] < potential[u] + w:
                potential[v] = potential[u] + w; changed = True
        if not changed:
            break
    else:
        raise RuntimeError('antichain extension invariant failed')
    new = [old[i] + potential[i] - potential[anchor] for i in range(n)]
    # The matching edges form a vertex-disjoint chain cover. Each order edge
    # gets an ACTUAL graph path, rather than a trusted transitive-closure claim.
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for u, v, w in reduced:
        adjacency[u].append((v, w))
    def tight_path(start: int, end: int) -> list[int]:
        parent = {start: -1}; todo = deque([start])
        while todo and end not in parent:
            u = todo.popleft()
            for v, w in adjacency[u]:
                if v not in parent and dist[v][end] is not None and w + dist[v][end] == dist[u][end]:
                    parent[v] = u; todo.append(v)
        if end not in parent:
            raise RuntimeError('missing path witness')
        path = [end]
        while path[-1] != start:
            path.append(parent[path[-1]])
        return path[::-1]
    chains = []
    for start in range(n):
        if right[start] != -1:
            continue
        vertices = [start]; paths = []
        while left[vertices[-1]] != -1:
            v = left[vertices[-1]]
            paths.append(tight_path(vertices[-1], v)); vertices.append(v)
        chains.append({'blocks': vertices, 'paths': paths})
    changes = sum(a != b for a, b in zip(old, new))
    if changes != n - len(chains) or len(pinned) != len(chains):
        raise RuntimeError('primal-dual cardinalities disagree')
    return {'offsets': new, 'changed_fields': changes, 'pinned': pinned,
            'certificate': {'chains': chains}}
