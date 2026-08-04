
"""
Layout mapper for the Python Presentation Engine.

Responsibility:
- Load a converted PowerPoint template at runtime using python-pptx.
- Enumerate all available slide layouts.
- Resolve layouts by layout name only.

Important:
- This module never resolves layouts by index.
- This module does not hardcode placeholder mappings.
- This module does not build slides or modify the presentation.
- This module is prepared for later archetype-to-layout resolution from archetype-baseline.json.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Protocol

from pptx import Presentation
from pptx.presentation import Presentation as PresentationObject
from pptx.slide import SlideLayout

from presentation_engine.config import EngineConfig, config


logger = logging.getLogger(__name__)


class LayoutMapperError(Exception):
    """Base exception for layout mapper failures."""


class LayoutNotFoundError(LayoutMapperError):
    """Raised when a requested slide layout name does not exist in the template."""

    def __init__(self, layout_name: str, available_layouts: Iterable[str]) -> None:
        available = sorted(available_layouts)
        message = (
            f"Slide layout was not found by name: '{layout_name}'. "
            f"Available layouts: {available}"
        )
        super().__init__(message)
        self.layout_name = layout_name
        self.available_layouts = available


class TemplateLoadError(LayoutMapperError):
    """Raised when the PowerPoint template cannot be loaded."""


class PresentationLoader(Protocol):
    """Interface for loading a PowerPoint presentation template."""

    def load(self, template_path: Path) -> PresentationObject:
        """Load and return a python-pptx Presentation object."""


@dataclass(frozen=True)
class PythonPptxPresentationLoader:
    """
    Default presentation loader backed by python-pptx.

    This adapter exists so LayoutMapper depends on an abstraction instead of
    directly depending on the python-pptx constructor. Tests can inject a fake
    loader without opening real PowerPoint files.
    """

    def load(self, template_path: Path) -> PresentationObject:
        """
        Load a PowerPoint file from disk.

        Args:
            template_path: Path to the converted .pptx template.

        Returns:
            A python-pptx Presentation object.

        Raises:
            TemplateLoadError: If the file cannot be loaded.
        """

        try:
            return Presentation(str(template_path))
        except Exception as exc:
            raise TemplateLoadError(f"Failed to load PowerPoint template: {template_path}") from exc


@dataclass
class LayoutMapper:
    """
    Maps PowerPoint slide layout names to python-pptx SlideLayout objects.

    The mapper loads the PowerPoint template at runtime and indexes layouts by
    their actual names. It intentionally avoids index-based access because slide
    layout positions can change when the template is edited or re-saved.

    This service is designed for dependency injection:
    - Inject EngineConfig to control configured paths.
    - Inject PresentationLoader to control how presentations are loaded.
    - Inject a logger for testability and consistent diagnostics.

    Later, archetype-baseline.json can resolve an archetype such as "cards3"
    into a layout name such as "Content - Cards 3". This mapper should then
    receive only the resolved layout name through get_layout(name).
    """

    engine_config: EngineConfig = config
    presentation_loader: PresentationLoader = field(default_factory=PythonPptxPresentationLoader)
    log: logging.Logger = logger
    template_path: Optional[Path] = None

    _presentation: Optional[PresentationObject] = field(default=None, init=False, repr=False)
    _layouts_by_name: Dict[str, SlideLayout] = field(default_factory=dict, init=False, repr=False)

    def load(self, template_path: Optional[str | Path] = None) -> None:
        """
        Load the template and enumerate available slide layouts.

        Args:
            template_path: Optional explicit path to a converted .pptx template.
                When omitted, the path is read from EngineConfig.template.converted_pptx_path.

        Raises:
            TemplateLoadError: If the template path is invalid or cannot be opened.
        """

        resolved_template_path = self._resolve_template_path(template_path)
        self.log.info("Loading PowerPoint template for layout mapping: %s", resolved_template_path)

        presentation = self.presentation_loader.load(resolved_template_path)
        layouts_by_name = self._enumerate_layouts(presentation)

        self._presentation = presentation
        self._layouts_by_name = layouts_by_name
        self.template_path = resolved_template_path

        self.log.info("Loaded %s slide layouts from template.", len(layouts_by_name))
        self.log.debug("Available slide layouts: %s", sorted(layouts_by_name.keys()))

    def load_from_presentation(
        self,
        presentation: PresentationObject,
        template_path: Optional[str | Path] = None,
    ) -> None:
        """
        Load layout mappings from an already-open python-pptx Presentation object.

        This is required when another builder is going to add slides to that same
        Presentation instance. SlideLayout objects must come from the same
        Presentation object that receives the new slides, otherwise PowerPoint
        can repair or remove content when opening the generated file.

        Args:
            presentation: Already-loaded python-pptx Presentation object.
            template_path: Optional path used only for diagnostics/logging.
        """

        self.log.info("Loading slide layouts from existing presentation instance.")

        layouts_by_name = self._enumerate_layouts(presentation)

        self._presentation = presentation
        self._layouts_by_name = layouts_by_name

        if template_path is not None:
            self.template_path = Path(template_path).expanduser().resolve()

        self.log.info(
            "Loaded %s slide layouts from existing presentation.",
            len(layouts_by_name),
        )
        self.log.debug(
            "Available slide layouts: %s",
            sorted(layouts_by_name.keys()),
        )

    def get_layout(self, name: str) -> SlideLayout:
        """
        Return a slide layout by exact layout name.

        Args:
            name: Exact PowerPoint slide layout name.

        Returns:
            The matching python-pptx SlideLayout object.

        Raises:
            LayoutNotFoundError: If the layout name does not exist.
            TemplateLoadError: If layouts have not been loaded yet.
        """

        self._ensure_loaded()

        if name not in self._layouts_by_name:
            self.log.error("Requested layout does not exist: %s", name)
            raise LayoutNotFoundError(name, self._layouts_by_name.keys())

        self.log.debug("Resolved slide layout by name: %s", name)
        return self._layouts_by_name[name]

    def get_layout_for_archetype(self, archetype: str, archetype_layout_map: Mapping[str, str]) -> SlideLayout:
        """
        Resolve an archetype to a layout name, then return the matching layout.

        This method prepares the mapper for archetype-baseline.json without
        making this class responsible for reading or validating that file.
        The caller should load archetype-baseline.json and pass a simple mapping
        of archetype name to layout name.

        Args:
            archetype: Slide archetype from the JSON contract.
            archetype_layout_map: Mapping of archetype names to layout names.

        Returns:
            The matching python-pptx SlideLayout object.

        Raises:
            LayoutNotFoundError: If the archetype has no mapped layout name or
                if the mapped layout name does not exist in the template.
        """

        layout_name = archetype_layout_map.get(archetype)

        if not layout_name:
            self.log.error("No layout mapping found for archetype: %s", archetype)
            raise LayoutNotFoundError(
                layout_name=f"<unmapped archetype: {archetype}>",
                available_layouts=self._layouts_by_name.keys(),
            )

        return self.get_layout(layout_name)

    def available_layout_names(self) -> tuple[str, ...]:
        """
        Return all available layout names discovered in the loaded template.

        Returns:
            A sorted tuple of layout names.

        Raises:
            TemplateLoadError: If layouts have not been loaded yet.
        """

        self._ensure_loaded()
        return tuple(sorted(self._layouts_by_name.keys()))

    def _resolve_template_path(self, template_path: Optional[str | Path]) -> Path:
        resolved_path = Path(template_path).expanduser().resolve() if template_path else self.engine_config.template.converted_pptx_path

        if not resolved_path.exists():
            raise TemplateLoadError(f"Converted PowerPoint template was not found: {resolved_path}")

        if not resolved_path.is_file():
            raise TemplateLoadError(f"Configured PowerPoint template path is not a file: {resolved_path}")

        if resolved_path.suffix.lower() != ".pptx":
            raise TemplateLoadError(f"LayoutMapper expects a converted .pptx template: {resolved_path}")

        return resolved_path

    def _enumerate_layouts(self, presentation: PresentationObject) -> Dict[str, SlideLayout]:
        layouts: Dict[str, SlideLayout] = {}

        for slide_master in presentation.slide_masters:
            for layout in slide_master.slide_layouts:
                layout_name = layout.name

                if not layout_name:
                    self.log.warning("Skipping unnamed slide layout.")
                    continue

                if layout_name in layouts:
                    self.log.warning("Duplicate slide layout name found. Keeping first occurrence: %s", layout_name)
                    continue

                layouts[layout_name] = layout
                self.log.debug("Discovered slide layout: %s", layout_name)

        if not layouts:
            raise TemplateLoadError("No slide layouts were found in the PowerPoint template.")

        return layouts

    def _ensure_loaded(self) -> None:
        if self._presentation is None or not self._layouts_by_name:
            raise TemplateLoadError("LayoutMapper has not loaded a template yet. Call load() first.")
