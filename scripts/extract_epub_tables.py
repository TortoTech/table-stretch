#!/usr/bin/env python3
"""Read-only EPUB sampling; write numeric metrics, never whole book contents.

English: whitespace words, gap=1. CJK cells: scalar wrapping, gap=0.
Widths use Unicode East Asian Width (W/F=2), combining marks=0, otherwise 1.
This is a deterministic test measurer, NOT the torto font/CSS layout engine.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import unicodedata
import xml.etree.ElementTree as ET
import zipfile


def tag(node):
    return node.tag.rsplit('}', 1)[-1].lower() if isinstance(node.tag, str) else ''


def width(text):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)


def metrics(cell):
    # Separate block contents, preserve inline element adjacency.
    def content(node):
        parts = [node.text or '']
        for child in node:
            block = tag(child) in {'p', 'div', 'li', 'br'}
            parts += [' ' if block else '', content(child), ' ' if block else '', child.tail or '']
        return ''.join(parts)
    text = ' '.join(content(cell).split())
    cjk = any('\u3400' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff' for c in text)
    if cjk:
        tokens, gap, mode = [width(c) for c in text if width(c)], 0, 'cjk-scalar-wrap'
    else:
        tokens, gap, mode = [width(w) for w in text.split() if width(w)], 1, 'word-wrap'
    return {'tokens': tokens, 'gap': gap, 'mode': mode}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--library', type=Path, default=Path.home() / 'Library/Application Support/com.Rebook.Rebook/library')
    ap.add_argument('--output', type=Path, default=Path('tests/fixtures/ebooks.json'))
    ap.add_argument('--tables', type=int, default=16)
    ap.add_argument('--per-book', type=int, default=2)
    ap.add_argument('--max-columns', type=int, default=8)
    ap.add_argument('--max-rows', type=int, default=60)
    ap.add_argument('--max-tokens', type=int, default=200)
    args = ap.parse_args()
    manifest = json.loads((args.library / 'library.json').read_text())
    counts, selected, skipped = Counter(), [], []
    for book in manifest['books']:
        path = args.library / 'books' / book['storage_name']
        if path.suffix.lower() != '.epub' or not path.exists():
            continue
        counts['epub_books_scanned'] += 1
        picked = 0
        with zipfile.ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if Path(name).suffix.lower() not in {'.html', '.xhtml', '.htm'}:
                    continue
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError:
                    counts['unparsed_documents'] += 1
                    continue
                for index, table in enumerate(n for n in root.iter() if tag(n) == 'table'):
                    counts['tables_seen'] += 1
                    source = {'book': book['title'], 'document': name, 'table_index': index}
                    nodes = list(table.iter())
                    if any(tag(n) == 'table' for n in nodes[1:]):
                        counts['skipped_nested'] += 1
                        continue
                    if any(n.get('colspan', '1') != '1' or n.get('rowspan', '1') != '1' for n in nodes):
                        counts['skipped_spans'] += 1
                        skipped.append({**source, 'reason': 'rowspan/colspan'})
                        continue
                    if any(tag(n) in {'img', 'svg', 'math'} for n in nodes):
                        counts['skipped_nontext'] += 1
                        continue
                    rows = [[metrics(c) for c in row if tag(c) in {'td', 'th'}]
                            for row in nodes if tag(row) == 'tr']
                    rows = [r for r in rows if r]
                    if not rows or not 2 <= len(rows[0]) <= args.max_columns or not 2 <= len(rows) <= args.max_rows:
                        counts['skipped_size'] += 1
                        continue
                    if any(len(r) != len(rows[0]) for r in rows):
                        counts['skipped_ragged'] += 1
                        continue
                    if max(len(c['tokens']) for r in rows for c in r) > args.max_tokens:
                        counts['skipped_long_cells'] += 1
                        continue
                    if (args.per_book and picked >= args.per_book) or (args.tables and len(selected) >= args.tables):
                        counts['eligible_not_sampled'] += 1
                        continue
                    selected.append({
                        'book': book['title'], 'book_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'document': name, 'table_index': index, 'rows': rows,
                    })
                    picked += 1
    result = {'schema': 1, 'measurement': __doc__.strip(), 'scan': dict(counts),
              'filters': {'max_columns': args.max_columns, 'max_rows': args.max_rows, 'max_tokens': args.max_tokens},
              'unsupported': skipped, 'tables': selected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'scan': dict(counts), 'selected': len(selected),
                      'books': sorted({t['book'] for t in selected}),
                      'shapes': [(len(t['rows']), len(t['rows'][0])) for t in selected]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
