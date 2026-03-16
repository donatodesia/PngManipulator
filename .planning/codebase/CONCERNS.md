# Codebase Concerns

**Analysis Date:** 2025-03-16

## Orphaned / Dead Code

**sidebar.py (abandoned):**
- Issue: `ui/sidebar.py` is no longer used; replaced by `ui/sprites_panel.py` per project memory
- Files: `ui/sidebar.py`
- Impact: Codebase bloat, potential confusion for developers, dead imports
- Fix approach: Delete `ui/sidebar.py` completely. Verify no imports reference it (grep check: none found currently)
- Priority: **Low** (already orphaned, no risk of regression)

## Fragile Areas

**Bare `except Exception` clauses:**
- Problem: Two locations use overly broad exception handling that masks real errors
- Files: `ui/source_panel.py` lines 256-267, 315-325
- Why fragile:
  - Line 256-267: `_load_sheet()` catches all exceptions, displays generic "Error: {e}" to user, but doesn't log details
  - Line 315-325: `load_from_path()` catches all exceptions silently and returns False; caller can't distinguish network errors from corrupt files
- Safe modification: Replace bare `Exception` catches with specific exception types (e.g., `IOError`, `PIL.UnidentifiedImageError`), log full tracebacks for debugging
- Test coverage: No unit tests exist for error paths in sprite detection

**numpy array indexing without bounds validation:**
- Problem: `core/trimmer.py` uses numpy array indexing that assumes valid content bounds
- Files: `core/trimmer.py` lines 22-25 (in `get_content_bbox()`)
- Why fragile: If `np.argmax()` returns 0 on reversed arrays, the calculation `img.height - int(np.argmax(rows[::-1]))` can produce invalid coordinates
- Safe modification: Add validation that `left < right` and `top < bottom` before returning bbox
- Risk: Trimming fully transparent sprites or edge-case images may return invalid bounds

**Content rect computation with insufficient bounds checking:**
- Problem: `ui/main_window.py` lines 224-227 compute sprite bounds but use `min()` with fitted dimensions
- Files: `ui/main_window.py` `_compute_content_rects()` method
- Why fragile: Lines 224-227 clamp bbox to fitted_w/h, which can produce rects larger than the cell itself visually
- Safe modification: Validate that computed rect coordinates stay within cell boundaries before adding to rects list
- Impact: Blue outline overlays on canvas may display incorrectly for oversized sprites

## Test Coverage Gaps

**No unit test suite:**
- What's not tested: All core logic (sprite detection, packing, trimming, export)
- Files: All `core/` modules lack tests
- Risk: Regressions in image processing go undetected until user runs manual workflow
- Priority: **High** — image manipulation is error-prone and benefit from parameterized tests

**No integration tests for UI workflows:**
- What's not tested: Full end-to-end flows (load → detect → pack → export)
- Files: All `ui/` modules
- Risk: Signal/slot wiring bugs, state synchronization failures between panels
- Priority: **Medium** — could use pytest-qt or similar for headless UI testing

**No error path testing:**
- What's not tested: Corrupted images, missing files, permission errors, out-of-memory scenarios
- Files: `ui/source_panel.py`, `core/exporter.py`
- Risk: Silent failures or cryptic errors to user in edge cases
- Priority: **Medium**

## Known Limitations

**Memory usage with large spritesheets:**
- Problem: PIL images stored in SpriteEntry and undo/redo stacks are not explicitly managed
- Files: `core/image_manager.py` (undo/redo stack), `ui/sprites_panel.py` (thumbnail generation)
- Current behavior: Each sprite kept in memory with full resolution; 50-entry undo history = 50 full copies
- Scaling limit: A 4K × 4K PNG with 100 sprites + 50 undo levels = ~2–3 GB memory if all sprites stored uncompressed
- Scaling path: Consider lazy loading, memory-mapped files, or SQLite blob storage for large projects
- Impact: Desktop app may become sluggish/crash on large spritesheets with many undo steps

**No persistence / autosave:**
- Problem: All edits exist only in memory; closing app without exporting loses work
- Files: `main.py`, `ui/main_window.py` (no save/load handlers)
- Impact: User frustration if app crashes mid-edit
- Improvement path: Add `.json` project file format storing sprite list + metadata, auto-save every N seconds

## Performance Bottlenecks

**Thumbnail generation in `refresh_list()` not cached:**
- Problem: Every call to `sprites_panel.refresh_list()` regenerates thumbnails for ALL sprites
- Files: `ui/sprites_panel.py` lines 94-103
- Cause: Thumbnails created on-the-fly without memoization
- Improvement: Cache QPixmap as attribute on SpriteEntry or use dict lookup by sprite ID
- Impact: Noticeable lag when list has 50+ sprites and refresh is called (e.g., after drag-reorder)

