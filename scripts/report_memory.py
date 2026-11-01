#!/usr/bin/env python3
"""Validate and summarize fresh-process memory runs without changing time results."""
import argparse
import json
import math
import statistics
from collections import Counter

from benchmark_native import ROOT
from benchmark_unified import sha, verify
from report_native import paper_name


def distribution(values):
    return dict(p50=statistics.median(values),
                p95=sorted(values)[math.ceil(len(values)*.95)-1], maximum=max(values))


def summarize(env, records, inputs):
    n = len(inputs)
    assert len(records) == n*len(env['methods'])
    results = {}
    for method in env['methods']:
        cases = [r for r in records if r['algorithm']==method]
        assert len(cases) == n and {r['case'] for r in cases} == set(range(n))
        complete, measured, statuses = 0, 0, Counter()
        fields = ['heap_extra_peak_bytes','heap_baseline_bytes','heap_peak_bytes','rss_peak_bytes']
        samples = {key:[] for key in fields}
        for case in cases:
            item = inputs[case['case']]
            assert case['input_sha256'] == item['input_sha256']
            assert (case['sample_index'],case['width']) == (item['sample_index'],item['width'])
            runs = case['runs']
            assert len(runs) == env['repeats']
            for run in runs:
                statuses[run['status']] += 1
                assert run['status'] in ('optimal','heuristic','timeout','resource_limit','error')
                if run['layout'] is not None:
                    verify(item['table'],run['layout'],item['reference_height'])
                    assert (run['status']=='heuristic') == (method=='html')
                if run['status'] in ('optimal','heuristic'):
                    assert run['layout'] is not None and run['wall_ns'] <= env['timeout_ms']*1_000_000
                if run['memory_available']:
                    assert run['heap_peak_bytes'] >= run['heap_end_bytes'] >= 0
                    assert run['heap_peak_bytes']-run['heap_baseline_bytes'] == run['heap_extra_peak_bytes'] >= 0
                    assert run['rss_peak_bytes'] > 0
            complete += all(r['status'] in ('optimal','heuristic') for r in runs)
            if all(r['memory_available'] for r in runs):
                measured += 1
                for key in fields:
                    samples[key].append(statistics.median(r[key] for r in runs))
        # Never silently drop a hard-killed/crashed case to make percentiles smaller.
        results[method] = dict(completed=complete,measured=measured,cases=n,statuses=dict(statuses),
            metrics={key:distribution(values) if measured == n else None for key,values in samples.items()})
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--suite',choices=['ebooks','minizinc'],required=True)
    args = ap.parse_args()
    stem = 'benchmark-native' if args.suite=='ebooks' else 'benchmark-minizinc'
    raw_path = ROOT/f'docs/{stem}-memory.jsonl'
    rows = [json.loads(s) for s in raw_path.read_text().splitlines()]
    env, records = rows[0], rows[1:]
    path = ROOT/env['input_manifest']
    assert sha(path) == env['input_manifest_sha256']
    timing_path = ROOT/env['timing_summary']
    assert sha(timing_path) == env['timing_summary_sha256']
    timing = json.loads(timing_path.read_text())
    assert timing['selected'] == env['selected']
    inputs = json.loads(path.read_text())
    results = summarize(env,records,inputs)
    output = dict(environment=env,raw_sha256=sha(raw_path),methods=results)
    (ROOT/f'docs/{stem}-memory-summary.json').write_text(json.dumps(output,indent=2)+'\n')
    title = 'Ebook' if args.suite=='ebooks' else 'MiniZinc'
    report = f'# {title} memory benchmark\n\n'
    report += f'{len(inputs)} cases, {env["repeats"]} fresh processes per method/case, {env["timeout_ms"]/1000:g}-second solve limit. {env["machine"]}, {env["memory_bytes"]//2**30} GiB RAM. Recorded at {env["utc"]}.\n\n'
    report += 'The six implementations are fixed to those selected by the corresponding timing benchmark. Rows retain its P95 time order. Completion counts below belong to this separate instrumented memory pass.\n\n'
    report += '| Method | Completed | Measured | Extra heap P50 (KiB) | Extra heap P95 (KiB) | Extra heap max (KiB) | RSS P95 (MiB) |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
    def value(s, key, percentile, divisor):
        metric = s['metrics'][key]
        return f'{metric[percentile]/divisor:.3f}' if metric is not None else '—'
    for name, method in sorted(env['selected'].items(),key=lambda p:(timing['methods'][p[1]]['p95_ms'],timing['methods'][p[1]]['p50_ms'])):
        s = results[method]
        report += f'| {paper_name(name,method)} | {s["completed"]}/{len(inputs)} | {s["measured"]}/{len(inputs)} | '
        report += ' | '.join([value(s,'heap_extra_peak_bytes',k,1024) for k in ['p50','p95','maximum']]
                             +[value(s,'rss_peak_bytes','p95',1024**2)])+' |\n'
    report += '\nEach case contributes the median of its repetitions; P50/P95/max summarize those case medians. Timeout memory is included as observed, with no artificial memory penalty. It is not an upper bound on memory required to finish. If any case lacks telemetry, that method’s aggregate memory values are withheld; missing values are never zero-filled.\n\n'
    report += '## Measurement scope\n\n'
    report += '- **Extra heap:** peak live bytes requested through Rust’s global allocator during the library call, minus live bytes just before it. Includes preparation, models, search and the returned layout. Excludes the already loaded input, JSON serialization, stack, allocator metadata/caches and transient buffers internal to realloc. Counts live bytes, not cumulative allocation traffic.\n'
    report += '- **RSS:** macOS `/usr/bin/time -l` maximum resident set size for the entire fresh child process, converted from bytes. Includes startup, one loaded input, libraries, stack, allocator retention, solver and output. No baseline subtraction is applied to RSS.\n'
    report += '- **Isolation:** one case and one solve per process, no warmup; the allocator begins tracking the solve after input parsing and resets the heap peak. Raw records retain baseline, total peak and end heap bytes. This prevents earlier calls from contaminating either peak.\n'
    report += '- **Timing:** allocation instrumentation adds overhead. Its diagnostic durations are not substituted for the original uninstrumented timings. A two-second process watchdog grace handles startup and cooperative timeout overruns; hard kills are recorded as missing memory.\n\n'
    report += 'The allocator delegates to [`System`](https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html). RSS is reported by [Apple’s time implementation](https://github.com/apple-oss-distributions/shell_cmds/blob/main/time/time.c).\n\n'
    report += f'## Reproduce\n\n```sh\npython3 scripts/benchmark_memory.py --suite {args.suite}\npython3 scripts/report_memory.py --suite {args.suite}\npython3 scripts/report_native.py --suite {args.suite}\n```\n\n'
    report += f'[Raw measurements]({stem}-memory.jsonl) · [Summary]({stem}-memory-summary.json) · [Timing benchmark]({stem}.md)\n'
    (ROOT/f'docs/{stem}-memory.md').write_text(report)
    print(report.split('Each case')[0])


if __name__=='__main__':
    main()
