# Model, certificates and proofs

## 1. Finite semantics

Fix a finite set U of ground atoms and a finite list R of Horn rules. A rule r
has a head h(r) in U and a finite, possibly empty, set b(r) of premises in U.
A set X is closed when b(r) ⊆ X implies h(r) ∈ X for every r. For a base B ⊆ U,
write L_R(B) for the intersection of all closed supersets of B. This intersection
is itself closed: if every premise is in the intersection, it is in every such
superset, so the head is in every such superset. Therefore L_R(B) exists, is the
unique least closed superset, and is obtained by finite Horn saturation. Empty
bodies are true, not ignored.

The temporal front end has finite typed constant domains, a horizon
T = {0,...,H−1}, and typed predicates. Each rule has a head at time t, a
half-open allowed head-time range, and positive premises at t+d for explicitly
specified integer shifts d. A static relational guard lists permitted tuples
for every object variable. Equivalently, conjoining this guard with the finite
clock relation guards all object and time variables. A rule instance with any
premise time outside T is inapplicable; the invalid premise is not erased.
There are no function symbols, negative literals or existential variables.

A temporal fact A@[a,b) denotes precisely the integer points a ≤ t < b. Facts
with overlapping intervals are unioned. An empty interval denotes no points.
Grounding enumerates all typed atoms and applicable guarded rule instances,
then removes duplicate premises and duplicate instances. Deduplication is sound
because conjunction and the set-valued immediate-consequence operator are
idempotent. At each t and substitution, a temporal rule is satisfied exactly
when its ground instance is satisfied. By induction on saturation rounds, the
point representation of the temporal least model equals L_R(B). The output
coalescer only replaces consecutive runs of points by maximal half-open
intervals; it does not change the interpretation.

All claims are charged to this *expanded* ground input. Its universe size is
H times the sum, over predicates, of the products of their argument-domain
sizes. A horizon encoded in binary can make expansion exponential in the bit
length of an interval endpoint. Neither guardedness nor finiteness is used to
hide that cost. Changing the horizon, domains, guards or rule list requires a
new checked session. Only base membership and the certificates change within a
session.

## 2. Full ranked certificates

A selected witness W for M assigns to every h ∈ M either the marker seed, which
requires h ∈ B, or a rule r with h(r)=h and b(r) ⊆ M. It selects one rule, not all
alternative derivations. A rank ρ : M → Z is valid when ρ(b)<ρ(h) for every
premise b of every selected non-seed witness for h. Ranks may be equal on
unrelated atoms, and need not start at zero.

**Proposition 1 (ranked model certificate).** A candidate M is L_R(B) if it is
closed, contains B, and has valid selected witnesses and ranks. Conversely,
every L_R(B) has such a certificate.

*Proof.* Closure and B ⊆ M give L_R(B) ⊆ M by the definition of the least closed
superset. For the other inclusion, order M by increasing integer rank, breaking
ties arbitrarily. This is possible because M is finite. A seed is in B and
hence in L_R(B). For a selected rule, every premise has a strictly smaller rank
and has already been shown to be in L_R(B); closure of L_R(B) gives the head.
An empty-body selected rule requires no induction hypotheses. Thus M ⊆ L_R(B).
For the converse, assign to each derived atom its first saturation stage, and
select a rule whose premises were present in the previous stage. Select seed
for each base atom. Every selected premise has a smaller stage. At most |U|
new-atom stages are needed, so finite integer ranks suffice. □

The ranking requirement cannot be replaced by local membership. With rules
s→a, a→b and b→a, the old base {s} derives {s,a,b}. After deleting s, the set
{a,b} is closed and each atom has a locally satisfied witness, but the least
model is empty. Selecting the two cycle edges would require both ρ(a)<ρ(b)
and ρ(b)<ρ(a). This is the negative control for unsupported cyclic support.

## 3. The three update interfaces

Assume (B,M,W,ρ) has passed full checking. An external update is an exact
base deletion B− ⊆ B and insertion B+ disjoint from B. They are disjoint, and
B'=(B\B−)∪B+. A producer claims truth deletion D ⊆ M and insertion I disjoint
from M, and proposes M'=(M\D)∪I. A patch P supplies selected witnesses for every
new atom and any changed retained witness. Unmentioned retained witnesses are
copied, giving W'. No deleted or absent atom may have a patched witness.

