#!/usr/bin/env python3
"""Frozen validation selection followed by grouped evaluation and ablations."""
import argparse
import json
import math
import platform
import random
import statistics
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ablation_protocol import ROOT, build
from benchmark_native import Worker
from benchmark_memory import measure
from benchmark_unified import canonical, sha, verify

DIRECTORY = ROOT/'docs/ablation'
PROTOCOL = ROOT/'docs/ablation-protocol.json'
SELECTION = DIRECTORY/'selection.json'


def source_hashes():
    paths = [ROOT/'Cargo.toml', ROOT/'Cargo.lock', *sorted((ROOT/'src').glob('*.rs')),
             ROOT/'examples/native_worker.rs', ROOT/'examples/memory_worker.rs',
             ROOT/'scripts/benchmark_ablation.py', ROOT/'scripts/ablation_protocol.py',
             ROOT/'scripts/benchmark_native.py', ROOT/'scripts/benchmark_memory.py', ROOT/'scripts/benchmark_unified.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}


def load_protocol():
    p = json.loads(PROTOCOL.read_text())
    assert p == build(), 'Frozen protocol/input/grouping changed'
    # This commit predates the experiment; the file is not just a mutable promise.
    frozen = subprocess.check_output(['git', 'show', 'a341ad9:docs/ablation-protocol.json'], cwd=ROOT)
    assert frozen == PROTOCOL.read_bytes()
    return p


def read_records(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    return rows[0], rows[1:]


def summarize(records, expected, repeats, timeout_ms):
    assert {r['case'] for r in records} == set(expected) and len(records) == len(expected)
    values, completed = [], 0
    for record in records:
        assert len(record['runs']) == repeats
        runs = record['runs']
        completed += all(r['status'] == 'optimal' for r in runs)
        values.append(statistics.median(r['wall_ns']/1e6 if r['status']=='optimal' else timeout_ms for r in runs))
    return dict(completed=completed, cases=len(records), p50_ms=statistics.median(values),
                p95_ms=sorted(values)[math.ceil(.95*len(values))-1])


def select(protocol):
    assert not SELECTION.exists(), 'Selection already frozen'
    metrics, files, hashes = {}, {}, None
    for methods in protocol['families'].values():
        for method in methods:
            path = DIRECTORY/f'validation-{method}-timing.jsonl'
            env, records = read_records(path)
            assert env['protocol_sha256'] == sha(PROTOCOL)
            assert env['stage'] == 'validation' and env['mode'] == 'timing'
            assert env['source_sha256'] == source_hashes()
            if hashes is None: hashes = env['source_sha256']
            assert hashes == env['source_sha256']
            assert all(r['profile']=='full' for r in records)
            metrics[method] = summarize(records, protocol['validation_cases'], protocol['timing']['repeats'], protocol['timing']['timeout_ms'])
            files[str(path.relative_to(ROOT))] = sha(path)
    chosen = {family:min(methods, key=lambda m:(-metrics[m]['completed'], metrics[m]['p95_ms'], metrics[m]['p50_ms'], m))
              for family, methods in protocol['families'].items()}
    selection = dict(protocol_sha256=sha(PROTOCOL), source_sha256=hashes, validation_raw_sha256=files,
                     selected=chosen, metrics=metrics, utc=datetime.now(timezone.utc).isoformat())
    DIRECTORY.mkdir(exist_ok=True)
    with SELECTION.open('x') as out: json.dump(selection, out, indent=2); out.write('\n')
    print(json.dumps(chosen), flush=True)


def run(stage, mode, protocol):
    if stage == 'validation':
        assert mode == 'timing'
        methods = [m for group in protocol['families'].values() for m in group]
        configs = [(m, 'full', protocol['full_options']) for m in methods]
        case_ids = protocol['validation_cases']
        manifest = ROOT/'docs/benchmark-library-inputs.json'
    else:
        selection = json.loads(SELECTION.read_text())
        assert selection['protocol_sha256'] == sha(PROTOCOL)
        assert selection['source_sha256'] == source_hashes(), 'Code changed after validation selection'
        for name, digest in selection['validation_raw_sha256'].items(): assert sha(ROOT/name) == digest
        methods = list(selection['selected'].values())
        configs = [(m, name, options) for m in methods for name, options in protocol['profiles'][m].items()]
        case_ids = protocol['evaluation_cases'] if stage=='ebooks' else protocol['minizinc_cases']
        manifest = ROOT/('docs/benchmark-library-inputs.json' if stage=='ebooks' else 'docs/benchmark-minizinc-inputs.json')
    assert sha(manifest) == protocol['inputs'][str(manifest.relative_to(ROOT))]
    inputs = json.loads(manifest.read_text())
    settings = protocol['timing' if mode=='timing' else 'memory']
    timeout = protocol['timing']['timeout_ms']
    example = 'native_worker' if mode=='timing' else 'memory_worker'
    subprocess.run(['cargo', 'build', '--locked', '--release', '--example', example], cwd=ROOT, check=True)
    env = dict(kind='environment', stage=stage, mode=mode, utc=datetime.now(timezone.utc).isoformat(),
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        protocol_sha256=sha(PROTOCOL), source_sha256=source_hashes(),
        selection_sha256=sha(SELECTION) if stage!='validation' else None,
        manifest=str(manifest.relative_to(ROOT)), manifest_sha256=sha(manifest),
        case_ids=case_ids, settings=settings, timeout_ms=timeout,
        machine=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
        memory_bytes=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)), platform=platform.platform(),
        rustc=subprocess.check_output(['rustc','-Vv'],text=True),
        worker_sha256=sha(ROOT/f'target/release/examples/{example}'))
    DIRECTORY.mkdir(exist_ok=True)
    paths = {m:DIRECTORY/f'{stage}-{m}-{mode}.jsonl' for m in methods}
    assert not any(p.exists() for p in paths.values()), 'Do not overwrite experiment results'
    outputs = {}
    worker = Worker(manifest, timeout) if mode=='timing' else None
    rng = random.Random(settings['seed'])
    try:
        for m, path in paths.items():
            outputs[m] = path.open('x')
            outputs[m].write(json.dumps({**env, 'algorithm':m, 'profiles':{n:o for method,n,o in configs if method==m}})+'\n')
            outputs[m].flush()
        with tempfile.TemporaryDirectory(prefix='ablation-memory-') as temporary:
            input_path = Path(temporary)/'input.json'
            for pos, index in enumerate(case_ids):
                item = inputs[index]
                if mode=='memory': input_path.write_bytes(canonical(item['table']))
                runs = {(m,n):[] for m,n,_ in configs}
                warmups, ranks = {}, {k:[] for k in runs}
                for repeat in range(settings['warmups']+settings['repeats']):
                    order = list(configs); rng.shuffle(order)
                    for rank, (method, name, options) in enumerate(order):
                        result = worker.run(index, method, options) if worker else measure(input_path, method, timeout, options)
                        if result['layout'] is not None:
                            verify(item['table'], result['layout'], item['reference_height'])
                            assert result['status']=='optimal'
                        if repeat < settings['warmups']: warmups[method,name] = result
                        else: runs[method,name].append(result)
                        ranks[method,name].append(rank)
                for method, name, options in configs:
                    record = dict(kind='case', case=index, input_sha256=item['input_sha256'],
                        algorithm=method, profile=name, options=options, runs=runs[method,name],
                        warmup=warmups.get((method,name)), order_ranks=ranks[method,name])
                    outputs[method].write(json.dumps(record)+'\n'); outputs[method].flush()
                if (pos+1)%50==0 or pos+1==len(case_ids) or stage=='minizinc':
                    failures = sum(any(r['status']!='optimal' for r in series) for series in runs.values())
                    print(f'{stage}/{mode}: {pos+1}/{len(case_ids)} ({failures} incomplete configurations on this case)', flush=True)
    finally:
        if worker: worker.close()
        for out in outputs.values(): out.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['validation','select','ebooks','minizinc'])
    parser.add_argument('--mode', choices=['timing','memory'], default='timing')
    args = parser.parse_args()
    protocol = load_protocol()
    if args.stage == 'select': select(protocol)
    else: run(args.stage, args.mode, protocol)


if __name__ == '__main__': main()
