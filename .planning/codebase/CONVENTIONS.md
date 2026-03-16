# Coding Conventions

**Analysis Date:** 2026-03-16

## Naming Patterns

**Files:**
- Lowercase with underscores: `image_manager.py`, `sprite_detector.py`, `source_panel.py`
- Class names: PascalCase: `ImageManager`, `GridPacker`, `SpritesheetCanvas`, `SourcePanel`
- Module naming follows single purpose: detector, manager, exporter, etc.

**Functions:**
- snake_case for all functions: `detect_regular()`, `auto_bg_color()`, `compute_safe_margins()`, `get_content_bbox()`
- Private functions prefixed with underscore: `_make_mask()`, `_find_bands()`, `_make_checker_brush()`, `_copy_list()`
- Signal handlers prefixed with underscore: `_on_sprites_detected()`, `_build_ui()`, `_connect_signals()`
- Internal helper prefixed with underscore: `_snapshot()`, `_layout_grid()`, `_compute_content_rects()`

**Variables:**
- snake_case for local variables: `cell_w`, `cell_h`, `padding`, `bg_color`, `source_rect`
- Constant UPPERCASE: `MAX_HISTORY`, `LAYOUT_HORIZONTAL`, `LAYOUT_VERTICAL`, `LAYOUT_GRID`, `THUMB_SIZE`, `PRESETS`
- Instance variables prefixed with underscore: `self._sprites`, `self._undo_stack`, `self._source_image`, `self._cell_w`
- Protected class variables (constants) uppercase: `MAX_HISTORY = 50` in `ImageManager`
- Data role constants use Qt convention: `_ENTRY_ROLE = Qt.ItemDataRole.UserRole`

**Types:**
- Use type hints throughout: `list[SpriteEntry]`, `tuple[int, int, int, int]`, `Optional[Image.Image]`
- Union with pipe operator: `str | Path`
- Optional imported from typing: `from typing import Optional`
- Dataclass with type hints: `@dataclass class SpriteEntry: name: str, image: Image.Image, source_file: str = ""`

## Code Style

**Formatting:**
- 4-space indentation (Python standard)
- Single blank line between methods in classes
- Double blank line between top-level functions
- `from __future__ import annotations` at top of all files (enables forward references and deferred annotation evaluation)
- Max line length: no hard limit observed, but most lines under 100 characters
- No trailing whitespace

**Linting:**
- No `.flake8`, `.pylintrc`, or `pyproject.toml` detected
- No automated formatting tool config detected (no `.prettierrc` or `black` config)
- Code follows PEP 8 style implicitly

## Import Organization

**Order:**
1. Future imports: `from __future__ import annotations`
2. Standard library: `import sys`, `import json`, `from pathlib import Path`, `from typing import Optional`
3. Third-party: `from PIL import Image`, `import numpy as np`, `from PyQt6.QtCore import...`
4. Local imports: `from core.image_manager import...`, `from ui.canvas import...`

**Path Aliases:**
- No path aliases configured
- All imports use absolute paths from project root: `from core.exporter import Exporter`, `from ui.main_window import MainWindow`

**Style:**
- Imports grouped with blank line separating major groups
- Multi-line imports use parentheses for readability:
  ```python
  from PyQt6.QtWidgets import (
      QFileDialog,
      QMainWindow,
      QMessageBox,
  )
  ```

## Error Handling

**Patterns:**
- Defensive early returns: `if not valid: return False`
- Guard clauses: `if 0 <= index < len(self._sprites): ...`
- Type validation implicit (no explicit try/except for type mismatches)
- File operations wrapped with Path safety: `p.parent.mkdir(parents=True, exist_ok=True)`
- Optional returns for uncertain operations: `Optional[tuple[int, int, int, int]]` returns `None` if image fully transparent
- No explicit error raising observed — functions return `None`/`False`/empty collections on failure

**No visible exception handling patterns:**
- No try/except blocks detected in core modules
- File operations assume success (PIL, Path operations)
- PyQt signals/slots assume valid connections

## Logging

**Framework:** None detected

