#!/usr/bin/env python3
"""All-Rust, in-process benchmark; one persistent worker, fresh model per call."""
import argparse
import hashlib
import json
import os
import platform
import random
import select
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from benchmark_unified import canonical, sha, verify

ROOT = Path(__file__).resolve().parents[1]
METHODS = ['pareto', 'astar2011', 'html', 'cp2011', 'lcg2011', 'lcg2015',
           'mip2015_unary', 'mip2015_onehot', 'mip2015_cellfree']


class Worker:
    def __init__(self, manifest, timeout_ms):
        self.manifest, self.timeout_ms = manifest, timeout_ms
        self.proc = None
        self.request_id = 0
        self.generation = 0

    def close(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.kill()
            self.proc.wait()
            self.proc.stdin.close()
            self.proc.stdout.close()
            self.proc = None

    def run(self, case, algorithm, options=None):
        if self.proc is None:
            self.proc = subprocess.Popen([str(ROOT/'target/release/examples/native_worker'), str(self.manifest)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=ROOT,
                                         env={**os.environ, 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'})
            self.generation += 1
        self.request_id += 1
        request = dict(id=self.request_id, case=case, algorithm=algorithm, timeout_ms=self.timeout_ms)
        if options is not None:
            request['options'] = options
        try:
            self.proc.stdin.write(json.dumps(request).encode()+b'\n')
            self.proc.stdin.flush()
        except BrokenPipeError:
            self.close()
            return dict(status='error', wall_ns=None, layout=None, phases=None,
                        error='worker closed request pipe', worker_generation=self.generation)
        # Deadline covers the entire response, including a partial JSON line.
        # A readable pipe does not guarantee that readline() would terminate.
        deadline = time.monotonic() + self.timeout_ms/1000 + 2
        line = bytearray()
        while not line.endswith(b'\n'):
            remaining = deadline - time.monotonic()
            ready = select.select([self.proc.stdout], [], [], remaining)[0] if remaining > 0 else []
            if not ready:
                self.close()
                return dict(status='timeout', wall_ns=None, layout=None, phases=None,
                            error='hard watchdog', worker_generation=self.generation)
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                self.close()
                return dict(status='error', wall_ns=None, layout=None, phases=None,
                            error='worker closed response pipe', worker_generation=self.generation)
            line.extend(chunk)
        result = json.loads(line)
        assert result.pop('id') == self.request_id
        result['worker_generation'] = self.generation
        if result['wall_ns'] > self.timeout_ms * 1_000_000:
            # Drop late incumbents/optima; never report them as completed.
            result.update(status='timeout', layout=None, phases=None)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, default=ROOT/'docs/benchmark-library-inputs.json')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/benchmark-native.jsonl')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--timeout-ms', type=int, default=1000)
    parser.add_argument('--cases', type=int, default=0, help='0 means all cases')
    args = parser.parse_args()
    assert args.repeats > 0 and args.timeout_ms > 0 and args.cases >= 0
    subprocess.run(['cargo', 'build', '--locked', '--release', '--example', 'native_worker'], cwd=ROOT, check=True)
    inputs = json.loads(args.inputs.read_text())[:args.cases or None]
    for item in inputs:
        assert hashlib.sha256(canonical(item['table'])).hexdigest() == item['input_sha256']
    paths = [ROOT/'Cargo.toml', ROOT/'Cargo.lock', *sorted((ROOT/'src').glob('*.rs')),
             ROOT/'examples/native_worker.rs', Path(__file__), ROOT/'scripts/benchmark_unified.py']
    meta = dict(kind='environment', utc=datetime.now(timezone.utc).isoformat(),
                platform=platform.platform(), machine=subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip(),
                memory_bytes=int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True)),
                rustc=subprocess.check_output(['rustc', '-Vv'], text=True),
                input_manifest=str(args.inputs.resolve().relative_to(ROOT)), input_manifest_sha256=sha(args.inputs), worker_sha256=sha(ROOT/'target/release/examples/native_worker'),
                source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
                methods=METHODS, repeats=args.repeats, warmups=1, timeout_ms=args.timeout_ms, seed=1, threads=1,
                selection=[[i['sample_index'], i['width']] for i in inputs],
                timing='library call: validation, preparation, model, search, validation/stretch, solver teardown; excludes IPC, parsing and text measurement',
                deadline='same full-call wall budget, cooperative checks plus hard watchdog with 2-second grace; late results discarded',
                state='one serial persistent process; fresh model/solver for each call; no cross-call incumbent or solver reuse',
                native_count_limits='disabled; CP model-construction safety limit retained',
                backends={'CP':'Pumpkin 0.5.0, NoLearningResolver', 'LCG':'Pumpkin 0.5.0, ResolutionResolver (1-UIP)',
                          'MIP':'microlp 0.7.0, pure Rust LP + branch-and-bound, zero MIP gap'})
    worker = Worker(args.inputs, args.timeout_ms)
    rng = random.Random(1)
    try:
        with args.output.open('w') as out:
            out.write(json.dumps(meta)+'\n'); out.flush()
            for pos, instance in enumerate(inputs):
                runs = {m: [] for m in METHODS}
                warmups, orders = {}, []
                for repeat in range(args.repeats + 1):
                    order = list(METHODS); rng.shuffle(order); orders.append(order)
                    for method in order:
                        result = worker.run(pos, method)
                        if result['layout'] is not None:
                            verify(instance['table'], result['layout'], instance['reference_height'])
                            assert (result['status'] == 'heuristic') == (method == 'html')
                        if repeat: runs[method].append(result)
                        else: warmups[method] = result
                for method in METHODS:
                    record = dict(kind='case', case=pos, sample_index=instance['sample_index'], width=instance['width'],
                                  algorithm=method, input_sha256=instance['input_sha256'],
                                  reference_height=instance['reference_height'], runs=runs[method], warmup=warmups[method],
                                  method_order_by_round=orders)
                    out.write(json.dumps(record)+'\n')
                out.flush()
                failures = {m: [r['status'] for r in runs[m]] for m in METHODS if any(r['status'] not in ('optimal','heuristic') for r in runs[m])}
                print(f'{pos+1}/{len(inputs)} {failures}', flush=True)
    finally:
        worker.close()


if __name__ == '__main__':
    main()
