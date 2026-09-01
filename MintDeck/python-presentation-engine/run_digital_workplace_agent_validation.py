from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from presentation_engine.builders.deck_builder import DeckBuilder

CONTRACT_PATH = Path("data/input/digital_workplace_agent_contract.json")
REPORT_PATH = Path("data/output/digital_workplace_agent_validation_report.json")
EXPECTED_SLIDE_COUNT = 8
EXPECTED_ARCHETYPES = [
    "cover", "thesis", "cards3", "chart",
    "table", "cards3", "process_flow", "closing",
]
EXPECTED_CHART_SLIDE = 4
EXPECTED_TABLE_SLIDE = 5
EXPECTED_CHART_TITLE = "Monthly Incidents"
EXPECTED_CATEGORIES = ["Apr", "May", "Jun", "Jul"]
EXPECTED_SERIES_NAME = "Incidents"
EXPECTED_VALUES = [820, 910, 1040, 1120]
EXPECTED_TABLE_HEADERS = ["Metric", "Result"]
EXPECTED_TABLE_ROWS = [
    ["First-contact resolution", "68%"],
    ["Compliant devices", "967 of 1240"],
    ["Acrobat deployed", "1020 of 1240"],
    ["Median access completion", "14 hours"],
    ["User satisfaction", "3.7/5"],
]
PROMPT_PATTERNS = [
    "Click to edit Master title style",
    "Click to edit Master text styles",
    "Click to edit Master subtitle style",
    "Click to add title",
    "Click to add text",
]
NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
CHART_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing contract: {path}")
    return json.loads(path.read_text(encoding="utf8"))


def duplicate_zip_entries(path: Path) -> dict[str, int]:
    with zipfile.ZipFile(path, "r") as archive:
        counts = Counter(archive.namelist())
    return {name: count for name, count in counts.items() if count > 1}


def relationship_targets(rels_xml: bytes) -> dict[str, str]:
    root = ET.fromstring(rels_xml)
    return {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in root
        if rel.attrib.get("Type") == CHART_REL_TYPE
        and rel.attrib.get("Id")
        and rel.attrib.get("Target")
    }


def resolve_target(slide_path: str, target: str) -> str:
    import posixpath
    return posixpath.normpath(posixpath.join(posixpath.dirname(slide_path), target))


def xml_text(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    values = [node.text for node in root.findall(".//a:t", NAMESPACES) if node.text]
    values.extend(node.text for node in root.findall(".//c:v", NAMESPACES) if node.text)
    return values


def inspect_package(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "slide_count": 0,
        "prompt_leaks": [],
        "chart": {"found": False, "missing_text": [], "missing_values": []},
        "table": {"found": False, "missing_text": []},
    }
    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        slides = sorted(
            (n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.search(r"slide(\d+)\.xml", n).group(1)),
        )
        report["slide_count"] = len(slides)
        for number, slide_path in enumerate(slides, 1):
            text = archive.read(slide_path).decode("utf8", errors="ignore")
            leaks = [pattern for pattern in PROMPT_PATTERNS if pattern in text]
            if leaks:
                report["prompt_leaks"].append({"slide_number": number, "patterns": leaks})

        table_path = f"ppt/slides/slide{EXPECTED_TABLE_SLIDE}.xml"
        if table_path in names:
            table_root = ET.fromstring(archive.read(table_path))
            report["table"]["found"] = bool(table_root.findall(".//a:tbl", NAMESPACES))
            table_text = xml_text(archive.read(table_path))
            expected = EXPECTED_TABLE_HEADERS + [cell for row in EXPECTED_TABLE_ROWS for cell in row]
            report["table"]["missing_text"] = [v for v in expected if v not in table_text]

        slide_path = f"ppt/slides/slide{EXPECTED_CHART_SLIDE}.xml"
        rels_path = f"ppt/slides/_rels/slide{EXPECTED_CHART_SLIDE}.xml.rels"
        chart_text: list[str] = []
        if slide_path in names and rels_path in names:
            root = ET.fromstring(archive.read(slide_path))
            rel_ids = [
                node.attrib.get(f"{{{NAMESPACES['r']}}}id")
                for node in root.findall(".//c:chart", NAMESPACES)
            ]
            targets = relationship_targets(archive.read(rels_path))
            parts = []
            for rel_id in rel_ids:
                target = targets.get(rel_id or "")
                if not target:
                    continue
                part = resolve_target(slide_path, target)
                if part in names:
                    parts.append(part)
                    chart_text.extend(xml_text(archive.read(part)))
            report["chart"]["found"] = bool(parts)
            report["chart"]["parts"] = parts
        expected_text = [EXPECTED_CHART_TITLE, EXPECTED_SERIES_NAME, *EXPECTED_CATEGORIES]
        report["chart"]["missing_text"] = [v for v in expected_text if v not in chart_text]
        numeric_values = []
        for value in chart_text:
            try:
                numeric_values.append(float(value))
            except (TypeError, ValueError):
                pass
        report["chart"]["missing_values"] = [v for v in EXPECTED_VALUES if float(v) not in numeric_values]
    return report


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    defects: list[str] = []

    actual_archetypes = [slide.get("archetype") for slide in contract.get("slides", [])]
    if actual_archetypes != EXPECTED_ARCHETYPES:
        defects.append(f"Archetype sequence mismatch: {actual_archetypes}")

    result = DeckBuilder().build_from_contract_file(CONTRACT_PATH)
    pptx_path = Path(result.output_pptx_path)
    if not pptx_path.exists():
        defects.append(f"Generated PPTX does not exist: {pptx_path}")

    duplicates = duplicate_zip_entries(pptx_path) if pptx_path.exists() else {}
    if duplicates:
        defects.append(f"Duplicate ZIP entries found: {duplicates}")

    package = inspect_package(pptx_path) if pptx_path.exists() else {}
    if package.get("slide_count") != EXPECTED_SLIDE_COUNT:
        defects.append(f"Expected {EXPECTED_SLIDE_COUNT} slides, found {package.get('slide_count')}")
    if package.get("prompt_leaks"):
        defects.append(f"Prompt text leak detected: {package['prompt_leaks']}")
    if not package.get("chart", {}).get("found"):
        defects.append("Expected chart was not found on slide 4.")
    if package.get("chart", {}).get("missing_text"):
        defects.append(f"Expected chart text missing: {package['chart']['missing_text']}")
    if package.get("chart", {}).get("missing_values"):
        defects.append(f"Expected chart values missing: {package['chart']['missing_values']}")
    if not package.get("table", {}).get("found"):
        defects.append("Expected table was not found on slide 5.")
    if package.get("table", {}).get("missing_text"):
        defects.append(f"Expected table text missing: {package['table']['missing_text']}")

    report = {
        "contract_used": str(CONTRACT_PATH),
        "generated_pptx": str(pptx_path),
        "slides_requested": len(contract.get("slides", [])),
        "slides_generated": package.get("slide_count"),
        "duplicate_zip_entries": len(duplicates),
        "package_validation": package,
        "visual_validation": {
            "status": "REQUIRES_MANUAL_REVIEW",
            "instructions": [
                "Open the generated PPTX.",
                "Confirm all eight slides are visible and use the expected layouts.",
                "Confirm the chart columns are visible on slide 4.",
                "Confirm the table is readable on slide 5.",
                "Check titles, text wrapping, spacing, and placeholder cleanup on every slide.",
            ],
        },
        "defects": defects,
        "overall_package_status": "PASS" if not defects else "FAIL",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not defects else 1


if __name__ == "__main__":
    raise SystemExit(main())
