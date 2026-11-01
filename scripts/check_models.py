#!/usr/bin/env python3
"""Independent tiny integer-width enumeration vs every CP/LCG/MIP encoding."""
import itertools
import json
from pathlib import Path
import random
import tempfile
from compare_solvers import METHODS, run_once, verify


def oracle(data):
    best = None
    for widths in itertools.product(*(range(a,b+1) for a,b in zip(data['lo'],data['hi']))):
        if sum(widths) > data['budget']: continue
        heights = [0]*data['m']
        for d in range(data['cells']):
            steps = [k for k in range(data['first'][d]-1,data['last'][d]) if data['sw'][k] <= widths[data['cell_col'][d]-1]]
            if not steps: break
            r = data['cell_row'][d]-1
            heights[r] = max(heights[r],data['sh'][steps[-1]])
        else:
            value = sum(heights)
            best = value if best is None else min(best,value)
    return best


def generate(rng):
    n,m = rng.randint(1,3),rng.randint(1,3)
    data = dict(n=n,m=m,lo=[1]*n,hi=[rng.randint(2,5) for _ in range(n)],
                first=[],last=[],cell_row=[],cell_col=[],sw=[],sh=[],row_upper=[0]*m,cells=n*m)
    for j in range(n):
        for i in range(m):
            data['first'].append(len(data['sw'])+1)
            h = rng.randint(0,12)
            for w in range(1,data['hi'][j]+1):
                h = max(0,h-rng.randint(0,3))
                data['sw'].append(w);data['sh'].append(h)
                data['row_upper'][i] = max(data['row_upper'][i],h)
            data['last'].append(len(data['sw']))
            data['cell_row'].append(i+1);data['cell_col'].append(j+1)
    data['steps'] = len(data['sw'])
    data['budget'] = rng.randint(n,sum(data['hi']))
    return data


def main():
    rng = random.Random(20112015)
    mini = Path('.tools/minizinc-path.txt').read_text().strip()
    instances = [generate(rng) for _ in range(12)]
    instances.append(json.loads(Path('tests/fixtures/minizinc-unary-regression.json').read_text()))
    impossible = generate(rng);impossible['budget']=0;instances.append(impossible)
    # RCSV must retain an API lower bound between actual curve breakpoints.
    # Both a budget cutoff and a lower bound beyond a dropped height are tested.
    for lower,budget in [(2,3),(5,5)]:
        instances.append(dict(n=1,m=1,lo=[lower],hi=[6],budget=budget,cells=1,
            steps=3,first=[1],last=[3],cell_row=[1],cell_col=[1],
            sw=[1,4,6],sh=[5,2,0],row_upper=[5]))
    with tempfile.TemporaryDirectory() as root:
        path = Path(root)/'instance.json'
        for i,data in enumerate(instances):
            expected = oracle(data);path.write_text(json.dumps(data))
            for method in METHODS:
                result = run_once(mini,method,path,2000)
                if expected is None: assert result['status']=='UNSATISFIABLE',(i,method,result)
                else:
                    assert result['status']=='OPTIMAL_SOLUTION',(i,method,result)
                    assert verify(data,result['solution'],True)==expected,(i,method,result)
    print(f'{len(instances)*len(METHODS)} model/oracle checks passed')


if __name__ == '__main__': main()
