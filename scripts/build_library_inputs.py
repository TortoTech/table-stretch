#!/usr/bin/env python3
"""Deduplicate numeric geometry, establish references, and check raw-token layout."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from benchmark_native import ROOT, Worker
from benchmark_unified import canonical, sha, verify


def token_heights(rows, widths):
    result = []
    for row in rows:
        tallest = 0
        for c,w in zip(row,widths):
            used, lines = 0, int(bool(c['tokens']))
            for token in c['tokens']:
                assert token <= w
                nxt = token if not used else used+c['gap']+token
                if nxt > w:
                    lines += 1; used = token
                else:
                    used = nxt
            tallest = max(tallest,lines)
        result.append(tallest)
    return result


def main():
    corpus_path = ROOT/'tests/fixtures/ebooks-library.json'
    output = ROOT/'docs/benchmark-library-inputs.json'
    subprocess.run(['cargo','build','--locked','--release','--example','library_inputs','--example','native_worker'],cwd=ROOT,check=True)
    raw = json.loads(subprocess.check_output([str(ROOT/'target/release/examples/library_inputs'),str(corpus_path)]))
    corpus = json.loads(corpus_path.read_text())
    # Preserve every original challenge case, including very tight budgets
    # not represented by the percentage grid. Never dilute them out of coverage.
    source_index={(t['book'],t['document'],t['table_index']):i for i,t in enumerate(corpus['tables'])
                  if t['source_kind']=='whole'}
    legacy=json.loads((ROOT/'docs/benchmark-unified-inputs.json').read_text())
    for old in legacy:
        index=source_index[(old['book'],old['document'],old['table_index'])]
        sample=corpus['tables'][index]
        item={k:old[k] for k in ['width','book','document','table_index','table']}
        item.update(sample_index=index,format=sample['format'],source_kind=sample['source_kind'],
                    book_sha256=sample['book_sha256'],reference_height=None,legacy_challenge=True)
        raw.append(item)
    seen, inputs = {}, []
    for item in raw:
        digest = hashlib.sha256(canonical(item['table'])).hexdigest()
        if digest in seen:
            if item.get('legacy_challenge'):
                seen[digest]['legacy_challenge']=True
            seen[digest]['duplicate_sources'].append({k:item[k] for k in ['sample_index','book','document','table_index']})
            continue
        item.update(input_sha256=digest, duplicate_sources=[])
        seen[digest]=item; inputs.append(item)
    output.write_text(json.dumps(inputs,ensure_ascii=False,separators=(',',':'))+'\n')
    worker = Worker(output,2000)
    audit = []
    try:
        for i,item in enumerate(inputs):
            witnesses=[]; attempts=[]
            for method in ['pareto','astar2011']:
                r=worker.run(i,method); attempts.append(dict(method=method,status=r['status'],wall_ns=r['wall_ns']))
                if r['status']=='optimal':
                    value=r['layout']['total_height']
                    verify(item['table'],r['layout'],value)
                    assert token_heights(corpus['tables'][item['sample_index']]['rows'],r['layout']['column_widths'])==r['layout']['row_heights']
                    witnesses.append((method,value))
            if len(witnesses)<2:
                r=worker.run(i,'lcg2015'); attempts.append(dict(method='lcg2015',status=r['status'],wall_ns=r['wall_ns']))
                if r['status']=='optimal':
                    value=r['layout']['total_height'];verify(item['table'],r['layout'],value)
                    assert token_heights(corpus['tables'][item['sample_index']]['rows'],r['layout']['column_widths'])==r['layout']['row_heights']
                    witnesses.append(('lcg2015',value))
            if witnesses:
                assert len({v for _,v in witnesses})==1, (i,witnesses)
                item['reference_height']=witnesses[0][1]
            item['reference_verified_by']=[m for m,_ in witnesses]
            audit.append(dict(case=i,attempts=attempts))
            if (i+1)%50==0: print(f'{i+1}/{len(inputs)} references',flush=True)
    finally:
        worker.close()
    # Do not drop unresolved instances; the benchmark must expose hard cases.
    output.write_text(json.dumps(inputs,ensure_ascii=False,separators=(',',':'))+'\n')
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),corpus_sha256=sha(corpus_path),input_manifest_sha256=sha(output),
                 raw_cases=len(raw),distinct_cases=len(inputs),tables=len(corpus['tables']),
                 legacy_challenge_cases=sum(i.get('legacy_challenge',False) for i in inputs),
                 books=len({t['book_sha256'] for t in corpus['tables']}),
                 reference_timeout_ms=2000,unknown_references=sum(i['reference_height'] is None for i in inputs),
                 cross_checked=sum(len(i['reference_verified_by'])>=2 for i in inputs),attempts=audit)
    (ROOT/'docs/library-validation.json').write_text(json.dumps(summary,ensure_ascii=False,separators=(',',':'))+'\n')
    print({k:v for k,v in summary.items() if k!='attempts'})


if __name__=='__main__':
    main()
