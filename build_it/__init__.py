"""
build_it — Flutter multi-flavor build automation CLI.
=====================================================

build_it is a standalone Python CLI that reads your ``flavorizr`` configuration
and builds all your Flutter app flavors in a single command — with support for
per-flavor dart-defines, parallel execution, and rich terminal output.

Quick start
-----------
::

    # From the root of your Flutter project
    build_it info            # check project detection
    build_it list            # list flavors and resolved config
    build_it init            # generate .build_it.yaml starter config
    build_it build --all     # build every flavor sequentially
    build_it build --all --parallel   # build across targets in parallel

Package layout
--------------
::

    build_it/
    ├── __init__.py          ← version and author (this file)
    ├── core/
    │   ├── enums.py         ← BuildTarget, BuildStatus, BuildType
    │   ├── models.py        ← Pydantic models: FlavorInfo, BuildJob, …
    │   ├── parser.py        ← flavorizr parser (syntaxes A, B, C)
    │   ├── config.py        ← .build_it.yaml loader and resolver
    │   └── builder.py       ← async runner, parallel/sequential logic
    ├── cli/
    │   └── main.py          ← Typer app: list / build / init / info
    └── utils/
        ├── constants.py     ← project-wide constants (no circular deps)
        ├── utils.py         ← has_flutter_project(), safe_load_yaml()
        └── guards.py        ← require_flutter_project() pre-flight check
"""

__version__ = "0.1.0"
__author__  = "Dayane S. R. Assogba"