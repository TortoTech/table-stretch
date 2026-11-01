# MiniZinc table-layout corpus

All **26 DZN instances** from the official [MiniZinc benchmark repository](https://github.com/MiniZinc/minizinc-benchmarks/tree/26bcd0a78433025f7b6896a6fa8caf128795760b/table-layout), pinned to commit `26bcd0a78433025f7b6896a6fa8caf128795760b`. No instance is excluded or resized. Tables have 15–174 rows, 3–9 columns, and container widths of 534–1,200 pixels.

The [original files](../tests/fixtures/minizinc-table-layout), upstream model, MIT license, and per-file SHA-256 hashes are preserved. This is a MiniZinc public benchmark; we do not claim it is the complete dataset used by the 2011 or 2015 papers.

## Conversion

Each DZN contains the original container width and row-major arrays of allowed cell width/height configurations. We discard only paired `(-1, -1)` padding entries. For each cell we construct the exact lower envelope:

`height(w) = min(configuration.height where configuration.width <= w)`.

Duplicate widths retain the smallest height; dominated configurations disappear. This preserves the optimum: each cell can independently choose its shortest fitting configuration, and each row must accommodate its tallest cell. A column's minimum width is the largest minimum cell width in that column. After optimization, remaining container space may be added to columns without increasing any height. Original numeric dimensions are retained; there is no OCR, tokenization, or font measurement.

## Validation and timing

Pareto DP and A* independently agree on all **26 optimal heights**. Every reference layout is additionally checked against the original DZN configurations, independently of the converted curves. LCG provides a third check on 23 cases within the 5-second reference budget; its three timeouts remain in the dataset. [Reference audit](minizinc-validation.json).

Tests check padding, array orientation, dominated configurations, and every original curve breakpoint and its preceding width. Rust regression tests rerun Pareto DP and A* on all 26 inputs.

The [benchmark](benchmark-minizinc.md) uses the same native Rust harness as the ebook suite: one warmup and three timed calls per method/case, a 1-second full-call budget, and identical converted input for every method. Reference construction is outside timed runs. Results remain separate from ebook results to expose differences between corpora.

## Reproduce

```sh
# Uses the bundled, hash-checked source files; --fetch refreshes the pinned snapshot.
python3 scripts/build_minizinc_inputs.py
python3 scripts/test_minizinc_inputs.py
cargo test --locked --test minizinc_corpus
python3 scripts/benchmark_native.py --inputs docs/benchmark-minizinc-inputs.json --output docs/benchmark-minizinc.jsonl
python3 scripts/report_native.py --suite minizinc
```

[Converted inputs](benchmark-minizinc-inputs.json) · [Source manifest](../tests/fixtures/minizinc-table-layout/source.json) · [Upstream license](../tests/fixtures/minizinc-table-layout/LICENSE)
