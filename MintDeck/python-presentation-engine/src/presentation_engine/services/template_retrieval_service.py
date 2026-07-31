"""
Template retrieval service for the Python Presentation Engine.

Temporary development mode:
- Prefer an already downloaded local FY27 AI-Ready .potx template.
- Do not perform SharePoint authentication.
- Do not perform HTTP/network retrieval.

Future compatibility:
- The DownloadClient interface is intentionally preserved so a future
  authenticated Microsoft Graph retrieval client can be re-enabled with minimal
  changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Protocol

from presentation_engine.config import EngineConfig, config


logger = logging.getLogger(__name__)


class TemplateRetrievalError(Exception):
    """Raised when the FY27 AI-Ready template cannot be found or validated."""


class DownloadClient(Protocol):
    """Interface reserved for future authenticated remote template retrieval."""

    def download(self, source_url: str, destination_path: Path) -> Path:
        """Download source_url to destination_path and return destination_path."""


@dataclass(frozen=True)
class DisabledNetworkDownloadClient:
    """
    Development-mode download client.

    This intentionally performs no network activity. It preserves the existing
    service interface while SharePoint/Graph authentication is being finalized.
    """

    def download(self, source_url: str, destination_path: Path) -> Path:
        raise TemplateRetrievalError(
            "Network template retrieval is disabled in temporary local development mode. "
            "Place the approved FY27 AI-Ready .potx file under the project root, "
            "preferably data/work/template/."
        )


@dataclass
class TemplateRetrievalService:
    """
    Retrieves the approved FY27 AI-Ready POTX template for the engine.

    In temporary local development mode, the service first searches the project
    for an already downloaded template. If found, it returns the local path
    immediately. It does not authenticate to SharePoint and does not make HTTP
    requests.

    The constructor still accepts a DownloadClient so that a future authenticated
    Graph retrieval client can be plugged in without changing callers.
    """

    engine_config: EngineConfig = field(default_factory=lambda: config)
    download_client: DownloadClient = field(default_factory=DisabledNetworkDownloadClient)
    log: logging.Logger = field(default_factory=lambda: logger)

    def retrieve_latest_template(self) -> Path:
        """
        Return the local FY27 AI-Ready .potx template path.

        Returns:
            Local path of the discovered .potx template.

        Raises:
            TemplateRetrievalError: If no valid local .potx template is found.
        """

        self.log.info("Starting FY27 AI-Ready template retrieval in local development mode.")

        local_template_path = self._find_local_template()
        if local_template_path:
            self._validate_local_template(local_template_path)
            self.log.info("Using local FY27 AI-Ready template: %s", local_template_path)
            return local_template_path

        raise TemplateRetrievalError(
            "FY27 AI-Ready .potx template was not found locally. "
            "Place it under data/work/template/ or another folder under the project root. "
            "Network retrieval is disabled for temporary local development mode."
        )

    def _find_local_template(self) -> Optional[Path]:
        """
        Search for the approved template under the project root.

        Search priority:
        1. Configured downloaded POTX path.
        2. data/work/template.
        3. data/work.
        4. Recursive project-root search.

        Returns:
            The newest matching local path, or None when not found.
        """

        template_file_name = self.engine_config.sharepoint.template_file_name
        project_root = self.engine_config.base_dir

        direct_candidate = self.engine_config.template.downloaded_potx_path
        if self._is_valid_candidate(direct_candidate, template_file_name):
            return direct_candidate

        search_roots = [
            self.engine_config.template.download_dir,
            self.engine_config.work_dir,
            project_root,
        ]

        candidates: list[Path] = []
        for search_root in search_roots:
            candidates.extend(self._find_candidates(search_root, template_file_name))

        unique_candidates = {candidate.resolve() for candidate in candidates}
        if not unique_candidates:
            return None

        return max(unique_candidates, key=lambda path: path.stat().st_mtime)

    def _find_candidates(self, search_root: Path, template_file_name: str) -> list[Path]:
        """Return matching template candidates from a search root."""

        if not search_root.exists():
            self.log.debug("Skipping missing template search root: %s", search_root)
            return []

        if search_root.is_file():
            return [search_root] if self._is_valid_candidate(search_root, template_file_name) else []

        exact_matches = list(search_root.rglob(template_file_name))
        prefix_matches = list(search_root.rglob("FY27 AI-Ready*.potx"))

        return [
            candidate
            for candidate in self._dedupe_paths([*exact_matches, *prefix_matches])
            if self._is_valid_candidate(candidate, template_file_name)
        ]

    def _is_valid_candidate(self, candidate: Path, template_file_name: str) -> bool:
        """Check whether a candidate looks like the local approved POTX template."""

        return (
            candidate.exists()
            and candidate.is_file()
            and candidate.suffix.lower() == ".potx"
            and candidate.name.startswith("FY27 AI-Ready")
            and (candidate.name == template_file_name or candidate.name.startswith("FY27 AI-Ready"))
        )

    def _validate_local_template(self, template_path: Path) -> None:
        """
        Validate the local template without opening or modifying it.

        Args:
            template_path: Local path to validate.

        Raises:
            TemplateRetrievalError: If the file is missing, empty, or not .potx.
        """

        if not template_path.exists():
            raise TemplateRetrievalError(f"Local template does not exist: {template_path}")

        if not template_path.is_file():
            raise TemplateRetrievalError(f"Local template path is not a file: {template_path}")

        if template_path.suffix.lower() != ".potx":
            raise TemplateRetrievalError(f"Local template must have a .potx extension: {template_path}")

        if template_path.stat().st_size <= 0:
            raise TemplateRetrievalError(f"Local template is empty: {template_path}")

    def _dedupe_paths(self, paths: Iterable[Path]) -> list[Path]:
        """Return paths without duplicates while preserving order."""

        seen: set[Path] = set()
        unique_paths: list[Path] = []
        for path in paths:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_paths.append(path)
        return unique_paths
