"""
Slide builder for the Python Presentation Engine.

Milestone scope:
- Create slides for the first supported archetypes only: cover, cards3, closing.
- Resolve layouts through ArchetypeMapper.
- Create slides with python-pptx.

Important:
- This module does not populate placeholders yet.
- This module does not implement unsupported archetypes.
- This module does not interact directly with LayoutMapper.
- This module does not hardcode layout names or use slide layout indexes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence

from presentation_engine.config import EngineConfig, config


logger = logging.getLogger(__name__)


SUPPORTED_ARCHETYPES: frozenset[str] = frozenset({"cover", "cards3", "closing"})


class SlideBuilderException(Exception):
    """Raised when slides cannot be created from the supplied contract."""


class ArchetypeLayoutResolver(Protocol):
    """Interface for resolving an archetype into a PowerPoint layout object."""

    def get_layout_for_archetype(self, archetype: str) -> Any:
        """Return the layout object configured for the supplied archetype."""


class SlideCollection(Protocol):
    """Subset of the python-pptx slides collection used by the builder."""

    def add_slide(self, slide_layout: Any) -> Any:
        """Create and return a slide using the supplied layout."""


class PresentationLike(Protocol):
    """Subset of a python-pptx Presentation used by the builder."""

    slides: SlideCollection


class PresentationFactory(Protocol):
    """Interface for creating a presentation from a template path."""

    def create_from_template(self, template_path: Path) -> PresentationLike:
        """Load and return a presentation from the converted FY27 template."""


@dataclass(frozen=True)
class PythonPptxPresentationFactory:
    """
    Default presentation factory backed by python-pptx.

    The import is intentionally local to keep unit tests lightweight and allow a
    fake factory to be injected without requiring PowerPoint files.
    """

    def create_from_template(self, template_path: Path) -> PresentationLike:
        """
        Load a converted PPTX template and return a presentation object.

        Args:
            template_path: Path to the converted FY27 .pptx template.

        Raises:
            SlideBuilderException: If the template cannot be loaded.
        """

        try:
            from pptx import Presentation

            return Presentation(str(template_path))
        except Exception as exc:
            raise SlideBuilderException(
                f"Failed to create presentation from converted template: {template_path}"
            ) from exc


@dataclass(frozen=True)
class SlideBuildResult:
    """Result returned after creating milestone slides from a JSON contract."""

    presentation: PresentationLike
    slides: tuple[Any, ...]


@dataclass
class SlideBuilder:
    """
    Creates milestone slides from a parsed Mint Deck Builder JSON contract.

    This first version supports only cover, cards3, and closing. It resolves each
    archetype through ArchetypeMapper and creates a slide with the returned
    python-pptx layout. Placeholder population is intentionally excluded from
    this milestone.
    """

    archetype_mapper: ArchetypeLayoutResolver
    engine_config: EngineConfig = field(default_factory=lambda: config)
    presentation_factory: PresentationFactory = field(default_factory=PythonPptxPresentationFactory)
    supported_archetypes: frozenset[str] = SUPPORTED_ARCHETYPES
    log: logging.Logger = field(default_factory=lambda: logger)

    def build(self, contract: Mapping[str, Any], template_path: Optional[str | Path] = None) -> SlideBuildResult:
        """
        Create milestone slides from a parsed JSON contract.

        Args:
            contract: Parsed JSON contract produced by the Mint Deck Builder agent.
            template_path: Optional explicit path to the converted FY27 PPTX template.
                When omitted, config.template.converted_pptx_path is used.

        Returns:
            SlideBuildResult containing the presentation and created slide objects.

        Raises:
            SlideBuilderException: If the contract is invalid, the template path
                is invalid, or an unsupported archetype is encountered.
        """

        resolved_template_path = self._resolve_template_path(template_path)
        slide_definitions = self._extract_slide_definitions(contract)

        self.log.info("Creating presentation from template: %s", resolved_template_path)
        presentation = self.presentation_factory.create_from_template(resolved_template_path)

        created_slides: list[Any] = []
        for slide_definition in slide_definitions:
            created_slides.append(self.build_slide(presentation, slide_definition))

        self.log.info("Created %s milestone slides.", len(created_slides))
        return SlideBuildResult(presentation=presentation, slides=tuple(created_slides))

    def build_slide(self, presentation: PresentationLike, slide_definition: Mapping[str, Any]) -> Any:
        """
        Create one supported slide and return the created slide object.

        The layout is always obtained through ArchetypeMapper. This method does
        not inspect template layouts directly and does not populate placeholders.
        """

        archetype = self._read_archetype(slide_definition)
        self._validate_supported_archetype(archetype)

        self.log.debug("Resolving layout for archetype: %s", archetype)
        layout = self.archetype_mapper.get_layout_for_archetype(archetype)

        self.log.debug("Creating slide for archetype: %s", archetype)
        return presentation.slides.add_slide(layout)

    def _resolve_template_path(self, template_path: Optional[str | Path]) -> Path:
        resolved_path = (
            Path(template_path).expanduser().resolve()
            if template_path is not None
            else self.engine_config.template.converted_pptx_path
        )

        if not resolved_path.exists():
            raise SlideBuilderException(f"Converted FY27 template was not found: {resolved_path}")

        if not resolved_path.is_file():
            raise SlideBuilderException(f"Converted FY27 template path is not a file: {resolved_path}")

        if resolved_path.suffix.lower() != ".pptx":
            raise SlideBuilderException(f"Converted FY27 template must be a .pptx file: {resolved_path}")

        return resolved_path

    def _extract_slide_definitions(self, contract: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        slides = contract.get("slides")

        if not isinstance(slides, list):
            raise SlideBuilderException("JSON contract must contain a 'slides' list.")

        for index, slide_definition in enumerate(slides):
            if not isinstance(slide_definition, Mapping):
                raise SlideBuilderException(f"Slide definition at index {index} must be an object.")

        return slides

    def _read_archetype(self, slide_definition: Mapping[str, Any]) -> str:
        archetype = slide_definition.get("archetype")

        if not isinstance(archetype, str) or not archetype.strip():
            raise SlideBuilderException("Each slide definition must contain a non-empty 'archetype'.")

        return archetype.strip().lower()

    def _validate_supported_archetype(self, archetype: str) -> None:
        if archetype not in self.supported_archetypes:
            supported = sorted(self.supported_archetypes)
            raise SlideBuilderException(
                f"Unsupported archetype '{archetype}' for the first milestone. "
                f"Supported archetypes: {supported}"
            )
