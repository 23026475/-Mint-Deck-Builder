"""
Image placeholder mapper for the Python Presentation Engine.

Loads PowerPoint placeholder indexes for image fields from configuration so that
ImageHandler does not contain template-specific placeholder mappings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


DEFAULT_IMAGE_PLACEHOLDER_MAPPING_PATH = Path("config/image-placeholder-baseline.json")
BASELINE_ID_TO_ARCHETYPE = {"B04": "image_right", "B06": "quote", "E01": "team", "E03": "logo_wall"}


class ImagePlaceholderMapperException(Exception):
    """Raised when image placeholder mapping cannot be loaded or resolved."""


class ImagePlaceholderMappingNotFoundException(ImagePlaceholderMapperException):
    """Raised when an image placeholder mapping is missing."""


@dataclass(frozen=True)
class ImagePlaceholderMapping:
    archetype: str
    field_name: str
    idx: int
    occurrence: Optional[int] = None


@dataclass
class ImagePlaceholderMapper:
    mapping_path: Path | str = DEFAULT_IMAGE_PLACEHOLDER_MAPPING_PATH
    mappings: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if self.mappings is None:
            self.mappings = self._load_mappings(Path(self.mapping_path))

    def resolve(self, archetype: str, field_name: str, occurrence: int | None = None) -> ImagePlaceholderMapping:
        canonical = self._canonical_archetype(archetype)
        archetype_mapping = self.mappings.get(canonical) if self.mappings else None
        if archetype_mapping is None:
            raise ImagePlaceholderMappingNotFoundException(f"No image placeholder mapping exists for archetype '{canonical}'.")
        if field_name not in archetype_mapping:
            raise ImagePlaceholderMappingNotFoundException(
                f"No image placeholder mapping exists for archetype '{canonical}', field '{field_name}'."
            )
        idx = self._resolve_idx_value(canonical, field_name, archetype_mapping[field_name], occurrence)
        return ImagePlaceholderMapping(archetype=canonical, field_name=field_name, idx=idx, occurrence=occurrence)

    def _load_mappings(self, path: Path) -> Mapping[str, Any]:
        if not path.exists():
            raise ImagePlaceholderMappingNotFoundException(f"Image placeholder mapping file was not found: '{path}'.")
        try:
            return json.loads(path.read_text(encoding="utf8"))
        except json.JSONDecodeError as exc:
            raise ImagePlaceholderMapperException(f"Invalid image placeholder mapping JSON: '{path}'.") from exc

    def _resolve_idx_value(self, archetype: str, field_name: str, raw_value: Any, occurrence: int | None) -> int:
        if isinstance(raw_value, int):
            if occurrence not in (None, 0):
                raise ImagePlaceholderMappingNotFoundException(
                    f"Mapping for archetype '{archetype}', field '{field_name}' does not support occurrence {occurrence}."
                )
            return raw_value
        if isinstance(raw_value, list):
            if occurrence is None:
                if len(raw_value) == 1:
                    return int(raw_value[0])
                raise ImagePlaceholderMappingNotFoundException(
                    f"Mapping for archetype '{archetype}', field '{field_name}' requires an occurrence index."
                )
            if occurrence < 0 or occurrence >= len(raw_value):
                raise ImagePlaceholderMappingNotFoundException(
                    f"No placeholder mapping for archetype '{archetype}', field '{field_name}', occurrence {occurrence}."
                )
            return int(raw_value[occurrence])
        if isinstance(raw_value, dict):
            if "idx" in raw_value:
                return self._resolve_idx_value(archetype, field_name, raw_value["idx"], occurrence)
            if "indexes" in raw_value:
                return self._resolve_idx_value(archetype, field_name, raw_value["indexes"], occurrence)
        raise ImagePlaceholderMapperException(
            f"Invalid mapping value for archetype '{archetype}', field '{field_name}': {raw_value!r}."
        )

    def _canonical_archetype(self, archetype: str) -> str:
        return BASELINE_ID_TO_ARCHETYPE.get(archetype.upper(), archetype.strip().lower())
