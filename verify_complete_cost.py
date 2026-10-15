#!/usr/bin/env python3
"""Untimed validation and descriptive export of retained complete-cost samples."""
import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

import complete_cost as study

PAPER_ROWS = {
    "Exchange, native": "exchange/4096/native",
    "Exchange, singleton": "exchange/4096/singleton",
    "Dense boundary": "boundary/4096/native",
    "Star": "star/4096/native",
    "Fan-in": "fanin/4096/singleton",
    "Ordinary policy": "policy/rbac_policy.csv/32/native",
    "Domain policy": "policy/rbac_with_domains_policy.csv/32/native",
    "Resource-role policy": "policy/rbac_with_resource_roles_policy.csv/32/native",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic(value):
    if isinstance(value, list):
        return [deterministic(x) for x in value]
    if isinstance(value, dict):
        return {k: deterministic(v) for k, v in value.items()
                if not k.endswith("_ns") and k not in ("repetition", "warmup", "state_bytes")}
    return value


def validate(path):
    meta = load(path / "environment.json")
    for name, expected in meta["sources_sha256"].items():
        study.require(hashlib.sha256((study.ROOT / name).read_bytes()).hexdigest() == expected,
                      "measured source changed: " + name)
    traces = [load(p) for p in sorted(path.glob("trace-*.json"))]
    fallbacks = [load(p) for p in sorted(path.glob("fallback-*.json"))]
    reps = meta["repetitions"]
    study.require(len(traces) == 27 * (reps + 1), "incomplete setting/repetition coverage")
    study.require(len(fallbacks) == reps + 1, "incomplete fallback coverage")
    groups = {}
    measured = real = noops = checks = rejections = rebuilds = 0
    for t in traces:
        key = study.case_name(t["case"])
        groups.setdefault(key, []).append(t)
        study.require(len(t["updates"]) == 12, "incomplete sequential trace")
        for r in t["updates"]:
            study.require(set(r["checks"]) == set(study.MODES))
            study.require(len({c["output_bytes"] for c in r["checks"].values()}) == 1)
            for c in r["checks"].values():
                study.require(c["accepted"] and c["check_commit_ns"] > 0 and c["output_ns"] > 0)
            if not t["warmup"]:
                checks += 3
                noops += bool(r["semantic_noop"])
                real += not r["semantic_noop"]
        if not t["warmup"]:
            measured += 1
            rejections += len(t["updates"][0]["rejection"]["checks"])
            rebuilds += len(t["recovery"]["consumers"])
    study.require(len(groups) == 27, "missing setting")
    for ts in groups.values():
        study.require({t["repetition"] for t in ts} == set(range(-1, reps)))
        expected = deterministic(ts[0])
        study.require(all(deterministic(t) == expected for t in ts), "deterministic repetition mismatch")
    summary = study.summarize(traces, fallbacks)
    study.require(summary == load(path / "summary.json"), "summary/raw mismatch")
    # Check the precise mechanism rather than inferring it from elapsed time.
    for t in traces:
        if t["case"]["family"] in ("boundary", "exchange") and t["case"]["partition"] == "native":
            r = t["updates"][0]
            boundary = t["case"]["family"] == "boundary"
            study.require(r["offset_fields"] == 1)
            study.require(r["checks"]["block"]["counters"]["pair_checks"] == (2 if boundary else 1))
            study.require(r["checks"]["ordinary-local"]["counters"]["rank_literals"] ==
                          (t["case"]["size"] + 1 if boundary else 1))
    return {"schema": "complete-cost-validation-1", "settings": 27, "warmup_traces": 27,
            "measured_traces": measured, "committed_updates_per_strategy": measured * 12,
            "real_updates_per_strategy": real, "semantic_noops_per_strategy": noops,
            "committed_checks_all_strategies": checks, "ordinary_rejections_all_strategies": rejections,
            "authoritative_base_rebuilds_all_strategies": rebuilds,
            "singleton_fallbacks_all_strategies": reps * 3,
            "source_identity_matches": True, "raw_summary_matches": True,
            "deterministic_repetitions_match": True}, traces, summary


def export_csv(summary):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(("setting", "mode", "real_updates", "noop_updates", "offset_fields", "packet_bytes",
                     "init_ms", "check_commit_ms", "steady_ms", "real_steady_ms", "output_ms",
                     "rebuild_ms", "reject_ms", "lifecycle_ms", "state_bytes"))
    for name, g in summary["groups"].items():
        for mode, v in g["modes"].items():
            row = [name, mode, g["real_updates_per_trace"], 12 - g["real_updates_per_trace"],
                   g["offset_fields_per_trace"], g["packet_bytes_per_trace"]]
            row += ["%.6f" % (v[k]["median"] / 1e6) for k in
                    ("initialize_ns", "check_commit_trace_ns", "steady_trace_ns", "real_update_trace_ns",
                     "output_trace_ns", "rebuild_ns", "rejection_ns", "lifecycle_ns")]
            row.append(v["state_bytes"]["median"])
            writer.writerow(row)
    return out.getvalue()


def export_tex(summary):
    lines = [r"\begin{tabular}{lrrr}", r"\toprule", r"Setting & Block & Direct & Full\\", r"\midrule"]
    for label, key in PAPER_ROWS.items():
        values = ["%.1f" % (summary["groups"][key]["modes"][mode]["lifecycle_ns"]["median"] / 1e6)
                  for mode in study.MODES]
        lines.append(label + " & " + " & ".join(values) + r"\\")
    return "\n".join(lines + [r"\bottomrule", r"\end{tabular}", ""])


def verify_paper_table(path, summary):
    text = path.read_text(encoding="utf-8")
    study.require(text.count(r"\label{tab:complete-cost}") == 1, "missing/duplicate complete-cost table")
    study.require(text.count(r"\input{figures/complete-cost-table}") == 1, "missing/duplicate table input")
    table = path.parent.parent / "figures" / "complete-cost-table.tex"
    study.require(table.read_bytes() == export_tex(summary).encode("utf-8"), "paper table differs from raw costs")
    study.require(re.search(r"\\subsection\{Same-information sequential costs\}", text) is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path, help="new directory for validation.json, summary.csv and complete-cost-table.tex")
    parser.add_argument("--check-exports", type=Path, help="check an existing validation/export directory without writes")
    parser.add_argument("--paper", type=Path, help="optional evaluation.tex table consistency check")
    args = parser.parse_args()
    report, _, summary = validate(args.directory)
    if args.paper:
        verify_paper_table(args.paper, summary)
        report["paper_table_matches"] = True
    if args.check_exports:
        saved = load(args.check_exports / "validation.json")
        study.require(all(saved.get(k) == v for k, v in report.items()), "validation receipt differs")
        study.require((args.check_exports / "summary.csv").read_bytes() == export_csv(summary).encode("utf-8"),
                      "all-setting CSV differs")
        study.require((args.check_exports / "complete-cost-table.tex").read_bytes() == export_tex(summary).encode("utf-8"),
                      "native table export differs")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        with (args.out / "validation.json").open("x", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        with (args.out / "summary.csv").open("x", encoding="utf-8", newline="\n") as f:
            f.write(export_csv(summary))
        with (args.out / "complete-cost-table.tex").open("x", encoding="utf-8", newline="\n") as f:
            f.write(export_tex(summary))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
