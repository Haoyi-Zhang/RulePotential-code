"""Polynomial encodings for compatible block-proof selection.

A max atom (z,u,v,c) means x[z] <= max(x[u],x[v]) + c.
This module encodes constraints; it is NOT a general Max-Atom solver.
The mathematical reductions allow arbitrary binary-encoded integers.
The runtime checker separately enforces its documented finite bounds.
"""
from itertools import product


def maxatom_to_horn(variable_count, atoms):
    if type(variable_count) is not int or variable_count < 1:
        raise ValueError("positive variable count required")
    blocks=list(range(variable_count)); local=[0]*variable_count
    base=set(range(variable_count)); rules=[]; triples=[]
    for z,u,v,c in atoms:
        if any(type(i) is not int or i < 0 or i >= variable_count for i in (z,u,v)):
            raise ValueError("invalid variable")
        if type(c) is not int:
            raise ValueError("integer offset required")
        h=len(blocks); a=h+1; b=h+2
        lh=max(c+1,0); lp=lh-c-1
        blocks.extend([z,u,v]); local.extend([lh,lp,lp]); base.update([a,b])
        rules.extend([{'head':h,'body':[a]},{'head':h,'body':[b]}])
        triples.append((h,a,b))
    raw={'n':len(blocks),'rules':rules,'blocks':blocks,'local':local}
    return raw,base,set(range(len(blocks))),triples


def horn_to_maxatom(raw,base,model):
    """Return variable count and max atoms. M must be the supplied least model.
    An absent supported head maps to an explicit contradiction; entailment itself
    is checked separately, not decided by these constraints.
    """
    blocks=raw['blocks']; local=raw['local']; k=max(blocks)+1; nxt=k
    out=[]; headrules={h:[] for h in model}
    for r in raw['rules']:
        h=r['head']; body=set(r['body'])
        if h in model and body <= model:
            headrules[h].append(tuple(sorted(body)))
    for h in sorted(model-base):
        choices=headrules[h]
        if any(not bs for bs in choices):
            continue
        if not choices:
            out.append((0,0,0,-1)); continue
        zs=[]
        for bs in choices:
            z=nxt; nxt+=1; zs.append(z)
            for b in bs:
                j=blocks[b]; c=local[h]-local[b]-1
                out.append((z,j,j,c))
        # A one-sided max tree is exact existentially: all internal variables
        # may be chosen equal to the maximum of their children.
        while len(zs)>2:
            a,b=zs.pop(),zs.pop(); t=nxt; nxt+=1
            out.append((t,a,b,0)); zs.append(t)
        if len(zs)==1: zs.append(zs[0])
        out.append((blocks[h],zs[0],zs[1],0))
    return nxt,out


def satisfies(values,atoms):
    return all(values[z] <= max(values[u],values[v])+c for z,u,v,c in atoms)


def selected_witness(raw,base,model,offsets):
    """Direct semantic test at supplied offsets, independent of graph relaxation."""
    ranks=[offsets[b]+l for b,l in zip(raw['blocks'],raw['local'])]
    witness={h:-1 for h in base}
    for h in sorted(model-base):
        for ri,r in enumerate(raw['rules']):
            if r['head']==h and all(b in model and ranks[b]<ranks[h] for b in r['body']):
                witness[h]=ri; break
        else:
            return None
    return witness


def extend_values(raw,base,model,x):
    """Construct the auxiliary max-atom values; used only in finite checks.
    The order mirrors the encoder but no constraint satisfiability is assumed.
    """
    values=list(x); by_head={h:[] for h in model}
    for r in raw['rules']:
        if r['head'] in model and set(r['body']) <= model:
            by_head[r['head']].append(tuple(sorted(set(r['body']))))
    for h in sorted(model-base):
        choices=by_head[h]
        if any(not bs for bs in choices) or not choices: continue
        zs=[]
        for bs in choices:
            zs.append(len(values))
            values.append(min(x[raw['blocks'][b]]+raw['local'][h]-raw['local'][b]-1 for b in bs))
        while len(zs)>2:
            a,b=zs.pop(),zs.pop(); zs.append(len(values)); values.append(max(values[a],values[b]))
    return values
