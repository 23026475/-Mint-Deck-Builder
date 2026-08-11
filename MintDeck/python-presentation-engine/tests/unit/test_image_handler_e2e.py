from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from PIL import Image

from presentation_engine.handlers.image_catalog import ImageCatalog
from presentation_engine.handlers.image_handler import ImageHandler
from presentation_engine.handlers.image_placeholder_mapper import ImagePlaceholderMapper


from types import SimpleNamespace

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


class ImageHandlerEndToEndTests(unittest.TestCase):
    def make_image(self, directory: Path, name="sample.jpg", size=(800, 400)) -> Path:
        path = directory / name
        Image.new("RGB", size, color=(200, 100, 50)).save(path)
        return path

    def handler(self, base: Path):
        return ImageHandler(
            image_catalog=ImageCatalog(base),
            placeholder_mapper=ImagePlaceholderMapper(mappings={
                "image_right": {"picture": 20},
                "quote": {"headshot": 30},
                "team": {"member_picture": [20, 21, 22]},
                "logo_wall": {"logo": [20, 21, 22, 23]},
            }),
        )

    def test_multiple_images_and_repeated_image_in_one_deck_like_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.make_image(base, "shared.jpg")
            self.make_image(base, "headshot.png")
            image_slide = FakeSlide([FakePlaceholder(20)])
            quote_slide = FakeSlide([FakePlaceholder(30)])
            handler = self.handler(base)
            r1 = handler.insert_images(image_slide, {"archetype": "image_right", "fields": {"picture": "shared.jpg"}})
            r2 = handler.insert_images(quote_slide, {"archetype": "quote", "fields": {"headshot": "headshot.png"}})
            r3 = handler.insert_images(FakeSlide([FakePlaceholder(20)]), {"archetype": "image_right", "fields": {"picture": "shared.jpg"}})
            self.assertEqual(len(r1), 1)
            self.assertEqual(len(r2), 1)
            self.assertEqual(len(r3), 1)

    def test_placeholder_geometry_unchanged_and_letterboxed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.make_image(base, "wide.jpg", size=(800, 400))
            placeholder = FakePlaceholder(20, left=1, top=2, width=400, height=400)
            slide = FakeSlide([placeholder])
            self.handler(base).insert_images(slide, {"archetype": "image_right", "fields": {"picture": "wide.jpg"}})
            picture = placeholder.inserted[0]
            self.assertEqual((picture.left, picture.top, picture.width, picture.height), (1, 2, 400, 400))
            self.assertLess(picture.crop_top, 0.0)
            self.assertLess(picture.crop_bottom, 0.0)

    def test_team_and_logo_wall_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ["member1.jpg", "member2.jpg", "logo1.png", "logo2.png"]:
                self.make_image(base, name)
            handler = self.handler(base)
            team = FakeSlide([FakePlaceholder(20), FakePlaceholder(21)])
            logos = FakeSlide([FakePlaceholder(20), FakePlaceholder(21)])
            team_report = handler.insert_images(team, {"archetype": "team", "fields": {"members": [{"picture": "member1.jpg"}, {"picture": "member2.jpg"}]}})
            logo_report = handler.insert_images(logos, {"archetype": "logo_wall", "fields": {"logos": ["logo1.png", "logo2.png"]}})
            self.assertEqual(len(team_report), 2)
            self.assertEqual(len(logo_report), 2)

if __name__ == "__main__":
    unittest.main()
