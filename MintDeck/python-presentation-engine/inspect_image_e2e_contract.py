import json
from pathlib import Path
from PIL import Image

CONTRACT_PATH = Path(r".\data\input\image_e2e_validation_contract.json")
IMAGE_DIR = Path(r".\data\assets\images")
METADATA_PATH = IMAGE_DIR / "images.json"
REPORT_PATH = Path(r".\data\output\image_e2e_contract_inspection_report.json")

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}

FAKE_FILENAMES = {
    "hero.jpg",
    "headshot.png",
    "member1.jpg",
    "member2.jpg",
    "member3.jpg",
    "logo1.png",
    "logo2.png",
    "logo3.png",
    "logo4.png",
}


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    text = path.read_text(encoding="utf8").strip()

    if not text:
        raise ValueError(f"File is empty: {path}")

    return json.loads(text)


def collect_image_references(contract):
    references = []

    for slide_number, slide in enumerate(contract.get("slides", []), start=1):
        archetype = slide.get("archetype")
        fields = slide.get("fields", {})

        if isinstance(fields, dict) and fields.get("picture"):
            references.append(
                {
                    "slide_number": slide_number,
                    "archetype": archetype,
                    "field": "picture",
                    "filename": fields["picture"],
                    "expected_role": "image_right",
                }
            )

        if isinstance(fields, dict) and fields.get("headshot"):
            references.append(
                {
                    "slide_number": slide_number,
                    "archetype": archetype,
                    "field": "headshot",
                    "filename": fields["headshot"],
                    "expected_role": "quote headshot",
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
                            "field": f"members.{index}.picture",
                            "filename": member["picture"],
                            "expected_role": "team member",
                        }
                    )

        logos = fields.get("logos") if isinstance(fields, dict) else None

        if isinstance(logos, list):
            for index, logo in enumerate(logos):
                references.append(
                    {
                        "slide_number": slide_number,
                        "archetype": archetype,
                        "field": f"logos.{index}",
                        "filename": logo,
                        "expected_role": "logo wall",
                    }
                )

    return references


def resolve_case_insensitive(filename):
    direct = IMAGE_DIR / filename

    if direct.exists():
        return direct

    wanted = filename.lower()

    for path in IMAGE_DIR.rglob("*"):
        if not path.is_file():
            continue

        relative_name = str(path.relative_to(IMAGE_DIR)).replace("\\", "/").lower()

        if relative_name == wanted or path.name.lower() == wanted:
            return path

    return None


def can_decode(path):
    try:
        with Image.open(path) as img:
            width, height = img.size
            image_format = img.format
            img.verify()

        return True, None, {
            "width": width,
            "height": height,
            "format": image_format,
        }

    except Exception as exc:
        return False, str(exc), None


def role_fit(reference, metadata_entry):
    role = reference["expected_role"]
    category = ""
    orientation = ""
    notes = []
    appropriate = True

    if isinstance(metadata_entry, dict):
        category = str(metadata_entry.get("category", "")).lower()
        orientation = str(metadata_entry.get("orientation", "")).lower()

    if role == "quote headshot":
        if "people" not in category and "corporate" not in category:
            appropriate = False
            notes.append("Quote headshot should preferably use a people/corporate image.")

    elif role == "team member":
        if "people" not in category and "corporate" not in category:
            appropriate = False
            notes.append("Team member image should preferably use a people/corporate image.")

    elif role == "logo wall":
        if "design" not in category and "logo" not in category and "icon" not in category:
            notes.append("Logo wall image is not clearly marked as design/logo/icon in metadata.")

    elif role == "image_right":
        if orientation not in {"landscape", "portrait", "square"}:
            notes.append("Orientation metadata is missing or unclear.")

    return {
        "appropriate": appropriate,
        "category": category,
        "orientation": orientation,
        "notes": notes,
    }


