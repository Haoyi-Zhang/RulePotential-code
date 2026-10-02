#!/usr/bin/env python3
"""Deterministic structural audit for the delivered research artifact.

This audit checks evidence presence, campaign invariants, test inventory, ledger
integrity, and independence boundaries visible in Python imports.  It does not
re-run the experiments, prove the mathematical theorems, query publishers, or
replace scientific review.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

CUTOFF = date(2026, 9, 16)
EXPECTED_PROJECT_ENTRIES = {"README.md", "artifact", "paper"}
EXPECTED_TEST_METHODS = {"tests": 23, "repair_tests.py": 15, "audit_tests.py": 6}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not reader.fieldnames:
        raise ValueError(f"missing CSV header: {path}")
    return list(reader.fieldnames), rows


def _test_count(path: Path) -> int:
    files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
    total = 0
    for file in files:
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        total += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
            for node in ast.walk(tree)
        )
    return total


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def _function_calls(path: Path, function_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            calls: set[str] = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        calls.add(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        calls.add(child.func.attr)
            return calls
    raise ValueError(f"missing function {function_name} in {path}")


def _pdf_pages(path: Path) -> int:
    completed = subprocess.run(
        ["pdfinfo", str(path)], check=True, text=True, capture_output=True
    )
    match = re.search(r"^Pages:\s+(\d+)\s*$", completed.stdout, re.MULTILINE)
    if not match:
        raise ValueError("pdfinfo did not report a page count")
    return int(match.group(1))


def _pdf_page_text(path: Path, page: int) -> str:
    completed = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), str(path), "-"],
        check=True, text=True, capture_output=True,
    )
    return completed.stdout


def audit(artifact: Path) -> dict[str, Any]:
    artifact = artifact.resolve()
    project = artifact.parent if artifact.name == "artifact" and (artifact.parent / "paper").is_dir() else None
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "README.md", "LICENSE", "run_environment.py", "src/checker.py", "src/producer.py",
        "src/offset_repair.py", "src/optimality_check.py",
        "src/bounded_offset_repair.py", "src/bounded_optimality_check.py",
        "tests/test_core.py", "repair_tests.py", "audit_tests.py",
        "claim_evidence_ledger.csv", "external_resources.csv",
        "literature_sources.csv", "literature_calibration.csv",
        "bibliography_verification.csv", "verify_bibliography.py",
        "results/campaign/summary.json", "results/campaign/environment.json",
        "results/reproduction/environment.json", "results/offset-repair.json",
        "results/bounded-offset-repair.json",
        "results/bibliography-verification-final.json",
        "inputs/casbin/SOURCE.md", "licenses/Apache-2.0.txt",
    ]
    for relative in required:
        if not (artifact / relative).is_file():
            errors.append(f"missing required file: {relative}")

    test_counts: dict[str, int] = {}
    for name, expected in EXPECTED_TEST_METHODS.items():
        path = artifact / name
        if path.exists():
            observed = _test_count(path)
            test_counts[name] = observed
            if observed != expected:
                errors.append(f"{name} has {observed} test methods; expected {expected}")

    boundaries = {
        "src/checker.py": {"producer", "oracle", "reference_check"},
        "src/optimality_check.py": {"offset_repair"},
        "src/bounded_optimality_check.py": {"bounded_offset_repair"},
        "src/semantic_check.py": {"temporal", "producer"},
        "src/obstruction_check.py": {"producer"},
    }
    import_boundaries: dict[str, list[str]] = {}
    for relative, forbidden in boundaries.items():
        path = artifact / relative
        if not path.exists():
            continue
        found = sorted(_imports(path) & forbidden)
        import_boundaries[relative] = found
        if found:
            errors.append(f"{relative} imports forbidden implementation modules: {found}")

    temporal_dependency = {
        "direct_model_calls": sorted(_function_calls(artifact / "src/semantic_check.py", "direct_model")),
        "grounder_imports": sorted(_imports(artifact / "src/semantic_check.py")),
    }
    if "elaborate" not in temporal_dependency["direct_model_calls"]:
        errors.append("semantic_check.direct_model no longer reuses elaborate; paper scope must be re-audited")

    timing_environment_records: dict[str, str] = {}
    for relative in ("results/campaign/environment.json", "results/reproduction/environment.json"):
        path = artifact / relative
        if not path.is_file():
            continue
        env = _json(path)
        status = env.get("recording_status")
        timing_environment_records[relative] = str(status)
        if status != "not_recorded_for_original_measurement":
            errors.append(f"{relative} must truthfully mark the retained run environment as unrecorded")
        for group in ("cpu", "architecture", "operating_system", "python"):
            if not isinstance(env.get(group), dict):
                errors.append(f"{relative} missing {group} object")
    for relative in ("results/campaign/execution.json", "results/reproduction/execution.json"):
        path = artifact / relative
        if not path.is_file():
            continue
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list) or not all(
            row.get("environment_file") == "environment.json" and
            row.get("environment_recording_status") == "not_recorded_for_original_measurement"
            for row in records
        ):
            errors.append(f"{relative} contains timing rows not linked to its environment record")
    for relative in (
        "results/offset-repair.json", "results/bounded-offset-repair.json",
        "results/offset-repair-reproduction.json", "results/bounded-offset-repair-reproduction.json",
    ):
        path = artifact / relative
        if path.is_file():
            env = _json(path).get("environment", {})
            timing_environment_records[relative] = str(env.get("recording_status"))
            if env.get("recording_status") != "not_recorded_for_original_measurement":
                errors.append(f"{relative} must mark its retained timing environment as unrecorded")

    removable_asserts: dict[str, int] = {}
    for relative in ("campaign.py", "summarize.py", "pilot.py"):
        path = artifact / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        count = sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
        removable_asserts[relative] = count
        if count:
            errors.append(f"{relative} contains {count} optimization-removable assert statements")

    campaign = _json(artifact / "results/campaign/summary.json")
    campaign_expectations = {
        ("completed_jobs",): 49,
        ("units", "tests"): 23,
        ("units", "failures"): 0,
        ("units", "errors"): 0,
        ("correct", "transitions"): 32768,
        ("correct", "oracle_mismatches"): 0,
        ("correct", "rollback_mismatches"): 0,
        ("candidate", "candidate_packets"): 112896,
        ("candidate", "wrong_models_accepted"): 0,
        ("candidate", "rollback_mismatches"): 0,
        ("representation", "cases"): 8640,
        ("representation", "oracle_mismatches"): 0,
        ("selection", "assignments"): 15000,
        ("selection", "forward_mismatches"): 0,
        ("selection", "reverse_mismatches"): 0,
        ("policy_updates",): 216,
        ("timeouts",): 0,
        ("failed_commands",): 0,
    }
    for path, expected in campaign_expectations.items():
        value: Any = campaign
        try:
            for key in path:
                value = value[key]
        except (KeyError, TypeError):
            errors.append(f"campaign summary missing {'.'.join(path)}")
            continue
        if value != expected:
            errors.append(f"campaign {'.'.join(path)}={value!r}; expected {expected!r}")

    repair = _json(artifact / "results/offset-repair.json")
    oracle = repair.get("oracle", {})
    for key, expected in {
        "graph_target_pairs": 110592,
        "feasible_pairs": 51435,
        "infeasible_pairs": 59157,
        "oracle_mismatches": 0,
        "certificate_failures": 0,
    }.items():
        if oracle.get(key) != expected:
            errors.append(f"unbounded repair {key}={oracle.get(key)!r}; expected {expected}")
    if len(repair.get("workload_rows", [])) != 126:
        errors.append("unbounded repair must retain 126 workload rows")

    bounded = _json(artifact / "results/bounded-offset-repair.json")
    for key, expected in {
        "cases": 331776,
        "feasible_cases": 125577,
        "infeasible_cases": 206199,
        "optimizer_mismatches": 0,
        "certificate_failures": 0,
    }.items():
        if bounded.get(key) != expected:
            errors.append(f"bounded repair {key}={bounded.get(key)!r}; expected {expected}")

    bibliography = _json(artifact / "results/bibliography-verification-final.json")
    if bibliography.get("status") != "PASS":
        errors.append("frozen bibliography audit is not PASS")
    for key, expected in {
        "bibliography_entries": 63,
        "distinct_cited_entries": 63,
        "source_ledger_rows": 63,
        "verification_ledger_rows": 63,
        "nocite_commands": 0,
    }.items():
        if bibliography.get(key) != expected:
            errors.append(f"bibliography {key}={bibliography.get(key)!r}; expected {expected}")

    ledger_counts: dict[str, int] = {}
    ledger_specs = [
        (
            "claim_evidence_ledger.csv",
            "claim_id",
            {"claim_id", "claim", "proof_location", "maturity",
             "implementation_or_test", "raw_evidence", "paper_location",
             "boundary", "fresh_recheck"},
        ),
        (
            "literature_sources.csv",
            "bibkey",
            {"bibkey", "title", "year", "primary_url", "reading_depth",
             "supported_claim", "cited_sections", "access_date", "integration"},
        ),
        (
            "bibliography_verification.csv",
            "bibkey",
            {"bibkey", "title", "authors", "year", "venue",
             "record_url", "record_type", "checked_fields",
             "verification_status", "checked_date", "notes"},
        ),
    ]
    for relative, unique_field, required_fields in ledger_specs:
        header, rows = _csv(artifact / relative)
        ledger_counts[relative] = len(rows)
        missing_columns = sorted(required_fields - set(header))
        if missing_columns:
            errors.append(f"{relative} missing required columns: {missing_columns}")
        seen: set[str] = set()
        for index, row in enumerate(rows, start=2):
            empty = sorted(field for field in required_fields if not row.get(field, "").strip())
            if empty:
                errors.append(f"{relative}:{index} has empty required fields: {empty}")
            key = row.get(unique_field, "")
            if key in seen:
                errors.append(f"{relative}:{index} duplicates {unique_field}={key!r}")
            seen.add(key)

    header, resources = _csv(artifact / "external_resources.csv")
    ledger_counts["external_resources.csv"] = len(resources)
    resource_ids: set[tuple[str, str]] = set()
    for index, row in enumerate(resources, start=2):
        if any(not row.get(field, "").strip() for field in header):
            errors.append(f"external_resources.csv:{index} has an empty required field")
        url = row.get("url", "")
        if not url.startswith("https://"):
            errors.append(f"external_resources.csv:{index} URL is not HTTPS")
        identity = (row.get("name", ""), url)
        if identity in resource_ids:
            errors.append(f"external_resources.csv:{index} duplicates name/URL")
        resource_ids.add(identity)
        try:
            if date.fromisoformat(row.get("access_date", "")) > CUTOFF:
                errors.append(f"external_resources.csv:{index} has future access date")
        except ValueError:
            errors.append(f"external_resources.csv:{index} has invalid access date")

    project_checks: dict[str, Any] = {}
    if project is not None:
        entries = {path.name for path in project.iterdir()}
        project_checks["root_entries"] = sorted(entries)
        if entries != EXPECTED_PROJECT_ENTRIES:
            errors.append(
                f"project root entries are {sorted(entries)}; expected {sorted(EXPECTED_PROJECT_ENTRIES)}"
            )
        pdf = project / "paper/main.pdf"
        if not pdf.is_file():
            errors.append("paper/main.pdf is missing")
        else:
            pages = _pdf_pages(pdf)
            project_checks["pdf_pages"] = pages
            if pages != 37:
                errors.append(f"paper/main.pdf has {pages} pages; expected 37")
            page_30 = _pdf_page_text(pdf, 30)
            page_31 = _pdf_page_text(pdf, 31)
            reference_start = 31 if re.search(r"(?m)^References\s*$", page_31) else None
            project_checks["body_end_page"] = 30 if reference_start == 31 else None
            project_checks["reference_start_page"] = reference_start
            if reference_start != 31 or re.search(r"(?m)^References\s*$", page_30):
                errors.append("paper body/reference boundary is not pages 30/31")

    transients = sorted(
        str(path.relative_to(artifact))
        for path in artifact.rglob("*")
        if path.is_file() and (path.suffix == ".pyc" or "__pycache__" in path.parts)
    )
    if transients:
        warnings.append(f"working tree contains {len(transients)} Python cache files; delivery packaging must exclude them")

    return {
        "status": "PASS" if not errors else "FAIL",
        "scope": (
            "Deterministic local structure, evidence, import-boundary, and frozen-result audit; "
            "not experiment re-execution, live bibliographic verification, mechanized proof, or peer review."
        ),
        "artifact_root": str(artifact),
        "project_mode": project is not None,
        "test_method_counts": test_counts,
        "total_test_methods": sum(test_counts.values()),
        "import_boundary_violations": import_boundaries,
        "temporal_validation_dependency": temporal_dependency,
        "timing_environment_records": timing_environment_records,
        "optimization_removable_asserts": removable_asserts,
        "ledger_row_counts": ledger_counts,
        "project_checks": project_checks,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.artifact)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
