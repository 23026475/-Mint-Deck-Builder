"""
Archetype mapper for the Python Presentation Engine.

Responsibility:
- Load archetype definitions from config/archetype-baseline.json.
- Resolve JSON contract archetype names to PowerPoint layout objects.
- Validate configured layout names against LayoutMapper.

Important:
- This module does not hardcode archetype-to-layout mappings.
- This module does not search for similar layouts.
- This module does not fall back to alternative layouts.
- This module does not use slide layout indexes.
- This module does not generate slides or fill placeholders.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol

from presentation_engine.config import EngineConfig, config


logger = logging.getLogger(__name__)


class ArchetypeMappingException(Exception):
    """Raised when archetype mapping configuration cannot be loaded or resolved."""


class LayoutResolver(Protocol):
    """Interface for resolving PowerPoint layouts by exact layout name."""

    def get_layout(self, name: str) -> Any:
        """Return the PowerPoint layout object for an exact layout name."""


class ArchetypeDefinitionLoader(Protocol):
    """Interface for loading archetype mapping definitions."""

    def load(self, path: Path) -> list[Mapping[str, Any]]:
        """Load normalized archetype definitions from a configuration file."""


@dataclass(frozen=True)
class ArchetypeDefinition:
    """Represents one archetype-to-layout rule loaded from configuration."""

    archetype: str
    layout_name: str
    raw_definition: Mapping[str, Any] = field(repr=False)


@dataclass(frozen=True)
class JsonArchetypeDefinitionLoader:
    """
    Loads archetype definitions from archetype-baseline.json.

    The loader accepts common JSON shapes while keeping the configuration file as
    the only source of truth:
    - A list of archetype definition objects.
    - A root object with an "archetypes" list.
    - A root object with an "archetypes" object keyed by archetype name.

    Each definition must contain an archetype identifier and a layout name. The
    loader does not invent or infer missing values.
    """

    archetypes_key: str = "archetypes"

    def load(self, path: Path) -> list[Mapping[str, Any]]:
        """
        Load normalized archetype definitions from JSON.

        Args:
            path: Path to config/archetype-baseline.json.

        Returns:
            A list of archetype definition mappings.

        Raises:
            ArchetypeMappingException: If the file is missing, invalid, or does
                not contain archetype definitions in a supported shape.
        """

        if not path.exists():
            raise ArchetypeMappingException(f"Archetype baseline file was not found: {path}")

        if not path.is_file():
            raise ArchetypeMappingException(f"Archetype baseline path is not a file: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf8"))
        except json.JSONDecodeError as exc:
            raise ArchetypeMappingException(f"Invalid JSON in archetype baseline file: {path}") from exc
        except Exception as exc:
            raise ArchetypeMappingException(f"Failed to read archetype baseline file: {path}") from exc

        return self._normalize(data)

    def _normalize(self, data: Any) -> list[Mapping[str, Any]]:
        if isinstance(data, list):
            return self._ensure_mapping_list(data)

        if isinstance(data, dict):
            if self.archetypes_key not in data:
                raise ArchetypeMappingException(
                    "archetype-baseline.json must contain an 'archetypes' collection."
                )

            archetypes = data[self.archetypes_key]

            if isinstance(archetypes, list):
                return self._ensure_mapping_list(archetypes)

            if isinstance(archetypes, dict):
                normalized: list[Mapping[str, Any]] = []
                for archetype_name, definition in archetypes.items():
                    if not isinstance(definition, dict):
                        raise ArchetypeMappingException(
                            f"Definition for archetype '{archetype_name}' must be an object."
                        )
                    merged = {"archetype": archetype_name, **definition}
                    normalized.append(merged)
                return normalized

        raise ArchetypeMappingException(
            "Unsupported archetype-baseline.json shape. Expected a list, an object with "
            "an 'archetypes' list, or an object with an 'archetypes' mapping."
        )

    def _ensure_mapping_list(self, values: list[Any]) -> list[Mapping[str, Any]]:
        definitions: list[Mapping[str, Any]] = []
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                raise ArchetypeMappingException(
                    f"Archetype definition at index {index} must be an object."
                )
            definitions.append(value)
        return definitions


@dataclass
class ArchetypeMapper:
    """
    Resolves JSON contract archetypes into validated PowerPoint layout objects.

    This service has a single responsibility: read configured archetype mappings
    and return layouts through LayoutMapper. It remains independent of slide
    generation, placeholder population, and any python-pptx slide operations.

    Args:
        layout_mapper: Resolver that knows the loaded PowerPoint template and can
            return layouts by exact name.
        engine_config: Project configuration containing the base directory.
        definition_loader: Loader for archetype-baseline.json.
        baseline_path: Optional explicit path to archetype-baseline.json.
        require_unique_layout_mappings: When True, more than one archetype cannot
            point to the same layout name.
        log: Logger used for diagnostics.
    """

    layout_mapper: LayoutResolver
    engine_config: EngineConfig = field(default_factory=lambda: config)
    definition_loader: ArchetypeDefinitionLoader = field(default_factory=JsonArchetypeDefinitionLoader)
    baseline_path: Optional[Path] = None
    require_unique_layout_mappings: bool = False
    log: logging.Logger = field(default_factory=lambda: logger)

    _definitions_by_archetype: dict[str, ArchetypeDefinition] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Load and validate mapping configuration immediately."""

        path = self._resolve_baseline_path()
        self.log.info("Loading archetype baseline from: %s", path)

        raw_definitions = self.definition_loader.load(path)
        definitions = self._parse_definitions(raw_definitions)
        self._validate_duplicate_archetypes(definitions)
        self._validate_duplicate_layout_mappings(definitions)
        self._validate_layouts_exist(definitions)

        self._definitions_by_archetype = {
            definition.archetype: definition for definition in definitions
        }

        self.log.info("Loaded %s archetype mappings.", len(self._definitions_by_archetype))

    def get_layout_for_archetype(self, archetype: str) -> Any:
        """
        Return the PowerPoint layout object configured for an archetype.

        Args:
            archetype: Archetype name from the Mint Deck Builder JSON contract.

        Returns:
            The matching PowerPoint layout object returned by LayoutMapper.

        Raises:
            ArchetypeMappingException: If the archetype is unknown or the
                configured layout cannot be resolved.
        """

        if archetype not in self._definitions_by_archetype:
            available = sorted(self._definitions_by_archetype.keys())
            raise ArchetypeMappingException(
                f"Unknown archetype '{archetype}'. Available archetypes: {available}"
            )

        definition = self._definitions_by_archetype[archetype]

        try:
            return self.layout_mapper.get_layout(definition.layout_name)
        except Exception as exc:
            raise ArchetypeMappingException(
                f"Layout '{definition.layout_name}' configured for archetype "
                f"'{archetype}' could not be found in the loaded template."
            ) from exc

    def get_layout_name_for_archetype(self, archetype: str) -> str:
        """
        Return the configured layout name for an archetype without returning the layout object.

        This is useful for diagnostics and tests. It does not perform any fallback
        or similarity matching.
        """

        if archetype not in self._definitions_by_archetype:
            available = sorted(self._definitions_by_archetype.keys())
            raise ArchetypeMappingException(
                f"Unknown archetype '{archetype}'. Available archetypes: {available}"
            )

        return self._definitions_by_archetype[archetype].layout_name

    def available_archetypes(self) -> tuple[str, ...]:
        """Return all configured archetype names sorted alphabetically."""

        return tuple(sorted(self._definitions_by_archetype.keys()))

    def _resolve_baseline_path(self) -> Path:
        if self.baseline_path:
            return self.baseline_path.expanduser().resolve()
        return (self.engine_config.base_dir / "config" / "archetype-baseline.json").resolve()

    def _parse_definitions(self, raw_definitions: list[Mapping[str, Any]]) -> list[ArchetypeDefinition]:
        definitions: list[ArchetypeDefinition] = []

        for index, raw_definition in enumerate(raw_definitions):
            archetype = self._read_required_string(
                raw_definition,
                keys=("archetype", "name", "id"),
                item_description=f"archetype definition at index {index}",
            )
            layout_name = self._read_required_string(
                raw_definition,
                keys=("layout", "layout_name", "layoutName", "powerpoint_layout", "powerPointLayout"),
                item_description=f"archetype '{archetype}'",
            )

            definitions.append(
                ArchetypeDefinition(
                    archetype=archetype,
                    layout_name=layout_name,
                    raw_definition=raw_definition,
                )
            )

        return definitions

    def _read_required_string(
        self,
        definition: Mapping[str, Any],
        keys: tuple[str, ...],
        item_description: str,
    ) -> str:
        for key in keys:
            value = definition.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        raise ArchetypeMappingException(
            f"Missing required string field in {item_description}. Expected one of: {list(keys)}"
        )

    def _validate_duplicate_archetypes(self, definitions: list[ArchetypeDefinition]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()

        for definition in definitions:
            if definition.archetype in seen:
                duplicates.add(definition.archetype)
            seen.add(definition.archetype)

        if duplicates:
            raise ArchetypeMappingException(
                f"Duplicate archetype definitions detected: {sorted(duplicates)}"
            )

    def _validate_duplicate_layout_mappings(self, definitions: list[ArchetypeDefinition]) -> None:
        if not self.require_unique_layout_mappings:
            return

        seen: dict[str, str] = {}
        duplicates: dict[str, list[str]] = {}

        for definition in definitions:
            if definition.layout_name in seen:
                duplicates.setdefault(definition.layout_name, [seen[definition.layout_name]]).append(
                    definition.archetype
                )
            else:
                seen[definition.layout_name] = definition.archetype

        if duplicates:
            duplicate_summary = {
                layout_name: sorted(archetypes)
                for layout_name, archetypes in duplicates.items()
            }
            raise ArchetypeMappingException(
                f"Duplicate layout mappings detected where uniqueness is required: {duplicate_summary}"
            )

    def _validate_layouts_exist(self, definitions: list[ArchetypeDefinition]) -> None:
        for definition in definitions:
            try:
                self.layout_mapper.get_layout(definition.layout_name)
            except Exception as exc:
                raise ArchetypeMappingException(
                    f"Configured layout '{definition.layout_name}' for archetype "
                    f"'{definition.archetype}' could not be found in the loaded template."
                ) from exc
