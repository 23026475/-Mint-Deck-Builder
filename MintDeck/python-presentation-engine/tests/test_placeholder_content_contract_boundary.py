"""Contract enforcement at the PlaceholderBuilder mutation boundary."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from presentation_engine.builders.placeholder_builder import (
    PlaceholderBuilder,
    PlaceholderDefinition,
    PlaceholderValidationException,
)
from presentation_engine.services.placeholder_content_limits import (
    PlaceholderContentLimitPolicy,
)


CONFIG = {
    "defaults": {"overflow_action": "reject"},
    "content_limits": {
        "statement_support": {
            "content_kind": "prose",
            "max_lines": 1,
            "max_characters": 90,
            "overflow_action": "reject",
        }
    },
    "archetype_placeholders": {
        "statement": {
            "support": {"idx": 2, "limit": "statement_support"}
        }
    },
}


class RecordingPlaceholder:
    def __init__(self, idx: int) -> None:
        self.placeholder_format = SimpleNamespace(idx=idx, type="BODY")
        self.has_text_frame = True
        self.is_placeholder = True
        self.name = "Statement Support"
        self._text = "template prompt"
        self.text_write_count = 0

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self.text_write_count += 1
        self._text = value


class FakeSlide:
    def __init__(self, placeholder: RecordingPlaceholder) -> None:
        self.placeholders = [placeholder]
        self.shapes = [placeholder]


class PlaceholderContentContractBoundaryTests(unittest.TestCase):
    def make_builder(self, layout_policy: Mock) -> PlaceholderBuilder:
        return PlaceholderBuilder(
            archetype_placeholders={
                "statement": [
                    PlaceholderDefinition(
                        "support",
                        2,
                        "fields.statement",
                    )
                ]
            },
            content_limit_policy=PlaceholderContentLimitPolicy(
                config_data=CONFIG
            ),
            text_box_layout_policy=layout_policy,
        )

    def test_invalid_content_is_rejected_before_text_write_and_layout_policy(self):
        placeholder = RecordingPlaceholder(2)
        slide = FakeSlide(placeholder)
        layout_policy = Mock()
        builder = self.make_builder(layout_policy)

        with self.assertRaises(PlaceholderValidationException) as context:
            builder.populate(
                slide,
                {
                    "archetype": "statement",
                    "fields": {"statement": "X" * 91},
                },
            )

        self.assertIn("maximum is 90", str(context.exception))
        self.assertEqual(placeholder.text_write_count, 0)
        self.assertEqual(placeholder.text, "template prompt")
        layout_policy.apply.assert_not_called()

    def test_multiple_lines_are_rejected_before_text_write_and_layout_policy(self):
        placeholder = RecordingPlaceholder(2)
        slide = FakeSlide(placeholder)
        layout_policy = Mock()
        builder = self.make_builder(layout_policy)

        with self.assertRaises(PlaceholderValidationException) as context:
            builder.populate(
                slide,
                {
                    "archetype": "statement",
                    "fields": {"statement": "First line\nSecond line"},
                },
            )

        self.assertIn("maximum is 1", str(context.exception))
        self.assertEqual(placeholder.text_write_count, 0)
        layout_policy.apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
