from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from PIL import Image

from presentation_engine.handlers.image_catalog import (
    ImageCatalog,
    ImageCatalogDuplicateFilenameException,
    ImageCatalogNotFoundException,
    ImageCatalogUnreadableException,
    ImageCatalogUnsupportedFormatException,
)

class ImageCatalogEndToEndTests(unittest.TestCase):
    def make_image(self, directory: Path, name="sample.jpg", size=(10, 10)) -> Path:
        path = directory / name
        Image.new("RGB", size, color=(1, 2, 3)).save(path)
        return path

    def test_cached_lookup_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image = self.make_image(base, "Sample.JPG", size=(20, 30))
            catalog = ImageCatalog(base)
            resolved = catalog.resolve("sample.jpg")
            meta = catalog.metadata(resolved)
            image.unlink()
            self.assertEqual(catalog.resolve("sample.jpg"), resolved)
            self.assertEqual((meta.width, meta.height), (20, 30))
            self.assertEqual(meta.format, "jpeg")

    def test_duplicate_filename_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "a").mkdir()
            (base / "b").mkdir()
            self.make_image(base / "a", "logo.png")
            self.make_image(base / "b", "LOGO.PNG")
            with self.assertRaises(ImageCatalogDuplicateFilenameException):
                ImageCatalog(base).resolve("logo.png")

    def test_unsupported_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ImageCatalogUnsupportedFormatException):
                ImageCatalog(tmp).resolve("bad.gif")

    def test_missing_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ImageCatalogNotFoundException):
                ImageCatalog(tmp).resolve("missing.jpg")

    def test_corrupt_image_metadata_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bad = base / "bad.jpg"
            bad.write_bytes(b"not really an image")
            catalog = ImageCatalog(base)
            with self.assertRaises(ImageCatalogUnreadableException):
                catalog.metadata(bad)

if __name__ == "__main__":
    unittest.main()
