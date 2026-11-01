#!/usr/bin/env python3
"""Generate the archived process-level benchmark reports."""
import json
import math
import statistics
from datetime import datetime
from zoneinfo import ZoneInfo

from benchmark_unified import METHODS, ROOT, sha, verify

NAMES = {
    'pareto': 'Pareto DP (Rust)',
    'pareto_baseline': 'Pareto DP (previous version)',
    'astar2011': 'A* (Rust)',
    'html': 'HTML proportional (Rust, heuristic)',
    'cp2011_gecode': 'CP (Gecode, column-width search)',
    'lcg2011_chuffed': 'Configuration LCG (Chuffed, mixed search)',
    'lcg2015_cellfree': 'Cell-free LCG (Chuffed, without RCSV)',
    'mip2015_unary': 'Unary MIP (HiGHS)',
    'mip2015_onehot': 'One-hot MIP (HiGHS)',
    'cp2011_chuffed_seq': 'CP (Chuffed, cell-height search, no learning)',
    'lcg2011_chuffed_seq': 'LCG (Chuffed, cell-height search)',
    'lcg2015_rcsv': 'Cell-free LCG (Chuffed, RCSV)',
    'mip2015_cellfree': 'Cell-free MIP (HiGHS, RCSV + unary)',
}
FAMILIES = {
    'Pareto DP': ['pareto'],
    'A*': ['astar2011'],
    'HTML heuristic': ['html'],
    'CP': ['cp2011_gecode', 'cp2011_chuffed_seq'],
    'CP/SAT (LCG)': ['lcg2011_chuffed', 'lcg2011_chuffed_seq',
                     'lcg2015_cellfree', 'lcg2015_rcsv'],
    'MIP': ['mip2015_unary', 'mip2015_onehot', 'mip2015_cellfree'],
}
FEATURED_NAMES = {
    'pareto': 'Pareto DP (Rust)', 'astar2011': 'A* (Rust)',
    'html': 'HTML heuristic (Rust)',
    'cp2011_gecode': 'CP (Gecode)', 'cp2011_chuffed_seq': 'CP (Chuffed)',
    'lcg2011_chuffed': 'LCG (Chuffed)', 'lcg2011_chuffed_seq': 'LCG (Chuffed)',
    'lcg2015_cellfree': 'LCG (Chuffed)', 'lcg2015_rcsv': 'LCG (Chuffed)',
    'mip2015_unary': 'MIP (HiGHS)', 'mip2015_onehot': 'MIP (HiGHS)',
    'mip2015_cellfree': 'MIP (HiGHS)',
}


def quantile(values, p):
    values = sorted(values)
    return values[max(0, math.ceil(len(values)*p)-1)] if values else None


def describe(values):
    return {'median': statistics.median(values), 'p95': quantile(values, .95),
            'max': max(values)} if values else None


def median_phase(cases, *keys):
    values = []
    for case in cases:
        per_run = []
        for run in case['runs']:
            value = run['phases']
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            if value is not None:
                per_run.append(value)
        if per_run:
            values.append(statistics.median(per_run))
    return statistics.median(values) if values else None


def fmt(value, divisor=1):
    return '—' if value is None else f'{value/divisor:.3f}'


