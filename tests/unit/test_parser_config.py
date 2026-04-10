"""
tests.unit.test_parser_config
==============================
Unit tests for:
  - build_it.core.parser  : load_flavors() across all three flavorizr syntaxes
  - build_it.core.config  : load_config(), resolve_dart_defines(), resolve_targets()

These tests never call `flutter` — everything is pure Python.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from build_it.core.config import (
    generate_default_config,
    load_config,
    resolve_dart_defines,
    resolve_targets,
)
from build_it.core.models import BuildTarget, GlobalBuildConfig
from build_it.core.parser import load_flavors
from build_it.utils.utils import has_flutter_project

# ─── Fixture paths ────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent.parent / "fixtures"
SYNTAX_A = FIXTURES / "syntax_a.yaml"
SYNTAX_B = FIXTURES / "syntax_b.yaml"
SYNTAX_C = FIXTURES / "syntax_c.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_flutter_project(tmp: Path, extra_files: dict[str, str] | None = None) -> Path:
    """
    Create a minimal Flutter project directory in *tmp*.

    A valid Flutter project must have pubspec.yaml with a ``flutter``
    dependency.  Extra files (relative path → content) can be added.
    """
    pubspec = tmp / "pubspec.yaml"
    pubspec.write_text(
        "name: test_app\n"
        "dependencies:\n"
        "  flutter:\n"
        "    sdk: flutter\n",
        encoding="utf-8",
    )
    for rel_path, content in (extra_files or {}).items():
        target = tmp / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp


# ─────────────────────────────────────────────────────────────────────────────
# Parser — Syntax A  (standalone flavorizr.yaml, v2+ app: wrapper)
# ─────────────────────────────────────────────────────────────────────────────

class TestParserSyntaxA:
    """Tests against tests/fixtures/syntax_a.yaml."""

    def test_load_returns_all_flavors(self, tmp_path: Path) -> None:
        """Three flavors defined → three FlavorInfo returned."""
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_A.read_text()})
        flavors = load_flavors(tmp_path)
        assert len(flavors) == 3

    def test_flavor_names(self, tmp_path: Path) -> None:
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_A.read_text()})
        names = [f.name for f in load_flavors(tmp_path)]
        assert names == ["apple", "banana", "cherry"]

    def test_app_name_extracted(self, tmp_path: Path) -> None:
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_A.read_text()})
        apple = load_flavors(tmp_path)[0]
        assert apple.app_name == "Apple App"

    def test_android_id_extracted(self, tmp_path: Path) -> None:
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_A.read_text()})
        apple = load_flavors(tmp_path)[0]
        assert apple.android_application_id == "com.example.apple"

    def test_ios_bundle_id_extracted(self, tmp_path: Path) -> None:
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_A.read_text()})
        apple = load_flavors(tmp_path)[0]
        assert apple.ios_bundle_id == "com.example.apple"

    def test_missing_ios_block_is_none(self, tmp_path: Path) -> None:
        """cherry has no ios: block → ios_bundle_id is None."""
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_A.read_text()})
        cherry = load_flavors(tmp_path)[2]
        assert cherry.ios_bundle_id is None

    def test_macos_bundle_id_extracted(self, tmp_path: Path) -> None:
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_A.read_text()})
        apple = load_flavors(tmp_path)[0]
        assert apple.macos_bundle_id == "com.example.apple.macos"


# ─────────────────────────────────────────────────────────────────────────────
# Parser — Syntax B  (flavorizr: embedded in pubspec.yaml)
# ─────────────────────────────────────────────────────────────────────────────

class TestParserSyntaxB:
    """Tests against tests/fixtures/syntax_b.yaml (used as pubspec.yaml)."""

    def test_load_from_pubspec(self, tmp_path: Path) -> None:
        """Flavors embedded under flavorizr: key in pubspec.yaml are detected."""
        shutil.copy(SYNTAX_B, tmp_path / "pubspec.yaml")
        flavors = load_flavors(tmp_path)
        assert len(flavors) == 2
        assert [f.name for f in flavors] == ["apple", "banana"]

    def test_app_name_from_pubspec(self, tmp_path: Path) -> None:
        shutil.copy(SYNTAX_B, tmp_path / "pubspec.yaml")
        apple = load_flavors(tmp_path)[0]
        assert apple.app_name == "Apple App"

    def test_android_id_from_pubspec(self, tmp_path: Path) -> None:
        shutil.copy(SYNTAX_B, tmp_path / "pubspec.yaml")
        banana = load_flavors(tmp_path)[1]
        assert banana.android_application_id == "com.example.banana"


# ─────────────────────────────────────────────────────────────────────────────
# Parser — Syntax C  (legacy v1 flat keys)
# ─────────────────────────────────────────────────────────────────────────────

class TestParserSyntaxC:
    """Tests against tests/fixtures/syntax_c.yaml."""

    def test_load_returns_all_flavors(self, tmp_path: Path) -> None:
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_C.read_text()})
        assert len(load_flavors(tmp_path)) == 3

    def test_flat_name_key(self, tmp_path: Path) -> None:
        """Syntax C uses name: at top level (no app: wrapper)."""
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_C.read_text()})
        apple = load_flavors(tmp_path)[0]
        assert apple.app_name == "Apple App"

    def test_missing_name_is_none(self, tmp_path: Path) -> None:
        """'mixed' flavor has no name key → app_name is None."""
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_C.read_text()})
        mixed = load_flavors(tmp_path)[2]
        assert mixed.app_name is None

    def test_android_id_still_parsed(self, tmp_path: Path) -> None:
        _make_flutter_project(tmp_path, {"flavorizr.yaml": SYNTAX_C.read_text()})
        mixed = load_flavors(tmp_path)[2]
        assert mixed.android_application_id == "com.example.mixed"


# ─────────────────────────────────────────────────────────────────────────────
# Parser — Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestParserEdgeCases:

    def test_no_flavorizr_returns_empty(self, tmp_path: Path) -> None:
        """A Flutter project with no flavorizr config → empty list, no error."""
        _make_flutter_project(tmp_path)
        assert load_flavors(tmp_path) == []

    def test_missing_pubspec_returns_empty(self, tmp_path: Path) -> None:
        """No pubspec.yaml → empty list (not a Flutter project)."""
        assert load_flavors(tmp_path) == []

    def test_has_flutter_project_true(self, tmp_path: Path) -> None:
        _make_flutter_project(tmp_path)
        assert has_flutter_project(tmp_path) is True

    def test_has_flutter_project_false_no_pubspec(self, tmp_path: Path) -> None:
        assert has_flutter_project(tmp_path) is False

    def test_has_flutter_project_false_no_flutter_dep(self, tmp_path: Path) -> None:
        """pubspec.yaml exists but doesn't list flutter → not detected as Flutter project."""
        (tmp_path / "pubspec.yaml").write_text(
            "name: plain_dart\ndependencies:\n  path: ^1.8.0\n", encoding="utf-8"
        )
        assert has_flutter_project(tmp_path) is False


