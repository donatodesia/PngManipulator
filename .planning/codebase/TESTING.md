# Testing Patterns

**Analysis Date:** 2026-03-16

## Test Framework

**Runner:**
- Not detected: No pytest, unittest, or test runner configured
- No `pytest.ini`, `setup.cfg`, `tox.ini`, or `conftest.py` found
- No test files present in repository

**Assertion Library:**
- Not applicable (no tests present)

**Run Commands:**
- No test commands available
- `python main.py` runs the application

## Test File Organization

**Location:**
- No test directory structure (`tests/`, `test/`, or co-located `*_test.py` files)
- No test files detected anywhere in repository

**Naming:**
- Not applicable

**Structure:**
- Not applicable

## Current Testing State

**Status:**
- Zero automated tests
- Application relies on manual testing via GUI
- No unit tests for core logic
- No integration tests for workflows

## Testing Opportunities

**Priority Areas for Test Implementation:**

**1. Core Logic (High Priority):**
- `core/sprite_detector.py`:
  - `detect_regular()` with various grid sizes and empty cell stripping
  - `detect_irregular()` projection-based detection edge cases
  - `auto_bg_color()` corner sampling logic
  - `_make_mask()` transparency vs solid color modes
  - `_replace_bg_with_alpha()` RGB matching and alpha replacement

- `core/image_manager.py`:
  - `add_sprites()`, `remove()`, `move()`, `reorder()` operations
  - Undo/redo stack depth limits (`MAX_HISTORY = 50`)
  - Snapshot isolation (`_copy_list()` shallow copy behavior)
  - `trim_sprites()` with multiple sprite indices
  - Edge cases: empty manager, single sprite, out-of-bounds indices

- `core/packer.py`:
  - `_layout_grid()` with various column counts
  - `_layout_horizontal()` group-by-source logic
  - `_layout_vertical()` group-by-source logic
  - `pack()` sprite positioning and cell centering
  - `metadata()` Phaser JSON structure correctness
  - `get_positions()` coordinate accuracy

- `core/trimmer.py`:
  - `get_content_bbox()` empty image handling (returns `None`)
  - `compute_safe_margins()` across multiple sprites
  - `apply_trim()` dimension validation

- `core/exporter.py`:
  - `export_png()` file creation and parent directory handling
  - `export_json()` JSON structure and UTF-8 encoding
  - `export_both()` dual file creation and naming

**2. PyQt6 Signal Flow (Medium Priority):**
- Sprite detection workflow: load → detect → manager update → panel refresh
- Layout mode synchronization between SourcePanel and OutputToolbar
- Undo/redo action enable/disable states
- Trim operation state propagation

**3. Edge Cases (Medium Priority):**
- Empty spritesheets
- Single sprite loading
- Very large cell sizes vs sheet dimensions
- Invalid file paths
- Corrupted image files

## Recommended Test Structure

**Unit Test Pattern:**
```python
import unittest
from PIL import Image

class TestSpriteDetector(unittest.TestCase):
    def setUp(self):
        # Create test image
        self.test_img = Image.new('RGBA', (64, 64), (0, 255, 0, 255))

    def test_detect_regular_2x2_grid(self):
        result = detect_regular(self.test_img, rows=2, cols=2)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].source_rect, (0, 0, 32, 32))

    def tearDown(self):
        pass
```

**Suggested Test Runner:**
- pytest (modern, simple, good fixture support)
- unittest (standard library, no additional dependency)

**Fixture/Factory Pattern:**
```python
# test_fixtures.py
def create_test_spritesheet(width=128, height=128, color=(0, 255, 0)):
    return Image.new('RGBA', (width, height), color + (255,))

def create_sprite_entry(name="sprite_0", width=32, height=32):
    img = Image.new('RGBA', (width, height), (255, 0, 0, 255))
    return SpriteEntry(name=name, image=img, source_file="test.png")
```

## Mocking Strategy

**What to Mock:**
- File I/O: Use `pathlib.Path.write_text()` with temporary directories
- PyQt6 signals: Test by checking state changes, not signal emission
- PIL Image operations: Create small test images, keep tests fast

**What NOT to Mock:**
- Core algorithms (sprite detection, layout, trimming)
- PIL Image operations (they're fast and reliable)
- numpy operations (central to algorithm correctness)
- ImageManager state transitions (test real undo/redo)

**Example:**
```python
from pathlib import Path
import tempfile

def test_export_png_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = Exporter()
        img = Image.new('RGBA', (64, 64))
        path = Path(tmpdir) / "test.png"
        exporter.export_png(img, path)
        self.assertTrue(path.exists())
```

## Coverage Recommendations

**Target:** 80% minimum for core modules

**Gaps:**
- `core/sprite_detector.py`: No tests for detection algorithms
- `core/image_manager.py`: No tests for state management
- `core/packer.py`: No tests for layout calculations
- `core/trimmer.py`: No tests for margin computation
- `core/exporter.py`: No tests for file writing
- `ui/*.py`: Integration tests only (GUI testing is harder, lower priority)

## Testing Best Practices for This Codebase

**1. Image Comparison:**
```python
def assert_image_equal(img1, img2):
    arr1 = np.array(img1.convert('RGBA'))
    arr2 = np.array(img2.convert('RGBA'))
    np.testing.assert_array_equal(arr1, arr2)
```

**2. Coordinate Verification:**
```python
def test_layout_positions():
    packer = GridPacker()
    manager = ImageManager()
    # Add test sprites
    positions = packer.get_positions(manager, columns=2, cell_w=32, cell_h=32)
    self.assertEqual(positions[0], (0, 0))
    self.assertEqual(positions[1], (32, 0))
    self.assertEqual(positions[2], (0, 32))
```

**3. State Machine Testing (Undo/Redo):**
```python
def test_undo_redo_sequence():
    manager = ImageManager()
    manager.add_sprites([sprite1])
    manager.add_sprites([sprite2])  # State 1
    self.assertTrue(manager.undo())  # Back to empty
    self.assertTrue(manager.redo())  # Forward to State 1
    self.assertEqual(len(manager.sprites), 2)
```

**4. PyQt6 Signal Testing:**
```python
def test_sprites_detected_signal(self):
    panel = SourcePanel()
    signal_spy = unittest.mock.Mock()
    panel.sprites_detected.connect(signal_spy)
    panel.sprites_detected.emit([sprite1, sprite2])
    signal_spy.assert_called_once_with([sprite1, sprite2])
```

## Implementation Roadmap

**Phase 1 - Core Logic (10–15 tests):**
- `test_sprite_detector.py`: Detection algorithms
- `test_image_manager.py`: State management

**Phase 2 - Layout & Export (8–10 tests):**
- `test_packer.py`: Grid layout algorithms
- `test_exporter.py`: File I/O

**Phase 3 - Trimming (5–7 tests):**
- `test_trimmer.py`: Margin computation and application

**Phase 4 - Integration (10+ tests):**
- PyQt6 workflow tests (signal chains)
- End-to-end sprite detection → pack → export

## Performance Testing

**Not implemented:** Benchmarks for detection on large spritesheets

**Recommended baselines:**
- Irregular detection on 2048×2048 sheet: < 500ms
- Grid layout with 1000 sprites: < 100ms
- PNG export: dependent on sheet size, not algorithm

---

*Testing analysis: 2026-03-16*
