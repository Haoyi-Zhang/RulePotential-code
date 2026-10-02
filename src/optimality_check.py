"""Independent minimum-offset-field certificate checker; imports no producer.

`edges` must be the trusted selected-proof block constraints, not a producer's
claimed affected graph. Paths certify only a lower bound on the number of offset
fields. The checker does not certify minimum bytes, witness edits or partitions.
"""

def check_optimality(n, edges, old, new, certificate):
    try:
        if type(n) is not int or not 1 <= n <= 256:
            return False
        if any(type(v) is not list or len(v) != n or any(type(x) is not int for x in v)
               for v in (old, new)):
            return False
        weights = {}
        for edge in edges:
            if not isinstance(edge, (list, tuple)) or len(edge) != 3 or any(type(x) is not int for x in edge):
                return False
            u, v, w = edge
            if not 0 <= u < n or not 0 <= v < n or new[v] - new[u] < w:
                return False
            weights[u, v] = max(weights.get((u, v), w), w)
        if type(certificate) is not dict or set(certificate) != {'chains'}:
            return False
        chains = certificate['chains']
        if type(chains) is not list or not 1 <= len(chains) <= n:
            return False
        covered = set()
        for chain in chains:
            if type(chain) is not dict or set(chain) != {'blocks', 'paths'}:
                return False
            blocks, paths = chain['blocks'], chain['paths']
            if type(blocks) is not list or not 1 <= len(blocks) <= n or type(paths) is not list or len(paths) != len(blocks) - 1:
                return False
            for b in blocks:
                if type(b) is not int or not 0 <= b < n or b in covered:
                    return False
                covered.add(b)
            for a, b, path in zip(blocks, blocks[1:], paths):
                if type(path) is not list or not 2 <= len(path) <= n or any(type(x) is not int or not 0 <= x < n for x in path):
                    return False
                if path[0] != a or path[-1] != b or len(set(path)) != len(path):
                    return False
                weight = old[a] - old[b]
                for u, v in zip(path, path[1:]):
                    if (u, v) not in weights:
                        return False
                    weight += weights[u, v]
                if weight <= 0:
                    return False
        changes = sum(a != b for a, b in zip(old, new))
        return len(covered) == n and changes == n - len(chains)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return False