# ─────────────────────────────────────────────────────────────────────────────
# Config — load_config()
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadConfig:

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert isinstance(cfg, GlobalBuildConfig)
        assert cfg.default_targets == [BuildTarget.APK]

    def test_global_targets_parsed(self, tmp_path: Path) -> None:
        content = "global:\n  targets: [apk, web]\n"
        (tmp_path / ".build_it.yaml").write_text(content, encoding="utf-8")
        cfg = load_config(tmp_path)
        assert cfg.default_targets == [BuildTarget.APK, BuildTarget.WEB]

    def test_load_from_pubspec_fallback(self, tmp_path: Path) -> None:
        """Loads configuration from pubspec.yaml if .build_it.yaml is absent."""
        content = (
            "name: test_app\n"
            "build_it:\n"
            "  global:\n"
            "    targets: [ios, web]\n"
        )
        (tmp_path / "pubspec.yaml").write_text(content, encoding="utf-8")
        # Ensure .build_it.yaml does not exist
        assert not (tmp_path / ".build_it.yaml").exists()
        
        cfg = load_config(tmp_path)
        assert cfg.default_targets == [BuildTarget.IOS, BuildTarget.WEB]

    def test_global_dart_defines_parsed(self, tmp_path: Path) -> None:
        content = "global:\n  dart_defines:\n    ENV: production\n    API: https://api.example.com\n"
        (tmp_path / ".build_it.yaml").write_text(content, encoding="utf-8")
        cfg = load_config(tmp_path)
        assert cfg.dart_defines == {"ENV": "production", "API": "https://api.example.com"}

    def test_flavor_override_parsed(self, tmp_path: Path) -> None:
        content = (
            "global:\n  targets: [apk]\n"
            "flavors:\n  apple:\n    targets: [apk, ios]\n    dart_defines:\n      FLAVOR: apple\n"
        )
        (tmp_path / ".build_it.yaml").write_text(content, encoding="utf-8")
        cfg = load_config(tmp_path)
        assert "apple" in cfg.flavors
        assert BuildTarget.IOS in (cfg.flavors["apple"].targets or [])

    def test_unknown_target_silently_skipped(self, tmp_path: Path) -> None:
        """Unknown target strings are ignored, not raised."""
        content = "global:\n  targets: [apk, not_a_target]\n"
        (tmp_path / ".build_it.yaml").write_text(content, encoding="utf-8")
        cfg = load_config(tmp_path)
        assert cfg.default_targets == [BuildTarget.APK]