The checker obtains two complete rule indexes from the fixed input:
Head(x)={r:h(r)=x} and Body(x)={r:x∈b(r)}. It also maintains a selected-consumer
index Cons_W(x)={h:W(h) is a rule whose body contains x}. The indexes are built
and updated by the checker, not attested by the producer.

**Lemma 2 (closure interface).** Given that M is closed, M' is closed iff all
rules in

    F = ⋃_{h∈D} Head(h)  ∪  ⋃_{b∈I} Body(b)

are satisfied by M'.

*Proof.* Necessity is immediate. For sufficiency, suppose b(r) ⊆ M'. If its
body meets I, r is inspected. Otherwise all its premises are retained old
atoms, so b(r) ⊆ M; old closure gives h(r) ∈ M. If the head is retained, the
new rule is satisfied. If not, it is in D, and r is inspected by its deleted
head. These exhaust the possibilities, including the empty-body case, whose
head must already have been in M. □

A producer need not send F: the checker reconstructs it. F can be larger than
the truth delta because many rules can share a head or premise. The lemma does
not assert that F is minimal; an implementation maintaining additional rule
activity summaries might sometimes inspect less.

Define the witness-validation interface

    Q = dom(P) ∪ I
        ∪ {h∈B− : W(h)=seed}
        ∪ ⋃_{x∈D} Cons_W(x).

Only members of Q ∩ M' need validation; this includes newly inserted atoms.

**Lemma 3 (witness membership interface).** If every member of Q ∩ M' has
a valid seed or locally satisfied rule witness in the new state, then every
member of M' does.

*Proof.* New and patched members are explicitly checked. Consider a retained
unpatched h outside Q. If W(h)=seed, then h∉B− and h remains a base atom. If
W(h)=r, its premises were all in M. None can be in D, or h would belong to
Cons_W(x) for a deleted premise x and hence to Q. Thus every premise remains
in M'. Its unchanged rule still has head h. □

This lemma deliberately addresses only witness membership, not well-foundedness.
A change of proof can create a cycle while leaving every premise true. Ranks
must also be validated. Base inclusion is checked separately: every added base
atom must be present in M', and no member of D may belong to B'. Old base
atoms that are neither revoked nor deleted remain present automatically.

## 4. Fixed blocks and rank potentials

Fix a partition γ:U→{0,...,k−1} and a local integer label ℓ(v) for every atom.
The dynamic rank is represented by one integer offset o_i for each block:

    ρ(v) = o_{γ(v)} + ℓ(v).

For a selected edge b→h within one block, rank validity is exactly ℓ(b)<ℓ(h).
For an edge from block i to a distinct block j, it is exactly

    o_j − o_i ≥ ℓ(b) − ℓ(h) + 1.

Let w_ij be the maximum right-hand side over the currently selected edges from
i to j, or −∞ if none is selected. The rank representation is valid iff its
internal selected edges have increasing local labels and o_j−o_i≥w_ij for all
nonempty ordered block pairs. This is an exact conjunction reduction, not an
approximation by a representative edge: the checker maintains the maximum over
*every* selected incidence in that pair.

### Reversible boundary summaries

For each ordered block pair, the checker allocates one slot per potential
cross-block premise incidence in the fixed ground program. An unselected slot
has value −∞; a selected slot has weight ℓ(b)−ℓ(h)+1. A maximum segment tree
maintains the pair maximum. Initializing all leaves and building bottom-up is
linear in the slot count. Every point change costs logarithmic time in that
pair's allocated slots. The total padded tree storage is linear in the total
number of cross-block incidences: rounding each positive slot count up to a
power of two increases it by less than a factor of two.

Let E_ch be the selected incidences removed or added by D and P. Let O be the
offset patch, and let T be the ordered pairs touched by E_ch. Before changing
offsets, let Adj(i) contain all currently nonempty ordered pairs incident to i.
After provisional selected-edge changes, inspect only

    K = T ∪ ⋃_{i∈dom(O)} Adj(i).

Pairs in K that have become empty impose no inequality.

**Lemma 4 (rank boundary interface).** If the old rank representation is valid,
all newly selected internal edges have increasing local labels, and all
nonempty pairs in K satisfy the patched offsets, then every selected edge in
W' has a strictly increasing new rank.

*Proof.* An unchanged internal edge keeps its local-label inequality; translating
its block adds the same offset to both endpoints. A newly selected internal
edge is checked directly. Consider a nonempty cross-block pair after the
update. If its selected incidences changed, it is in T and hence K. Otherwise
its maximum is the old maximum. If an endpoint offset changed, this pair was
already nonempty and belongs to the old Adj of that endpoint, so it is in K.
If neither selected incidences nor either offset changed, its previously valid
inequality is unchanged. Every pair therefore satisfies its new maximum bound,
which implies the inequality for each individual selected edge. □