def main():
    contract = load_json(CONTRACT_PATH)
    metadata = load_json(METADATA_PATH) if METADATA_PATH.exists() else {}

    references = collect_image_references(contract)
    inspected = []

    for reference in references:
        filename = reference["filename"]
        resolved_path = resolve_case_insensitive(filename)

        exists = resolved_path is not None
        supported_extension = Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS

        decode_success = False
        decode_error = None
        decoded_metadata = None

        if exists:
            decode_success, decode_error, decoded_metadata = can_decode(resolved_path)

        metadata_entry = metadata.get(filename)

        if metadata_entry is None and exists:
            metadata_entry = metadata.get(resolved_path.name)

        role_assessment = role_fit(reference, metadata_entry)

        inspected.append(
            {
                **reference,
                "exists": exists,
                "resolved_path": str(resolved_path) if resolved_path else None,
                "supported_extension": supported_extension,
                "decode_success": decode_success,
                "decode_error": decode_error,
                "metadata_found": metadata_entry is not None,
                "metadata": metadata_entry,
                "decoded_metadata": decoded_metadata,
                "role_assessment": role_assessment,
            }
        )

    fake_names = [
        item for item in inspected
        if item["filename"].lower() in FAKE_FILENAMES
    ]

    missing = [item for item in inspected if not item["exists"]]
    unreadable = [item for item in inspected if item["exists"] and not item["decode_success"]]
    unsupported = [item for item in inspected if not item["supported_extension"]]
    inappropriate = [
        item for item in inspected
        if not item["role_assessment"]["appropriate"]
    ]

    unique_images = sorted({item["filename"] for item in inspected})

    recommended_changes = []

    if fake_names:
        recommended_changes.append(
            "Replace fake/sample filenames before rerunning image E2E validation."
        )

    if missing:
        recommended_changes.append(
            "Replace missing image references with existing filenames from data/assets/images."
        )

    if unreadable:
        recommended_changes.append(
            "Replace only unreadable image references with appropriate readable assets from data/assets/images."
        )

    if not (8 <= len(unique_images) <= 10):
        recommended_changes.append(
            "Contract does not currently provide 8 to 10 unique real images."
        )

    report = {
        "contract_path": str(CONTRACT_PATH),
        "image_directory": str(IMAGE_DIR),
        "total_image_references": len(inspected),
        "unique_image_count": len(unique_images),
        "unique_images": unique_images,
        "coverage_is_adequate_8_to_10_real_images": 8 <= len(unique_images) <= 10,
        "fake_or_sample_filenames": fake_names,
        "missing_images": missing,
        "unsupported_images": unsupported,
        "unreadable_images": unreadable,
        "role_inappropriate_images": inappropriate,
        "images": inspected,
        "recommended_changes": recommended_changes,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf8",
    )

    print("Image E2E contract inspection")
    print(f"- Contract: {CONTRACT_PATH}")
    print(f"- Image references: {len(inspected)}")
    print(f"- Unique images: {len(unique_images)}")
    print(f"- Fake/sample filenames: {len(fake_names)}")
    print(f"- Missing images: {len(missing)}")
    print(f"- Unreadable images: {len(unreadable)}")
    print(f"- Unsupported images: {len(unsupported)}")
    print(f"- Role-inappropriate images: {len(inappropriate)}")
    print(f"- Adequate 8-10 image coverage: {report['coverage_is_adequate_8_to_10_real_images']}")
    print(f"- Report written: {REPORT_PATH}")

    if unreadable:
        print()
        print("Unreadable images:")
        for item in unreadable:
            print(
                f"  Slide {item['slide_number']} {item['archetype']} {item['field']}: "
                f"{item['filename']} -> {item['decode_error']}"
            )

    if missing:
        print()
        print("Missing images:")
        for item in missing:
            print(
                f"  Slide {item['slide_number']} {item['archetype']} {item['field']}: "
                f"{item['filename']}"
            )

    if fake_names:
        print()
        print("Fake/sample filenames:")
        for item in fake_names:
            print(
                f"  Slide {item['slide_number']} {item['archetype']} {item['field']}: "
                f"{item['filename']}"
            )

    if inappropriate:
        print()
        print("Role-inappropriate images:")
        for item in inappropriate:
            print(
                f"  Slide {item['slide_number']} {item['archetype']} {item['field']}: "
                f"{item['filename']} -> {item['role_assessment']['notes']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
