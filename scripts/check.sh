#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cargo fmt --check
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
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
