# Proof-carrying knowledge graph

A standalone, offline research artifact for **Block-Potential Certificates for
Incremental Temporal Rule Reasoning**. It checks exact finite positive Horn
materialisations after mixed base updates. It does not implement a clinical
system or deploy an access-control service.

## Run from a clean extraction

Use Python 3.10 or newer on a POSIX/Linux host with the standard `resource`
module. No package installation, network, GPU, model API, external solver, or
other project directory is required. Scientific consistency checks use explicit
failures and remain active under `python -O`; normal non-optimized execution is
still the documented route. A bounded optimized-mode smoke record is retained in
`results/optimized-mode-smoke.json`.

```sh
python example.py
python -m unittest discover -s tests -v
python reproduce.py --out reproduced-results
python summarize.py reproduced-results --compare results/campaign
python verify_artifact.py --out results/artifact-structure-check.json
```

The first command demonstrates rejection with unchanged state followed by a
valid update. The full campaign contains 49 serial jobs. Each child has an
independent 40-second parent watchdog, a 38/39-second soft/hard CPU limit, and a
3.5 GiB address-space limit. A child failure stops the campaign and retains its
stdout, stderr, and accounting. On a slower host a timeout is a reported failure,
not a missing case to exclude. There is no promise of equal timings on another
machine. Do not run several campaign drivers concurrently.

For a bounded interactive invocation, process a few jobs at a time:

```sh
python reproduce.py --out reproduced-results --max-jobs 4
python reproduce.py --out reproduced-results --resume --max-jobs 4
```

Repeat the second command until all 49 jobs are present, then run the summary
comparison. `--resume` skips only a result having a successful recorded exit;
final summarization validates all expected files and outcomes. To obtain a
small smoke check instead, use `python reproduce.py --quick --out quick-results`.
The quick route is **not** the full campaign and cannot be summarized as one.
Never point a new campaign at the retained measured directory. No output is
silently overwritten without explicit resumption.

`summary.json` describes the validated full campaign. Comparison requires all
deterministic results, dimensions, counters, accepted/rejected statuses, and
selection outcomes to match. Kernel times and per-job resource observations
are excluded from equality but retained as new measurements. It is not a
byte-identity, checksum, or software-environment attestation.

## Timing-environment provenance

`results/finite-checks.json` records an additional offline finite rerun on Windows
11 with CPython 3.12.14. It repeats all stated enumerations, both repair oracles,
216 policy updates, 168 original structured rows, 126 repair rows, and all 44 test
methods. All deterministic fields match the retained results. The reviewed driver
functions were invoked under native Windows process/memory/wall limits, not their
POSIX command-line resource controls. This local check is not a remote CI run,
mechanized proof, or replacement for the original timing observations; raw review
attempts are kept outside the deliverable.

The retained original campaign, unbounded repair, bounded repair, and earlier clean
reproduction outputs did not record CPU model/architecture, OS/kernel, or Python
implementation and full version. Those fields are not recoverable from the
retained evidence, and this artifact does not substitute the current machine or a
later rerun. `results/resource-intake.json` preserves the recorded quota and
resource envelope; the companion environment records explicitly mark the missing
fields. Consequently, the old absolute times are traceable to their raw samples
but not to a fully identified original execution environment.

New `reproduce.py` outputs write `environment.json` before the first job and link
every `execution.json` row to it. Resuming under a different recorded environment
is rejected. The unbounded and bounded repair runners embed the same environment
record in their output JSON. Deterministic comparisons continue to compare models,
counters, statuses, and byte counts while excluding time, resource, and environment
metadata.

## Files and trust boundaries

`src/checker.py` owns the complete rule indexes, selected witnesses, selected
consumer lists, block maxima, and active boundary lists. It imports none of the
producer or oracle implementations. Initialization checks a full certificate;
updates trust only that verified preceding state and the immutable input.
`src/producer.py` implements fresh semi-naive evaluation, a ground DRed
reference, fixed-proof offset synthesis, and packet construction. It is not an
optimized external engine and is not a complete search over all compatible
proof choices.