Using old adjacency is safe only because T also includes newly nonempty pairs.
Ignoring T would miss a new edge between blocks that previously had no selected
connection. Checking only the modified witness's edges is also insufficient:
shifting an offset can invalidate an unchanged selected boundary elsewhere.

## 5. The update theorem and transaction invariant

**Theorem 5 (local exact maintenance checking).** Start a session with a fully
checked ranked model of B. Keep the ground program, partition and local labels
fixed. Accept a packet only if its domains and base delta are valid, base
inclusion holds, the closure interface F is satisfied, the witness interface Q
is valid, and the internal and boundary rank checks in Lemma 4 succeed. The
resulting M' is exactly L_R(B'), and its retained certificate satisfies the same
invariant as the old state. The result holds after any finite sequence of
accepted packets, independently of how their producer works.

*Proof.* The domain checks define one unambiguous candidate and a complete
witness map on it. Base inclusion gives B'⊆M'. Lemma 2 gives full closure, not
just closure in a producer-named region. Lemma 3 gives a valid local witness
for every new fact. Lemma 4 gives a strict rank increase along every selected
premise. Proposition 1 now gives M'=L_R(B'). The checker updates its selected
consumer index, active pair adjacency and maximum-tree slots according to
exactly the accepted witness changes, so all auxiliary invariants hold for the
next packet. Induction on the number of accepted packets proves the sequential
claim. No step assumes DRed, a truthful producer, a minimal delta, or a
particular witness-selection heuristic. □

The implementation rejects invalid certificates without changing public state.
Tree leaf updates are provisional and record their prior values. Replaying the
journal in reverse restores every leaf even if a slot was changed more than
once; recomputing ancestors after each restoration restores every maximum.
All other persistent structures are changed only after successful checking.
Consequently a format, witness, closure or rank rejection leaves the old
verified state usable by a later packet. This is a serial in-memory transaction
property, not crash consistency, concurrent access safety, or recovery after
resource exhaustion during commit. Such failures require terminating the
session and reinitializing from a fully checked state.

### Conditional completeness and finite numerical bounds

**Theorem 6 (representation completeness).** For a chosen M'=L_R(B'), any valid
selected witness map and offsets expressible by the fixed block representation
can be installed by some accepted patch. With singleton blocks and local labels
zero, every finite least model is expressible.

*Proof.* Send the exact truth difference, supply every new/changed witness, and
supply every changed offset. All membership, closure and rank conditions hold
by assumption, hence so do their inspected subsets. For singleton blocks,
choose first-derivation-stage witnesses and ranks from Proposition 1 and use
each rank as its own block offset. These integers are bounded by |U|, so no
unbounded numerical representation is required. □

A fixed coarse partition is not promised complete. Choosing a different proof
may repair it; otherwise singleton reinitialization is a complete fallback,
but that rebuild is global and is not charged as a local update. The current
producer does not search over all alternative proofs or adaptively refine
partitions.

The implementation bounds local labels by 2^31−1, |U| by 200,000, and transmitted
offsets by ±2^62. Feasible block constraints always admit a normalized solution
between 0 and (k−1)2^31, as proved below; thus these bounds do not remove a
representable certificate within those dimension limits. Repeated translations
starting from old offsets can approach the transport bound. In that case the
producer recomputes a normalized solution; it may have to patch many offsets.
Python integer arithmetic is exact, including offset differences. A fixed-width
port must not silently overflow when subtracting two allowed offsets.

## 6. Representability and checked obstructions

The block graph has an arc i→j of weight w_ij for each nonempty cross-block
pair. A directed cycle is positive if its edge-weight sum is positive. A
zero-weight cycle is not an obstruction.

**Theorem 7 (exact block criterion).** A selected proof has a block-potential
rank iff (a) every internal selected edge increases its local label, and (b)
the weighted block graph has no positive directed cycle.

*Proof.* Necessity of (a) follows by cancelling the common offset. Summing the
inequalities around a directed cycle gives 0 at least its weight, proving (b).
For sufficiency, add an auxiliary source with a zero-weight arc to each block.
When no cycle is positive, deleting a repeated-vertex cycle from a walk cannot
decrease its weight. Thus the maximum weight of a walk ending at any block is
attained by a simple path and is finite. Let o_j be that maximum. Appending any
arc i→j to a maximum walk ending at i shows o_j≥o_i+w_ij. The internal edges
are valid by (a). These offsets therefore give a valid rank. A simple path
visits at most k original vertices, giving 0≤o_j≤(k−1)W when every positive
weight is at most W. Here W≤2^31. □

