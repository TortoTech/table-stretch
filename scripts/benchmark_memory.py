#!/usr/bin/env python3
"""Separate memory pass: fresh macOS process per case/method/repetition."""
import argparse
import hashlib
import json
import os
import platform
import random
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from benchmark_native import ROOT
from benchmark_unified import canonical, run_process, sha, verify


def parse_rss(stderr):
    matches = re.findall(r'^\s*(\d+)\s+maximum resident set size\s*$', stderr, re.M)
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous macOS peak RSS')
    value = int(matches[0])
    if value <= 0:
        raise ValueError('Invalid peak RSS')
    return value


def measure(path, method, timeout_ms):
    raw = run_process(['/usr/bin/time', '-l', str(ROOT/'target/release/examples/memory_worker'),
                       str(path), method, str(timeout_ms)], timeout_ms+2000,
                      env={**os.environ, 'LC_ALL':'C', 'OMP_NUM_THREADS':'1', 'OPENBLAS_NUM_THREADS':'1'})
    if raw['timeout'] or raw['returncode'] != 0:
        return dict(status='timeout' if raw['timeout'] else 'error', layout=None,
                    memory_available=False, error='hard watchdog' if raw['timeout'] else raw['stderr'],
                    process_wall_ns=raw['wall_ns'])
    if len(raw['lines']) != 1:
        raise ValueError('Expected one complete worker response')
    result = json.loads(raw['lines'][0][1])
    result.update(rss_peak_bytes=parse_rss(raw['stderr']), memory_available=True,
                  process_wall_ns=raw['wall_ns'])
    assert result['heap_peak_bytes']-result['heap_baseline_bytes'] == result['heap_extra_peak_bytes'] >= 0
    assert result['heap_end_bytes'] <= result['heap_peak_bytes']
    if result['wall_ns'] > timeout_ms*1_000_000:
        result.update(status='timeout', layout=None)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--suite', choices=['ebooks', 'minizinc'], required=True)
    ap.add_argument('--repeats', type=int, default=3)
    args = ap.parse_args()
    if platform.system() != 'Darwin':
        ap.error('This RSS collector requires macOS /usr/bin/time -l (RSS in bytes).')
    assert args.repeats > 0
    stem = 'benchmark-native' if args.suite == 'ebooks' else 'benchmark-minizinc'
    timing_path = ROOT/f'docs/{stem}-summary.json'
    timing = json.loads(timing_path.read_text())
    selection = timing['selected']
    methods = list(selection.values())
    assert len(methods) == len(set(methods)) == 6
    inputs_path = ROOT/timing['environment']['input_manifest']
    assert sha(inputs_path) == timing['environment']['input_manifest_sha256']
    inputs = json.loads(inputs_path.read_text())
    assert [[i['sample_index'],i['width']] for i in inputs] == timing['environment']['selection']
    # These are the very same implementations as the published timing pass.
    for path, digest in timing['environment']['source_sha256'].items():
        if path.startswith('src/') or path in ('Cargo.toml', 'Cargo.lock'):
            assert sha(ROOT/path) == digest, f'Stale timing implementation: {path}'
    subprocess.run(['cargo','build','--locked','--release','--example','memory_worker'], cwd=ROOT, check=True)
    paths = [ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'src').glob('*.rs')),
             ROOT/'examples/memory_worker.rs',Path(__file__),ROOT/'scripts/benchmark_unified.py']
    env = dict(kind='environment',suite=args.suite,utc=datetime.now(timezone.utc).isoformat(),
        platform=platform.platform(),machine=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
        memory_bytes=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),
        rustc=subprocess.check_output(['rustc','-Vv'],text=True),
        input_manifest=str(inputs_path.relative_to(ROOT)),input_manifest_sha256=sha(inputs_path),
        timing_summary=str(timing_path.relative_to(ROOT)),timing_summary_sha256=sha(timing_path),
        selected=selection,methods=methods,repeats=args.repeats,warmups=0,seed=1,threads=1,
        timeout_ms=timing['environment']['timeout_ms'],
        worker_sha256=sha(ROOT/'target/release/examples/memory_worker'),
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
        heap='peak live requested Rust heap bytes during the library call minus live bytes immediately before it; excludes loaded input, JSON, stack, allocator metadata/caches and realloc internal transient buffers',
        rss='macOS /usr/bin/time -l maximum resident set size, bytes; whole fresh child process including startup, one input, solver, stack, allocator caches, libraries and output',
        state='one new process per case/method/repetition; no warmups or cross-call allocator reuse',
        deadline='same solve wall limit as timing pass, plus two-second process watchdog grace; unfinished runs retain observed memory, not a bound for completed solves',
        timing='instrumented elapsed times are diagnostic only; existing uninstrumented timing results are preserved')
    rng = random.Random(1)
    with tempfile.TemporaryDirectory(prefix='table-memory-') as tmp, (ROOT/f'docs/{stem}-memory.jsonl').open('w') as out:
        out.write(json.dumps(env)+'\n'); out.flush()
        path = Path(tmp)/'input.json'
        for case, item in enumerate(inputs):
            payload = canonical(item['table'])
            assert hashlib.sha256(payload).hexdigest() == item['input_sha256']
            path.write_bytes(payload)
            runs = {m:[] for m in methods}
            orders = []
            for _ in range(args.repeats):
                order = list(methods); rng.shuffle(order); orders.append(order)
                for method in order:
                    result = measure(path, method, env['timeout_ms'])
                    if result['layout'] is not None:
                        verify(item['table'],result['layout'],item['reference_height'])
                        assert (result['status']=='heuristic') == (method=='html')
                    runs[method].append(result)
            for method in methods:
                out.write(json.dumps(dict(kind='case',case=case,sample_index=item['sample_index'],
                    width=item['width'],input_sha256=item['input_sha256'],algorithm=method,
                    runs=runs[method],method_order_by_round=orders))+'\n')
            out.flush()
            if (case+1)%50 == 0 or case+1 == len(inputs) or args.suite == 'minizinc':
                print(f'{args.suite}: {case+1}/{len(inputs)}',flush=True)


if __name__ == '__main__':
    main()
