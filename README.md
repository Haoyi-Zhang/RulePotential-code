# Block-Potential Certificates

An offline artifact for *Block-Potential Certificates for Incremental Temporal Rule Reasoning*. It checks exact finite positive Horn materialisations after mixed base updates. It does not deploy an access-control service or clinical system.

## Requirements and quick checks

Run from this directory with Python 3.10+ and the standard library. Original campaign/repair runners require POSIX/Linux's `resource` module. The complete-cost tools and PDF-tool regressions also run on Windows. No package installation, network, GPU, model API, external solver, or other project is needed for computational reproduction. Normal execution is documented; scientific consistency checks use explicit failures and remain active under `python -O`.

The test suites are separate commands:

```sh
python -B example.py
python -B -m unittest discover -s tests -v
python -B repair_tests.py -v
python -B audit_tests.py -v
python -B potential_regression.py -v
python -B complete_cost_regression.py -v
python -B pdf_tools_regression.py -v
```

Their method counts are 23, 15, 6, 6, 8, and 2: 60 in the current inventory. Discovery under `tests/` alone runs 23, not 60. Historical 44-test receipts cover only the first three suites. The six potential regressions and eight complete-cost regressions are untimed; the latter include 20,736 two-atom candidate packets checked against a test-local interpretation oracle. PDF-tool tests mock Poppler output and need no Poppler installation.

## Original campaign

Choose a fresh output directory, never the retained `results/campaign/`:

```sh
python -B reproduce.py --out reproduced-results
python -B summarize.py reproduced-results --compare results/campaign
```

The full run has 49 serial jobs. Each child has a 40-second watchdog, 38/39-second soft/hard CPU limits, and a 3.5 GiB address-space limit. Failures/timeouts stop the campaign and retain stdout, stderr, and accounting. Do not run multiple campaign drivers concurrently. No cross-host timing equality is promised.

For bounded interactive execution:

```sh
python -B reproduce.py --out reproduced-results --max-jobs 4
python -B reproduce.py --out reproduced-results --resume --max-jobs 4
```

Repeat the second command until all 49 jobs exist, then summarize/compare. A bounded driver exit alone does not establish a complete campaign. Resume skips only outputs with successful recorded exits and rejects a changed recorded environment. `--quick` instead runs the unit suite and one small timing sample; it cannot be summarized as the full campaign. Existing nonempty output requires explicit resumption.

Comparison checks deterministic dimensions, counters, outcomes, and selection results, excluding kernel times, resources, and environment metadata. New runs write `environment.json` before their first job and link accounting rows to it.

## Fixed-proof minimum-field repair

The unbounded and interval-bounded optimizers retain as many old offsets as possible for a fixed selected proof. They do not choose a partition or proof, minimize packet bytes, or introduce a new generic isotonic algorithm. Both use exact integers and are capped at 256 blocks. The bounded variant trusts the supplied per-coordinate integer intervals.

```sh
python -B repair_experiments.py --out offset-reproduced.json --compare results/offset-repair.json
python -B bounded_repair_experiments.py --out bounded-reproduced.json --compare results/bounded-offset-repair.json
```

The unbounded oracle covers 110,592 graph-target pairs (51,435 feasible, 59,157 infeasible); the bounded oracle covers 331,776 cases (125,577 feasible, 206,199 infeasible). Retained optimizer/certificate disagreement counts are zero. These are finite checks, not mechanized general proofs. `docs/offset-repair.md` gives assumptions, certificates, and oracle bounds.

Three structured families retain 126 timing rows: one verified session and warm-up per setting, then seven tentative checks rolled back to that state, not fresh initialization. At 127 blocks, fan-out needs one optimal field instead of 126, but 3,439 bytes of optimality evidence exceed its 61-byte update packet. The tree gives no field improvement; ordered-chain exact repair changes the same 126 fields and has more packet bytes.

## Same-information complete costs

The block checker, an ordinary local checker with active individual boundary incidences, and a full ranked-model scan consume identical compressed packets and verified predecessors. Both local checkers skip unchanged internal edges; a dense-boundary control isolates pair-maximum aggregation rather than making the local baseline scan an entire translated block.

```sh
python -B complete_cost.py --check
python -B verify_complete_cost.py results/complete-cost --check-exports results/complete-cost-validation
```

The first command runs an untimed smoke trace without writing results; the second checks retained samples, measured source identities, and exports without new measurements. To make a separately authorized new measurement, choose absent output directories and use the coordinated host's measurement runner when available:

```sh
python -B complete_cost.py --out fresh-complete-cost --repetitions 5
python -B verify_complete_cost.py fresh-complete-cost --out fresh-validation
```

`results/complete-cost/` retains environment, source identities, warm-ups, and every sample; `results/complete-cost-validation/` retains validation, all-setting medians, and the native LaTeX table. There are 27 settings and 135 measured twelve-update traces: 1,365 genuine base changes and 255 no-ops per checker, 4,860 accepted commits, 405 rejection/rollback checks, 405 source-to-output rebuilds, and 15 singleton fallback initializations. All committed states/complete outputs agree. This run identifies CPython 3.12.14 on Windows 11/AMD64; the reported processor descriptor/kernel are retained in its environment record.

At size 4,096 the first dense-boundary shift checks two pair inequalities versus 4,097 direct edges, with median check/commit times of 36.5 microseconds and 2.8732 milliseconds. Pure exchange checks one edge in both local controls and takes 29.0 versus 24.2 microseconds. The star's twelve-update check totals are 108.686/48.069/36.008 milliseconds for block/local/full. Policy schedules have no offset changes and repeated grounding dominates their cost. These conditional kernel savings are not a general lifecycle advantage.

