"""
Archetype mapper for the Python Presentation Engine.

Responsibility:
- Load the approved Mint archetype baseline from config/archetype-baseline.json.
- Support both the legacy top-level "archetypes" structure and the approved
  grouped "groups" structure supplied by the project owner.
- Resolve JSON contract archetype names to PowerPoint layout objects through
  LayoutMapper.

Important:
- This module does not create slides.
- This module does not fill placeholders.
- This module does not hardcode layout names.
- This module does not use PowerPoint layout indexes.
"""

from __future__ import annotations

import json
import logging
import re
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
    aliases: tuple[str, ...] = field(default_factory=tuple)
    group_name: Optional[str] = None


@dataclass(frozen=True)
class JsonArchetypeDefinitionLoader:
    """
    Loads archetype definitions from archetype-baseline.json.

    Supported input shapes:
    1. Legacy list:
       [ {"archetype": "cards3", "layout": "Content - Cards 3"} ]

    2. Legacy object with archetypes list:
       { "archetypes": [ ... ] }

    3. Legacy object with archetypes object:
       { "archetypes": { "cards3": {"layout": "Content - Cards 3"} } }

    4. Approved grouped structure:
       {
         "version": "1.3",
         "date": "2026-07-08",
         "groups": {
           "Content": [
             {
               "id": "B05",
               "name": "Full-bleed image statement",
               "layout": "Statement - Full Bleed"
             }
           ]
         }
       }

    The grouped structure is flattened into the same normalized collection used
    by the mapper. The original item metadata is preserved and the group name is
    added as metadata under "group".
    """

    archetypes_key: str = "archetypes"
    groups_key: str = "groups"

    def load(self, path: Path) -> list[Mapping[str, Any]]:
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

        if not isinstance(data, Mapping):
            raise ArchetypeMappingException(
                "Unsupported archetype-baseline.json shape. Expected a list or object."
            )

        if self.archetypes_key in data:
            return self._normalize_legacy_archetypes(data[self.archetypes_key])

        if self.groups_key in data:
            return self._normalize_grouped_archetypes(data[self.groups_key])

        raise ArchetypeMappingException(
            "archetype-baseline.json must contain either an 'archetypes' collection "
            "or the approved 'groups' structure."
        )

    def _normalize_legacy_archetypes(self, archetypes: Any) -> list[Mapping[str, Any]]:
        if isinstance(archetypes, list):
            return self._ensure_mapping_list(archetypes)

        if isinstance(archetypes, Mapping):
            normalized: list[Mapping[str, Any]] = []
            for archetype_name, definition in archetypes.items():
                if not isinstance(definition, Mapping):
                    raise ArchetypeMappingException(
                        f"Definition for archetype '{archetype_name}' must be an object."
                    )
                normalized.append({"archetype": archetype_name, **definition})
            return normalized

        raise ArchetypeMappingException("The 'archetypes' collection must be a list or object.")

    def _normalize_grouped_archetypes(self, groups: Any) -> list[Mapping[str, Any]]:
        if groups is None:
            raise ArchetypeMappingException("The approved baseline is missing the 'groups' object.")

        if not isinstance(groups, Mapping):
            raise ArchetypeMappingException("The approved baseline 'groups' value must be an object.")

        if not groups:
            raise ArchetypeMappingException("The approved baseline 'groups' object is empty.")

        normalized: list[Mapping[str, Any]] = []
        empty_groups: list[str] = []

        for group_name, group_items in groups.items():
            if not isinstance(group_items, list):
                raise ArchetypeMappingException(
                    f"Group '{group_name}' must contain a list of archetype definitions."
                )

            if not group_items:
                empty_groups.append(str(group_name))
                continue

            for index, item in enumerate(group_items):
                if not isinstance(item, Mapping):
                    raise ArchetypeMappingException(
                        f"Archetype definition at groups.{group_name}[{index}] must be an object."
                    )
                normalized.append({"group": group_name, **item})

        if empty_groups:
            raise ArchetypeMappingException(
                f"The following archetype groups are empty: {sorted(empty_groups)}"
            )

        if not normalized:
            raise ArchetypeMappingException("No archetype definitions were found in the approved grouped baseline.")

        return normalized

    def _ensure_mapping_list(self, values: list[Any]) -> list[Mapping[str, Any]]:
        definitions: list[Mapping[str, Any]] = []
        for index, value in enumerate(values):
            if not isinstance(value, Mapping):
                raise ArchetypeMappingException(
                    f"Archetype definition at index {index} must be an object."
                )
            definitions.append(value)
        return definitions


