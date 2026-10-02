"""Second temporal expander plus a tuple fixed-point evaluator.

``elaborate`` independently enumerates typed substitutions, tests guard
membership, interval bounds, and shifts, and imports neither the producer nor
``src.temporal``.  ``direct_model`` intentionally reuses the clauses and base
returned by ``elaborate``; only its fixed-point evaluation is independent of the
producer counter and DRed algorithms.  It is therefore not a third grounding
front end, and it shares any expansion defect in guard, shift, or interval
handling with ``elaborate``.
"""
import itertools


def elaborate(spec, partition='temporal'):
    if not isinstance(spec,dict) or set(spec)!={'horizon','types','predicates','guards','rules','facts'}:
        raise ValueError('invalid source document')
    H=spec['horizon']
    if type(H)!=int or H<1 or H>200000: raise ValueError('horizon outside contract')
    domains=spec['types']; signatures=spec['predicates']
    if type(domains)!=dict or type(signatures)!=dict or not signatures: raise ValueError('missing signatures')
    for key,values in domains.items():
        if type(key)!=str or not key or type(values)!=list or not values: raise ValueError('type declaration')
        seen=set()
        for v in values:
            if type(v)!=str or not v or v[0]=='?' or v in seen: raise ValueError('constant declaration')
            seen.add(v)
    count=0
    for p,signature in signatures.items():
        if type(p)!=str or not p or type(signature)!=list or len(signature)>6: raise ValueError('predicate declaration')
        ways=H
        for tp in signature:
            if tp not in domains: raise ValueError('undefined type')
            ways*=len(domains[tp])
        count+=ways
    if count<1 or count>200000: raise ValueError('universe size budget')
    if partition not in ('temporal','singleton'): raise ValueError('partition name')
    guards=spec['guards']
    if type(guards)!=dict: raise ValueError('guard table')
    guard_sets={}
    for name,g in guards.items():
        if type(name)!=str or type(g)!=dict or set(g)!={'types','rows'}: raise ValueError('guard schema')
        if type(g['types'])!=list or type(g['rows'])!=list: raise ValueError('guard fields')
        if any(tp not in domains for tp in g['types']): raise ValueError('guard types')
        acc=set()
        for row in g['rows']:
            if type(row)!=list or len(row)!=len(g['types']): raise ValueError('guard arity')
            for value,tp in zip(row,g['types']):
                if type(value)!=str or value not in domains[tp]: raise ValueError('guard value')
            tup=tuple(row)
            if tup in acc: raise ValueError('repeated guard row')
            acc.add(tup)
        guard_sets[name]=acc
    clauses=[];estimate=0;substitution_estimate=0
    if type(spec['rules'])!=list or type(spec['facts'])!=list: raise ValueError('invalid rules or facts')
    for r in spec['rules']:
        if type(r)!=dict or set(r)!={'guard','vars','head','body','start','stop'}: raise ValueError('clause schema')
        if r['guard'] not in guards or type(r['vars'])!=list: raise ValueError('clause guard')
        ts=guards[r['guard']]['types']
        if len(ts)!=len(r['vars']) or len(set(r['vars']))!=len(r['vars']): raise ValueError('variable arity')
        if any(type(x)!=str or not x.startswith('?') or len(x)<2 for x in r['vars']): raise ValueError('variable name')
        env_types=dict(zip(r['vars'],ts))
        if type(r['start'])!=int or type(r['stop'])!=int or not 0<=r['start']<=r['stop']<=H:
            raise ValueError('clause time interval')
        if type(r['body'])!=list or len(r['body'])>16: raise ValueError('body budget')
        for atom in [r['head']]+r['body']:
            if type(atom)!=dict or set(atom)!={'pred','terms','shift'}: raise ValueError('literal schema')
            if atom['pred'] not in signatures or type(atom['terms'])!=list: raise ValueError('literal predicate')
            sig=signatures[atom['pred']]
            if len(sig)!=len(atom['terms']): raise ValueError('literal arity')
            if type(atom['shift'])!=int or not -H<=atom['shift']<=H: raise ValueError('literal shift')
            for term,tp in zip(atom['terms'],sig):
                if type(term)!=str: raise ValueError('literal term')
                if term.startswith('?'):
                    if term not in env_types or env_types[term]!=tp: raise ValueError('guard does not type-cover term')
                elif term not in domains[tp]: raise ValueError('constant type mismatch')
        if r['head']['shift']!=0: raise ValueError('nonzero head shift')
        estimate+=len(guard_sets[r['guard']])*(r['stop']-r['start'])
        if estimate>1000000: raise ValueError('rule instance budget')
        combinations=r['stop']-r['start']
        for tp in ts: combinations*=len(domains[tp])
        substitution_estimate+=combinations
        if substitution_estimate>1000000: raise ValueError('independent substitution budget')
        # Deliberately not a guard-driven join: enumerate the declared types.
        for values in itertools.product(*(domains[tp] for tp in ts)):
            if values not in guard_sets[r['guard']]: continue
            subst=dict(zip(r['vars'],values))
            for time in range(r['start'],r['stop']):
                inst=[]
                for atom in [r['head']]+r['body']:
                    when=time+atom['shift']
                    if when<0 or when>=H: break
                    args=tuple(subst[x] if x.startswith('?') else x for x in atom['terms'])
                    inst.append((atom['pred'],args,when))
                if len(inst)==len(r['body'])+1: clauses.append((inst[0],frozenset(inst[1:])))
    universe=[];blocks=[];labels=[];component=0
    for p in sorted(signatures):
        for args in itertools.product(*(sorted(domains[t]) for t in signatures[p])):
            for when in range(H):
                universe.append((p,args,when));blocks.append(component);labels.append(when)
            component+=1
    rows={}
    for f in spec['facts']:
        if type(f)!=dict or set(f)!={'pred','args','start','stop'}: raise ValueError('fact record schema')
        if f['pred'] not in signatures or type(f['args'])!=list or len(f['args'])!=len(signatures[f['pred']]):
            raise ValueError('fact signature')
        for value,tp in zip(f['args'],signatures[f['pred']]):
            if type(value)!=str or value not in domains[tp]: raise ValueError('fact value')
        if type(f['start'])!=int or type(f['stop'])!=int or not 0<=f['start']<=f['stop']<=H:
            raise ValueError('fact interval')
        rows.setdefault((f['pred'],tuple(f['args'])),[]).append((f['start'],f['stop']))
    base={a for a in universe if any(lo<=a[2]<hi for lo,hi in rows.get(a[:2],[]))}
    number={a:i for i,a in enumerate(universe)}
    canonical=sorted({(number[h],tuple(sorted(number[x] for x in b))) for h,b in clauses})
    if partition=='singleton':blocks=list(range(count));labels=[0]*count
    raw={'n':count,'rules':[{'head':h,'body':list(b)} for h,b in canonical],'blocks':blocks,'local':labels}
    return raw,{number[x] for x in base},universe,clauses,base


def direct_model(spec):
    """Saturate tuples produced by :func:`elaborate`.

    The fixed-point loop is independent of the producer counter and DRed
    engines, but grounding is deliberately reused from ``elaborate``.  This is
    not the all-interpretations oracle or a third end-to-end temporal semantics.
    """
    _,_,atoms,clauses,known=elaborate(spec)
    if len(atoms)>20000 or len(clauses)>100000: raise ValueError('semantic oracle budget')
    for _ in range(len(atoms)+1):
        consequence={head for head,body in clauses if body.issubset(known)}
        if consequence.issubset(known): return known
        known=known|consequence
    raise AssertionError('finite closure did not converge')
