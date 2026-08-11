from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from presentation_engine.handlers.image_catalog import ImageCatalog, ImageCatalogNotFoundException, ImageCatalogUnsupportedFormatException


class ImageCatalogTests(unittest.TestCase):
    def make_image(self, directory: Path, name="Sample.JPG") -> Path:
        path = directory / name
        Image.new("RGB", (10, 10), color=(1, 2, 3)).save(path)
        return path

    def test_resolves_filenames_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            actual = self.make_image(base, "Sample.JPG")
            resolved = ImageCatalog(base).resolve("sample.jpg")
            self.assertTrue(resolved.samefile(actual))

    def test_caches_resolved_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            actual = self.make_image(base, "sample.jpg")
            catalog = ImageCatalog(base)
            first = catalog.resolve("sample.jpg")
            actual.unlink()
            second = catalog.resolve("sample.jpg")
            self.assertEqual(first, second)

    def test_missing_image_raises_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ImageCatalogNotFoundException):
                ImageCatalog(tmp).resolve("missing.jpg")

    def test_unsupported_extension_raises_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ImageCatalogUnsupportedFormatException):
                ImageCatalog(tmp).resolve("bad.gif")


if __name__ == "__main__":
    unittest.main()
