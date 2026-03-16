# External Integrations

**Analysis Date:** 2026-03-16

## APIs & External Services

**None** - This is a standalone desktop application with no external API integrations.

## Data Storage

**Databases:**
- Not used - No persistent database

**File Storage:**
- Local filesystem only
- Input: User selects PNG/JPG files via file dialog (`QFileDialog.getOpenFileName`)
- Output: User specifies export location via file dialog (`QFileDialog.getSaveFileName`)
- Location: `core/exporter.py` handles all file I/O

**Caching:**
- In-memory only
- Undo/redo stack: stored in `ImageManager._undo_stack` (max 50 states)
- Current spritesheet: `MainWindow._current_sheet` (PIL Image)
- No persistent caching between sessions

## Authentication & Identity

**Auth Provider:**
- Not used - No user authentication

**Credentials:**
- None required - Standalone desktop app with no account/service dependencies

## Monitoring & Observability

**Error Tracking:**
- Not used - No remote error reporting
- Errors displayed via `QMessageBox` to user in UI

**Logs:**
- Print to stdout (via `print()` statements)
- No file logging configured
- No remote logging services

## CI/CD & Deployment

**Hosting:**
- Not deployed - Runs locally on user's machine
- No server component
- Single executable (python main.py)

**Distribution:**
- Distributed as Python source code
- Requires pip install requirements.txt
- No PyPI package, Docker, or release builds configured

## Environment Configuration

**Required env vars:**
- None - All configuration is hardcoded or user-controlled via UI

**Secrets location:**
- N/A - No secrets/API keys/credentials needed

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## File Format Output Specifications

**PNG Export:**
- Format: PNG with RGBA channels
- Saved via `Pillow.Image.save(format="PNG")`
- Location: `core/exporter.py.export_png()`

**JSON Export:**
- Format: Phaser JSON Hash (TexturePacker-compatible)
- Structure (per `core/packer.py.metadata()`):
  ```json
  {
    "frames": {
      "sprite_name": {
        "frame": {"x": int, "y": int, "w": int, "h": int},
        "rotated": false,
        "trimmed": false,
        "spriteSourceSize": {"x": 0, "y": 0, "w": int, "h": int},
        "sourceSize": {"w": int, "h": int}
      }
    },
    "meta": {
      "app": "PngManipulator",
      "version": "1.0",
      "image": "spritesheet.png",
      "format": "RGBA8888",
      "size": {"w": int, "h": int},
      "scale": "1"
    }
  }
  ```
- Saved via `core/exporter.py.export_json()` using standard `json.dump()`
- Compatible with Phaser game framework

## Drag-and-Drop Integration

**Source:**
- Windows native drag-drop support via `QMainWindow.setAcceptDrops(True)`
- Accepts file paths from desktop
- Handler: `MainWindow.dragEnterEvent()`, `MainWindow.dropEvent()`
- Supported: PNG/JPG files

---

*Integration audit: 2026-03-16*
