from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from presentation_engine.handlers.image_catalog import ImageCatalog
from presentation_engine.handlers.image_placeholder_mapper import ImagePlaceholderMapper

CONTRACT_PATH = Path("data/contracts/image_handler_e2e_contract.json")
CHECKLIST_PATH = Path("data/output/image_handler_e2e_validation_checklist.json")


def value_from_path(item: Mapping[str, Any], source: str) -> Any:
    current: Any = item
    for part in source.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            if not part.isdigit():
                return None
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        else:
            return None
    return current


def image_requests(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for slide_no, slide in enumerate(contract["slides"], start=1):
        archetype = slide["archetype"]
        if archetype == "image_right":
            requests.append({"slide": slide_no, "archetype": archetype, "field": "picture", "source": "fields.picture", "occurrence": None})
        elif archetype == "quote":
            requests.append({"slide": slide_no, "archetype": archetype, "field": "headshot", "source": "fields.headshot", "occurrence": None})
        elif archetype == "team":
            for i, _member in enumerate(slide["fields"].get("members", [])):
                requests.append({"slide": slide_no, "archetype": archetype, "field": "member_picture", "source": f"fields.members.{i}.picture", "occurrence": i})
        elif archetype == "logo_wall":
            for i, _logo in enumerate(slide["fields"].get("logos", [])):
                requests.append({"slide": slide_no, "archetype": archetype, "field": "logo", "source": f"fields.logos.{i}", "occurrence": i})
    return requests


def test_contract_exists_and_uses_between_8_and_10_image_references():
    assert CONTRACT_PATH.exists(), f"Missing contract: {CONTRACT_PATH}"
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf8"))
    requests = image_requests(contract)
    assert 8 <= len(requests) <= 10


def test_every_referenced_image_resolves_through_image_catalog():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf8"))
    catalog = ImageCatalog()
    for request in image_requests(contract):
        filename = value_from_path(contract["slides"][request["slide"] - 1], request["source"])
        assert isinstance(filename, str) and filename.strip()
        resolved = catalog.resolve(filename)
        metadata = catalog.metadata(resolved)
        assert resolved.exists()
        assert metadata.width > 0
        assert metadata.height > 0


def test_every_referenced_placeholder_resolves_from_mapper():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf8"))
    mapper = ImagePlaceholderMapper()
    for request in image_requests(contract):
        mapping = mapper.resolve(request["archetype"], request["field"], request["occurrence"])
        assert isinstance(mapping.idx, int)
        assert mapping.idx > 0


def test_repeated_image_is_present_for_cache_validation():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf8"))
    filenames = []
    for request in image_requests(contract):
        filenames.append(value_from_path(contract["slides"][request["slide"] - 1], request["source"]))
    duplicates = {filename for filename in filenames if filenames.count(filename) > 1}
    assert duplicates, "Expected at least one repeated image for cache validation."


def test_checklist_matches_contract_requests():
    assert CHECKLIST_PATH.exists(), f"Missing checklist: {CHECKLIST_PATH}"
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf8"))
    checklist = json.loads(CHECKLIST_PATH.read_text(encoding="utf8"))
    request_count = len(image_requests(contract))
    checklist_count = sum(len(item["expected_image_filenames"]) for item in checklist)
    assert checklist_count == request_count
