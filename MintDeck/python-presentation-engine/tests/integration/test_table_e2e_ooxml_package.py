from __future__ import annotations

import json
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "data" / "output" / "table_e2e_validation_report.json"
RUNNER_PATH = PROJECT_ROOT / "run_table_e2e_validation.py"

NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}

EXPECTED_TEXT = [
    "Capability",
    "Status",
    "Notes",
    "ImageHandler",
    "Complete",
    "Images render in the generated deck",
    "TableHandler",
    "In validation",
    "Structured rows and columns are inserted",
    "ChartHandler",
    "Next",
    "Not started in this milestone",
]


class TableE2EOoxmlPackageTests(unittest.TestCase):
    def test_table_e2e_report_points_to_pptx_with_expected_table_xml(self):
        if not REPORT_PATH.exists():
            self.fail(
                f"Missing {REPORT_PATH}. Run python .\\run_table_e2e_validation.py first."
            )

        report = json.loads(REPORT_PATH.read_text(encoding="utf8"))
        self.assertEqual(report["overall_status"], "PASS", report.get("defects"))

        pptx_path = Path(report["generated_pptx"])
        self.assertTrue(pptx_path.exists(), f"Generated PPTX does not exist: {pptx_path}")

        with zipfile.ZipFile(pptx_path, "r") as archive:
            slide_xml = archive.read("ppt/slides/slide1.xml")
            root = ET.fromstring(slide_xml)
            tables = root.findall(".//a:tbl", NAMESPACES)

            self.assertEqual(len(tables), 1)

            text_values = [
                node.text
                for node in tables[0].findall(".//a:t", NAMESPACES)
                if node.text is not None
            ]

        for expected in EXPECTED_TEXT:
            self.assertIn(expected, text_values)


if __name__ == "__main__":
    unittest.main()
