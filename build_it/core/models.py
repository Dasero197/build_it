"""
build_it.core.models
====================
Pydantic data models shared across the entire build_it package.

All other modules import from here — never the other way around — to keep the
dependency graph acyclic.

Classes
-------
FlavorInfo
    Normalised representation of a single flavor parsed from flavorizr.

DartDefineConfig
    Resolved set of ``--dart-define`` key/value pairs and
    ``--dart-define-from-file`` paths for one build job.

FlavorBuildConfig
    Per-flavor settings read from ``.build_it.yaml``.

GlobalBuildConfig
    Top-level configuration from ``.build_it.yaml``, including per-flavor
    overrides.

BuildJob
    Atomic unit of work: one flavor × one target, with all arguments
    already resolved and ready to be passed to ``flutter build``.

BuildResult
    Outcome of a single completed :class:`BuildJob`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from build_it.core.enums import BuildStatus, BuildTarget


# ─────────────────────────────────────────────────────────────────────────────
# Flavor metadata (from flavorizr)
# ─────────────────────────────────────────────────────────────────────────────

class FlavorInfo(BaseModel):
    """
    Normalised flavor data parsed from any flavorizr syntax version.

    Attributes
    ----------
    name:
        The flavor key as it appears in flavorizr (e.g. ``"apple"``).
    app_name:
        Human-readable application name (``app.name`` in flavorizr v2, or
        the top-level ``name`` key in v1).  ``None`` when not specified.
    android_application_id:
        Android package identifier (``applicationId`` or
        ``applicationIdSuffix``).  ``None`` when not specified.
    ios_bundle_id:
        iOS bundle identifier (``ios.bundleId``).  ``None`` when not
        specified.
    macos_bundle_id:
        macOS bundle identifier (``macos.bundleId``).  ``None`` when not
        specified.
    raw:
        The original, unmodified YAML body for this flavor.  Kept for
        forward-compatibility — future features can inspect it without
        requiring a parser update.
    """

    name: str
    app_name: Optional[str] = None
    android_application_id: Optional[str] = None
    ios_bundle_id: Optional[str] = None
    macos_bundle_id: Optional[str] = None
    raw: dict = Field(
        default_factory=dict,
        description="Original unmodified YAML body — kept for forward-compatibility.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dart-define resolution
# ─────────────────────────────────────────────────────────────────────────────

class DartDefineConfig(BaseModel):
    """
    Resolved dart-define arguments for one build job.

    Produced by :func:`~build_it.core.config.resolve_dart_defines` after
    merging global config, flavor config, and CLI flags.

    Attributes
    ----------
    defines:
        Mapping of ``KEY → value`` pairs passed as ``--dart-define KEY=VALUE``.
    define_files:
        Ordered list of JSON file paths passed as ``--dart-define-from-file``.
        Order is significant: global files come first, then flavor-specific
        files, then CLI-supplied files.
    """

    defines: dict[str, str] = Field(default_factory=dict)
    define_files: list[Path] = Field(default_factory=list)

    def to_cli_args(self) -> list[str]:
        """
        Expand this config into the CLI token list to append to
        ``flutter build``.

        Returns
        -------
        list[str]
            Alternating flag/value pairs, e.g.
            ``["--dart-define", "ENV=prod", "--dart-define-from-file", "cfg.json"]``.
        """
        args: list[str] = []
        for k, v in self.defines.items():
            args += ["--dart-define", f"{k}={v}"]
        for f in self.define_files:
            args += ["--dart-define-from-file", str(f)]
        return args


# ─────────────────────────────────────────────────────────────────────────────
# Per-flavor config (from .build_it.yaml)
# ─────────────────────────────────────────────────────────────────────────────

class FlavorBuildConfig(BaseModel):
    """
    Per-flavor build settings read from ``.build_it.yaml``.

    When a field is ``None`` or empty the value falls back to the
    corresponding global setting in :class:`GlobalBuildConfig`.

    Attributes
    ----------
    targets:
        Targets to build for this flavor.  When ``None``, the global
        ``default_targets`` are used instead.
    dart_defines:
        Flavor-specific ``KEY → value`` dart-defines.  Merged on top of
        global defines (flavor wins on key collision).
    dart_define_files:
        Flavor-specific define files, appended after global files.
    extra_args:
        Additional raw CLI arguments appended after global ``extra_args``.
    entry_point:
        Optional custom Dart entry-point (``--target lib/main_apple.dart``).
        When ``None`` the Flutter default entry-point is used.
    """

    targets: Optional[list[BuildTarget]] = None
    dart_defines: dict[str, str] = Field(default_factory=dict)
    dart_define_files: list[Path] = Field(default_factory=list)
    extra_args: list[str] = Field(default_factory=list)
    entry_point: Optional[Path] = None


# ─────────────────────────────────────────────────────────────────────────────
# Global config (from .build_it.yaml)
# ─────────────────────────────────────────────────────────────────────────────

class GlobalBuildConfig(BaseModel):
    """
    Top-level configuration from ``.build_it.yaml``.

    Attributes
    ----------
    default_targets:
        Targets used for any flavor that does not specify its own.
        Defaults to all available :class:`~build_it.core.enums.BuildTarget`
        values when ``.build_it.yaml`` is absent.
    dart_defines:
        Global ``KEY → value`` dart-defines applied to every job before
        flavor-specific defines are merged in.
    dart_define_files:
        Global define files prepended to every job's file list.
    extra_args:
        Global raw CLI arguments prepended to every job's argument list.
    flavors:
        Per-flavor overrides keyed by flavor name.  Populated from the
        ``flavors:`` block in ``.build_it.yaml``.
    """

    # When no targets are configured we default to all available targets.
    # Individual flavors that do not specify targets will inherit this list.
    default_targets: list[BuildTarget] = Field(
        default_factory=lambda: BuildTarget.to_list()
    )
    dart_defines: dict[str, str] = Field(default_factory=dict)
    dart_define_files: list[Path] = Field(default_factory=list)
    extra_args: list[str] = Field(default_factory=list)
    flavors: dict[str, FlavorBuildConfig] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Build job (one flavor × one target)
# ─────────────────────────────────────────────────────────────────────────────

class BuildJob(BaseModel):
    """
    Atomic unit of work: one flavor compiled for one target.

    The builder resolves and merges all dart-define arguments before
    constructing ``BuildJob`` instances, so this model holds the final,
    ready-to-use CLI arguments — no further merging is needed at execution
    time.

    Attributes
    ----------
    flavor:
        Flavor name passed to ``--flavor``.  ``None`` in no-flavor mode
        (projects without a flavorizr configuration).
    target:
        The :class:`~build_it.core.enums.BuildTarget` to build.
    dart_define:
        Fully resolved dart-define config for this job.
    extra_args:
        Additional raw CLI arguments appended to the ``flutter build`` call.
    entry_point:
        Optional custom Dart entry-point (``--target``).
    """

    flavor: Optional[str]
    target: BuildTarget
    dart_define: DartDefineConfig = Field(default_factory=DartDefineConfig)
    extra_args: list[str] = Field(default_factory=list)
    entry_point: Optional[Path] = None

    @property
    def label(self) -> str:
        """
        Short human-readable identifier for this job.

        Used in log output and the summary table.

        Returns
        -------
        str
            ``"<flavor> / <target>"`` (e.g. ``"apple / apk"``), or
            ``"default / <target>"`` in no-flavor mode.
        """
        f = self.flavor or "default"
        return f"{f} / {self.target.value}"


# ─────────────────────────────────────────────────────────────────────────────
# Build result
# ─────────────────────────────────────────────────────────────────────────────

class BuildResult(BaseModel):
    """
    Outcome of a single completed :class:`BuildJob`.

    Attributes
    ----------
    job:
        The :class:`BuildJob` that produced this result.
    status:
        Terminal :class:`~build_it.core.enums.BuildStatus` of the job.
    duration_seconds:
        Wall-clock time from process start to finish, in seconds.
    output_dir:
        Resolved output directory.  ``None`` when the job was skipped or
        when the target does not support ``--output-dir``.
    error_summary:
        Last meaningful error line extracted from ``stderr``.  ``None`` on
        success or skipped jobs.
    stdout_error:
        Full ``stderr`` text of the failed build (truncated to the last
        1 200 characters for display).  ``None`` on success.
    stdout_output:
        Full ``stdout`` text of the build (truncated).  ``None`` on success.
    """

    job: BuildJob
    status: BuildStatus
    duration_seconds: float = 0.0
    output_dir: Optional[Path] = None
    error_summary: Optional[str] = None
    stdout_error: Optional[str] = None
    stdout_output: Optional[str] = None