# ─────────────────────────────────────────────────────────────────────────────
# Config — resolve_dart_defines()  (priority merge)
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveDartDefines:

    def _make_global(self, defines: dict = {}, files: list = []) -> GlobalBuildConfig:
        return GlobalBuildConfig(dart_defines=defines, dart_define_files=files)

    def test_cli_wins_over_global(self) -> None:
        gcfg = self._make_global({"KEY": "global"})
        result = resolve_dart_defines(gcfg, None, {"KEY": "cli"}, [])
        assert result.defines["KEY"] == "cli"

    def test_flavor_wins_over_global(self, tmp_path: Path) -> None:
        from build_it.core.models import FlavorBuildConfig
        gcfg = self._make_global({"KEY": "global"})
        fcfg = FlavorBuildConfig(dart_defines={"KEY": "flavor"})
        result = resolve_dart_defines(gcfg, fcfg, {}, [])
        assert result.defines["KEY"] == "flavor"

    def test_cli_wins_over_flavor(self, tmp_path: Path) -> None:
        from build_it.core.models import FlavorBuildConfig
        gcfg = self._make_global({"KEY": "global"})
        fcfg = FlavorBuildConfig(dart_defines={"KEY": "flavor"})
        result = resolve_dart_defines(gcfg, fcfg, {"KEY": "cli"}, [])
        assert result.defines["KEY"] == "cli"

    def test_merge_keeps_non_overlapping_keys(self) -> None:
        gcfg = self._make_global({"GLOBAL_KEY": "g_val"})
        result = resolve_dart_defines(gcfg, None, {"CLI_KEY": "c_val"}, [])
        assert result.defines == {"GLOBAL_KEY": "g_val", "CLI_KEY": "c_val"}

    def test_files_concatenated_in_order(self, tmp_path: Path) -> None:
        from build_it.core.models import FlavorBuildConfig
        g_file = tmp_path / "global.json"
        f_file = tmp_path / "flavor.json"
        c_file = tmp_path / "cli.json"
        gcfg   = self._make_global(files=[g_file])
        fcfg   = FlavorBuildConfig(dart_define_files=[f_file])
        result = resolve_dart_defines(gcfg, fcfg, {}, [c_file])
        assert result.define_files == [g_file, f_file, c_file]


# ─────────────────────────────────────────────────────────────────────────────
# Config — resolve_targets()
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveTargets:

    def _make_global(self, targets: list[BuildTarget] = None) -> GlobalBuildConfig:
        return GlobalBuildConfig(default_targets=targets or [BuildTarget.APK])

    def test_cli_target_overrides_all(self) -> None:
        from build_it.core.models import FlavorBuildConfig
        gcfg = self._make_global([BuildTarget.APK])
        fcfg = FlavorBuildConfig(targets=[BuildTarget.APPBUNDLE])
        result = resolve_targets(gcfg, fcfg, BuildTarget.WEB)
        assert result == [BuildTarget.WEB]

    def test_flavor_target_overrides_global(self) -> None:
        from build_it.core.models import FlavorBuildConfig
        gcfg = self._make_global([BuildTarget.APK])
        fcfg = FlavorBuildConfig(targets=[BuildTarget.APPBUNDLE, BuildTarget.IOS])
        result = resolve_targets(gcfg, fcfg, None)
        assert result == [BuildTarget.APPBUNDLE, BuildTarget.IOS]

    def test_global_default_when_no_flavor(self) -> None:
        gcfg = self._make_global([BuildTarget.APK, BuildTarget.WEB])
        result = resolve_targets(gcfg, None, None)
        assert result == [BuildTarget.APK, BuildTarget.WEB]


# ─────────────────────────────────────────────────────────────────────────────
# Config — generate_default_config()
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateDefaultConfig:

    def test_output_is_valid_yaml(self) -> None:
        content = generate_default_config(["apple", "banana"])
        parsed = yaml.safe_load(content)
        assert parsed is not None

    def test_all_flavors_present(self) -> None:
        content = generate_default_config(["apple", "banana", "cherry"])
        assert "apple" in content
        assert "banana" in content
        assert "cherry" in content

    def test_global_section_present(self) -> None:
        content = generate_default_config([])
        assert "global:" in content

    def test_empty_flavors_list(self) -> None:
        """Should not raise when there are no flavors."""
        content = generate_default_config([])
        parsed = yaml.safe_load(content)
        assert "global" in parsed
