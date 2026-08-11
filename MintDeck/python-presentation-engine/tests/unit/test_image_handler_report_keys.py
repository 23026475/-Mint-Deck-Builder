from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from presentation_engine.handlers.image_catalog import ImageCatalog
from presentation_engine.handlers.image_handler import ImageHandler
from presentation_engine.handlers.image_placeholder_mapper import ImagePlaceholderMapper


class FakePicture:
    def __init__(self, left, top, width, height):
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.crop_left = 0.0
        self.crop_right = 0.0
        self.crop_top = 0.0
        self.crop_bottom = 0.0


class FakePlaceholder:
    def __init__(self, idx):
        self.placeholder_format = SimpleNamespace(idx=idx, type="PICTURE")
        self.left = 1
        self.top = 2
        self.width = 400
        self.height = 200

    def insert_picture(self, path):
        return FakePicture(self.left, self.top, self.width, self.height)


class FakeSlide:
    def __init__(self, placeholders):
        self.placeholders = placeholders


class ImageHandlerReportKeysTests(unittest.TestCase):
    def test_report_contains_legacy_and_resolved_placeholder_idx_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image_path = base / "hero.jpg"
            Image.new("RGB", (800, 400), color=(1, 2, 3)).save(image_path)
            handler = ImageHandler(
                image_catalog=ImageCatalog(base),
                placeholder_mapper=ImagePlaceholderMapper(mappings={"image_right": {"picture": 20}}),
            )

            report = handler.insert_images(
                FakeSlide([FakePlaceholder(20)]),
                {"archetype": "image_right", "fields": {"picture": "hero.jpg"}},
            )

            self.assertEqual(report[0]["resolved_placeholder_idx"], 20)
            self.assertEqual(report[0]["placeholder_idx"], 20)


if __name__ == "__main__":
    unittest.main()
