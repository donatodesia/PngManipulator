# Codebase Structure

**Analysis Date:** 2026-03-16

## Directory Layout

```
PngManipulator/
├── main.py                 # Application entry point
├── requirements.txt        # Python package dependencies
├── DESIGN_DOC.txt         # Design notes (reference)
├── core/                  # Business logic and algorithms
│   ├── __init__.py
│   ├── image_manager.py   # Sprite state management + undo/redo
│   ├── packer.py          # Layout engine (3 strategies)
│   ├── sprite_detector.py # Regular grid + irregular auto-detect
│   ├── trimmer.py         # Trim detection and application
│   └── exporter.py        # PNG/JSON output
├── ui/                    # PyQt6 user interface
│   ├── __init__.py
│   ├── main_window.py     # Application window (orchestrator)
│   ├── source_panel.py    # Left: load sheet, detection config
│   ├── sprites_panel.py   # Right: sprite list, reorder, remove
│   ├── canvas.py          # Center: sheet preview with grid overlays
│   ├── toolbar.py         # Bottom: output settings, export buttons
│   └── sidebar.py         # ORPHANED (replaced by sprites_panel.py)
└── .planning/             # Documentation directory
    └── codebase/          # This analysis lives here
        ├── ARCHITECTURE.md
        ├── STRUCTURE.md
        ├── CONVENTIONS.md
        ├── TESTING.md
        ├── CONCERNS.md
        ├── STACK.md
        └── INTEGRATIONS.md
```

## Directory Purposes

**core/ — Business Logic & Algorithms**
- Purpose: All non-UI functionality; pure Python, no Qt dependencies
- Contains: Image processing, sprite detection, packing algorithms, state management, file I/O
- Key files: `image_manager.py` (state), `packer.py` (layout), `sprite_detector.py` (extraction)
- No external files: All operations work directly with PIL Image objects in memory

**ui/ — Graphical Interface Components**
- Purpose: PyQt6 widgets, user input handling, scene rendering
- Contains: Main window, side panels, canvas, toolbar; all Qt classes
- Key files: `main_window.py` (orchestrator), `canvas.py` (preview), `source_panel.py` (input), `sprites_panel.py` (list)
- Dependencies: Imports from `core/` for business logic

## Key File Locations

**Entry Points:**
- `main.py`: Root application entry (line 6, `main()` function)
- `ui/main_window.py`: Window initialization (line 29, `MainWindow.__init__()`)
- `core/image_manager.py`: State singleton pattern usage location

**Configuration:**
- `requirements.txt`: Python package versions
- `DESIGN_DOC.txt`: Design notes and project overview

**Core Logic:**
- `core/image_manager.py`: Sprite collection and undo/redo (150 lines)
- `core/packer.py`: Layout calculation and Phaser JSON generation (190 lines)
- `core/sprite_detector.py`: Sprite extraction algorithms (160 lines)
- `core/trimmer.py`: Transparent border detection and removal (75 lines)
- `core/exporter.py`: PNG and JSON file writing (30 lines)

**Testing:**
- Not found; no test files present in codebase

**UI Components:**
- `ui/main_window.py`: Signal routing and workflow orchestration (346 lines) — CRITICAL
- `ui/source_panel.py`: Input sheet loading and detection parameters (326 lines)
- `ui/sprites_panel.py`: Sprite list, reorder, trim, remove operations (168 lines)
- `ui/canvas.py`: Graphics rendering with grid and content overlays (173 lines)
- `ui/toolbar.py`: Output settings and export buttons (205 lines)
- `ui/sidebar.py`: ORPHANED (no longer used; replaced by `sprites_panel.py`)

## Naming Conventions

**Files:**
- Snake case: `image_manager.py`, `source_panel.py`
- Module groups: `core/` for algorithms, `ui/` for widgets
- Double underscores: `__init__.py` for package markers
- No suffix patterns (not `_test.py` or `.spec.js`)

**Functions:**
- Snake case throughout: `detect_regular()`, `_on_sprites_detected()`, `get_content_bbox()`
- Private convention: Leading underscore for internal methods: `_load_sheet()`, `_build_ui()`, `_layout()`
- Public methods: No prefix: `pack()`, `refresh()`, `export_png()`
- Signal handlers: Prefix with `_on_` for clarity: `_on_sprites_changed()`, `_on_zoom_changed()`

**Variables:**
- Snake case for locals and instance attributes: `self._source_image`, `self._undo_stack`, `cell_w`, `sheet_h`
- Prefixed private: `self._sprites` (internal manager state), `self._scene` (internal Qt scene)
- Constants: All caps: `LAYOUT_HORIZONTAL`, `MAX_HISTORY`, `THUMB_SIZE`, `PRESETS`
- Abbreviations: `px` (pixels), `w`/`h` (width/height), `bg` (background), `col`/`row`, `sel` (selected)

