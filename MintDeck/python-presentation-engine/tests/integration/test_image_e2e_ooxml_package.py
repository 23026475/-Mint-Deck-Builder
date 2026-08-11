from __future__ import annotations

import hashlib
import json
import posixpath
import re
import subprocess
import sys
import unittest
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "data" / "input" / "image_e2e_validation_contract.json"
IMAGE_DIR = PROJECT_ROOT / "data" / "assets" / "images"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
REPORT_PATH = OUTPUT_DIR / "image_e2e_validation_report.json"
E2E_RUNNER = PROJECT_ROOT / "run_image_e2e_validation.py"

EXPECTED_IMAGE_USAGES_BY_SLIDE = {
    1: 1,
    2: 1,
    3: 1,
    4: 3,
    5: 4,
    6: 1,
}

EXPECTED_TOTAL_IMAGE_USAGES = 11
EXPECTED_UNIQUE_SOURCE_IMAGES = 10

IMAGE_RELATIONSHIP_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict:
    if not path.exists():
        raise AssertionError(f"Required file does not exist: {path}")

    text = path.read_text(encoding="utf8").strip()

    if not text:
        raise AssertionError(f"Required JSON file is empty: {path}")

    return json.loads(text)


def collect_contract_image_references(contract: dict) -> list[dict]:
    references: list[dict] = []

    for slide_number, slide in enumerate(contract.get("slides", []), start=1):
        archetype = slide.get("archetype")
        fields = slide.get("fields", {})

        if isinstance(fields, dict) and fields.get("picture"):
            references.append(
                {
                    "slide_number": slide_number,
                    "archetype": archetype,
                    "field": "fields.picture",
                    "filename": fields["picture"],
                }
            )

        if isinstance(fields, dict) and fields.get("headshot"):
            references.append(
                {
                    "slide_number": slide_number,
                    "archetype": archetype,
                    "field": "fields.headshot",
                    "filename": fields["headshot"],
                }
            )

        members = fields.get("members") if isinstance(fields, dict) else None

        if isinstance(members, list):
            for index, member in enumerate(members):
                if isinstance(member, dict) and member.get("picture"):
                    references.append(
                        {
                            "slide_number": slide_number,
                            "archetype": archetype,
                            "field": f"fields.members.{index}.picture",
                            "filename": member["picture"],
                        }
                    )

        logos = fields.get("logos") if isinstance(fields, dict) else None

        if isinstance(logos, list):
            for index, logo in enumerate(logos):
                references.append(
                    {
                        "slide_number": slide_number,
                        "archetype": archetype,
                        "field": f"fields.logos.{index}",
                        "filename": logo,
                    }
                )

    return references


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

    raise AssertionError(f"Image referenced by contract was not found: {filename}")


def duplicate_zip_entries(zip_path: Path) -> dict[str, int]:
    with zipfile.ZipFile(zip_path, "r") as archive:
        counts = Counter(archive.namelist())

    return {name: count for name, count in counts.items() if count > 1}