This is the classical feasibility criterion for difference constraints,
specialised to a chosen proof representation; it is not claimed as a new
shortest-path theorem. Its role is to state exactly where the compression can
fail and to make rejection evidence checkable.

An internal-order obstruction names one selected rule incidence b→h with
γ(b)=γ(h) and ℓ(b)≥ℓ(h). A positive-cycle obstruction names a simple cycle of
blocks and, for each arc, an actual selected rule incidence with its weight.
It need not prove that its weight is the maximum: the individual inequalities
already sum to a contradiction. The independent obstruction checker verifies
the rule identifiers, head/premise membership, chosen witness, block endpoints,
weights, cycle closure and positive sum. Hence an accepted obstruction proves
infeasibility of the **specified** witness and partition, not that the queried
facts are underivable.

For example, let blocks be A={a_0,a_1}, B={b_0,b_1} with local labels 0 and 1.
The selected edges a_1→b_0 and b_1→a_0 are an acyclic fact-level proof with
base {a_1,b_1}. Nevertheless both block arcs have weight 2, so their positive
cycle forbids offsets. In contrast, a_0→b_1 and b_0→a_1 give weights 0 and 0
and are valid with equal offsets. Rejecting every cyclic quotient would lose
this legitimate representation.

## 7. What the certificate size can depend on

### Truth stability does not bound scalar rank repair

For n≥1, let U contain x,y,a_1,...,a_n,b_1,...,b_n. There are two chains
x→a_1→...→a_n and y→b_1→...→b_n, and two alternative rules b_n→a_1 and
a_n→b_1. With base {x,y}, every atom is true. Deleting x loses only x, and
deleting y loses only y: the surviving chain rescues the other one.

**Theorem 8 (scalar patch lower bound).** Whatever valid scalar ranks are
stored initially, one of these two one-seed deletions forces at least
ceil(n/2) of the surviving a_i,b_i scalar labels to change in every valid new
selected proof. This is a lower bound for a format that writes each changed
scalar label explicitly.

*Proof.* After deleting x, every valid proof of a_1 must select b_n→a_1 because
x is absent. The b-chain must be grounded in y: selecting a_n→b_1 would close
a selected cycle and violate strict ranks. Thus every b_i precedes every a_j
in rank. After deleting y, the symmetric strict ordering is forced. For each
index i, either ρ_old(a_i)≤ρ_old(b_i), in which case deleting x forces at least
one member of that pair to change, or ρ_old(a_i)>ρ_old(b_i), in which case
deleting y does. Equal ranks fall in the first class and also require change
for the other deletion, but are counted only once. The two classes cover n
pairwise disjoint pairs. One class has at least ceil(n/2) members, so its deletion
requires that many distinct changed labels. □

This statement is independent of the producer's initial proof choice, but not
of the rank encoding. It does not lower-bound all dynamic topological-order
structures, compressed integer assignments, or all certificate systems.

With canonical initial ranks ρ(a_i)=ρ(b_i)=i and root ranks zero, deleting x
requires at least n surviving chain-label changes. Indeed, if any a_i and b_j
both kept their old values, the forced path b_j→...→b_n→a_1→...→a_i would
require ρ(a_i)−ρ(b_j)≥n−j+i, whereas the preserved difference is i−j. At least
one entire chain must therefore lose its labels. Raising all a-labels by n
attains this bound. The experiment's scalar producer uses this canonical start.

### Blocks remove that rank cost on the same family

Place x,a_1,...,a_n in one block and y,b_1,...,b_n in another. Give roots local
label 0 and each chain position local label i. Initially both offsets are zero,
and selected witnesses follow the two original chains.

**Theorem 9 (constant-field exchange certificate).** Deleting x is certified
by D={x}, I=∅, changing only a_1's witness to b_n→a_1, and setting the a-block
offset to n. The checker examines one witness premise and one cross-block
maximum and performs one segment-tree leaf update, independently of n.

*Proof.* No rule has head x, and I is empty, so F is empty. The only selected
consumer of x is a_1, so Q contains only that retained head. Its new premise
b_n remains true. All unchanged internal chain edges increase local time.
The sole new selected cross-block edge has weight n−1+1=n, exactly the patched
offset difference. Its pair has one allocated cross-block incidence, so its
maximum tree has one leaf. Theorem 5 applies. The new least model is the old
one without x by the explicit rescued-chain derivation. □

