# Same-information sequential cost study

The block representation compresses rank edits. Its advantage over a full scan
does not imply an advantage over an ordinary local checker with the same
partition and preceding verified state. This study separates those questions
and charges source adaptation, initialization, production, maintenance, output
and two forms of recovery within the existing serial in-memory interface.

## Consumers and equal information

All three consumers receive the **same UTF-8 JSON packet**, fixed program,
partition, local labels and verified predecessor. The producer's truth set and
selected proof are identical. No baseline must expand the packet into explicit
scalar rank fields before receiving it.

* `block`: unchanged `src/checker.py`, with reversible pair-maximum trees.
* `ordinary-local`: `src/ordinary_check.py`, using the same Head/Body and selected
  consumers, plus an index of active individual cross-block incidences. It skips
  invariant internal edges and inactive potential edges. It checks newly selected
  edges and the active edges incident to changed offsets, without pair maxima.
* `full`: the same ordinary interface assembles the complete candidate from the
  packet, runs `reference_check.verify_all`, and installs the new state. Candidate
  copying and installation are timed; rebuilding local indexes is not required.

The schema helpers and Verdict are shared, not independently reimplemented.
The ordinary-local mathematical argument uses the paper's closure and membership
frontiers. For ranks, every newly selected edge is checked. An unchanged internal
edge cancels its block offset. An unchanged cross-block edge can change its
inequality only if one endpoint's offset changes; it is then in the old active
incidence index. Removing/adding exactly the committed selected incidences
preserves that index for the next operation. Thus it establishes the same exact
ranked-model guarantee, including tentative checks and ordinary rejection.

If `a` unchanged active boundary incidences are exposed by changed offsets and
`d` incidences change selected status, the ordinary control charges `a+d` direct
edge work (plus exposed-set sorting and dictionary costs). The maximum-tree
variant replaces repeated pair-edge comparisons by distinct-pair comparisons
but charges logarithmic tree updates for changed incidences. Neither cost is
bounded by the number of changed truths. These are specified implementations,
not optimality claims over all possible dynamic checker data structures.

## Inputs and discriminating controls

There are 27 settings. At sizes 64, 512 and 4096, exchange has native and singleton
representations, star its native two-block representation, and inactive fan-in
singletons. A new `boundary` family has exchange's two chains plus `n` distinct
heads `c_j`, all with rule `a_n -> c_j`, in a third block with fixed local label
`32*n+1`. This label is specified before timing. In twelve base updates a chain
offset can rise by at most `12*n`, so this third block need not translate.

On the first deletion of `x`, ordinary-local checks one selected cross edge in
pure exchange: it does **not** scan the translated chain. Boundary instead has
`n+1` direct rank checks versus two maximum-pair inequalities, with one changed
tree leaf. This isolates active boundary multiplicity rather than block size.
Later updates include the opposite seed deletion, reinsertion, mixed seed swaps,
complete model loss and rederivation. Each designed trace has eleven genuine
base-set changes and a separately identified final no-op.

The remaining twelve settings reuse the exact three retained Casbin fixtures,
the existing six-schema Horn adapter and twelve-record-edit schedules at horizons
8 and 32, with temporal and singleton partitions. Each has nine genuine semantic
updates and three union-normalized no-ops. There are still no offset changes in
these policy schedules. The adapter re-grounds the entire fixed rule input on
each snapshot; this actual cost is included rather than replaced by a hypothetical
incremental policy front end. Source records and Apache-2.0 notices are unchanged.
No Casbin implementation or new external service is executed.

## Timing and cost boundary

Each setting has one retained warm-up and five fresh whole-trace repetitions.
Within a trace, updates really commit; they are not repeated tentative checks
against an unchanged state. Consumer order rotates cyclically across repetitions
and steps. All stages use `perf_counter_ns`; samples and min/median/max are retained.
Fresh saturation, full certificate checks and exact state comparisons are untimed
diagnostics outside the compared stages. This is a sum-of-stages cost account,
not a single end-to-end wall-clock latency including those diagnostics.

