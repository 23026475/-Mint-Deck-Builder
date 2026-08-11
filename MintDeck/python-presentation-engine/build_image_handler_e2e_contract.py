"""
Build a comprehensive ImageHandler E2E validation contract from data/assets/images/images.json.

This script does not modify engine implementation. It reads the local image metadata catalog and writes:
- data/contracts/image_handler_e2e_contract.json
- data/output/image_handler_e2e_validation_checklist.json
- data/output/image_handler_e2e_validation_checklist.md

Run from project root:
    python .\build_image_handler_e2e_contract.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

IMAGE_DIR = Path("data/assets/images")
METADATA_PATH = IMAGE_DIR / "images.json"
CONTRACT_PATH = Path("data/contracts/image_handler_e2e_contract.json")
CHECKLIST_JSON_PATH = Path("data/output/image_handler_e2e_validation_checklist.json")
CHECKLIST_MD_PATH = Path("data/output/image_handler_e2e_validation_checklist.md")
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}

PLACEHOLDER_INDEXES = {
    "image_right": {"picture": 20},
    "quote": {"headshot": 30},
    "team": {"member_picture": [20, 21, 22]},
    "logo_wall": {"logo": [20, 21, 22, 23, 24, 25, 26, 27]},
}


@dataclass(frozen=True)
class CatalogImage:
    filename: str
    category: str | None
    orientation: str | None
    width: int | None
    height: int | None
    tags: tuple[str, ...]


def load_catalog() -> list[CatalogImage]:
    if not METADATA_PATH.exists():
        raise SystemExit(f"Missing metadata catalog: {METADATA_PATH}")

    raw = json.loads(METADATA_PATH.read_text(encoding="utf8"))
    if not isinstance(raw, Mapping):
        raise SystemExit(f"Metadata catalog must be a JSON object: {METADATA_PATH}")

    images: list[CatalogImage] = []
    for filename, metadata in raw.items():
        if not isinstance(filename, str) or not isinstance(metadata, Mapping):
            continue
        if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if not (IMAGE_DIR / filename).exists():
            continue
        tags = metadata.get("tags") or []
        images.append(
            CatalogImage(
                filename=filename,
                category=str(metadata.get("category")).strip() if metadata.get("category") is not None else None,
                orientation=str(metadata.get("orientation")).strip().lower() if metadata.get("orientation") is not None else None,
                width=_safe_int(metadata.get("width")),
                height=_safe_int(metadata.get("height")),
                tags=tuple(str(tag).strip().lower() for tag in tags if str(tag).strip()),
            )
        )

    if len(images) < 8:
        raise SystemExit("Need at least 8 supported local images referenced by images.json for this validation contract.")
    return images


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def score_image(image: CatalogImage, *, preferred_orientation: str | None = None, category_keywords: Iterable[str] = (), tag_keywords: Iterable[str] = ()) -> int:
    score = 0
    if preferred_orientation and image.orientation == preferred_orientation:
        score += 50
    category = (image.category or "").lower()
    for keyword in category_keywords:
        if keyword.lower() in category:
            score += 20
    tags = " ".join(image.tags)
    for keyword in tag_keywords:
        if keyword.lower() in tags:
            score += 10
    # Prefer larger images for visual validation.
    if image.width and image.height:
        score += min((image.width * image.height) // 1_000_000, 15)
    return score


def pick_one(images: list[CatalogImage], used: set[str], *, purpose: str, preferred_orientation: str | None = None, category_keywords: Iterable[str] = (), tag_keywords: Iterable[str] = ()) -> CatalogImage:
    candidates = [image for image in images if image.filename not in used]
    if not candidates:
        raise SystemExit(f"Unable to select image for {purpose}; no unused images remain.")
    candidates.sort(key=lambda img: score_image(img, preferred_orientation=preferred_orientation, category_keywords=category_keywords, tag_keywords=tag_keywords), reverse=True)
    selected = candidates[0]
    used.add(selected.filename)
    return selected


def pick_images(images: list[CatalogImage]) -> dict[str, CatalogImage | list[CatalogImage]]:
    used: set[str] = set()

    hero = pick_one(images, used, purpose="image_right hero", preferred_orientation="landscape", category_keywords=("ai", "tech"), tag_keywords=("artificial intelligence", "cloud", "technology"))
    repeated = hero
    quote = pick_one(images, used, purpose="quote headshot", preferred_orientation="portrait", category_keywords=("people", "corporate"), tag_keywords=("people", "collaboration", "team"))
    team = [
        pick_one(images, used, purpose="team member 1", preferred_orientation="portrait", category_keywords=("people", "corporate"), tag_keywords=("people", "business")),
        pick_one(images, used, purpose="team member 2", preferred_orientation="portrait", category_keywords=("people", "corporate"), tag_keywords=("collaboration", "team")),
        pick_one(images, used, purpose="team member 3", preferred_orientation="landscape", category_keywords=("people", "corporate"), tag_keywords=("meeting", "team")),
    ]
    logos = [
        pick_one(images, used, purpose="logo wall 1", preferred_orientation="square", category_keywords=("design", "logo", "icon"), tag_keywords=("icon", "logo", "design")),
        pick_one(images, used, purpose="logo wall 2", preferred_orientation="square", category_keywords=("design", "logo", "icon"), tag_keywords=("icon", "logo", "design")),
        pick_one(images, used, purpose="logo wall 3", preferred_orientation="landscape", category_keywords=("design", "tech"), tag_keywords=("design", "abstract")),
        pick_one(images, used, purpose="logo wall 4", preferred_orientation="portrait", category_keywords=("design", "uncategorized"), tag_keywords=("screenshot", "design")),
    ]

    # 1 repeated + 8 unique = 9 total references, 8 different images.
    return {"hero": hero, "repeated": repeated, "quote": quote, "team": team, "logos": logos}


def image_info(image: CatalogImage) -> dict[str, Any]:
    return {
        "filename": image.filename,
        "category": image.category,
        "orientation": image.orientation,
        "width": image.width,
        "height": image.height,
        "tags": list(image.tags),
    }


def build_contract(selection: dict[str, CatalogImage | list[CatalogImage]]) -> dict[str, Any]:
    hero = selection["hero"]
    repeated = selection["repeated"]
    quote = selection["quote"]
    team = selection["team"]
    logos = selection["logos"]
    assert isinstance(hero, CatalogImage)
    assert isinstance(repeated, CatalogImage)
    assert isinstance(quote, CatalogImage)
    assert isinstance(team, list)
    assert isinstance(logos, list)

    return {
        "title": "Image Handler E2E Validation",
        "description": "Validation contract dedicated to ImageHandler local image insertion, placeholder mapping, letterboxing and cache behaviour.",
        "slides": [
            {
                "archetype": "image_right",
                "action_title": "Landscape image insertion preserves the template.",
                "fields": {
                    "kicker": "IMAGE HANDLER",
                    "body": "This slide validates a single local image inserted into the image-right picture placeholder while preserving layout geometry.",
                    "picture": hero.filename,
                },
                "validation_notes": {"purpose": "single landscape image; letterboxing and placeholder geometry check", "selected_image": image_info(hero)},
            },
            {
                "archetype": "quote",
                "fields": {
                    "quote": "Local image support is validated through the media orchestration layer.",
                    "attribution": "Presentation Engine Validation",
                    "role": "Image pipeline regression test",
                    "headshot": quote.filename,
                },
                "validation_notes": {"purpose": "quote headshot image insertion", "selected_image": image_info(quote)},
            },
            {
                "archetype": "team",
                "action_title": "Multiple team images validate repeated placeholder mapping.",
                "fields": {
                    "members": [
                        {"name": "Validation Member 1", "role": "Image catalog resolution", "picture": team[0].filename},
                        {"name": "Validation Member 2", "role": "Placeholder mapping", "picture": team[1].filename},
                        {"name": "Validation Member 3", "role": "Letterboxing review", "picture": team[2].filename},
                    ]
                },
                "validation_notes": {"purpose": "three images on one slide; member_picture occurrence mapping", "selected_images": [image_info(image) for image in team]},
            },
            {
                "archetype": "logo_wall",
                "action_title": "Logo wall validates multiple picture placeholders.",
                "fields": {
                    "kicker": "MEDIA REGRESSION",
                    "caption": "This slide validates multiple mapped media placeholders and mixed aspect ratios.",
                    "logos": [image.filename for image in logos],
                },
                "validation_notes": {"purpose": "multiple images on one slide; logo occurrence mapping", "selected_images": [image_info(image) for image in logos]},
            },
            {
                "archetype": "image_right",
                "action_title": "Repeated image validates ImageCatalog cache behaviour.",
                "fields": {
                    "kicker": "CACHE CHECK",
                    "body": "This slide intentionally reuses the first image to confirm repeated image references resolve consistently through the catalog cache.",
                    "picture": repeated.filename,
                },
                "validation_notes": {"purpose": "repeated image usage for cache validation", "selected_image": image_info(repeated)},
            },
        ],
    }


def build_checklist(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    checklist: list[dict[str, Any]] = []
    for slide_number, slide in enumerate(contract["slides"], start=1):
        archetype = slide["archetype"]
        if archetype == "image_right":
            checklist.append({
                "slide_number": slide_number,
                "archetype": archetype,
                "expected_image_filenames": [slide["fields"]["picture"]],
                "placeholder_fields": ["picture"],
                "expected_placeholder_indexes": [PLACEHOLDER_INDEXES[archetype]["picture"]],
                "expected_image_orientation": [slide["validation_notes"]["selected_image"].get("orientation")],
                "expected_behaviour": slide["validation_notes"]["purpose"],
            })
        elif archetype == "quote":
            checklist.append({
                "slide_number": slide_number,
                "archetype": archetype,
                "expected_image_filenames": [slide["fields"]["headshot"]],
                "placeholder_fields": ["headshot"],
                "expected_placeholder_indexes": [PLACEHOLDER_INDEXES[archetype]["headshot"]],
                "expected_image_orientation": [slide["validation_notes"]["selected_image"].get("orientation")],
                "expected_behaviour": slide["validation_notes"]["purpose"],
            })
        elif archetype == "team":
            selected = slide["validation_notes"]["selected_images"]
            checklist.append({
                "slide_number": slide_number,
                "archetype": archetype,
                "expected_image_filenames": [member["picture"] for member in slide["fields"]["members"]],
                "placeholder_fields": ["member_picture[0]", "member_picture[1]", "member_picture[2]"],
                "expected_placeholder_indexes": PLACEHOLDER_INDEXES[archetype]["member_picture"],
                "expected_image_orientation": [item.get("orientation") for item in selected],
                "expected_behaviour": slide["validation_notes"]["purpose"],
            })
        elif archetype == "logo_wall":
            selected = slide["validation_notes"]["selected_images"]
            indexes = PLACEHOLDER_INDEXES[archetype]["logo"][: len(slide["fields"]["logos"])]
            checklist.append({
                "slide_number": slide_number,
                "archetype": archetype,
                "expected_image_filenames": slide["fields"]["logos"],
                "placeholder_fields": [f"logo[{i}]" for i in range(len(slide["fields"]["logos"]))],
                "expected_placeholder_indexes": indexes,
                "expected_image_orientation": [item.get("orientation") for item in selected],
                "expected_behaviour": slide["validation_notes"]["purpose"],
            })
    return checklist


def write_markdown_checklist(checklist: list[dict[str, Any]]) -> None:
    lines = ["# Image Handler E2E Validation Checklist", ""]
    lines.append("| Slide | Archetype | Images | Fields | Placeholder idx | Orientation | Expected behaviour |")
    lines.append("|---:|---|---|---|---|---|---|")
    for item in checklist:
        lines.append(
            "| {slide_number} | {archetype} | {images} | {fields} | {indexes} | {orientations} | {behaviour} |".format(
                slide_number=item["slide_number"],
                archetype=item["archetype"],
                images="<br>".join(item["expected_image_filenames"]),
                fields="<br>".join(item["placeholder_fields"]),
                indexes="<br>".join(str(idx) for idx in item["expected_placeholder_indexes"]),
                orientations="<br>".join(str(value) for value in item["expected_image_orientation"]),
                behaviour=item["expected_behaviour"],
            )
        )
    CHECKLIST_MD_PATH.write_text("\n".join(lines), encoding="utf8")


def main() -> int:
    images = load_catalog()
    selection = pick_images(images)
    contract = build_contract(selection)
    checklist = build_checklist(contract)

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKLIST_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    CONTRACT_PATH.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf8")
    CHECKLIST_JSON_PATH.write_text(json.dumps(checklist, indent=2, ensure_ascii=False), encoding="utf8")
    write_markdown_checklist(checklist)

    unique_images = sorted({filename for item in checklist for filename in item["expected_image_filenames"]})
    print("Image Handler E2E contract created")
    print("- Contract:", CONTRACT_PATH)
    print("- Checklist JSON:", CHECKLIST_JSON_PATH)
    print("- Checklist MD:", CHECKLIST_MD_PATH)
    print("- Slides:", len(contract["slides"]))
    print("- Image references:", sum(len(item["expected_image_filenames"]) for item in checklist))
    print("- Unique images:", len(unique_images))
    for filename in unique_images:
        print("  -", filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
