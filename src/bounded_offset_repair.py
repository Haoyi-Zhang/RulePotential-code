"""Exact minimum-field repair with per-coordinate integer bounds.

For trusted difference constraints ``o[v] - o[u] >= w`` and old offsets ``a``, 
this module minimizes the number of coordinates that change subject to
``lower[i] <= o[i] <= upper[i]``.  It fixes the graph, selected proof, partition,
and local labels.  The result is a bounded specialization of the same
violator-order/maximum-antichain principle used by ``offset_repair.py``.

The returned lower-bound certificate is checked independently by
``bounded_optimality_check.py``; that checker imports no code from this module.
"""
from collections import deque
from typing import Sequence

Edge = tuple[int, int, int]
MAX_BLOCKS = 256


def _input(n: int, edges: Sequence[Edge], old: Sequence[int],
           lower: Sequence[int], upper: Sequence[int]) -> list[Edge]:
    if type(n) is not int or not 1 <= n <= MAX_BLOCKS:
        raise ValueError('block count outside reference bound')
    for name, values in [('old', old), ('lower', lower), ('upper', upper)]:
        if not isinstance(values, (tuple, list)) or len(values) != n or any(type(x) is not int for x in values):
            raise ValueError(f'invalid {name} offsets')
    if any(lo > hi for lo, hi in zip(lower, upper)):
        raise ValueError('empty coordinate interval')
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


def optimal_bounded_offsets(n: int, edges: Sequence[Edge], old: Sequence[int],
                            lower: Sequence[int], upper: Sequence[int]) -> dict:
    """Return an exact bounded-integer minimum-field repair and certificate.

    Bounds are trusted constraints, not merely output-format checks.  The old
    vector need not satisfy them: a coordinate outside its interval is then
    necessarily changed.  Raises ``ValueError`` on malformed input or an
    infeasible bounded system.
    """
    es = _input(n, edges, old, lower, upper)
    anchor = n
    size = n + 1

    # Reduced coordinates y_i = o_i-a_i with y_anchor=0.  Bound inequalities
    # are represented as ordinary difference edges involving the anchor.
    reduced = [(u, v, w + old[u] - old[v]) for u, v, w in es]
    reduced.extend((anchor, i, lower[i] - old[i]) for i in range(n))
    reduced.extend((i, anchor, old[i] - upper[i]) for i in range(n))

    # Keep only the strongest parallel edge; this also simplifies witnesses.
    strongest: dict[tuple[int, int], int] = {}
    for u, v, w in reduced:
        strongest[u, v] = max(strongest.get((u, v), w), w)
    reduced = [(u, v, w) for (u, v), w in sorted(strongest.items())]

    dist: list[list[int | None]] = [[None] * size for _ in range(size)]
    for i in range(size):
        dist[i][i] = 0
    for u, v, w in reduced:
        if dist[u][v] is None or w > dist[u][v]:
            dist[u][v] = w
    for mid in range(size):
        for i in range(size):
            left = dist[i][mid]
            if left is None:
                continue
            for j in range(size):
                right = dist[mid][j]
                if right is not None and (dist[i][j] is None or left + right > dist[i][j]):
                    dist[i][j] = left + right
        if any(dist[i][i] > 0 for i in range(size)):
            raise ValueError('positive cycle: bounded offset constraints infeasible')

    # A coordinate can possibly remain old only when it is incomparable with
    # the fixed anchor in the positive-path order.
    eligible = [i for i in range(n)
                if not (dist[anchor][i] is not None and dist[anchor][i] > 0)
                and not (dist[i][anchor] is not None and dist[i][anchor] > 0)]
    eligible_set = set(eligible)
    order = {i: [j for j in eligible
                 if dist[i][j] is not None and dist[i][j] > 0]
             for i in eligible}

    # Maximum matching in the bipartite copy of the induced strict order.
    right: dict[int, int] = {}

    def augment(u: int, seen: set[int]) -> bool:
        for v in order[u]:
            if v in seen:
                continue
            seen.add(v)
            if v not in right or augment(right[v], seen):
                right[v] = u
                return True
        return False

    for u in eligible:
        augment(u, set())
    left = {u: v for v, u in right.items()}

    # Recover a maximum antichain from alternating reachability.
    zl = {u for u in eligible if u not in left}
    zr: set[int] = set()
    queue = deque(sorted(zl))
    while queue:
        u = queue.popleft()
        for v in order[u]:
            if left.get(u) == v or v in zr:
                continue
            zr.add(v)
            if v in right and right[v] not in zl:
                zl.add(right[v])
                queue.append(right[v])
    pinned = sorted(zl - zr)

    # Add equality-to-anchor edges for the selected unchanged coordinates and
    # construct an integer longest-path potential.  The antichain criterion
    # guarantees that the augmented graph remains free of positive cycles.
    pinned_graph = reduced + [(anchor, f, 0) for f in pinned] + [(f, anchor, 0) for f in pinned]
    potential = [0] * size
    for _ in range(size):
        changed = False
        for u, v, w in pinned_graph:
            if potential[v] < potential[u] + w:
                potential[v] = potential[u] + w
                changed = True
        if not changed:
            break
    else:
        raise RuntimeError('bounded antichain extension invariant failed')
    y0 = potential[anchor]
    new = [old[i] + potential[i] - y0 for i in range(n)]

    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(size)]
    for u, v, w in reduced:
        adjacency[u].append((v, w))
    for row in adjacency:
        row.sort()

    def tight_path(start: int, end: int) -> list[int]:
        parent = {start: -1}
        todo = deque([start])
        while todo and end not in parent:
            u = todo.popleft()
            for v, w in adjacency[u]:
                if v not in parent and dist[v][end] is not None and w + dist[v][end] == dist[u][end]:
                    parent[v] = u
                    todo.append(v)
        if end not in parent:
            raise RuntimeError('missing positive-path witness')
        path = [end]
        while path[-1] != start:
            path.append(parent[path[-1]])
        return path[::-1]

    # Matching edges form a minimum chain partition of the eligible order.
    chains = []
    for start in eligible:
        if start in right:
            continue
        blocks = [start]
        paths = []
        while blocks[-1] in left:
            nxt = left[blocks[-1]]
            paths.append(tight_path(blocks[-1], nxt))
            blocks.append(nxt)
        chains.append({'blocks': blocks, 'paths': paths})

    # Every ineligible block carries an explicit positive path to or from the
    # anchor, proving that its old coordinate violates the bounded system.
    forced = []
    for i in range(n):
        if i in eligible_set:
            continue
        if dist[anchor][i] is not None and dist[anchor][i] > 0:
            forced.append({'block': i, 'direction': 'from_anchor',
                           'path': tight_path(anchor, i)})
        elif dist[i][anchor] is not None and dist[i][anchor] > 0:
            forced.append({'block': i, 'direction': 'to_anchor',
                           'path': tight_path(i, anchor)})
        else:
            raise RuntimeError('ineligible coordinate lacks anchor witness')

    changes = sum(a != b for a, b in zip(old, new))
    if changes != n - len(chains) or len(pinned) != len(chains):
        raise RuntimeError('bounded primal-dual cardinalities disagree')
    if any(new[v] - new[u] < w for u, v, w in es):
        raise RuntimeError('constructed vector violates trusted edge')
    if any(not lo <= x <= hi for x, lo, hi in zip(new, lower, upper)):
        raise RuntimeError('constructed vector violates bound')
    return {
        'offsets': new,
        'changed_fields': changes,
        'pinned': pinned,
        'certificate': {'chains': chains, 'forced': forced},
    }
