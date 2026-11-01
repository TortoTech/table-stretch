#!/usr/bin/env python3
"""Generate the primary all-Rust benchmark and the concise README table."""
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from datetime import datetime
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


def p95(values):
    return sorted(values)[math.ceil(len(values)*.95)-1]


def main():
    rows = [json.loads(s) for s in (ROOT/'docs/benchmark-native.jsonl').read_text().splitlines()]
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
    date = datetime.fromisoformat(env['utc']).astimezone(ZoneInfo('US/Pacific')).date()
    intro = f'Latest run: **{date}**, {env["machine"]}, {env["memory_bytes"]//2**30} GiB RAM. **{n} real ebook cases**, single thread, {repeats} measurements per case, {env["timeout_ms"]/1000:g}-second limit.\n\n'
    intro += 'All methods run as **Rust library calls in one process**. Times include preparation, model construction, search, and final layout; exclude text measurement, JSON parsing, and process startup.\n\n'
    def fmt_ms(value):
        return '<0.001' if 0 < value < 0.001 else f'{value:.3f}'

    def table(featured):
        text = '| Method | Completed | P50 (ms) | P95 (ms) |\n| --- | ---: | ---: | ---: |\n'
        for name,m in featured:
            s = summary[m]
            text += f'| {name} | {s["completed"]}/{n} | {fmt_ms(s["p50_ms"])} | {fmt_ms(s["p95_ms"])} |\n'
        return text
    featured = intro + table(selected.items())
    featured += f'\nFastest variant per family, ranked by completion rate then P95. Unfinished runs count as {env["timeout_ms"]/1000:g} second in these percentiles. HTML matched the optimum in {summary["html"]["matched"]}/{n} cases.\n'
    readme_path = ROOT/'README.md'; readme = readme_path.read_text()
    begin, end = '<!-- benchmark:start -->', '<!-- benchmark:end -->'
    a,b = readme.index(begin)+len(begin),readme.index(end)
    readme_path.write_text(readme[:a]+'\n'+featured+readme[b:])
    report = '# Native Rust benchmark\n\n'+featured
    report += '\n[Dataset coverage and extraction](library-coverage.md). The expanded dataset includes complete EPUB tables, rectangular bodies, and visually reviewed PDF tables.\n'
    report += '\n## All variants\n\n'+table((NAMES[m],m) for m in METHODS)
    report += '\nEach percentile uses one median per case. Failures and timeouts are censored at the common limit, including in selection. A case completes only when every measured repetition completes. All returned layouts are checked against the original profiles and the fixed reference optimum.\n'
    report += '\n## Phase medians\n\nMedians over completed cases only; each case uses the median of its repetitions. These component medians need not sum to the total median. Solver teardown is included in search.\n\n| Method | Prepare (ms) | Model (ms) | Search (ms) | Finalize (ms) |\n| --- | ---: | ---: | ---: | ---: |\n'
    for m in METHODS:
        values = summary[m]['phases_ms']
        report += '| '+NAMES[m]+' | '+' | '.join(f'{values[k]:.4f}' if k in values else '—' for k in ['prepare_ns','model_ns','search_ns','finalize_ns'])+' |\n'
    report += '\n## Reproduce\n\n```sh\npython3 scripts/benchmark_native.py\npython3 scripts/report_native.py\n```\n\n'
    report += 'One warmup per method/case precedes the measured repetitions. Method order is shuffled with seed 1. Every call creates a fresh solver; there is no reused model or cross-method incumbent. All methods share the full-call wall limit; a watchdog kills and restarts the worker if cooperative termination overruns by two seconds. Raw records preserve errors, actual elapsed times and worker generations. Count limits are disabled for this benchmark.\n\n'
    report += f'[Raw measurements](benchmark-native.jsonl) · [Summary](benchmark-native-summary.json) · [Inputs]({path.name}) · [Model mappings](native-models.md)\n\n'
    report += 'The [external-solver benchmark](benchmark-unified.md) remains a separate process-level reference. Its timings include startup and MiniZinc compilation and must not be mixed with this table.\n'
    (ROOT/'docs/benchmark-native.md').write_text(report)
    (ROOT/'docs/benchmark-native-summary.json').write_text(json.dumps({'environment':env,'selected':selected,'methods':summary},indent=2)+'\n')
    print(table(selected.items()))


if __name__ == '__main__':
    main()