`src/reference_check.py` is a separate full-certificate scan. `src/oracle.py`
enumerates closed interpretations on tiny ground inputs. `src/temporal.py` and
`semantic_check.elaborate` are two separately implemented temporal expanders.
`semantic_check.direct_model` intentionally reuses the latter's clauses and base
and supplies only a fixed-point algorithm independent of producer counter/DRed;
it is not a third front end and shares that expander's guard, shift, and interval
failure boundary. `src/obstruction_check.py` checks explicit internal-edge or positive-cycle
obstructions. `src/selection.py` implements the two Max-Atom reduction directions
used by the finite assignment tests. `src/offset_repair.py` and
`src/bounded_offset_repair.py` synthesize exact minimum-field repairs for fixed
selected proofs, while `src/optimality_check.py` and
`src/bounded_optimality_check.py` independently validate path/chain lower-bound
certificates without importing optimizer, closure, or matching code. These
independently written components are not independent human reviews or mechanized
proofs.

`docs/model-and-proofs.md` contains the mathematical specification and core proofs.
`docs/offset-repair.md` contains the unbounded and interval-bounded repair proofs,
certificate arguments, and exact-oracle boundaries. `docs/interface.md` specifies
the executable interface, including unsupported operations. `docs/evaluation.md`
explains counts, timing, and negative results. `claim_evidence_ledger.csv` connects
retained claims to proofs and exact results; `external_resources.csv` records lawful
inputs and source attribution. `literature_calibration.csv` and
`docs/literature-calibration.md` record the completed 12+5+5 paper-planning matrix.
Public policy fixtures are retained under `inputs/casbin/`; their temporal schedules
and Horn adaptation are generated here, not observed production events.

## Retained observations

The measured campaign reports 23 passing unit tests, 32,768 exact update
transitions, 112,896 candidate packets with no wrong model accepted, 8,640
representation cases, 15,000 reduction assignments, and 216 accepted temporal
policy updates. These finite checks do not replace the general proofs. Peak
observed child RSS is 246,944 KiB; final measured campaign child CPU time including
startup is 61.6 seconds. An earlier clock-resolution problem is preserved in
`results/clock-resolution-observation.json`; the measured campaign uses elapsed
rather than short-operation CPU timings.

At family size 16,384, exchange uses a 69-byte block packet versus a 218,329-byte
explicit scalar packet. However, the reference DRed producer is slower than
fresh materialisation there. The star requires 16,384 witness replacements, and
the fan-in exposes 16,384 closure rules. Local verification loses to full scans
on those controls. No general end-to-end speedup is claimed.

## Limits and license

Fixed finite domains, positive rules, a fixed integer horizon, fixed rule set,
partition, and local labels are required. There is no negation, invented object,
program edit, horizon extension, concurrent update protocol, durable crash
transaction, or full probabilistic provenance. Ordinary packet rejection is
rolled back in memory; process failure or memory exhaustion during commit is
outside that claim. A full singleton reinitialization is a global fallback.

Original artifact files use the MIT license. Casbin records retain Apache-2.0. Do not treat the mathematical prototype as a verified operational decision service.

## Manuscript data exports

`python export_paper_data.py --out exported-data` regenerates the two numerical
LaTeX tables, four PGFPlots input files, and the underlying timing summary CSV.
Use `--check` to compare an existing export byte for byte without changing it.
This operation needs no manuscript, network, optional library, or hidden cache.
The final clean-extraction reproduction results are retained in
`results/reproduction/`, separately from the original reported measurements.
All 49 deterministic job outputs matched `results/campaign/`; no command failed or
timed out. After the explicit-check hardening, the fresh run used 118.734062 child
CPU seconds including startup, 51.154015374 kernel CPU seconds, and 248,144 KiB
peak child RSS. Runtime and resource fluctuations are retained but are not
semantic failures.

## Exact minimum-field offset repair

For a fixed feasible selected-proof graph, `src/offset_repair.py` specializes
classical L0 violator-order/maximum-antichain methods to retain as many old block
offsets as possible. It is **not** a new generic isotonic algorithm, a partition
selector, or a joint witness optimizer. `src/optimality_check.py` independently
checks a chain partition with actual weighted paths and a feasible vector meeting
the certified lower bound. It imports no synthesis or matching code.

```sh
python repair_tests.py -v
python audit_tests.py -v
python repair_experiments.py --out offset-reproduced.json --compare results/offset-repair.json
python bounded_repair_experiments.py --out bounded-reproduced.json --compare results/bounded-offset-repair.json
python export_repair_data.py --out repair-exports
python export_repair_data.py --out repair-exports --check
```

