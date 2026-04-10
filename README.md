# build_it

> **Flutter multi-flavor build automation CLI** — read your `flavorizr` config
> and build all your app flavors in a single command.

```
build_it build --all --parallel
```

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/badge/status-alpha-orange)](https://pypi.org/project/build_it/)

---

## Why build_it?

Managing Flutter builds across multiple flavors quickly becomes tedious:
different `applicationId`s, per-environment Dart defines, and varying build
targets require long, error-prone shell commands.

**build_it** turns this:

```bash
flutter build apk --flavor apple --dart-define ENV=prod --dart-define-from-file config/apple.json
flutter build apk --flavor banana --dart-define ENV=prod --dart-define-from-file config/banana.json
flutter build ios --flavor apple  --dart-define ENV=prod --dart-define-from-file config/apple.json
```

Into this:

```bash
build_it build --all --parallel
```

---

## Features

| Feature | Details |
|---|---|
| **All flavorizr syntaxes** | v1 (legacy flat keys), v2+ standalone `flavorizr.yaml`, embedded in `pubspec.yaml` |
| **Per-flavor dart-defines** | Global → flavor → CLI priority merge |
| **Smart parallel builds** | Automatic parallelism across different targets; sequential within the same target |
| **Build type control** | `--type release` (default) / `profile` / `debug` |
| **Rich terminal output** | Live progress, per-flavor logs, final summary table with durations |
| **Zero config to start** | Works out of the box; `.build_it.yaml` is optional |
| **pip / pipx installable** | Single command global install, no manual PATH setup |

---

## Installation

```bash
# Via pipx (recommended — fully isolated global install)
pipx install build_it

# Via pip
pip install build_it

# Development mode (editable install from the cloned repo)
pip install -e ".[dev]"
```

---

## Quick start

```bash
# Run from the root of your Flutter project

build_it info          # check project detection and tool version
build_it list          # list detected flavors and resolved config
build_it init          # generate a .build_it.yaml starter config

build_it build --flavor apple                   # build one flavor
build_it build --all                            # build all flavors (sequential)
build_it build --all --parallel                 # build across targets in parallel
build_it build --all --target appbundle         # force a specific target
build_it build --flavor apple --type profile    # profile build
build_it build --all -D ENV=staging -y          # extra defines, skip prompt
```

---

## Configuration — `.build_it.yaml`

Place this file at the root of your Flutter project (next to `pubspec.yaml`).
Generate a pre-populated version with `build_it init`.

```yaml
# .build_it.yaml

global:
  targets: [apk]                    # default targets for every flavor
  dart_defines:                     # applied to every build job
    ENV: production
  dart_define_files:
    - config/global.json
  extra_args: []

flavors:
  apple:
    targets: [apk, ios]             # overrides global targets for this flavor
    dart_defines:
      FLAVOR_NAME: apple
    dart_define_files:
      - config/apple.json
    entry_point: lib/main_apple.dart  # optional custom entry point

  banana:
    # no targets → inherits global.targets
    dart_defines:
      FLAVOR_NAME: banana
```

You can also embed the config directly in `pubspec.yaml` under the `build_it:` key.

### Dart-define priority (highest → lowest)

| Priority | Source |
|---|---|
| 1 (highest) | `--dart-define` / `--dart-define-from-file` on the CLI |
| 2 | Flavor-specific `dart_defines` in `.build_it.yaml` |
| 3 (lowest) | Global `dart_defines` in `.build_it.yaml` |

For **key/value pairs**, higher-priority values override lower-priority ones on key collision.
For **files**, all sources are concatenated: global → flavor → CLI.

### Target priority (highest → lowest)

| Priority | Source |
|---|---|
| 1 (highest) | `--target` on the CLI |
| 2 | Flavor `targets` in `.build_it.yaml` |
| 3 (lowest) | Global `targets` in `.build_it.yaml` |

---

## Parallel mode

| Scenario | Behaviour |
|---|---|
| Multiple flavors, **same target** | Sequential — prevents `build/` directory corruption |
| Multiple flavors, **different targets** | Parallel automatically suggested |
| `--parallel` flag | Forced parallel — each job gets an isolated `--output-dir build/outputs/<flavor>_<target>/` |

Output directories are printed in the summary table at the end of every build.

---

## Commands

| Command | Description |
|---|---|
| `build_it info` | Project detection status and tool version |
| `build_it list` | Detected flavors with resolved targets and dart-defines |
| `build_it init [--force]` | Generate `.build_it.yaml` pre-populated with detected flavors |
| `build_it build [OPTIONS]` | Build one or all flavors |
| `build_it --version` | Print the installed version |

### `build_it build` options

| Option | Short | Description |
|---|---|---|
| `--flavor NAME` | `-f` | Flavor to build (omit to build all) |
| `--target TARGET` | `-t` | Override build target |
| `--all` | `-a` | Build all detected flavors |
| `--parallel` | `-p` | Run builds in parallel across targets |
| `--type MODE` | `-T` | Build mode: `release` (default), `profile`, `debug` |
| `--dart-define K=V` | `-D` | Extra dart define, repeatable |
| `--dart-define-from-file PATH` | `-F` | Extra define file, repeatable |
| `--yes` | `-y` | Skip confirmation prompt |

---

## Supported targets

| Value | Flutter command | Supports `--output-dir` |
|---|---|---|
| `apk` | `flutter build apk` | ✓ |
| `appbundle` | `flutter build appbundle` | ✓ |
| `ios` | `flutter build ipa` | ✓ |
| `web` | `flutter build web` | ✓ |
| `macos` | `flutter build macos` | — |
| `windows` | `flutter build windows` | — |
| `linux` | `flutter build linux` | — |

> **Note** — iOS and macOS builds require macOS.  They are automatically
> skipped with status `⊘ skipped` on Linux and Windows hosts.

---

## Project layout

```
build_it/
├── pyproject.toml
├── README.md
├── .gitignore
├── scripts/
│   └── build_binaries.sh    ← PyInstaller build script
├── build_it/
│   ├── __init__.py          ← version & author
│   ├── core/
│   │   ├── enums.py         ← BuildTarget, BuildStatus, BuildType
│   │   ├── models.py        ← Pydantic models (FlavorInfo, BuildJob, …)
│   │   ├── parser.py        ← flavorizr parser (syntaxes A, B, C)
│   │   ├── config.py        ← .build_it.yaml loader + resolver
│   │   └── builder.py       ← async runner, parallel/sequential, summary
│   ├── cli/
│   │   └── main.py          ← Typer app: list / build / init / info
│   └── utils/
│       ├── constants.py     ← project-wide constants (no circular deps)
│       ├── utils.py         ← has_flutter_project(), safe_load_yaml()
│       └── guards.py        ← require_flutter_project() pre-flight check
└── tests/
    ├── fixtures/
    │   ├── syntax_a.yaml    ← flavorizr v2+ standalone
    │   ├── syntax_b.yaml    ← flavorizr embedded in pubspec.yaml
    │   └── syntax_c.yaml    ← flavorizr v1 legacy (flat keys)
    └── unit/
        └── test_parser_config.py
```

---

## Development

```bash
# Clone and install in editable mode with dev dependencies
git clone https://github.com/dasero197/build_it.git
cd build_it
pip install -e ".[dev]"

# Run the test suite
pytest

# Build a standalone binary (requires PyInstaller)
bash scripts/build_binaries.sh
```

### Running tests

```
pytest -v
```

The test suite covers:

- Parser — all three flavorizr syntaxes (A, B, C) and edge cases
- Config — loading, target resolution, dart-define merge priority
- `generate_default_config` — YAML validity and content

Tests never invoke `flutter` — the build runner is tested separately via mocks.

---

## Roadmap

- [x] P0 — Standalone project structure & package skeleton
- [x] P1 — flavorizr parser (syntaxes A, B, C) + `.build_it.yaml` resolver
- [x] P2 — Builder (async runner) + CLI commands (`list`, `build`, `init`, `info`)
- [x] P3 — Distribution: PyPI publication + PyInstaller binary + GitHub CI/CD setup
- [ ] P4 — Polish: verbose/quiet logging, build report, extended test coverage

---

## 🤖 A Word from the Author: Human-AI Collaboration

This project was developed in collaboration with **Claude** and **Gemini** via the **Antigravity** agent. 

In the modern era of AI, it is crucial not to fall into blind dependency, but rather to master the art of conciliating human architectural skills with the raw execution speed of AI. 
By maintaining the role of the Architect—designing workflows, drafting precise skeletons, defining rules, and steering corrections—while delegating boilerplate, bash scripting, and exhaustive docstring generation to the AI, we were able to deliver a complete, robust, and pristine product in record time. 

This repository stands as a testament to augmented software engineering: a powerful synergy between human vision and artificial intelligence.

---

## Contributing

Contributions, issues, and feature requests are welcome.
Please open an issue before submitting a PR so we can discuss the approach.

---

## License

MIT © [Dayane S. R. Assogba](https://github.com/dasero197)
