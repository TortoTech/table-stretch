#!/usr/bin/env python3
"""Generate the primary all-Rust benchmark and the concise README table."""
import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from benchmark_native import ROOT, METHODS
from benchmark_unified import sha, verify

NAMES = {'pareto':'Pareto DP', 'astar2011':'A*', 'html':'HTML heuristic',
         'cp2011':'CP (2011, Pumpkin)', 'lcg2011':'LCG (2011, Pumpkin)',
         'lcg2015':'LCG (2015 cell-free, Pumpkin)', 'mip2015_unary':'MIP (unary, microlp)',
         'mip2015_onehot':'MIP (one-hot, microlp)', 'mip2015_cellfree':'MIP (cell-free, microlp)'}
FAMILIES = {'Pareto DP':['pareto'], 'A*':['astar2011'], 'HTML heuristic':['html'],
            'CP (Pumpkin)':['cp2011'], 'LCG (Pumpkin)':['lcg2011','lcg2015'],
            'MIP (microlp)':['mip2015_unary','mip2015_onehot','mip2015_cellfree']}


PAPERS = {
    'cp2011': 'https://doi.org/10.1145/2034691.2034697',
    'lcg2011': 'https://doi.org/10.1145/2034691.2034697',
    'lcg2015': 'https://doi.org/10.1287/ijoc.2014.0637',
    'mip2015_unary': 'https://doi.org/10.1287/ijoc.2014.0637',
    'mip2015_onehot': 'https://doi.org/10.1287/ijoc.2014.0637',
    'mip2015_cellfree': 'https://doi.org/10.1287/ijoc.2014.0637',
}


def paper_name(name, method):
    if method == 'pareto':
        return f'**{name}**'
    if method not in PAPERS:
        return name
    label, separator, suffix = name.partition(' ')
    return f'[{label}]({PAPERS[method]}){separator}{suffix}'


def p95(values):
    return sorted(values)[math.ceil(len(values)*.95)-1]


