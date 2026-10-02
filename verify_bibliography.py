#!/usr/bin/env python3
"""Audit bibliography identity, use, and traceability without network access.

The audit is deliberately split into two layers:
1. deterministic local checks over the manuscript, BibTeX and ledgers; and
2. the frozen `bibliography_verification.csv`, whose rows record the primary or
   canonical scholarly record inspected during the project audit.

A PASS proves consistency with those recorded checks. It is not a promise that
publishers will never correct metadata, nor a substitute for author review.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.I)
YEAR_RE = re.compile(r"^(?:18|19|20)\d{2}$")
CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)?\{([^}]*)\}")
NOCITE_RE = re.compile(r"\\nocite\s*\{")


def _read_braced(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise ValueError("expected opening brace")
    depth = 1
    i = start + 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth:
        raise ValueError("unterminated brace")
    return text[start + 1 : i - 1], i


def parse_bibtex(path: Path) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str]] = {}
    cursor = 0
    header = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.S)
    while (match := header.search(text, cursor)) is not None:
        kind, key = match.group(1).lower(), match.group(2)
        depth = 1
        i = match.end()
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        if depth:
            raise ValueError(f"unterminated BibTeX entry {key}")
        if key in entries:
            raise ValueError(f"duplicate BibTeX key {key}")
        body = text[match.end() : i - 1]
        fields: dict[str, str] = {"entrytype": kind, "bibkey": key}
        p = 0
        while p < len(body):
            while p < len(body) and (body[p].isspace() or body[p] == ","):
                p += 1
            if p >= len(body):
                break
            fm = re.match(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", body[p:])
            if not fm:
                raise ValueError(f"cannot parse field in {key}: {body[p:p+40]!r}")
            name = fm.group(1).lower()
            p += fm.end()
            if p >= len(body):
                raise ValueError(f"missing value for {key}.{name}")
            if body[p] == "{":
                value, p = _read_braced(body, p)
            elif body[p] == '"':
                q = p + 1
                escaped = False
                out = []
                while q < len(body):
                    ch = body[q]
                    if ch == '"' and not escaped:
                        break
                    out.append(ch)
                    escaped = ch == "\\" and not escaped
                    if ch != "\\":
                        escaped = False
                    q += 1
                if q >= len(body):
                    raise ValueError(f"unterminated quote for {key}.{name}")
                value, p = "".join(out), q + 1
            else:
                q = p
                while q < len(body) and body[q] != ",":
                    q += 1
                value, p = body[p:q].strip(), q
            if name in fields:
                raise ValueError(f"duplicate field {key}.{name}")
            fields[name] = re.sub(r"\s+", " ", value).strip()
        entries[key] = fields
        cursor = i
    if not entries:
        raise ValueError("no BibTeX entries found")
    return entries


def manuscript_citations(root: Path) -> tuple[set[str], int]:
    keys: set[str] = set()
    nocite = 0
    for path in sorted((root / "paper").rglob("*.tex")):
        text = path.read_text(encoding="utf-8")
        nocite += len(NOCITE_RE.findall(text))
        for match in CITE_RE.finditer(text):
            keys.update(k.strip() for k in match.group(1).split(",") if k.strip())
    return keys, nocite


def _csv_rows(path: Path, key: str) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty CSV: {path}")
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if not value or value in index:
            raise ValueError(f"missing/duplicate {key} in {path}: {value!r}")
        index[value] = row
    return rows, index


def _canonical_doi(value: str) -> str:
    return value.strip().lower()


def _expected_venue(entry: dict[str, str]) -> str:
    """Return the venue label that the verification ledger must mirror."""
    if entry.get("journal"):
        return entry["journal"]
    if entry.get("booktitle"):
        return entry["booktitle"]
    if entry.get("archiveprefix"):
        return entry["archiveprefix"]
    note = entry.get("note", "").lower()
    if "technical report" in note or "preprint" in note:
        return "Technical report"
    return ""


def audit(root: Path, minimum: int) -> dict[str, Any]:
    bib = parse_bibtex(root / "paper" / "references.bib")
    cited, nocite = manuscript_citations(root)
    source_rows, sources = _csv_rows(root / "artifact" / "literature_sources.csv", "bibkey")
    verification_rows, verification = _csv_rows(
        root / "artifact" / "bibliography_verification.csv", "bibkey"
    )
    calibration_path = root / "artifact" / "literature_calibration.csv"
    with calibration_path.open(newline="", encoding="utf-8") as handle:
        calibration_rows = list(csv.DictReader(handle))
    if not calibration_rows:
        raise ValueError(f"empty CSV: {calibration_path}")
    calibration_slots: set[tuple[str, str]] = set()
    for row in calibration_rows:
        composite = (row.get("group", ""), row.get("slot", ""))
        if not all(composite) or composite in calibration_slots:
            raise ValueError(
                f"missing/duplicate (group, slot) in {calibration_path}: {composite!r}"
            )
        calibration_slots.add(composite)

    errors: list[str] = []
    warnings: list[str] = []
    keys = set(bib)
    if len(keys) < minimum:
        errors.append(f"bibliography has {len(keys)} entries; minimum is {minimum}")
    if nocite:
        errors.append(f"found {nocite} \\nocite command(s)")
    for name, observed in [("citations", cited), ("source ledger", set(sources)),
                           ("verification ledger", set(verification))]:
        missing = sorted(keys - observed)
        extra = sorted(observed - keys)
        if missing:
            errors.append(f"{name} missing keys: {missing}")
        if extra:
            errors.append(f"{name} has extra keys: {extra}")

    dois: dict[str, str] = {}
    titles: dict[str, str] = {}
    non_doi = []
    for key, entry in bib.items():
        for field in ("author", "title", "year"):
            if not entry.get(field):
                errors.append(f"{key} missing {field}")
        if entry["entrytype"] == "article" and not entry.get("journal"):
            errors.append(f"{key} article missing journal")
        if entry["entrytype"] == "inproceedings" and not entry.get("booktitle"):
            errors.append(f"{key} proceedings entry missing booktitle")
        year = entry.get("year", "")
        if not YEAR_RE.fullmatch(year):
            errors.append(f"{key} has invalid year {year!r}")
        title_norm = re.sub(r"[^a-z0-9]+", "", entry.get("title", "").lower())
        if title_norm in titles:
            errors.append(f"duplicate normalized title: {key}, {titles[title_norm]}")
        titles[title_norm] = key
        doi = entry.get("doi", "").strip()
        if doi:
            if not DOI_RE.fullmatch(doi):
                errors.append(f"{key} has malformed DOI {doi!r}")
            canon = _canonical_doi(doi)
            if canon in dois:
                errors.append(f"duplicate DOI: {key}, {dois[canon]} ({doi})")
            dois[canon] = key
        else:
            non_doi.append(key)

        source = sources.get(key, {})
        verify = verification.get(key, {})
        for column in ("title", "year", "primary_url", "reading_depth", "supported_claim",
                       "cited_sections", "access_date", "integration"):
            if not source.get(column, "").strip():
                errors.append(f"{key} source ledger missing {column}")
        if source.get("title") != entry.get("title"):
            errors.append(f"{key} title differs between BibTeX and source ledger")
        if source.get("year") != year:
            errors.append(f"{key} year differs between BibTeX and source ledger")
        if _canonical_doi(source.get("doi", "")) != _canonical_doi(doi):
            errors.append(f"{key} DOI differs between BibTeX and source ledger")
        url = source.get("primary_url", "")
        if not url.startswith("https://"):
            errors.append(f"{key} primary URL is not HTTPS")
        try:
            if date.fromisoformat(source.get("access_date", "")) > date(2026, 9, 16):
                errors.append(f"{key} has future access date")
        except ValueError:
            errors.append(f"{key} has invalid access date")

        required_verify = ("title", "authors", "year", "venue", "record_url",
                           "record_type", "checked_fields", "verification_status",
                           "checked_date", "notes")
        for column in required_verify:
            if not verify.get(column, "").strip():
                errors.append(f"{key} verification ledger missing {column}")
        expected_metadata = (
            ("title", entry.get("title", "")),
            ("authors", entry.get("author", "")),
            ("year", year),
            ("venue", _expected_venue(entry)),
            ("volume", entry.get("volume", "")),
            ("number", entry.get("number", "")),
            ("pages", entry.get("pages", "")),
            ("doi", doi),
        )
        for column, expected in expected_metadata:
            if verify.get(column, "") != expected:
                errors.append(f"{key} verification {column} differs from BibTeX")
        if verify.get("verification_status") != "primary_record_cross_checked":
            errors.append(f"{key} verification status is not primary_record_cross_checked")
        try:
            if date.fromisoformat(verify.get("checked_date", "")) > date(2026, 9, 16):
                errors.append(f"{key} verification has future date")
        except ValueError:
            errors.append(f"{key} verification has invalid checked_date")
        record_url = verify.get("record_url", "")
        if not record_url.startswith("https://"):
            errors.append(f"{key} verification URL is not HTTPS")
        if doi and record_url.lower() != f"https://doi.org/{doi}".lower() and not verify.get("notes", ""):
            warnings.append(f"{key} uses a noncanonical record URL")
        if not doi and verify.get("record_type") not in {
            "author_manuscript", "institutional_publication_record"
        }:
            errors.append(f"{key} lacks DOI without an approved non-DOI record type")

    # Exactly the venue-calibration contract: 12 AIJ, 5 influential, 5 adjacent.
    group_counts: dict[str, int] = {}
    unique_calibration: set[str] = set()
    for row in calibration_rows:
        group = row.get("group", "")
        group_counts[group] = group_counts.get(group, 0) + 1
        key = row.get("bibkey", "")
        if key not in bib:
            errors.append(f"calibration slot {row.get('slot')} uses unknown bibkey {key!r}")
        unique_calibration.add(key)
    expected_groups = {"same_venue": 12, "influential": 5, "adjacent_venue": 5}
    if group_counts != expected_groups:
        errors.append(f"calibration groups {group_counts}, expected {expected_groups}")
    if len(unique_calibration) != 21:
        errors.append(f"calibration has {len(unique_calibration)} unique papers; expected 21")

    result: dict[str, Any] = {
        "status": "PASS" if not errors else "FAIL",
        "scope": (
            "Deterministic consistency audit plus frozen primary-record cross-check ledger; "
            "not independent peer review and not a live publisher-registry query."
        ),
        "bibliography_entries": len(bib),
        "distinct_cited_entries": len(cited),
        "source_ledger_rows": len(source_rows),
        "verification_ledger_rows": len(verification_rows),
        "doi_entries": len(dois),
        "non_doi_entries": sorted(non_doi),
        "calibration_slots": len(calibration_rows),
        "calibration_unique_papers": len(unique_calibration),
        "calibration_group_counts": group_counts,
        "nocite_commands": nocite,
        "errors": errors,
        "warnings": warnings,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--minimum", type=int, default=55)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.root.resolve(), args.minimum)
    text = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
