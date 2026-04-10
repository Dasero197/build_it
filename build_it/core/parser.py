"""
build_it.core.parser
====================
Parse flavorizr configuration from **all three supported syntaxes**.

flavorizr is a Flutter package that automates app-flavor management.  Over the
years its YAML schema evolved, producing three distinct formats that build_it
must handle transparently:

Syntax A — standalone ``flavorizr.yaml`` (most common, v2+)
────────────────────────────────────────────────────────────
::

    flavors:
      apple:
        app:
          name: "Apple App"
        android:
          applicationId: "com.example.apple"
        ios:
          bundleId: "com.example.apple"

Syntax B — embedded in ``pubspec.yaml`` under the ``flavorizr:`` key
─────────────────────────────────────────────────────────────────────
::

    flavorizr:
      flavors:
        apple:
          app:
            name: "Apple App"
          ...

Syntax C — legacy v1 (flat keys directly under the flavor name)
────────────────────────────────────────────────────────────────
::

    flavors:
      apple:
        name: "Apple App"          # ← no "app:" wrapper
        android:
          applicationId: "com.example.apple"

All three syntaxes resolve to a normalised list of
:class:`~build_it.core.models.FlavorInfo` objects.

Public API
----------
load_flavors(project_root)
    Return all detected flavors.  Returns an empty list when no flavorizr
    config is found — this triggers the *no-flavor mode* in the CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from build_it.core.models import FlavorInfo
from build_it.utils.constants import FLAVORIZR_FILE, PUBSPEC_FILE
from build_it.utils.utils import safe_load_yaml


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_flavors(project_root: Path = Path(".")) -> list[FlavorInfo]:
    """
    Return the list of flavors detected in the Flutter project at *project_root*.

    Lookup order
    ~~~~~~~~~~~~
    1. ``<project_root>/flavorizr.yaml``               → Syntax A or C
    2. ``<project_root>/pubspec.yaml`` key ``flavorizr`` → Syntax B
    3. ``<project_root>/pubspec.yaml`` key ``flavors``   → bare-flavors fallback

    Each location is tried in turn; the first one that yields at least one
    flavor wins and the remaining locations are skipped.

    Parameters
    ----------
    project_root:
        Root directory of the Flutter project.  Defaults to the current
        working directory.

    Returns
    -------
    list[FlavorInfo]
        Ordered list of normalised flavor descriptors.  Returns an empty
        list — **not** an exception — when no flavorizr configuration is
        found.  Callers should interpret an empty list as *no-flavor mode*.
    """
    root = Path(project_root)

    # ── 1. flavorizr.yaml ────────────────────────────────────────────────────
    fz_path = root / FLAVORIZR_FILE
    if fz_path.exists():
        data = safe_load_yaml(fz_path)
        if data:
            flavors = _extract_from_flavorizr_block(data)
            if flavors:
                return flavors

    # ── 2. pubspec.yaml → flavorizr: key ─────────────────────────────────────
    ps_path = root / PUBSPEC_FILE
    if ps_path.exists():
        data = safe_load_yaml(ps_path)
        if data:
            if "flavorizr" in data and isinstance(data["flavorizr"], dict):
                flavors = _extract_from_flavorizr_block(data["flavorizr"])
                if flavors:
                    return flavors

            # ── 3. pubspec.yaml → bare flavors: key (uncommon but valid) ─────
            if "flavors" in data and isinstance(data["flavors"], dict):
                return _parse_flavors_block(data["flavors"])

    return []


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_from_flavorizr_block(data: dict) -> list[FlavorInfo]:
    """
    Extract the flavor list from a dict that may be either:

    * the root mapping of a standalone ``flavorizr.yaml``, or
    * the value of the ``flavorizr:`` key inside ``pubspec.yaml``.

    Both cases expose a ``flavors:`` sub-key whose value is a mapping of
    flavor name → flavor body.

    Parameters
    ----------
    data:
        Parsed YAML mapping to inspect.

    Returns
    -------
    list[FlavorInfo]
        Empty list when the ``flavors`` key is absent or not a dict.
    """
    if "flavors" not in data or not isinstance(data["flavors"], dict):
        return []
    return _parse_flavors_block(data["flavors"])


def _parse_flavors_block(flavors_dict: dict) -> list[FlavorInfo]:
    """
    Normalise a raw ``flavors:`` mapping into a list of :class:`FlavorInfo`.

    Handles Syntax A (``app:`` wrapper), Syntax C (flat keys), and mixed
    blocks where some flavors use one format and others use another.

    Scalar flavor values (e.g. ``apple: null``) are treated as flavors with
    no metadata.

    Parameters
    ----------
    flavors_dict:
        Raw ``{flavor_name: flavor_body}`` mapping from the parsed YAML.

    Returns
    -------
    list[FlavorInfo]
        One :class:`FlavorInfo` per entry in *flavors_dict*.
    """
    result: list[FlavorInfo] = []
    for name, body in flavors_dict.items():
        if not isinstance(body, dict):
            # Scalar value — treat as a flavor with no metadata
            result.append(FlavorInfo(name=str(name), raw={}))
            continue
        result.append(_normalise_flavor(str(name), body))
    return result


def _normalise_flavor(name: str, body: dict) -> FlavorInfo:
    """
    Convert a raw flavor body (any syntax) into a :class:`FlavorInfo`.

    Syntax detection logic
    ~~~~~~~~~~~~~~~~~~~~~~
    * **Syntax A** — ``body["app"]`` is a dict → read ``body["app"]["name"]``.
    * **Syntax C** — ``body["app"]`` is absent or not a dict → read
      ``body["name"]`` directly.

    Parameters
    ----------
    name:
        The flavor key from the YAML mapping (e.g. ``"apple"``).
    body:
        The raw flavor body dict from the parsed YAML.

    Returns
    -------
    FlavorInfo
        Normalised flavor descriptor with all optional fields populated from
        whichever syntax was detected.
    """
    # ── App name ─────────────────────────────────────────────────────────────
    app_name: Optional[str] = None
    app_block = body.get("app")
    if isinstance(app_block, dict):
        app_name = app_block.get("name")          # Syntax A
    else:
        app_name = body.get("name")               # Syntax C

    # ── Android ──────────────────────────────────────────────────────────────
    android = body.get("android") or {}
    # Accept both applicationId (v2) and applicationIdSuffix (legacy suffix-only config)
    android_id: Optional[str] = android.get("applicationId") or android.get(
        "applicationIdSuffix"
    )

    # ── iOS ──────────────────────────────────────────────────────────────────
    ios = body.get("ios") or {}
    ios_bundle: Optional[str] = ios.get("bundleId")

    # ── macOS ─────────────────────────────────────────────────────────────────
    macos = body.get("macos") or {}
    macos_bundle: Optional[str] = macos.get("bundleId")

    return FlavorInfo(
        name=name,
        app_name=app_name,
        android_application_id=android_id,
        ios_bundle_id=ios_bundle,
        macos_bundle_id=macos_bundle,
        raw=body,
    )
