#!/usr/bin/env python3
"""Regenerate the minimum-offset-repair table and all-setting summary offline."""
from __future__ import annotations
import argparse, csv, io, json, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def exports(source: Path) -> dict[str,bytes]:
    data=json.loads(source.read_text()); oracle=data['oracle']; rows=data['workload_rows']
    if oracle['graph_target_pairs']!=110592 or oracle['oracle_mismatches'] or oracle['certificate_failures']:
        raise ValueError('complete successful offset oracle required')
    if len(rows)!=126 or not all(r['accepted'] for r in rows):
        raise ValueError('126 accepted timing rows required')
    families=('fanout','tree','ordered'); sizes=(3,7,15,31,63,127)
    summary=[]
    deterministic=('monotone_offset_fields','optimal_offset_fields','monotone_packet_bytes',
                   'optimal_packet_bytes','optimality_certificate_bytes','truth_edits','witness_edits')
    timings=('monotone_synthesis_seconds','optimal_synthesis_seconds','optimality_check_seconds','local_check_seconds')
    for family in families:
        for k in sizes:
            values=[r for r in rows if r['family']==family and r['blocks']==k]
            if len(values)!=7 or sorted(r['repetition'] for r in values)!=list(range(7)):
                raise ValueError('incorrect repetitions')
            out={'family':family,'blocks':k}
            for key in deterministic:
                if len({r[key] for r in values})!=1: raise ValueError('nonconstant deterministic field')
                out[key]=values[0][key]
            for key in timings:
                sample=[r[key] for r in values]
                out[key+'_median']=statistics.median(sample)
                out[key+'_min']=min(sample);out[key+'_max']=max(sample)
            summary.append(out)
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    tex=[r'\begin{tabular}{lrrrrr}',r'\toprule',
         r'Family & Fields: raise & Fields: exact & Packet & Proof & Solve (ms)\\',r'\midrule']
    labels={'fanout':'Fan-out','tree':'Binary tree','ordered':'Ordered chain'}
    for r in summary:
        if r['blocks']!=127:continue
        tex.append(labels[r['family']]+' & '+' & '.join([
            str(r['monotone_offset_fields']),str(r['optimal_offset_fields']),
            f"{r['optimal_packet_bytes']:,}",f"{r['optimality_certificate_bytes']:,}",
            f"{1000*r['optimal_synthesis_seconds_median']:.2f}"])+r'\\')
    tex.extend([r'\bottomrule',r'\end{tabular}'])
    return {'repair-table.tex':('\n'.join(tex)+'\n').encode(),'repair-data.csv':buf.getvalue().encode()}

def main()->None:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'results/offset-repair.json');p.add_argument('--out',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args()
    try:
        data=exports(a.source)
        if a.check:
            for name,content in data.items():
                if (a.out/name).read_bytes()!=content:raise ValueError('export differs: '+name)
            print('Both offset-repair exports agree exactly.')
        else:
            a.out.mkdir(parents=True,exist_ok=True)
            for name,content in data.items():(a.out/name).write_bytes(content)
            print('Exported offset-repair table and summary.')
    except (OSError,ValueError,KeyError) as e:p.exit(1,str(e)+'\n')
if __name__=='__main__':main()
