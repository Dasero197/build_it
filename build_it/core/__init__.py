"""
build_it.core
=============
Core business logic of the build_it package.

Modules
-------
enums
    :class:`~build_it.core.enums.BuildTarget`,
    :class:`~build_it.core.enums.BuildStatus`,
    :class:`~build_it.core.enums.BuildType`.
    All enumerations are isolated here to avoid circular imports.

models
    Pydantic data models shared across modules:
    :class:`~build_it.core.models.FlavorInfo`,
    :class:`~build_it.core.models.DartDefineConfig`,
    :class:`~build_it.core.models.FlavorBuildConfig`,
    :class:`~build_it.core.models.GlobalBuildConfig`,
    :class:`~build_it.core.models.BuildJob`,
    :class:`~build_it.core.models.BuildResult`.

parser
    :func:`~build_it.core.parser.load_flavors` — reads flavorizr config
    in all three supported syntaxes (A, B, C) and returns a list of
    :class:`~build_it.core.models.FlavorInfo`.

config
    :func:`~build_it.core.config.load_config`,
    :func:`~build_it.core.config.resolve_dart_defines`,
    :func:`~build_it.core.config.resolve_targets` —
    load and resolve ``.build_it.yaml``.

builder
    :func:`~build_it.core.builder.run_jobs`,
    :func:`~build_it.core.builder.print_summary` —
    execute build jobs sequentially or in parallel.

Dependency order (each module only imports from those above it)
---------------------------------------------------------------
::

    utils.constants  ←  enums  ←  models  ←  parser
                                          ←  config
                                          ←  builder
"""