@dataclass
class ArchetypeMapper:
    """
    Resolves JSON contract archetypes into validated PowerPoint layout objects.

    The public API is unchanged:
        mapper = ArchetypeMapper(layout_mapper)
        layout = mapper.get_layout_for_archetype("cards3")

    For approved grouped baselines, the mapper flattens all groups into one
    lookup collection and preserves group metadata on each raw definition.
    """

    layout_mapper: LayoutResolver
    engine_config: EngineConfig = field(default_factory=lambda: config)
    definition_loader: ArchetypeDefinitionLoader = field(default_factory=JsonArchetypeDefinitionLoader)
    baseline_path: Optional[Path] = None
    require_unique_layout_mappings: bool = False
    log: logging.Logger = field(default_factory=lambda: logger)

    _definitions_by_archetype: dict[str, ArchetypeDefinition] = field(default_factory=dict, init=False, repr=False)
    _definitions_by_alias: dict[str, ArchetypeDefinition] = field(default_factory=dict, init=False, repr=False)

    # Contract aliases map friendly JSON contract archetype names to approved
    # baseline IDs. This avoids hardcoding layout names while allowing the agent
    # contract to keep simple names like "statement", "cover_dark", and "logo_wall".
    # Layout names still come ONLY from config/archetype-baseline.json.
    _contract_alias_to_baseline_id: dict[str, str] = field(
        default_factory=lambda: {
            # Openers
            "cover": "A01",
            "cover_brand": "A01",
            "cover_dark": "A02",
            "cover_dark_minimal": "A02",
            "agenda": "A03",
            "agenda_contents": "A03",
            "section_divider": "A04",

            # Content
            "title_content": "B01",
            "title_bullets": "B01",
            "cards3": "B02",
            "cards4": "B02",
            "card_grid": "B02",
            "cards_with_bullets": "B03",
            "cards_with_bullet_lists": "B03",
            "image_right": "B04",
            "image_text_split": "B04",
            "statement": "B05",
            "full_bleed_statement": "B05",
            "quote": "B06",
            "testimonial": "B06",
            "comparison": "B08",
            "two_column_comparison": "B08",
            "faq": "B09",
            "qanda": "B09",
            "thesis": "B10",

            # Process and time
            "process_flow": "C01",
            "roadmap": "C02",
            "timeline": "C02",

            # Data
            "data_table": "D01",
            "table": "D01",
            "chart": "D02",
            "chart_takeaway": "D02",
            "kpi": "D03",
            "kpi_stats": "D03",
            "matrix": "D05",
            "matrix_2x2": "D05",

            # People and proof
            "team": "E01",
            "meet_the_team": "E01",
            "org_chart": "E02",
            "logo_wall": "E03",
            "case_study": "E04",

            # Commercial
            "pricing_stat": "F01",
            "pricing_options_table": "F02",
            "prerequisites_terms": "F03",

            # Closers
            "summary_cta": "G01",
            "summary": "G01",
            "closing": "G02",
            "next_steps": "G02",
            "thank_you": "G03",
            "thank_you_contact": "G03",
        },
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        path = self._resolve_baseline_path()
        self.log.info("Loading archetype baseline from: %s", path)

        raw_definitions = self.definition_loader.load(path)
        definitions = self._parse_definitions(raw_definitions)
        self._validate_duplicate_archetypes(definitions)
        self._validate_duplicate_layout_mappings(definitions)

        self._definitions_by_archetype = {definition.archetype: definition for definition in definitions}
        self._definitions_by_alias = self._build_alias_index(definitions)

        self.log.info("Loaded %s archetype mappings.", len(self._definitions_by_archetype))

    def get_layout_for_archetype(self, archetype: str) -> Any:
        definition = self._get_definition(archetype)

        try:
            return self.layout_mapper.get_layout(definition.layout_name)
        except Exception as exc:
            raise ArchetypeMappingException(
                f"Layout '{definition.layout_name}' configured for archetype "
                f"'{archetype}' could not be found in the loaded template."
            ) from exc

    def get_layout_name_for_archetype(self, archetype: str) -> str:
        return self._get_definition(archetype).layout_name

    def available_archetypes(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions_by_alias.keys()))

    def _get_definition(self, archetype: str) -> ArchetypeDefinition:
        lookup_key = self._normalize_key(archetype)

        if lookup_key not in self._definitions_by_alias:
            available = sorted(self._definitions_by_alias.keys())
            raise ArchetypeMappingException(
                f"Unknown archetype '{archetype}'. Available archetypes and aliases: {available}"
            )

        return self._definitions_by_alias[lookup_key]

    def _resolve_baseline_path(self) -> Path:
        if self.baseline_path:
            return self.baseline_path.expanduser().resolve()
        return (self.engine_config.base_dir / "config" / "archetype-baseline.json").resolve()

    def _parse_definitions(self, raw_definitions: list[Mapping[str, Any]]) -> list[ArchetypeDefinition]:
        definitions: list[ArchetypeDefinition] = []

        for index, raw_definition in enumerate(raw_definitions):
            layout_name = self._read_required_string(
                raw_definition,
                keys=("layout", "layout_name", "layoutName", "powerpoint_layout", "powerPointLayout"),
                item_description=f"archetype definition at index {index}",
            )

            archetype = self._read_archetype_identifier(raw_definition, index)
            aliases = self._build_definition_aliases(raw_definition, archetype)

            definitions.append(
                ArchetypeDefinition(
                    archetype=archetype,
                    layout_name=layout_name,
                    raw_definition=raw_definition,
                    aliases=aliases,
                    group_name=self._optional_string(raw_definition, "group"),
                )
            )

        return definitions

    def _read_archetype_identifier(self, definition: Mapping[str, Any], index: int) -> str:
        for key in ("archetype", "contract_archetype", "contractArchetype", "id", "name"):
            value = definition.get(key)
            if isinstance(value, str) and value.strip():
                return self._normalize_key(value)

        raise ArchetypeMappingException(
            f"Archetype definition at index {index} is missing archetype/id/name metadata."
        )

    def _build_definition_aliases(self, definition: Mapping[str, Any], archetype: str) -> tuple[str, ...]:
        aliases: set[str] = {archetype}

        for key in ("archetype", "contract_archetype", "contractArchetype", "id", "name"):
            value = definition.get(key)
            if isinstance(value, str) and value.strip():
                aliases.add(self._normalize_key(value))

        id_value = definition.get("id")
        if isinstance(id_value, str):
            normalized_id = self._normalize_key(id_value)
            for contract_alias, baseline_id in self._contract_alias_to_baseline_id.items():
                if self._normalize_key(baseline_id) == normalized_id:
                    aliases.add(self._normalize_key(contract_alias))

        return tuple(sorted(aliases))

    def _build_alias_index(self, definitions: list[ArchetypeDefinition]) -> dict[str, ArchetypeDefinition]:
        alias_index: dict[str, ArchetypeDefinition] = {}
        duplicate_aliases: dict[str, list[str]] = {}

        for definition in definitions:
            for alias in definition.aliases:
                existing = alias_index.get(alias)
                if existing is not None and existing.archetype != definition.archetype:
                    duplicate_aliases.setdefault(alias, [existing.archetype]).append(definition.archetype)
                    continue
                alias_index[alias] = definition

        if duplicate_aliases:
            raise ArchetypeMappingException(
                f"Duplicate archetype aliases detected: {duplicate_aliases}"
            )

        return alias_index

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

    def _optional_string(self, definition: Mapping[str, Any], key: str) -> Optional[str]:
        value = definition.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

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
                duplicates.setdefault(definition.layout_name, [seen[definition.layout_name]]).append(definition.archetype)
            else:
                seen[definition.layout_name] = definition.archetype

        if duplicates:
            duplicate_summary = {
                layout_name: sorted(archetypes) for layout_name, archetypes in duplicates.items()
            }
            raise ArchetypeMappingException(
                f"Duplicate layout mappings detected where uniqueness is required: {duplicate_summary}"
            )

    def _normalize_key(self, value: str) -> str:
        normalized = value.strip().lower()
        normalized = normalized.replace("&", "and")
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")