The structural rule-dependency graph contains a strongly connected component
of 2n chain consequences, but the local certificate never traverses it. This
is a verification result, not a claim that the implemented DRed producer avoids
traversing it. The number of packet fields is constant; identifier and offset
encoding still takes O(log n) bits. A fixed maximum machine encoding would
bound n instead of making its bit cost disappear.

The family is expressible by three guarded temporal rule schemas over the
fixed horizon [0,n+1): one shift-by-one chain rule for two chain constants and
two cross-chain rules at head time 1 with shift n−1. The numerical horizon and
cross shift vary with the family parameter, but are immutable within each
session.

### Truth stability does not bound witness repair either

**Theorem 10 (explicit witness patch lower bound).** With base {x,y} and rules
x→v_i and y→v_i for i=1,...,n, for any initial selected witness map one of the
two single-seed deletions forces at least ceil(n/2) retained heads to change
witness, although the truth difference has size one.

*Proof.* Each v_i is not a base atom and must choose one of the two rules. At
least half choose the same seed. Delete that seed. All v_i remain derivable
through the other seed, but every selected rule using the removed seed is
invalid and must change. These are distinct witness-map entries. □

Offsets cannot remove this obligation for a packet format with one explicit
witness entry per head. A richer language might encode a whole family of
changes symbolically; the theorem does not rule that out. In this construction,
two rank blocks still suffice, but the verifier performs many tree updates.

Finally, let h be the sole seed and let p_i→h be n rules whose premises are
all false. Deleting h changes one truth and no retained witness, but the
closure interface of Lemma 2 contains all n rules. This is an exact sensitivity
example for the specified checker, not a universal lower bound against
algorithms with stronger cached summaries.

## 8. Work, space and producer boundaries

Let L be total ground premise incidence, and s_ij the number of potential
cross-block incidences in pair (i,j). Initialization constructs all rule,
consumer, slot and adjacency indexes in O(|U|+|R|+L) space and time, excluding
front-end grounding and the production of the initial model. The initial
certificate is checked in the same bound. The checked complete program must
remain in memory; small packets do not imply small global state.

For an update, charge the parsed packet length, the base delta, all rule-index
entries exposed by D and I, all selected-consumer entries exposed by D, the
premises of revalidated witnesses and inspected closure rules, all changed
selected incidences, and all old active pairs incident to changed offsets.
Each changed cross incidence adds O(log(1+s_ij)) segment-tree work. The number
of final maximum inequalities is at most the number of exposed/touched pairs.
Expected constant-time set and map operations give this bound in the usual
RAM dictionary model. The implementation additionally sorts its exposed sets
for deterministic traversal; its sorting terms must be added and no global
sort of the materialisation occurs in the update method. Python arbitrary
precision arithmetic charges the bit length of numbers outside a bounded-word
interpretation.

All named producer algorithms are separate from the checker. The full engine
uses an agenda and unsatisfied-premise counters. The ground DRed implementation
first closes the overdeletion set along old-active rule instances, removes it,
restores new base seeds and one-step alternate derivations, and propagates
rederived/inserted atoms. If an old selected premise is overdeleted, its head
is overdeleted as well; consequently survivors retain valid old proofs. New
proofs use already known premises, extending this surviving proof DAG in their
discovery order. Standard overdeletion/least-fixed-point reasoning establishes
the same model as full evaluation; the independent tiny interpretation oracle
checks this implementation on the declared finite spaces.

This producer is conservative, copies survivor state, and can repeat rule
checks. It is not Motik et al.'s optimized in-situ DRed or FBF implementation.
On the exchange family it overdeletes and rederives Θ(n) atoms, even though
checking the resulting block certificate has constant incidence work. Potential
synthesis also scans selected witnesses and solves block constraints. The
paper reports these costs rather than hiding them behind a verifier speedup.
No claim of complete probabilistic provenance, proof minimisation, streaming
window optimality, clinical reasoning or production security is implied.

## 10. Choosing a compatible proof

The previous criterion fixes W. Consider instead **Compatible Block Proof**:
given finite ground R, B, its least model M, a partition gamma and nonnegative
binary-encoded local labels, decide whether *some* selected witness map and
integer offsets certify M. Offsets are unbounded mathematical integers here;
the implementation's dimension/transport caps are not part of this asymptotic
problem. M can be recomputed in polynomial ground-size time, so supplying M is
not an oracle or an unverified entailment promise.

