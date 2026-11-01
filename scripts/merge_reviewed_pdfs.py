#!/usr/bin/env python3
"""Include only PDF metrics matching a recorded visual review exactly."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def key(t):
    return (t['book_sha256'],t['document'],t['table_index'],tuple(t['bbox']))


def main():
    path=ROOT/'tests/fixtures/ebooks-library.json'
    corpus=json.loads(path.read_text())
    candidates=json.loads((ROOT/'.tools/pdf-table-candidates.json').read_text())['tables']
    reviews={key(t):t for t in json.loads((ROOT/'docs/pdf-table-review.json').read_text())['candidates']}
    corpus['tables']=[t for t in corpus['tables'] if t['format']!='pdf']
    accepted=0
    for t in candidates:
        review=reviews.get(key(t))
        if review is None or review['decision']!='accept':
            continue
        digest=hashlib.sha256(json.dumps(t['rows'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert digest==review['metrics_sha256'], 'PDF metrics changed since review'
        t['visual_review']='accepted'
        corpus['tables'].append(t);accepted+=1
    corpus['scan']['pdf_visually_accepted']=accepted
    corpus['scan']['pdf_not_included']=len(candidates)-accepted
    path.write_text(json.dumps(corpus,ensure_ascii=False,separators=(',',':'))+'\n')
    print('Corpus tables:',len(corpus['tables']),'PDF accepted:',accepted)


if __name__=='__main__':
    main()
