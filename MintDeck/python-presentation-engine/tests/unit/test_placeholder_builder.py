"""Unit tests for PlaceholderBuilder."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from presentation_engine.builders.placeholder_builder import PlaceholderBuilder, PlaceholderBuilderException


class FakeParent:
    def __init__(self, placeholders):
        self.placeholders = placeholders

    def remove(self, element):
        placeholder = element.placeholder
        if placeholder in self.placeholders:
            self.placeholders.remove(placeholder)


class FakeElement:
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.parent = None

    def getparent(self):
        return self.parent


class FakePlaceholder:
    def __init__(self, idx, text="PROMPT", has_text_frame=True, font_marker="template-format"):
        self.placeholder_format = SimpleNamespace(idx=idx)
        self.text = text
        self.has_text_frame = has_text_frame
        self.font_marker = font_marker
        self._element = FakeElement(self)


class FakeSlide:
    def __init__(self, indexes):
        self.placeholders = [FakePlaceholder(idx) for idx in indexes]
        parent = FakeParent(self.placeholders)
        for placeholder in self.placeholders:
            placeholder._element.parent = parent

    def by_idx(self, idx):
        for placeholder in self.placeholders:
            if placeholder.placeholder_format.idx == idx:
                return placeholder
        raise KeyError(idx)

    def indexes(self):
        return {p.placeholder_format.idx for p in self.placeholders}


class PlaceholderBuilderTests(unittest.TestCase):
    def test_cover_placeholders_populate_correctly(self):
        slide = FakeSlide([0, 2, 3, 4, 11, 99])
        builder = PlaceholderBuilder()

        builder.populate(
            slide,
            {
                "archetype": "cover",
                "fields": {
                    "title": "Microsoft 365 Copilot Adoption",
                    "subtitle": "Turning AI assistance into measurable productivity gains",
                    "kicker": "PREPARED FOR CONTOSO MANUFACTURING",
                },
            },
        )

        self.assertEqual(slide.by_idx(0).text, "Microsoft 365 Copilot Adoption")
        self.assertEqual(slide.by_idx(2).text, "Turning AI assistance into measurable productivity gains")
        self.assertEqual(slide.by_idx(11).text, "PREPARED FOR CONTOSO MANUFACTURING")
        self.assertNotIn(3, slide.indexes())
        self.assertNotIn(4, slide.indexes())
        self.assertNotIn(99, slide.indexes())

    def test_cards3_populates_all_three_cards_correctly(self):
        slide = FakeSlide([0, 11, 20, 21, 22, 23, 24, 25, 40])
        builder = PlaceholderBuilder()

        builder.populate(
            slide,
            {
                "archetype": "cards3",
                "action_title": "Three barriers are slowing Copilot value across the business.",
                "fields": {
                    "kicker": "THE STAKES",
                    "cards": [
                        {"title": "Low Awareness", "body": "Employees are unsure where Copilot delivers immediate value."},
                        {"title": "Inconsistent Usage", "body": "Adoption varies widely between teams and functions."},
                        {"title": "Governance Concerns", "body": "Data access and compliance questions delay rollout."},
                    ],
                },
            },
        )

        self.assertEqual(slide.by_idx(0).text, "Three barriers are slowing Copilot value across the business.")
        self.assertEqual(slide.by_idx(11).text, "THE STAKES")
        self.assertEqual(slide.by_idx(20).text, "Low Awareness")
        self.assertEqual(slide.by_idx(21).text, "Employees are unsure where Copilot delivers immediate value.")
        self.assertEqual(slide.by_idx(22).text, "Inconsistent Usage")
        self.assertEqual(slide.by_idx(23).text, "Adoption varies widely between teams and functions.")
        self.assertEqual(slide.by_idx(24).text, "Governance Concerns")
        self.assertEqual(slide.by_idx(25).text, "Data access and compliance questions delay rollout.")

    def test_closing_populates_steps_correctly(self):
        slide = FakeSlide([0, 11, 12, 13])
        builder = PlaceholderBuilder()

        builder.populate(
            slide,
            {
                "archetype": "closing",
                "action_title": "The next step is launching a focused adoption pilot.",
                "fields": {
                    "steps": [
                        "Confirm pilot scope and success measures",
                        "Select priority business scenarios",
                        "Enable pilot users and champions",
                    ]
                },
            },
        )

        self.assertEqual(slide.by_idx(0).text, "The next step is launching a focused adoption pilot.")
        self.assertEqual(
            slide.by_idx(12).text,
            "Confirm pilot scope and success measures\nSelect priority business scenarios\nEnable pilot users and champions",
        )
        self.assertNotIn(11, slide.indexes())
        self.assertNotIn(13, slide.indexes())

    def test_optional_callout_is_removed_when_absent(self):
        slide = FakeSlide([0, 11, 20, 21, 22, 23, 24, 25, 40])
        builder = PlaceholderBuilder()

        builder.populate(
            slide,
            {
                "archetype": "cards3",
                "action_title": "Three barriers are slowing Copilot value across the business.",
                "fields": {
                    "kicker": "THE STAKES",
                    "cards": [
                        {"title": "One", "body": "Body one"},
                        {"title": "Two", "body": "Body two"},
                        {"title": "Three", "body": "Body three"},
                    ],
                },
            },
        )

        self.assertNotIn(40, slide.indexes())

    def test_missing_required_placeholder_idx_raises_exception(self):
        slide = FakeSlide([2, 11])
        builder = PlaceholderBuilder()

        with self.assertRaisesRegex(PlaceholderBuilderException, "Required placeholder idx 0"):
            builder.populate(
                slide,
                {
                    "archetype": "cover",
                    "fields": {
                        "title": "Title",
                        "subtitle": "Subtitle",
                        "kicker": "Kicker",
                    },
                },
            )

    def test_existing_formatting_is_preserved_only_text_changes(self):
        slide = FakeSlide([0, 2, 11])
        original_marker = slide.by_idx(0).font_marker
        builder = PlaceholderBuilder()

        builder.populate(
            slide,
            {
                "archetype": "cover",
                "fields": {
                    "title": "Title",
                    "subtitle": "Subtitle",
                    "kicker": "Kicker",
                },
            },
        )

        self.assertEqual(slide.by_idx(0).text, "Title")
        self.assertEqual(slide.by_idx(0).font_marker, original_marker)


if __name__ == "__main__":
    unittest.main()
