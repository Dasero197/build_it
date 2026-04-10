"""
build_it.cli
============
Typer-based command-line interface for build_it.

The entry point registered in ``pyproject.toml`` is:

    [project.scripts]
    build_it = "build_it.cli.main:app"

Modules
-------
main
    The :data:`~build_it.cli.main.app` Typer application with all four
    sub-commands: ``list``, ``build``, ``init``, ``info``.
"""
