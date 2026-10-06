# Bibliography verification

The manuscript bibliography is relevance-first rather than count-padded.  The
current packet contains 63 scholarly entries, all cited in manuscript body text.
`literature_sources.csv` records what each source supports and the actual reading
depth.  `bibliography_verification.csv` separately records title, authors, year,
venue, volume/issue/pages or article number, DOI or stable primary record, and the
record used for the final metadata cross-check.

Run the deterministic consistency audit from `artifact/` in the complete
delivered project. It requires the sibling `../paper/` manuscript; the flat
code-only repository alone cannot perform this optional manuscript audit.
Alternatively, pass `--root /path/to/project` with both directories:

```sh
python verify_bibliography.py --minimum 55 \
  --out results/bibliography-verification.json
```

The audit parses BibTeX without a third-party library and checks all of the
following:

* at least 55 entries and one body citation for every entry;
* no undefined citations, unused entries, or `\\nocite` padding;
* one source-ledger and one verification-ledger row per BibTeX key;
* exact title, authors, year, venue, volume, issue, pages/article number, and DOI
  agreement between BibTeX and the frozen verification ledger;
* DOI syntax and uniqueness, HTTPS record locations, and nonfuture check dates;
* an explicit author-hosted or institutional record for either non-DOI paper;
* exactly 12 same-venue, 5 influential/foundational, and 5 adjacent-venue
  calibration slots, with the documented one-paper overlap giving 21 unique
  papers.

The frozen final ledger has 61 DOI-bearing records and two documented non-DOI
records: the Atserias--Maneva author manuscript and the Microsoft Research CIDR
record for Differential Dataflow.  A passing script establishes internal
consistency with the retained primary-record cross-checks; it is not a live
registry lookup, independent librarian review, or proof that every cited claim is
correct.  Claim support remains limited to the roles and reading depths stated in
`literature_sources.csv`.
