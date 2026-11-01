#!/usr/bin/env python3
"""Compare shared-bound optimizations with the previous published implementation."""
import json
import subprocess

from benchmark_native import ROOT
from benchmark_unified import sha
from report_native import NAMES, fmt_kib, paper_name

BASELINE = '3bfc6998c97db3d3ea305a5cfca98bf151bb0658'


def previous(name):
    return json.loads(subprocess.check_output(['git', 'show', f'{BASELINE}:docs/{name}'], cwd=ROOT))


def main():
    output = dict(baseline_commit=BASELINE, suites={})
    text = '# Shared bounds and A* optimization\n\n'
    text += f'Compared with [the previous implementation](https://github.com/TortoTech/table-stretch/tree/{BASELINE}) on the same inputs, machine, 1-second full-call limit and three repetitions. Both timing and fresh-process memory were rerun. This is a comparison of the combined changes, not an attribution of gains to each individual change.\n\n'
    text += 'A* adds a feasible incumbent, suffix area/floor bounds, clipped candidate domains, direct final-column completion and parent links. It remains best-first search with column-minimality pruning. CP/LCG/MIP add root area bounds, a feasible objective upper bound and corresponding row caps. When the root lower bound meets the feasible height, preprocessing certifies the result without constructing a backend. Otherwise the existing engines and branchers are used. All preprocessing is included in the timings. [Algorithms and correctness](algorithms.md#bounds-shared-with-other-exact-methods) · [Model bounds](native-models.md#objective-bounds).\n\n'
    text += 'Pareto DP keeps its existing algorithm and shares its bound implementation with A*. HTML is unchanged. Small differences in their timings are run-to-run variation, not evidence of a new optimization.\n'
    for suite, stem in [('Ebooks', 'benchmark-native'), ('MiniZinc', 'benchmark-minizinc')]:
        before = previous(f'{stem}-summary.json')
        old_memory = previous(f'{stem}-memory-summary.json')
        after = json.loads((ROOT/f'docs/{stem}-summary.json').read_text())
        memory = json.loads((ROOT/f'docs/{stem}-memory-summary.json').read_text())
        for key in ['input_manifest_sha256', 'machine', 'memory_bytes', 'timeout_ms', 'repeats']:
            assert before['environment'][key] == after['environment'][key], (suite, key)
            assert old_memory['environment'][key] == memory['environment'][key], (suite, key)
        assert memory['environment']['timing_summary_sha256'] == sha(ROOT/f'docs/{stem}-summary.json')
        raw = [json.loads(line) for line in (ROOT/f'docs/{stem}.jsonl').read_text().splitlines()][1:]
        n = len(after['environment']['selection'])
        cap = after['environment']['timeout_ms']
        def time(value):
            return f'> {cap:.2f}' if value >= cap else f'{value:.4f}'
        comparisons = {}
        for method, current in after['methods'].items():
            old = before['methods'][method]
            root_cases = sum(all(
                run['status'] == 'optimal'
                and run['layout']['stats']['generated'] == 0
                and run['layout']['stats']['terminal_evaluations'] == 0
                and run['layout']['stats']['bound_pruned'] > 0
                for run in record['runs'])
                for record in raw if record['algorithm'] == method)
            comparisons[method] = dict(
                before_completed=old['completed'], after_completed=current['completed'],
                before_p50_ms=old['p50_ms'], after_p50_ms=current['p50_ms'],
                before_p95_ms=old['p95_ms'], after_p95_ms=current['p95_ms'],
                root_certified_cases=root_cases)
        output['suites'][suite] = dict(cases=n, methods=comparisons,
            selected_before=before['selected'], selected_after=after['selected'], memory={})
        text += f'\n## {suite}: {n} cases\n\n'
        text += '| Method | Completed before → after | P50 before → after (ms) | P95 before → after (ms) | Root certificates |\n| --- | --- | ---: | ---: | ---: |\n'
        for method, r in sorted(comparisons.items(), key=lambda p: (p[1]['after_p95_ms'], p[1]['after_p50_ms'])):
            text += f'| {paper_name(NAMES[method], method)} | {r["before_completed"]}/{n} → {r["after_completed"]}/{n} | {time(r["before_p50_ms"])} → {time(r["after_p50_ms"])} | {time(r["before_p95_ms"])} → {time(r["after_p95_ms"])} | {r["root_certified_cases"]}/{n} |\n'
        text += '\nRoot certificates count cases certified before search in every repetition. They do not measure backend search speed. Remaining cases still require their named search algorithm.\n\n'
        text += '| Measured implementation | Extra heap P95 before → after (KiB) | Change | RSS P95 before → after (KiB) |\n| --- | ---: | ---: | ---: |\n'
        for method, current in sorted(memory['methods'].items(), key=lambda p: after['methods'][p[0]]['p95_ms']):
            new_metrics = current['metrics']
            assert current['measured'] == n
            if method not in old_memory['methods']:
                output['suites'][suite]['memory'][method] = dict(before_heap_p95_bytes=None,
                    after_heap_p95_bytes=new_metrics['heap_extra_peak_bytes']['p95'], change_percent=None,
                    before_rss_p95_bytes=None, after_rss_p95_bytes=new_metrics['rss_peak_bytes']['p95'])
                text += f'| {paper_name(NAMES[method], method)} | — → {fmt_kib(new_metrics["heap_extra_peak_bytes"]["p95"])} | no same-variant baseline | — → {fmt_kib(new_metrics["rss_peak_bytes"]["p95"])} |\n'
                continue
            old_metrics = old_memory['methods'][method]['metrics']
            a, b = old_metrics['heap_extra_peak_bytes']['p95'], new_metrics['heap_extra_peak_bytes']['p95']
            c, d = old_metrics['rss_peak_bytes']['p95'], new_metrics['rss_peak_bytes']['p95']
            delta = (b/a-1)*100
            output['suites'][suite]['memory'][method] = dict(before_heap_p95_bytes=a, after_heap_p95_bytes=b,
                change_percent=delta, before_rss_p95_bytes=c, after_rss_p95_bytes=d)
            text += f'| {paper_name(NAMES[method], method)} | {fmt_kib(a)} → {fmt_kib(b)} | {delta:+.1f}% | {fmt_kib(c)} → {fmt_kib(d)} |\n'
        text += '\nMemory comparisons use the identical implementation variant on both sides. Memory is collected separately from timing; observed timeout peaks are not completion-memory bounds.\n'
        for family, method in after['selected'].items():
            old_method = before['selected'][family]
            if old_method != method:
                text += f'\nFeatured {family} changed from {NAMES[old_method]} to {NAMES[method]}. The timing rows above compare each variant with itself; absent same-variant memory baselines are shown as missing, not substituted from another variant.\n'
        regressions = [m for m, r in comparisons.items() if r['after_completed'] < r['before_completed']]
        if regressions:
            text += '\nCompletion regressions: ' + ', '.join(NAMES[m] for m in regressions) + '.\n'
        text += f'\n[Timing and all variants]({stem}.md) · [Memory details]({stem}-memory.md)\n'
    text += '\n## Validation\n\nAll returned exact layouts match fixed reference optima. Rust tests cover exhaustive small integer widths, zero heights, gaps, capped final columns, path reconstruction and a case where the first completed A* tail is suboptimal. Rust tests, Clippy, Python checks and the existing abstract Lean proofs pass. Backend floating-point acceptance checks are unchanged. The abstract proofs do not verify the complete A* implementation or the CP/MIP engines.\n\n[Machine-readable comparison](bound-optimization.json). Regenerate with `python3 scripts/report_bound_optimization.py` after refreshing both timing and memory suites.\n'
    (ROOT/'docs/bound-optimization.json').write_text(json.dumps(output, indent=2)+'\n')
    (ROOT/'docs/bound-optimization.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
