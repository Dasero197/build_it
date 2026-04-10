"""
build_it.core.enums
===================
All enumerations shared across the build_it package.

Keeping enums in a dedicated module breaks the circular-import chain that
would otherwise occur if they were defined inside ``models.py`` or
``constants.py``.

Classes
-------
BuildTarget
    Supported Flutter build targets (apk, appbundle, ios, web, …).

BuildStatus
    Outcome of a single build job (success, failure, skipped).

BuildType
    Flutter build mode (release, profile, debug).
"""

from __future__ import annotations

from enum import Enum

from build_it.utils.constants import BUILD_TARGET_MAP


# ─────────────────────────────────────────────────────────────────────────────
# Build target
# ─────────────────────────────────────────────────────────────────────────────

class BuildTarget(str, Enum):
    """
    Supported Flutter build targets.

    Each member's string value is the token passed to ``flutter build <target>``
    (with the exception of ``IOS``, which maps to ``flutter build ipa``).

    Examples
    --------
    >>> BuildTarget.APK.flutter_command()
    'apk'
    >>> BuildTarget.IOS.flutter_command()
    'ipa'
    """

    APK        = "apk"
    APPBUNDLE  = "appbundle"
    IOS        = "ios"       # flutter build ipa
    WEB        = "web"
    MACOS      = "macos"
    WINDOWS    = "windows"
    LINUX      = "linux"

    def flutter_command(self) -> str:
        """
        Return the sub-command token passed to ``flutter build <cmd>``.

        For iOS the Flutter CLI expects ``flutter build ipa``, even though
        the enum value is ``"ios"``.
        """
        return "ipa" if self == BuildTarget.IOS else self.value

    def output_subdir(self) -> str:
        """
        Return the relative path inside ``build/`` where Flutter writes the
        compiled artifact for this target.

        The mapping is defined centrally in ``utils/constants.py`` so that
        both the builder and external tooling can import it without touching
        the enum.
        """
        return BUILD_TARGET_MAP.get(self.value, self.value)

    @staticmethod
    def to_list() -> list["BuildTarget"]:
        """Return all ``BuildTarget`` members as an ordered list."""
        return list(BuildTarget._member_map_.values())


# ─────────────────────────────────────────────────────────────────────────────
# Build status
# ─────────────────────────────────────────────────────────────────────────────

class BuildStatus(str, Enum):
    """
    Terminal state of a single :class:`~build_it.core.models.BuildJob`.

    Attributes
    ----------
    SUCCESS:
        The ``flutter build`` command exited with return code 0.
    FAILURE:
        The command exited with a non-zero return code, or an unhandled
        exception occurred during execution.
    SKIPPED:
        The job was intentionally not executed — typically because the
        target requires a platform that is unavailable (e.g. iOS on Linux).
    """

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


# ─────────────────────────────────────────────────────────────────────────────
# Build type (Flutter build mode)
# ─────────────────────────────────────────────────────────────────────────────

class BuildType(str, Enum):
    """
    Flutter build mode, passed as ``--release``, ``--profile``, or ``--debug``.

    Attributes
    ----------
    RELEASE:
        Optimised for distribution.  This is the default.
    PROFILE:
        Enables performance profiling while keeping most release optimisations.
    DEBUG:
        Hot-reload enabled, no optimisation.  Useful for integration testing.
    """

    RELEASE = "release"
    PROFILE = "profile"
    DEBUG   = "debug"