def latest_image_e2e_pptx() -> Path | None:
    candidates = sorted(
        OUTPUT_DIR.glob("*Image Handler E2E Validation*.pptx"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    return candidates[0] if candidates else None


def pptx_from_report() -> Path | None:
    if not REPORT_PATH.exists():
        return None

    try:
        report = load_json(REPORT_PATH)
    except Exception:
        return None

    generated = report.get("generated_pptx")

    if not generated:
        return None

    path = Path(generated)

    return path if path.exists() else None


def ensure_generated_pptx_exists() -> Path:
    from_report = pptx_from_report()

    if from_report:
        return from_report

    latest = latest_image_e2e_pptx()

    if latest:
        return latest

    if E2E_RUNNER.exists():
        # The existing E2E runner may currently return a failing status because
        # shape_type based image detection is known to be inaccurate. This test
        # validates the generated PPTX at OOXML/package level, so it does not
        # rely on the runner exit code.
        subprocess.run(
            [sys.executable, str(E2E_RUNNER)],
            cwd=PROJECT_ROOT,
            check=False,
        )

    from_report = pptx_from_report()

    if from_report:
        return from_report

    latest = latest_image_e2e_pptx()

    if latest:
        return latest

    raise AssertionError(
        "No generated Image Handler E2E PPTX found. "
        "Run python .\\run_image_e2e_validation.py first."
    )


def relationship_targets_by_id(rels_xml: bytes) -> dict[str, str]:
    root = ET.fromstring(rels_xml)
    targets: dict[str, str] = {}

    for rel in root:
        rel_id = rel.attrib.get("Id")
        rel_type = rel.attrib.get("Type")
        target = rel.attrib.get("Target")

        if rel_id and target and rel_type == IMAGE_RELATIONSHIP_TYPE:
            targets[rel_id] = target

    return targets


def embedded_blip_relationship_ids(slide_xml: bytes) -> list[str]:
    root = ET.fromstring(slide_xml)

    namespaces = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }

    rel_ids: list[str] = []

    for blip in root.findall(".//a:blip", namespaces):
        rel_id = blip.attrib.get(f"{{{namespaces['r']}}}embed")

        if rel_id:
            rel_ids.append(rel_id)

    return rel_ids


def resolve_relationship_target(slide_xml_path: str, target: str) -> str:
    slide_dir = posixpath.dirname(slide_xml_path)
    return posixpath.normpath(posixpath.join(slide_dir, target))


def slide_number_from_path(path: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", path)

    if not match:
        raise ValueError(f"Could not determine slide number from path: {path}")

    return int(match.group(1))


class ImageE2EOoxmlPackageTests(unittest.TestCase):
    def test_generated_pptx_contains_expected_image_usages_at_ooxml_level(self):
        contract = load_json(CONTRACT_PATH)
        references = collect_contract_image_references(contract)

        self.assertEqual(
            len(references),
            EXPECTED_TOTAL_IMAGE_USAGES,
            "The image E2E contract should contain the expected number of image usages.",
        )

        expected_source_hashes_by_slide: dict[int, list[str]] = defaultdict(list)
        expected_unique_source_hashes: set[str] = set()

        for reference in references:
            source_path = resolve_image_case_insensitive(reference["filename"])
            source_hash = sha256_file(source_path)
            expected_source_hashes_by_slide[reference["slide_number"]].append(source_hash)
            expected_unique_source_hashes.add(source_hash)

        self.assertEqual(
            len(expected_unique_source_hashes),
            EXPECTED_UNIQUE_SOURCE_IMAGES,
            "The contract should have 10 unique source images because one image is reused.",
        )

        pptx_path = ensure_generated_pptx_exists()
        self.assertTrue(pptx_path.exists(), f"Generated PPTX does not exist: {pptx_path}")

        duplicates = duplicate_zip_entries(pptx_path)
        self.assertEqual(
            duplicates,
            {},
            f"Generated PPTX contains duplicate ZIP entries: {duplicates}",
        )

        matched_usage_hashes_by_slide: dict[int, list[str]] = defaultdict(list)
        matched_unique_source_hashes: set[str] = set()

        with zipfile.ZipFile(pptx_path, "r") as archive:
            names = set(archive.namelist())
            media_parts = [name for name in names if name.startswith("ppt/media/")]

            self.assertGreater(
                len(media_parts),
                0,
                "Generated PPTX does not contain any ppt/media image parts.",
            )

            media_hashes = {
                media_part: sha256_bytes(archive.read(media_part))
                for media_part in media_parts
            }

            slide_xml_files = sorted(
                [
                    name for name in names
                    if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
                ],
                key=slide_number_from_path,
            )

            for slide_xml_path in slide_xml_files:
                slide_number = slide_number_from_path(slide_xml_path)

                if slide_number not in EXPECTED_IMAGE_USAGES_BY_SLIDE:
                    continue

                rels_path = (
                    slide_xml_path
                    .replace("ppt/slides/", "ppt/slides/_rels/")
                    + ".rels"
                )

                self.assertIn(
                    rels_path,
                    names,
                    f"Slide {slide_number} is missing its relationships part.",
                )

                slide_xml = archive.read(slide_xml_path)
                rels_xml = archive.read(rels_path)
                rel_targets = relationship_targets_by_id(rels_xml)
                embedded_ids = embedded_blip_relationship_ids(slide_xml)

                expected_hashes_for_slide = expected_source_hashes_by_slide[slide_number]

                for rel_id in embedded_ids:
                    target = rel_targets.get(rel_id)

                    if not target:
                        continue

                    media_part = resolve_relationship_target(slide_xml_path, target)

                    if media_part not in media_hashes:
                        continue

                    media_hash = media_hashes[media_part]

                    if media_hash in expected_hashes_for_slide:
                        matched_usage_hashes_by_slide[slide_number].append(media_hash)
                        matched_unique_source_hashes.add(media_hash)

        for slide_number, expected_count in EXPECTED_IMAGE_USAGES_BY_SLIDE.items():
            with self.subTest(slide_number=slide_number):
                actual_count = len(matched_usage_hashes_by_slide.get(slide_number, []))

                self.assertEqual(
                    actual_count,
                    expected_count,
                    (
                        f"Slide {slide_number} should contain {expected_count} expected "
                        f"image usage(s), but OOXML/media hash matching found {actual_count}."
                    ),
                )

        total_usage_count = sum(
            len(items) for items in matched_usage_hashes_by_slide.values()
        )

        self.assertEqual(
            total_usage_count,
            EXPECTED_TOTAL_IMAGE_USAGES,
            "The generated PPTX should contain all 11 expected image usages.",
        )

        self.assertEqual(
            matched_unique_source_hashes,
            expected_unique_source_hashes,
            "The generated PPTX should contain media matching all 10 unique expected source images.",
        )


if __name__ == "__main__":
    unittest.main()