**Theorem 11 (proof-selection equivalence).** Compatible Block Proof and integer
MAX-ATOM satisfiability are polynomial-time many-one interreducible. Hardness
already holds for unary rules, an acyclic depth-one dependency graph, and a
materialisation equal to the entire supplied universe.

*Upper reduction.* Put x_i=-o_i. A selected rule r for head h requires, for every
premise b, x_gamma(h) <= x_gamma(b)+ell(h)-ell(b)-1. For each nonbase head h,
retain precisely the rules with that head whose bodies lie in M. An empty-body
alternative imposes no constraint. No alternative gives immediate contradiction.
Otherwise introduce z_r for each retained rule and the difference constraints
z_r <= x_gamma(b)+ell(h)-ell(b)-1 for every b in body(r), together with
x_gamma(h) <= max_r z_r. A difference constraint is a max atom with two equal
right-hand variables. A maximum with more than two entries is encoded by a
binary tree of fresh variables, each bounded above by its children's maximum.

For any compatible proof, set x=-o and z_r to the minimum of the indicated
premise bounds. At least the selected rule has z_r >= x_gamma(h), so the head
constraint holds. Set internal tree variables to their actual child maxima.
Conversely, any solution has z_r bounded above by every premise bound; its head
constraint guarantees some z_r >= x_gamma(h). Select that rule. All its strict
rank inequalities hold. Base heads choose their seed marker. These choices give
a valid globally ranked proof, including in the presence of recursion and
same-block incidences. The number of variables and inequalities is linear in
rules plus premise incidences, and the integer bit lengths grow only by a
constant beyond the input-label subtraction.

*Lower reduction.* Given max atoms x_z <= max(x_u,x_v)+c, make one block per
variable. For each constraint introduce a fresh nonbase head h in block z and
fresh base atoms p_u,p_v in blocks u,v. Add only p_u -> h and p_v -> h. Set
ell(h)=max(c+1,0) and ell(p_u)=ell(p_v)=ell(h)-c-1. These labels are nonnegative.
Add a base placeholder of label zero to each block so even an unused variable
has a nonempty block. The materialisation is U after one inference round.
Choosing the u rule is valid precisely when x_z <= x_u+c, and the v alternative
precisely when x_z <= x_v+c. At least one holds exactly when the max atom holds.
Fresh atoms prevent unintended rule sharing; repeated variables merely put
fresh atoms in the same block and leave this calculation unchanged. All rules
are unary and all edges go from base-only atoms to fresh heads. There are
three atoms and two rules per constraint plus one placeholder per variable;
encoding lengths are polynomial. This proves both directions. Square.

The existing MAX-ATOM/mean-payoff-game equivalence is due to Atserias and Maneva
(author-hosted report revised 3 February 2010; original report 2009), with the
MAX-ATOM foundation of Bezem, Nieuwenhuis and Rodriguez-Carbonell (LPAR 2008).
Our reduction identifies a representation-induced selection boundary; it is
not a new algorithm for games or an NP-completeness/undecidability assertion.
In particular, polynomial checking of a *given* selected proof does not imply
that choosing a compatible one is equally easy. Conversely, failure of our
first-derivation producer is not an impossibility certificate for all proofs.
A global assertion of incompatibility would need this stronger selection
problem solved, rather than one positive cycle for one chosen proof.

## 11. Certified minimum-field repair of fixed proof offsets

The complete new mathematical argument is in `docs/offset-repair.md` of this
standalone repository (the manuscript includes the principal proofs in §5.4–5.6).
It fixes the selected proof and specializes the established L0 violator-order
method, not compatible-proof selection. For feasible constraints and old offsets
a, a maximum antichain of positive reduced path violations is precisely a maximum
set of offsets that may remain unchanged. An anchor construction extends that set.
Hence the unbounded optimum is k minus the antichain width. With independent
coordinate intervals, lower and upper bounds become edges to and from a fixed
anchor; anchor-comparable coordinates are forced to change, and the same width
argument applies to the induced order on the remaining coordinates. Complete
chain partitions, actual positive graph paths, anchor paths for forced fields, and
feasible vectors meeting the resulting lower bounds provide separately checked
optima. All assumptions, proofs, numeric boundaries, oracle sufficiency, and
negative cases are stated in that document; no general mechanized proof is asserted.
