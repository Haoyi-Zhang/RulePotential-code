# Minimum-field repair of a fixed selected proof

## Scope and relation to prior work

Fix the true atoms, selected witnesses, partition, and local labels after an
update. Read every active selected-proof block inequality from that proof:
`o[j] - o[i] >= w[i,j]`. The fixed graph must be feasible. Offsets are mathematical
integers. The objective is the number of coordinates that differ from an old
vector `a`, not the sum of numerical changes, packet bytes, changes to witnesses,
or changes to the partition. The executable reference supports 1–256 blocks.
It is an optional global optimizer, not an extension of the local-checking bound.

The generic reduction of L0 order repair to retaining a maximum antichain in a
violator graph is established: Quentin F. Stout, *L0 Isotonic Regression with
Secondary Objectives*, revised author preprint (2022), DOI
10.48550/arXiv.2106.00279, Section 2. The present weighted difference-constraint
extension and certificate interface do not claim a new generic isotonic algorithm.
The cardinality equality uses Dilworth's theorem, DOI 10.2307/1969503; the path
closure uses the max-plus form of Floyd's recurrence, DOI
10.1145/367766.368168. No source implementation is copied or executed.

## Compatible pinned coordinates

Give edge (i,j) reduced weight `w[i,j] + a[i] - a[j]`. Let D(i,j) be the maximum
weight of a path, minus infinity when unreachable, and D(i,i)=0. Since feasible
constraints have no positive cycle, removing cycles cannot lower a path weight;
maxima are attained by simple paths. Define i ≺ j exactly when D(i,j)>0.
This relation is irreflexive. Concatenating positive paths gives a positive walk,
which simplifies without losing weight, so it is transitive.

A set F of coordinates can all keep their old values exactly when F is an
antichain. Necessity follows by summing inequalities along a positive reduced
path between fixed endpoints: their zero reduced difference would have to be
positive. For sufficiency put y=o-a. Add an anchor z and zero-weight edges
z→f and f→z for all f in F. Cycles avoiding z are nonpositive. A walk through z
splits into original-graph paths between pinned vertices, and each such path
has nonpositive weight. Thus there is no positive cycle. Add a source with zero
edges to every vertex, take maximum source-path weights, and translate all
potentials by minus the anchor's value. Both anchor edges force y[f]=0, and
all original inequalities still hold. This also proves an integer extension.

Consequently the minimum changed-field count is k-width(≺). Compute closure,
maximum bipartite matching, its maximum antichain and minimum chain cover,
then the anchor extension. An extra unchanged coordinate would enlarge the
maximum antichain, so the constructed vector has exactly the claimed cost.
Dense closure and matching require O(k^3) arithmetic operations, and extension
plus graph-path recovery takes O(km+k^2). Storage is O(k^2+m). Arithmetic-operation
counts must be multiplied by the relevant integer-operation cost; path sums have
polynomial encoding length. This is not a polynomial bound in fixed-width
machine instructions regardless of input bit length.

## Independently checked optimality

The optimizer supplies chains partitioning all k block vertices. Consecutive
vertices in each chain have explicit paths in the *trusted selected-proof graph*
with positive reduced weight. The verifier does not import closure, matching,
or synthesis. It checks exact field types, vertex coverage without duplicates,
path endpoints, actual edges, positive reduced path weights, every proposed
rank inequality, and the proposed vector's changed-coordinate count.

For q valid chains, no feasible vector can leave two coordinates unchanged in
one chain. A path between nonconsecutive chain members is obtained by concatenating
positive consecutive paths. At most q coordinates can therefore remain unchanged:
at least k-q must change. A feasible vector changing exactly k-q attains that lower
bound. This proves optimality without asking the checker to certify that the
optimizer's matching is maximum.

The matching produces at most k-1 comparisons, each with a simple graph path
of at most k-1 edges. Certificate size and checking may be O(k^2) path incidences,
plus O(m) to verify the complete constraint graph. No claim of local or constant
optimality checking is made. The ordinary local checker can accept a correct
nonoptimal packet without this optional evidence.

## Per-coordinate integer intervals

The bounded variant accepts trusted intervals `lower[i] <= o[i] <= upper[i]`.
The old value may lie outside its interval and is then necessarily changed. Put
`y=o-a`, add an anchor `z` fixed at zero, and encode each interval as two ordinary
difference edges:

* `z -> i` with weight `lower[i]-a[i]`;
* `i -> z` with weight `a[i]-upper[i]`.

The bounded system is feasible exactly when this augmented graph has no positive
cycle. A coordinate can remain old only when it has no positive path to or from
the anchor. Among those anchor-incomparable coordinates, simultaneous retention
is possible exactly for antichains of the positive-path order. Therefore the
minimum changed-field count is `k-width`, where width is computed on the induced
order of anchor-incomparable coordinates; coordinates outside that set are forced
to change.

The sufficiency proof adds zero-weight equality edges between the anchor and every
chosen antichain coordinate. Any new cycle decomposes into augmented-graph paths
between retained coordinates or the anchor, each of nonpositive weight. Integer
longest-path potentials therefore extend the retained values while respecting
all proof edges and intervals.

`src/bounded_offset_repair.py` implements the construction. Its certificate has
(1) a chain partition of the anchor-incomparable coordinates, with actual positive
paths between consecutive blocks, and (2) one actual positive path to or from the
anchor for every forced coordinate. `src/bounded_optimality_check.py` imports no
optimizer, path closure, or matching code. It checks raw bounds, every trusted
inequality, each path and its weight, disjoint coverage, and that the proposed
vector changes exactly `k-q` fields for `q` chains. These facts prove the lower
bound and optimality without trusting the optimizer.

