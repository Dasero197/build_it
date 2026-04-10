"""
build_it.utils.guards
=====================
Pre-flight checks executed before any CLI command that operates on a Flutter
project.

Functions
---------
require_flutter_project(root)
    Abort with a user-friendly error message when the current directory is
    not recognised as a Flutter project.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from build_it.utils.utils import has_flutter_project

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Flutter project guard
# ─────────────────────────────────────────────────────────────────────────────

def require_flutter_project(root: Path = Path(".")) -> None:
    """
    Abort with a friendly error when *root* is not a Flutter project.

    Calls :func:`~build_it.utils.utils.has_flutter_project` and, if the
    check fails, prints a descriptive Rich-formatted error message and exits
    the process with code ``1`` via :exc:`typer.Exit`.

    This guard is intended to be the **first call** inside every CLI command
    that requires a Flutter project context (``build``, ``list``, ``init``).

    Parameters
    ----------
    root:
        Directory to inspect.  Defaults to the current working directory,
        which is the expected working directory when the user runs
        ``build_it`` from the project root.

    Raises
    ------
    typer.Exit
        Always raised (with code ``1``) when the directory is not a valid
        Flutter project.  Normal execution continues if the check passes.

    Examples
    --------
    ::

        @app.command()
        def build_cmd(...) -> None:
            require_flutter_project()   # ← exits immediately if not Flutter
            ...
    """
    if not has_flutter_project(root):
        console.print(
            "[red]✗ Not a Flutter project.[/red]\n"
            "  [dim]build_it must be run from the root of a Flutter project "
            "(a directory containing pubspec.yaml with a flutter dependency).[/dim]"
        )
        raise typer.Exit(1)
