# Architecture

**Analysis Date:** 2026-03-16

## Pattern Overview

**Overall:** Layered MVC-like Desktop Application

**Key Characteristics:**
- Clean separation between UI layer and business logic layer
- Unidirectional signal-based event flow from UI to core
- Single source of truth in `ImageManager` for sprite state
- Pluggable layout engine with three runtime modes (horizontal/vertical/grid)
- Snapshot-based undo/redo system

## Layers

**Presentation (UI):**
- Purpose: Render visual components and capture user input
- Location: `ui/` directory
- Contains: Qt6 widgets (panels, canvas, toolbar), signal emissions, style/layout
- Depends on: `core.image_manager`, `core.packer` (for rendering), event signals
- Used by: Main application window as view components

**State Management (Core):**
- Purpose: Manage sprite collection, mutations, and undo/redo history
- Location: `core/image_manager.py`
- Contains: `ImageManager` class with sprite list and snapshot stacks
- Depends on: PIL, PyQt6 utilities only
- Used by: All UI components, packer, exporter

**Layout & Packing Engine (Core):**
- Purpose: Calculate sprite positions and generate output spritesheet
- Location: `core/packer.py` (`GridPacker` class)
- Contains: Three layout strategies (horizontal/vertical/grid), sheet generation, Phaser JSON metadata
- Depends on: `ImageManager`, PIL for image composition
- Used by: Main window for rendering, export

**Sprite Detection (Core):**
- Purpose: Parse source spritesheets and extract individual sprites
- Location: `core/sprite_detector.py`
- Contains: Regular grid detection, irregular/auto-detect via projection
- Depends on: PIL, numpy for image analysis
- Used by: Source panel on user action

**Image Processing (Core):**
- Purpose: Pixel-level operations (trimming, background removal, format conversion)
- Location: `core/exporter.py`, `core/trimmer.py`
- Contains: Export to PNG/JSON, trim detection and application
- Depends on: PIL, numpy, json
- Used by: Main window for export, ImageManager for trim mutations

**Application Root:**
- Purpose: Bootstrap Qt application and wire signal connections
- Location: `main.py` (entry point), `ui/main_window.py` (orchestrator)
- Contains: QApplication setup, window initialization, signal routing
- Depends on: All UI and core modules
- Used by: Python runtime

## Data Flow

**Detection Workflow (Source → Manager → Canvas):**

1. User loads spritesheet in `SourcePanel` (or drag-drops to `MainWindow`)
2. `SourcePanel._load_sheet()` → PIL opens image, displays thumbnail
3. User configures detection mode (regular grid params or irregular min_pixels) and background mode
4. User clicks "Detect Sprites" button
5. `_detect()` calls `sprite_detector.detect_regular()` or `detect_irregular()` → returns `list[DetectedSprite]`
6. Wraps results as `list[SpriteEntry]` with auto-generated names and source_file tracking
7. Emits `sprites_detected` signal → routed to `MainWindow._on_sprites_detected()`
8. Main window optionally applies auto-trim via `trimmer.compute_safe_margins()` + `apply_trim()`
9. Calls `ImageManager.add_sprites()` → saves undo snapshot, extends sprite list
10. Refreshes list view and triggers `MainWindow.refresh()` for output recalculation

**Rendering Workflow (Manager → Packer → Canvas):**

1. User adjusts output settings (cell size, columns, padding, layout mode) via `OutputToolbar`
2. Toolbar emits `settings_changed` signal
3. `MainWindow.refresh()` reads current toolbar values and layout mode
4. Calls `GridPacker.pack()` with current `ImageManager.sprites`, packing parameters, and layout mode
5. Packer calculates positions via `_layout()` (dispatches to `_layout_horizontal/vertical/grid`)
6. Packer creates output `Image` by:
   - Calling `_fit()` if sprite exceeds cell size (scales down with NEAREST resampling)
   - Centering sprite in cell
   - Pasting into output sheet at calculated position
7. Stores result in `MainWindow._current_sheet` (PIL Image)
8. Computes content bounding boxes via `_compute_content_rects()` for blue outline overlays
9. Calls `canvas.load_sheet()` with output image, grid params, and content rects
10. Canvas converts PIL image to QPixmap, renders in scene, draws grid + content outlines in `drawForeground()`

**State Mutation & Undo/Redo:**

1. User performs action: reorder sprite, remove sprite, trim selected, clear all
2. UI widget calls corresponding `ImageManager` method (e.g., `reorder()`, `remove()`, `trim_sprites()`)
3. Method calls `_snapshot()` before mutation:
   - Pushes copy of current `_sprites` to `_undo_stack` (max 50 entries)
   - Clears `_redo_stack` (new edit invalidates redo history)
   - Then applies the mutation
4. `SpritesPanel` emits `sprites_changed` signal
5. Main window slot `_on_sprites_changed()` calls `refresh()` (full re-render)
6. User presses Ctrl+Z or menu → calls `MainWindow._undo()`
7. `ImageManager.undo()` swaps current state with top of undo stack, pushes current to redo stack
8. Refreshes UI and re-renders

**Export Workflow:**

1. User clicks "Export PNG", "Export JSON", or "Export Both" in toolbar or File menu
2. Triggers `_export_png()`, `_export_json()`, or `_export_both()` in MainWindow
3. If no sheet generated yet, shows warning
4. Opens save dialog via Qt file browser
5. For PNG: calls `Exporter.export_png(self._current_sheet, path)` → saves PIL image
6. For JSON: calls `GridPacker.metadata()` to generate Phaser-compatible JSON, then `Exporter.export_json(meta, path)`
7. For Both: calls `export_both()` which saves PNG and automatically creates `.json` alongside
8. Never overwrites source file (separate output path)

