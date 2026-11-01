#!/usr/bin/env python3
"""Run real CP/LCG/MIP engines on a deterministic hard/diverse corpus subset."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import tempfile
import time

METHODS = {
    'cp2011_gecode': ('gecode', 'cp2011.mzn', []),
    'lcg2011_chuffed': ('chuffed', 'cp2011.mzn', ['-f', '--vsids']),
    'lcg2015_cellfree': ('chuffed', 'lcg2015.mzn', ['-f', '--vsids']),
    'mip2015_unary': ('highs', 'mip2015.mzn', []),
    'mip2015_onehot': ('highs', 'mip2015_onehot.mzn', []),
}


def verify(data, solution, optimal):
    widths, heights = solution['widths'], solution['heights']
    assert len(widths) == data['n'] and len(heights) == data['m']
    assert all(isinstance(v, int) for v in widths + heights)
    assert sum(widths) <= data['budget']
    assert all(a <= w <= b for a, w, b in zip(data['lo'], widths, data['hi']))
    actual = [0] * data['m']
    for d in range(data['cells']):
        choices = [k for k in range(data['first'][d]-1, data['last'][d])
                   if data['sw'][k] <= widths[data['cell_col'][d]-1]]
        assert choices
        row = data['cell_row'][d]-1
        actual[row] = max(actual[row], data['sh'][choices[-1]])
    assert all(a <= h <= cap for a, h, cap in zip(actual, heights, data['row_upper']))
    assert sum(heights) == solution['height']
    if optimal:
        assert sum(actual) == solution['height']
    # The model uses <= budget, exactly as the paper. Fill spare width after
    # solving; this monotone operation cannot increase any row height.
    spare = data['budget'] - sum(widths)
    filled = list(widths)
    while spare:
        active = [j for j in range(data['n']) if filled[j] < data['hi'][j]]
        assert active
        share = max(1, spare // len(active))
        for j in active:
            add = min(share, spare, data['hi'][j] - filled[j])
            filled[j] += add; spare -= add
    solution['filled_widths'] = filled
    return sum(actual)


def run_once(minizinc, method, data_path, timeout_ms):
    solver, model, flags = METHODS[method]
    cmd = [str(minizinc), '-O0', '--solver', solver, '--statistics', '--json-stream',
           '--solver-time-limit', str(timeout_ms), '-p', '1', '-r', '1', *flags,
           str(Path('models') / model), str(data_path)]
    started = time.perf_counter_ns()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_ms/1000 + 10)
        elapsed = time.perf_counter_ns()-started
    except subprocess.TimeoutExpired:
        return {'status': 'process_timeout', 'wall_ns': time.perf_counter_ns()-started}
    result = {'status': 'UNKNOWN', 'wall_ns': elapsed, 'statistics': {}, 'stderr': proc.stderr}
    for line in proc.stdout.splitlines():
        try: item = json.loads(line)
        except ValueError: continue
        if item['type'] == 'statistics': result['statistics'].update(item['statistics'])
        if item['type'] == 'status': result['status'] = item['status']
        if item['type'] == 'solution': result['solution'] = json.loads(item['output']['default'])
        if item['type'] == 'error': result['error'] = item
    if proc.returncode:
        result['status'] = 'ERROR'; result['returncode'] = proc.returncode
    if result['status'] == 'UNKNOWN' and 'solution' in result:
        result['status'] = 'FEASIBLE_NOT_PROVEN'
    return result


def select_cases(tables, cases, count):
    selected = []
    def add(key):
        if key not in selected and len(selected) < count: selected.append(key)
    pareto = [c for c in cases if c['algorithm'] == 'pareto']
    for c in pareto:
        if c['status'] != 'optimal': add((c['sample_index'], c['width']))
    for metric in ['columns', 'rows', 'profile_steps']:
        for t in sorted(tables.values(), key=lambda x: x[metric], reverse=True)[:10]:
            add((t['sample_index'], t['widths'][len(t['widths'])//2]))
    for method in ['pareto', 'astar2011']:
        for c in sorted((c for c in cases if c['algorithm'] == method),
                        key=lambda x: x['solve']['median_ns'], reverse=True)[:20]:
            add((c['sample_index'], c['width']))
    # Fill any remaining slots in stable sample order, avoiding all-fixed cases.
    for t in tables.values():
        if len(t['widths']) > 1: add((t['sample_index'], t['widths'][len(t['widths'])//2]))
    return selected


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native', type=Path, default=Path('docs/benchmark-rust.jsonl'))
    ap.add_argument('--output', type=Path, default=Path('docs/benchmark-external.jsonl'))
    ap.add_argument('--minizinc', type=Path)
    ap.add_argument('--cases', type=int, default=64)
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--timeout-ms', type=int, default=1000)
    args = ap.parse_args()
    minizinc = args.minizinc or Path('.tools/minizinc-path.txt').read_text().strip()
    rows = [json.loads(l) for l in args.native.read_text().splitlines()]
    tables = {r['sample_index']: r for r in rows if r['kind'] == 'table'}
    cases = [r for r in rows if r['kind'] == 'case']
    refs = {(r['sample_index'], r['width']): r['height'] for r in cases
            if r['algorithm'] == 'astar2011' and r['status'] == 'optimal'}
    selection = select_cases(tables, cases, args.cases)
    meta = {'kind': 'environment', 'utc': datetime.now(timezone.utc).isoformat(),
            'minizinc': subprocess.check_output([str(minizinc), '--version'], text=True).strip(),
            'solvers': json.loads(subprocess.check_output([str(minizinc), '--solvers-json'], text=True)),
            'selection': selection, 'repeats': args.repeats, 'warmups': 1,
            'timeout_ms': args.timeout_ms, 'threads': 1, 'seed': 1, 'compiler_optimization': 0,
            'native_sha256': hashlib.sha256(args.native.read_bytes()).hexdigest(),
            'model_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('models').glob('*.mzn')}}
    with args.output.open('w') as out, tempfile.TemporaryDirectory(prefix='table-stretch-') as tmp:
        out.write(json.dumps(meta, ensure_ascii=False)+'\n'); out.flush()
        for pos, (index, width) in enumerate(selection):
            data = dict(tables[index]['model_data']); data['budget'] = width
            data_path = Path(tmp)/'instance.json'; data_path.write_text(json.dumps(data))
            for method in METHODS:
                runs = []
                for repeat in range(args.repeats+1):
                    result = run_once(minizinc, method, data_path, args.timeout_ms)
                    if 'solution' in result:
                        actual = verify(data, result['solution'], result['status'] == 'OPTIMAL_SOLUTION')
                        if (index, width) in refs:
                            assert actual >= refs[index,width], (method,index,width,result)
                            if result['status'] == 'OPTIMAL_SOLUTION': assert actual == refs[index,width]
                    if repeat: runs.append(result)
                record = {'kind':'case', 'sample_index':index, 'width':width, 'algorithm':method,
                          'runs':runs, 'wall_median_ns':statistics.median(r['wall_ns'] for r in runs),
                          'all_optimal':all(r['status']=='OPTIMAL_SOLUTION' for r in runs)}
                out.write(json.dumps(record, ensure_ascii=False)+'\n');out.flush()
                print(f"{pos+1}/{len(selection)} {method} table={index} width={width} "
                      f"statuses={[r['status'] for r in runs]} wall_ms={record['wall_median_ns']/1e6:.2f}",flush=True)


if __name__ == '__main__':
    main()
