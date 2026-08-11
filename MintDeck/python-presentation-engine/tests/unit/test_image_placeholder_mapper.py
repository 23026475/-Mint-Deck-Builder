from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from presentation_engine.handlers.image_placeholder_mapper import ImagePlaceholderMapper, ImagePlaceholderMappingNotFoundException


class ImagePlaceholderMapperTests(unittest.TestCase):
    def write_mapping(self, data):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "image-placeholder-baseline.json"
        path.write_text(json.dumps(data), encoding="utf8")
        return tmp, path

    def test_resolves_mapping_from_configuration(self):
        tmp, path = self.write_mapping({"quote": {"headshot": 30}})
        self.addCleanup(tmp.cleanup)
        mapping = ImagePlaceholderMapper(path).resolve("quote", "headshot")
        self.assertEqual(mapping.idx, 30)

    def test_resolves_occurrence_mapping(self):
        tmp, path = self.write_mapping({"team": {"member_picture": [20, 21, 22]}})
        self.addCleanup(tmp.cleanup)
        mapping = ImagePlaceholderMapper(path).resolve("team", "member_picture", 1)
        self.assertEqual(mapping.idx, 21)

    def test_missing_mapping_raises_clear_exception(self):
        tmp, path = self.write_mapping({"quote": {"headshot": 30}})
        self.addCleanup(tmp.cleanup)
        with self.assertRaises(ImagePlaceholderMappingNotFoundException):
            ImagePlaceholderMapper(path).resolve("quote", "logo")


if __name__ == "__main__":
    unittest.main()
