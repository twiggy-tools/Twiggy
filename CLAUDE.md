# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Twiggy is a Python CLI tool that generates real-time directory structure files for Cursor AI. It watches for file system changes and updates `.cursor/rules/file-structure.mdc` automatically so Cursor's AI always knows the full codebase structure.

## Commands

```bash
# Install in development mode
pip install -e .

# Initialize in a project
twiggy init              # Interactive setup
twiggy init --defaults   # Use defaults (no prompts)
twiggy init --config-only  # Create config without scanning

# Run the tool
twiggy watch   # Start file watcher (real-time updates)
twiggy scan    # One-time manual scan
```

## Architecture

All source code is in `cursor_context/`:

- **cli.py** - Click-based CLI entry point with `init`, `watch`, `scan` commands
- **config.py** - `Config` class that parses `twiggy.yml`, manages ignore patterns (default + custom + .gitignore sync)
- **scanner.py** - `DirectoryScanner` that recursively builds directory tree and generates output (XML or tree format)
- **watcher.py** - `FileWatcher` and `CursorContextHandler` using watchdog for real-time file system monitoring with 1-second debounce
- **gitignore.py** - Ensures `.cursor/rules/file-structure.mdc` is added to `.gitignore`
- **defaults.py** - Default configuration values
- **templates/** - `.mdc.template` and `.yml.template` files loaded via `importlib.resources`

## Key Design Decisions

- **Config file tracked, output not**: `twiggy.yml` is tracked in git; `.cursor/rules/file-structure.mdc` is gitignored by design. This ensures the generated file is either accurate (when watcher is running) or doesn't exist (never stale).
- **Output formats**: XML (default, better for LLMs) or tree (visual `├──` style)
- **Ignore system**: Combines hardcoded defaults (node_modules, __pycache__, .git, etc.) + custom patterns from `twiggy.yml` + optional .gitignore sync
