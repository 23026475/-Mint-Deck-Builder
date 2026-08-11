"""
Local image catalog for the Python Presentation Engine.

Responsibilities:
- Resolve local image filenames from the configured image library.
- Load optional image metadata from a JSON catalog.
- Validate supported file extensions.
- Cache resolved image paths and metadata during a run.
- Detect duplicate filenames that would make case-insensitive lookup ambiguous.

The metadata JSON is expected to use image filenames as keys, for example:
{
  "FY27 Ai Image (1).jpg": {
    "category": "ai",
    "orientation": "landscape",
    "width": 7373,
    "height": 4147,
    "tags": ["artificial intelligence", "cloud computing"]
  }
}

This module is independent from PowerPoint and does not download or access remote images.
"""

from __future__ import annotations

import imghdr
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

try:
    from PIL import Image, UnidentifiedImageError
except Exception:  # pragma: no cover
    Image = None
    UnidentifiedImageError = Exception


DEFAULT_IMAGE_LIBRARY_DIR = Path("data/assets/images")
DEFAULT_IMAGE_METADATA_PATH = Path("data/assets/images/images.json")
DEFAULT_SUPPORTED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
REMOTE_PREFIXES = ("http://", "https://", "ftp://", "s3://")


class ImageCatalogException(Exception):
    """Raised when the image catalog cannot resolve or inspect an image."""


class ImageCatalogNotFoundException(ImageCatalogException):
    """Raised when an image file cannot be found."""


class ImageCatalogUnsupportedFormatException(ImageCatalogException):
    """Raised when an image uses an unsupported extension or detected format."""


class ImageCatalogUnreadableException(ImageCatalogException):
    """Raised when an image cannot be opened or decoded."""


class ImageCatalogDuplicateFilenameException(ImageCatalogException):
    """Raised when duplicate filenames make case-insensitive lookup ambiguous."""


class ImageCatalogMetadataException(ImageCatalogException):
    """Raised when image metadata JSON is invalid."""


@dataclass(frozen=True)
class ImageMetadata:
    path: Path
    width: int
    height: int
    format: str
    extension: str
    category: str | None = None
    orientation: str | None = None
    tags: tuple[str, ...] = ()


