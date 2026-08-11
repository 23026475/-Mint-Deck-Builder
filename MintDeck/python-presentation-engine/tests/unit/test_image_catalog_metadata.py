from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from presentation_engine.handlers.image_catalog import ImageCatalog


class ImageCatalogMetadataTests(unittest.TestCase):
    def make_image(self, directory: Path, name="FY27 Ai Image (1).jpg", size=(100, 50)) -> Path:
        path = directory / name
        Image.new("RGB", size, color=(1, 2, 3)).save(path)
        return path

    def test_reads_metadata_json_for_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image = self.make_image(base, "FY27 Ai Image (1).jpg", size=(100, 50))
            metadata_path = base / "images.json"
            metadata_path.write_text(json.dumps({
                image.name: {
                    "category": "ai",
                    "orientation": "landscape",
                    "width": 7373,
                    "height": 4147,
                    "tags": ["artificial intelligence", "cloud computing"],
                }
            }), encoding="utf8")

            metadata = ImageCatalog(base, metadata_path=metadata_path).metadata(image.name)

            self.assertEqual(metadata.width, 7373)
            self.assertEqual(metadata.height, 4147)
            self.assertEqual(metadata.category, "ai")
            self.assertEqual(metadata.orientation, "landscape")
            self.assertIn("cloud computing", metadata.tags)

    def test_metadata_lookup_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image = self.make_image(base, "FY27 Design Elements (1).png", size=(20, 30))
            metadata_path = base / "images.json"
            metadata_path.write_text(json.dumps({
                "FY27 Design Elements (1).png": {
                    "category": "uncategorized",
                    "orientation": "portrait",
                    "width": 1522,
                    "height": 2887,
                    "tags": ["screenshot"],
                }
            }), encoding="utf8")

            metadata = ImageCatalog(base, metadata_path=metadata_path).metadata("fy27 design elements (1).PNG")

            self.assertEqual(metadata.path, image.resolve())
            self.assertEqual(metadata.orientation, "portrait")
            self.assertEqual(metadata.width, 1522)

    def test_falls_back_to_file_dimensions_when_metadata_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image = self.make_image(base, "sample.jpg", size=(44, 22))
            metadata = ImageCatalog(base, metadata_path=base / "images.json").metadata(image.name)
            self.assertEqual((metadata.width, metadata.height), (44, 22))
            self.assertEqual(metadata.orientation, "landscape")


if __name__ == "__main__":
    unittest.main()
