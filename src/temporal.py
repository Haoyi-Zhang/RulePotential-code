"""Producer-side finite guarded temporal Horn grounding and interval I/O.

Time is the bounded integer set 0..H-1. Rule head ranges are half open;
body shifts are integer points relative to the head time. A static relational
guard contains every object variable. There is no negation or infinite time.
This module is not imported by the checker-side semantic implementation.
"""
from itertools import product
from math import prod


def checked_spec(s):
    if type(s) is not dict or set(s) != {'horizon','types','predicates','guards','rules','facts'}:
        raise ValueError('invalid temporal document fields')
    h=s['horizon']
    if type(h) is not int or not 1 <= h <= 200000:
        raise ValueError('invalid horizon')
    types=s['types']; preds=s['predicates']
    if type(types) is not dict or type(preds) is not dict or not preds:
        raise ValueError('missing type or predicate dictionary')
    for name,domain in types.items():
        if type(name) is not str or not name or type(domain) is not list or not domain:
            raise ValueError('invalid type')
        if any(type(x) is not str or not x or x.startswith('?') for x in domain):
            raise ValueError('invalid constant')
        if len(set(domain)) != len(domain): raise ValueError('duplicate constant')
    for name,ts in preds.items():
        if type(name) is not str or not name or type(ts) is not list or len(ts)>6:
            raise ValueError('invalid predicate')
        if any(t not in types for t in ts): raise ValueError('unknown type')
    size=h*sum(prod(len(types[t]) for t in ts) for ts in preds.values())
    if not 1<=size<=200000: raise ValueError('ground universe exceeds 200000')
    if type(s['guards']) is not dict: raise ValueError('invalid guards')
    for name,g in s['guards'].items():
        if type(name) is not str or type(g) is not dict or set(g)!={'types','rows'}:
            raise ValueError('invalid guard')
        if type(g['types']) is not list or any(t not in types for t in g['types']):
            raise ValueError('guard type mismatch')
        if type(g['rows']) is not list: raise ValueError('invalid guard rows')
        rows=[]
        for row in g['rows']:
            if type(row) is not list or len(row)!=len(g['types']): raise ValueError('guard arity')
            if any(type(x) is not str or x not in types[t] for x,t in zip(row,g['types'])):
                raise ValueError('guard constant outside domain')
            rows.append(tuple(row))
        if len(set(rows))!=len(rows): raise ValueError('duplicate guard tuple')
    if type(s['rules']) is not list or type(s['facts']) is not list:
        raise ValueError('rules and facts must be lists')
    estimate=0
    substitution_estimate=0
    for rule in s['rules']:
        if type(rule) is not dict or set(rule)!={'guard','vars','head','body','start','stop'}:
            raise ValueError('invalid rule schema')
        g=s['guards'].get(rule['guard'])
        if g is None or type(rule['vars']) is not list or len(rule['vars'])!=len(g['types']):
            raise ValueError('invalid rule guard')
        if any(type(v) is not str or not v.startswith('?') or len(v)<2 for v in rule['vars']):
            raise ValueError('invalid variable name')
        if len(set(rule['vars']))!=len(rule['vars']): raise ValueError('duplicate variable')
        vt=dict(zip(rule['vars'],g['types']))
        if any(type(rule[z]) is not int for z in ['start','stop']) or not 0<=rule['start']<=rule['stop']<=h:
            raise ValueError('invalid head-time range')
        if type(rule['body']) is not list or len(rule['body'])>16: raise ValueError('invalid body width')
        for atom in [rule['head']]+rule['body']:
            if type(atom) is not dict or set(atom)!={'pred','terms','shift'}: raise ValueError('invalid atom')
            ts=preds.get(atom['pred'])
            if ts is None or type(atom['terms']) is not list or len(atom['terms'])!=len(ts):
                raise ValueError('atom arity')
            if type(atom['shift']) is not int or not -h<=atom['shift']<=h: raise ValueError('invalid time shift')
            for term,t in zip(atom['terms'],ts):
                if type(term) is not str: raise ValueError('non-string term')
                if term.startswith('?'):
                    if vt.get(term)!=t: raise ValueError('unguarded or mistyped variable')
                elif term not in types[t]: raise ValueError('mistyped constant')
        if rule['head']['shift']!=0: raise ValueError('head shift must be zero')
        estimate+=len(g['rows'])*(rule['stop']-rule['start'])
        substitution_estimate+=prod(len(types[t]) for t in g['types'])*(rule['stop']-rule['start'])
        if substitution_estimate>1000000: raise ValueError('independent substitution budget exceeds 1000000')
    if estimate>1000000: raise ValueError('ground rule candidate budget exceeds 1000000')
    for f in s['facts']:
        if type(f) is not dict or set(f)!={'pred','args','start','stop'}: raise ValueError('invalid fact schema')
        ts=preds.get(f['pred'])
        if ts is None or type(f['args']) is not list or len(f['args'])!=len(ts): raise ValueError('fact arity')
        if any(type(x) is not str or x not in types[t] for x,t in zip(f['args'],ts)):
            raise ValueError('fact constant outside domain')
        if any(type(f[z]) is not int for z in ['start','stop']) or not 0<=f['start']<=f['stop']<=h:
            raise ValueError('invalid fact interval')
    return size,estimate