Initialization charges source reading/generation and grounding, schedule creation,
construction of the specified partition, producer indexes, initial least-model
and offset production, full consumer initialization, and a complete output export.
Source builders initially emit a provisional layout; its allocation remains in
input cost and is not silently subtracted. The measured partition stage derives
the declared structural/temporal grouping or singleton arrays. It is **not** an
automatic discovery or search for good partitions.

Every update charges the actual adapter/base normalization, set differences and
their sorted caller lists, DRed production, certificate synthesis, producer offset
state copying/application, JSON plus UTF-8 encoding, UTF-8 decoding plus strict
parsing, checking **including commit and auxiliary-index maintenance**, and complete
answer generation. Structured output is sorted point-model JSON text; policy
output coalesces all accepted points to intervals and generates JSON text. Output
byte counts are diagnostics; there is no socket, file sink or output-I/O timing.

One invalid packet precedes the first valid update of every trace. Where possible
it fails a rank inequality after provisional tree changes; otherwise it is a
schema rejection. Encoding, parsing, rejection and rollback are timed, and the
whole persistent state, including tree leaves, is compared before/after outside
timing. A subsequent valid update must commit normally.

State-loss recovery rereads/regenerates the authoritative source and final base,
rebuilds the declared partition and producer, recomputes witnesses/offsets,
fully initializes each consumer, and exports the complete answer. Witnesses and
offsets may differ from those in the discarded session; the least model/output
must agree. A separate four-atom control starts from a valid coarse partition,
deletes two redundant seeds, records a positive block-cycle synthesis failure,
then pays for singleton layout, fresh production, full checked initialization
and output. No failed coarse proof is relabelled as successful local repair.

`lifecycle_ns` is initialization plus twelve normal updates, one ordinary rejection
and one source-to-output rebuild in each repetition. The summaries take a median
of those per-repetition sums, **not** a sum of unrelated medians. This explicit
event mix is not a predicted production failure frequency or a universal
amortization/break-even law. Disk persistence, authenticated transport,
distributed ordering, crash transactions and process-failure recovery are not
implemented by the original consumer and are not assigned fictitious costs.

Reachable CPython object sizes are recorded without timing, identity-deduplicated
within each consumer. They describe the actual prototypes, including their
canonical rule representations; they are not isolated process RSS, peak memory,
or an implementation-independent memory lower bound. Normal interpreter GC is
left enabled, and outliers are retained. The shared host runner excludes other
coordinated measurement/compile holders, not unrelated OS activity. No per-process
CPU affinity or 3.5-GiB/POSIX resource limit is asserted for this new Windows run.

## Reproduction and validation

Run from the standalone artifact root using Python 3.10+ and the standard library:

```sh
python -B complete_cost_regression.py -v
python -B complete_cost.py --check
# Use the coordinated host's measurement runner when available:
python -B complete_cost.py --out fresh-complete-cost --repetitions 5
python -B verify_complete_cost.py fresh-complete-cost --out fresh-validation
python -B verify_complete_cost.py results/complete-cost --check-exports results/complete-cost-validation
```

The regression suite has eight methods, including all 20,736 candidate packets
for every two-atom unary program, old/new bases, candidate truth set, applicable
witness/seed choice, and offsets in `{0,1,2}^2`. Three checkers agree on acceptance,
and every accepted model agrees with a test-local closed-superset intersection.
No general theorem is inferred from this finite search. `--check` runs eleven
small settings and 132 committed updates per strategy without reading a clock
or writing results. Normal measurements refuse an existing output directory,
retain each trace immediately, and preserve an explicit failure record on error.

Current samples are `results/complete-cost/`; validation, all-setting median CSV
and native table are in `results/complete-cost-validation/`. They add 135
measured traces, 1,620 updates per strategy (1,365 genuine changes and 255 no-ops),
4,860 committed checks, 405 ordinary rejections, 405 authoritative-base rebuilds
and 15 singleton fallback initializations. The original 49-job campaign and all
its reported historical timings are unchanged.

