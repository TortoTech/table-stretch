#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cargo fmt --check
cargo test --locked --all-targets
cargo clippy --locked --all-targets -- -D warnings
python3 scripts/test_benchmark_unified.py
python3 scripts/test_benchmark_native.py
python3 scripts/test_extract_library_tables.py
python3 scripts/test_minizinc_inputs.py
if [[ -z "${LEAN_BIN:-}" ]]; then
  if [[ -x .tools/lean-4.19.0-darwin_aarch64/bin/lean ]]; then
    LEAN_BIN="$PWD/.tools/lean-4.19.0-darwin_aarch64/bin/lean"
  else
    LEAN_BIN=lean
  fi
fi
cd proof
"$LEAN_BIN" --version
"$LEAN_BIN" Optimality.lean
