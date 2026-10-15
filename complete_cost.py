#!/usr/bin/env python3
"""Sequential, same-information cost study; stdlib only, no historical reruns.

Use the shared measurement runner on coordinated hosts. --check is untimed and
does not write. Measured output directories must not exist. All measured stages,
warmups, no-ops, failures, and source identities are retained, not filtered.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from cases import alternate_star, exchange, inactive_fanin
from checker import BOUND, Session, strict_loads
from ordinary_check import OrdinarySession
from policy_cases import FIXTURES, make_policy, snapshots
from producer import Program, certificate, dred, full, potentials
from reference_check import verify_all
from run_environment import capture_environment
from temporal import coalesce, ground

MODES = ("block", "ordinary-local", "full")


def require(value, detail="complete-cost invariant failed"):
    if not value:
        raise RuntimeError(detail)


class Clock:
    def __init__(self, measured=True):
        self.measured = measured

    def call(self, fn, *args, **kwargs):
        if not self.measured:
            return fn(*args, **kwargs), None
        start = time.perf_counter_ns()
        value = fn(*args, **kwargs)
        return value, time.perf_counter_ns() - start


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def wire_encode(value):
    return encoded(value).encode("utf-8")


def wire_parse(wire):
    return strict_loads(wire.decode("utf-8"))


def prepare_delta(base, newbase):
    removed, added = base - newbase, newbase - base
    return removed, added, sorted(removed), sorted(added)


def advance_offsets(offsets, packet):
    new = list(offsets)
    for b, value in packet["offset"].items():
        new[int(b)] = value
    return new


def signature(s):
    """Untimed exact persistent-state comparison, including all tree leaves."""
    result = {"base": sorted(s.base), "model": sorted(s.model),
              "witness": sorted(s.witness.items()), "offset": list(s.offset)}
    for name in ("consumers", "active_neighbours", "boundary", "head_index", "body_index"):
        if hasattr(s, name):
            result[name] = [sorted(x) for x in getattr(s, name)]
    if hasattr(s, "trees"):
        result["trees"] = [(pair, tuple(t.values)) for pair, t in sorted(s.trees.items())]
    return result


def retained_bytes(obj):
    """Reachable CPython object bytes, identity-deduplicated; not RSS or peak."""
    seen = set()

    def visit(value):
        key = id(value)
        if key in seen:
            return 0
        seen.add(key)
        size = sys.getsizeof(value)
        if isinstance(value, dict):
            size += sum(visit(k) + visit(v) for k, v in value.items())
        elif isinstance(value, (list, tuple, set, frozenset)):
            size += sum(visit(v) for v in value)
        elif hasattr(value, "__dict__"):
            size += visit(value.__dict__)
        return size
    return visit(obj)


def source(case):
    family, n = case["family"], case["size"]
    if family == "policy":
        spec = make_policy(case["fixture"], n)
        raw, base, atoms = ground(spec, "singleton")
        return raw, base, atoms, spec
    if family in ("exchange", "boundary"):
        raw, base = exchange(n, False)
        if family == "boundary":
            first = raw["n"]
            raw["n"] += n
            raw["rules"].extend({"head": h, "body": [n]} for h in range(first, raw["n"]))
            raw["blocks"] = list(range(raw["n"]))
            raw["local"] = [0] * raw["n"]
    elif family == "star":
        raw, base = alternate_star(n)
    elif family == "fanin":
        raw, base = inactive_fanin(n)
    else:
        raise ValueError("unknown family")
    return raw, base, None, None


def layout(raw, atoms, case, force_singleton=False):
    n, size = raw["n"], case["size"]
    if force_singleton or case["partition"] == "singleton":
        blocks, labels = list(range(n)), [0] * n
    elif case["family"] in ("exchange", "boundary"):
        chain_atoms = 2 * (size + 1)
        blocks = [int(i >= size + 1) for i in range(chain_atoms)]
        labels = [i % (size + 1) for i in range(chain_atoms)]
        if case["family"] == "boundary":
            # Fixed slack for the entire twelve-update schedule, not fitted to
            # timings: these heads stay rank-valid without translating block C.
            blocks += [2] * size
            labels += [32 * size + 1] * size
    elif case["family"] == "star":
        blocks, labels = [0, 0] + [1] * size, [0] * n
    elif case["family"] == "policy":
        groups = {}
        blocks, labels = [], []
        for p, args, t in atoms:
            key = (p, args)
            if key not in groups:
                groups[key] = len(groups)
            blocks.append(groups[key])
            labels.append(t)
    else:
        raise ValueError("no native partition for family")
    return dict(raw, blocks=blocks, local=labels)


def schedule(case, base, spec):
    if case["family"] == "policy":
        return snapshots(spec)[1:]
    if case["family"] == "fanin":
        h = case["size"]
        states = [set(), {h}, set(), {h}, {0}, {h}, set(), {0}, {h}, set(), {h}, {h}]
    else:
        x, y = sorted(base)
        states = [{y}, {x, y}, {x}, {x, y}, {x}, {y}, {x, y},
                  set(), {x, y}, {x}, {x, y}, {x, y}]
    return [("step-%02d" % i, b) for i, b in enumerate(states, 1)]


def normalize(case, target):
    if case["family"] == "policy":
        return ground(target, "singleton")
    return None, set(target), None


def make_session(mode, raw, base, model, why, offsets):
    args = (raw, sorted(base), sorted(model), {str(h): r for h, r in why.items()}, offsets)
    if mode == "block":
        return Session(*args)
    return OrdinarySession(*args, strategy="local" if mode == "ordinary-local" else "full")


def output(s, atoms):
    # A complete observable answer, not the diagnostic inspect() export.
    return encoded(coalesce(atoms, s.model) if atoms is not None else sorted(s.model))


def rank_mutation(raw, packet, model, why):
    for h in sorted(model):
        r = why[h]
        if r >= 0:
            for b in raw["rules"][r]["body"]:
                if raw["blocks"][b] != raw["blocks"][h]:
                    bad = copy.deepcopy(packet)
                    bad["offset"][str(raw["blocks"][h])] = -BOUND
                    return bad, "rank-after-provisional-changes"
    bad = copy.deepcopy(packet)
    bad["extra"] = True
    return bad, "schema-before-mutation"


def trace(case, repetition, clock):
    (raw0, base, atoms, spec), input_ns = clock.call(source, case)
    targets, schedule_ns = clock.call(schedule, case, base, spec)
    raw, partition_ns = clock.call(layout, raw0, atoms, case)
    pg, program_ns = clock.call(Program, raw)
    (model, why, _), materialize_ns = clock.call(full, pg, base)
    (offsets, info), potential_ns = clock.call(potentials, pg, model, why)
    require(offsets is not None, info)
    sessions, initialization, state_bytes = {}, {}, {}
    order = MODES[repetition % 3:] + MODES[:repetition % 3]
    for mode in order:
        sessions[mode], initialization[mode] = clock.call(make_session, mode, raw, base, model, why, offsets)
        state_bytes[mode] = retained_bytes(sessions[mode])
    initial_output, initial_output_ns = clock.call(output, sessions["block"], atoms)
    result = {"case": case, "repetition": repetition,
              "warmup": repetition == -1, "atoms": raw["n"], "rules": len(raw["rules"]),
              "initial": {"input_build_ns": input_ns, "schedule_ns": schedule_ns,
                          "partition_ns": partition_ns, "producer_index_ns": program_ns,
                          "materialize_ns": materialize_ns, "potential_ns": potential_ns,
                          "consumer_init_ns": initialization, "state_bytes": state_bytes,
                          "output_ns": initial_output_ns, "output_bytes": len(initial_output.encode())},
              "updates": []}
    for step, (label, target) in enumerate(targets):
        (nr, nb, na), front_ns = clock.call(normalize, case, target)
        if nr is not None:
            require(nr == raw0 and na == atoms, "immutable program changed")
        (removed, added, removed_list, added_list), delta_ns = clock.call(prepare_delta, base, nb)
        (nm, nw, pc), produce_ns = clock.call(dred, pg, model, why, base, removed, added)
        (packet, evidence), synthesize_ns = clock.call(certificate, pg, model, why, offsets, nm, nw)
        require(packet is not None, evidence)
        newoffset, maintain_ns = clock.call(advance_offsets, offsets, packet)
        # Diagnostics are untimed and not charged to any consumer.
        fm, _, _ = full(pg, nb)
        require(fm == nm, "DRed/fresh mismatch")
        require(verify_all(raw, nb, nm, nw, newoffset)[0], "producer certificate invalid")
        wire, serialize_ns = clock.call(wire_encode, packet)
        row = {"step": step, "label": label, "base_removed": len(removed), "base_added": len(added),
               "semantic_noop": not removed and not added,
               "truth_fields": len(packet["delete"]) + len(packet["insert"]),
               "witness_fields": len(packet["witness"]), "offset_fields": len(packet["offset"]),
               "packet_bytes": len(wire), "producer_counters": pc,
               "shared": {"front_end_ns": front_ns, "delta_ns": delta_ns, "produce_ns": produce_ns,
                          "synthesize_ns": synthesize_ns, "producer_state_ns": maintain_ns,
                          "serialize_ns": serialize_ns}, "checks": {}}
        if step == 0:
            bad, kind = rank_mutation(raw, packet, nm, nw)
            bad_wire, bad_encode_ns = clock.call(wire_encode, bad)
            row["rejection"] = {"kind": kind, "checks": {}}
            row["rejection"]["serialize_ns"] = bad_encode_ns
            for mode in order:
                before = signature(sessions[mode])
                bad_parsed, bp_ns = clock.call(wire_parse, bad_wire)
                verdict, br_ns = clock.call(sessions[mode].check, removed_list, added_list, bad_parsed)
                require(not verdict.accepted, (mode, "mutation accepted"))
                require(before == signature(sessions[mode]), (mode, "rejection changed state"))
                row["rejection"]["checks"][mode] = {"parse_ns": bp_ns, "check_rollback_ns": br_ns,
                                                              "reason": verdict.reason,
                                                              "counters": verdict.counters}
        order = MODES[(repetition + step) % 3:] + MODES[:(repetition + step) % 3]
        answers = []
        for mode in order:
            parsed, parse_ns = clock.call(wire_parse, wire)
            verdict, check_ns = clock.call(sessions[mode].check, removed_list, added_list, parsed)
            require(verdict.accepted, (mode, verdict.reason))
            answer, out_ns = clock.call(output, sessions[mode], atoms)
            answers.append(answer)
            require((sessions[mode].base, sessions[mode].model, sessions[mode].witness, sessions[mode].offset)
                    == (nb, nm, nw, newoffset), "committed states disagree")
            row["checks"][mode] = {"parse_ns": parse_ns, "check_commit_ns": check_ns,
                                   "output_ns": out_ns, "output_bytes": len(answer.encode()),
                                   "accepted": True, "counters": verdict.counters}
        require(len(set(answers)) == 1, "observable answers disagree")
        result["updates"].append(row)
        base, model, why, offsets = nb, nm, nw, newoffset

    # State loss: reread/regenerate the source, construct the declared partition,
    # recompute from the authoritative FINAL base, verify and rebuild consumers.
    # All schedules end at their original base; assert rather than assume it.
    (rr0, rb, ra, _), reload_ns = clock.call(source, case)
    require(rb == base and rr0 == raw0 and ra == atoms, "final authoritative source mismatch")
    rr, rp_ns = clock.call(layout, rr0, ra, case)
    rpg, ri_ns = clock.call(Program, rr)
    (rm, rw, _), rf_ns = clock.call(full, rpg, rb)
    (ro, re), rs_ns = clock.call(potentials, rpg, rm, rw)
    require(ro is not None, re)
    require(rm == model, "recovery changed least model")
    recovery = {"input_reload_ns": reload_ns, "partition_ns": rp_ns,
                "producer_index_ns": ri_ns, "materialize_ns": rf_ns, "potential_ns": rs_ns,
                "consumers": {}}
    for mode in order:
        recovered, rc_ns = clock.call(make_session, mode, rr, rb, rm, rw, ro)
        answer, out_ns = clock.call(output, recovered, ra)
        require(answer == answers[0], "recovered output mismatch")
        recovery["consumers"][mode] = {"init_ns": rc_ns, "output_ns": out_ns}
    result["recovery"] = recovery
    return result


def fallback_trial(repetition, clock):
    raw = {"n": 4, "rules": [{"head": 0, "body": [3]}, {"head": 2, "body": [1]}],
           "blocks": [0, 0, 1, 1], "local": [0, 1, 0, 1]}
    base, nb = set(range(4)), {1, 3}
    pg = Program(raw)
    m, w, _ = full(pg, base)
    o, _ = potentials(pg, m, w)
    old = {mode: make_session(mode, raw, base, m, w, o) for mode in MODES}
    (nm, nw, _), prod_ns = clock.call(dred, pg, m, w, base, base - nb, set())
    (packet, obstruction), failed_ns = clock.call(certificate, pg, m, w, o, nm, nw)
    require(packet is None and obstruction["kind"] == "positive_cycle", "missing incompatible-proof control")
    case = {"family": "exchange", "size": 1, "partition": "singleton"}
    scalar, partition_ns = clock.call(layout, raw, None, case, True)
    newpg, index_ns = clock.call(Program, scalar)
    (fm, fw, _), full_ns = clock.call(full, newpg, nb)
    (fo, _), synth_ns = clock.call(potentials, newpg, fm, fw)
    require(fm == nm and fo is not None, "singleton fallback failed")
    rebuilt = {}
    for mode in MODES:
        before = signature(old[mode])
        new, init_ns = clock.call(make_session, mode, scalar, nb, fm, fw, fo)
        answer, out_ns = clock.call(output, new, None)
        require(before == signature(old[mode]), "fallback modified rejected old session")
        rebuilt[mode] = {"init_ns": init_ns, "output_ns": out_ns, "output_bytes": len(answer.encode())}
    return {"repetition": repetition, "warmup": repetition == -1,
            "obstruction": obstruction, "failed_produce_ns": prod_ns, "failed_synthesis_ns": failed_ns,
            "partition_ns": partition_ns, "producer_index_ns": index_ns,
            "materialize_ns": full_ns, "potential_ns": synth_ns, "consumers": rebuilt}


def cases(quick=False):
    result = []
    for n in ([4] if quick else [64, 512, 4096]):
        for family, parts in (("exchange", ("native", "singleton")),
                              ("boundary", ("native",)),
                              ("star", ("native",)), ("fanin", ("singleton",))):
            result.extend({"family": family, "size": n, "partition": part} for part in parts)
    for name in FIXTURES:
        for h in ([4] if quick else [8, 32]):
            result.extend({"family": "policy", "size": h, "fixture": name, "partition": part}
                          for part in ("native", "singleton"))
    return result


def case_name(case):
    return "/".join(str(case[k]) for k in ("family", "fixture", "size", "partition") if k in case)


def describe(xs):
    return {"min": min(xs), "median": statistics.median(xs), "max": max(xs)}


def summarize(traces, fallbacks):
    groups = {}
    for t in traces:
        if not t["warmup"]:
            groups.setdefault(case_name(t["case"]), []).append(t)
    result = {"groups": {}, "measured_traces": sum(len(ts) for ts in groups.values()),
              "fallback_trials": sum(not x["warmup"] for x in fallbacks)}
    for name, ts in groups.items():
        record = {"repetitions": len(ts), "updates_per_trace": len(ts[0]["updates"]),
                  "real_updates_per_trace": sum(not r["semantic_noop"] for r in ts[0]["updates"]),
                  "offset_fields_per_trace": sum(r["offset_fields"] for r in ts[0]["updates"]),
                  "packet_bytes_per_trace": sum(r["packet_bytes"] for r in ts[0]["updates"]), "modes": {}}
        for mode in MODES:
            init, steady, check, outputs, recovery, rejection, state = [], [], [], [], [], [], []
            real_steady = []
            for t in ts:
                i = t["initial"]
                init.append(sum(i[k] for k in ("input_build_ns", "schedule_ns", "partition_ns",
                                             "producer_index_ns", "materialize_ns", "potential_ns", "output_ns"))
                            + i["consumer_init_ns"][mode])
                check.append(sum(r["checks"][mode]["check_commit_ns"] for r in t["updates"]))
                outputs.append(sum(r["checks"][mode]["output_ns"] for r in t["updates"]))
                def update_total(r):
                    c = r["checks"][mode]
                    return sum(r["shared"].values()) + c["parse_ns"] + c["check_commit_ns"] + c["output_ns"]
                steady.append(sum(update_total(r) for r in t["updates"]))
                real_steady.append(sum(update_total(r) for r in t["updates"] if not r["semantic_noop"]))
                rec = t["recovery"]
                recovery.append(sum(v for k, v in rec.items() if k != "consumers")
                                + sum(rec["consumers"][mode].values()))
                rej = t["updates"][0]["rejection"]["checks"][mode]
                rejection.append(t["updates"][0]["rejection"]["serialize_ns"] +
                                 rej["parse_ns"] + rej["check_rollback_ns"])
                state.append(i["state_bytes"][mode])
            record["modes"][mode] = {"initialize_ns": describe(init), "check_commit_trace_ns": describe(check),
                                      "output_trace_ns": describe(outputs), "steady_trace_ns": describe(steady),
                                      "real_update_trace_ns": describe(real_steady), "rebuild_ns": describe(recovery),
                                      "rejection_ns": describe(rejection), "state_bytes": describe(state),
                                      "lifecycle_ns": describe([a+b+c+d for a,b,c,d in zip(init,steady,recovery,rejection)])}
        result["groups"][name] = record
    return result


def source_identity():
    paths = [Path(__file__), ROOT / "run_environment.py"]
    paths += [ROOT / "src" / (x + ".py") for x in
              ("checker", "ordinary_check", "producer", "reference_check", "cases", "temporal", "policy_cases")]
    paths += [ROOT / "inputs" / "casbin" / name for name in FIXTURES]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true", help="untimed quick functional trace; no writes")
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.check:
        for case in cases(True):
            trace(case, 0, Clock(False))
        fallback_trial(0, Clock(False))
        print("UNTIMED: 11 settings, 132 committed updates per strategy, rejection/rebuild/fallback passed")
        return
    if args.out is None or not 1 <= args.repetitions <= 20:
        parser.error("measurement requires --out and 1..20 repetitions")
    if args.out.exists():
        parser.error("refusing existing output directory")
    args.out.mkdir(parents=True)
    environment = capture_environment()
    environment["recorded_utc"] = datetime.now(timezone.utc).isoformat()
    metadata = {"schema": "p069-complete-cost-2", "environment": environment,
                "sources_sha256": source_identity(), "repetitions": args.repetitions,
                "warmups_per_setting": 1, "clock": "perf_counter_ns", "consumer_order": "cyclic counterbalanced",
                "scope": "serial in-memory offline prototype; no disk/network persistence or crash transaction",
                "same_information": "identical compressed packet, fixed program/partition/proof and verified predecessor",
                "output": "complete point-model JSON; temporal models coalesced to intervals",
                "accounting": "sum of disjoint stages, including delta sorting, producer offset copying and UTF-8 wire conversion; diagnostics excluded",
                "memory": "identity-deduplicated reachable sys.getsizeof bytes; not peak RSS"}
    def save(name, value):
        with (args.out / name).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
    save("environment.json", metadata)
    traces, fallbacks = [], []
    try:
        for case in cases():
            for repetition in range(-1, args.repetitions):
                t = trace(case, repetition, Clock())
                save("trace-%03d.json" % len(traces), t)
                traces.append(t)
            print("COMPLETE " + case_name(case), flush=True)
        for repetition in range(-1, args.repetitions):
            f = fallback_trial(repetition, Clock())
            save("fallback-%02d.json" % len(fallbacks), f)
            fallbacks.append(f)
        save("summary.json", summarize(traces, fallbacks))
        print("COMPLETE %d trace files; %d measured traces; same-state/output checks passed" %
              (len(traces), sum(not t["warmup"] for t in traces)), flush=True)
    except Exception as exc:
        save("failure.json", {"exception": type(exc).__name__, "message": str(exc),
                              "completed_trace_files": len(traces), "completed_fallback_files": len(fallbacks)})
        raise


if __name__ == "__main__":
    main()