This result still fixes the selected proof, partition, and local labels. It does
not optimize packet bytes, proof choice, repartitioning, or coupled non-box domains.

## Exact oracle and why its box is sufficient

All six possible nonself directed edges on three vertices independently take
values absent, -1, 0, or 1: 4^6=4096 graphs. All 27 old targets in {-1,0,1}^3
are tested, giving 110592 graph–target pairs. The independent oracle evaluates
all vectors in {-3,-2,-1,0,1,2,3}^3 directly against the raw constraints. It does
not call path closure or matching.

For feasible graphs every maximum path has weight at most two: a simple path
uses at most two edges of weight at most one. For any compatible pinned subset F,
define L(v) as the maximum path weight to v from any original vertex, including
length-zero paths. An extension is the maximum of `-3 + L(v)` and every finite
`a[f] + D_w(f,v)` for f in F, where D_w uses original weights. Appending edges
proves all constraints. The floor is between -3 and -1; pinned paths are at most
3. At a pinned vertex f, compatibility keeps all other pinned bounds at most
a[f], the floor is at most -1 <= a[f], and its own empty path attains a[f].
Thus an extension in [-3,3]^3 realizes every feasible unchanged set, establishing
that the bounded oracle finds the unbounded-integer optimum. With F empty,
normalized source distances in [0,2] also suffice.

Measured outcomes: 1905 feasible graphs; 51435 feasible graph–target pairs;
59157 infeasible pairs; zero optimum/feasibility mismatches; zero rejected valid
optimality certificates. Among feasible pairs, optimum counts 0, 1, 2 occur
11499, 32310, and 7626 times. No feasible pair needs all three coordinates changed,
as translation always permits retaining at least one coordinate.

## Exact bounded oracle

For the bounded campaign, the same 4096 weighted graphs and 27 old vectors are
crossed with three fixed interval profiles: `[-1,1]^3`,
`[0,1] x [-1,0] x [0,1]`, and its reflection. The independent oracle enumerates
every vector in each finite box and directly evaluates the raw inequalities; it
imports neither bounded optimizer nor checker.

The 331776 cases contain 125577 feasible and 206199 infeasible instances. The
optimizer has zero feasibility or minimum-count disagreements, and all feasible
outputs pass the independent anchor/path certificate checker. The global optimum
histogram is 18877 cases with zero changes, 53490 with one, 40386 with two, and
12824 with three. These finite checks are evidence for the implementation, not a
mechanized proof of the general theorem.

## Structured controls and measurement scope

Three actual Horn programs use singleton blocks at sizes 3,7,15,31,63,127.
All updates preserve the complete truth set.

* Fan-out: base facts 0 and 1, rule 0→1 and rules 1→j for all j≥2. Local labels
  are 1,1,2,...,2. Removing seed 1 changes one witness. Raising only requires k-1
  offset changes, while lowering offset 0 by one requires a single field.
* Binary tree: a full binary conjunction tree, with leaves and root initially
  base. Deleting the root seed changes one witness and exactly one offset under
  both methods. This is a control in which monotone repair is already optimal.
* Ordered chain: all vertices are initially base, all labels zero, and rules
  (j-1)→j. Removing every seed except vertex 0 leaves all truths derived but
  requires k-1 witness and offset changes. This is an intrinsic large-repair control.

There is one warm-up and seven measured repetitions per setting, 126 retained
rows. Each setting constructs one verified session. Tentative local checks use
commit=False and roll back to that same verified state; repetitions do not
allocate fresh session indexes. Fixed order and interpreter/cache effects remain.
The exact and monotone methods share witnesses and semantics. Both packets pass
the original local checker, and the exact solution also passes a full ranked-model
scan. All timing samples and deterministic byte counts are retained.

The original fan-in proof generator used a conjunction too wide for the existing
width-16 input bound. Its rejection is retained in offset-input-guard.json; no
failed timings are counted. The measured conjunction control is the binary tree.
This is a change to the control's generator, not a relaxation of the checker.

At 127 blocks, fan-out uses 1 instead of 126 offset fields (61 instead of 954
packet bytes), but its separate optimality evidence is 3439 bytes. The tree has
no field saving. On the ordered chain, the exact minimum-field vector has a
2258-byte packet versus 2134 for monotone repair, despite both changing 126 fields.
This is an observed counterexample to interpreting minimum fields as minimum bytes.

## Commands and evidence

Run from this standalone repository root. Scientific checks use explicit failures and remain active under `python -O`; normal non-optimized execution is the documented route:

```sh
python repair_tests.py -v
python repair_experiments.py --out offset-reproduced.json --compare results/offset-repair.json
python bounded_repair_experiments.py --out bounded-reproduced.json --compare results/bounded-offset-repair.json
python export_repair_data.py --out repair-data
python export_repair_data.py --out repair-data --check
```

Both oracle commands refuse an existing output path, use one process, impose a
35-second CPU limit and 3.5GB address-space limit, and use no network or external
solver. Original results are in `results/offset-repair.json` and
`results/bounded-offset-repair.json`; fresh deterministic comparisons are retained
separately. Fifteen repair tests (eight unbounded and seven bounded) do not alter
the original 23-test suite or the original 49-job campaign's deterministic
contract. Six additional independent property/input-contract audits are in
`audit_tests.py`, so the complete delivered test-method count is 44.
