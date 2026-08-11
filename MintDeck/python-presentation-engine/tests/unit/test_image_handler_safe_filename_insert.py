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
    def __init__(self, inserted_path: str) -> None:
        self.inserted_path = inserted_path
        self.left = None
        self.top = None
        self.width = None
        self.height = None
        self.crop_left = None
        self.crop_right = None
        self.crop_top = None
        self.crop_bottom = None


class FakePicturePlaceholder:
    def __init__(self, idx: int) -> None:
        self.placeholder_format = SimpleNamespace(idx=idx, type="PICTURE")
        self.left = 10
        self.top = 20
        self.width = 300
        self.height = 200
        self.inserted_paths: list[str] = []

    def insert_picture(self, image_file: str) -> FakePicture:
        self.inserted_paths.append(image_file)
        return FakePicture(image_file)


class FakeSlide:
    def __init__(self, placeholder: FakePicturePlaceholder) -> None:
        self.placeholders = [placeholder]


class SafeFilenameInsertionTests(unittest.TestCase):
    def test_ampersand_filename_uses_safe_temporary_path_and_reports_original_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image_dir = base / "images"
            image_dir.mkdir()

            original = image_dir / "FY27 People Collaborating & Corporate (69).JPG"
            Image.new("RGB", (120, 80), color="blue").save(original)

            mapper_config = base / "image-placeholder-baseline.json"
            mapper_config.write_text('{"quote": {"headshot": 30}}', encoding="utf8")

            placeholder = FakePicturePlaceholder(idx=30)
            slide = FakeSlide(placeholder)

            handler = ImageHandler(
                image_catalog=ImageCatalog(image_library_dir=image_dir),
                placeholder_mapper=ImagePlaceholderMapper(mapping_path=mapper_config),
            )

            report = handler.insert_images(
                slide,
                {
                    "archetype": "quote",
                    "fields": {
                        "quote": "Validation quote.",
                        "attribution": "Validation",
                        "headshot": original.name,
                    },
                },
            )

            self.assertEqual(len(report), 1)
            self.assertEqual(Path(report[0]["resolved_filename"]).resolve(), original.resolve())
            self.assertEqual(report[0]["placeholder_idx"], 30)
            self.assertEqual(report[0]["resolved_placeholder_idx"], 30)

            self.assertEqual(len(placeholder.inserted_paths), 1)
            inserted_path = Path(placeholder.inserted_paths[0])
            self.assertEqual(inserted_path.name, "image.jpg")
            self.assertNotIn("&", inserted_path.name)
            self.assertTrue(original.exists())
            self.assertEqual(original.name, "FY27 People Collaborating & Corporate (69).JPG")
            self.assertFalse(inserted_path.exists())
            self.assertEqual(placeholder.left, 10)
            self.assertEqual(placeholder.top, 20)
            self.assertEqual(placeholder.width, 300)
            self.assertEqual(placeholder.height, 200)

    def test_spaces_and_parentheses_filename_continues_to_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image_dir = base / "images"
            image_dir.mkdir()

            original = image_dir / "FY27 Ai Image (1).jpg"
            Image.new("RGB", (120, 80), color="green").save(original)

            mapper_config = base / "image-placeholder-baseline.json"
            mapper_config.write_text('{"image_right": {"picture": 20}}', encoding="utf8")

            placeholder = FakePicturePlaceholder(idx=20)
            slide = FakeSlide(placeholder)

            handler = ImageHandler(
                image_catalog=ImageCatalog(image_library_dir=image_dir),
                placeholder_mapper=ImagePlaceholderMapper(mapping_path=mapper_config),
            )

            report = handler.insert_images(
                slide,
                {
                    "archetype": "image_right",
                    "fields": {"picture": original.name},
                },
            )

            self.assertEqual(len(report), 1)
            self.assertEqual(Path(report[0]["resolved_filename"]).resolve(), original.resolve())
            self.assertEqual(len(placeholder.inserted_paths), 1)
            self.assertEqual(Path(placeholder.inserted_paths[0]).name, "image.jpg")
            self.assertEqual(placeholder.left, 10)
            self.assertEqual(placeholder.top, 20)
            self.assertEqual(placeholder.width, 300)
            self.assertEqual(placeholder.height, 200)


if __name__ == "__main__":
    unittest.main()