**`_compute_content_rects()` recomputes on every refresh:**
- Problem: Called by `main_window.refresh()` every time user changes settings, regenerates blue outline bounds
- Files: `ui/main_window.py` lines 200-230
- Cause: No caching; does `get_content_bbox()` for every sprite even if settings didn't change
- Improvement: Cache content rects when sprite list hasn't changed
- Impact: Minor with <50 sprites, noticeable with 100+ sprites on slower machines

**numpy conversion in sprite_detector not optimized:**
- Problem: Every detection call converts PIL images to numpy arrays multiple times
- Files: `core/sprite_detector.py` lines 77, 133 (detect_regular, detect_irregular)
- Cause: `np.array(rgba)` called per cell in regular grid; `_find_bands()` iterates list instead of vectorized ops
- Improvement: Vectorize band-finding or use PIL's built-in transpose/getdata
- Impact: Irregular detection is slow on very large spritesheets (>8K pixels)

## Security Considerations

**File path handling via drag-drop:**
- Risk: User can drag arbitrary files; app accepts any `.png`, `.jpg`, `.jpeg` without validation
- Files: `ui/main_window.py` lines 336-345 (dropEvent), `ui/source_panel.py` lines 314-325
- Current mitigation: PIL.Image.open() will raise exception on malformed files; caught and reported
- Recommendations:
  - Validate file size before loading (reject >512 MB images)
  - Use `imghdr` module to verify magic bytes match extension
  - Consider sandboxing image processing in subprocess for untrusted input

**Export path traversal:**
- Risk: QFileDialog.getSaveFileName() can write to arbitrary locations if user specifies path like `../../sensitive_file.png`
- Files: `ui/main_window.py` lines 268-295 (all export handlers)
- Current mitigation: None; PIL will attempt to write anywhere user specifies
- Recommendations: Restrict export to user's home or designated output folder; reject absolute paths or `..` in filename

**No input validation on spinbox values:**
- Risk: Cell width/height spinboxes accept 1–2048; creating 2048×2048 cell with 1000 sprites = massive memory allocation
- Files: `ui/toolbar.py` lines 109-117 (spin_w, spin_h range)
- Current mitigation: PIL._fit() will rescale oversized cells, but could cause temporary memory spike
- Recommendations: Add UI-level feedback showing estimated output sheet size before packing

## Dependencies at Risk

**numpy version constraint loose:**
- Risk: `numpy>=1.23.0` is very permissive; numpy 2.0+ has breaking changes in array API
- Files: `requirements.txt`
- Impact: Code using `np.argmax()`, array slicing may break silently on numpy 2.x
- Migration plan: Test with numpy 2.0+, pin to `numpy>=1.23.0,<2.0` or update code for 2.0 compat

**PyQt6 no fallback:**
- Risk: Hard dependency on PyQt6; PyQt5 incompatible
- Files: All `ui/` modules
- Impact: Cannot run on systems with PyQt5-only environments (unlikely but possible in corporate/legacy setups)
- Migration: Document as PyQt6-only or add Qt version compatibility layer if needed

## State Synchronization Issues

**Layout mode sync between SourcePanel and Toolbar:**
- Problem: Two panels both have layout radio buttons; sync is explicit signal-passing via main_window
- Files: `ui/main_window.py` lines 171-177 (layout sync handlers)
- Fragility: If one panel's signal doesn't fire (blocked signals during updates), state can diverge
- Safe modification: Use a single shared layout state object in ImageManager or create a dedicated LayoutController
- Current workaround: `blockSignals()` used in both panels to prevent feedback loops

**Sprite list order sync on drag-reorder:**
- Problem: SpritesPanel emits sprites_changed when user reorders; main_window calls refresh(), which calls packer.get_positions()
- Files: `ui/sprites_panel.py` lines 137-144, `ui/main_window.py` lines 136-138
- Fragility: If undo/redo is triggered during drag, state can become inconsistent
- Safe modification: Serialize drag operation as atomic manager operation, not as side-effect of signal

## Design Debt

**PIL Image stored directly in SpriteEntry:**
- Problem: SpriteEntry holds full PIL Image objects; these are mutable and shared across undo/redo snapshots
- Files: `core/image_manager.py` lines 10-14 (SpriteEntry dataclass)
- Trade-off: Avoids copying on every operation (good for performance), but makes undo/redo fragile
- Consequence: If image is mutated in-place, all undo snapshots see the change
- Recommendation: Consider immutable image wrapper or explicit copy on mutation

**Undo/redo stores shallow copies of SpriteEntry list:**
- Problem: `_copy_list()` creates new SpriteEntry wrappers but reuses same PIL Image objects
- Files: `core/image_manager.py` lines 152-155
- Design choice: Explicit comment acknowledges this ("PIL images are shared")
- Risk: Very low if mutation is rare; all mutations currently go through trim_sprites() which creates new Images
- Safe if: Code review ensures no other code mutates entry.image in-place

---

*Concerns audit: 2025-03-16*
