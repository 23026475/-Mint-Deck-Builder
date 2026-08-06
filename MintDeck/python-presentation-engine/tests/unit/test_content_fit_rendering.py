"""Unit tests for render-safe text preparation."""

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

    def by_idx(self, idx):
        for shape in self.shapes:
            if shape.placeholder_format.idx == idx:
                return shape
        raise KeyError(idx)


class ContentFitRenderingTests(unittest.TestCase):
    def test_cover_dark_valid_title_can_be_wrapped_without_contract_change(self):
        slide = FakeSlide([
            FakeShape(0),
            FakeShape(2),
            FakeShape(3),
            FakeShape(4),
            FakeShape(11),
        ])

        PlaceholderBuilder().populate(
            slide,
            {
                "archetype": "cover_dark",
                "fields": {
                    "title": "Exact-match validation is ready",
                    "subtitle": "Baseline and template alignment",
                    "abstract": "Supported layouts are generating with populated text.",
                    "kicker": "VALIDATION",
                },
            },
        )

        self.assertEqual(
            slide.by_idx(0).text,
            "Exact-match validation is ready",
        )

    def test_cover_dark_invalid_title_is_still_rejected(self):
        slide = FakeSlide([
            FakeShape(0),
            FakeShape(2),
            FakeShape(3),
            FakeShape(4),
            FakeShape(11),
        ])

        with self.assertRaisesRegex(PlaceholderValidationException, "45 characters"):
            PlaceholderBuilder().populate(
                slide,
                {
                    "archetype": "cover_dark",
                    "fields": {
                        "title": "This cover dark title is intentionally far too long",
                    },
                },
            )

    def test_summary_cta_cta_can_wrap_without_contract_change(self):
        slide = FakeSlide([
            FakeShape(0),
            FakeShape(2),
            FakeShape(3),
            FakeShape(4),
        ])

        PlaceholderBuilder().populate(
            slide,
            {
                "archetype": "summary_cta",
                "action_title": "The validation package is ready for review.",
                "fields": {
                    "subheading": "Exact-match archetype coverage",
                    "body": "The generated deck confirms layout resolution, placeholder population and clean package generation.",
                    "cta": "Review output and approve next implementation phase.",
                },
            },
        )

        self.assertEqual(
            slide.by_idx(4).text,
            "Review output and approve\nnext implementation phase.",
        )


if __name__ == "__main__":
    unittest.main()