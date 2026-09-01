from __future__ import annotations

import hashlib
import json
import posixpath
import re
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from presentation_engine.builders.deck_builder import DeckBuilder


CONTRACT_PATH = Path("data/input/it_skills_engine_validation_contract.json")
REPORT_PATH = Path("data/output/it_skills_engine_validation_report.json")
IMAGE_DIR = Path("data/assets/images")
EXPECTED_SLIDE_COUNT = 8
EXPECTED_IMAGE_FILENAME = "FY27 People Collaborating & Corporate (70).jpg"
EXPECTED_TABLE_TEXT = [
    "Capability", "Core skills", "Typical tools", "Primary outcome",
    "Infrastructure & Cloud", "Cloud platforms, networking, infrastructure", "Azure, AWS, Terraform", "Scalable infrastructure",
    "Software Engineering", "Programming, APIs, application development", "Python, C#, Git", "Software delivery",
    "Data Engineering", "Pipelines, databases, data modelling", "SQL, Python, ADF", "Reliable data",
    "Analytics & Automation", "BI, automation, reporting", "Power BI, Power Automate", "Operational insight",
    "AI & Machine Learning", "ML, AI systems, model integration", "Python, AI services", "Intelligent solutions",
]
EXPECTED_CHART_TEXT = [
    "Illustrative Capability Maturity",
    "Illustrative maturity",
    "Infrastructure & Cloud",
    "Software Engineering",
    "Data Engineering",
    "Analytics & Automation",
    "AI & Machine Learning",
]
EXPECTED_CHART_VALUES = [80, 70, 60, 50, 40]
PROMPT_PATTERNS = [
    "Click to edit Master title style",
    "Click to edit Master text styles",
    "Click to edit Master subtitle style",
    "Click to add title",
    "Click to add text",
]
IMAGE_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
CHART_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


