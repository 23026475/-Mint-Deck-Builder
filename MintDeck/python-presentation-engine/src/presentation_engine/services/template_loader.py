"""
Template loader for the Python Presentation Engine.

Responsibility:
- Obtain the latest FY27 AI-Ready PowerPoint template from the configured source.
- Store the downloaded/copied template in the configured local working location.

Important:
- This module does not convert .potx to .pptx.
- This module does not use python-pptx.
- This module does not perform PowerPoint slide operations.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from presentation_engine.config import EngineConfig, config


class TemplateLoaderError(Exception):
    """Raised when the template cannot be obtained from the configured source."""


class TemplateSource(Protocol):
    """Interface for any source that can provide a template file."""

    def fetch(self, destination_path: Path) -> Path:
        """Fetch the template and return the local destination path."""


@dataclass(frozen=True)
class UrlTemplateSource:
    """Downloads a template from a configured HTTP or HTTPS URL."""

    template_url: str

    def fetch(self, destination_path: Path) -> Path:
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        request = Request(self.template_url, headers={"User-Agent": "presentation-engine"})

        try:
            with urlopen(request) as response, destination_path.open("wb") as output_file:
                shutil.copyfileobj(response, output_file)
        except Exception as exc:
            raise TemplateLoaderError(
                f"Failed to download template from configured URL: {self.template_url}"
            ) from exc

        return destination_path


@dataclass(frozen=True)
class LocalFileTemplateSource:
    """Copies a template from a configured local file path."""

    template_path: Path

    def fetch(self, destination_path: Path) -> Path:
        if not self.template_path.exists():
            raise TemplateLoaderError(f"Configured template file was not found: {self.template_path}")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.template_path, destination_path)
        return destination_path


@dataclass(frozen=True)
class LocalDirectoryTemplateSource:
    """Finds the latest FY27 AI-Ready template in a configured local folder."""

    directory_path: Path
    file_prefix: str = "FY27 AI-Ready"
    allowed_extensions: tuple[str, ...] = (".potx", ".pptx")

    def fetch(self, destination_path: Path) -> Path:
        latest_template = self._find_latest_template()

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(latest_template, destination_path)
        return destination_path

    def _find_latest_template(self) -> Path:
        if not self.directory_path.exists() or not self.directory_path.is_dir():
            raise TemplateLoaderError(f"Configured template folder was not found: {self.directory_path}")

        candidates = list(self._template_candidates(self.directory_path.iterdir()))

        if not candidates:
            raise TemplateLoaderError(
                f"No template starting with '{self.file_prefix}' was found in: {self.directory_path}"
            )

        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _template_candidates(self, paths: Iterable[Path]) -> Iterable[Path]:
        for path in paths:
            if not path.is_file():
                continue

            if not path.name.startswith(self.file_prefix):
                continue

            if path.suffix.lower() not in self.allowed_extensions:
                continue

            yield path


@dataclass(frozen=True)
class TemplateLoader:
    """Obtains the latest configured FY27 AI-Ready template for the engine."""

    engine_config: EngineConfig = config

    def load_latest_template(self) -> Path:
        """
        Obtain the latest template and return the local downloaded/copied path.

        The configured source may be:
        - an HTTP or HTTPS URL
        - a local template file path
        - a local folder containing FY27 AI-Ready templates
        """

        self.engine_config.ensure_runtime_directories()

        source = self._build_source()
        destination_path = self.engine_config.template.downloaded_potx_path

        return source.fetch(destination_path)

    def _build_source(self) -> TemplateSource:
        configured_location = self.engine_config.sharepoint.template_url

        if not configured_location:
            raise TemplateLoaderError(
                "No template location configured. Set PRESENTATION_ENGINE_SHAREPOINT_TEMPLATE_URL."
            )

        parsed_location = urlparse(configured_location)

        if parsed_location.scheme in {"http", "https"}:
            return UrlTemplateSource(configured_location)

        local_path = Path(configured_location).expanduser().resolve()

        if local_path.is_file():
            return LocalFileTemplateSource(local_path)

        if local_path.is_dir():
            return LocalDirectoryTemplateSource(local_path)

        raise TemplateLoaderError(
            "Configured template location is not a valid URL, file, or folder: "
            f"{configured_location}"
        )
