"""
build_it.utils.utils
====================
Shared utility functions used across the build_it package.

Functions
---------
has_flutter_project(project_root)
    Return ``True`` when the given directory is a valid Flutter project.

safe_load_yaml(path)
    Load a YAML file and return its content, or ``None`` on any error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from build_it.utils.constants import PUBSPEC_FILE


# ─────────────────────────────────────────────────────────────────────────────
# Flutter project detection
# ─────────────────────────────────────────────────────────────────────────────

def has_flutter_project(project_root: Path = Path(".")) -> bool:
    """
    Return ``True`` when *project_root* looks like a Flutter project.

    A directory is considered a Flutter project when its ``pubspec.yaml``:

    * exists, **and**
    * declares ``flutter`` in ``dependencies`` or ``dev_dependencies``,
      **or** contains a top-level ``flutter:`` section (for projects that
      configure assets / fonts but don't list flutter as a dependency).

    Parameters
    ----------
    project_root:
        Path to the directory to inspect.  Defaults to the current
        working directory.

    Returns
    -------
    bool
        ``True`` if ``project_root`` is a Flutter project, ``False`` otherwise.
    """
    ps = project_root / PUBSPEC_FILE
    if not ps.exists():
        return False
    data = safe_load_yaml(ps) or {}
    deps = data.get("dependencies", {}) or {}
    dev_deps = data.get("dev_dependencies", {}) or {}
    flutter_in_deps = "flutter" in deps or "flutter" in dev_deps
    has_flutter_section = "flutter" in data
    return flutter_in_deps or has_flutter_section


# ─────────────────────────────────────────────────────────────────────────────
# YAML helpers
# ─────────────────────────────────────────────────────────────────────────────

def safe_load_yaml(path: Path) -> Optional[dict]:
    """
    Load a YAML file and return its parsed content.

    Unlike a bare ``yaml.safe_load`` call, this function catches **all**
    exceptions (``IOError``, ``yaml.YAMLError``, …) and returns ``None``
    so that callers can handle the missing/malformed file gracefully without
    try/except boilerplate.

    Parameters
    ----------
    path:
        Absolute or relative path to the YAML file to read.

    Returns
    -------
    dict or None
        The parsed YAML mapping, or ``None`` if the file could not be
        read or parsed.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None
