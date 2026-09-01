from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from presentation_engine.builders.deck_builder import DeckBuilder

DEFAULT_CONTRACT = Path("data/input/minideck_agent_it_skills_contract.json")
DEFAULT_REPORT = Path("data/output/minideck_agent_it_skills_validation_report.json")
EXPECTED_ARCHETYPES = [
    "cover", "statement", "table", "table",
    "chart", "image_right", "process_flow", "closing",
]
EXPECTED_TABLES = {
    3: ["Capability Area", "Primary Focus", "Infrastructure and Cloud", "AI and Machine Learning"],
    4: ["Capability", "Core Skills", "Business Value", "Intelligent decision-making"],
}
EXPECTED_CHART_CATEGORIES = [
    "Infrastructure and Cloud", "Software Engineering", "Data Engineering",
    "Analytics and Automation", "AI and Machine Learning",
]
EXPECTED_CHART_VALUES = [92, 85, 78, 71, 98]
EXPECTED_PROCESS_TEXT = ["Assess", "Learn", "Apply", "Optimise and Scale"]
EXPECTED_CLOSING_TEXT = [
    "Confirm priority capability investments", "Align workforce development plans",
    "Define capability targets", "Establish a quarterly review cadence",
]
PROMPT_PATTERNS = [
    "Click to edit Master title style", "Click to edit Master text styles",
    "Click to edit Master subtitle style", "Click to add title", "Click to add text",
]
NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
CHART_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"

class ValidationError(Exception):
    pass

