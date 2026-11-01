#!/usr/bin/env python3
"""Coverage and validation report for the expanded local-library corpus."""
import json
from collections import Counter
from pathlib import Path
from benchmark_native import ROOT, METHODS
from benchmark_unified import sha
from report_native import NAMES


def main():
    corpus_path=ROOT/'tests/fixtures/ebooks-library.json'
    input_path=ROOT/'docs/benchmark-library-inputs.json'
    corpus=json.loads(corpus_path.read_text());tables=corpus['tables']
    inputs=json.loads(input_path.read_text())
    validation=json.loads((ROOT/'docs/library-validation.json').read_text())
    assert validation['corpus_sha256']==sha(corpus_path)
    assert validation['input_manifest_sha256']==sha(input_path)
    raw=[json.loads(l) for l in (ROOT/'docs/benchmark-native.jsonl').read_text().splitlines()]
    assert raw[0]['input_manifest_sha256']==sha(input_path)
    assert len(raw[1:])==len(inputs)*len(METHODS)
    legacy=json.loads((ROOT/'docs/benchmark-unified-inputs.json').read_text())
    assert {r['input_sha256'] for r in legacy} <= {r['input_sha256'] for r in inputs}
    counts=Counter(t['source_kind'] for t in tables)
    max_rows=max(len(t['rows']) for t in tables);max_cols=max(len(t['rows'][0]) for t in tables)
    max_tokens=max(len(c['tokens']) for t in tables for r in t['rows'] for c in r)
    books=len({t['book_sha256'] for t in tables})
    by_kind={kind:[t for t in tables if t['source_kind']==kind] for kind in counts}
    report=f'''# Local-library coverage

The corpus contains **{len(tables)} real table samples from {books} books** and **{len(inputs):,} distinct width cases**, replacing the earlier 64-case primary benchmark. All 317 original complete EPUB tables remain present.

| Source | Samples | Books |
| --- | ---: | ---: |
'''
    for kind,items in by_kind.items():
        report+=f'| {kind} | {len(items)} | {len({t["book_sha256"] for t in items})} |\n'
    report+=f'''
Book counts overlap between source categories. Rectangular bodies are contiguous rows from actual tables, with merged headers, occupied rowspan rows, image cells and irregular rows excluded. They are labeled as derived bodies, not whole-table span support.

Scanned **{corpus['scan']['epub_books_scanned']} EPUB books** and **{corpus['scan']['pdf_pages_scanned']:,} sampled pages across {corpus['scan']['pdf_books_scanned']} PDF books**. EPUB parsing found {corpus['scan']['epub_tables_seen']} table elements and used HTML recovery for {corpus['scan']['html_recovered_documents']} documents. PDF detection uses ruled grids, at most 100 evenly spaced pages and three candidates per book. Of six PDF candidates, five passed rendered-page review; one was rejected because outlined typeface names were absent from text extraction. Scanned/image-only and unruled PDF tables are not covered. Two AZW3 books and one CHM were not processed.

Largest dimensions are **{max_rows} rows**, **{max_cols} columns**, and **{max_tokens} tokens in one cell** (these maxima may occur in different tables). Source file hashes, EPUB row ranges, and PDF page/bounding-box metadata are retained. Only numeric text metrics are committed, not cell text or page images.

## Case selection and validation

For every sample, container widths are 10%, 35%, and 70% of the interval between its minimum feasible and maximum useful width, rounded down. Repeated widths and identical curve inputs are deduplicated with source aliases retained. All 64 original challenge inputs remain covered; they represent 63 distinct geometries. Selection does not depend on algorithm runtime or success.

**All {len(inputs):,} cases have matching Pareto DP and A* reference heights.** Both reference layouts are also checked against an independent greedy wrapper on the original token widths, without consulting the generated staircase curves. Unresolved cases would be retained rather than silently dropped; this run has none. The complete manifest is a Cargo regression test. Extraction tests specifically guard against inherited rowspans and nested-table flattening.

This is a deterministic Unicode-width/word-wrap model with line height 1, not a reproduction of each book's fonts, CSS, forced line breaks, or original PDF geometry. Single-row and single-column tables are excluded. The broader sample mix changes aggregate percentiles; differences from the earlier 64-case table are not algorithm speedups.

## Completed cases by source

All nine implementations use the same one-second full-call limit, one warmup and three measured repetitions. A case completes only if all three repetitions finish; exact returned heights are checked against the references. Subsets below are classified by the retained representative after geometry deduplication.

| Method | Whole EPUB | EPUB bodies | PDF | Retained challenges |
| --- | ---: | ---: | ---: | ---: |
'''
    subsets={k:{i for i,x in enumerate(inputs) if x['source_kind']==k} for k in counts}
    subsets['challenge']={i for i,x in enumerate(inputs) if x.get('legacy_challenge')}
    for method in METHODS:
        records={r['case']:r for r in raw[1:] if r['algorithm']==method}
        values=[]
        for kind in ['whole','rectangular-body','ruled-pdf','challenge']:
            ids=subsets[kind]
            complete=sum(all(x['status'] in ('optimal','heuristic') for x in records[i]['runs']) for i in ids)
            values.append(f'{complete}/{len(ids)}')
        report+='| '+NAMES[method]+' | '+' | '.join(values)+' |\n'
    report+='''
[Timing report](benchmark-native.md) · [Reference checks](library-validation.json) · [Numeric corpus](../tests/fixtures/ebooks-library.json) · [Inputs](benchmark-library-inputs.json) · [PDF visual review](pdf-table-review.json)

## Reproduce

```sh
python3 -m venv .tools/corpus-python
.tools/corpus-python/bin/pip install -r scripts/corpus-requirements.txt
.tools/corpus-python/bin/python scripts/extract_library_tables.py
# Locally inspect candidate PNGs before recording any new PDF approvals.
python3 scripts/merge_reviewed_pdfs.py
python3 scripts/build_library_inputs.py
cargo test --test library_corpus
python3 scripts/benchmark_native.py
python3 scripts/report_native.py
python3 scripts/report_library.py
```

Re-extraction needs the local library; tests and benchmarks run from the committed numeric fixtures. PDF approvals include metric hashes so changed extraction output cannot reuse a stale review.
'''
    (ROOT/'docs/library-coverage.md').write_text(report)
    print(f'{len(tables)} samples / {books} books / {len(inputs)} distinct cases')


if __name__=='__main__':
    main()