**Types & Classes:**
- PascalCase: `ImageManager`, `GridPacker`, `SpritesPanel`, `MainWindow`, `SpriteEntry`, `DetectedSprite`
- Dataclasses marked with `@dataclass`: `SpriteEntry`, `DetectedSprite`

**Qt-Specific:**
- Signals: `pyqtSignal()` instances named descriptively: `sprites_detected`, `settings_changed`, `zoom_changed`
- Slots: Methods named with handler semantics: `_on_*` prefix (auto-connect) or explicit `.connect()` call
- Widgets: Prefixed by type for clarity in UI builders: `lbl_file` (label), `btn_load` (button), `spin_cols` (spinbox), `radio_grid` (radio button)

## Where to Add New Code

**New Feature (e.g., sprite splitting):**
- Primary code: `core/sprite_splitter.py` (new module)
- UI trigger: Add button to `ui/sprites_panel.py` header row
- Integration: Call `ImageManager.add_sprites()` with results
- Signal flow: Emit new signal from UI panel → route through `MainWindow`

**New Component/Widget (e.g., color picker panel):**
- Implementation: `ui/color_panel.py` (new file)
- Register in `MainWindow._build_ui()`: Add to splitter or layout
- Signals: Define `pyqtSignal()` instances, connect in `_connect_signals()`
- Data flow: Emit from widget → handle in MainWindow → pass to core

**Utilities (e.g., image format converter):**
- Shared helpers: `core/utils.py` or add to existing module
- Keep in `core/` if pure (no Qt dependency)
- Move to `ui/` only if requires PyQt6 widgets

**Test Files:**
- Location: `tests/` directory (create if adding tests)
- Pattern: Mirror structure: `tests/test_image_manager.py`, `tests/ui/test_canvas.py`
- Framework: Use `pytest` or `unittest` (not currently in use)

## Special Directories

**ui/ — Generated artifacts from .ui files:**
- Status: No `.ui` files in this project
- Generation: Not used; widgets built programmatically in Python

**.planning/codebase/**
- Purpose: Stores architecture and conventions documentation
- Generated: By `/gsd:map-codebase` command
- Committed: Yes (tracked in version control)
- Read by: `/gsd:plan-phase` and `/gsd:execute-phase` commands

**.claude/**
- Purpose: GSD workflow templates and agent definitions
- Generated: By GSD setup
- Committed: Yes
- Usage: Referenced by Claude Code agent for planning/execution

## Import Organization

**Pattern: Stdlib → Third-party → Local**

Example from `main_window.py`:
```python
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (...)

from core.exporter import Exporter
from core.image_manager import ImageManager, SpriteEntry
from core.packer import GridPacker
from core.trimmer import get_content_bbox, compute_safe_margins, apply_trim
from ui.canvas import SpritesheetCanvas
from ui.source_panel import SourcePanel
from ui.sprites_panel import SpritesPanel
from ui.toolbar import OutputToolbar
```

**Order:**
1. `from __future__ import annotations` (Python 3.7+ compatibility, always first)
2. Standard library: `pathlib`, `json`, `io`
3. Third-party: `PIL`, `numpy`, `PyQt6.*`
4. Local: `core.*`, `ui.*`
5. Within each group: alphabetical or logical grouping

**Path Aliases:**
- No aliases configured (not using `jsconfig.json` or `tsconfig.json` pattern)
- Relative imports: None used; all absolute from project root
- Module access: `from core.image_manager import ImageManager` (explicit)

## Directory Modification Patterns

**Adding core logic:**
1. Create file in `core/` (e.g., `core/new_feature.py`)
2. Use PIL Image and numpy only; no Qt
3. Export public functions/classes at module level
4. Import in `ui/` or from other `core/` modules as needed

**Adding UI panel:**
1. Create file in `ui/` (e.g., `ui/new_panel.py`) inheriting from `QWidget`
2. Define signals as `pyqtSignal()` at class level
3. Implement `_build_ui()` method for layout
4. Connect internal signals in `__init__()` or `_connect_signals()`
5. Register in `MainWindow._build_ui()`: add to splitter or main layout
6. Connect widget signals in `MainWindow._connect_signals()`

**Modifying existing UI:**
- Always update `MainWindow._connect_signals()` if signal semantics change
- Preserve signal names/signatures for backward compatibility with main window routing
- Test layout changes via visual inspection after `python main.py`

**Modifying core logic:**
- Keep all functions pure (deterministic, no side effects)
- Use PIL Image as standard image format throughout `core/`
- Always convert to RGBA immediately: `Image.open(path).convert("RGBA")`
- Use `Image.Resampling.NEAREST` for pixel art operations
- Return typed results (not tuples) when possible; use dataclasses for complex returns

---

*Structure analysis: 2026-03-16*
