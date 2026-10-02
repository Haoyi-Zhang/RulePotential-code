"""Check a local obstruction to ranking a specified selected proof.

This establishes failure of this proof/partition representation only, never
non-entailment or failure of every possible proof. No synthesis code imported.
"""
def check_obstruction(raw,model,witness,evidence):
    try:
        if type(evidence)!=dict: return False
        def edge(row):
            if type(row)!=list or len(row)!=3 or any(type(x)!=int for x in row):
                raise ValueError('invalid edge')
            r,b,h=row
            if not 0<=r<len(raw['rules']) or h not in model or b not in model:
                raise ValueError('edge domain')
            rule=raw['rules'][r]
            if witness.get(h)!=r or rule['head']!=h or b not in rule['body']:
                raise ValueError('not a selected proof edge')
            return raw['blocks'][b],raw['blocks'][h],raw['local'][b]-raw['local'][h]+1
        if evidence.get('kind')=='internal_order':
            u,v,w=edge([evidence['rule'],evidence['premise'],evidence['head']])
            return u==v and w>0
        if evidence.get('kind')!='positive_cycle': return False
        cycle=evidence['cycle']
        if type(cycle)!=list or not 1<=len(cycle)<=len(raw['blocks']): return False
        arcs={};weight=0
        for e in cycle:
            if type(e)!=dict or set(e)!={'left','right','weight','edge'}: return False
            if any(type(e[x])!=int for x in ['left','right','weight']): return False
            u,v,w=edge(e['edge'])
            if (u,v,w)!=(e['left'],e['right'],e['weight']) or u==v or u in arcs: return False
            arcs[u]=v;weight+=w
        start=next(iter(arcs));node=start;seen=set()
        while node not in seen:
            seen.add(node)
            if node not in arcs:return False
            node=arcs[node]
        return node==start and len(seen)==len(arcs) and weight>0 and evidence.get('weight_sum')==weight
    except (ValueError,TypeError,KeyError,IndexError):
        return False
