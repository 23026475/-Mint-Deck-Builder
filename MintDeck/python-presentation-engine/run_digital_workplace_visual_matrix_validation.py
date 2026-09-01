from __future__ import annotations
import hashlib
import json
import posixpath
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from presentation_engine.builders.deck_builder import DeckBuilder

CONTRACT_PATH = Path("data/input/digital_workplace_visual_matrix_contract.json")
REPORT_PATH = Path("data/output/digital_workplace_visual_matrix_validation_report.json")
IMAGE_DIR = Path("data/assets/images")
EXPECTED_ARCHETYPES = ["cover", "thesis", "cards3", "chart", "table", "image_right", "matrix", "quote", "process_flow", "closing"]
EXPECTED_IMAGES = {6: "FY27 People Collaborating & Corporate (70).jpg", 8: "FY27 People Collaborating & Corporate (69).JPG"}
EXPECTED_MATRIX_TEXT = ["PRIORITIZATION", "Business impact", "Delivery readiness", "Immediate focus", "Build next", "Monitor", "Later consideration", "273 non-compliant devices", "Access delays", "220 incomplete deployments", "Satisfaction 3.7/5", "Weak status updates"]
EXPECTED_CHART_TEXT = ["Monthly incidents", "Incidents", "Apr", "May", "Jun", "Jul"]
EXPECTED_CHART_VALUES = [820, 910, 1040, 1120]
EXPECTED_TABLE_TEXT = ["Metric", "July result", "First-contact resolution", "68%", "Compliant devices", "967 of 1240", "Acrobat deployed", "1020 of 1240", "Median access completion", "14 hours", "Satisfaction", "3.7/5"]
PROMPT_PATTERNS = ["Click to edit Master title style", "Click to edit Master text styles", "Click to edit Master subtitle style", "Click to add title", "Click to add text"]
IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
CHART_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
NS = {"a":"http://schemas.openxmlformats.org/drawingml/2006/main", "c":"http://schemas.openxmlformats.org/drawingml/2006/chart", "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

def load_json(path: Path) -> dict[str, Any]:
    if not path.exists(): raise SystemExit(f"Missing contract: {path}")
    return json.loads(path.read_text(encoding="utf8"))

def duplicates(path: Path) -> dict[str, int]:
    with zipfile.ZipFile(path) as z: counts = Counter(z.namelist())
    return {n:c for n,c in counts.items() if c > 1}

def image_path(name: str) -> Path:
    direct = IMAGE_DIR / name
    if direct.exists(): return direct
    wanted = name.lower()
    for p in IMAGE_DIR.rglob("*"):
        if p.is_file() and p.name.lower() == wanted: return p
    raise FileNotFoundError(name)

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def slide_path(n: int) -> str: return f"ppt/slides/slide{n}.xml"
def rels_path(n: int) -> str: return f"ppt/slides/_rels/slide{n}.xml.rels"

def rel_targets(data: bytes, kind: str) -> dict[str, str]:
    root = ET.fromstring(data)
    return {r.attrib["Id"]:r.attrib["Target"] for r in root if r.attrib.get("Type") == kind and r.attrib.get("Id") and r.attrib.get("Target")}

def resolve(base: str, target: str) -> str: return posixpath.normpath(posixpath.join(posixpath.dirname(base), target))

def text_values(data: bytes) -> list[str]:
    root = ET.fromstring(data)
    values = [n.text for n in root.findall(".//a:t", NS) if n.text]
    values += [n.text for n in root.findall(".//c:v", NS) if n.text]
    return values

def inspect(path: Path) -> dict[str, Any]:
    result = {"slide_count":0,"prompt_leaks":[],"images":{},"matrix":{},"chart":{},"table":{}}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        slides = [n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        result["slide_count"] = len(slides)
        for n in range(1, len(slides)+1):
            sp = slide_path(n)
            if sp in names:
                xml = z.read(sp).decode("utf8", errors="ignore")
                leaks = [p for p in PROMPT_PATTERNS if p in xml]
                if leaks: result["prompt_leaks"].append({"slide":n,"patterns":leaks})
        for n, filename in EXPECTED_IMAGES.items():
            sp, rp = slide_path(n), rels_path(n)
            found = False; parts = []
            if sp in names and rp in names:
                targets = rel_targets(z.read(rp), IMAGE_REL)
                root = ET.fromstring(z.read(sp))
                ids = [b.attrib.get(f"{{{NS['r']}}}embed") for b in root.findall(".//a:blip", NS)]
                expected_hash = sha(image_path(filename))
                for rid in ids:
                    target = targets.get(rid or "")
                    if target:
                        part = resolve(sp, target)
                        if part in names:
                            parts.append(part)
                            if hashlib.sha256(z.read(part)).hexdigest() == expected_hash: found = True
            result["images"][str(n)] = {"filename":filename,"found":found,"media_parts":parts}
        matrix_text = text_values(z.read(slide_path(7))) if slide_path(7) in names else []
        result["matrix"] = {"missing_text":[v for v in EXPECTED_MATRIX_TEXT if v not in matrix_text]}
        table_xml = z.read(slide_path(5)) if slide_path(5) in names else b""
        table_text = text_values(table_xml) if table_xml else []
        table_found = bool(ET.fromstring(table_xml).findall(".//a:tbl", NS)) if table_xml else False
        result["table"] = {"found":table_found,"missing_text":[v for v in EXPECTED_TABLE_TEXT if v not in table_text]}
        sp, rp = slide_path(4), rels_path(4); chart_text=[]; chart_parts=[]
        if sp in names and rp in names:
            targets = rel_targets(z.read(rp), CHART_REL); root=ET.fromstring(z.read(sp))
            ids=[c.attrib.get(f"{{{NS['r']}}}id") for c in root.findall(".//c:chart", NS)]
            for rid in ids:
                target=targets.get(rid or "")
                if target:
                    part=resolve(sp,target)
                    if part in names: chart_parts.append(part); chart_text += text_values(z.read(part))
        nums=[]
        for v in chart_text:
            try: nums.append(float(v))
            except ValueError: pass
        result["chart"]={"found":bool(chart_parts),"parts":chart_parts,"missing_text":[v for v in EXPECTED_CHART_TEXT if v not in chart_text],"missing_values":[v for v in EXPECTED_CHART_VALUES if float(v) not in nums]}
    return result

def main() -> int:
    contract=load_json(CONTRACT_PATH); defects=[]
    actual=[s.get("archetype") for s in contract.get("slides",[])]
    if actual != EXPECTED_ARCHETYPES: defects.append(f"Archetype sequence mismatch: {actual}")
    build=DeckBuilder().build_from_contract_file(CONTRACT_PATH); pptx=Path(build.output_pptx_path)
    if not pptx.exists(): defects.append(f"Generated PPTX missing: {pptx}")
    dup=duplicates(pptx) if pptx.exists() else {}
    if dup: defects.append(f"Duplicate ZIP entries: {dup}")
    package=inspect(pptx) if pptx.exists() else {}
    if package.get("slide_count") != 10: defects.append(f"Expected 10 slides, found {package.get('slide_count')}")
    if package.get("prompt_leaks"): defects.append(f"Prompt leaks: {package['prompt_leaks']}")
    for n, item in package.get("images",{}).items():
        if not item.get("found"): defects.append(f"Expected image not found on slide {n}: {item.get('filename')}")
    if package.get("matrix",{}).get("missing_text"): defects.append(f"Matrix text missing: {package['matrix']['missing_text']}")
    if not package.get("table",{}).get("found") or package.get("table",{}).get("missing_text"): defects.append(f"Table validation failed: {package.get('table')}")
    if not package.get("chart",{}).get("found") or package.get("chart",{}).get("missing_text") or package.get("chart",{}).get("missing_values"): defects.append(f"Chart validation failed: {package.get('chart')}")
    report={"contract_used":str(CONTRACT_PATH),"generated_pptx":str(pptx),"slides_generated":package.get("slide_count"),"duplicate_zip_entries":len(dup),"package_validation":package,"visual_validation":{"status":"REQUIRES_MANUAL_REVIEW","instructions":["Confirm both images are visible on slides 6 and 8.","Confirm the matrix is readable on slide 7.","Confirm the chart columns are visible on slide 4.","Confirm the table is readable on slide 5.","Review wrapping, spacing and placeholder cleanup on all slides."]},"defects":defects,"overall_package_status":"PASS" if not defects else "FAIL"}
    REPORT_PATH.parent.mkdir(parents=True,exist_ok=True); REPORT_PATH.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
    print(json.dumps(report,indent=2,ensure_ascii=False)); return 0 if not defects else 1

if __name__ == "__main__": raise SystemExit(main())