def main():
    rows = [json.loads(line) for line in (ROOT/'docs/benchmark-unified.jsonl').read_text().splitlines()]
    env, records = rows[0], rows[1:]
    methods = env['methods']
    assert set(methods) in (set(METHODS), set(METHODS) | {'pareto_baseline'})
    native_methods = [m for m in methods if m in ('pareto_baseline','pareto','astar2011','html')]
    external_methods = [m for m in methods if m not in native_methods]
    inputs_path = ROOT/'docs/benchmark-unified-inputs.json'
    assert sha(inputs_path) == env['input_manifest_sha256']
    inputs = {(r['sample_index'],r['width']):r for r in json.loads(inputs_path.read_text())}
    expected = {tuple(pair) for pair in env['selection']}
    n, repeats = len(expected), env['repeats']
    assert len(records) == n*len(methods)
    grouped = {m: [r for r in records if r['algorithm']==m] for m in methods}
    for method, cases in grouped.items():
        assert {(r['sample_index'],r['width']) for r in cases} == expected
        for case in cases:
            instance = inputs[case['sample_index'],case['width']]
            assert case['input_sha256'] == instance['input_sha256']
            assert len(case['runs']) == repeats
            for run in case['runs']:
                assert run['status'] in ('optimal', 'heuristic', 'timeout')
                assert run['status'] != 'heuristic' or method == 'html'
                if run['status'] != 'timeout':
                    assert run['wall_ns'] <= env['timeout_ms']*1e6
                if run['layout']:
                    verify(instance['table'],run['layout'],instance['reference_height'])
    common = expected.copy()
    for m in methods:
        common &= {(r['sample_index'],r['width']) for r in grouped[m] if r['all_completed']}
    summary = {'cases': n, 'repeats': repeats, 'common_completed_cases':len(common),
               'common_selection':sorted(common), 'methods':{}}
    for m, cases in grouped.items():
        runs = [run for r in cases for run in r['runs']]
        capped = [statistics.median(min(run['wall_ns']/1e6,env['timeout_ms']) for run in r['runs']) for r in cases]
        completed = [r['wall_median_ns']/1e6 for r in cases if r['all_completed']]
        common_cases = [r for r in cases if (r['sample_index'],r['width']) in common]
        timeouts = [r for r in runs if r['status']=='timeout']
        gaps = [r['gap'] for r in timeouts if r['gap'] is not None]
        summary['methods'][m] = {
            'completed_cases': sum(r['all_completed'] for r in cases),
            'optimal_cases': sum(r['all_optimal'] for r in cases),
            'timeout_runs': len(timeouts), 'capped_wall_ms':describe(capped),
            'successful_wall_ms':describe(completed),
            'common_wall_ms':describe([r['wall_median_ns']/1e6 for r in common_cases]),
            'native_total_ms':describe([statistics.median(sum(run['phases']['native'].values()) for run in r['runs'])/1e6 for r in cases if r['all_completed']]) if m in native_methods else None,
            'native_stats':{key:describe([statistics.median(run['layout']['stats'].get(key,0) for run in r['runs']) for r in cases if r['all_completed']]) for key in ('generated','comparisons','peak_frontier','bound_pruned','terminal_evaluations')} if m in native_methods else None,
            'par2_ms': statistics.mean(2*env['timeout_ms'] if r['status']!='optimal' else r['wall_ns']/1e6 for r in runs) if m!='html' else None,
            'timeout_gap':describe(gaps), 'timeout_missing_feasible':sum(r['layout'] is None for r in timeouts),
            'equal_reference_cases': sum(all(run['layout'] and run['layout']['total_height']==r['reference_height'] for run in r['runs']) for r in cases),
            'phase_common': {
                'read_ns':median_phase(common_cases,'read_ns'), 'fallback_ns':median_phase(common_cases,'fallback_ns'),
                'native_prepare_ns':median_phase(common_cases,'native','prepare_ns'),
                'native_search_ns':median_phase(common_cases,'native','search_ns'),
                'native_finalize_ns':median_phase(common_cases,'native','finalize_ns'),
                'export_ns':median_phase(common_cases,'export_ns'),
                'flat_seconds':median_phase(common_cases,'engine_statistics','flatTime'),
                'init_seconds':median_phase(common_cases,'engine_statistics','initTime'),
                'solve_seconds':median_phase(common_cases,'engine_statistics','solveTime')}}
    data = summary['methods']
    selected = {}
    for family, candidates in FAMILIES.items():
        available = [m for m in candidates if m in data]
        assert available, family
        selected[family] = min(available, key=lambda m: (
            -data[m]['completed_cases'],
            data[m]['capped_wall_ms']['p95'], data[m]['capped_wall_ms']['median']))

    date = datetime.fromisoformat(env['utc']).astimezone(ZoneInfo('US/Pacific')).strftime('%Y-%m-%d')
    hardware = f"{env['machine']}, {env['memory_bytes']//2**30} GiB RAM"
    featured = f"""Latest run: **{date}**, {hardware}. **{n} real ebook cases**, single thread, {repeats} measurements per case, {env['timeout_ms']/1000:g}-second limit.

One variant per family, selected by completion rate, then lowest P95. Times cover the full process from precomputed size curves to layout, including startup and model compilation.

| Method | Completed | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
"""
    for m in selected.values():
        stats = data[m]
        featured += f"| {FEATURED_NAMES[m]} | {stats['completed_cases']}/{n} | {fmt(stats['capped_wall_ms']['median'])} | {fmt(stats['capped_wall_ms']['p95'])} |\n"
    featured += f"\nExact runs report solver-certified optimality (MIP uses floating-point tolerances). The HTML heuristic matched the optimum in {data['html']['equal_reference_cases']}/{n} cases.\n"

    overview = '# External solver reference\n\nThe primary comparison is now the [native Rust benchmark](benchmark-native.md). The archived results below include process startup and MiniZinc compilation.\n\n' + featured + """
The cases are drawn from 317 tables in 25 ebooks. Quantiles use each case's median runtime. All methods receive identical inputs and share the same end-to-end deadline.

## Reproduce

```sh
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc
python3 scripts/report_unified.py
```

[All variants and phase timings](benchmark-unified-details.md) · [Raw measurements](benchmark-unified.jsonl) · [Inputs](benchmark-unified-inputs.json) · [Summary](benchmark-unified-summary.json)
"""
    report = f"# All benchmark variants\n\n{date} · {hardware} · {n} cases · {repeats} measurements per case.\n\n[Featured results](benchmark-unified.md) select one implementation per family. This report retains every measured variant.\n\n"
    report += '| Method | Completed | Timeout runs | P50 (ms) | P95 (ms) | PAR-2 (ms) |\n| --- | ---: | ---: | ---: | ---: | ---: |\n'
    for m in methods:
        stats = data[m]
        report += f"| {NAMES[m]} | {stats['completed_cases']}/{n} | {stats['timeout_runs']}/{n*repeats} | {fmt(stats['capped_wall_ms']['median'])} | {fmt(stats['capped_wall_ms']['p95'])} | {fmt(stats['par2_ms'])} |\n"
    report += f"""
A completed exact run must certify optimality before the deadline. A completed case requires every measured run to finish. P50/P95 use per-case median times across all {n} cases, with timeouts capped at {env['timeout_ms']} ms. PAR-2 averages all runs, charging twice the deadline for a timeout; the HTML heuristic is excluded from that score.

## Phase diagnostics

These medians use the same {len(common)} cases completed by every implementation. Engine clocks and phase boundaries differ; use end-to-end times for comparisons.

Native phases, in microseconds:

| Method | Preparation | Search | Final stretch |
| --- | ---: | ---: | ---: |
"""
    for m in native_methods:
        phase = data[m]['phase_common']
        report += f"| {NAMES[m]} | {fmt(phase['native_prepare_ns'],1e3)} | {fmt(phase['native_search_ns'],1e3)} | {fmt(phase['native_finalize_ns'],1e3)} |\n"
    report += '\nExternal phases, in milliseconds. Chuffed rounds search statistics to milliseconds.\n\n| Method | Export | Compile | Initialize | Solve |\n| --- | ---: | ---: | ---: | ---: |\n'
    for m in external_methods:
        phase = data[m]['phase_common']
        report += f"| {NAMES[m]} | {fmt(phase['export_ns'],1e6)} | {fmt(phase['flat_seconds'],.001)} | {fmt(phase['init_seconds'],.001)} | {fmt(phase['solve_seconds'],.001)} |\n"
    report += """
## Protocol

- One warmup, then serial measurements with shuffled method order, one thread, and seed 1.
- Fresh worker processes read identical curve JSON. Timing includes validation, a common feasible fallback, method-specific preparation, model compilation, solving, stretching, and output. Font shaping and curve construction are excluded.
- A parent watchdog enforces the total deadline and cleans up the entire live process tree, including solver processes in separate groups. Only output received before the deadline is accepted.
- Every layout is checked against the input curves. Certified optima are checked against reference heights. Timed-out runs retain any received feasible layout without claiming optimality.
- MiniZinc uses `-O0` because of a known [compiler regression](algorithms.md#compiler-regression). The metadata records solver versions, flags, input hashes, source hashes, and worker identity.

The current measurements replace earlier runs affected by incomplete timeout cleanup. These are project implementations on ebook-derived curves; model correspondence is documented in the [research audit](research-audit.md).

## Reproduce

```sh
python3 scripts/check_models.py
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc
python3 scripts/report_unified.py
```

To include the previous Pareto version in the same run:

```sh
git worktree add --detach .tools/pareto-before-source 104c545
cargo build --locked --release --manifest-path .tools/pareto-before-source/Cargo.toml --example unified_worker
python3 scripts/benchmark_unified.py --minizinc /path/to/minizinc --baseline-worker .tools/pareto-before-source/target/release/examples/unified_worker
python3 scripts/report_unified.py
```

The benchmark runner currently targets macOS. The committed input manifest requires no access to the local ebook library.

[Raw measurements](benchmark-unified.jsonl) · [Inputs](benchmark-unified-inputs.json) · [Statistics](benchmark-unified-summary.json) · [Algorithms](algorithms.md)
"""
    (ROOT/'docs/benchmark-unified.md').write_text(overview)
    (ROOT/'docs/benchmark-unified-details.md').write_text(report)
    (ROOT/'docs/benchmark-unified-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(featured)


if __name__ == '__main__':
    main()
