# Evaluation contract and interpretation

## Finite spaces

The correct-update space enumerates all 512 subsets of the nine unary rules on
three atoms and all 64 old/new base pairs: 32,768 transitions. It checks exact
least models against an all-interpretations oracle and validates without commit,
checking unchanged state after each trial. The policy trace and unit tests
separately exercise committed multi-update sequences.

The candidate-packet space has two atoms and six possible rules: for each head,
bodies `{0}`, `{1}`, and `{0,1}`. All 64 rule subsets, 16 old/new base pairs,
candidate subsets, applicable head rule choices plus the seed marker, and both
offsets in `{0,1,2}` are enumerated. There are 112,896 candidate packets, 8,448
accepted, and no wrong model accepted. Every covered base pair has a correct
certificate. This does not exhaust all programs or packet integers.

Representation checks use the 64 directed edge subsets on three atoms, five
set partitions, and 27 local-label assignments in `{0,1,2}**3`: 8,640 cases.
Offsets are enumerated through `(k-1)*3` inclusively. The representability theorem
justifies this bound for these weights. All 6,861 infeasible cases have separately
checked internal-edge or positive-cycle witnesses for the selected proof.

Selection checks use one or two max atoms over two variables with constants
`{-1,0,1}`: 24 single constraints and 576 ordered pairs. All 25 assignments in
`{-2,-1,0,1,2}**2` are checked, giving 15,000 assignment cases. These validate
algebraic correspondence, not an unbounded decision algorithm.

## Designed timing families

Exchange isolates shared rank translation. The alternate-support star isolates
explicit witness-map replacement. Inactive fan-in isolates the declared closure
frontier. All have one changed truth. Sizes are 16, 64, 256, 1,024, 4,096, and
16,384, with one warm-up and seven individual measured operations per setting.
The exchange family has both chain blocks and singleton offsets; the other
families use their declared fixed partitions, yielding 168 rows.

Initialization, fresh materialisation, DRed, synthesis, serialization, parsing,
local checking, and full checking are timed separately. The producer and checker
use the same fixed ground input. Full checking does not rebuild the local
checker indices. Reference DRed is a new conservative ground implementation,
not an optimized upstream system; claims comparing to RDFox or DRedMTL would be
unsupported. Operation counters describe the declared implementation rather than
hardware instruction counts.

Order is fixed: block then scalar; within a repetition, fresh materialisation,
DRed, synthesis, serialization, parsing, local check, then full check. No claim
of randomized-order statistical control is made. Seven-run min/median/max are
descriptive. Cache, memory layout, garbage collection, and container scheduling
can affect timings. A CPU clock gave zero readings for short operations in an
earlier run; the record is preserved, and all final kernel elapsed measurements
are positive. The original CPU model/architecture, OS/kernel, and Python
implementation/full version were not recorded for any reported timing group and
are not recoverable; current-host details are not substituted. It is incorrect to
divide by the old zero measurements, mix the two clocks in a speedup, or treat the
absolute values as fully environment-reproducible.

## Policy traces

Three retained fixtures have 5, 6, and 6 source records. There are horizons 8, 16,
and 32, twelve fixed edits after initialization, and temporal/singleton block
choices: 216 sequential updates. Two separately implemented expanders are compared
on each snapshot. The tuple fixed-point evaluator then reuses the second expander's
clauses and base, so it checks saturation against producer counter/DRed but shares
that expander's guard, shift, and interval-expansion failure boundary. This is
example adaptation, not a third end-to-end semantics, a real service experiment,
a medical experiment, or Casbin conformance.

No offset changes occur in these traces. Packet sizes therefore match between
partitions. Temporal grouping reduces exposed block-pair counts only; it is not
evidence of naturally occurring rank-shift compression. Failed synthesis would
have been recorded as incompatible-first-proof and stopped that trace rather
than silently changing the partition. No such failure occurs in the measured
trace. Overlap normalization includes semantic no-op edits by design.

## Negative findings and limits

The chosen DRed producer overdeletes both chains in exchange and is slower than
fresh computation despite a small accepted packet. At the largest size, star
and fan-in local checks are slower than their full scans. Neither a small truth
delta nor a small offset packet guarantees small total work. A production engine
comparison, realistic workload-derived block selection, selection-aware producer,
and unbounded temporal semantics are outside the evidence.

The general arguments are in model-and-proofs.md. The checker, full scanner,
oracles, and reductions are independently implemented in the software sense,
not independently authored or externally reviewed. All finite tests supplement,
rather than mechanically certify, those arguments.

## Clean standalone reproduction

The complete repository was run from the final clean project without depending on
the manuscript directory. The example, 23 original tests, 15 repair tests, 6
independent property/input-contract audits, all 49 campaign jobs, both exact
repair campaigns, and both data exporters succeeded.
The original-campaign comparison found no difference in deterministic dimensions,
operation counts, accepted/rejected outcomes, or finite selection checks.

Final evidence is retained in `results/reproduction/`,
`results/offset-repair-reproduction.json`, and
`results/bounded-offset-repair-reproduction.json`. Their comparison records exclude
only runtime/resource fields. After explicit-check hardening, the 49-job run used
118.734062 child CPU seconds including startup and 248,144 KiB peak child RSS; the
unbounded and bounded repair runs used 5.272505468 and 14.112702954 process CPU
seconds with peaks of 94,640 and 93,108 KiB, respectively. Timing equality is not
required across executions. This
is an execution and evidence-alignment check, not independent mathematical
certification.

## Fixed-proof offset optimization

`results/offset-repair.json` is a separate original campaign: 110,592 exact
weighted graph-target pairs, 126 timing rows, eight unbounded-repair unit tests,
and independent optimality verification. `results/bounded-offset-repair.json`
adds 331,776 exact graph/old-vector/interval cases and seven bounded-repair tests.
It contains 125,577 feasible and 206,199 infeasible cases, with zero feasibility,
minimum-count, or certificate disagreement. Full enumeration bounds, hypotheses,
controls, measured costs, and limits are in `docs/offset-repair.md`. The original
49-job results are unchanged and are not relabelled as outcomes of either optimizer.
The complete executable test count is 23 original, 15 repair, and 6 independent
property/input-contract audit tests: 44 methods in total.

The new samples use tentative checks on one unchanged verified session per
setting, not reallocation of persistent state at every repetition. They cannot
be interpreted as fresh-initialization timings. New source data are exported by
`export_repair_data.py`; all-setting medians/minima/maxima and deterministic sizes
are available in its CSV export. The rejected wide-conjunction pilot is retained
as an input-boundary observation, not a successful timing sample.
