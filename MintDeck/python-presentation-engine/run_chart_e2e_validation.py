from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from presentation_engine.builders.deck_builder import DeckBuilder


CONTRACT_PATH = Path("data/input/chart_e2e_validation_contract.json")
REPORT_PATH = Path("data/output/chart_e2e_validation_report.json")

EXPECTED_SLIDE_NUMBER = 1
EXPECTED_CHART_TITLE = "Milestone Progress"
EXPECTED_CATEGORIES = ["Images", "Tables", "Charts"]
EXPECTED_SERIES_NAME = "Status"
EXPECTED_VALUES = ["100.0", "60.0", "10.0"]

CHART_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"

NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


class ChartE2EValidationException(Exception):
    """Raised when the chart E2E validation cannot complete."""


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ChartE2EValidationException(f"Required JSON file does not exist: {path}")

    text = path.read_text(encoding="utf8").strip()

    if not text:
        raise ChartE2EValidationException(f"Required JSON file is empty: {path}")

    return json.loads(text)


def duplicate_zip_entries(pptx_path: Path) -> dict[str, int]:
    with zipfile.ZipFile(pptx_path, "r") as archive:
        counts = Counter(archive.namelist())

    return {name: count for name, count in counts.items() if count > 1}


def slide_xml_path(slide_number: int) -> str:
    return f"ppt/slides/slide{slide_number}.xml"


def slide_rels_path(slide_number: int) -> str:
    return f"ppt/slides/_rels/slide{slide_number}.xml.rels"


def relationship_targets_by_id(rels_xml: bytes) -> dict[str, str]:
    root = ET.fromstring(rels_xml)
    targets: dict[str, str] = {}

    for rel in root:
        rel_id = rel.attrib.get("Id")
        rel_type = rel.attrib.get("Type")
        target = rel.attrib.get("Target")

        if rel_id and target and rel_type == CHART_RELATIONSHIP_TYPE:
            targets[rel_id] = target

    return targets


def chart_relationship_ids(slide_xml: bytes) -> list[str]:
    root = ET.fromstring(slide_xml)
    rel_ids: list[str] = []

    for chart in root.findall(".//c:chart", NAMESPACES):
        rel_id = chart.attrib.get(f"{{{NAMESPACES['r']}}}id")
        if rel_id:
            rel_ids.append(rel_id)

    return rel_ids


def resolve_chart_target(target: str) -> str:
    normalized = target.replace("\\", "/")
    if normalized.startswith("../"):
        return "ppt/" + normalized[3:]
    if normalized.startswith("charts/"):
        return "ppt/" + normalized
    return normalized


def chart_text_values(chart_xml: bytes) -> list[str]:
    root = ET.fromstring(chart_xml)
    values: list[str] = []

    for node in root.findall(".//c:v", NAMESPACES):
        if node.text is not None:
            values.append(node.text)

    for node in root.findall(".//a:t", NAMESPACES):
        if node.text is not None:
            values.append(node.text)

    return values


def inspect_charts_in_pptx(pptx_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(pptx_path, "r") as archive:
        names = set(archive.namelist())
        slide_path = slide_xml_path(EXPECTED_SLIDE_NUMBER)
        rels_path = slide_rels_path(EXPECTED_SLIDE_NUMBER)

        if slide_path not in names:
            raise ChartE2EValidationException(f"Expected slide XML was not found: {slide_path}")

        if rels_path not in names:
            raise ChartE2EValidationException(f"Expected slide relationships XML was not found: {rels_path}")

        slide_xml = archive.read(slide_path)
        rels_xml = archive.read(rels_path)
        rel_targets = relationship_targets_by_id(rels_xml)
        chart_ids = chart_relationship_ids(slide_xml)

        chart_reports: list[dict[str, Any]] = []

        for rel_id in chart_ids:
            target = rel_targets.get(rel_id)
            if not target:
                chart_reports.append({"rel_id": rel_id, "status": "missing_relationship_target"})
                continue

            chart_part = resolve_chart_target(target)
            if chart_part not in names:
                chart_reports.append(
                    {"rel_id": rel_id, "target": target, "chart_part": chart_part, "status": "missing_chart_part"}
                )
                continue

            text_values = chart_text_values(archive.read(chart_part))
            chart_reports.append(
                {
                    "rel_id": rel_id,
                    "target": target,
                    "chart_part": chart_part,
                    "status": "resolved",
                    "text": text_values,
                }
            )

    return {
        "charts_detected": len([chart for chart in chart_reports if chart.get("status") == "resolved"]),
        "charts": chart_reports,
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

    inspection = inspect_charts_in_pptx(pptx_path) if pptx_path.exists() else {"charts_detected": 0, "charts": []}

    if inspection["charts_detected"] != 1:
        defects.append(f"Expected 1 inserted chart, found {inspection['charts_detected']}.")

    matched_chart = next((chart for chart in inspection["charts"] if chart.get("status") == "resolved"), None)

    if matched_chart:
        text_values = matched_chart.get("text", [])
        expected_text = [EXPECTED_CHART_TITLE, EXPECTED_SERIES_NAME, *EXPECTED_CATEGORIES, *EXPECTED_VALUES]
        missing_text = [value for value in expected_text if value not in text_values]

        if missing_text:
            defects.append(f"Expected chart text/value content was not found: {missing_text}")

    report = {
        "contract_used": str(CONTRACT_PATH),
        "generated_pptx": str(pptx_path),
        "duplicate_zip_entries": len(duplicate_details),
        "duplicate_zip_entry_details": duplicate_details,
        "slides": [
            {
                "slide_number": EXPECTED_SLIDE_NUMBER,
                "archetype": contract.get("slides", [{}])[0].get("archetype"),
                "expected_charts": 1,
                "charts_detected": inspection["charts_detected"],
                "charts": inspection["charts"],
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
