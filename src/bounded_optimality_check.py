"""Independent checker for bounded minimum-offset-field certificates.

The checker trusts only the complete selected-proof edge set and the declared
coordinate intervals.  It verifies a feasible vector and a lower-bound cover:
positive paths between successive blocks in each chain allow at most one old
coordinate per chain, while a positive path to or from the fixed anchor forces
that block to change.  It imports no optimizer, closure, or matching code.
"""


def check_bounded_optimality(n, edges, old, lower, upper, new, certificate):
    try:
        if type(n) is not int or not 1 <= n <= 256:
            return False
        vectors = (old, lower, upper, new)
        if any(type(v) is not list or len(v) != n or any(type(x) is not int for x in v)
               for v in vectors):
            return False
        if any(lo > hi or not lo <= x <= hi for lo, hi, x in zip(lower, upper, new)):
            return False

        anchor = n
        weights = {}
        for edge in edges:
            if not isinstance(edge, (list, tuple)) or len(edge) != 3 or any(type(x) is not int for x in edge):
                return False
            u, v, w = edge
            if not 0 <= u < n or not 0 <= v < n or new[v] - new[u] < w:
                return False
            rw = w + old[u] - old[v]
            weights[u, v] = max(weights.get((u, v), rw), rw)
        for i in range(n):
            weights[anchor, i] = max(weights.get((anchor, i), lower[i] - old[i]), lower[i] - old[i])
            weights[i, anchor] = max(weights.get((i, anchor), old[i] - upper[i]), old[i] - upper[i])

        if type(certificate) is not dict or set(certificate) != {'chains', 'forced'}:
            return False
        chains, forced = certificate['chains'], certificate['forced']
        if type(chains) is not list or type(forced) is not list:
            return False
        if len(chains) > n or len(forced) > n:
            return False

        def positive_path(path, start, end):
            if type(path) is not list or not 2 <= len(path) <= n + 1:
                return False
            if any(type(x) is not int or not 0 <= x <= anchor for x in path):
                return False
            if path[0] != start or path[-1] != end or len(set(path)) != len(path):
                return False
            total = 0
            for u, v in zip(path, path[1:]):
                if (u, v) not in weights:
                    return False
                total += weights[u, v]
            return total > 0

        covered = set()
        for chain in chains:
            if type(chain) is not dict or set(chain) != {'blocks', 'paths'}:
                return False
            blocks, paths = chain['blocks'], chain['paths']
            if type(blocks) is not list or not 1 <= len(blocks) <= n:
                return False
            if type(paths) is not list or len(paths) != len(blocks) - 1:
                return False
            for b in blocks:
                if type(b) is not int or not 0 <= b < n or b in covered:
                    return False
                covered.add(b)
            for a, b, path in zip(blocks, blocks[1:], paths):
                if not positive_path(path, a, b):
                    return False

        for item in forced:
            if type(item) is not dict or set(item) != {'block', 'direction', 'path'}:
                return False
            b, direction, path = item['block'], item['direction'], item['path']
            if type(b) is not int or not 0 <= b < n or b in covered:
                return False
            covered.add(b)
            if direction == 'from_anchor':
                if not positive_path(path, anchor, b):
                    return False
            elif direction == 'to_anchor':
                if not positive_path(path, b, anchor):
                    return False
            else:
                return False

        changes = sum(a != b for a, b in zip(old, new))
        return len(covered) == n and changes == n - len(chains)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return False