def fmt_kib(value):
    return str((Decimal(str(value)) / 1024).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['ebooks', 'minizinc'], default='ebooks')
    parser.add_argument('--without-memory', action='store_true', help='Refresh timing before collecting new memory results')
    args = parser.parse_args()
    mini = args.suite == 'minizinc'
    stem = 'benchmark-minizinc' if mini else 'benchmark-native'
    rows = [json.loads(s) for s in (ROOT/f'docs/{stem}.jsonl').read_text().splitlines()]
    env, records = rows[0], rows[1:]
    assert env['methods'] == METHODS
    path = ROOT/env.get('input_manifest', 'docs/benchmark-unified-inputs.json')
    assert sha(path) == env['input_manifest_sha256']
    inputs = {(i['sample_index'], i['width']):i for i in json.loads(path.read_text())}
    expected = set(map(tuple, env['selection']))
    n, repeats, cap = len(expected), env['repeats'], env['timeout_ms']*1_000_000
    assert len(records) == n * len(METHODS)
    summary = {}
    for method in METHODS:
        cases = [r for r in records if r['algorithm'] == method]
        assert {(r['sample_index'],r['width']) for r in cases} == expected
        assert len(cases) == n
        medians, phases, complete, optimal, matched = [], [], 0, 0, 0
        statuses = Counter()
        for case in cases:
            item = inputs[case['sample_index'],case['width']]
            assert item['input_sha256'] == case['input_sha256']
            assert len(case['runs']) == repeats
            times, case_phases = [], []
            for run in case['runs']:
                status = run['status']; statuses[status] += 1
                assert status in ('optimal','heuristic','timeout','resource_limit','error')
                if status in ('optimal','heuristic'):
                    assert 0 <= run['wall_ns'] <= cap
                    assert (status == 'heuristic') == (method == 'html')
                    verify(item['table'], run['layout'], item['reference_height'])
                    assert sum(run['phases'].values()) <= run['wall_ns']
                    case_phases.append(run['phases'])
                    times.append(run['wall_ns'])
                else:
                    assert run['layout'] is None
                    times.append(cap)
            medians.append(statistics.median(times))
            if len(case_phases) == repeats:
                complete += 1
                optimal += all(r['status'] == 'optimal' for r in case['runs'])
                matched += all(r['layout']['total_height'] == item['reference_height'] for r in case['runs'])
                phases.append({k:statistics.median(p[k] for p in case_phases) for k in case_phases[0]})
        summary[method] = dict(completed=complete, optimal=optimal, matched=matched,
                               p50_ms=statistics.median(medians)/1e6, p95_ms=p95(medians)/1e6,
                               statuses=dict(statuses), phases_ms={k:statistics.median(p[k] for p in phases)/1e6 for k in phases[0]} if phases else {})
    selected = {family:min(methods, key=lambda m:(-summary[m]['completed'],summary[m]['p95_ms'],summary[m]['p50_ms'])) for family,methods in FAMILIES.items()}
    memory_path = ROOT/f'docs/{stem}-memory-summary.json'
    memory = json.loads(memory_path.read_text()) if memory_path.exists() and not args.without_memory else None
    if memory:
        assert memory['environment']['selected'] == selected
        assert memory['environment']['input_manifest_sha256'] == env['input_manifest_sha256']
        assert memory['raw_sha256'] == sha(ROOT/f'docs/{stem}-memory.jsonl')
        assert memory['environment']['timing_summary_sha256'] == sha(ROOT/f'docs/{stem}-summary.json')
        for source, digest in env['source_sha256'].items():
            if source.startswith('src/') or source in ('Cargo.toml', 'Cargo.lock'):
                assert memory['environment']['source_sha256'][source] == digest, 'Stale memory measurements: rerun memory benchmark'
    date = datetime.fromisoformat(env['utc']).astimezone(ZoneInfo('US/Pacific')).date()
    dataset = 'MiniZinc public cases' if mini else 'real ebook cases'
    intro = f'Latest run: **{date}**, {env["machine"]}, {env["memory_bytes"]//2**30} GiB RAM. **{n} {dataset}**, single thread, {repeats} measurements per case, {env["timeout_ms"]/1000:g}-second limit.\n\n'
    intro += 'Timing uses **Rust library calls in one persistent process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.\n\n'
    def fmt_ms(value):
        return '<0.001' if 0 < value < 0.001 else f'{value:.3f}'

    def table(featured, with_memory=False):
        text = '| Method | Completed | P50 (ms) | P95 (ms) |\n| --- | ---: | ---: | ---: |\n'
        if with_memory:
            text = '| Method | Completed | P50 (ms) | P95 (ms) | Extra heap P95 (KiB) | RSS P95 (KiB) |\n| --- | ---: | ---: | ---: | ---: | ---: |\n'
        for name,m in sorted(featured, key=lambda item: (summary[item[1]]['p95_ms'], summary[item[1]]['p50_ms'])):
            s = summary[m]
            text += f'| {paper_name(name, m)} | {s["completed"]}/{n} | {fmt_ms(s["p50_ms"])} | {fmt_ms(s["p95_ms"])} |'
            if with_memory:
                metrics = memory['methods'][m]['metrics']
                for key in ['heap_extra_peak_bytes', 'rss_peak_bytes']:
                    metric = metrics[key]
                    text += f' {fmt_kib(metric["p95"])} |' if metric is not None else ' — |'
            text += '\n'
        return text
    featured_methods = [(name, m) for name, m in selected.items() if m != 'html']
    featured = intro + table(featured_methods, with_memory=bool(memory))
    featured += f'\nOne variant per exact-method family, selected by completion rate then P95. Rows are sorted by P95 time ascending. Unfinished runs count as {env["timeout_ms"]/1000:g} second in timing percentiles.\n'
    if memory:
        featured += '\nMemory is measured separately in fresh processes: extra live heap during solving and whole-process peak RSS. Includes observed timeout memory; completion counts above are from the timing pass.\n'
    readme_path = ROOT/'README.md'; readme = readme_path.read_text()
    marker = 'benchmark-minizinc' if mini else 'benchmark'
    begin, end = f'<!-- {marker}:start -->', f'<!-- {marker}:end -->'
    a,b = readme.index(begin)+len(begin),readme.index(end)
    readme_path.write_text(readme[:a]+'\n'+featured+readme[b:])
    report = ('# MiniZinc public benchmark\n\n' if mini else '# Native Rust benchmark\n\n')+featured
    if memory:
        report += f'\n[Memory measurement details and completion counts]({stem}-memory.md).\n'
    if mini:
        report += '\n[Source, conversion, and validation](minizinc-corpus.md). All 26 upstream table-layout instances are included at their original widths.\n'
    else:
        report += '\n[Dataset coverage and extraction](library-coverage.md). The expanded dataset includes complete EPUB tables, rectangular bodies, and visually reviewed PDF tables.\n'
    report += '\n## All variants\n\n'+table((NAMES[m],m) for m in METHODS)
    report += f'\nHTML matched the optimum in {summary["html"]["matched"]}/{n} cases.\n'
    report += '\nEach percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.\n'
    report += '\n## Phase medians\n\nMedians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.\n\n| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |\n| --- | ---: | ---: | ---: | ---: |\n'
    for m in sorted(METHODS, key=lambda m: (summary[m]['p95_ms'], summary[m]['p50_ms'])):
        values = summary[m]['phases_ms']
        report += '| '+paper_name(NAMES[m], m)+' | '+' | '.join(f'{values[k]:.4f}' if k in values else '—' for k in ['prepare_ns','model_ns','search_ns','finalize_ns'])+' |\n'
    commands = ('python3 scripts/build_minizinc_inputs.py\n'
                'python3 scripts/benchmark_native.py --inputs docs/benchmark-minizinc-inputs.json --output docs/benchmark-minizinc.jsonl\n'
                'python3 scripts/report_native.py --suite minizinc --without-memory' if mini else
                'python3 scripts/benchmark_native.py\npython3 scripts/report_native.py --without-memory')
    if memory:
        commands += f'\npython3 scripts/benchmark_memory.py --suite {args.suite}\npython3 scripts/report_memory.py --suite {args.suite}\npython3 scripts/report_native.py --suite {args.suite}'
    report += '\n## Reproduce\n\n```sh\n'+commands+'\n```\n\n'
    report += 'One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Every call creates a fresh solver; there is no reused model or cross-method incumbent. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.\n\n'
    report += f'[Raw measurements]({stem}.jsonl) · [Summary]({stem}-summary.json) · [Inputs]({path.name}) · [Model mappings](native-models.md)\n\n'
    report += 'The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.\n'
    (ROOT/f'docs/{stem}.md').write_text(report)
    (ROOT/f'docs/{stem}-summary.json').write_text(json.dumps({'environment':env,'selected':selected,'methods':summary},indent=2)+'\n')
    print(table(featured_methods, with_memory=bool(memory)))


if __name__ == '__main__':
    main()
