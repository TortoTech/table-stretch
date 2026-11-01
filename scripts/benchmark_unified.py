#!/usr/bin/env python3
"""Uniform fresh-process, curves-to-layout benchmark for every listed method."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import selectors
import signal
import statistics
import subprocess
import tempfile
import time
from compare_solvers import METHODS as EXTERNAL_METHODS

ROOT = Path(__file__).resolve().parents[1]
METHODS = ['pareto', 'astar2011', 'html', 'cp2011_gecode', 'lcg2011_chuffed',
           'lcg2015_cellfree', 'mip2015_unary', 'mip2015_onehot',
           'cp2011_chuffed_seq', 'lcg2011_chuffed_seq', 'lcg2015_rcsv', 'mip2015_cellfree']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(table):
    return json.dumps(table, sort_keys=True, separators=(',', ':')).encode()


def unpack(data, width):
    columns = [{'min_width': a, 'max_width': b, 'cells': [None] * data['m']}
               for a, b in zip(data['lo'], data['hi'])]
    for d in range(data['cells']):
        columns[data['cell_col'][d]-1]['cells'][data['cell_row'][d]-1] = {
            'steps': [{'width': data['sw'][k], 'height': data['sh'][k]}
                      for k in range(data['first'][d]-1, data['last'][d])]}
    assert all(cell is not None for c in columns for cell in c['cells'])
    return {'width': width, 'reserved_width': 0, 'columns': columns}


def make_inputs(native, previous):
    rows = [json.loads(line) for line in native.read_text().splitlines()]
    tables = {r['sample_index']: r for r in rows if r['kind'] == 'table'}
    refs = {(r['sample_index'], r['width']): r['height'] for r in rows
            if r['kind'] == 'case' and r['algorithm'] == 'astar2011' and r['status'] == 'optimal'}
    selection = json.loads(previous.read_text().splitlines()[0])['selection']
    inputs = []
    for index, width in selection:
        t = tables[index]
        table = unpack(t['model_data'], width)
        inputs.append({'sample_index': index, 'width': width, 'book': t['book'],
                       'document': t['document'], 'table_index': t['table_index'],
                       'reference_height': refs[index, width], 'table': table,
                       'input_sha256': hashlib.sha256(canonical(table)).hexdigest()})
    return inputs


def kill_process_tree(proc):
    """Stop live ancestors before enumerating/killing their descendants.

    MiniZinc puts its FlatZinc solver in a separate process group. killpg on
    the worker alone leaks that solver. The worker waits for MiniZinc, so the
    parent links remain available at a timeout. Freeze ancestors while taking
    snapshots so a child cannot keep spawning or reparenting during cleanup.
    Normal completed workers have already waited for all solver processes.
    """
    if proc.poll() is not None:
        return []
    known, stopped = {proc.pid}, set()
    while True:
        for pid in known - stopped:
            try:
                os.kill(pid, signal.SIGSTOP)
            except ProcessLookupError:
                pass
            stopped.add(pid)
        pairs = [tuple(map(int, line.split())) for line in subprocess.check_output(
            ['ps', '-axo', 'pid=,ppid='], text=True).splitlines()]
        found = set(known)
        while True:
            children = {pid for pid, ppid in pairs if ppid in found}
            if children <= found:
                break
            found |= children
        if found <= known:
            break
        known = found
    # Descendants first. Their stopped parents cannot reap/reuse the PIDs.
    for pid in sorted(known - {proc.pid}, reverse=True) + [proc.pid]:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return sorted(known)


def run_process(cmd, timeout_ms, env=None):
    """Time from before spawn through pipe drain + exit. Kill the process tree.

    Retain only complete output lines received by the deadline. Thus a solution
    emitted during watchdog cleanup cannot become a pre-deadline incumbent.
    """
    begin = time.perf_counter_ns()
    deadline = begin + timeout_ms * 1_000_000
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, env=env)
    chunks, lines, stderr = b'', [], bytearray()
    expired = False
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ, 'stdout')
            selector.register(proc.stderr, selectors.EVENT_READ, 'stderr')
            while selector.get_map():
                remaining = (deadline - time.perf_counter_ns()) / 1e9
                if remaining <= 0:
                    expired = True
                    break
                for key, _ in selector.select(remaining):
                    data = os.read(key.fileobj.fileno(), 65536)
                    received = time.perf_counter_ns()
                    if received > deadline:
                        expired = True
                        break
                    if not data:
                        selector.unregister(key.fileobj)
                    elif key.data == 'stderr':
                        stderr.extend(data)
                    else:
                        chunks += data
                        while b'\n' in chunks:
                            line, chunks = chunks.split(b'\n', 1)
                            lines.append((received - begin, line.decode()))
                if expired:
                    break
        if not expired:
            try:
                proc.wait(timeout=max(0, (deadline-time.perf_counter_ns())/1e9))
            except subprocess.TimeoutExpired:
                expired = True
        wall_ns = time.perf_counter_ns() - begin
        expired |= wall_ns > timeout_ms * 1_000_000
    finally:
        cleanup_pids = kill_process_tree(proc)
        proc.communicate(timeout=5)
        proc.stdout.close()
        proc.stderr.close()
    return {'timeout': expired, 'wall_ns': wall_ns,
            'cleanup_ns': time.perf_counter_ns()-begin-wall_ns,
            'cleanup_pids': cleanup_pids,
            'returncode': proc.returncode, 'lines': lines, 'stderr': stderr.decode()}


def verify(table, layout, reference):
    widths = layout['column_widths']
    assert len(widths) == len(table['columns'])
    assert all(type(v) is int for v in widths + layout['row_heights'])
    assert sum(widths) + table['reserved_width'] == table['width']
    actual = [0] * len(table['columns'][0]['cells'])
    for c, w in zip(table['columns'], widths):
        assert c['min_width'] <= w <= c['max_width']
        for r, cell in enumerate(c['cells']):
            steps = [s for s in cell['steps'] if s['width'] <= w]
            assert steps
            actual[r] = max(actual[r], steps[-1]['height'])
    assert actual == layout['row_heights']
    assert sum(actual) == layout['total_height'] >= reference
    if layout['optimal']:
        assert layout['total_height'] == reference


def interpret(raw, instance, method):
    events = [{'received_ns': ns, **json.loads(line)} for ns, line in raw.pop('lines')]
    final = None
    best = None
    for event in events:
        if event['kind'] == 'error':
            raise RuntimeError(f"{method}: {event['message']}")
        if 'layout' in event:
            verify(instance['table'], event['layout'], instance['reference_height'])
            if best is None or event['layout']['total_height'] < best['total_height']:
                best = dict(event['layout'])
        if event['kind'] == 'result':
            assert final is None
            final = event
    if raw['timeout']:
        status = 'timeout'
    else:
        if raw['returncode'] != 0 or final is None:
            raise RuntimeError(f"{method}: missing successful final result: {raw}, {events}")
        status = final['status']
        assert status == ('heuristic' if method == 'html' else 'optimal')
        assert final['layout']['optimal'] == (status == 'optimal')
        best = dict(final['layout'])
    if best is not None:
        best['optimal'] = status == 'optimal'
    reference = instance['reference_height']
    return {**raw, 'status': status, 'layout': best,
            'gap': ((best['total_height']-reference)/reference if reference else 0) if best else None,
            'phases': final.get('phases') if final and status != 'timeout' else None,
            'events': events}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--minizinc', type=Path)
    ap.add_argument('--output', type=Path, default=ROOT/'docs/benchmark-unified.jsonl')
    ap.add_argument('--inputs', type=Path, default=ROOT/'docs/benchmark-unified-inputs.json')
    ap.add_argument('--rebuild-inputs', action='store_true')
    ap.add_argument('--cases', type=int, default=64)
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--timeout-ms', type=int, default=1000)
    ap.add_argument('--baseline-worker', type=Path, help='Optional pre-optimization worker, measured in the same rounds')
    ap.add_argument('--baseline-commit', default='104c545b439f3bbe18b8436f5de029a8bc13b73f')
    args = ap.parse_args()
    assert args.cases > 0 and args.repeats > 0 and args.timeout_ms > 0
    os.chdir(ROOT)
    if args.rebuild_inputs or not args.inputs.exists():
        args.inputs.write_text(json.dumps(make_inputs(ROOT/'docs/benchmark-rust.jsonl',
            ROOT/'docs/benchmark-external.jsonl'), ensure_ascii=False, separators=(',', ':'))+'\n')
    inputs = json.loads(args.inputs.read_text())[:args.cases]
    mini = (args.minizinc or Path(Path('.tools/minizinc-path.txt').read_text().strip())).resolve()
    subprocess.run(['cargo', 'build', '--locked', '--release', '--example', 'unified_worker'], check=True)
    worker = (ROOT/'target/release/examples/unified_worker').resolve()
    methods = list(METHODS)
    baseline = args.baseline_worker.resolve() if args.baseline_worker else None
    if baseline:
        assert baseline.is_file()
        methods.insert(0, 'pareto_baseline')
    env = {**os.environ, 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
           'MKL_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1'}
    source_paths = [Path('Cargo.lock'), Path('Cargo.toml'), *Path('src').glob('*.rs'),
                    Path('examples/unified_worker.rs'), Path(__file__), Path('scripts/compare_solvers.py'),
                    *Path('models').glob('*.mzn')]
    meta = {'kind': 'environment', 'utc': datetime.now(timezone.utc).isoformat(),
            'platform': platform.platform(), 'machine': subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'], text=True).strip(),
            'memory_bytes': int(subprocess.check_output(['sysctl','-n','hw.memsize'], text=True)),
            'rustc': subprocess.check_output(['rustc','-Vv'], text=True),
            'minizinc': subprocess.check_output([str(mini),'--version'], text=True).strip(),
            'solvers': json.loads(subprocess.check_output([str(mini),'--solvers-json'], text=True)),
            'selection': [[r['sample_index'], r['width']] for r in inputs],
            'methods': methods, 'repeats': args.repeats, 'warmups': 1,
            'external_models_and_flags': EXTERNAL_METHODS,
            'baseline': {'commit': args.baseline_commit, 'worker_sha256': sha(baseline)} if baseline else None,
            'timeout_ms': args.timeout_ms, 'threads': 1, 'seed': 1, 'compiler_optimization': 0,
            'native_count_limits': 'disabled', 'deadline_scope': 'before common worker spawn through exit and stdout/stderr drain',
            'profile_construction': 'excluded for every method; identical canonical curve JSON input',
            'fallback': 'common HTML fallback charged to every run, not passed to search; optimized Pareto separately computes its own incumbent within timed preparation',
            'cache': 'fresh processes; one warmup; OS filesystem caches not flushed',
            'timeout_cleanup': 'freeze and kill live worker descendants, including separate solver process groups',
            'input_manifest_sha256': sha(args.inputs), 'worker_sha256': sha(worker),
            'source_sha256': {str(p.relative_to(ROOT) if p.is_absolute() else p): sha(p) for p in source_paths}}
    rng = random.Random(1)
    with args.output.open('w') as out, tempfile.TemporaryDirectory(prefix='table-unified-') as tmp:
        out.write(json.dumps(meta, ensure_ascii=False)+'\n'); out.flush()
        scratch = Path(tmp)
        input_path = scratch/'table.json'
        for pos, instance in enumerate(inputs):
            payload = canonical(instance['table'])
            assert hashlib.sha256(payload).hexdigest() == instance['input_sha256']
            input_path.write_bytes(payload)
            runs = {method: [] for method in methods}
            warmups = {}
            orders = []
            for repeat in range(args.repeats + 1):
                order = list(methods); rng.shuffle(order); orders.append(order)
                for method in order:
                    executable = baseline if method == 'pareto_baseline' else worker
                    worker_method = 'pareto' if method == 'pareto_baseline' else method
                    cmd = [str(executable), worker_method, str(input_path), str(mini), str(ROOT/'models'), str(scratch)]
                    result = interpret(run_process(cmd, args.timeout_ms, env), instance, method)
                    if repeat:
                        runs[method].append(result)
                    else:
                        warmups[method] = result
            for method in methods:
                record = {'kind': 'case', 'sample_index': instance['sample_index'], 'width': instance['width'],
                          'algorithm': method, 'input_sha256': instance['input_sha256'],
                          'reference_height': instance['reference_height'], 'runs': runs[method],
                          'warmup': warmups[method], 'method_order_by_round': orders,
                          'all_optimal': all(r['status'] == 'optimal' for r in runs[method]),
                          'all_completed': all(r['status'] in ('optimal','heuristic') for r in runs[method]),
                          'wall_median_ns': statistics.median(r['wall_ns'] for r in runs[method])}
                out.write(json.dumps(record, ensure_ascii=False)+'\n')
            out.flush()
            statuses = {m: [r['status'] for r in runs[m]] for m in methods if any(r['status']=='timeout' for r in runs[m])}
            print(f"{pos+1}/{len(inputs)} table={instance['sample_index']} width={instance['width']} timeouts={statuses}", flush=True)


if __name__ == '__main__':
    main()
