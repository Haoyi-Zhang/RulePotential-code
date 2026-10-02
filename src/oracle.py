"""Deliberately different tiny oracle: intersection of all closed supersets.

This module does not import the producer or checker. It is exponential and
refuses more than eight atoms; it is not a performance baseline.
"""
from itertools import combinations


def least_model(raw, base):
    n = raw["n"]
    if n > 8:
        raise ValueError("tiny oracle restricted to at most eight atoms")
    result = set(range(n))
    base = set(base)
    for mask in range(1 << n):
        candidate = {i for i in range(n) if mask & (1 << i)}
        if not base <= candidate:
            continue
        closed = True
        for row in raw["rules"]:
            if set(row["body"]) <= candidate and row["head"] not in candidate:
                closed = False
                break
        if closed:
            result.intersection_update(candidate)
    return result


def intervals_points(rows, horizon):
    result = set()
    for fact, start, stop in rows:
        if type(start) is not int or type(stop) is not int or not 0 <= start <= stop <= horizon:
            raise ValueError("invalid interval")
        for t in range(horizon):
            if start <= t < stop:
                result.add((tuple(fact), t))
    return result
