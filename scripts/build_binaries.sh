#!/usr/bin/env bash
# scripts/build_binaries.sh
#
# Build standalone binaries for build_it using PyInstaller.
# Run from the project root: bash scripts/build_binaries.sh
#
# Outputs:
#   dist_bin/build_it              ← Linux / macOS binary
#   dist_bin/build_it.exe          ← Windows binary (cross-compile or run on Windows)
#
# Requirements:
#   pip install pyinstaller  (or pip install -e ".[dev]")

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist_bin"
ENTRY="$PROJECT_ROOT/build_it/cli/main.py"
BINARY_NAME="build_it"

cd "$PROJECT_ROOT"

echo "==> Cleaning previous dist..."
rm -rf "$DIST_DIR" build/ *.spec

echo "==> Building standalone binary with PyInstaller..."
pyinstaller \
    --onefile \
    --name "$BINARY_NAME" \
    --distpath "$DIST_DIR" \
    --hidden-import "build_it.core.models" \
    --hidden-import "build_it.core.parser" \
    --hidden-import "build_it.core.config" \
    --hidden-import "build_it.core.builder" \
    --hidden-import "build_it.cli.main" \
    --hidden-import "build_it.utils.guards" \
    "$ENTRY"

echo ""
echo "==> Binary available at: $DIST_DIR/$BINARY_NAME"
echo "    Size: $(du -sh "$DIST_DIR/$BINARY_NAME" | cut -f1)"
echo ""
echo "Quick test:"
echo "  $DIST_DIR/$BINARY_NAME --version"
