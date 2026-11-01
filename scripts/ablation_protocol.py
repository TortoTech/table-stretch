#!/usr/bin/env python3
"""Freeze book-grouped retrospective evaluation before any new measurements."""
import hashlib
import json
from pathlib import Path

from benchmark_native import ROOT
from benchmark_unified import sha

FULL = dict(incumbent=True, area_bound=True, floor_bound=True, column_caps=True,
            terminal_column=True, compact_paths=True, row_caps=True, root_certificate=True)
FAMILIES = {'Pareto DP':['pareto'], 'A*':['astar2011'], 'CP':['cp2011'],
            'LCG':['lcg2011','lcg2015'], 'MIP':['mip2015_unary','mip2015_onehot','mip2015_cellfree']}


def profiles(method):
    if method in ('pareto', 'astar2011'):
        base = {**FULL, 'incumbent':False, 'area_bound':method=='astar2011', 'floor_bound':False,
                'column_caps':False, 'terminal_column':False, 'compact_paths':False}
        result = dict(base=base, common={**FULL, 'terminal_column':False, 'compact_paths':False}, full=FULL.copy())
        for key in ['incumbent', 'area_bound', 'floor_bound', 'column_caps', 'terminal_column', 'compact_paths']:
            result['without_'+key] = {**FULL, key:False}
        return result
    return dict(base={**FULL, 'incumbent':False, 'area_bound':False, 'row_caps':False, 'root_certificate':False},
                full=FULL.copy(), without_area_bound={**FULL, 'area_bound':False},
                without_incumbent={**FULL, 'incumbent':False, 'row_caps':False, 'root_certificate':False},
                without_row_caps={**FULL, 'row_caps':False},
                without_root_certificate={**FULL, 'root_certificate':False})


def build():
    inputs_path = ROOT/'docs/benchmark-library-inputs.json'
    source_path = ROOT/'tests/fixtures/ebooks-library.json'
    mini_path = ROOT/'docs/benchmark-minizinc-inputs.json'
    inputs, sources = json.loads(inputs_path.read_text()), json.loads(source_path.read_text())['tables']
    parent = {s['book_sha256']:s['book_sha256'] for s in sources}
    def root(book):
        if parent[book] != book: parent[book] = root(parent[book])
        return parent[book]
    # Duplicate geometries can have several source aliases. Connected books
    # must stay together, even when the retained representative has one name.
    case_books = []
    for case in inputs:
        assert sources[case['sample_index']]['book_sha256'] == case['book_sha256']
        books = {case['book_sha256']} | {sources[a['sample_index']]['book_sha256'] for a in case['duplicate_sources']}
        for b in books: parent[root(b)] = root(case['book_sha256'])
        case_books.append(books)
    groups = {}
    for book in sorted(parent): groups.setdefault(root(book), []).append(book)
    seed = 'table-stretch-book-holdout-v1'
    ordered = sorted(groups.values(), key=lambda g: hashlib.sha256((seed+':'+','.join(g)).encode()).hexdigest())
    n_validation = max(1, len(ordered)//3)
    validation_books = set(b for group in ordered[:n_validation] for b in group)
    evaluation_books = set(parent)-validation_books
    validation, evaluation = [], []
    for index, books in enumerate(case_books):
        assert books <= validation_books or books <= evaluation_books
        (validation if books <= validation_books else evaluation).append(index)
    assert set(inputs[i]['input_sha256'] for i in validation).isdisjoint(inputs[i]['input_sha256'] for i in evaluation)
    return dict(schema=1, seed=seed, development_baseline='d74547957327dca06dc349550a3660231bc16606',
        prior_exposure='Both corpora were used in earlier development. This is a retrospective grouped selection/evaluation split, not a never-seen test set.',
        inputs={str(p.relative_to(ROOT)):sha(p) for p in [inputs_path, source_path, mini_path]},
        grouping='Connected book SHA-256 groups including duplicate source aliases; all widths of a source table remain in one group.',
        validation_books=sorted(validation_books), evaluation_books=sorted(evaluation_books),
        validation_cases=validation, evaluation_cases=evaluation,
        minizinc_cases=list(range(len(json.loads(mini_path.read_text())))),
        families=FAMILIES, full_options=FULL,
        profiles={m:profiles(m) for methods in FAMILIES.values() for m in methods},
        common_alias='For CP/LCG/MIP, common equals full; no extra family-specific optimization is introduced in this ablation scope.',
        dependencies='without_incumbent also disables its dependent row caps and root certificate in research models. Existing static row floors, column caps, sparse-domain compaction and fixed-cell elimination remain fixed in those models. Search baseline A* retains its original area heuristic and column-minimality; Pareto retains dominance pruning.',
        selection='Full configuration only on validation cases. Max completed cases, then minimum capped P95, then minimum median, then method name. Freeze one variant per family before evaluation; use the same variant on both evaluation suites. Do not select an ablation winner on evaluation data.',
        timing=dict(timeout_ms=1000, repeats=3, warmups=1, seed=1, threads=1,
            scope='Full Rust library call including all preparation, model/search, layout validation and teardown; excludes JSON/IPC, text measurement and startup.'),
        memory=dict(repeats=3, warmups=0, seed=1,
            scope='Every evaluation configuration in a fresh process. Extra live requested heap during solve and whole-process macOS peak RSS; measured separately from uninstrumented time.'),
        statistics='One median per case. P95 nearest-rank; incomplete repetitions count as timeout for timing. Completion requires all repetitions optimal. Missing memory is never zero-filled. Performance profiles use solved cases divided by best solved time, failures at infinity; denominator includes all cases.',
        provenance='Commit this protocol and its generator before running selection/evaluation. Changes require a new protocol/version; no split or configuration changes based on outcomes.')


if __name__ == '__main__':
    path = ROOT/'docs/ablation-protocol.json'
    value = build()
    payload = json.dumps(value, indent=2)+'\n'
    if path.exists():
        assert path.read_text() == payload, 'Frozen protocol differs; create a new version rather than overwrite it.'
    else:
        path.write_text(payload)
    print(f"Validation: {len(value['validation_books'])} books / {len(value['validation_cases'])} cases; evaluation: {len(value['evaluation_books'])} books / {len(value['evaluation_cases'])} cases; MiniZinc: {len(value['minizinc_cases'])}.")
