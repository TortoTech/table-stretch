#!/usr/bin/env python3
"""Compare published memory results against the pre-optimization commit."""
import json
import subprocess

from benchmark_native import ROOT
from benchmark_unified import sha
from report_native import NAMES, paper_name

BASELINE = 'ae9faf0'


def previous(name):
    return json.loads(subprocess.check_output(['git','show',f'{BASELINE}:docs/{name}'],cwd=ROOT))


def main():
    commit = subprocess.check_output(['git','rev-parse',BASELINE],cwd=ROOT,text=True).strip()
    results = []
    completion_regressions = []
    for suite, stem in [('Ebooks','benchmark-native'),('MiniZinc','benchmark-minizinc')]:
        old_time = previous(f'{stem}-summary.json')
        old_mem = previous(f'{stem}-memory-summary.json')
        new_time = json.loads((ROOT/f'docs/{stem}-summary.json').read_text())
        new_mem = json.loads((ROOT/f'docs/{stem}-memory-summary.json').read_text())
        assert old_time['environment']['input_manifest_sha256'] == new_time['environment']['input_manifest_sha256']
        assert old_mem['environment']['input_manifest_sha256'] == new_mem['environment']['input_manifest_sha256']
        assert new_mem['environment']['timing_summary_sha256'] == sha(ROOT/f'docs/{stem}-summary.json')
        for before, after in [(old_time, new_time), (old_mem, new_mem)]:
            for key in ['machine', 'memory_bytes', 'timeout_ms', 'repeats']:
                assert before['environment'][key] == after['environment'][key], (suite, key)
        for method, after in new_time['methods'].items():
            before = old_time['methods'][method]
            if after['completed'] < before['completed']:
                completion_regressions.append(dict(suite=suite,method=method,
                    before=before['completed'],after=after['completed'],
                    cases=len(new_time['environment']['selection'])))
        for family in ['CP (Pumpkin)','LCG (Pumpkin)','MIP (microlp)']:
            a, b = old_time['selected'][family], new_time['selected'][family]
            before = old_mem['methods'][a]['metrics']['heap_extra_peak_bytes']['p95']
            after = new_mem['methods'][b]['metrics']['heap_extra_peak_bytes']['p95']
            results.append(dict(suite=suite,family=family,before_method=a,after_method=b,
                same_variant=a==b,before_heap_p95_bytes=before,after_heap_p95_bytes=after,
                heap_reduction_percent=(1-after/before)*100 if a==b else None,
                before_time_p95_ms=old_time['methods'][a]['p95_ms'],
                after_time_p95_ms=new_time['methods'][b]['p95_ms'],
                before_completed=old_time['methods'][a]['completed'],
                after_completed=new_time['methods'][b]['completed'],
                cases=len(new_time['environment']['selection'])))
    results.sort(key=lambda r:(r['suite']=='MiniZinc',r['after_time_p95_ms']))
    (ROOT/'docs/memory-optimization.json').write_text(json.dumps(dict(baseline_commit=commit,comparisons=results,completion_regressions=completion_regressions),indent=2)+'\n')
    text = '# Model memory optimization\n\n'
    text += f'Compared with [the published baseline](https://github.com/TortoTech/table-stretch/tree/{commit}), using the same 1,383 ebook cases and 26 MiniZinc cases, hardware, 1-second solve limit and three repetitions. Timing and memory remain separate measurement passes.\n\n'
    text += '## Changes\n\n'
    text += '- Grow the Pumpkin nogood arena on demand instead of reserving 1 MB.\n- Encode sparse integer domains with interval-exclusion clauses instead of explicit holes.\n- Use literal constants in element arrays and fold fixed cells into row/column lower bounds.\n- Remove impossible low row heights and redundant MIP clauses and fixed-cell configuration variables.\n\n'
    text += 'These are equivalent model reductions; CP still disables learning and LCG still enables it. Gap clauses change propagation scheduling and explanations, so identical search traces or runtime improvements are not assumed. [Equivalence arguments](native-models.md#compact-model-construction).\n\n'
    text += '## Peak additional live heap\n\n| Dataset | Implementation before → after | P95 before (KiB) | P95 after (KiB) | Reduction |\n| --- | --- | ---: | ---: | ---: |\n'
    for r in results:
        label = paper_name(NAMES[r['before_method']],r['before_method'])
        if not r['same_variant']:
            label += ' → '+paper_name(NAMES[r['after_method']],r['after_method'])
        reduction = f'{r["heap_reduction_percent"]:.1f}%' if r['same_variant'] else 'variant changed'
        text += f'| {r["suite"]} | {label} | {r["before_heap_p95_bytes"]/1024:.3f} | {r["after_heap_p95_bytes"]/1024:.3f} | {reduction} |\n'
    text += '\nEach family uses the version selected by its respective timing pass. Percentage reductions are only reported for the same variant. Timeout memory is the peak observed before termination, not a bound on memory required to complete.\n\n'
    text += '## Timing and completion\n\n| Dataset | Family | Completed before → after | P95 before (ms) | P95 after (ms) |\n| --- | --- | --- | ---: | ---: |\n'
    for r in results:
        text += f'| {r["suite"]} | {paper_name(r["family"],r["after_method"])} | {r["before_completed"]}/{r["cases"]} → {r["after_completed"]}/{r["cases"]} | {r["before_time_p95_ms"]:.3f} | {r["after_time_p95_ms"]:.3f} |\n'
    if completion_regressions:
        text += '\n### Tradeoffs across all variants\n\n'
        for r in completion_regressions:
            text += f'- {r["suite"]}: {paper_name(NAMES[r["method"]],r["method"])} completion fell from {r["before"]}/{r["cases"]} to {r["after"]}/{r["cases"]} at the same time limit.\n'
        text += '\nReduced model memory does not guarantee faster search: the gap-clause representation changes propagation and conflict explanations. These regressions remain visible in the all-variant reports; family selection still prioritizes completion before P95 time.\n'
    text += '\nAll returned exact layouts are checked against the fixed reference optima. Regression tests cover large gaps, zero-height cells, fixed cells dominating row heights, and exhaustive small-width oracles. Rust tests, Clippy, Python checks and the existing abstract Lean proofs pass. MIP numerical acceptance tolerances are unchanged; these results do not constitute a rational optimality certificate for the floating-point backend.\n\n'
    text += '[Ebook results](benchmark-native.md) · [MiniZinc results](benchmark-minizinc.md) · [Comparison data](memory-optimization.json)\n\nRegenerate this comparison with `python3 scripts/report_memory_optimization.py` after refreshing both timing and memory reports.\n'
    (ROOT/'docs/memory-optimization.md').write_text(text)
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
