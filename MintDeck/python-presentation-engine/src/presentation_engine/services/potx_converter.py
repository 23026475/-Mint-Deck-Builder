"""
POTX to PPTX converter for the Python Presentation Engine.

Responsibility:
- Convert a .potx PowerPoint template package into a .pptx package.
- Change only the OpenXML presentation content type required for python-pptx compatibility.

Important:
- This module does not download templates.
- This module does not use python-pptx.
- This module does not build or modify slides.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


TEMPLATE_CONTENT_TYPE = "presentationml.template.main+xml"
PRESENTATION_CONTENT_TYPE = "presentationml.presentation.main+xml"
CONTENT_TYPES_FILE_NAME = "[Content_Types].xml"


class PotxConversionError(Exception):
    """Raised when a POTX file cannot be converted into a PPTX file."""


@dataclass(frozen=True)
class PotxConverter:
    """
    Converts a POTX file into a PPTX file by updating the OpenXML content type.

    This keeps the conversion step isolated so template loading and PowerPoint
    generation can remain separate responsibilities.
    """

    def convert(self, potx_path: str | Path, pptx_path: str | Path, overwrite: bool = True) -> Path:
        """
        Convert a .potx file to a .pptx file.

        Args:
            potx_path: Source .potx template path.
            pptx_path: Destination .pptx presentation path.
            overwrite: Whether to replace an existing destination file.

        Returns:
            The destination .pptx path.

        Raises:
            PotxConversionError: If conversion cannot be completed.
        """

        source_path = Path(potx_path).expanduser().resolve()
        destination_path = Path(pptx_path).expanduser().resolve()

        self._validate_source(source_path)
        self._validate_destination(source_path, destination_path, overwrite)

        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="potx_converter_") as temp_dir:
            extraction_dir = Path(temp_dir) / "extracted"
            extraction_dir.mkdir(parents=True, exist_ok=True)

            self._extract_package(source_path, extraction_dir)
            self._flip_content_type(extraction_dir)
            self._create_pptx_package(extraction_dir, destination_path, overwrite)

        return destination_path

    def _validate_source(self, source_path: Path) -> None:
        if not source_path.exists():
            raise PotxConversionError(f"POTX source file does not exist: {source_path}")

        if not source_path.is_file():
            raise PotxConversionError(f"POTX source path is not a file: {source_path}")

        if source_path.suffix.lower() != ".potx":
            raise PotxConversionError(f"Expected a .potx file, received: {source_path.name}")

        if not zipfile.is_zipfile(source_path):
            raise PotxConversionError(f"POTX source is not a valid OpenXML zip package: {source_path}")

    def _validate_destination(self, source_path: Path, destination_path: Path, overwrite: bool) -> None:
        if destination_path.suffix.lower() != ".pptx":
            raise PotxConversionError(f"Destination must be a .pptx file: {destination_path.name}")

        if source_path == destination_path:
            raise PotxConversionError("Source POTX path and destination PPTX path cannot be the same.")

        if destination_path.exists() and not overwrite:
            raise PotxConversionError(f"Destination already exists and overwrite is disabled: {destination_path}")

    def _extract_package(self, source_path: Path, extraction_dir: Path) -> None:
        try:
            with zipfile.ZipFile(source_path) as archive:
                archive.extractall(extraction_dir)
        except Exception as exc:
            raise PotxConversionError(f"Failed to extract POTX package: {source_path}") from exc

    def _flip_content_type(self, extraction_dir: Path) -> None:
        content_types_path = extraction_dir / CONTENT_TYPES_FILE_NAME

        if not content_types_path.exists():
            raise PotxConversionError(f"Missing OpenXML content types file: {content_types_path}")

        try:
            content_types = content_types_path.read_text(encoding="utf8")
        except Exception as exc:
            raise PotxConversionError(f"Failed to read OpenXML content types file: {content_types_path}") from exc

        if TEMPLATE_CONTENT_TYPE not in content_types:
            raise PotxConversionError(
                "Template content type was not found. Expected to replace "
                f"'{TEMPLATE_CONTENT_TYPE}' with '{PRESENTATION_CONTENT_TYPE}'."
            )

        content_types = content_types.replace(TEMPLATE_CONTENT_TYPE, PRESENTATION_CONTENT_TYPE)

        try:
            content_types_path.write_text(content_types, encoding="utf8")
        except Exception as exc:
            raise PotxConversionError(f"Failed to update OpenXML content types file: {content_types_path}") from exc

    def _create_pptx_package(self, extraction_dir: Path, destination_path: Path, overwrite: bool) -> None:
        archive_base_path = destination_path.with_suffix("")
        temporary_zip_path = archive_base_path.with_suffix(".zip")

        if destination_path.exists() and overwrite:
            destination_path.unlink()

        if temporary_zip_path.exists():
            temporary_zip_path.unlink()

        try:
            created_archive_path = shutil.make_archive(str(archive_base_path), "zip", extraction_dir)
            Path(created_archive_path).rename(destination_path)
        except Exception as exc:
            raise PotxConversionError(f"Failed to create PPTX package: {destination_path}") from exc
