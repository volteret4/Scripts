# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A two-part tool for quickly searching and editing dotfiles/configuration files:

1. **`dotfiles_indexer.py`** — CLI script that indexes files from `~/.local/share/chezmoi` into `dotfiles.db` (SQLite)
2. **`dotfiles_quick_editor.py`** — PyQt6 GUI that searches the database and opens files in an external editor

## Running the Tools

```bash
# Activate the shared virtual environment first
source /home/huan/Scripts/python_venv/bin/activate

# Run the GUI editor
python dotfiles_quick_editor.py
python dotfiles_quick_editor.py --theme gruvbox  # with a specific theme

# Index/update the database
python dotfiles_indexer.py              # incremental update
python dotfiles_indexer.py --force      # full re-index
python dotfiles_indexer.py --stats      # show DB statistics
python dotfiles_indexer.py --search vim # search from CLI
```

## Architecture

### Data Flow
`chezmoi files → dotfiles_indexer.py → dotfiles.db → dotfiles_quick_editor.py → external editor`

### Database (`dotfiles.db`)
SQLite with WAL mode. Main table: `dotfiles` (path, filename, extension, is_config, is_executable, source_root, relative_path, hash, mtime). The `dotfiles_with_categories` view joins files with their auto-classified categories. `DotfilesIndexer.is_file_changed()` uses mtime+hash to skip unchanged files.

### GUI (`dotfiles_quick_editor.py`)
- Search runs in a `DatabaseSearchThread` (QThread) to avoid blocking the UI — emits `results_ready` signal when done
- Results sorted by relevance: exact filename match → prefix match → path match → rest
- Max 500 results per query
- Theme colors loaded from `themes.yml` at startup via PyYAML

### Configuration constants in `dotfiles_indexer.py`
- `SEARCH_PATHS` — directories to index (default: `~/.local/share/chezmoi`)
- `EXCLUDE_PATHS` — heavy/irrelevant dirs (Chrome, Firefox, Steam, Discord caches, etc.)
- `CONFIG_EXTENSIONS` / `CONFIG_FILENAMES` — what counts as a config file
- `MAX_FILE_SIZE` — 10MB cap per file

## Themes

Defined in `themes.yml`. Each theme has: `bg_color`, `widget_bg`, `text_color`, `accent_color`, `border_color`, `search_bg`, `search_border`. Available: `catppucin`, `forest-dark`, `gruvbox`, `kanagawa`, `neon`, `solarized-dark`, `tokyo-night`.

## Repository Context

This directory lives inside `/home/huan/Scripts/`, a personal automation monorepo. The Python virtual environment at `/home/huan/Scripts/python_venv/` is shared across projects. Pre-commit hooks run `gitleaks` (v8.24.0) to scan for secrets. The broader repo also contains PyQt6 GUI apps in `menus/` (icon browser, blog post creator, script launcher) that follow the same pattern: SQLite DB + PyQt6 frontend + YAML themes.
