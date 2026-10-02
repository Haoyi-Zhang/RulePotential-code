# Executable interface

## Session initialization

Import `Session` and `strict_loads` from `src/checker.py`. A ground program is an
object with `n`, `rules`, `blocks`, and `local`. Atom identifiers are integers in
`[0,n)`, with `1 <= n <= 200000`. Each rule is exactly an object `head` and `body`;
`body` is a duplicate-free list of at most 16 atom identifiers. There are at most
one million rules. Empty bodies are allowed. Rules are immutable during a session.

`blocks` and `local` have length `n`. Block identifiers must cover a contiguous
nonempty range `[0,k)`. Local labels are in `[0,2**31-1]`. An offset list has
length `k`, and every integer lies in `[-2**62,2**62]`. Ranks are exact integer
sums, so a sum or difference is not truncated to a machine word.

The remaining initialization arguments are duplicate-free `base` and `model`
lists, a witness object, and offsets. Each witness key is the canonical decimal
string of an atom in `model`, with no leading zeros. Value `-1` denotes a base
witness; other values are rule indices. Every true atom must have exactly one
witness. The constructor checks base inclusion, closure, membership, and strict
selected-edge ranks; invalid initialization raises `ValueError`.

## Sequential updates

`session.check(removed, added, packet)` consumes exact disjoint base differences.
Every removed atom must be an old base fact; no added atom may already be in the
base. Simultaneously removing and adding the same atom is not a normalized delta.
Interval updates must first be union-normalized and converted to point differences.

A packet has exactly four fields:

```json
{"delete": [0], "insert": [], "witness": {"2": 8}, "offset": {"0": 4}}
```

The numbers in this example are schematic; `example.py` obtains a valid packet
for its explicitly generated program. `delete` and `insert` are disjoint truth
changes relative to the old model. `witness` patches true heads only and must
cover all inserted heads. `offset` contains absolute new offsets, not increments.
Unmentioned witnesses and offsets are retained. The checker does not accept a
producer-supplied frontier, selected-consumer index, or claimed maximum.

The returned dataclass has `accepted`, `reason`, and operation `counters`.
On ordinary invalid-format, membership, closure, or rank rejection, the old
verified state is retained. `commit=False` validates but rolls back provisional
tree changes even on acceptance. `inspect()` is a full diagnostic export and is
excluded from the timed local-check path. A caller must serialize updates and
bind them to the correct session; the prototype provides no concurrent network
identity or durable transaction mechanism.

Use `strict_loads` for untrusted JSON text. It rejects duplicate keys, non-finite
constants, and payloads over 64 MiB. Map identifiers must be canonical decimal
strings. Boolean values are not integer identifiers. Python's ordinary exception
and resource behavior still applies: there is no denial-of-service guarantee
against arbitrary nesting, memory exhaustion, or interpreter compromise.

## Temporal input and adapter

Temporal input declares finite typed domains, predicate signatures, static guard
relations, rule schemas, a horizon, and base intervals. Every object variable is
in the rule's static guard. Rules use integer point shifts; the head shift is
zero and the head time must lie in its half-open allowed range. If any shifted
premise is outside `[0,H)`, the entire instance is inapplicable. It is never
silently converted into a rule with that premise removed.

The front end expands every point explicitly. Adjacent and overlapping base
intervals are unioned before updates are computed. A sparse guard does not
promise small Cartesian verification: the independent frontend bounds candidate
substitutions times the horizon at one million. This cost is separate from
resident ground checking. No arbitrary metric temporal operator is implemented.

The example-policy adapter defines membership closure, grants inherited through
roles, grants inherited through resource roles, and a two-point stability
predicate. It has six positive schemas. It ignores no supported record silently,
but it is not a reproduction of the complete Casbin engine. All users, resources,
and roles are public upstream toy examples; generated intervals are synthetic.
