# Technology Stack

**Analysis Date:** 2026-03-16

## Languages

**Primary:**
- Python 3.9+ - Core application logic and CLI entry point

**Secondary:**
- None - Monolithic Python codebase

## Runtime

**Environment:**
- Python 3.9 or higher
- Native desktop application (Windows/Linux/macOS compatible)

**Package Manager:**
- pip
- Lockfile: requirements.txt (pinned versions)

## Frameworks

**Core UI:**
- PyQt6 (>=6.4.0) - Desktop GUI framework
  - Used by: `ui/main_window.py`, `ui/canvas.py`, `ui/source_panel.py`, `ui/sprites_panel.py`, `ui/toolbar.py`
  - Components: QMainWindow, QGraphicsView/QGraphicsScene, dialogs, widgets, signals/slots

**Image Processing:**
- Pillow (>=9.1.0) - PIL Image library
  - Used by: `core/sprite_detector.py`, `core/image_manager.py`, `core/packer.py`, `core/exporter.py`, `core/trimmer.py`
  - Operations: image crop, resize (NEAREST resampling), save PNG, RGBA conversion, pixel manipulation

**Numerical Computing:**
- numpy (>=1.23.0) - Array operations and masking
  - Used by: `core/sprite_detector.py`, `core/trimmer.py`
  - Operations: array masking for transparency detection, content bounding boxes, pixel-level operations

## Key Dependencies

**Image I/O:**
- Pillow - PNG/JPG loading and RGBA pixel manipulation
  - Critical for: sprite detection, image packing, export

**GUI Framework:**
- PyQt6 - Cross-platform desktop UI
  - Critical for: main window, canvas rendering, dialogs, drag-drop support

**Numeric Operations:**
- numpy - Efficient pixel and mask computations
  - Critical for: irregular sprite detection (projection-based row/col bands), content boundary detection

**Standard Library Only:**
- json - Phaser JSON metadata export
- pathlib - File path handling
- dataclasses - SpriteEntry, DetectedSprite
- io.BytesIO - PIL to QPixmap conversion
- collections.Counter - Background color detection

## Configuration

**Environment:**
- No environment variables required
- No secrets/credentials needed
- Hardcoded constants:
  - `LAYOUT_HORIZONTAL`, `LAYOUT_VERTICAL`, `LAYOUT_GRID` in `core/packer.py`
  - `Image.Resampling.NEAREST` for pixel art preservation
  - `MAX_HISTORY = 50` (undo/redo stack limit)

**Build/Run:**
- Entry point: `main.py` → `ui.main_window.MainWindow`
- Run command: `python main.py`
- No build step (pure Python)

## Platform Requirements

**Development:**
- Python 3.9+
- pip package manager
- Dependencies from requirements.txt

**Runtime:**
- Python 3.9+
- PyQt6 (requires Qt libraries on system):
  - Windows: included in PyQt6 package
  - Linux: may need system Qt6 libraries
  - macOS: included in PyQt6 package
- No database or external services required
- Standalone desktop application (no server needed)

## File I/O

**Input Supported:**
- PNG files (`.png`)
- JPG files (`.jpg`, `.jpeg`)
- Loaded via Pillow from user's filesystem

**Output Formats:**
- PNG spritesheet (`.png`)
- Phaser JSON metadata (`.json`) - TexturePacker-compatible Hash format
- Exported via `core/exporter.py`

## Resampling & Quality

**Pixel Art Handling:**
- All image resize operations use `Image.Resampling.NEAREST`
- Preserves sharp edges for pixel art and game sprites
- Used in `core/packer.py` during sprite fitting to cells

**Canvas Rendering:**
- QGraphicsView disables smooth pixmap transform for sharp rendering at any zoom level
- Cosmetic pen (1px at all zoom scales) for grid overlay

---

*Stack analysis: 2026-03-16*
