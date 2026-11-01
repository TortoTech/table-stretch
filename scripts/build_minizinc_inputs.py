#!/usr/bin/env python3
"""Import a pinned MiniZinc table-layout corpus and verify its size curves."""
import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path

from benchmark_native import ROOT, Worker
from benchmark_unified import canonical, sha, verify

REVISION = '26bcd0a78433025f7b6896a6fa8caf128795760b'
REPOSITORY = 'https://github.com/MiniZinc/minizinc-benchmarks'
SOURCE = ROOT/'tests/fixtures/minizinc-table-layout'
OUTPUT = ROOT/'docs/benchmark-minizinc-inputs.json'


def fetch_sources():
    url = f'https://api.github.com/repos/MiniZinc/minizinc-benchmarks/contents/table-layout?ref={REVISION}'
    entries = json.load(urllib.request.urlopen(url, timeout=30))
    names = sorted(e['name'] for e in entries if e['name'].endswith('.dzn'))
    assert len(names) == 26
    SOURCE.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in [*names, 'TableLayout.mzn', 'LICENSE']:
        remote = name if name == 'LICENSE' else f'table-layout/{name}'
        data = urllib.request.urlopen(
            f'https://raw.githubusercontent.com/MiniZinc/minizinc-benchmarks/{REVISION}/{remote}',
            timeout=30).read()
        (SOURCE/name).write_bytes(data)
        files[name] = dict(path=remote, sha256=hashlib.sha256(data).hexdigest())
    (SOURCE/'source.json').write_text(json.dumps(dict(repository=REPOSITORY,
        revision=REVISION, files=files), indent=2)+'\n')


def parse_dzn(text):
    """Strict parser for this corpus's scalar and ROWS/COLS/CONFIGS array syntax."""
    text = re.sub(r'%[^\n]*', '', text)
    data = {}
    for statement in text.split(';'):
        if not statement.strip():
            continue
        match = re.fullmatch(r'\s*(\w+)\s*=\s*(.*?)\s*', statement, re.S)
        if not match:
            raise ValueError('Unsupported DZN assignment')
        key, value = match.groups()
        if key in data:
            raise ValueError(f'Duplicate field: {key}')
        if re.fullmatch(r'\d+', value):
            data[key] = int(value)
        else:
            array = re.fullmatch(r'array3d\(\s*ROWS\s*,\s*COLS\s*,\s*CONFIGS\s*,\s*\[([\s\d,\-]*)\]\s*\)', value)
            if not array:
                raise ValueError(f'Unsupported DZN value: {key}')
            data[key] = [int(v.strip()) for v in array[1].split(',') if v.strip()]
    if set(data) != {'pixelwidth', 'maxconfig', 'rows', 'cols', 'width', 'height'}:
        raise ValueError('Unexpected DZN fields')
    if min(data[k] for k in ['pixelwidth', 'maxconfig', 'rows', 'cols']) <= 0:
        raise ValueError('Non-positive dimension')
    count = data['rows']*data['cols']*data['maxconfig']
    if len(data['width']) != count or len(data['height']) != count:
        raise ValueError('Incorrect array dimensions')
    return data


def configurations(data, row, col):
    start = (row*data['cols']+col)*data['maxconfig']
    result = []
    for k in range(start, start+data['maxconfig']):
        w, h = data['width'][k], data['height'][k]
        if (w, h) == (-1, -1):
            continue
        if w <= 0 or h <= 0:
            raise ValueError('Invalid configuration or mismatched padding')
        result.append((w, h))
    if not result:
        raise ValueError('Cell has no configurations')
    return result


def convert(data):
    columns = []
    for col in range(data['cols']):
        cells = []
        for row in range(data['rows']):
            steps = []
            best = None
            by_width = {}
            for w, h in configurations(data, row, col):
                by_width[w] = min(h, by_width.get(w, h))
            for w, h in sorted(by_width.items()):
                if best is None or h < best:
                    steps.append(dict(width=w, height=h)); best = h
            cells.append(dict(steps=steps))
        columns.append(dict(min_width=max(c['steps'][0]['width'] for c in cells),
                            max_width=data['pixelwidth'], cells=cells))
    table = dict(width=data['pixelwidth'], reserved_width=0, columns=columns)
    if sum(c['min_width'] for c in columns) > table['width']:
        raise ValueError('Infeasible source instance')
    return table


def verify_original(data, layout):
    """Check returned layout directly against the DZN, independently of conversion."""
    widths = layout['column_widths']
    assert len(widths) == data['cols'] and sum(widths) == data['pixelwidth']
    heights = [max(min(h for w, h in configurations(data, r, c) if w <= widths[c])
                   for c in range(data['cols'])) for r in range(data['rows'])]
    assert layout['row_heights'] == heights
    assert layout['total_height'] == sum(heights)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fetch', action='store_true', help='Download pinned source files')
    ap.add_argument('--timeout-ms', type=int, default=5000)
    args = ap.parse_args()
    if args.fetch:
        fetch_sources()
    source = json.loads((SOURCE/'source.json').read_text())
    assert source['revision'] == REVISION
    inputs, originals = [], []
    for name, entry in sorted(source['files'].items()):
        assert sha(SOURCE/name) == entry['sha256']
        if not name.endswith('.dzn'):
            continue
        data = parse_dzn((SOURCE/name).read_text())
        table = convert(data)
        originals.append(data)
        inputs.append(dict(sample_index=len(inputs), source_file=name,
            source_sha256=entry['sha256'], width=table['width'], table=table,
            input_sha256=hashlib.sha256(canonical(table)).hexdigest(),
            reference_height=None, reference_verified_by=[]))
    assert len(inputs) == 26
    OUTPUT.write_text(json.dumps(inputs, separators=(',', ':'))+'\n')
    subprocess.run(['cargo', 'build', '--locked', '--release', '--example', 'native_worker'], cwd=ROOT, check=True)
    worker = Worker(OUTPUT, args.timeout_ms)
    audit = []
    try:
        for index, (item, data) in enumerate(zip(inputs, originals)):
            attempts, values = [], []
            for method in ['pareto', 'astar2011', 'lcg2015']:
                result = worker.run(index, method)
                attempts.append(dict(method=method, **result))
                if result['status'] == 'optimal':
                    layout = result['layout']
                    verify_original(data, layout)
                    verify(item['table'], layout, layout['total_height'])
                    values.append(layout['total_height'])
                    item['reference_verified_by'].append(method)
            assert len(set(values)) <= 1, (item['source_file'], values)
            if values:
                item['reference_height'] = values[0]
            audit.append(dict(source_file=item['source_file'], attempts=attempts))
            print(item['source_file'], item['reference_height'], item['reference_verified_by'], flush=True)
    finally:
        worker.close()
    OUTPUT.write_text(json.dumps(inputs, separators=(',', ':'))+'\n')
    (ROOT/'docs/minizinc-validation.json').write_text(json.dumps(dict(
        source_revision=REVISION, input_manifest_sha256=sha(OUTPUT),
        reference_timeout_ms=args.timeout_ms, cases=audit), indent=2)+'\n')
    assert all(len(i['reference_verified_by']) >= 2 for i in inputs), 'Unresolved references retained; increase reference time limit'


if __name__ == '__main__':
    main()
