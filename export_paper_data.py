#!/usr/bin/env python3
"""Export the exact table/plot inputs from an aggregated, offline campaign.

This script needs no manuscript directory. --check compares exact output bytes
against an existing export, without replacing files or creating a hash manifest.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def exports(results: Path) -> dict[str, bytes]:
    summary = json.loads((results / 'summary.json').read_text())
    if summary['completed_jobs'] != 49 or summary['failed_commands'] or summary['timeouts']:
        raise ValueError('a successful complete 49-job campaign is required')
    with (results / 'timing-summary.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    with (results / 'policy-summary.csv').open(newline='') as f:
        policies = list(csv.DictReader(f))
    if len(rows) != 24 or len(policies) != 18:
        raise ValueError('unexpected campaign coverage')
    files = {'timing-data.csv': (results / 'timing-summary.csv').read_bytes()}
    pairs = [('exchange','block'), ('exchange','scalar'), ('star','block'), ('fanin','scalar')]
    names = dict(zip(pairs, ['Exchange, blocks','Exchange, scalar','Star','Fan-in']))
    out = [r'\begin{tabular}{lrrrrr}', r'\toprule',
           r"Family & Bytes & $Q'$ & $F$ & $O$ & $K$\\", r'\midrule']
    for row in rows:
        if row['size'] != '16384':
            continue
        values = [row[c] for c in ('packet_bytes','local_witness_heads','local_closure_rules',
                                   'local_offset_fields','local_pair_checks')]
        out.append(names[(row['family'],row['partition'])] + ' & ' +
                   ' & '.join(f'{int(v):,}' for v in values) + r'\\')
    out += [r'\bottomrule', r'\end{tabular}']
    files['work-table.tex'] = ('\n'.join(out)+'\n').encode()
    for family, part in pairs:
        values = [r for r in rows if (r['family'],r['partition']) == (family,part)]
        if [int(r['size']) for r in values] != [16,64,256,1024,4096,16384]:
            raise ValueError('unexpected size order')
        out = ['n local_us full_us']
        for r in values:
            local = float(r['local_check_wall_seconds_median'])*1e6
            full = float(r['full_check_wall_seconds_median'])*1e6
            if not local > 0 or not full > 0:
                raise ValueError('nonpositive elapsed observation')
            out.append(f"{r['size']} {local:.9f} {full:.9f}")
        files[f'{family}-{part}.dat'] = ('\n'.join(out)+'\n').encode()
    out = [r'\begin{tabular}{lrrrrr}', r'\toprule',
           r'Fixture & Truth & Witness & Closure & Pairs: scalar & Pairs: time\\', r'\midrule']
    for fixture, label in [('rbac_policy.csv','Ordinary'),('rbac_with_domains_policy.csv','Domains'),
                           ('rbac_with_resource_roles_policy.csv','Resource roles')]:
        vals = {r['partition']:r for r in policies if r['fixture']==fixture and r['horizon']=='32'}
        if set(vals) != {'singleton','temporal'}:
            raise ValueError('missing policy partition')
        a, b = vals['singleton'], vals['temporal']
        for field in ('truth_fields_total','witness_heads_total','closure_rules_total','packet_bytes_total'):
            if a[field] != b[field]:
                raise ValueError('unexpected partition mismatch: '+field)
        numbers = [a[k] for k in ('truth_fields_total','witness_heads_total','closure_rules_total',
                                 'pair_checks_total')] + [b['pair_checks_total']]
        out.append(label+' & '+' & '.join(f'{int(v):,}' for v in numbers)+r'\\')
    out += [r'\bottomrule',r'\end{tabular}']
    files['policy-table.tex'] = ('\n'.join(out)+'\n').encode()
    return files

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT/'results/campaign')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        data = exports(args.results)
        if args.check:
            for name, content in data.items():
                if (args.out/name).read_bytes() != content:
                    raise ValueError('export differs: '+name)
            print(f'All {len(data)} data exports agree exactly.')
        else:
            args.out.mkdir(parents=True, exist_ok=True)
            for name, content in data.items():
                (args.out/name).write_bytes(content)
            print(f'Exported {len(data)} data files.')
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, str(exc)+'\n')

if __name__ == '__main__':
    main()