def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValidationError(f"Contract not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def duplicate_entries(path: Path) -> dict[str, int]:
    with zipfile.ZipFile(path) as z:
        counts = Counter(z.namelist())
    return {name: count for name, count in counts.items() if count > 1}

def text_values(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    values = [n.text for n in root.findall(".//a:t", NAMESPACES) if n.text]
    values += [n.text for n in root.findall(".//c:v", NAMESPACES) if n.text]
    return values

def slide_path(n: int) -> str:
    return f"ppt/slides/slide{n}.xml"

def rels_path(n: int) -> str:
    return f"ppt/slides/_rels/slide{n}.xml.rels"

def relationship_targets(xml_bytes: bytes, rel_type: str) -> dict[str, str]:
    result = {}
    for rel in ET.fromstring(xml_bytes):
        if rel.attrib.get("Type") == rel_type:
            result[rel.attrib["Id"]] = rel.attrib["Target"]
    return result

def resolve_target(slide_xml: str, target: str) -> str:
    import posixpath
    return posixpath.normpath(posixpath.join(posixpath.dirname(slide_xml), target))

def check_contract(contract: dict[str, Any]) -> list[str]:
    defects: list[str] = []
    slides = contract.get("slides")
    if not isinstance(slides, list):
        return ["slides must be a list"]
    actual = [slide.get("archetype") for slide in slides]
    if actual != EXPECTED_ARCHETYPES:
        defects.append(f"Archetype sequence mismatch: {actual}")
    if len(slides) != 8:
        defects.append(f"Expected 8 slides, received {len(slides)}")
    if len(slides) >= 2:
        support = slides[1].get("fields", {}).get("statement", "")
        if len(support) > 90:
            defects.append(f"statement.support exceeds 90 characters: {len(support)}")
    for n in (3, 4):
        if len(slides) >= n:
            table = slides[n-1].get("fields", {}).get("table")
            if not isinstance(table, dict):
                defects.append(f"Slide {n}: fields.table object missing")
            else:
                total_rows = len(table.get("rows", [])) + (1 if table.get("headers") else 0)
                if total_rows > 10:
                    defects.append(f"Slide {n}: table has {total_rows} total rows; maximum is 10")
    if len(slides) >= 5:
        chart = slides[4].get("fields", {}).get("chart")
        if not isinstance(chart, dict):
            defects.append("Slide 5: fields.chart object missing")
        else:
            categories = chart.get("categories", [])
            for series in chart.get("series", []):
                if len(series.get("values", [])) != len(categories):
                    defects.append("Slide 5: chart series value count does not match category count")
    if len(slides) >= 7 and len(slides[6].get("fields", {}).get("steps", [])) > 4:
        defects.append("Slide 7: process_flow exceeds 4 steps")
    return defects

def inspect_pptx(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "slide_count": 0, "prompt_leaks": [], "tables": {},
        "chart": {"found": False, "missing_categories": [], "missing_values": []},
        "process_missing_text": [], "closing_missing_text": [],
    }
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        slides = sorted(n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
        result["slide_count"] = len(slides)
        for number in range(1, len(slides)+1):
            sp = slide_path(number)
            if sp in names:
                raw = z.read(sp).decode("utf-8", errors="ignore")
                leaks = [p for p in PROMPT_PATTERNS if p in raw]
                if leaks:
                    result["prompt_leaks"].append({"slide": number, "patterns": leaks})
        for number, expected in EXPECTED_TABLES.items():
            sp = slide_path(number)
            if sp not in names:
                result["tables"][str(number)] = {"found": False, "missing_text": expected}
                continue
            root = ET.fromstring(z.read(sp))
            vals = text_values(z.read(sp))
            result["tables"][str(number)] = {
                "found": bool(root.findall(".//a:tbl", NAMESPACES)),
                "missing_text": [x for x in expected if x not in vals],
            }
        sp, rp = slide_path(5), rels_path(5)
        chart_vals: list[str] = []
        if sp in names and rp in names:
            root = ET.fromstring(z.read(sp))
            rels = relationship_targets(z.read(rp), CHART_REL)
            ids = [n.attrib.get(f"{{{NAMESPACES['r']}}}id") for n in root.findall(".//c:chart", NAMESPACES)]
            parts = []
            for rel_id in ids:
                target = rels.get(rel_id or "")
                if target:
                    part = resolve_target(sp, target)
                    if part in names:
                        parts.append(part)
                        chart_vals.extend(text_values(z.read(part)))
            result["chart"]["found"] = bool(parts)
            result["chart"]["parts"] = parts
        result["chart"]["missing_categories"] = [x for x in EXPECTED_CHART_CATEGORIES if x not in chart_vals]
        numeric = set()
        for value in chart_vals:
            try: numeric.add(float(value))
            except (TypeError, ValueError): pass
        result["chart"]["missing_values"] = [x for x in EXPECTED_CHART_VALUES if float(x) not in numeric]
        for number, key, expected in ((7, "process_missing_text", EXPECTED_PROCESS_TEXT), (8, "closing_missing_text", EXPECTED_CLOSING_TEXT)):
            sp = slide_path(number)
            vals = text_values(z.read(sp)) if sp in names else []
            result[key] = [x for x in expected if x not in vals]
    return result

def run_tests() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", ".\\tests", "-p", "test_*.py"],
        text=True, capture_output=True,
    )
    return {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    contract = load_json(args.contract)
    defects = check_contract(contract)
    output_path: Path | None = None
    package: dict[str, Any] = {}

    if not defects:
        result = DeckBuilder().build_from_contract_file(args.contract)
        output_path = Path(result.output_pptx_path)
        if not output_path.exists():
            defects.append(f"Generated PPTX does not exist: {output_path}")
        else:
            duplicates = duplicate_entries(output_path)
            if duplicates:
                defects.append(f"Duplicate ZIP entries: {duplicates}")
            package = inspect_pptx(output_path)
            if package["slide_count"] != 8:
                defects.append(f"Expected 8 output slides, found {package['slide_count']}")
            if package["prompt_leaks"]:
                defects.append(f"Prompt text leaked: {package['prompt_leaks']}")
            for slide, table in package["tables"].items():
                if not table["found"]:
                    defects.append(f"Slide {slide}: table not found")
                if table["missing_text"]:
                    defects.append(f"Slide {slide}: missing table text {table['missing_text']}")
            if not package["chart"]["found"]:
                defects.append("Slide 5: chart not found")
            if package["chart"]["missing_categories"]:
                defects.append(f"Slide 5: missing chart categories {package['chart']['missing_categories']}")
            if package["chart"]["missing_values"]:
                defects.append(f"Slide 5: missing chart values {package['chart']['missing_values']}")
            if package["process_missing_text"]:
                defects.append(f"Slide 7: missing process text {package['process_missing_text']}")
            if package["closing_missing_text"]:
                defects.append(f"Slide 8: missing closing text {package['closing_missing_text']}")

    tests = {"status": "SKIPPED"} if args.skip_tests else run_tests()
    if tests.get("status") == "FAIL":
        defects.append("Automated test suite failed")

    report = {
        "contract_used": str(args.contract),
        "generated_pptx": str(output_path) if output_path else None,
        "contract_preflight": "PASS" if not check_contract(contract) else "FAIL",
        "tests": tests,
        "package_validation": package,
        "manual_visual_review": {
            "status": "REQUIRED",
            "checks": [
                "Open the PPTX and confirm all 8 slides are visually present.",
                "Check slide 2 statement containment and paragraph spacing.",
                "Check slides 3 and 4 table styling, row heights, margins, and overlap.",
                "Check slide 5 chart labels and plot-area utilisation.",
                "Check slide 6 text fit; no image is expected because the contract supplies no picture reference.",
                "Check slide 7 process text fit and slide 8 closing text fit.",
            ],
        },
        "defects": defects,
        "overall_package_status": "PASS" if not defects else "FAIL",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not defects else 1

if __name__ == "__main__":
    raise SystemExit(main())
