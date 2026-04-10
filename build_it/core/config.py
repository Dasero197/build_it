"""
build_it.core.config
====================
Load and resolve the ``.build_it.yaml`` project configuration file.

``.build_it.yaml`` is a build_it-specific file placed at the Flutter project
root, next to ``pubspec.yaml``.  It does **not** modify ``flavorizr.yaml``.
It can also be embedded inside ``pubspec.yaml`` under the ``build_it:`` key.

Configuration schema
--------------------
::

    # .build_it.yaml

    global:
      targets: [apk, appbundle]        # default targets for every flavor
      dart_defines:
        ENV: production
        API_URL: https://api.example.com
      dart_define_files:
        - config/global.json
      extra_args: []

    flavors:
      apple:
        targets: [apk, ios]            # overrides global targets for this flavor
        dart_defines:
          FLAVOR_NAME: apple
        dart_define_files:
          - config/apple.json
        extra_args: ["--release"]
        entry_point: lib/main_apple.dart

      banana:
        # no targets → inherits global.targets
        dart_defines:
          FLAVOR_NAME: banana

Merge rules
-----------
* ``dart_defines`` — merged: global first, flavor-specific on top
  (flavor wins on key collision), CLI on top of both.
* ``dart_define_files`` — concatenated: global → flavor → CLI.
* ``extra_args`` — concatenated: global → flavor.
* ``targets`` — **not** merged: a flavor's ``targets`` fully replaces the
  global default for that flavor.

Public API
----------
load_config(project_root)
    Load and return the :class:`~build_it.core.models.GlobalBuildConfig`.

resolve_dart_defines(global_cfg, flavor_cfg, cli_defines, cli_define_files)
    Merge dart-define arguments according to the priority rules above.

resolve_targets(global_cfg, flavor_cfg, cli_target)
    Return the effective list of targets for a flavor.

generate_default_config(flavor_names)
    Return a YAML string for a starter ``.build_it.yaml``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from build_it.core.models import (
    DartDefineConfig,
    FlavorBuildConfig,
    GlobalBuildConfig,
)
from build_it.core.enums import BuildTarget
from build_it.utils.constants import CONFIG_FILE, PUBSPEC_FILE, REPO_URL


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_config(project_root: Path = Path(".")) -> GlobalBuildConfig:
    """
    Load ``.build_it.yaml`` from *project_root* and return the parsed config.

    Lookup order
    ~~~~~~~~~~~~
    1. ``<project_root>/.build_it.yaml`` (dedicated config file — preferred).
    2. ``<project_root>/pubspec.yaml`` under the ``build_it:`` key (embedded
       config — convenient for smaller projects).

    When neither source is found or both fail to parse, a
    :class:`~build_it.core.models.GlobalBuildConfig` with sensible defaults
    is returned (all targets, no dart-defines).

    Parameters
    ----------
    project_root:
        Root directory of the Flutter project.  Defaults to the current
        working directory.

    Returns
    -------
    GlobalBuildConfig
        Parsed and validated configuration.  Never raises — parsing errors
        are printed as Rich warnings and the default config is used instead.
    """
    raw = None

    main_path = project_root / CONFIG_FILE
    sub_path = project_root / PUBSPEC_FILE

    # ── Primary: .build_it.yaml ───────────────────────────────────────────────
    if main_path.exists():
        try:
            with main_path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except Exception as exc:
            from rich.console import Console
            Console().print(
                f"[yellow]Warning: could not parse .build_it.yaml: {exc}[/yellow]"
            )

    # ── Fallback: pubspec.yaml → build_it: key ───────────────────────────────
    if raw is None and sub_path.exists():
        try:
            with sub_path.open("r", encoding="utf-8") as f:
                result = yaml.safe_load(f)
                raw = result.get("build_it", None) if isinstance(result, dict) else None
        except Exception as exc:
            from rich.console import Console
            Console().print(
                f"[yellow]Warning: could not parse pubspec.yaml: {exc}[/yellow]"
            )

    return _parse_config(raw, project_root) if raw is not None else GlobalBuildConfig(default_targets=[BuildTarget.APK])


def resolve_dart_defines(
    global_cfg: GlobalBuildConfig,
    flavor_cfg: Optional[FlavorBuildConfig],
    cli_defines: dict[str, str],
    cli_define_files: list[Path],
) -> DartDefineConfig:
    """
    Merge dart-define arguments following the priority chain (highest → lowest):

    1. ``--dart-define`` / ``--dart-define-from-file`` flags on the CLI
    2. Flavor-specific ``dart_defines`` / ``dart_define_files`` in ``.build_it.yaml``
    3. Global ``dart_defines`` / ``dart_define_files`` in ``.build_it.yaml``

    For **key/value pairs** the higher-priority source wins on key collision.
    For **files** all sources are concatenated: global → flavor → CLI.

    Parameters
    ----------
    global_cfg:
        Top-level configuration loaded from ``.build_it.yaml``.
    flavor_cfg:
        Per-flavor overrides, or ``None`` in no-flavor mode.
    cli_defines:
        ``KEY → value`` pairs supplied via ``--dart-define`` on the CLI.
    cli_define_files:
        File paths supplied via ``--dart-define-from-file`` on the CLI.

    Returns
    -------
    DartDefineConfig
        Fully merged dart-define configuration ready to be passed to
        :meth:`~build_it.core.models.DartDefineConfig.to_cli_args`.
    """
    merged_defines: dict[str, str] = {}
    merged_defines_files: list[Path] = []

    # 3 — global (lowest priority)
    merged_defines.update(global_cfg.dart_defines)
    merged_defines_files.extend(global_cfg.dart_define_files)

    # 2 — flavor-specific
    if flavor_cfg:
        merged_defines.update(flavor_cfg.dart_defines)
        merged_defines_files.extend(flavor_cfg.dart_define_files)

    # 1 — CLI (highest priority)
    merged_defines.update(cli_defines)
    merged_defines_files.extend(cli_define_files)

    # Normalise keys and values (strip surrounding whitespace)
    merged_defines = {str(k).strip(): str(v).strip() for k, v in merged_defines.items()}

    merged_defines_files = list(dict.fromkeys(merged_defines_files))

    return DartDefineConfig(defines=merged_defines, define_files=merged_defines_files)


def resolve_targets(
    global_cfg: GlobalBuildConfig,
    flavor_cfg: Optional[FlavorBuildConfig],
    cli_target: Optional[BuildTarget],
) -> list[BuildTarget]:
    """
    Return the effective list of build targets for a flavor.

    Priority (highest → lowest):

    1. ``--target`` CLI flag — returns a single-element list, overrides all.
    2. Flavor ``targets`` in ``.build_it.yaml`` — fully replaces the global
       default for this flavor (no merging).
    3. Global ``default_targets`` in ``.build_it.yaml``.

    Parameters
    ----------
    global_cfg:
        Top-level configuration with the global default target list.
    flavor_cfg:
        Per-flavor overrides, or ``None`` in no-flavor mode.
    cli_target:
        Single target supplied via ``--target``, or ``None`` when absent.

    Returns
    -------
    list[BuildTarget]
        Ordered list of targets to build.  Always contains at least one
        element.
    """
    if cli_target is not None:
        return [cli_target]
    if flavor_cfg and flavor_cfg.targets:
        return list(flavor_cfg.targets)
    return list(global_cfg.default_targets)


def generate_default_config(flavor_names: list[str]) -> str:
    """
    Return a YAML string for a starter ``.build_it.yaml`` pre-populated with
    the detected flavor names.

    Used by the ``build_it init`` command.  Each flavor section is generated
    with empty/commented-out fields, ready for the user to fill in.

    Parameters
    ----------
    flavor_names:
        List of flavor names to include.  Can be empty for projects without
        flavors.

    Returns
    -------
    str
        Valid YAML content suitable for writing directly to ``.build_it.yaml``.
    """
    lines = [
        "# .build_it.yaml — build_it configuration",
        f"# See: {REPO_URL}",
        "",
        "global:",
        "  targets: [apk]          # apk | appbundle | ios | web | macos | windows | linux",
        "  dart_defines: {}        # KEY: value",
        "  dart_define_files: []   # - path/to/file.json",
        "  extra_args: []",
        "",
        "flavors:",
    ]
    for name in flavor_names:
        lines += [
            f"  {name}:",
            "    # targets: [apk]        # uncomment to override global targets",
            "    dart_defines: {}",
            "    dart_define_files: []",
            "    extra_args: []",
            f"    # entry_point: lib/main_{name}.dart",
            "",
        ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_config(raw: dict[str, Any], root: Path) -> GlobalBuildConfig:
    """
    Convert a raw YAML mapping into a :class:`GlobalBuildConfig`.

    Parameters
    ----------
    raw:
        Parsed YAML dict (i.e. the full content of ``.build_it.yaml``).
    root:
        Flutter project root, used to resolve relative file paths.

    Returns
    -------
    GlobalBuildConfig
        Fully populated configuration object.
    """
    global_raw = raw.get("global") or {}
    flavors_raw = raw.get("flavors") or {}

    global_cfg = GlobalBuildConfig(
        default_targets=_parse_targets(
            global_raw.get("targets"), default=[BuildTarget.APK]
        ),
        dart_defines=_parse_defines(global_raw.get("dart_defines")),
        dart_define_files=_parse_defines_files(
            global_raw.get("dart_define_files"), root
        ),
        extra_args=_parse_extra_args(global_raw.get("extra_args")),
    )

    for fname, fraw in (flavors_raw or {}).items():
        fraw = fraw or {}
        global_cfg.flavors[fname] = FlavorBuildConfig(
            targets=_parse_targets(fraw.get("targets"), default=[BuildTarget.APK])
            or None,
            dart_defines=_parse_defines(fraw.get("dart_defines")),
            dart_define_files=_parse_defines_files(fraw.get("dart_define_files"), root),
            extra_args=_parse_extra_args(fraw.get("extra_args")),
            entry_point=Path(fraw["entry_point"]) if fraw.get("entry_point") else None,
        )

    return global_cfg


def _parse_targets(
    raw: Any, default: list[BuildTarget] | None = None
) -> list[BuildTarget]:
    """
    Parse a ``targets`` value from YAML into a list of :class:`BuildTarget`.

    * ``raw=None``        → return *default*.
    * ``raw="apk"``       → ``[BuildTarget.APK]``.
    * ``raw=["apk","web"]`` → ``[BuildTarget.APK, BuildTarget.WEB]``.
    * Unknown strings are silently ignored.

    Parameters
    ----------
    raw:
        Raw YAML value for the ``targets`` key.
    default:
        Fallback list returned when *raw* is ``None`` or produces no valid
        targets.

    Returns
    -------
    list[BuildTarget]
    """
    if raw is None or not isinstance(raw, (str, list)):
        return list(default) if default is not None else []

    if isinstance(raw, str):
        raw = [raw]

    result: dict[BuildTarget, None] = {}
    for t in raw:
        try:
            result[BuildTarget(str(t).strip().lower())] = None
        except ValueError:
            pass  # silently skip unknown target strings

    return list(result.keys()) or (list(default) if default is not None else [])


def _parse_defines(raw: Any) -> dict[str, str]:
    """
    Parse a ``dart_defines`` YAML mapping into a ``{str: str}`` dict.

    Returns an empty dict for any non-mapping input (``None``, scalars, lists).

    Parameters
    ----------
    raw:
        Raw YAML value for the ``dart_defines`` key.

    Returns
    -------
    dict[str, str]
    """
    if not isinstance(raw, dict):
        return {}
    return {str(k).strip(): str(v).strip() for k, v in raw.items()}


def _parse_defines_files(raw: Any, root: Path) -> list[Path]:
    """
    Parse a ``dart_define_files`` YAML list into a list of absolute
    :class:`~pathlib.Path` objects resolved against *root*.

    Accepts a bare string (single file) or a list of strings.  Returns an
    empty list for ``None`` or other unexpected types.

    Parameters
    ----------
    raw:
        Raw YAML value for the ``dart_define_files`` key.
    root:
        Flutter project root used to resolve relative paths.

    Returns
    -------
    list[Path]
    """
    if raw is None or not isinstance(raw, (str, list)):
        return []
    if isinstance(raw, str):
        raw = [raw]
    return [root / path for path in dict.fromkeys(str(p).strip() for p in raw if p)]


def _parse_extra_args(raw: Any) -> list[str]:
    """
    Parse an ``extra_args`` YAML list into a list of strings.

    Accepts a bare string (single argument) or a list.  Returns an empty
    list for ``None`` or other unexpected types.

    Parameters
    ----------
    raw:
        Raw YAML value for the ``extra_args`` key.

    Returns
    -------
    list[str]
    """
    if raw is None or not isinstance(raw, (str, list)):
        return []
    if isinstance(raw, str):
        return [raw]
    return list(dict.fromkeys(str(a).strip() for a in raw if a))
