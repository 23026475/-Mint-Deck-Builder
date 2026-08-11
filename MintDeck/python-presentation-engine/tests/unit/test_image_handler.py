from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from presentation_engine.handlers.image_catalog import ImageCatalog
from presentation_engine.handlers.image_handler import ImageHandler, ImagePlaceholderNotFoundException
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
    def __init__(self, idx, left=10, top=20, width=400, height=200):
        self.placeholder_format = SimpleNamespace(idx=idx, type="PICTURE")
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.inserted = []

    def insert_picture(self, path):
        picture = FakePicture(self.left, self.top, self.width, self.height)
        self.inserted.append(picture)
        return picture


class FakeSlide:
    def __init__(self, placeholders):
        self.placeholders = placeholders


class ImageHandlerOrchestrationTests(unittest.TestCase):
    def make_image(self, directory: Path, name="sample.jpg", size=(800, 400)) -> Path:
        path = directory / name
        Image.new("RGB", size, color=(200, 100, 50)).save(path)
        return path

    def handler(self, base: Path, mappings):
        return ImageHandler(
            image_catalog=ImageCatalog(base),
            placeholder_mapper=ImagePlaceholderMapper(mappings=mappings),
        )

    def test_image_insertion_succeeds_through_mapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image = self.make_image(base, "hero.jpg")
            placeholder = FakePlaceholder(20)
            slide = FakeSlide([placeholder])
            report = self.handler(base, {"image_right": {"picture": 20}}).insert_images(
                slide,
                {"archetype": "image_right", "fields": {"picture": image.name}},
            )
            self.assertEqual(report[0]["placeholder_idx"], 20)
            self.assertEqual(len(placeholder.inserted), 1)

    def test_missing_placeholder_raises_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image = self.make_image(base, "hero.jpg")
            slide = FakeSlide([FakePlaceholder(99)])
            with self.assertRaises(ImagePlaceholderNotFoundException):
                self.handler(base, {"image_right": {"picture": 20}}).insert_images(
                    slide,
                    {"archetype": "image_right", "fields": {"picture": image.name}},
                )

    def test_letterboxing_preserves_placeholder_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image = self.make_image(base, "hero.jpg", size=(800, 400))
            placeholder = FakePlaceholder(20, left=1, top=2, width=400, height=400)
            slide = FakeSlide([placeholder])
            self.handler(base, {"image_right": {"picture": 20}}).insert_images(
                slide,
                {"archetype": "image_right", "fields": {"picture": image.name}},
            )
            picture = placeholder.inserted[0]
            self.assertEqual((picture.left, picture.top, picture.width, picture.height), (1, 2, 400, 400))
            self.assertLess(picture.crop_top, 0.0)
            self.assertLess(picture.crop_bottom, 0.0)


if __name__ == "__main__":
    unittest.main()