class ItSkillsValidationException(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ItSkillsValidationException(f"Required JSON file does not exist: {path}")
    text = path.read_text(encoding="utf8").strip()
    if not text:
        raise ItSkillsValidationException(f"Required JSON file is empty: {path}")
    return json.loads(text)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def resolve_image_case_insensitive(filename: str) -> Path:
    direct = IMAGE_DIR / filename
    if direct.exists():
        return direct.resolve()
    wanted = filename.lower()
    for path in IMAGE_DIR.rglob("*"):
        if not path.is_file():
            continue
        relative_name = str(path.relative_to(IMAGE_DIR)).replace("\\", "/").lower()
        if relative_name == wanted or path.name.lower() == wanted:
            return path.resolve()
    raise ItSkillsValidationException(f"Image file not found: {filename}")


def duplicate_zip_entries(pptx_path: Path) -> dict[str, int]:
    with zipfile.ZipFile(pptx_path, "r") as archive:
        counts = Counter(archive.namelist())
    return {name: count for name, count in counts.items() if count > 1}


def relationship_targets_by_type(rels_xml: bytes, rel_type: str) -> dict[str, str]:
    root = ET.fromstring(rels_xml)
    targets: dict[str, str] = {}
    for rel in root:
        rel_id = rel.attrib.get("Id")
        current_type = rel.attrib.get("Type")
        target = rel.attrib.get("Target")
        if rel_id and target and current_type == rel_type:
            targets[rel_id] = target
    return targets


def resolve_relationship_target(slide_xml_path: str, target: str) -> str:
    slide_dir = posixpath.dirname(slide_xml_path)
    return posixpath.normpath(posixpath.join(slide_dir, target))


def slide_path(slide_number: int) -> str:
    return f"ppt/slides/slide{slide_number}.xml"


def rels_path(slide_number: int) -> str:
    return f"ppt/slides/_rels/slide{slide_number}.xml.rels"


def text_values_from_xml(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    values: list[str] = []
    for node in root.findall(".//a:t", NAMESPACES):
        if node.text:
            values.append(node.text)
    for node in root.findall(".//c:v", NAMESPACES):
        if node.text:
            values.append(node.text)
    return values


def numeric_text_present(values: list[str], expected_number: float) -> bool:
    for value in values:
        try:
            if float(value) == float(expected_number):
                return True
        except Exception:
            continue
    return False


def inspect_pptx(pptx_path: Path) -> dict[str, Any]:
    source_image_hash = sha256_file(resolve_image_case_insensitive(EXPECTED_IMAGE_FILENAME))
    result: dict[str, Any] = {
        "slide_count": 0,
        "prompt_leaks": [],
        "image": {"expected_filename": EXPECTED_IMAGE_FILENAME, "found": False, "slide_number": 6},
        "table": {"found": False, "slide_number": 4, "missing_text": []},
        "chart": {"found": False, "slide_number": 5, "missing_text": [], "missing_values": [], "chart_parts": []},
    }
    with zipfile.ZipFile(pptx_path, "r") as archive:
        names = set(archive.namelist())
        slide_xml_files = sorted(name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        result["slide_count"] = len(slide_xml_files)

        for slide_number in range(1, result["slide_count"] + 1):
            sp = slide_path(slide_number)
            if sp not in names:
                continue
            text = archive.read(sp).decode("utf8", errors="ignore")
            leaks = [pattern for pattern in PROMPT_PATTERNS if pattern in text]
            if leaks:
                result["prompt_leaks"].append({"slide_number": slide_number, "patterns": leaks})

        # Image: slide 6 media hash match
        sp = slide_path(6)
        rp = rels_path(6)
        if sp in names and rp in names:
            slide_xml = archive.read(sp)
            rel_targets = relationship_targets_by_type(archive.read(rp), IMAGE_RELATIONSHIP_TYPE)
            root = ET.fromstring(slide_xml)
            embedded_ids = [node.attrib.get(f"{{{NAMESPACES['r']}}}embed") for node in root.findall(".//a:blip", NAMESPACES)]
            media_hashes = {}
            for rel_id in embedded_ids:
                target = rel_targets.get(rel_id or "")
                if not target:
                    continue
                media_part = resolve_relationship_target(sp, target)
                if media_part in names:
                    media_hashes[media_part] = sha256_bytes(archive.read(media_part))
            result["image"]["found"] = source_image_hash in set(media_hashes.values())
            result["image"]["media_parts"] = sorted(media_hashes.keys())

        # Table: slide 4 contains table and expected table text
        sp = slide_path(4)
        if sp in names:
            root = ET.fromstring(archive.read(sp))
            tables = root.findall(".//a:tbl", NAMESPACES)
            table_text = text_values_from_xml(archive.read(sp))
            result["table"]["found"] = len(tables) >= 1
            result["table"]["tables_detected"] = len(tables)
            result["table"]["missing_text"] = [value for value in EXPECTED_TABLE_TEXT if value not in table_text]

        # Chart: slide 5 has chart relationship and chart part with expected content
        sp = slide_path(5)
        rp = rels_path(5)
        if sp in names and rp in names:
            root = ET.fromstring(archive.read(sp))
            chart_rel_ids = [node.attrib.get(f"{{{NAMESPACES['r']}}}id") for node in root.findall(".//c:chart", NAMESPACES)]
            rel_targets = relationship_targets_by_type(archive.read(rp), CHART_RELATIONSHIP_TYPE)
            chart_text_values: list[str] = []
            chart_parts: list[str] = []
            for rel_id in chart_rel_ids:
                target = rel_targets.get(rel_id or "")
                if not target:
                    continue
                chart_part = resolve_relationship_target(sp, target)
                if chart_part not in names:
                    continue
                chart_parts.append(chart_part)
                chart_text_values.extend(text_values_from_xml(archive.read(chart_part)))
            result["chart"]["found"] = len(chart_parts) >= 1
            result["chart"]["chart_parts"] = chart_parts
            result["chart"]["missing_text"] = [value for value in EXPECTED_CHART_TEXT if value not in chart_text_values]
            result["chart"]["missing_values"] = [value for value in EXPECTED_CHART_VALUES if not numeric_text_present(chart_text_values, value)]
            result["chart"]["text_values"] = chart_text_values

    return result


def maybe_run_unittest() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", ".\\tests", "-p", "test_*.py"],
        text=True,
        capture_output=True,
    )
    return {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "status": "PASS" if completed.returncode == 0 else "FAIL",
    }


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    defects: list[str] = []
    result = DeckBuilder().build_from_contract_file(CONTRACT_PATH)
    pptx_path = Path(result.output_pptx_path)

    if not pptx_path.exists():
        defects.append(f"Generated PPTX does not exist: {pptx_path}")

    duplicates = duplicate_zip_entries(pptx_path) if pptx_path.exists() else {}
    if duplicates:
        defects.append(f"Duplicate ZIP entries found: {duplicates}")

    package = inspect_pptx(pptx_path) if pptx_path.exists() else {}
    if package.get("slide_count") != EXPECTED_SLIDE_COUNT:
        defects.append(f"Expected {EXPECTED_SLIDE_COUNT} slides, found {package.get('slide_count')}")
    if package.get("prompt_leaks"):
        defects.append(f"Prompt text leak detected: {package.get('prompt_leaks')}")
    if not package.get("image", {}).get("found"):
        defects.append("Expected image was not found on slide 6 by media hash matching.")
    table = package.get("table", {})
    if not table.get("found"):
        defects.append("Expected table was not found on slide 4.")
    if table.get("missing_text"):
        defects.append(f"Expected table text missing: {table.get('missing_text')}")
    chart = package.get("chart", {})
    if not chart.get("found"):
        defects.append("Expected chart was not found on slide 5.")
    if chart.get("missing_text"):
        defects.append(f"Expected chart text missing: {chart.get('missing_text')}")
    if chart.get("missing_values"):
        defects.append(f"Expected chart values missing: {chart.get('missing_values')}")

    # Visual chart rendering cannot be proven by OOXML alone. This scenario deliberately reports it as manual-required.
    visual_validation = {
        "status": "REQUIRES_MANUAL_REVIEW",
        "instructions": [
            "Open the generated PPTX.",
            "Go to slide 5.",
            "Confirm that the chart bars/columns are visibly rendered, not only the chart title.",
            "If the chart object exists but the plot area is blank, mark ChartHandler visual validation as FAIL."
        ]
    }

    report = {
        "contract_used": str(CONTRACT_PATH),
        "generated_pptx": str(pptx_path),
        "slides_requested": len(contract.get("slides", [])),
        "slides_generated": package.get("slide_count"),
        "duplicate_zip_entries": len(duplicates),
        "package_validation": package,
        "visual_validation": visual_validation,
        "defects": defects,
        "overall_package_status": "PASS" if not defects else "FAIL",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not defects else 1


if __name__ == "__main__":
    raise SystemExit(main())
