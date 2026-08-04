
"""Unit tests for placeholder cleanup behavior."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from presentation_engine.builders.placeholder_builder import PlaceholderBuilder


class FakeParent:
    def __init__(self, shapes):
        self.shapes = shapes
    def remove(self, element):
        if element.shape in self.shapes:
            self.shapes.remove(element.shape)


class FakeElement:
    def __init__(self, shape):
        self.shape = shape
        self.parent = None
    def getparent(self):
        return self.parent


class FakeShape:
    def __init__(self, idx=None, text="", has_text_frame=True, is_placeholder=True, ph_type="TEXT", name=None):
        self.name = name or f"Shape {idx}"
        self.text = text
        self.has_text_frame = has_text_frame
        self.is_placeholder = is_placeholder
        self.placeholder_format = SimpleNamespace(idx=idx, type=ph_type) if idx is not None else None
        self._element = FakeElement(self)


class FakeSlide:
    def __init__(self, shapes):
        self.shapes = shapes
        self.placeholders = [shape for shape in shapes if shape.is_placeholder and shape.placeholder_format is not None]
        parent = FakeParent(self.shapes)
        for shape in self.shapes:
            shape._element.parent = parent


class PlaceholderCleanupTests(unittest.TestCase):
    def test_removes_default_prompt_text_after_population(self):
        slide = FakeSlide([
            FakeShape(0, "Click to edit Master title style"),
            FakeShape(11, "Click to edit Master text styles"),
            FakeShape(None, "Click to edit Master text styles", is_placeholder=False, name="Prompt Box"),
        ])
        PlaceholderBuilder().populate(slide, {"archetype": "statement", "action_title": "Governed adoption matters", "fields": {"kicker": "SHIFT"}})
        texts = [shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)]
        self.assertIn("Governed adoption matters", texts)
        self.assertIn("SHIFT", texts)
        self.assertNotIn("Click to edit Master text styles", texts)

    def test_preserves_business_text_containing_prompt_word(self):
        slide = FakeSlide([
            FakeShape(0, "Click to edit Master title style"),
            FakeShape(11, "KICKER"),
            FakeShape(None, "Prompt coaching is a valid adoption activity", is_placeholder=False),
        ])
        PlaceholderBuilder().populate(slide, {"archetype": "statement", "action_title": "Governed adoption matters", "fields": {"kicker": "SHIFT"}})
        texts = [shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)]
        self.assertIn("Prompt coaching is a valid adoption activity", texts)

    def test_preserves_media_placeholders(self):
        media = FakeShape(20, "", has_text_frame=False, ph_type="PICTURE", name="Picture Placeholder")
        slide = FakeSlide([
            FakeShape(0, "Click to edit Master title style"),
            FakeShape(11, "Click to edit Master text styles"),
            FakeShape(12, "Click to edit Master text styles"),
            media,
        ])
        PlaceholderBuilder().populate(slide, {"archetype": "image_right", "action_title": "Image layout title", "fields": {"body": "Body text"}})
        self.assertIn(media, slide.shapes)
        self.assertTrue(any(item["idx"] == 20 for item in PlaceholderBuilder().cleanup_reports) is False)


if __name__ == "__main__":
    unittest.main()
