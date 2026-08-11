"""
Media handler orchestration layer for the Python Presentation Engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from presentation_engine.handlers.image_handler import ImageHandler

logger = logging.getLogger(__name__)


class MediaHandlerException(Exception):
    """Raised when media processing fails."""


class MediaProcessor(Protocol):
    def process(self, slide: Any, slide_definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Process media for the supplied slide."""


@dataclass
class ImageMediaProcessor:
    image_handler: ImageHandler = field(default_factory=ImageHandler)

    def process(self, slide: Any, slide_definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        return self.image_handler.insert_images(slide, slide_definition)


@dataclass
class MediaHandler:
    processors: Sequence[MediaProcessor] = field(default_factory=lambda: (ImageMediaProcessor(),))
    log: logging.Logger = field(default_factory=lambda: logger)

    def process(self, slide: Any, slide_definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        archetype = slide_definition.get("archetype", "unknown")
        for processor in self.processors:
            try:
                reports.extend(processor.process(slide, slide_definition) or [])
            except Exception as exc:
                self.log.exception("media processing failed", extra={"archetype": archetype, "processor": processor.__class__.__name__})
                raise MediaHandlerException(f"Media processing failed for archetype '{archetype}': {exc}") from exc
        return reports
