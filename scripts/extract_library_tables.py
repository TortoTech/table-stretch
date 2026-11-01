#!/usr/bin/env python3
"""Extract numeric table metrics from EPUBs and ruled PDF tables, read-only.

Requires scripts/corpus-requirements.txt. Whole EPUB tables and contiguous
rectangular bodies are distinguished. PDF candidates require visual approval
before inclusion in the benchmark. No cell text or page images are committed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from extract_epub_tables import metrics, tag


def direct_rows(table):
    for child in table:
        if tag(child) == 'table':
            continue
        if tag(child) == 'tr':
            yield child
        else:
            yield from direct_rows(child)


def rectangular_parts(table):
    """Never include cells occupied by a rowspan from a discarded earlier row."""
    rows = list(direct_rows(table))
    valid, blocked = [], -1
    for i, row in enumerate(rows):
        cells = [c for c in row if tag(c) in {'td', 'th'}]
        inherited = i <= blocked
        for c in cells:
            try:
                span = int(c.get('rowspan', '1'))
            except ValueError:
                span = 0
            if span != 1:
                blocked = max(blocked, len(rows) if span <= 0 else i + span - 1)
        clean = bool(cells) and not inherited and all(
            c.get('colspan', '1') == '1' and c.get('rowspan', '1') == '1'
            and not any(tag(n) in {'table', 'img', 'svg', 'math'} for n in c.iter()) for c in cells)
        valid.append([metrics(c) for c in cells] if clean else None)
    parts, start, current = [], 0, []
    for i, row in enumerate(valid + [None]):
        if row is None or (current and len(row) != len(current[0])):
            if len(current) >= 2 and len(current[0]) >= 2:
                parts.append((start, i, current))
            current = []
        if row is not None:
            if not current:
                start = i
            current.append(row)
    return [(a, b, r, 'whole' if a == 0 and b == len(rows) else 'rectangular-body') for a, b, r in parts]


def text_metric(text):
    cell = ET.Element('td'); cell.text = text
    return metrics(cell)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--library', type=Path, default=Path.home()/'Library/Application Support/com.Rebook.Rebook/library')
    ap.add_argument('--output', type=Path, default=Path('tests/fixtures/ebooks-library.json'))
    ap.add_argument('--pdf-candidates', type=Path, default=Path('.tools/pdf-table-candidates.json'))
    ap.add_argument('--pdf-pages-per-book', type=int, default=100)
    ap.add_argument('--pdf-tables-per-book', type=int, default=3)
    ap.add_argument('--epub-only', action='store_true')
    args = ap.parse_args()
    from lxml import html
    import pdfplumber
    manifest = json.loads((args.library/'library.json').read_text())
    counts, tables, pdfs, failures = Counter(), [], [], []
    for book in manifest['books']:
        path = args.library/'books'/book['storage_name']
        if not path.exists() or path.suffix.lower() not in ('.epub','.pdf'):
            continue
        if args.epub_only and path.suffix.lower() == '.pdf':
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        common = dict(book=book['title'], book_sha256=digest, format=path.suffix[1:])
        if path.suffix.lower() == '.epub':
            counts['epub_books_scanned'] += 1
            with zipfile.ZipFile(path) as archive:
                for name in sorted(archive.namelist()):
                    if Path(name).suffix.lower() not in ('.html','.xhtml','.htm'):
                        continue
                    data = archive.read(name)
                    parser = 'xml'
                    try:
                        root = ET.fromstring(data)
                    except ET.ParseError:
                        parser = 'html-recovery'
                        counts['html_recovered_documents'] += 1
                        try:
                            root = html.fromstring(data)
                        except (ValueError, ET.ParseError):
                            counts['unparsed_documents'] += 1
                            continue
                    for index, table in enumerate(n for n in root.iter() if tag(n) == 'table'):
                        counts['epub_tables_seen'] += 1
                        for start, stop, rows, kind in rectangular_parts(table):
                            if len(rows) > 1000 or len(rows[0]) > 64 or max(len(c['tokens']) for row in rows for c in row) > 5000:
                                counts['oversized_parts'] += 1; continue
                            tables.append(dict(**common, document=name, table_index=index,
                                               source_kind=kind, source_rows=[start, stop], parser=parser, rows=rows))
                            counts['epub_'+kind] += 1
        else:
            counts['pdf_books_scanned'] += 1
            try:
                with pdfplumber.open(path) as pdf:
                    count = len(pdf.pages)
                    # Fixed evenly spaced sample; no selection by solver success.
                    pages = sorted({int(i*(count-1)/max(1,min(count,args.pdf_pages_per_book)-1))
                                    for i in range(min(count,args.pdf_pages_per_book))})
                    selected = 0
                    for number in pages:
                        if selected >= args.pdf_tables_per_book:
                            break
                        page = pdf.pages[number]
                        counts['pdf_pages_scanned'] += 1
                        for index, table in enumerate(page.find_tables({'vertical_strategy':'lines_strict', 'horizontal_strategy':'lines_strict'})):
                            rows = table.extract()
                            if len(rows) < 2 or not 2 <= len(rows[0]) <= 32 or len(rows) > 300:
                                continue
                            if any(len(row) != len(rows[0]) or any(c is None for c in row) for row in rows):
                                counts['pdf_skipped_irregular_or_merged'] += 1; continue
                            cells = [c for row in rows for c in row]
                            if sum(bool(c.strip()) for c in cells)/len(cells) < .6 or max(map(len,cells)) < 8:
                                continue
                            measured = [[text_metric(c) for c in row] for row in rows]
                            if max(len(c['tokens']) for row in measured for c in row) > 5000:
                                continue
                            candidate = dict(**common, document=f'page:{number+1}', page=number+1,
                                             table_index=index, bbox=list(table.bbox), source_kind='ruled-pdf',
                                             rows=measured, visual_review='pending')
                            pdfs.append(candidate); selected += 1
                            counts['pdf_candidates'] += 1
                            # Private local review image, never part of the corpus.
                            image = page.to_image(resolution=100)
                            image.draw_rect(table.bbox, stroke='red', fill=None)
                            image.save(args.pdf_candidates.parent/f'pdf-table-{len(pdfs)-1:03d}.png')
                            if selected >= args.pdf_tables_per_book:
                                break
                        page.close()
            except Exception as e:
                failures.append(dict(book=book['title'], error=type(e).__name__+': '+str(e)))
                counts['pdf_failed_books'] += 1
        print(json.dumps(dict(book=book['title'], tables=len(tables), pdf_candidates=len(pdfs)), ensure_ascii=False), flush=True)
    result = dict(schema=2, measurement='Same Unicode token-width model as extract_epub_tables.py; line height 1; no font/CSS fidelity claim.',
                  scan=dict(counts), failures=failures, tables=tables)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    args.pdf_candidates.write_text(json.dumps(dict(scan=dict(counts),failures=failures,tables=pdfs),ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps(dict(scan=dict(counts),epub_tables=len(tables),pdf_candidates=len(pdfs)),indent=2))


if __name__ == '__main__':
    main()
