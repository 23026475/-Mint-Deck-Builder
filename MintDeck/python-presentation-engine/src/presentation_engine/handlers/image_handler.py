"""
Image handler for the Python Presentation Engine.

Inserts local images into existing PowerPoint picture placeholders through a
mapper and catalog. It never creates slides, resolves layouts, populates text,
or knows about other media types.
"""

from __future__ import annotations

import shutil
import tempfile
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from presentation_engine.handlers.image_catalog import (
    ImageCatalog,
    ImageCatalogException,
    ImageCatalogNotFoundException,
    ImageCatalogUnsupportedFormatException,
    ImageCatalogUnreadableException,
    ImageMetadata,
)
from presentation_engine.handlers.image_placeholder_mapper import ImagePlaceholderMapper

logger = logging.getLogger(__name__)


class ImageHandlerException(Exception):
    """Raised when image insertion fails."""


class ImageNotFoundException(ImageHandlerException):
    """Raised when a referenced image cannot be found."""


class UnsupportedImageFormatException(ImageHandlerException):
    """Raised when a referenced image format is unsupported."""


class UnreadableImageException(ImageHandlerException):
    """Raised when a referenced image cannot be loaded."""


class ImagePlaceholderNotFoundException(ImageHandlerException):
    """Raised when an expected picture placeholder cannot be found."""


BASELINE_ID_TO_ARCHETYPE = {"B04": "image_right", "B06": "quote", "E01": "team", "E03": "logo_wall"}


@dataclass(frozen=True)
class ImageContractField:
    field_name: str
    source: str
    occurrence: int | None = None


