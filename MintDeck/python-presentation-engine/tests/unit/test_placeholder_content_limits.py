from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from presentation_engine.services.placeholder_content_limits import (
    PlaceholderContentLimitConfigurationError,
    PlaceholderContentLimitPolicy,
    PlaceholderContentOverflowError,
)


TEST_CONFIG = {
    "defaults": {
        "overflow_action": "reject",
    },
    "content_limits": {
        "statement_support": {
            "content_kind": "prose",
            "max_lines": 1,
            "max_characters": 90,
            "overflow_action": "reject",
        },
        "process_body": {
            "content_kind": "prose",
            "max_lines": 4,
            "overflow_action": "reject",
        },
        "table": {
            "content_kind": "table",
            "max_total_rows": 10,
            "overflow_action": "reject",
        },
    },
    "archetype_placeholders": {
        "statement": {
            "support": {
                "idx": 2,
                "limit": "statement_support",
            }
        },
        "process_flow": {
            "step1_body": {
                "idx": 21,
                "limit": "process_body",
            }
        },
        "table": {
            "table": {
                "idx": 10,
                "limit": "table",
            }
        },
    },
}


class PlaceholderContentLimitPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = PlaceholderContentLimitPolicy(config_data=TEST_CONFIG)

    def test_resolves_statement_support_binding(self):
        binding = self.policy.resolve_binding("statement", "support")

        self.assertIsNotNone(binding)
        self.assertEqual(binding.placeholder_idx, 2)
        self.assertEqual(binding.limit_name, "statement_support")
        self.assertEqual(binding.rule.max_characters, 90)
        self.assertEqual(binding.rule.max_lines, 1)

    def test_unknown_binding_is_allowed_without_validation(self):
        result = self.policy.validate("cover", "title", "Any supported title")

        self.assertTrue(result.allowed)
        self.assertIsNone(result.binding)
        self.assertEqual(result.violations, ())

    def test_statement_support_within_ceiling_passes(self):
        result = self.policy.validate(
            "statement",
            "support",
            "Modern IT teams need cloud, data, automation and AI capability.",
        )

        self.assertTrue(result.allowed)
        self.assertLessEqual(result.measurement.characters, 90)
        self.assertEqual(result.measurement.estimated_lines, 1)

    def test_statement_support_above_character_ceiling_fails(self):
        text = "A" * 91
        result = self.policy.validate("statement", "support", text)

        self.assertFalse(result.allowed)
        self.assertTrue(any("maximum is 90" in item for item in result.violations))

    def test_statement_support_multiple_lines_fails(self):
        result = self.policy.validate(
            "statement",
            "support",
            "First line\nSecond line",
        )

        self.assertFalse(result.allowed)
        self.assertTrue(any("maximum is 1" in item for item in result.violations))

    def test_process_body_supports_four_explicit_lines(self):
        result = self.policy.validate(
            "process_flow",
            "step1_body",
            "Line one\nLine two\nLine three\nLine four",
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.measurement.estimated_lines, 4)

    def test_table_counts_header_plus_body_rows(self):
        result = self.policy.validate(
            "table",
            "table",
            {
                "headers": ["A", "B"],
                "rows": [[str(index), str(index)] for index in range(9)],
            },
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.measurement.total_rows, 10)

    def test_table_above_ten_total_rows_fails(self):
        result = self.policy.validate(
            "table",
            "table",
            {
                "headers": ["A", "B"],
                "rows": [[str(index), str(index)] for index in range(10)],
            },
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.measurement.total_rows, 11)
        self.assertTrue(any("maximum is 10" in item for item in result.violations))

    def test_validate_or_raise_produces_actionable_error(self):
        with self.assertRaises(PlaceholderContentOverflowError) as context:
            self.policy.validate_or_raise("statement", "support", "A" * 100)

        message = str(context.exception)
        self.assertIn("statement.support", message)
        self.assertIn("placeholder idx 2", message)
        self.assertIn("statement_support", message)

    def test_missing_configuration_file_raises_clear_error(self):
        with self.assertRaises(PlaceholderContentLimitConfigurationError):
            PlaceholderContentLimitPolicy(config_path="missing-content-limits.json")

    def test_invalid_json_configuration_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "invalid.json"
            config_path.write_text("{invalid", encoding="utf8")

            with self.assertRaises(PlaceholderContentLimitConfigurationError):
                PlaceholderContentLimitPolicy(config_path=config_path)

    def test_configuration_with_unknown_limit_reference_is_rejected(self):
        invalid = json.loads(json.dumps(TEST_CONFIG))
        invalid["archetype_placeholders"]["statement"]["support"]["limit"] = "missing"

        with self.assertRaises(PlaceholderContentLimitConfigurationError):
            PlaceholderContentLimitPolicy(config_data=invalid)


if __name__ == "__main__":
    unittest.main()
