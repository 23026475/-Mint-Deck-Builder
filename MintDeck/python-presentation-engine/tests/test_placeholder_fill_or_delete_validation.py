"""Unit tests for fill-or-delete and per-archetype validation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from presentation_engine.builders.placeholder_builder import (
    PlaceholderBuilder,
    PlaceholderValidationException,
)


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
    def __init__(self, idx, text="PROMPT", has_text_frame=True, ph_type="TEXT", is_placeholder=True):
        self.text = text
        self.has_text_frame = has_text_frame
        self.is_placeholder = is_placeholder
        self.placeholder_format = SimpleNamespace(idx=idx, type=ph_type)
        self._element = FakeElement(self)
        self.name = f"Placeholder {idx}"


class FakeSlide:
    def __init__(self, shapes):
        self.shapes = shapes
        self.placeholders = [shape for shape in shapes if shape.is_placeholder]
        parent = FakeParent(self.shapes)
        for shape in self.shapes:
            shape._element.parent = parent

    def indexes(self):
        return {shape.placeholder_format.idx for shape in self.shapes if shape.is_placeholder}


class FillOrDeleteAndValidationTests(unittest.TestCase):
    def test_optional_text_placeholder_is_deleted(self):
        slide = FakeSlide([FakeShape(0), FakeShape(11), FakeShape(20), FakeShape(40)])
        PlaceholderBuilder().populate(
            slide,
            {
                "archetype": "process_flow",
                "action_title": "Four workstreams move adoption",
                "fields": {"steps": [{"title": "Prepare"}]},
            },
        )
        self.assertNotIn(40, slide.indexes())

    def test_media_placeholder_remains_in_place(self):
        slide = FakeSlide([
            FakeShape(0),
            FakeShape(11),
            FakeShape(12),
            FakeShape(20, has_text_frame=False, ph_type="PICTURE"),
        ])
        PlaceholderBuilder().populate(
            slide,
            {
                "archetype": "image_right",
                "action_title": "Ownership keeps adoption focused",
                "fields": {"body": "A short body line."},
            },
        )
        self.assertIn(20, slide.indexes())

    def test_cover_dark_title_validation(self):
        slide = FakeSlide([FakeShape(0), FakeShape(2), FakeShape(3), FakeShape(4), FakeShape(11)])
        with self.assertRaisesRegex(PlaceholderValidationException, "45 characters"):
            PlaceholderBuilder().populate(
                slide,
                {
                    "archetype": "cover_dark",
                    "fields": {"title": "This cover dark title is intentionally far too long"},
                },
            )

    def test_chart_lead_in_validation(self):
        slide = FakeSlide([
            FakeShape(0),
            FakeShape(10, has_text_frame=False, ph_type="CHART"),
            FakeShape(11),
            FakeShape(13),
            FakeShape(14),
            FakeShape(41),
        ])
        with self.assertRaisesRegex(PlaceholderValidationException, "60 characters"):
            PlaceholderBuilder().populate(
                slide,
                {
                    "archetype": "chart",
                    "action_title": "This chart lead in sentence is intentionally longer than the allowed sixty character limit",
                    "fields": {"takeaway": "Short takeaway."},
                },
            )

    def test_chart_takeaway_validation(self):
        slide = FakeSlide([
            FakeShape(0),
            FakeShape(10, has_text_frame=False, ph_type="CHART"),
            FakeShape(11),
            FakeShape(13),
            FakeShape(14),
            FakeShape(41),
        ])
        with self.assertRaisesRegex(PlaceholderValidationException, "25 words"):
            PlaceholderBuilder().populate(
                slide,
                {
                    "archetype": "chart",
                    "action_title": "Adoption rises through pilot",
                    "fields": {
                        "takeaway": (
                            "This takeaway body intentionally contains more than twenty five words "
                            "so the validation rule rejects the chart content before the slide is "
                            "generated and prevents overcrowded chart commentary from entering the deck."
                        )
                    },
                },
            )


if __name__ == "__main__":
    unittest.main()