**Layout Synchronization (Source ↔ Toolbar):**

1. User changes layout radio in `SourcePanel` (Horizontal/Vertical/Grid)
2. Emits `layout_changed` signal with mode string
3. `MainWindow._on_source_layout_changed()` calls `toolbar.set_layout(mode)` (blocks signals to prevent recursion)
4. Toolbar updates its radio buttons and hides columns spinbox if not Grid mode
5. Toolbar also emits `layout_changed` signal
6. Both routes end with `MainWindow.refresh()` which uses `toolbar.layout_mode`
7. Same pattern in reverse if user changes toolbar layout radio

## Key Abstractions

**SpriteEntry:**
- Purpose: Atomic sprite unit with image data and metadata
- Examples: `core/image_manager.py` lines 10–14
- Pattern: Simple dataclass wrapping PIL Image + name + source tracking
- Fields: `name` (str), `image` (PIL Image), `source_file` (str for origin tracking)

**DetectedSprite:**
- Purpose: Intermediate result from sprite detection before wrapping as SpriteEntry
- Examples: `core/sprite_detector.py` lines 10–13
- Pattern: Temporary dataclass containing image and source rectangle info
- Used internally by detection functions, converted to SpriteEntry by UI layer

**ImageManager:**
- Purpose: Authoritative sprite collection and mutation handler
- Examples: `core/image_manager.py` lines 17–156
- Pattern: Manager pattern with snapshot-based state preservation
- Public interface: `add_sprites()`, `remove()`, `reorder()`, `trim_sprites()`, `undo()`, `redo()`, read-only `sprites` property
- Guarantees: Every mutation is undoable (within 50-entry limit), redo cleared on new edits

**GridPacker:**
- Purpose: Convert sprite collection + parameters into packed output sheet
- Examples: `core/packer.py` lines 41–194
- Pattern: Strategy pattern with three layout implementations
- Public methods: `pack()` (PIL Image output), `metadata()` (Phaser JSON), `get_positions()` (sprite locations for canvas overlays)
- Three layout strategies: `_layout_horizontal()` (rows), `_layout_vertical()` (columns), `_layout_grid()` (table)

**SpritesheetCanvas:**
- Purpose: Qt graphics view rendering sprite sheet with grid and content outlines
- Examples: `ui/canvas.py` lines 23–173
- Pattern: Custom QGraphicsView with scene-based rendering
- Drawing: `drawForeground()` for red grid lines + blue content outlines (always 1px cosmetic pen regardless of zoom)
- Zoom: Wheel scroll with 1.2x factor, emits `zoom_changed` signal for status bar

## Entry Points

**Application Root:**
- Location: `main.py` lines 1–15
- Triggers: Python interpreter invocation
- Responsibilities: Create Qt application, set Fusion style, instantiate and show MainWindow

**MainWindow:**
- Location: `ui/main_window.py` lines 29–346
- Triggers: Qt event loop
- Responsibilities: Orchestrate all UI components, wire signals, execute workflows, manage file I/O

**Signal Entry Points (from UI):**
- `SourcePanel.sprites_detected` → `MainWindow._on_sprites_detected()` (detection result)
- `SourcePanel.layout_changed` → `MainWindow._on_source_layout_changed()` (layout sync)
- `SpritesPanel.sprites_changed` → `MainWindow._on_sprites_changed()` (sprite list mutation)
- `SpritesPanel.trim_requested` → `MainWindow._on_trim_requested()` (selective trim)
- `OutputToolbar.settings_changed` → `MainWindow.refresh()` (output recalculation)
- `Canvas.zoom_changed` → `MainWindow._on_zoom_changed()` (status bar update)

## Error Handling

**Strategy:** Defensive validation + exception catching at UI boundary

**Patterns:**

1. **File I/O:** Try-except in load_sheet methods
   - Example: `source_panel.py` lines 252–267, `load_from_path()` lines 314–325
   - Shows error label on failure, disables Detect button

2. **Image Processing:** Validation before operation
   - Example: `packer.py` _layout methods check for empty sprite list early
   - `sprite_detector.py` returns empty list for edge cases (fully transparent, min_pixels exceeded)

3. **Signal-Slot Validation:** Guards in event handlers
   - Example: `_on_sprites_detected()` checks `if not entries` before proceeding
   - `_on_trim_requested()` checks return value of `manager.trim_sprites()`

4. **Export Safety:** Require sheet check before save
   - Example: `main_window.py` lines 256–263 `_require_sheet()`
   - Shows message box if no sheet to export

5. **Undo/Redo Safety:** Stack bounds checking
   - Example: `image_manager.py` lines 106–127 check stack emptiness

## Cross-Cutting Concerns

**Logging:** Not implemented; would use `print()` or Python logging module for debug output

**Validation:**
- Image format validation: `supported_exts = {".png", ".jpg", ".jpeg"}`
- Numeric bounds: SpinBox widgets enforce min/max on grid params
- Null checks: `if self._current_sheet is None` before export

**Authentication:** Not applicable (desktop-only, no user accounts)

**Pixel Art Preservation:**
- Always use `Image.Resampling.NEAREST` for downscaling (lines 33 in packer, 261 in source_panel, 98 in sprites_panel)
- Canvas render hint `SmoothPixmapTransform = False` for sharp pixels at any zoom

**Image Format Standardization:**
- All internal work in RGBA: `.convert("RGBA")` called immediately on load
- PIL Image objects used throughout, converted to QPixmap only at render boundary

---

*Architecture analysis: 2026-03-16*
