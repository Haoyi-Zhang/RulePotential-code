"""Explicit positive Horn adaptation of the retained Casbin example records.

Not a Casbin implementation or security enforcement conformance test.
Generated interval edits are not measurements of real policy administration.
"""
from pathlib import Path
from itertools import product
from copy import deepcopy
import csv

FIXTURES=('rbac_policy.csv','rbac_with_domains_policy.csv','rbac_with_resource_roles_policy.csv')


def make_policy(name,horizon=8):
    if name not in FIXTURES:raise ValueError('unknown fixture')
    path=Path(__file__).resolve().parents[1]/'inputs'/'casbin'/name
    rows=[]
    with path.open(newline='') as f:
        for row in csv.reader(f,skipinitialspace=True):
            if row: rows.append(row)
    domains='with_domains' in name
    subjects=set();objects=set();actions=set();tenants=set();facts=[]
    def fact(p,args):facts.append({'pred':p,'args':args,'start':0,'stop':horizon})
    for row in rows:
        if row[0]=='p':
            if domains:
                _,sub,tenant,obj,action=row
            else:
                _,sub,obj,action=row;tenant='scope'
            subjects.add(sub);objects.add(obj);actions.add(action);tenants.add(tenant)
            fact('grant',[sub,tenant,obj,action])
        elif row[0]=='g':
            if domains:_,sub,role,tenant=row
            else:_,sub,role=row;tenant='scope'
            subjects|={sub,role};tenants.add(tenant);fact('member',[sub,role,tenant])
        elif row[0]=='g2':
            _,obj,group=row;objects|={obj,group};fact('resource',[obj,group])
        else: raise ValueError('unsupported upstream record')
    types={'subject':sorted(subjects),'tenant':sorted(tenants),'object':sorted(objects),'action':sorted(actions)}
    signatures={'grant':['subject','tenant','object','action'],
                'member':['subject','subject','tenant'],'resource':['object','object'],
                'rolepath':['subject','subject','tenant'],
                'allow':['subject','tenant','object','action'],
                'stable':['subject','tenant','object','action']}
    guards={};rules=[]
    def a(pred,terms,shift=0):return {'pred':pred,'terms':terms.split(),'shift':shift}
    var_types={'?s':'subject','?r':'subject','?z':'subject','?d':'tenant',
               '?o':'object','?g':'object','?a':'action'}
    def rule(head,body):
        variables=sorted({x for atom in [head]+body for x in atom['terms'] if x.startswith('?')})
        ts=[var_types[x] for x in variables];gid='guard'+str(len(rules))
        guards[gid]={'types':ts,'rows':[list(row) for row in product(*(types[t] for t in ts))]}
        rules.append({'guard':gid,'vars':variables,'head':head,'body':body,'start':0,'stop':horizon})
    rule(a('rolepath','?s ?r ?d'),[a('member','?s ?r ?d')])
    rule(a('rolepath','?s ?r ?d'),[a('rolepath','?s ?z ?d'),a('member','?z ?r ?d')])
    rule(a('allow','?s ?d ?o ?a'),[a('grant','?s ?d ?o ?a')])
    rule(a('allow','?s ?d ?o ?a'),[a('rolepath','?s ?r ?d'),a('grant','?r ?d ?o ?a')])
    rule(a('allow','?s ?d ?o ?a'),[a('resource','?o ?g'),a('allow','?s ?d ?g ?a')])
    rule(a('stable','?s ?d ?o ?a'),[a('allow','?s ?d ?o ?a'),a('allow','?s ?d ?o ?a',-1)])
    return {'horizon':horizon,'types':types,'predicates':signatures,'guards':guards,'rules':rules,'facts':facts}


def snapshots(spec):
    """Twelve fixed pre-outcome edits. Always derive set deltas after union."""
    current=deepcopy(spec);H=spec['horizon'];baseline=deepcopy(spec['facts'])
    result=[('initial',deepcopy(current))]
    # Shrink one interval at both boundaries, then restore it.
    current['facts'][0]['start']=1;result.append(('start-shift',deepcopy(current)))
    current['facts']=deepcopy(baseline);result.append(('restore-start',deepcopy(current)))
    current['facts'][0]['stop']=H//2;result.append(('end-shrink',deepcopy(current)))
    current['facts']=deepcopy(baseline);result.append(('restore-end',deepcopy(current)))
    # Duplicate coverage changes record structure without changing any point fact.
    current['facts'].append(deepcopy(baseline[0]));current['facts'][-1]['start']=H//3
    result.append(('overlap-add',deepcopy(current)))
    current['facts'][0]['stop']=H//2;result.append(('overlap-shrink',deepcopy(current)))
    current['facts']=deepcopy(baseline);result.append(('overlap-normalize',deepcopy(current)))
    membership=next(i for i,f in enumerate(baseline) if f['pred']=='member')
    current['facts'][membership]['stop']=current['facts'][membership]['start']
    result.append(('membership-remove',deepcopy(current)))
    current['facts']=deepcopy(baseline);result.append(('membership-restore',deepcopy(current)))
    # Simultaneously lose an initial slice and gain a later slice of a grant.
    current['facts'][0]['stop']=H//2
    current['facts'][1]['start']=H//2
    result.append(('mixed-shrink',deepcopy(current)))
    current['facts'][0]['start']=H//2;current['facts'][0]['stop']=H
    current['facts'][1]['start']=0;current['facts'][1]['stop']=H//2
    result.append(('mixed-move',deepcopy(current)))
    current['facts']=deepcopy(baseline);result.append(('restore-all',deepcopy(current)))
    return result
