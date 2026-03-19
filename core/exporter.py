from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


class Exporter:
    def export_png(self, sheet: Image.Image, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(str(p), "PNG")

    def export_json(self, metadata: dict, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def export_both(
        self,
        sheet: Image.Image,
        metadata: dict,
        png_path: str | Path,
    ) -> None:
        """Export PNG and the matching JSON alongside it."""
        png_path = Path(png_path)
        self.export_png(sheet, png_path)
        json_path = png_path.with_suffix(".json")
        self.export_json(metadata, json_path)