Initialization, structural partition construction, production/maintenance, UTF-8 packet handling, check/commit, complete JSON answers, rejection, and authoritative-base rebuilding are charged. Lifecycle sums one initialization, twelve updates, one rejection, and one rebuild; that event mix is not an estimated production failure frequency. No durable crash transaction, persistence, automatic partition discovery, or external service is included. Definitions and all losses remain in `docs/complete-cost.md`.

## Data exports

Export retained observations without rerunning measurements, using separate output directories:

```sh
python -B export_paper_data.py --out exported-data
python -B export_paper_data.py --out exported-data --check
python -B export_repair_data.py --out repair-exports
python -B export_repair_data.py --out repair-exports --check
```

The first exporter produces two numerical LaTeX tables, four PGFPlots inputs, and a timing-summary CSV. The second produces the repair table and all-setting CSV. Both need no manuscript/cache/network; `--check` compares existing export bytes without rewriting them. The complete-cost verifier's `--out` additionally generates `complete-cost-table.tex`; `--paper ../paper/sections/evaluation.tex` can check its manuscript consumer in a full project.

## Implementation and contract

`src/checker.py` owns rule indexes, witnesses, selected consumers, block maxima, and boundary lists without importing producer/oracle/full-scan implementations. Initialization checks a full certificate; updates trust that verified predecessor and immutable input. `src/producer.py` supplies fresh semi-naive evaluation, a ground DRed reference, fixed-proof offset synthesis, and packets, not an optimized external engine or complete proof-choice search. Fixed-proof synthesis reuses one sorted immutable edge sequence per call; transport rebase builds its own. Proof choices, obstruction edges, counters, and formats remain deterministic; no measured speedup is attributed to that bookkeeping.

`src/reference_check.py` is a full scan; `src/oracle.py` enumerates tiny closed interpretations. `src/temporal.py` and `semantic_check.elaborate` separately expand temporal input. `semantic_check.direct_model` reuses the latter's clauses/base and checks fixed-point evaluation, not a third independent front end. Obstruction, selection-reduction, and independent repair-optimality checkers remain under `src/`.

The contract requires finite domains, positive fixed rules, a fixed integer horizon, partition, and local labels. It excludes negation, invented objects, rule edits, horizon extension, concurrent updates, durable crash transactions, and full probabilistic provenance. Ordinary rejection rolls back in memory; process failure/memory exhaustion during commit is outside that guarantee. Singleton reinitialization is a global fallback. Specification/proofs, interface, and evaluation details are in `docs/model-and-proofs.md`, `docs/interface.md`, and `docs/evaluation.md`.

## Retained evidence and provenance

The original campaign records 32,768 update transitions, 112,896 candidate packets with no wrong model accepted, 8,640 representation cases, 15,000 reduction assignments, and 216 temporal policy updates. At size 16,384 exchange uses a 69-byte block packet versus 218,329 explicit scalar bytes, but the DRed producer is slower than fresh materialisation. Star/fan-in local checks lose to full scans on their controls. The clock-resolution observation and all negative results remain in `results/`.

`results/reproduction/` retains a complete 49-job comparison; `results/offset-repair-reproduction.json` and `results/bounded-offset-repair-reproduction.json` retain the repair reruns and separate comparisons. `results/finite-checks.json` records a Windows finite rerun. `results/measurements/current-linux/` records Ubuntu 24.04.5/CPython 3.12.14 execution of the historical 44-test suite, 49 jobs, and both repair oracles. None is relabelled as a new 60-test/native measurement.

The original campaign, repairs, and earlier clean reproduction did not record CPU model/architecture, OS/kernel, or full Python identity. Those fields remain explicitly unrecorded; later environments do not reconstruct them. `results/resource-intake.json` retains the quota/envelope. Absolute historical times remain raw observations with that host-identity limit.

The scientific workflow runs all six current test commands, untimed optimized smoke, retained complete-cost/export checking, the 49-job comparison, and both repair oracles on Ubuntu 24.04. It retains failures and raw outputs with a 12-minute scientific-step watchdog, one-core affinity, and 3.5 GiB limit. Material-integrity CI checks syntax/files only; neither workflow proves theorems or checks live external sources.

## Optional project audits and licenses

`verify_artifact.py` checks frozen evidence, inventory, and import boundaries without rerunning experiments. It also checks the PDF via Poppler (`pdfinfo`, `pdftotext`) when run in a complete project with a sibling `paper/`; a flat artifact checkout skips that project-only section. Its default output is stdout:

```sh
python -B verify_artifact.py
```

`verify_bibliography.py` is a complete-project check requiring both `artifact/` and `paper/`, not a flat-checkout dependency. It checks local citation/ledger consistency and the retained calibration contract, not publisher truth or unread source bodies:

```sh
python -B verify_bibliography.py --minimum 55 --out bibliography-check.json
```

Use `--root /path/to/project` for an explicit full-project root. The source/metadata ledgers retain 63 references and precise reading scopes; `docs/bibliography-verification.md` and `docs/literature-calibration.md` explain them. The 12+5+5 planning slots contain 21 unique papers because of one overlap, not independent peer review. `results/bibliography-verification-final.json` is a consumed frozen validator input and is retained unchanged.

`claim_evidence_ledger.csv` maps claims to evidence; `external_resources.csv`, `literature_sources.csv`, and `bibliography_verification.csv` retain lawful source identities. Casbin fixtures and attribution remain in `inputs/casbin/`, with original Apache-2.0 terms under `licenses/`; their temporal schedules/Horn adaptation are generated examples, not production observations or Casbin conformance. Original files use MIT (`LICENSE`). No upstream paper PDFs or implementations are redistributed.