The raw files were produced before the delivery directory was given its semantic
name. Moving the directory changes neither samples nor source identities. The
recorded input and producing-source hashes remain exact; documentation, table
export and CI edits are not retrospectively substituted into that timing record.
The verifier/exporter is not one of the timed producing sources. This current
measurement is separate from all original historical campaigns and does not
reconstruct an unidentified execution host.

`verify_complete_cost.py --out` exports `summary.csv`, `validation.json` and the
native `complete-cost-table.tex` without rerunning measurements. `--check-exports`
checks existing exports byte for byte. The manuscript imports the same table,
and `--paper` checks that include and its exact numerical content. The flat
artifact CI checks raw/source identities and both exports in addition to the
new regression suite and optimized untimed trace; it does not time CI as another
sample of this environment.

## Observations

The recorded environment is Windows 11 kernel 10.0.28000, AMD64, CPython 3.12.14,
with processor descriptor `Intel64 Family 6 Model 151 Stepping 2, GenuineIntel`.
The descriptor is the runtime's reported value, not an inferred commercial CPU
name. Five samples are descriptive observations rather than population confidence
intervals.

At `n=4096`, pure exchange's first shift has one rank check in both local methods:
block median 29.0 microseconds (26.2--35.3), ordinary-local 24.2 (20.8--35.9).
The first dense-boundary shift has two maximum inequalities versus 4,097 direct
edge comparisons: medians 36.5 microseconds (30.7--40.8) and 2.8732 milliseconds
(2.8201--21.8038). Full checking there is 6.6465 milliseconds (6.2161--6.8061).
The ordinary-local outlier is retained. Packet sizes are identical at 67 bytes
within each setting. The contrast locates the benefit in boundary multiplicity,
not in forcing a baseline to visit every translated atom.

Whole-trace check/commit medians at size 4,096 are, in block/ordinary-local/full
order: exchange 22.231/25.833/55.034 milliseconds; boundary
53.425/47.889/80.017; star 108.686/48.069/36.008; fan-in
3.332/3.374/5.638. The traces include collapse/rederivation and do not all retain
the first shift's tiny frontier. Full stage accounting gives the following
median lifecycle sums, in milliseconds:

| Setting | Block | Ordinary local | Full |
| --- | ---: | ---: | ---: |
| Exchange, native, 4096 | 178.512 | 177.373 | 198.424 |
| Exchange, singleton, 4096 | 343.716 | 330.010 | 301.959 |
| Dense boundary, native, 4096 | 292.121 | 301.019 | 287.796 |
| Star, native, 4096 | 260.459 | 154.911 | 139.218 |
| Fan-in, singleton, 4096 | 52.407 | 39.386 | 39.971 |
| Ordinary RBAC, temporal, H=32 | 185.707 | 174.778 | 179.043 |
| Domain RBAC, temporal, H=32 | 412.024 | 379.210 | 388.631 |
| Resource-role RBAC, temporal, H=32 | 297.893 | 277.262 | 280.333 |

For the three policy traces, repeated grounding alone takes medians
126.726/275.368/201.974 milliseconds; the block check/commit totals are
3.374/4.996/4.039 milliseconds. The ordinary local baseline has lower lifecycle
medians on all three. The first boundary shift's large kernel saving does not
establish an overall lifecycle win over full checking; differences comparable
to the observed variation are not significance claims.

Source-to-output rebuilding is substantial: at size 4,096, exchange's median
rebuild is 42.380 milliseconds for block state and 37.417 for full state;
dense boundary is 79.114 and 51.468. The separate four-atom incompatible-proof
control costs 44.0/38.4/34.8 microseconds through failed synthesis and complete
singleton fallback. This tiny control establishes the charged path and its
semantics, not a scale-independent fallback latency. The raw files and CSV
retain initialization, maintenance, output, rejection, rebuild, memory and all
27 settings, not just the displayed largest-scale rows.