@dataclass
class ImageHandler:
    image_catalog: ImageCatalog = field(default_factory=ImageCatalog)
    placeholder_mapper: ImagePlaceholderMapper = field(default_factory=ImagePlaceholderMapper)
    log: logging.Logger = field(default_factory=lambda: logger)

    def insert_images(self, slide: Any, slide_definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        archetype = self._canonical_archetype(self._read_archetype(slide_definition))
        inserted: list[dict[str, Any]] = []
        inserted_indexes: set[int] = set()

        for field in self._image_contract_fields(archetype, slide_definition):
            image_reference = self._normalise_image_reference(self._value_from_path(slide_definition, field.source))
            if image_reference is None:
                continue
            try:
                mapping = self.placeholder_mapper.resolve(archetype, field.field_name, field.occurrence)
                idx = mapping.idx
                if idx in inserted_indexes:
                    continue
                placeholder = self._picture_placeholder_by_idx(slide, idx)
                if placeholder is None:
                    raise ImagePlaceholderNotFoundException(
                        f"Picture placeholder idx {idx} was not found for archetype '{archetype}', media field '{field.field_name}'."
                    )
                image_path = self._resolve_image_path(image_reference, archetype)
                metadata = self._resolve_image_metadata(image_path, image_reference, archetype)
                picture = self._insert_letterboxed_image(placeholder, image_path, metadata)
                inserted_indexes.add(idx)
                report = {
                    "archetype": archetype,
                    "media_field": field.field_name,
                    "source": field.source,
                    "resolved_filename": str(image_path),
                    "resolved_placeholder_idx": idx,
                    "placeholder_idx": idx,
                    "insertion_success": True,
                    "image_width": metadata.width,
                    "image_height": metadata.height,
                    "image_format": metadata.format,
                    "letterbox_crop": self._picture_crop_report(picture),
                }
                inserted.append(report)
                self.log.info("image inserted", extra=report)
            except Exception:
                self.log.exception("image insertion failed", extra={"archetype": archetype, "media_field": field.field_name, "image_reference": image_reference})
                raise

        return inserted

    def _image_contract_fields(self, archetype: str, slide_definition: Mapping[str, Any]) -> list[ImageContractField]:
        if archetype == "image_right":
            return [ImageContractField("picture", "fields.picture"), ImageContractField("picture", "fields.image")]
        if archetype == "quote":
            return [ImageContractField("headshot", "fields.headshot")]
        if archetype == "team":
            members = self._value_from_path(slide_definition, "fields.members")
            count = len(members) if isinstance(members, Sequence) and not isinstance(members, (str, bytes)) else 0
            return [ImageContractField("member_picture", f"fields.members.{index}.picture", index) for index in range(count)]
        if archetype == "logo_wall":
            logos = self._value_from_path(slide_definition, "fields.logos")
            count = len(logos) if isinstance(logos, Sequence) and not isinstance(logos, (str, bytes)) else 0
            return [ImageContractField("logo", f"fields.logos.{index}", index) for index in range(count)]
        return []

    def _read_archetype(self, slide_definition: Mapping[str, Any]) -> str:
        archetype = slide_definition.get("archetype")
        if not isinstance(archetype, str) or not archetype.strip():
            raise ImageHandlerException("Slide definition must contain a non-empty 'archetype'.")
        return archetype.strip().lower()

    def _canonical_archetype(self, archetype: str) -> str:
        return BASELINE_ID_TO_ARCHETYPE.get(archetype.upper(), archetype)

    def _value_from_path(self, item: Mapping[str, Any], source: str) -> Any:
        current: Any = item
        for part in source.split("."):
            if isinstance(current, Mapping):
                current = current.get(part)
            elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
                if not part.isdigit():
                    return None
                index = int(part)
                current = current[index] if index < len(current) else None
            else:
                return None
        return current

    def _normalise_image_reference(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, Mapping):
            for key in ("path", "file", "filename", "name", "src"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        return None

    def _picture_placeholder_by_idx(self, slide: Any, idx: int) -> Any | None:
        for placeholder in getattr(slide, "placeholders", []):
            try:
                if int(placeholder.placeholder_format.idx) == idx:
                    return placeholder
            except Exception:
                continue
        return None

    def _resolve_image_path(self, image_reference: str, archetype: str) -> Path:
        try:
            return self.image_catalog.resolve(image_reference)
        except ImageCatalogUnsupportedFormatException as exc:
            raise UnsupportedImageFormatException(f"Unsupported image '{image_reference}' for archetype '{archetype}'. {exc}") from exc
        except ImageCatalogNotFoundException as exc:
            raise ImageNotFoundException(f"Image '{image_reference}' for archetype '{archetype}' could not be found. {exc}") from exc
        except ImageCatalogException as exc:
            raise ImageHandlerException(f"Image '{image_reference}' for archetype '{archetype}' could not be resolved. {exc}") from exc

    def _resolve_image_metadata(self, image_path: Path, image_reference: str, archetype: str) -> ImageMetadata:
        try:
            return self.image_catalog.metadata(image_path)
        except ImageCatalogUnsupportedFormatException as exc:
            raise UnsupportedImageFormatException(f"Unsupported image '{image_reference}' for archetype '{archetype}'. {exc}") from exc
        except ImageCatalogUnreadableException as exc:
            raise UnreadableImageException(f"Image '{image_reference}' for archetype '{archetype}' could not be loaded. {exc}") from exc
        except ImageCatalogException as exc:
            raise ImageHandlerException(f"Image '{image_reference}' for archetype '{archetype}' could not be inspected. {exc}") from exc

    def _insert_letterboxed_image(self, placeholder: Any, image_path: Path, metadata: ImageMetadata) -> Any:
        """
        Insert an image into an existing picture placeholder using letterboxing.

        python-pptx placeholder.insert_picture() uses the source image filename
        when constructing XML for placeholder pictures. FY27 image filenames can
        contain XML-sensitive characters such as '&'. To preserve the canonical
        original asset name while avoiding XML parsing failures, insert from a
        temporary copy with a safe generated filename.

        This method does not rename, modify, move, or resize the original image.
        It also does not move or resize the placeholder. It copies placeholder
        geometry to the inserted picture and applies letterbox crop values so the
        image aspect ratio is preserved.
        """

        left = placeholder.left
        top = placeholder.top
        width = placeholder.width
        height = placeholder.height

        if not hasattr(placeholder, "insert_picture"):
            raise ImagePlaceholderNotFoundException(
                "Target placeholder does not support insert_picture()."
            )

        suffix = image_path.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            suffix = ".img"

        with tempfile.TemporaryDirectory(prefix="presentation_engine_image_") as temp_dir:
            safe_image_path = Path(temp_dir) / f"image{suffix}"
            shutil.copyfile(image_path, safe_image_path)
            picture = placeholder.insert_picture(str(safe_image_path))

        picture.left = left
        picture.top = top
        picture.width = width
        picture.height = height

        crop = self._calculate_letterbox_crop(
            int(width),
            int(height),
            metadata.width,
            metadata.height,
        )

        for name, value in crop.items():
            if hasattr(picture, name):
                setattr(picture, name, value)

        return picture

    def _calculate_letterbox_crop(self, placeholder_width: int, placeholder_height: int, image_width: int, image_height: int) -> dict[str, float]:
        placeholder_ratio = placeholder_width / placeholder_height
        image_ratio = image_width / image_height
        crop = {"crop_left": 0.0, "crop_right": 0.0, "crop_top": 0.0, "crop_bottom": 0.0}
        if image_ratio > placeholder_ratio:
            fitted_height = placeholder_width / image_ratio
            negative_crop = -((placeholder_height - fitted_height) / 2) / max(fitted_height, 1)
            crop["crop_top"] = negative_crop
            crop["crop_bottom"] = negative_crop
        elif image_ratio < placeholder_ratio:
            fitted_width = placeholder_height * image_ratio
            negative_crop = -((placeholder_width - fitted_width) / 2) / max(fitted_width, 1)
            crop["crop_left"] = negative_crop
            crop["crop_right"] = negative_crop
        return crop

    def _picture_crop_report(self, picture: Any) -> dict[str, float | None]:
        return {
            "crop_left": getattr(picture, "crop_left", None),
            "crop_right": getattr(picture, "crop_right", None),
            "crop_top": getattr(picture, "crop_top", None),
            "crop_bottom": getattr(picture, "crop_bottom", None),
        }