The unbounded oracle covers 4,096 directed weighted graphs and 27 old vectors each:
110,592 graph-target pairs, with 51,435 feasible and 59,157 infeasible outcomes.
It agrees on every optimum and feasibility decision, and all feasible outputs pass
independent optimality checking. The bounded oracle crosses the same graphs and
old vectors with three interval profiles: 331,776 cases, 125,577 feasible and
206,199 infeasible, again with zero optimizer or certificate disagreement. Fifteen
repair tests preserve the original 23-test/49-job contract. Six separately written
property and input-contract audits bring the delivered total to 44 test methods;
all three test commands are required for that total. Oracle and proof boundaries are in
`docs/offset-repair.md`.

Three new Horn families at 3–127 blocks retain 126 timing rows. Each setting uses
one verified session, one warm-up and seven tentative checks rolled back to that
same state. Fan-out needs one optimal field instead of 126 at 127 blocks, but the
3,439-byte optimality evidence exceeds the 61-byte update packet. The binary-tree
control gives no field improvement. On the ordered chain, both algorithms change
126 fields, and the exact minimum-field result has *more* packet bytes. The optimizers are global, use exact integers, and are capped at 256 blocks. The
bounded variant treats per-coordinate integer intervals as trusted constraints;
neither optimizer minimizes packet bytes, proof choice, or partitions.

`literature_sources.csv` maps all 63 manuscript references to primary source
locations, exact supported roles, and honest reading depth. `bibliography_verification.csv` records the
primary-record metadata cross-check, and `verify_bibliography.py` enforces the
55-reference minimum, citation/ledger equality, DOI uniqueness, and the 12+5+5
calibration contract. See `docs/bibliography-verification.md`. 
```sh
python verify_bibliography.py --minimum 55 --out results/bibliography-verification.json
```

This bibliography command is a **complete-project** check: it also reads the
sibling `../paper/` manuscript and bibliography. Run it from `artifact/` in the
delivered project, or give `--root /path/to/project` containing both `paper/` and
`artifact/`. A flat code-only repository does not contain the manuscript; its
computational reproduction is standalone, but this optional manuscript audit is
not. The frozen source and metadata ledgers do not supply source-paper full texts.

The completed planning
calibration contains 12 full AIJ slots, 5 influential/foundational slots, and 5
adjacent-venue slots (21 unique papers because one foundation overlaps), with an
AIJ bibliography-count median of 48.5. No upstream paper PDFs or implementations
are redistributed, and this planning calibration is not independent peer review.


## Current clean reproduction

`results/reproduction/` is the final clean-extraction recheck of all 49 original
jobs. Every deterministic dimension, counter, accepted/rejected result, and finite
selection outcome matched `results/campaign/`; timing and resource observations
were retained as new measurements and excluded from equality. The run completed
with zero timeouts and zero failed commands. See `results/reproduction/summary.json`
and `results/reproduction/comparison.json`.

`results/offset-repair-reproduction.json` repeats the complete unbounded oracle and
structured families: 110,592 graph–target pairs, 51,435 feasible outcomes, 59,157
infeasible outcomes, 126 workload rows, zero optimizer disagreement, and zero
certificate failure. It used 5.272505468 process CPU seconds and 94,640 KiB peak
RSS. `results/offset-repair-reproduction-comparison.json` records deterministic
identity after excluding runtime/resource fields.

`results/bounded-offset-repair-reproduction.json` repeats all 331,776 bounded cases:
125,577 feasible and 206,199 infeasible, with zero optimizer disagreement and zero
certificate failure. It used 14.112702954 process CPU seconds and 93,108 KiB peak
RSS. `results/bounded-offset-repair-reproduction-comparison.json` records the same
deterministic equality rule. The retained final logs show 23 original tests, 15
repair tests, and 6 independent property/input-contract audit tests: all 44 test
methods passed. These executions are reproducibility checks, not mechanized proofs
or independent peer review.

## Scientific workflow

The prepared `.github/workflows/scientific-checks.yml` runs the offline example,
all three test suites, the 49-job campaign with deterministic comparison, and both
complete repair oracles on Ubuntu 24.04 from a flat artifact-repository root. Its
whole scientific step has a 12-minute wall watchdog, one-core affinity, a 3.5 GiB
address-space limit, and inherited CPU limits; the drivers retain their tighter
per-child limits. Every scientific failure remains a failed step, and an
`always()` upload retains raw attempts. The existing material-integrity workflow
still checks only supplied-file and syntax integrity. Neither workflow builds the
paper, verifies external source claims, or establishes the general theorems. A
prepared workflow is not evidence that it has been run or passed on GitHub.
