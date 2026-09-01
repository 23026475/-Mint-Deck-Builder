from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from presentation_engine.builders.deck_builder import DeckBuilder


CONTRACT_PATH = Path("data/input/table_e2e_validation_contract.json")
REPORT_PATH = Path("data/output/table_e2e_validation_report.json")

EXPECTED_SLIDE_NUMBER = 1
EXPECTED_HEADERS = ["Capability", "Status", "Notes"]
EXPECTED_ROWS = [
    ["ImageHandler", "Complete", "Images render in the generated deck"],
    ["TableHandler", "In validation", "Structured rows and columns are inserted"],
    ["ChartHandler", "Next", "Not started in this milestone"],
]
EXPECTED_TABLE_TEXT = EXPECTED_HEADERS + [cell for row in EXPECTED_ROWS for cell in row]

NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


class TableE2EValidationException(Exception):
    """Raised when the table E2E validation cannot complete."""


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise TableE2EValidationException(f"Required JSON file does not exist: {path}")

    text = path.read_text(encoding="utf8").strip()

    if not text:
        raise TableE2EValidationException(f"Required JSON file is empty: {path}")

    return json.loads(text)


def duplicate_zip_entries(pptx_path: Path) -> dict[str, int]:
    with zipfile.ZipFile(pptx_path, "r") as archive:
        counts = Counter(archive.namelist())

    return {name: count for name, count in counts.items() if count > 1}


def slide_xml_path(slide_number: int) -> str:
    return f"ppt/slides/slide{slide_number}.xml"


def table_text(table_element: ET.Element) -> list[str]:
    values: list[str] = []

    for text_node in table_element.findall(".//a:t", NAMESPACES):
        if text_node.text is not None:
            values.append(text_node.text)

    return values


def table_dimensions(table_element: ET.Element) -> tuple[int, int]:
    rows = table_element.findall(".//a:tr", NAMESPACES)
    row_count = len(rows)
    column_count = 0

    if rows:
        column_count = len(rows[0].findall(".//a:tc", NAMESPACES))

    return row_count, column_count


def inspect_tables_in_pptx(pptx_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(pptx_path, "r") as archive:
        names = set(archive.namelist())
        target_slide = slide_xml_path(EXPECTED_SLIDE_NUMBER)

        if target_slide not in names:
            raise TableE2EValidationException(f"Expected slide XML was not found: {target_slide}")

        slide_xml = archive.read(target_slide)
        root = ET.fromstring(slide_xml)
        tables = root.findall(".//a:tbl", NAMESPACES)

        table_reports: list[dict[str, Any]] = []

        for index, table in enumerate(tables, start=1):
            row_count, column_count = table_dimensions(table)
            text_values = table_text(table)
            table_reports.append(
                {
                    "table_index": index,
                    "row_count": row_count,
                    "column_count": column_count,
                    "text": text_values,
                }
            )

    return {
        "tables_detected": len(table_reports),
        "tables": table_reports,
    }


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    result = DeckBuilder().build_from_contract_file(CONTRACT_PATH)
    pptx_path = Path(result.output_pptx_path)

    defects: list[str] = []

    if not pptx_path.exists():
        defects.append(f"Generated PPTX does not exist: {pptx_path}")

    duplicate_details = duplicate_zip_entries(pptx_path) if pptx_path.exists() else {}

    if duplicate_details:
        defects.append(f"Duplicate ZIP entries detected: {duplicate_details}")

    inspection = inspect_tables_in_pptx(pptx_path) if pptx_path.exists() else {"tables_detected": 0, "tables": []}

    if inspection["tables_detected"] != 1:
        defects.append(f"Expected 1 inserted table, found {inspection['tables_detected']}.")

    matched_table = inspection["tables"][0] if inspection["tables"] else None

    if matched_table:
        expected_row_count = 1 + len(EXPECTED_ROWS)
        expected_column_count = len(EXPECTED_HEADERS)

        if matched_table["row_count"] != expected_row_count:
            defects.append(
                f"Expected {expected_row_count} table rows, found {matched_table['row_count']}."
            )

        if matched_table["column_count"] != expected_column_count:
            defects.append(
                f"Expected {expected_column_count} table columns, found {matched_table['column_count']}."
            )

        missing_text = [value for value in EXPECTED_TABLE_TEXT if value not in matched_table["text"]]

        if missing_text:
            defects.append(f"Expected table text was not found: {missing_text}")

    report = {
        "contract_used": str(CONTRACT_PATH),
        "generated_pptx": str(pptx_path),
        "duplicate_zip_entries": len(duplicate_details),
        "duplicate_zip_entry_details": duplicate_details,
        "slides": [
            {
                "slide_number": EXPECTED_SLIDE_NUMBER,
                "archetype": contract.get("slides", [{}])[0].get("archetype"),
                "expected_tables": 1,
                "tables_detected": inspection["tables_detected"],
                "tables": inspection["tables"],
                "status": "PASS" if not defects else "FAIL",
            }
        ],
        "defects": defects,
        "overall_status": "PASS" if not defects else "FAIL",
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
