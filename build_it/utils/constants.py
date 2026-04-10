"""
build_it.utils.constants
========================
Project-wide constants shared across all modules.

All values in this module are pure Python primitives (strings, sets, dicts,
``pathlib.Path`` objects) — **no imports from the rest of build_it** — so
any module can import from here without risk of a circular dependency.

Constants
---------
BUILD_TARGET_MAP
    Maps each build-target string value to the relative path inside
    ``build/`` where Flutter writes the compiled artifact.

SUPPORTS_OUTPUT_DIR
    Set of target string values that accept Flutter's ``--output-dir`` flag.

FLAVORIZR_FILE
    Default filename for a standalone flavorizr configuration file.

PUBSPEC_FILE
    Standard Flutter project manifest filename.

CONFIG_FILE
    Filename of the build_it tool configuration file placed at the Flutter
    project root.

REPO_URL
    Canonical URL of the build_it source repository.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict


# ─────────────────────────────────────────────────────────────────────────────
# Build-output paths
# ─────────────────────────────────────────────────────────────────────────────

# Target string values are used here instead of BuildTarget enum members to
# avoid a circular import (enums.py → constants.py → enums.py).
BUILD_TARGET_MAP: Dict[str, str] = {
    "apk":       "app/outputs/flutter-apk",
    "appbundle": "app/outputs/bundle",
    "ios":       "ios/ipa",
    "web":       "web",
    "macos":     "macos/Build/Products/Release",
    "windows":   "windows/x64/runner/Release",
    "linux":     "linux/x64/release/bundle",
}
"""
Mapping of build-target value → default Flutter output sub-directory
(relative to the project root ``build/`` directory).
"""

# ─────────────────────────────────────────────────────────────────────────────
# Targets that support --output-dir
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTS_OUTPUT_DIR: set[str] = {"apk", "appbundle", "ios", "web"}
"""
Set of build-target string values whose ``flutter build`` command accepts
the ``--output-dir`` flag.

Desktop targets (macos, windows, linux) do not support this flag as of
Flutter 3.x; jobs targeting them will have their ``output_dir`` field
ignored during command assembly.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Well-known filenames
# ─────────────────────────────────────────────────────────────────────────────

FLAVORIZR_FILE = Path("flavorizr.yaml")
"""Filename of a standalone flavorizr configuration file."""

PUBSPEC_FILE = Path("pubspec.yaml")
"""Standard Flutter/Dart project manifest filename."""

CONFIG_FILE = Path(".build_it.yaml")
"""
Filename of the build_it tool configuration file.
Placed at the Flutter project root, next to ``pubspec.yaml``.
Can also be embedded in ``pubspec.yaml`` under the ``build_it:`` key.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Project metadata
# ─────────────────────────────────────────────────────────────────────────────

REPO_URL = "https://github.com/dasero197/build_it"
"""Canonical URL of the build_it source repository."""