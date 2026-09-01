from __future__ import annotations

import json
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "data" / "output" / "chart_e2e_validation_report.json"

NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
}

EXPECTED_TEXT = [
    "Milestone Progress",
    "Status",
    "Images",
    "Tables",
    "Charts",
]

EXPECTED_NUMERIC_VALUES = [
    100,
    60,
    10,
]


def contains_numeric_value(values: list[str], expected: float) -> bool:
    for value in values:
        try:
            if float(value) == float(expected):
                return True
        except (TypeError, ValueError):
            continue

    return False


class ChartE2EOoxmlPackageTests(unittest.TestCase):
    def test_chart_e2e_report_points_to_pptx_with_expected_chart_xml(self):
        if not REPORT_PATH.exists():
            self.fail(
                f"Missing {REPORT_PATH}. Run python .\\run_chart_e2e_validation.py first."
            )

        report = json.loads(REPORT_PATH.read_text(encoding="utf8"))
        self.assertEqual(report["overall_status"], "PASS", report.get("defects"))

        pptx_path = Path(report["generated_pptx"])
        self.assertTrue(pptx_path.exists(), f"Generated PPTX does not exist: {pptx_path}")

        chart_parts: list[str] = []
        text_values: list[str] = []

        with zipfile.ZipFile(pptx_path, "r") as archive:
            names = archive.namelist()
            chart_parts = [
                name
                for name in names
                if name.startswith("ppt/charts/chart") and name.endswith(".xml")
            ]

            self.assertGreaterEqual(len(chart_parts), 1)

            for chart_part in chart_parts:
                root = ET.fromstring(archive.read(chart_part))

                for node in root.findall(".//c:v", NAMESPACES):
                    if node.text is not None:
                        text_values.append(node.text)

                for node in root.findall(".//a:t", NAMESPACES):
                    if node.text is not None:
                        text_values.append(node.text)

        for expected in EXPECTED_TEXT:
            self.assertIn(expected, text_values)

        for expected in EXPECTED_NUMERIC_VALUES:
            self.assertTrue(
                contains_numeric_value(text_values, expected),
                f"Expected numeric chart value was not found: {expected}. Found values: {text_values}",
            )


if __name__ == "__main__":
    unittest.main()