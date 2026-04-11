"""
build_it.utils
==============
Utility helpers shared across the build_it package.

All modules in this sub-package may be imported from any other module without
risk of circular dependencies — they only import from the Python standard
library or from ``build_it.utils.constants``.

Modules
-------
constants
    Project-wide constants: ``BUILD_TARGET_MAP``,
    ``FLAVORIZR_FILE``, ``PUBSPEC_FILE``, ``CONFIG_FILE``, ``REPO_URL``.
    No intra-package imports — safe as an import root.

utils
    :func:`~build_it.utils.utils.has_flutter_project` — detect whether a
    directory is a valid Flutter project.

    :func:`~build_it.utils.utils.safe_load_yaml` — load a YAML file and
    return ``None`` on any error instead of raising.

guards
    :func:`~build_it.utils.guards.require_flutter_project` — abort the
    current CLI command with a user-friendly message when the current
    directory is not a Flutter project.
"""
