#!/usr/bin/env python3
"""Validate a complete campaign and emit claim-linked, non-cherry-picked tables.

All files come from the given directory. Published results are never overwritten
unless that directory is explicitly selected. Runtime values are excluded from
--compare; all semantic and operation-count results must match exactly.
"""
from __future__ import annotations
import argparse, csv, json, statistics
from collections import defaultdict
from pathlib import Path
from reproduce import jobs


def require(condition, detail='summary invariant failed'):
    if not condition:
        raise ValueError(detail)


def load(directory: Path) -> dict:
    records=json.loads((directory/'execution.json').read_text())
    data={}
    for key,_ in jobs(False):
        valid=[r for r in records if r['case']==key and r['returncode']==0 and not r['timeout']]
        if not valid: raise ValueError(f'missing successful command: {key}')
        data[key]=json.loads((directory/(key+'.json')).read_text())
    if len(data)!=49: raise ValueError('unexpected campaign definition')
    return data


def stable(value):
    if isinstance(value,dict):
        return {k:stable(v) for k,v in value.items() if k!='run' and not k.endswith('_seconds')}
    if isinstance(value,list): return [stable(v) for v in value]
    return value


def csv_write(path: Path, rows: list[dict]) -> None:
    if not rows: raise ValueError('empty result table')
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def summarize(directory: Path) -> dict:
    data=load(directory)
    environment=json.loads((directory/'environment.json').read_text())
    if not isinstance(environment,dict) or 'recording_status' not in environment:
        raise ValueError('missing or invalid timing environment record')
    units=data['units']; require(units['tests']==23 and units['failures']==units['errors']==units['skipped']==0,'unit summary mismatch')
    summary={'completed_jobs':len(data),'units':{k:v for k,v in units.items() if k!='run'},
             'timing_environment':{'file':'environment.json',**environment}}
    groups=[('correct', ['transitions','oracle_mismatches','rollback_mismatches','deletions','insertions','mixed','no_base_change']),
            ('candidate',['candidate_packets','accepted_packets','wrong_models_accepted','old_new_pairs_with_certificate','rollback_mismatches']),
            ('representation',['cases','feasible','internal_order','positive_cycle','checked_obstructions','oracle_mismatches'])]
    for group,keys in groups:
        summary[group]={k:sum(d[k] for name,d in data.items() if name.startswith(group+'-')) for k in keys}
    summary['selection']={k:v for k,v in data['selection'].items() if k!='run'}
    require(summary['correct']['transitions']==32768,'transition count mismatch')
    require(summary['candidate']['old_new_pairs_with_certificate']==1024,'candidate pair count mismatch')
    require(summary['representation']['cases']==8640,'representation count mismatch')
    for group in ['correct','candidate','representation','selection']:
        for k,v in summary[group].items():
            if 'mismatch' in k or k=='wrong_models_accepted': require(v==0,(group,k,v))
    timing=[r for name,d in data.items() if name.startswith(('exchange-','star-','fanin-')) for r in d['rows']]
    policies=[r for name,d in data.items() if name.startswith('policy-') for r in d['rows']]
    require(len(timing)==168 and all(r['accepted'] for r in timing),'timing rows incomplete or rejected')
    require(len(policies)==216 and all(r['status']=='accepted' for r in policies),'policy rows incomplete or rejected')
    require(all(d['oracle_mismatches']==0 for name,d in data.items() if name.startswith('policy-')),'policy oracle mismatch')
    numeric_times=[v for r in timing for k,v in r.items() if k.endswith('_wall_seconds')]
    if not all(v>0 for v in numeric_times): raise ValueError('nonpositive elapsed kernel timing; inspect clock')
    summary['timing_rows']=len(timing)
    summary['policy_updates']=len(policies)
    summary['policy_status_counts']={s:sum(r['status']==s for r in policies) for s in sorted({r['status'] for r in policies})}
    summary['max_atoms']=max(r['atoms'] for r in timing+policies)
    summary['max_rules']=max(r['rules'] for r in timing+policies)
    summary['peak_rss_kib']=max(d['run']['peak_rss_kib'] for d in data.values())
    summary['kernel_cpu_seconds']=sum(d['run']['cpu_seconds'] for d in data.values())
    records=json.loads((directory/'execution.json').read_text())
    if not all(r.get('environment_file')=='environment.json' and
               r.get('environment_recording_status')==environment['recording_status'] for r in records):
        raise ValueError('execution record is not linked to the directory timing environment')
    summary['child_cpu_seconds_including_startup']=sum(r['cpu_seconds'] for r in records)
    summary['timeouts']=sum(r['timeout'] for r in records)
    summary['failed_commands']=sum(r['returncode']!=0 for r in records)
    require(summary['timeouts']==summary['failed_commands']==0,'campaign timeout or command failure')
    grouped=defaultdict(list)
    for r in timing:grouped[(r['family'],r['size'],r['partition'])].append(r)
    aggregates=[]
    for (family,n,partition),rows in sorted(grouped.items()):
        require(len(rows)==7,('timing repetition count',family,n,partition,len(rows)))
        row={'family':family,'size':n,'partition':partition,'repetitions':len(rows)}
        for k in rows[0]:
            if k.endswith('_wall_seconds'):
                values=[r[k] for r in rows]
                row[k+'_min']=min(values);row[k+'_median']=statistics.median(values);row[k+'_max']=max(values)
            elif k.startswith(('local_','dred_','full_','verify_')) or k in ['atoms','rules','premise_incidences','packet_bytes']:
                values={r[k] for r in rows}
                if len(values)!=1:raise ValueError(f'nonconstant operation count: {k}')
                row[k]=rows[0][k]
        aggregates.append(row)
    csv_write(directory/'timing-raw.csv',timing)
    csv_write(directory/'timing-summary.csv',aggregates)
    csv_write(directory/'policy-raw.csv',policies)
    policy_summary=[]
    for fixture in sorted({r['fixture'] for r in policies}):
        for h in [8,16,32]:
            for partition in ['temporal','singleton']:
                rs=[r for r in policies if r['fixture']==fixture and r['horizon']==h and r['partition']==partition]
                require(len(rs)==12,('policy update count',fixture,h,partition,len(rs)))
                policy_summary.append({'fixture':fixture,'horizon':h,'partition':partition,'updates':len(rs),
                    'atoms':rs[0]['atoms'],'rules':rs[0]['rules'],
                    **{f'{k}_total':sum(r[k] for r in rs) for k in ['packet_bytes','truth_fields','witness_heads','closure_rules','offset_fields','pair_checks']},
                    'local_check_wall_seconds_median':statistics.median(r['local_check_wall_seconds'] for r in rs)})
    csv_write(directory/'policy-summary.csv',policy_summary)
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    parser.add_argument('--compare',type=Path,help='compare every deterministic result with a second complete campaign')
    args=parser.parse_args();summary=summarize(args.directory)
    if args.compare:
        a,b=load(args.directory),load(args.compare)
        differences=[key for key in a if stable(a[key])!=stable(b[key])]
        if differences:raise SystemExit('deterministic mismatch: '+', '.join(differences))
        summary['compared_deterministic_jobs']=len(a)
        (args.directory/'comparison.json').write_text(json.dumps({'jobs':len(a),'mismatches':[],
          'excluded_fields':'per-kernel runtime seconds, per-run resource accounting, and runtime-environment metadata only'},indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
