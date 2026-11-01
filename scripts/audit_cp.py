#!/usr/bin/env python3
"""Revisit the six CP timeouts from commit 5d3d36b with a longer deadline."""
import json
from datetime import datetime, timezone
from benchmark_native import ROOT, Worker
from benchmark_unified import sha, verify


def main():
    path = ROOT/'docs/benchmark-unified-inputs.json'
    cases = json.loads(path.read_text())
    worker = Worker(path, 5000)
    results = []
    try:
        for case in [0, 23, 28, 29, 37, 40]:
            item = cases[case]
            for algorithm in ['cp2011', 'lcg2011']:
                result = worker.run(case, algorithm)
                if result['layout'] is not None:
                    verify(item['table'], result['layout'], item['reference_height'])
                results.append(dict(case=case, sample_index=item['sample_index'], width=item['width'],
                                    algorithm=algorithm, reference_height=item['reference_height'],
                                    input_sha256=item['input_sha256'], result=result))
                print(case, algorithm, result['status'], result['wall_ns'], flush=True)
    finally:
        worker.close()
    output = dict(utc=datetime.now(timezone.utc).isoformat(), timeout_ms=5000,
                  purpose='Single-run diagnostic, not a replacement for the 1-second benchmark',
                  input_manifest_sha256=sha(path), worker_sha256=sha(ROOT/'target/release/examples/native_worker'),
                  source_sha256=sha(ROOT/'src/research.rs'), results=results)
    (ROOT/'docs/cp-audit-diagnostics.json').write_text(json.dumps(output, indent=2)+'\n')


if __name__ == '__main__':
    main()
