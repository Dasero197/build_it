"""
build_it.cli.main
=================
CLI entry point built with `Typer <https://typer.tiangolo.com/>`_.

Commands
--------
``build_it list``
    List all flavors detected in the current Flutter project and display
    their resolved targets and dart-defines.

``build_it build``
    Build one flavor, a specific set of flavors, or all flavors at once.
    Supports sequential (default) and parallel execution.

``build_it init``
    Generate a starter ``.build_it.yaml`` configuration file pre-populated
    with the detected flavor names.

``build_it info``
    Display project detection status (Flutter project? flavors found?
    ``.build_it.yaml`` present?) and the installed tool version.

Global options
--------------
``--version`` / ``-v``
    Print the installed build_it version and exit.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import time
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from build_it import __version__
from build_it.core.builder import (
    console,
    print_summary,
    run_jobs,
)
from build_it.core.config import (
    generate_default_config,
    load_config,
    resolve_dart_defines,
    resolve_targets,
)
from build_it.core.enums import BuildTarget, BuildType
from build_it.core.models import BuildJob, BuildResult
from build_it.core.parser import load_flavors
from build_it.utils.guards import require_flutter_project
from build_it.utils.utils import has_flutter_project


app = typer.Typer(
    name="build_it",
    help="Flutter multi-flavor build automation CLI.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ─────────────────────────────────────────────────────────────────────────────
# Global callback — version flag
# ─────────────────────────────────────────────────────────────────────────────


def version_callback(value: bool) -> None:
    """Print the installed version and exit when ``--version`` is passed."""
    if value:
        console.print(f"build_it {__version__}")
        raise typer.Exit()


@app.callback()
def version(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """Flutter multi-flavor build automation CLI."""


# ─────────────────────────────────────────────────────────────────────────────
# list
# ─────────────────────────────────────────────────────────────────────────────


@app.command(name="list")
def list_cmd() -> None:
    """
    List all detected flavors and their resolved build configuration.

    Reads flavorizr config (``flavorizr.yaml`` or ``pubspec.yaml``) and
    ``.build_it.yaml`` from the current directory, then prints a Rich table
    showing each flavor together with its resolved targets and dart-defines.

    A global-config summary line is printed below the table.
    """
    require_flutter_project()
    flavors = load_flavors()
    cfg = load_config()

    if not flavors:
        console.print(
            "[yellow]No flavors detected — project will build without --flavor.[/yellow]"
        )
        return

    table = Table(
        title=f"[bold]{len(flavors)} flavor(s) detected[/bold]",
        show_header=True,
        header_style="bold",
        border_style="dim",
        show_lines=True,
    )
    table.add_column("Flavor", style="magenta", no_wrap=True)
    table.add_column("App name", style="cyan")
    table.add_column("Android ID", style="dim")
    table.add_column("Targets", style="green")
    table.add_column("Dart defines (merged)", overflow="fold")

    for fi in flavors:
        flavor_cfg = cfg.flavors.get(fi.name)
        targets = resolve_targets(cfg, flavor_cfg, None)
        dd = resolve_dart_defines(cfg, flavor_cfg, {}, [])

        defines_str = ", ".join(f"{k}={v}" for k, v in dd.defines.items()) or "—"
        if dd.define_files:
            defines_str += (
                "  [dim]+" + ", ".join(f.name for f in dd.define_files) + "[/dim]"
            )

        table.add_row(
            fi.name,
            fi.app_name or "—",
            fi.android_application_id or "—",
            ", ".join(t.value for t in targets),
            defines_str,
        )

    console.print(table)

    # ── Global config summary ─────────────────────────────────────────────────
    console.print()
    g_targets = ", ".join(t.value for t in cfg.default_targets)
    console.print(f"[dim]Global default targets:[/dim] {g_targets}")
    if cfg.dart_define_files:
        console.print(
            "[dim]Global define files:[/dim]  "
            + ", ".join(f.name for f in cfg.dart_define_files)
        )


# ─────────────────────────────────────────────────────────────────────────────
# build
# ─────────────────────────────────────────────────────────────────────────────


@app.command(name="build")
def build_cmd(
    flavor: Annotated[
        Optional[str],
        typer.Option(
            "--flavor", "-f", help="Flavor name to build.  Omit to build all."
        ),
    ] = None,
    target: Annotated[
        Optional[BuildTarget],
        typer.Option(
            "--target", "-t", help="Override build target (apk, appbundle, ios, web…)."
        ),
    ] = None,
    all_flavors: Annotated[
        bool,
        typer.Option("--all", "-a", help="Build all detected flavors."),
    ] = False,
    parallel: Annotated[
        bool,
        typer.Option(
            "--parallel", "-p", help="Run builds in parallel across different targets."
        ),
    ] = False,
    dart_define: Annotated[
        Optional[list[str]],
        typer.Option(
            "--dart-define", "-D", help="Extra KEY=VALUE dart define (repeatable)."
        ),
    ] = None,
    dart_define_file: Annotated[
        Optional[list[Path]],
        typer.Option(
            "--dart-define-from-file",
            "-F",
            help="Extra dart-define JSON file (repeatable).",
        ),
    ] = None,
    build_type: Annotated[
        Optional[BuildType],
        typer.Option(
            "--type", "-T", help="Build mode: release (default), profile, or debug."
        ),
    ] = BuildType.RELEASE,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
    ] = False,
) -> None:
    """
    Build one flavor, all flavors, or a no-flavor project.

    Resolution logic
    ~~~~~~~~~~~~~~~~
    * ``--flavor NAME``  → build only that flavor.
    * ``--all`` or no ``--flavor`` → build all detected flavors.
    * No flavorizr config found → build once without ``--flavor``.

    Dart-define priority (highest → lowest):
    CLI ``--dart-define`` > flavor config > global config.

    Target priority (highest → lowest):
    CLI ``--target`` > flavor ``targets`` > global ``targets``.

    After building, a summary table is printed and the process exits with
    code ``1`` if any job failed.
    """
    require_flutter_project()

    cfg = load_config()
    flavors = load_flavors()
    cli_defines = _parse_cli_defines(dart_define or [])
    cli_files = dart_define_file or []

    # ── Determine which flavors to build ─────────────────────────────────────
    if not flavors:
        # No-flavor mode — build once without --flavor
        flavor_names: list[Optional[str]] = [None]
    elif all_flavors or flavor is None:
        flavor_names = [f.name for f in flavors]
    else:
        if flavor not in {f.name for f in flavors}:
            console.print(f"[red]Unknown flavor '{flavor}'.[/red]")
            console.print("Available: " + ", ".join(f.name for f in flavors))
            raise typer.Exit(1)
        flavor_names = [flavor]

    # ── Assemble build jobs ───────────────────────────────────────────────────
    jobs: list[BuildJob] = []
    for fname in flavor_names:
        flavor_cfg = cfg.flavors.get(fname) if fname else None
        targets = resolve_targets(cfg, flavor_cfg, target)
        dd = resolve_dart_defines(cfg, flavor_cfg, cli_defines, cli_files)

        # Merge extra_args: global first, then flavor-specific on top
        extra = list(cfg.extra_args)
        if flavor_cfg:
            extra.extend(flavor_cfg.extra_args)

        entry = flavor_cfg.entry_point if flavor_cfg else None

        for t in targets:
            jobs.append(
                BuildJob(
                    flavor=fname,
                    target=t,
                    dart_define=dd,
                    extra_args=extra,
                    entry_point=entry,
                )
            )

    if not jobs:
        console.print("[yellow]No build jobs to run.[/yellow]")
        raise typer.Exit()

    # ── Suggest parallel mode when multiple targets are detected ──────────────
    unique_targets = {j.target for j in jobs}
    if not parallel and len(unique_targets) > 1:
        console.print(
            "[dim]Tip: multiple targets detected across flavors. "
            "Use [bold]--parallel[/bold] to build them concurrently.[/dim]"
        )

    # ── Print plan and ask for confirmation ───────────────────────────────────
    _print_job_plan(jobs, parallel)
    if not yes and not Confirm.ask("Proceed?", default=True):
        raise typer.Exit()

    # ── Execute ───────────────────────────────────────────────────────────────
    console.print()
    completed = 0
    total = len(jobs)
    detailled_count = {target: 0 for target in BuildTarget.to_list()}
    build_start = time.monotonic()

    with console.status(
        f"[bold green]Building ({completed}/{total})...[/bold green]", spinner="dots"
    ) as status:

        def on_progress(result: BuildResult):
            nonlocal completed

            detailled_count[result.job.target] += 1
            completed += 1

            targets_status = " | ".join(
                [
                    f"{t.value}: {detailled_count[t]}"
                    for t in [k for k, v in detailled_count.items() if v > 0]
                ]
            )
            display_text = f"[bold green]Building ({completed}/{total})...[/bold green] [dim] {targets_status} [/dim]"
            status.update(display_text)

        results = asyncio.run(
            run_jobs(
                jobs,
                parallel=parallel,
                build_type=build_type,
                progress_cb=on_progress,
            )
        )
    elapsed_time = time.monotonic() - build_start
    print_summary(results, elapsed_time)

    # Exit with code 1 when at least one job failed
    if any(r.status.value == "failure" for r in results):
        raise typer.Exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# init
# ─────────────────────────────────────────────────────────────────────────────


@app.command(name="init")
def init_cmd(
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing .build_it.yaml."),
    ] = False,
) -> None:
    """
    Generate a starter ``.build_it.yaml`` in the current Flutter project.

    Reads the flavorizr configuration (if present) and pre-populates the
    generated file with a section for each detected flavor.  Each section
    contains commented-out fields ready to be filled in.

    Use ``--force`` to overwrite an existing ``.build_it.yaml``.
    """
    require_flutter_project()

    cfg_path = Path(".build_it.yaml")
    if cfg_path.exists() and not force:
        console.print(
            "[yellow].build_it.yaml already exists.  Use --force to overwrite.[/yellow]"
        )
        raise typer.Exit()

    flavors = load_flavors()
    content = generate_default_config([f.name for f in flavors])
    cfg_path.write_text(content, encoding="utf-8")
    console.print(f"[green]✓ Created {cfg_path}[/green]")
    if flavors:
        console.print(
            f"  {len(flavors)} flavor(s) pre-populated: "
            + ", ".join(f.name for f in flavors)
        )
    else:
        console.print("  No flavors detected — no-flavor config generated.")


# ─────────────────────────────────────────────────────────────────────────────
# info
# ─────────────────────────────────────────────────────────────────────────────


@app.command(name="info")
def info_cmd() -> None:
    """
    Show project detection status and the installed build_it version.

    Displays a Rich panel with:

    * Whether the current directory is a Flutter project.
    * How many flavors were detected.
    * Whether a ``.build_it.yaml`` config file is present.
    """
    is_flutter = has_flutter_project()
    flavors = load_flavors() if is_flutter else []
    cfg_exists = Path(".build_it.yaml").exists()

    console.print(
        Panel(
            f"[bold]build_it[/bold] {__version__}\n"
            f"Flutter project:  {'[green]yes[/green]' if is_flutter else '[red]no[/red]'}\n"
            f"Flavors found:    {len(flavors)}\n"
            f".build_it.yaml:   "
            f"{'[green]found[/green]' if cfg_exists else '[yellow]not found[/yellow] — run [bold]build_it init[/bold]'}",
            title="Project info",
            expand=False,
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_cli_defines(raw: list[str]) -> dict[str, str]:
    """
    Parse a list of ``"KEY=VALUE"`` strings from the CLI into a dict.

    Items that do not contain ``=`` are ignored with a warning printed to
    the console.

    Parameters
    ----------
    raw:
        List of raw ``--dart-define`` values from Typer.

    Returns
    -------
    dict[str, str]
        Mapping of define key → value with surrounding whitespace stripped.
    """
    out: dict[str, str] = {}
    for item in raw:
        if "=" in item:
            k, _, v = item.partition("=")
            out[k.strip()] = v.strip()
        else:
            console.print(
                f"[yellow]Warning: ignored malformed --dart-define '{item}' "
                f"(expected KEY=VALUE)[/yellow]"
            )
    return out


def _print_job_plan(jobs: list[BuildJob], parallel: bool) -> None:
    """
    Print a human-readable list of the jobs about to be executed.

    Shows execution mode (sequential / parallel), job labels, and the number
    of dart-defines per job.

    Parameters
    ----------
    jobs:
        Jobs that will be executed.
    parallel:
        Whether jobs will run in parallel mode.
    """
    mode = "[cyan]parallel[/cyan]" if parallel else "[dim]sequential[/dim]"
    console.print(f"\n[bold]{len(jobs)} job(s)[/bold] — {mode}\n")
    for job in jobs:
        dd_count = len(job.dart_define.defines) + len(job.dart_define.define_files)
        suffix = f"  [dim]+{dd_count} dart-define(s)[/dim]" if dd_count else ""
        console.print(f"  • {job.label}{suffix}")
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Invoke the Typer application.  Called by the ``build_it`` script entry point."""
    app()


if __name__ == "__main__":
    main()
