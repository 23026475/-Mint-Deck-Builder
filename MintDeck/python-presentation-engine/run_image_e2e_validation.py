from __future__ import annotations

import hashlib
import json
import posixpath
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from presentation_engine.builders.deck_builder import DeckBuilder
from presentation_engine.handlers.image_catalog import ImageCatalog
from presentation_engine.handlers.image_placeholder_mapper import ImagePlaceholderMapper


CONTRACT_PATH = Path("data/input/image_e2e_validation_contract.json")
REPORT_PATH = Path("data/output/image_e2e_validation_report.json")
IMAGE_DIR = Path("data/assets/images")

IMAGE_RELATIONSHIP_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
)

PROMPT_LEAK_PATTERNS = (
    "Click to edit Master title style",
    "Click to edit Master text styles",
    "Click to edit Master subtitle style",
    "Click to add title",
    "Click to add text",
)


class ImageE2EValidationException(Exception):
    """Raised when image E2E validation cannot complete."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ImageE2EValidationException(f"Required JSON file does not exist: {path}")

    text = path.read_text(encoding="utf8").strip()

    if not text:
        raise ImageE2EValidationException(f"Required JSON file is empty: {path}")

    return json.loads(text)


def duplicate_zip_entries(pptx_path: Path) -> dict[str, int]:
    with zipfile.ZipFile(pptx_path, "r") as archive:
        counts = Counter(archive.namelist())

    return {name: count for name, count in counts.items() if count > 1}


def canonical_media_field(field: str) -> str:
    if field == "picture":
        return "picture"
    if field == "headshot":
        return "headshot"
    if field.startswith("members."):
        return "member_picture"
    if field.startswith("logos."):
        return "logo"
    return field


def image_contract_references(contract: dict[str, Any]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []

    for slide_number, slide in enumerate(contract.get("slides", []), start=1):
        archetype = slide.get("archetype")
        fields = slide.get("fields", {})

        if not isinstance(fields, dict):
            continue

        if fields.get("picture"):
            references.append(
                {
                    "slide_number": slide_number,
                    "archetype": archetype,
                    "media_field": "picture",
                    "source": "fields.picture",
                    "image_reference": fields["picture"],
                    "occurrence": None,
                }
            )

        if fields.get("image"):
            references.append(
                {
                    "slide_number": slide_number,
                    "archetype": archetype,
                    "media_field": "picture",
                    "source": "fields.image",
                    "image_reference": fields["image"],
                    "occurrence": None,
                }
            )

        if fields.get("headshot"):
            references.append(
                {
                    "slide_number": slide_number,
                    "archetype": archetype,
                    "media_field": "headshot",
                    "source": "fields.headshot",
                    "image_reference": fields["headshot"],
                    "occurrence": None,
                }
            )

        members = fields.get("members")
        if isinstance(members, list):
            for index, member in enumerate(members):
                if isinstance(member, dict) and member.get("picture"):
                    references.append(
                        {
                            "slide_number": slide_number,
                            "archetype": archetype,
                            "media_field": "member_picture",
                            "source": f"fields.members.{index}.picture",
                            "image_reference": member["picture"],
                            "occurrence": index,
                        }
                    )

        logos = fields.get("logos")
        if isinstance(logos, list):
            for index, logo in enumerate(logos):
                references.append(
                    {
                        "slide_number": slide_number,
                        "archetype": archetype,
                        "media_field": "logo",
                        "source": f"fields.logos.{index}",
                        "image_reference": logo,
                        "occurrence": index,
                    }
                )

    return references


def resolve_image_path_case_insensitive(filename: str) -> Path:
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

    raise FileNotFoundError(f"Image file not found under {IMAGE_DIR}: {filename}")


def build_image_resolution_report(
    references: list[dict[str, Any]],
    catalog: ImageCatalog,
    mapper: ImagePlaceholderMapper,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    missing_images: list[dict[str, Any]] = []
    missing_mappings: list[dict[str, Any]] = []

    for reference in references:
        item = dict(reference)
        archetype = item["archetype"]
        media_field = item["media_field"]
        image_reference = item["image_reference"]

        try:
            mapping = mapper.resolve(archetype, media_field, item.get("occurrence"))
            item["resolved_placeholder_idx"] = mapping.idx
            item["placeholder_idx"] = mapping.idx
        except Exception as exc:
            item["status"] = "missing_mapping"
            item["error"] = str(exc)
            missing_mappings.append(item)
            continue

        try:
            image_path = catalog.resolve(image_reference)
            metadata = catalog.metadata(image_path)
            item.update(
                {
                    "status": "resolved",
                    "resolved_filename": str(image_path),
                    "image_width": metadata.width,
                    "image_height": metadata.height,
                    "image_format": metadata.format,
                    "category": metadata.category,
                    "orientation": metadata.orientation,
                    "source_sha256": sha256_file(image_path),
                }
            )
            resolved.append(item)
        except Exception as exc:
            item["status"] = "missing_image"
            item["error"] = str(exc)
            missing_images.append(item)

    return resolved, missing_images, missing_mappings


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


def prompt_leaks_from_slide_xml(slide_xml: bytes) -> list[str]:
    text = slide_xml.decode("utf-8", errors="ignore")
    return [pattern for pattern in PROMPT_LEAK_PATTERNS if pattern in text]


def expected_hashes_by_slide(resolved_images: list[dict[str, Any]]) -> dict[int, list[str]]:
    result: dict[int, list[str]] = defaultdict(list)
    for image in resolved_images:
        result[int(image["slide_number"])].append(image["source_sha256"])
    return result


def inspect_pptx_package(
    pptx_path: Path,
    resolved_images: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_by_slide = expected_hashes_by_slide(resolved_images)
    matched_hashes_by_slide: dict[int, list[str]] = defaultdict(list)
    matched_media_parts_by_slide: dict[int, list[str]] = defaultdict(list)
    prompt_leaks_by_slide: dict[int, list[str]] = defaultdict(list)
    all_media_parts: list[str] = []

    with zipfile.ZipFile(pptx_path, "r") as archive:
        names = set(archive.namelist())
        all_media_parts = sorted(name for name in names if name.startswith("ppt/media/"))

        media_hashes = {
            media_part: sha256_bytes(archive.read(media_part))
            for media_part in all_media_parts
        }

        slide_xml_files = sorted(
            [name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)],
            key=slide_number_from_path,
        )

        for slide_xml_path in slide_xml_files:
            slide_number = slide_number_from_path(slide_xml_path)
            slide_xml = archive.read(slide_xml_path)
            leaks = prompt_leaks_from_slide_xml(slide_xml)
            if leaks:
                prompt_leaks_by_slide[slide_number].extend(leaks)

            if slide_number not in expected_by_slide:
                continue

            rels_path = slide_xml_path.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
            if rels_path not in names:
                continue

            rel_targets = relationship_targets_by_id(archive.read(rels_path))
            embedded_ids = embedded_blip_relationship_ids(slide_xml)
            expected_hashes = expected_by_slide[slide_number]

            for rel_id in embedded_ids:
                target = rel_targets.get(rel_id)
                if not target:
                    continue

                media_part = resolve_relationship_target(slide_xml_path, target)
                if media_part not in media_hashes:
                    continue

                media_hash = media_hashes[media_part]
                if media_hash in expected_hashes:
                    matched_hashes_by_slide[slide_number].append(media_hash)
                    matched_media_parts_by_slide[slide_number].append(media_part)

    return {
        "pptx_media_parts": all_media_parts,
        "matched_hashes_by_slide": dict(matched_hashes_by_slide),
        "matched_media_parts_by_slide": dict(matched_media_parts_by_slide),
        "prompt_leaks_by_slide": dict(prompt_leaks_by_slide),
    }


def make_slide_reports(
    contract: dict[str, Any],
    resolved_images: list[dict[str, Any]],
    package_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    images_by_slide: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for image in resolved_images:
        images_by_slide[int(image["slide_number"])].append(image)

    matched_hashes_by_slide = package_report["matched_hashes_by_slide"]
    matched_media_parts_by_slide = package_report["matched_media_parts_by_slide"]
    prompt_leaks_by_slide = package_report["prompt_leaks_by_slide"]

    defects: list[str] = []
    slide_reports: list[dict[str, Any]] = []

    for slide_number, slide in enumerate(contract.get("slides", []), start=1):
        archetype = slide.get("archetype")
        image_requests = images_by_slide.get(slide_number, [])
        expected_count = len(image_requests)
        detected_count = len(matched_hashes_by_slide.get(slide_number, []))
        prompt_leaks = prompt_leaks_by_slide.get(slide_number, [])

        status = "PASS"

        if detected_count != expected_count:
            status = "FAIL"
            defects.append(
                f"Slide {slide_number} {archetype}: expected {expected_count} image usage(s), "
                f"but found {detected_count} OOXML package image usage(s)"
            )

        if prompt_leaks:
            status = "FAIL"
            defects.append(f"Slide {slide_number} {archetype}: prompt leakage detected")

        slide_reports.append(
            {
                "slide_number": slide_number,
                "archetype": archetype,
                "image_requests": image_requests,
                # Backward-compatible field name. This now reports OOXML-matched image usages,
                # not python-pptx shape_type values.
                "picture_shapes_detected": detected_count,
                "ooxml_image_usages_detected": detected_count,
                "expected_image_usages": expected_count,
                "matched_media_parts": matched_media_parts_by_slide.get(slide_number, []),
                "has_prompt_leak": bool(prompt_leaks),
                "prompt_leaks": prompt_leaks,
                "status": status,
            }
        )

    return slide_reports, defects


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    references = image_contract_references(contract)

    catalog = ImageCatalog()
    mapper = ImagePlaceholderMapper()

    resolved_images, missing_images, missing_mappings = build_image_resolution_report(
        references,
        catalog,
        mapper,
    )

    result = DeckBuilder().build_from_contract_file(CONTRACT_PATH)
    pptx_path = Path(result.output_pptx_path)

    duplicates = duplicate_zip_entries(pptx_path)
    package_report = inspect_pptx_package(pptx_path, resolved_images)
    slide_reports, defects = make_slide_reports(contract, resolved_images, package_report)

    if missing_images:
        defects.append(f"Missing images: {len(missing_images)}")

    if missing_mappings:
        defects.append(f"Missing mappings: {len(missing_mappings)}")

    if duplicates:
        defects.append(f"Duplicate ZIP entries: {len(duplicates)}")

    total_expected_usages = len(resolved_images)
    total_detected_usages = sum(slide["ooxml_image_usages_detected"] for slide in slide_reports)

    if total_detected_usages != total_expected_usages:
        defects.append(
            f"Expected {total_expected_usages} total image usage(s), found {total_detected_usages}"
        )

    unique_source_hashes = sorted({image["source_sha256"] for image in resolved_images})
    unique_matched_hashes = sorted(
        {
            image_hash
            for hashes in package_report["matched_hashes_by_slide"].values()
            for image_hash in hashes
        }
    )

    if set(unique_matched_hashes) != set(unique_source_hashes):
        defects.append(
            "Generated PPTX does not contain media matches for all unique expected source images"
        )

    report = {
        "contract_used": str(CONTRACT_PATH),
        "generated_pptx": str(pptx_path),
        "duplicate_zip_entries": len(duplicates),
        "duplicate_zip_entry_details": duplicates,
        "images_requested": resolved_images + missing_images + missing_mappings,
        "images_resolved": resolved_images,
        "skipped_insertions": [],
        "missing_images": missing_images,
        "missing_mappings": missing_mappings,
        "pptx_media_parts_count": len(package_report["pptx_media_parts"]),
        "expected_total_image_usages": total_expected_usages,
        "ooxml_total_image_usages_detected": total_detected_usages,
        "expected_unique_source_images": len(unique_source_hashes),
        "ooxml_unique_source_images_detected": len(unique_matched_hashes),
        "slides": slide_reports,
        "defects": defects,
        "overall_status": "PASS" if not defects else "FAIL",
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