def ground(s, grouping='temporal'):
    """Guard-driven join implementation, canonical rule and atom numbering."""
    checked_spec(s)
    if grouping not in {'temporal','singleton'}: raise ValueError('invalid partition')
    atoms=[];blocks=[];local=[];block=0
    for pred,ts in sorted(s['predicates'].items()):
        for args in product(*(sorted(s['types'][t]) for t in ts)):
            for t in range(s['horizon']):
                atoms.append((pred,tuple(args),t)); blocks.append(block); local.append(t)
            block+=1
    ids={atom:i for i,atom in enumerate(atoms)}
    rules=set()
    for row in s['rules']:
        for values in s['guards'][row['guard']]['rows']:
            env=dict(zip(row['vars'],values))
            for t in range(row['start'],row['stop']):
                resolved=[]
                for a in [row['head']]+row['body']:
                    tick=t+a['shift']
                    if not 0<=tick<s['horizon']: break
                    args=tuple(env.get(x,x) for x in a['terms'])
                    resolved.append(ids[(a['pred'],args,tick)])
                else:
                    rules.add((resolved[0],tuple(sorted(set(resolved[1:])))))
    base=set()
    for f in s['facts']:
        for t in range(f['start'],f['stop']):
            base.add(ids[(f['pred'],tuple(f['args']),t)])
    if grouping=='singleton': blocks=list(range(len(atoms))); local=[0]*len(atoms)
    raw={'n':len(atoms),'rules':[{'head':h,'body':list(b)} for h,b in sorted(rules)],
         'blocks':blocks,'local':local}
    return raw,base,atoms


def coalesce(atoms,model):
    """Unique disjoint maximal half-open runs, not a compressed evaluator."""
    times={}
    for i in model:
        p,a,t=atoms[i];times.setdefault((p,a),set()).add(t)
    rows=[]
    for (p,a),ts in sorted(times.items()):
        start=last=None
        for t in sorted(ts):
            if last is None: start=t
            elif t!=last+1:
                rows.append({'pred':p,'args':list(a),'start':start,'stop':last+1});start=t
            last=t
        if last is not None: rows.append({'pred':p,'args':list(a),'start':start,'stop':last+1})
    return rows


def exchange_spec(n):
    """Two mutually rescuing temporal chains; local clock labels are fixed."""
    H=n+1
    def atom(x,shift=0): return {'pred':'hold','terms':[x],'shift':shift}
    return {'horizon':H,'types':{'chain':['a','b']},'predicates':{'hold':['chain']},
        'guards':{'chains':{'types':['chain'],'rows':[['a'],['b']]},
                  'unit':{'types':[],'rows':[[]]}},
        'rules':[{'guard':'chains','vars':['?x'],'head':atom('?x'),
                  'body':[atom('?x',-1)],'start':1,'stop':H},
                 {'guard':'unit','vars':[],'head':atom('a'),'body':[atom('b',n-1)],'start':1,'stop':2},
                 {'guard':'unit','vars':[],'head':atom('b'),'body':[atom('a',n-1)],'start':1,'stop':2}],
        'facts':[{'pred':'hold','args':[x],'start':0,'stop':1} for x in ['a','b']]}
