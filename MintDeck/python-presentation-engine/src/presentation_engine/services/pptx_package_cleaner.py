"""
PPTX package cleaner for the Python Presentation Engine.

Responsibility:
- Rebuild a PPTX/Office OpenXML ZIP package without duplicate part names.
- Never write in append mode.
- Always create a fresh archive and replace the destination safely.

This is used to prevent PowerPoint repair prompts caused by duplicate ZIP entries.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path


class PptxPackageCleanerException(Exception):
    """Raised when a PPTX package cannot be normalized."""


def find_duplicate_zip_entries(package_path: str | Path) -> dict[str, int]:
    """
    Return duplicate ZIP entries from a PPTX/POTX package.

    Args:
        package_path: Path to a PPTX/POTX file.

    Returns:
        Dictionary of duplicate entry names and their counts.
    """

    path = Path(package_path)

    if not path.exists():
        raise PptxPackageCleanerException(f"Package file was not found: {path}")

    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()

    counts = Counter(names)
    return {name: count for name, count in counts.items() if count > 1}


def remove_duplicate_zip_entries(
    source_path: str | Path,
    destination_path: str | Path | None = None,
) -> Path:
    """
    Rebuild a PPTX/POTX archive without duplicate ZIP entries.

    If duplicate entries exist, the last occurrence is kept. The output is always
    written to a fresh temporary archive and then moved into place.

    Args:
        source_path: Source PPTX/POTX path.
        destination_path: Destination path. If omitted, source_path is replaced.

    Returns:
        Path to the cleaned package.
    """

    source = Path(source_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve() if destination_path else source

    if not source.exists():
        raise PptxPackageCleanerException(f"Source package was not found: {source}")

    if not source.is_file():
        raise PptxPackageCleanerException(f"Source package path is not a file: {source}")

    with zipfile.ZipFile(source, "r") as input_archive:
        infos = input_archive.infolist()

        latest_by_name: dict[str, zipfile.ZipInfo] = {}
        latest_content_by_name: dict[str, bytes] = {}

        for info in infos:
            latest_by_name[info.filename] = info
            latest_content_by_name[info.filename] = input_archive.read(info.filename)

    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pptx_package_cleaner_") as temp_dir:
        temp_output = Path(temp_dir) / destination.name

        with zipfile.ZipFile(temp_output, "w", compression=zipfile.ZIP_DEFLATED) as output_archive:
            for filename, info in latest_by_name.items():
                clean_info = zipfile.ZipInfo(filename=filename, date_time=info.date_time)
                clean_info.compress_type = zipfile.ZIP_DEFLATED
                clean_info.external_attr = info.external_attr
                output_archive.writestr(clean_info, latest_content_by_name[filename])

        if destination.exists():
            destination.unlink()

        shutil.move(str(temp_output), str(destination))

    return destination