**Patterns:**
- No logging framework (no `import logging`)
- Status messages via PyQt `QStatusBar`: `self.status_bar.showMessage()`
- Debug output could be added to console but currently not implemented

## Comments

**When to Comment:**
- Docstrings on public methods (class docstrings):
  ```python
  class ImageManager:
      """
      Ordered list of sprites to be packed.
      Every mutation saves an undo snapshot; redo stack is cleared on new edits.
      """
  ```
- Comments above method headers for clarity:
  ```python
  # ------------------------------------------------------------------
  # Read-only access
  # ------------------------------------------------------------------
  ```
- Inline comments for non-obvious algorithms:
  ```python
  # Sort left-to-right, top-to-bottom
  sprites.sort(key=lambda s: (s.source_rect[1], s.source_rect[0]))
  ```

**JSDoc/TSDoc:**
- Not applicable (Python project)
- Docstrings are minimal, focused on purpose not implementation
- Type hints serve as inline documentation

## Function Design

**Size:** Functions are concise, typically 10–30 lines

**Parameters:**
- Explicit over implicit: full parameter lists, no excessive *args/**kwargs
- Type hints required: `def detect_regular(img: Image.Image, rows: int, cols: int, bg_mode: str = "transparent", ...) -> list[DetectedSprite]`
- Default arguments for optional config: `strip_empty: bool = True`

**Return Values:**
- Single explicit return value (no multiple return types)
- Collections or None for optional returns: `Optional[tuple[int, int, int, int]]`
- Boolean for success/failure: `def trim_sprites(self, indices: list[int]) -> bool`
- Custom types preferred: `list[DetectedSprite]` over generic list

## Module Design

**Exports:**
- No `__all__` declarations observed
- Public API implicit through class/function definitions
- Dataclasses exported as types: `SpriteEntry`, `DetectedSprite`

**Barrel Files:**
- Not used (each module imports directly from source)
- `core/__init__.py` and `ui/__init__.py` are empty

**File Boundaries:**
- `core/` contains pure logic (image processing, layout, export)
- `ui/` contains PyQt6 presentation layer
- Strong separation: UI imports from core, core never imports from ui
- Clear responsibility: `sprite_detector.py` only detection, `image_manager.py` only state/list management

## Type System

**Type Hints:**
- Consistent throughout: all function signatures typed
- Union with pipe operator: `str | Path`
- Optional imported: `from typing import Optional`
- Forward references enabled: `from __future__ import annotations`
- Generic types with brackets: `list[SpriteEntry]`, `dict[str, list[SpriteEntry]]`

**Dataclass Usage:**
- `@dataclass` for data containers (no custom `__init__`):
  ```python
  @dataclass
  class SpriteEntry:
      name: str
      image: Image.Image
      source_file: str = ""
  ```

## PyQt6 Conventions

**Signals:**
- `pyqtSignal()` declared as class attributes: `sprites_detected = pyqtSignal(list)`
- Emitted via `.emit()`: `self.sprites_detected.emit(entries)`
- Connected in `_connect_signals()` method
- Signal naming: snake_case, descriptive verb: `sprites_detected`, `layout_changed`, `settings_changed`

**UI Building:**
- Layout construction in `_build_ui()` method
- Widget setup centralized (no scattered `setEnabled` calls)
- Signal connections in separate `_connect_signals()` method
- Naming: `self.btn_load`, `self.lbl_file`, `self.spin_cols` (type prefix)

**Styling:**
- Inline QSS for simple styles: `setStyleSheet("border: 1px solid #666; background: #333;")`
- Cosmetic pens for UI elements: `QPen(...).setCosmetic(True)` (1px at all zoom levels)

## Algorithm Conventions

**Pixel Art Handling:**
- Always use `Image.Resampling.NEAREST` for scaling (never BICUBIC or LANCZOS)
- Conversions to RGBA explicit: `img.convert("RGBA")`
- NumPy arrays for pixel-level operations: `arr = np.array(rgba)`

**Image Processing:**
- PIL for high-level operations (crop, resize, paste)
- NumPy for masks and bulk operations (projection, content detection)
- Coordinate system: (x, y, w, h) for rects, consistent throughout

---

*Convention analysis: 2026-03-16*
