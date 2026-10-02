"""Full ranked-model verification baseline without rebuilding persistent indexes.

Inputs are resident parsed objects over a previously validated fixed program.
This is a full semantic check, not the incremental checker's initialization cost.
"""
def verify_all(raw,base,model,witness,offset):
    counters={'rules':0,'rule_literals':0,'witnesses':0,'proof_literals':0}
    if set(witness)!=set(model) or not set(base)<=set(model):return False,counters
    for h in model:
        counters['witnesses']+=1
        r=witness[h]
        if r==-1:
            if h not in base:return False,counters
        elif type(r)!=int or not 0<=r<len(raw['rules']):return False,counters
        else:
            rule=raw['rules'][r]
            if rule['head']!=h:return False,counters
            rh=offset[raw['blocks'][h]]+raw['local'][h]
            for b in rule['body']:
                counters['proof_literals']+=1
                if b not in model:return False,counters
                if offset[raw['blocks'][b]]+raw['local'][b]>=rh:return False,counters
    for rule in raw['rules']:
        counters['rules']+=1;active=True
        for b in rule['body']:
            counters['rule_literals']+=1
            if b not in model:active=False;break
        if active and rule['head'] not in model:return False,counters
    return True,counters
