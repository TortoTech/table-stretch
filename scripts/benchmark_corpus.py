#!/usr/bin/env python3
"""Sequential isolated release workers. Timings exclude worker startup and I/O."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=Path('tests/fixtures/ebooks-expanded.json'))
    parser.add_argument('--output', type=Path, default=Path('docs/benchmark-expanded.jsonl'))
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--algorithms', choices=['pareto','all'], default='all')
    args = parser.parse_args()
    subprocess.run(['cargo', 'build', '--locked', '--release', '--example', 'benchmark'], check=True)
    corpus = json.loads(args.corpus.read_text())
    binary = Path('target/release/examples/benchmark').resolve()
    metadata = {'kind': 'environment', 'utc': datetime.now(timezone.utc).isoformat(),
                'platform': platform.platform(), 'rustc': command('rustc', '--version'),
                'repeats': args.repeats, 'warmups': 1, 'parallel_workers': 1, 'algorithms': args.algorithms,
                'timeout_seconds_per_table': args.timeout, 'corpus_sha256': hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
                'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'limits': {'max_generated': 1000000, 'max_comparisons': 20000000, 'max_frontier': 10000}}
    if platform.system() == 'Darwin':
        metadata['cpu'] = command('sysctl', '-n', 'machdep.cpu.brand_string')
        metadata['memory_bytes'] = int(command('sysctl', '-n', 'hw.memsize'))
    start = time.monotonic()
    with args.output.open('w') as out:
        out.write(json.dumps(metadata) + '\n'); out.flush()
        for index, table in enumerate(corpus['tables']):
            status, output, stderr = 'completed', b'', b''
            try:
                result = subprocess.run([str(binary), str(args.corpus), str(index), str(args.repeats), args.algorithms],
                                        capture_output=True, timeout=args.timeout)
                output, stderr = result.stdout, result.stderr
                if result.returncode: status = 'worker_error'
            except subprocess.TimeoutExpired as error:
                status, output, stderr = 'timeout', error.stdout or b'', error.stderr or b''
            records = []
            for line in output.splitlines():
                try:
                    record = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue  # incomplete final write is not a completed case
                records.append(record)
                out.write(json.dumps(record, ensure_ascii=False) + '\n')
            out.write(json.dumps({'kind': 'worker', 'sample_index': index, 'status': status,
                                  'stderr': stderr.decode(errors='replace')}, ensure_ascii=False) + '\n')
            out.flush()
            cases = [r for r in records if r['kind'] == 'case']
            failures = sum(r['status'] not in {'optimal', 'heuristic'} for r in cases)
            print(f"{index+1}/{len(corpus['tables'])}: {len(table['rows'])}x{len(table['rows'][0])} "
                  f"cases={len(cases)} limits/errors={failures} worker={status} elapsed={time.monotonic()-start:.1f}s", flush=True)


if __name__ == '__main__':
    main()
