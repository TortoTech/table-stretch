# Local-library coverage

The corpus contains **468 real table samples from 31 books** and **1,383 distinct width cases**, replacing the earlier 64-case primary benchmark. All 317 original complete EPUB tables remain present.

| Source | Samples | Books |
| --- | ---: | ---: |
| whole | 317 | 25 |
| rectangular-body | 146 | 14 |
| ruled-pdf | 5 | 2 |

Book counts overlap between source categories. Rectangular bodies are contiguous rows from actual tables, with merged headers, occupied rowspan rows, image cells and irregular rows excluded. They are labeled as derived bodies, not whole-table span support.

Scanned **67 EPUB books** and **2,759 sampled pages across 30 PDF books**. EPUB parsing found 827 table elements and used HTML recovery for 13 documents. PDF detection uses ruled grids, at most 100 evenly spaced pages and three candidates per book. Of six PDF candidates, five passed rendered-page review; one was rejected because outlined typeface names were absent from text extraction. Scanned/image-only and unruled PDF tables are not covered. Two AZW3 books and one CHM were not processed.

Largest dimensions are **150 rows**, **10 columns**, and **592 tokens in one cell** (these maxima may occur in different tables). Source file hashes, EPUB row ranges, and PDF page/bounding-box metadata are retained. Only numeric text metrics are committed, not cell text or page images.

## Case selection and validation

For every sample, container widths are 10%, 35%, and 70% of the interval between its minimum feasible and maximum useful width, rounded down. Repeated widths and identical curve inputs are deduplicated with source aliases retained. All 64 original challenge inputs remain covered; they represent 63 distinct geometries. Selection does not depend on algorithm runtime or success.

**All 1,383 cases have matching Pareto DP and A* reference heights.** Both reference layouts are also checked against an independent greedy wrapper on the original token widths, without consulting the generated staircase curves. Unresolved cases would be retained rather than silently dropped; this run has none. The complete manifest is a Cargo regression test. Extraction tests specifically guard against inherited rowspans and nested-table flattening.

This is a deterministic Unicode-width/word-wrap model with line height 1, not a reproduction of each book's fonts, CSS, forced line breaks, or original PDF geometry. Single-row and single-column tables are excluded. The broader sample mix changes aggregate percentiles; differences from the earlier 64-case table are not algorithm speedups.

## Completed cases by source

All nine implementations use the same one-second full-call limit, one warmup and three measured repetitions. A case completes only if all three repetitions finish; exact returned heights are checked against the references. Subsets below are classified by the retained representative after geometry deduplication.

| Method | Whole EPUB | EPUB bodies | PDF | Retained challenges |
| --- | ---: | ---: | ---: | ---: |
| HTML heuristic | 936/936 | 432/432 | 15/15 | 63/63 |
| **Pareto DP** | 936/936 | 432/432 | 15/15 | 63/63 |
| A* | 936/936 | 432/432 | 15/15 | 63/63 |
| [LCG](https://doi.org/10.1287/ijoc.2014.0637) (2015 cell-free, Pumpkin) | 936/936 | 432/432 | 15/15 | 63/63 |
| [LCG](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 936/936 | 432/432 | 15/15 | 63/63 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (unary, microlp) | 936/936 | 432/432 | 15/15 | 63/63 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (cell-free, microlp) | 936/936 | 432/432 | 15/15 | 63/63 |
| [CP](https://doi.org/10.1145/2034691.2034697) (2011, Pumpkin) | 925/936 | 427/432 | 15/15 | 57/63 |
| [MIP](https://doi.org/10.1287/ijoc.2014.0637) (one-hot, microlp) | 935/936 | 432/432 | 15/15 | 62/63 |

[Timing report](benchmark-native.md) · [Reference checks](library-validation.json) · [Numeric corpus](../tests/fixtures/ebooks-library.json) · [Inputs](benchmark-library-inputs.json) · [PDF visual review](pdf-table-review.json)

## Reproduce

```sh
python3 -m venv .tools/corpus-python
.tools/corpus-python/bin/pip install -r scripts/corpus-requirements.txt
.tools/corpus-python/bin/python scripts/extract_library_tables.py
# Locally inspect candidate PNGs before recording any new PDF approvals.
python3 scripts/merge_reviewed_pdfs.py
python3 scripts/build_library_inputs.py
cargo test --test library_corpus
python3 scripts/benchmark_native.py
python3 scripts/report_native.py
python3 scripts/report_library.py
```

Re-extraction needs the local library; tests and benchmarks run from the committed numeric fixtures. PDF approvals include metric hashes so changed extraction output cannot reuse a stale review.
