"""
build_it.core.builder
=====================
Execute Flutter build jobs asynchronously, with support for both sequential
and parallel execution strategies.

Parallel-safety rules
---------------------
Flutter writes compiled artifacts to ``build/<target>/`` by default.  Two
concurrent jobs targeting the **same** target would write to the same directory
and corrupt each other's output.

build_it avoids this with the following strategy:

Sequential mode (default)
    Jobs run one after the other — always safe, and produces clean,
    interleaved log output.

Parallel mode (``--parallel`` flag)
    * Jobs are grouped by target.
    * Groups execute **concurrently** via ``asyncio.gather``.
    * Jobs **within** the same group run **sequentially** to avoid write
      conflicts inside the shared build directory.
    * Every job receives a unique ``--output-dir build/outputs/<flavor>_<target>/``
      so that artifacts never collide even when two flavors share a target.

After all jobs finish a Rich summary table is printed showing the status,
duration, and resolved output directory of each job.

Public API
----------
run_jobs(jobs, parallel, progress_cb, build_type)
    Main entry point — execute a list of :class:`~build_it.core.models.BuildJob`
    objects and return :class:`~build_it.core.models.BuildResult` objects.

print_summary(results)
    Print a Rich-formatted summary table for a completed build session.

assign_parallel_output_dirs(jobs)
    Inject isolated ``output_dir`` values into every job before parallel
    execution.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from build_it.core.enums import BuildStatus, BuildTarget, BuildType
from build_it.core.models import BuildJob, BuildResult
from build_it.utils.constants import SUPPORTS_OUTPUT_DIR

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────

async def run_jobs(
    jobs: list[BuildJob],
    parallel: bool = False,
    progress_cb: Optional[Callable[[BuildResult], None]] = None,
    build_type: Optional[BuildType] = BuildType.RELEASE,
) -> list[BuildResult]:
    """
    Execute *jobs* and return one :class:`~build_it.core.models.BuildResult`
    per job.

    Parameters
    ----------
    jobs:
        Ordered list of build jobs to execute.
    parallel:
        When ``True``, jobs are grouped by target and groups are executed
        concurrently.  When ``False`` (default) all jobs run sequentially.
    progress_cb:
        Optional callback invoked with each :class:`BuildResult` immediately
        after the corresponding job finishes.  Useful for live progress
        updates in the CLI.
    build_type:
        Flutter build mode (``release``, ``profile`` or ``debug``).
        Defaults to ``release``.

    Returns
    -------
    list[BuildResult]
        Results in the same order as *jobs*, regardless of execution order.
    """
    if parallel:
        return await _run_parallel(jobs, progress_cb, build_type)
    return await _run_sequential(jobs, progress_cb, build_type)


def print_summary(results: list[BuildResult]) -> None:
    """
    Print a Rich-formatted summary table after a build session.

    The table columns are: Flavor · Target · Status · Duration · Output dir.
    A footer line shows the total number of jobs and how many succeeded,
    failed, or were skipped.

    Parameters
    ----------
    results:
        List of :class:`~build_it.core.models.BuildResult` objects returned
        by :func:`run_jobs`.
    """
    table = Table(
        title="Build summary",
        show_header=True,
        header_style="bold",
        border_style="dim",
        show_lines=True,
    )
    table.add_column("Flavor",     style="magenta", no_wrap=True)
    table.add_column("Target",     style="cyan",    no_wrap=True)
    table.add_column("Status",     no_wrap=True)
    table.add_column("Duration",   justify="right", no_wrap=True)
    table.add_column("Output dir", style="dim",     overflow="fold")

    for r in results:
        flavor = r.job.flavor or "—"
        target = r.job.target.value

        if r.status == BuildStatus.SUCCESS:
            status_str = "[green]✓ success[/green]"
        elif r.status == BuildStatus.SKIPPED:
            status_str = "[yellow]⊘ skipped[/yellow]"
        else:
            status_str = "[red]✗ failed[/red]"

        duration = f"{r.duration_seconds:.1f}s"
        out_dir  = str(r.output_dir) if r.output_dir else "—"

        table.add_row(flavor, target, status_str, duration, out_dir)

    console.print()
    console.print(table)

    ok    = sum(1 for r in results if r.status == BuildStatus.SUCCESS)
    fail  = sum(1 for r in results if r.status == BuildStatus.FAILURE)
    skip  = sum(1 for r in results if r.status == BuildStatus.SKIPPED)
    total = len(results)

    parts = [f"[bold]{total}[/bold] jobs"]
    if ok:   parts.append(f"[green]{ok} succeeded[/green]")
    if fail: parts.append(f"[red]{fail} failed[/red]")
    if skip: parts.append(f"[yellow]{skip} skipped[/yellow]")
    console.print("  " + " · ".join(parts))
    console.print()


def assign_parallel_output_dirs(jobs: list[BuildJob]) -> None:
    """
    Inject an isolated ``--output-dir`` path into every job before parallel
    execution.

    Without this, Flutter writes all artifacts of the same target type to the
    same ``build/<target>/`` directory, causing corruption when two jobs run
    concurrently.

    Path scheme: ``build/outputs/<flavor>_<target>/``

    Parameters
    ----------
    jobs:
        List of :class:`~build_it.core.models.BuildJob` to modify in-place.
        Only jobs whose target supports ``--output-dir`` (see
        ``SUPPORTS_OUTPUT_DIR`` in ``utils/constants.py``) will have this
        path injected into the Flutter command; others receive the path but
        it is silently ignored during command assembly.
    """
    for job in jobs:
        slug = f"{job.flavor or 'noflavor'}_{job.target.value}"
        job.output_dir = Path("build") / "outputs" / slug


# ─────────────────────────────────────────────────────────────────────────────
# Sequential runner
# ─────────────────────────────────────────────────────────────────────────────

async def _run_sequential(
    jobs: list[BuildJob],
    progress_cb: Optional[Callable[[BuildResult], None]],
    build_type: Optional[BuildType] = BuildType.RELEASE,
) -> list[BuildResult]:
    """
    Execute *jobs* one after the other in the order given.

    This is the default (and safest) execution strategy.  It produces clean,
    sequential log output and requires no output-directory isolation.
    """
    results = []
    for job in jobs:
        result = await _execute_job(job, build_type)
        results.append(result)
        if progress_cb:
            progress_cb(result)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Parallel runner
# ─────────────────────────────────────────────────────────────────────────────

async def _run_parallel(
    jobs: list[BuildJob],
    progress_cb: Optional[Callable[[BuildResult], None]],
    build_type: Optional[BuildType] = BuildType.RELEASE,
) -> list[BuildResult]:
    """
    Execute *jobs* concurrently, grouped by target.

    Jobs that share the same target run sequentially within their group to
    avoid ``build/`` directory collisions.  Groups for different targets run
    in parallel via ``asyncio.gather``.

    The final result list is re-sorted to match the original job order so
    that the summary table is always deterministic.
    """
    # Assign isolated output dirs before grouping so every job has its own
    # directory, even if two jobs share the same target.
    for job in jobs:
        job.output_dir = _resolve_output_dir(job)

    # Group by target value so same-target jobs always stay sequential
    groups: dict[str, list[BuildJob]] = defaultdict(list)
    for job in jobs:
        groups[job.target.value].append(job)

    all_results: list[BuildResult] = []
    results_lock = asyncio.Lock()

    async def _run_group(group: list[BuildJob]) -> None:
        """Run one target-group sequentially and append results thread-safely."""
        for job in group:
            result = await _execute_job(job, build_type)
            async with results_lock:
                all_results.append(result)
            if progress_cb:
                progress_cb(result)

    await asyncio.gather(*(_run_group(g) for g in groups.values()))

    # Re-sort by original job order for a stable, predictable summary table
    job_index = {id(j): i for i, j in enumerate(jobs)}
    all_results.sort(key=lambda r: job_index.get(id(r.job), 999))
    return all_results


# ─────────────────────────────────────────────────────────────────────────────
# Single job executor
# ─────────────────────────────────────────────────────────────────────────────

async def _execute_job(
    job: BuildJob,
    build_type: Optional[BuildType] = BuildType.RELEASE,
) -> BuildResult:
    """
    Run a single ``flutter build`` subprocess for *job* and return a
    :class:`~build_it.core.models.BuildResult`.

    Handles the following cases:

    * **Platform guard** — iOS and macOS targets are skipped with status
      ``SKIPPED`` on non-macOS hosts.
    * **Success** — process exits with code 0.
    * **Failure** — process exits with a non-zero code; last 1 200 chars of
      stdout/stderr are printed for diagnosis.
    * **Missing flutter** — ``FileNotFoundError`` means the ``flutter``
      binary is not in ``PATH``; a helpful message is printed.

    Parameters
    ----------
    job:
        The build job to execute.
    build_type:
        Flutter build mode flag (``--release``, ``--profile``, ``--debug``).

    Returns
    -------
    BuildResult
        Populated with status, duration, output directory, and any error
        information.
    """
    # ── OS guard for iOS / macOS ──────────────────────────────────────────────
    if job.target in (BuildTarget.IOS, BuildTarget.MACOS) and sys.platform != "darwin":
        console.print(
            f"[yellow]⊘ Skipped {job.label}[/yellow] — "
            f"{job.target.value} builds require macOS (current: {sys.platform})"
        )
        return BuildResult(job=job, status=BuildStatus.SKIPPED)

    cmd = _build_command(job, build_type=build_type)
    console.print(f"  [dim]▶ {job.label}[/dim]  [dim]{' '.join(cmd)}[/dim]")

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        elapsed = time.monotonic() - start

        # The output dir may have been set earlier (parallel mode); recompute
        # here as a fallback for sequential mode.
        out_dir = _resolve_output_dir(job)

        if proc.returncode == 0:
            console.print(
                f"  [green]✓ {job.label}[/green]  "
                f"[dim]{elapsed:.1f}s[/dim]  "
                f"[dim]{out_dir}[/dim]"
            )
            return BuildResult(
                job=job,
                status=BuildStatus.SUCCESS,
                duration_seconds=elapsed,
                output_dir=out_dir,
            )

        # ── Failure ───────────────────────────────────────────────────────────
        console.print(f"  [red]✗ {job.label}[/red]  [dim]{elapsed:.1f}s[/dim]")

        # Display the last 1 200 characters of stdout and stderr for diagnosis
        for stream_label, data in [("stdout", stdout), ("stderr", stderr)]:
            text = data.decode("utf-8", errors="replace").strip()
            if text:
                snippet = text[-1_200:]
                console.print(
                    Panel(snippet, title=stream_label, style="dim red", expand=False)
                )

        error_summary = _extract_error(stderr.decode("utf-8", errors="replace"))
        return BuildResult(
            job=job,
            status=BuildStatus.FAILURE,
            duration_seconds=elapsed,
            error_summary=error_summary,
        )

    except FileNotFoundError:
        console.print(
            "[red]✗ `flutter` not found in PATH.  Is Flutter installed?[/red]"
        )
        return BuildResult(
            job=job,
            status=BuildStatus.FAILURE,
            error_summary="`flutter` binary not found in PATH",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Command assembly
# ─────────────────────────────────────────────────────────────────────────────

def _build_command(
    job: BuildJob,
    build_type: Optional[BuildType] = BuildType.RELEASE,
) -> list[str]:
    """
    Assemble the full ``flutter build …`` command for *job*.

    Parameters
    ----------
    job:
        The build job containing all resolved arguments.
    build_type:
        Flutter build mode.  Translated to ``--release``, ``--profile``,
        or ``--debug``.

    Returns
    -------
    list[str]
        Token list ready to be passed to ``asyncio.create_subprocess_exec``.
    """
    cmd = ["flutter", "build", job.target.flutter_command(), f"--{build_type.value}"]

    if job.flavor:
        cmd += ["--flavor", job.flavor]

    if job.entry_point:
        cmd += ["--target", str(job.entry_point)]

    # Only inject --output-dir for targets that support the flag
    if job.output_dir and job.target.value in SUPPORTS_OUTPUT_DIR:
        cmd += ["--output-dir", str(job.output_dir)]

    # Dart-define arguments (already fully resolved and merged)
    cmd.extend(job.dart_define.to_cli_args())

    # Extra raw arguments from config / CLI
    cmd.extend(job.extra_args)

    return cmd


# ─────────────────────────────────────────────────────────────────────────────
# Output directory resolution
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_output_dir(job: BuildJob) -> Path:
    """
    Return the resolved output directory for *job*.

    If ``job.output_dir`` is already set (parallel mode pre-sets it via
    :func:`assign_parallel_output_dirs`) it is returned as-is.
    Otherwise the standard Flutter build-output path is constructed using
    the target's :meth:`~build_it.core.enums.BuildTarget.output_subdir`.

    Parameters
    ----------
    job:
        The build job to resolve the output directory for.

    Returns
    -------
    Path
        Relative path from the Flutter project root to the output directory.
    """
    if job.output_dir:
        return job.output_dir

    flavor_part = f"/{job.flavor}" if job.flavor else ""
    return Path("build") / job.target.output_subdir() / flavor_part.lstrip("/")


# ─────────────────────────────────────────────────────────────────────────────
# Error extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_error(stderr: str) -> Optional[str]:
    """
    Return the last meaningful error line from Flutter's ``stderr`` output.

    Scans the last 30 non-empty lines of *stderr* in reverse order for a
    line containing a known Flutter error keyword (``Error:``,
    ``Exception:``, ``error:``, ``FAILED``).  Falls back to the very last
    non-empty line if no keyword is found.

    Parameters
    ----------
    stderr:
        Decoded stderr text from the failed ``flutter build`` process.

    Returns
    -------
    str or None
        The most relevant error line, or ``None`` when *stderr* is empty.
    """
    lines = [line for line in stderr.splitlines() if line.strip()]
    for line in reversed(lines[-30:]):
        if any(k in line for k in ("Error:", "Exception:", "error:", "FAILED")):
            return line.strip()
    return lines[-1].strip() if lines else None