@dataclass
class ImageCatalog:
    image_library_dir: Path | str = DEFAULT_IMAGE_LIBRARY_DIR
    supported_extensions: Iterable[str] = field(default_factory=lambda: DEFAULT_SUPPORTED_EXTENSIONS)
    metadata_path: Path | str | None = DEFAULT_IMAGE_METADATA_PATH
    validate_file_signature: bool = True

    def __post_init__(self) -> None:
        self.image_library_dir = Path(self.image_library_dir)
        self.supported_extensions = frozenset(self._normalise_extension(ext) for ext in self.supported_extensions)
        self.metadata_path = Path(self.metadata_path) if self.metadata_path is not None else None
        self._index: dict[str, Path] | None = None
        self._resolved_cache: dict[str, Path] = {}
        self._metadata_cache: dict[Path, ImageMetadata] = {}
        self._metadata_index: dict[str, Mapping[str, Any]] | None = None

    def resolve(self, image_reference: str) -> Path:
        """Resolve a filename or relative path case-insensitively."""

        reference = self._validate_reference(image_reference)
        cache_key = reference.replace("\\", "/").lower()
        if cache_key in self._resolved_cache:
            return self._resolved_cache[cache_key]

        candidate = Path(reference)
        self._validate_extension(candidate.suffix)

        base = self.image_library_dir.resolve()
        direct = (base / candidate).resolve()
        self._ensure_inside_library(base, direct, reference)

        if direct.exists():
            self._resolved_cache[cache_key] = direct
            return direct

        index = self._image_index()
        relative_key = str(candidate).replace("\\", "/").lower()
        name_key = candidate.name.lower()
        resolved = index.get(relative_key) or index.get(name_key)
        if resolved is None:
            raise ImageCatalogNotFoundException(
                f"Image file '{reference}' could not be found under '{self.image_library_dir}'."
            )

        self._resolved_cache[cache_key] = resolved
        return resolved

    def metadata(self, image_reference: str | Path) -> ImageMetadata:
        """Return image metadata from JSON when available, validated against the local file."""

        path = image_reference if isinstance(image_reference, Path) else self.resolve(image_reference)
        path = path.resolve()
        if path in self._metadata_cache:
            return self._metadata_cache[path]

        self._validate_extension(path.suffix)
        detected_format = self._validate_decodeable_image(path) if self.validate_file_signature else self._format_from_extension(path.suffix)
        catalog_entry = self._metadata_for_path(path)

        if catalog_entry:
            width = self._safe_positive_int(catalog_entry.get("width"), "width", path)
            height = self._safe_positive_int(catalog_entry.get("height"), "height", path)
            category = self._optional_string(catalog_entry.get("category"))
            orientation = self._optional_string(catalog_entry.get("orientation"))
            tags = tuple(str(tag).strip() for tag in catalog_entry.get("tags", []) if str(tag).strip())
        else:
            width, height = self._read_image_dimensions(path)
            category = None
            orientation = self._orientation_from_dimensions(width, height)
            tags = ()

        metadata = ImageMetadata(
            path=path,
            width=width,
            height=height,
            format=detected_format,
            extension=self._normalise_extension(path.suffix),
            category=category,
            orientation=orientation,
            tags=tags,
        )
        self._metadata_cache[path] = metadata
        return metadata

    def all_metadata(self) -> dict[str, Mapping[str, Any]]:
        """Return loaded raw metadata keyed by lowercase filename/relative path."""
        return dict(self._load_metadata_index())

    def _metadata_for_path(self, path: Path) -> Mapping[str, Any] | None:
        metadata_index = self._load_metadata_index()
        if not metadata_index:
            return None

        base = self.image_library_dir.resolve()
        try:
            relative_key = str(path.relative_to(base)).replace("\\", "/").lower()
        except ValueError:
            relative_key = path.name.lower()

        return metadata_index.get(relative_key) or metadata_index.get(path.name.lower())

    def _load_metadata_index(self) -> dict[str, Mapping[str, Any]]:
        if self._metadata_index is not None:
            return self._metadata_index

        self._metadata_index = {}
        if self.metadata_path is None:
            return self._metadata_index

        path = self.metadata_path
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()

        if not path.exists():
            return self._metadata_index

        try:
            raw = json.loads(path.read_text(encoding="utf8"))
        except json.JSONDecodeError as exc:
            raise ImageCatalogMetadataException(f"Invalid image metadata JSON: '{path}'.") from exc

        if not isinstance(raw, Mapping):
            raise ImageCatalogMetadataException(f"Image metadata JSON must be an object: '{path}'.")

        indexed: dict[str, Mapping[str, Any]] = {}
        for filename, metadata in raw.items():
            if not isinstance(filename, str):
                raise ImageCatalogMetadataException("Image metadata keys must be filenames.")
            if not isinstance(metadata, Mapping):
                raise ImageCatalogMetadataException(f"Metadata for '{filename}' must be an object.")
            indexed[filename.replace("\\", "/").lower()] = metadata
            indexed.setdefault(Path(filename).name.lower(), metadata)

        self._metadata_index = indexed
        return self._metadata_index

    def _validate_reference(self, image_reference: str) -> str:
        if not isinstance(image_reference, str) or not image_reference.strip():
            raise ImageCatalogNotFoundException("Image reference must be a non-empty filename or relative path.")
        reference = image_reference.strip()
        lowered = reference.lower()
        if lowered.startswith(REMOTE_PREFIXES):
            raise ImageCatalogNotFoundException(f"Remote image references are not supported: '{reference}'.")
        if Path(reference).is_absolute():
            raise ImageCatalogNotFoundException(f"Absolute image paths are not supported: '{reference}'.")
        return reference

    def _validate_extension(self, extension: str) -> None:
        normalised = self._normalise_extension(extension)
        if normalised not in self.supported_extensions:
            raise ImageCatalogUnsupportedFormatException(
                f"Unsupported image format '{extension}'. Supported formats: {sorted(self.supported_extensions)}."
            )

    def _validate_decodeable_image(self, path: Path) -> str:
        """
        Validate that the image can be decoded by Pillow.

        Pillow verify() checks image integrity but leaves the image object
        unusable afterwards, so this method opens the file twice:
        first to verify, then again to load.
        """

        try:
            with Image.open(path) as image:
                detected_format = image.format
                image.verify()

            with Image.open(path) as image:
                image.load()
                detected_format = detected_format or image.format

            if not detected_format:
                return self._format_from_extension(path.suffix)

            return str(detected_format).lower()

        except Exception as exc:
            raise ImageCatalogUnreadableException(
                f"Image file could not be decoded: '{path}'."
            ) from exc
        
    def _read_image_dimensions(self, path: Path) -> tuple[int, int]:
        if Image is None:
            raise ImageCatalogUnreadableException("Pillow is required to read image dimensions.")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageCatalogUnreadableException(f"Image file could not be opened: '{path}'.") from exc
        if width <= 0 or height <= 0:
            raise ImageCatalogUnreadableException(f"Image file has invalid dimensions: '{path}'.")
        return width, height

    def _image_index(self) -> dict[str, Path]:
        if self._index is not None:
            return self._index

        base = self.image_library_dir.resolve()
        index: dict[str, Path] = {}
        duplicate_names: dict[str, list[Path]] = {}

        if base.exists():
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if self._normalise_extension(path.suffix) not in self.supported_extensions:
                    continue
                relative = path.relative_to(base)
                index[str(relative).replace("\\", "/").lower()] = path
                duplicate_names.setdefault(path.name.lower(), []).append(path)

        ambiguous = {name: paths for name, paths in duplicate_names.items() if len(paths) > 1}
        if ambiguous:
            details = "; ".join(f"{name}: {[str(path) for path in paths]}" for name, paths in ambiguous.items())
            raise ImageCatalogDuplicateFilenameException(f"Duplicate image filenames detected: {details}")

        for name, paths in duplicate_names.items():
            index[name] = paths[0]

        self._index = index
        return index

    def _ensure_inside_library(self, base: Path, candidate: Path, reference: str) -> None:
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise ImageCatalogNotFoundException(f"Image reference escapes image library: '{reference}'.") from exc

    def _normalise_extension(self, extension: str) -> str:
        value = str(extension).strip().lower()
        return value if value.startswith(".") else f".{value}"

    def _format_from_extension(self, extension: str) -> str:
        normalised = self._normalise_extension(extension)
        return "jpeg" if normalised in {".jpg", ".jpeg"} else normalised.lstrip(".")

    def _safe_positive_int(self, value: Any, field_name: str, path: Path) -> int:
        try:
            integer = int(value)
        except (TypeError, ValueError) as exc:
            raise ImageCatalogMetadataException(f"Metadata field '{field_name}' for '{path.name}' must be an integer.") from exc
        if integer <= 0:
            raise ImageCatalogMetadataException(f"Metadata field '{field_name}' for '{path.name}' must be positive.")
        return integer

    def _optional_string(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _orientation_from_dimensions(self, width: int, height: int) -> str:
        if width == height:
            return "square"
        return "landscape" if width > height else "portrait"
