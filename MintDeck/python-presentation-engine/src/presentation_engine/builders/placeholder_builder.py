
"""
Placeholder builder for the Python Presentation Engine.

Responsibility:
- Populate placeholders in an already-created slide.
- Locate placeholders by PowerPoint placeholder idx only.
- Preserve all formatting already defined by the template.
- Clean up only unresolved text prompt placeholders after population.

Important:
- This module does not create slides.
- This module does not select layouts.
- This module does not create text boxes.
- This module does not insert images, charts, tables, logos, or SmartArt yet.
- Media placeholders are preserved for future handlers.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from presentation_engine.config import EngineConfig, config


logger = logging.getLogger(__name__)


class PlaceholderBuilderException(Exception):
    """Raised when placeholder population fails."""


@dataclass(frozen=True)
class PlaceholderDefinition:
    """One placeholder population rule."""

    name: str
    idx: int
    source: str
    required: bool = True
    join_with: str = "\n"
    content_type: str = "text"

    @property
    def is_media(self) -> bool:
        return self.content_type in {"image", "picture", "logo", "chart", "table", "smartart", "media"}


DEFAULT_PROMPT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^click\s+to\s+edit(?:\s+master)?(?:\s+title\s+style|\s+text\s+styles|\s+subtitle|\s+text)?$", re.I),
    re.compile(r"^click\s+to\s+add(?:\s+title|\s+subtitle|\s+text|\s+caption|\s+picture|\s+chart|\s+table)?$", re.I),
    re.compile(r"^presentation\s+title$", re.I),
    re.compile(r"^one-line\s+subtitle\s+for\s+the\s+engagement$", re.I),
    re.compile(r"^prepared\s+for\s+client\s+name$", re.I),
    re.compile(r"^section\s+title\s+goes\s+here$", re.I),
)


EXACT_MATCH_PLACEHOLDER_MAPPINGS: dict[str, list[PlaceholderDefinition]] = {
    "cover": [
        PlaceholderDefinition("title", 0, "fields.title"),
        PlaceholderDefinition("subtitle", 2, "fields.subtitle"),
        PlaceholderDefinition("abstract", 3, "fields.abstract", required=False),
        PlaceholderDefinition("prepared_by", 4, "fields.prepared-by", required=False),
        PlaceholderDefinition("kicker", 11, "fields.kicker"),
    ],
    "cards3": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker"),
        PlaceholderDefinition("intro", 12, "fields.intro", required=False),
        PlaceholderDefinition("card1_title", 20, "fields.cards.0.title"),
        PlaceholderDefinition("card1_body", 21, "fields.cards.0.body"),
        PlaceholderDefinition("card2_title", 22, "fields.cards.1.title"),
        PlaceholderDefinition("card2_body", 23, "fields.cards.1.body"),
        PlaceholderDefinition("card3_title", 24, "fields.cards.2.title"),
        PlaceholderDefinition("card3_body", 25, "fields.cards.2.body"),
        PlaceholderDefinition("callout", 40, "fields.callout", required=False),
    ],
    "closing": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("steps", 12, "fields.steps"),
        PlaceholderDefinition("footer", 13, "fields.footer", required=False),
    ],
    "cover_dark": [
        PlaceholderDefinition("title", 0, "fields.title"),
        PlaceholderDefinition("subtitle", 2, "fields.subtitle", required=False),
        PlaceholderDefinition("abstract", 3, "fields.abstract", required=False),
        PlaceholderDefinition("footer", 4, "fields.footer", required=False),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
    ],
    "image_right": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("body", 12, "fields.body"),
        PlaceholderDefinition("picture", 20, "fields.picture", required=False, content_type="image"),
    ],
    "statement": [
        PlaceholderDefinition("statement", 0, "action_title"),
        PlaceholderDefinition("support", 2, "fields.statement", required=False),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
    ],
    "quote": [
        PlaceholderDefinition("quote", 20, "fields.quote"),
        PlaceholderDefinition("name", 21, "fields.attribution", required=False),
        PlaceholderDefinition("role", 22, "fields.role", required=False),
        PlaceholderDefinition("headshot", 30, "fields.headshot", required=False, content_type="image"),
    ],
    "comparison": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("left_heading", 20, "fields.columns.0.heading"),
        PlaceholderDefinition("left_points", 21, "fields.columns.0.points"),
        PlaceholderDefinition("right_heading", 22, "fields.columns.1.heading"),
        PlaceholderDefinition("right_points", 23, "fields.columns.1.points"),
        PlaceholderDefinition("verdict", 40, "fields.verdict", required=False),
    ],
    "faq": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("q1", 20, "fields.items.0.question"),
        PlaceholderDefinition("a1", 21, "fields.items.0.answer"),
        PlaceholderDefinition("q2", 22, "fields.items.1.question", required=False),
        PlaceholderDefinition("a2", 23, "fields.items.1.answer", required=False),
        PlaceholderDefinition("q3", 24, "fields.items.2.question", required=False),
        PlaceholderDefinition("a3", 25, "fields.items.2.answer", required=False),
        PlaceholderDefinition("q4", 26, "fields.items.3.question", required=False),
        PlaceholderDefinition("a4", 27, "fields.items.3.answer", required=False),
    ],
    "thesis": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("claim1", 20, "fields.claims.0"),
        PlaceholderDefinition("claim2", 21, "fields.claims.1", required=False),
        PlaceholderDefinition("pivot_question", 22, "fields.pivot_question"),
        PlaceholderDefinition("verdict", 23, "fields.verdict"),
        PlaceholderDefinition("footnote", 24, "fields.footnote", required=False),
    ],
    "process_flow": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("step1_title", 20, "fields.steps.0.title"),
        PlaceholderDefinition("step1_body", 21, "fields.steps.0.body", required=False),
        PlaceholderDefinition("step2_title", 22, "fields.steps.1.title", required=False),
        PlaceholderDefinition("step2_body", 23, "fields.steps.1.body", required=False),
        PlaceholderDefinition("step3_title", 24, "fields.steps.2.title", required=False),
        PlaceholderDefinition("step3_body", 25, "fields.steps.2.body", required=False),
        PlaceholderDefinition("step4_title", 26, "fields.steps.3.title", required=False),
        PlaceholderDefinition("step4_body", 27, "fields.steps.3.body", required=False),
        PlaceholderDefinition("note", 40, "fields.note", required=False),
    ],
    "table": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("table", 10, "fields.table", required=False, content_type="table"),
        PlaceholderDefinition("table_text", 10, "fields.table_text", required=False),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("intro", 12, "fields.intro", required=False),
        PlaceholderDefinition("callout", 40, "fields.callout", required=False),
    ],
    "chart": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("chart", 10, "fields.chart", required=False, content_type="chart"),
        PlaceholderDefinition("chart_text", 10, "fields.chart_text", required=False),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("takeaway_primary", 13, "fields.takeaway", required=False),
        PlaceholderDefinition("takeaway_secondary", 14, "fields.secondary_takeaway", required=False),
        PlaceholderDefinition("source", 41, "fields.source", required=False),
    ],
    "kpi": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("stat1_number", 20, "fields.stats.0.number"),
        PlaceholderDefinition("stat1_label", 21, "fields.stats.0.label"),
        PlaceholderDefinition("stat2_number", 22, "fields.stats.1.number", required=False),
        PlaceholderDefinition("stat2_label", 23, "fields.stats.1.label", required=False),
        PlaceholderDefinition("stat3_number", 24, "fields.stats.2.number", required=False),
        PlaceholderDefinition("stat3_label", 25, "fields.stats.2.label", required=False),
        PlaceholderDefinition("stat4_number", 26, "fields.stats.3.number", required=False),
        PlaceholderDefinition("stat4_label", 27, "fields.stats.3.label", required=False),
        PlaceholderDefinition("context", 40, "fields.context", required=False),
    ],
    "matrix": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("q1_title", 20, "fields.quadrants.0.title"),
        PlaceholderDefinition("q1_items", 21, "fields.quadrants.0.items"),
        PlaceholderDefinition("q2_title", 22, "fields.quadrants.1.title", required=False),
        PlaceholderDefinition("q2_items", 23, "fields.quadrants.1.items", required=False),
        PlaceholderDefinition("q3_title", 24, "fields.quadrants.2.title", required=False),
        PlaceholderDefinition("q3_items", 25, "fields.quadrants.2.items", required=False),
        PlaceholderDefinition("q4_title", 26, "fields.quadrants.3.title", required=False),
        PlaceholderDefinition("q4_items", 27, "fields.quadrants.3.items", required=False),
        PlaceholderDefinition("vertical_axis", 30, "fields.vertical_axis", required=False),
        PlaceholderDefinition("horizontal_axis", 31, "fields.horizontal_axis", required=False),
    ],
    "team": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("person1_name", 10, "fields.members.0.name"),
        PlaceholderDefinition("person1_role", 11, "fields.members.0.role"),
        PlaceholderDefinition("person2_name", 12, "fields.members.1.name", required=False),
        PlaceholderDefinition("person2_role", 13, "fields.members.1.role", required=False),
        PlaceholderDefinition("person3_name", 14, "fields.members.2.name", required=False),
        PlaceholderDefinition("person3_role", 15, "fields.members.2.role", required=False),
        PlaceholderDefinition("picture1", 20, "fields.members.0.picture", required=False, content_type="image"),
        PlaceholderDefinition("picture2", 21, "fields.members.1.picture", required=False, content_type="image"),
        PlaceholderDefinition("picture3", 22, "fields.members.2.picture", required=False, content_type="image"),
    ],
    "org_chart": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("top_role", 20, "fields.top_role"),
        PlaceholderDefinition("lead1", 21, "fields.leads.0", required=False),
        PlaceholderDefinition("lead2", 22, "fields.leads.1", required=False),
        PlaceholderDefinition("lead3", 23, "fields.leads.2", required=False),
        PlaceholderDefinition("team1", 24, "fields.teams.0", required=False),
        PlaceholderDefinition("team2", 25, "fields.teams.1", required=False),
        PlaceholderDefinition("team3", 26, "fields.teams.2", required=False),
        PlaceholderDefinition("note", 40, "fields.note", required=False),
    ],
    "logo_wall": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("caption", 40, "fields.caption", required=False),
        *[PlaceholderDefinition(f"logo{i}", 19 + i, f"fields.logos.{i - 1}", required=False, content_type="logo") for i in range(1, 9)],
    ],
    "case_study": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("client_line", 13, "fields.client_line"),
        PlaceholderDefinition("challenge", 20, "fields.challenge"),
        PlaceholderDefinition("approach", 21, "fields.approach"),
        PlaceholderDefinition("outcome", 22, "fields.outcome"),
        PlaceholderDefinition("headline_result", 40, "fields.headline_result", required=False),
    ],
    "pricing_stat": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("kicker", 11, "fields.kicker", required=False),
        PlaceholderDefinition("lead_in", 13, "fields.lead_in", required=False),
        PlaceholderDefinition("bullet_col_1", 14, "fields.bullet_columns.0", required=False),
        PlaceholderDefinition("bullet_col_2", 15, "fields.bullet_columns.1", required=False),
        PlaceholderDefinition("stat_kicker", 20, "fields.stat.kicker", required=False),
        PlaceholderDefinition("number", 21, "fields.stat.number"),
        PlaceholderDefinition("secondary", 22, "fields.stat.secondary", required=False),
        PlaceholderDefinition("term", 23, "fields.stat.term", required=False),
        PlaceholderDefinition("note", 24, "fields.stat.note", required=False),
        PlaceholderDefinition("fine_print", 41, "fields.fine_print", required=False),
    ],
    "summary_cta": [
        PlaceholderDefinition("title", 0, "action_title"),
        PlaceholderDefinition("subheading", 2, "fields.subheading", required=False),
        PlaceholderDefinition("body", 3, "fields.body"),
        PlaceholderDefinition("cta", 4, "fields.cta", required=False),
    ],
}

BASELINE_ID_TO_ARCHETYPE: dict[str, str] = {
    "A01": "cover", "A02": "cover_dark", "B04": "image_right", "B05": "statement",
    "B06": "quote", "B08": "comparison", "B09": "faq", "B10": "thesis",
    "C01": "process_flow", "D01": "table", "D02": "chart", "D03": "kpi", "D05": "matrix",
    "E01": "team", "E02": "org_chart", "E03": "logo_wall", "E04": "case_study",
    "F01": "pricing_stat", "F02": "table", "G01": "summary_cta", "G02": "closing",
}

SUPPORTED_ARCHETYPES: frozenset[str] = frozenset(EXACT_MATCH_PLACEHOLDER_MAPPINGS.keys()) | frozenset(key.lower() for key in BASELINE_ID_TO_ARCHETYPE.keys())


@dataclass
class PlaceholderBuilder:
    """Populates placeholders and removes unresolved default prompt text."""

    engine_config: EngineConfig = field(default_factory=lambda: config)
    baseline_path: Optional[Path] = None
    archetype_placeholders: Optional[dict[str, list[PlaceholderDefinition]]] = None
    log: logging.Logger = field(default_factory=lambda: logger)
    cleanup_reports: list[dict[str, Any]] = field(default_factory=list)
    last_cleanup_report: dict[str, Any] = field(default_factory=dict)

    def populate(self, slide: Any, slide_definition: Mapping[str, Any]) -> None:
        archetype = self._canonical_archetype(self._read_archetype(slide_definition))
        mappings = self._load_placeholder_definitions()

        if archetype not in mappings:
            raise PlaceholderBuilderException(f"Unsupported archetype for placeholder population: '{archetype}'")

        report: dict[str, Any] = {
            "archetype": archetype,
            "populated": [],
            "removed_unfilled_text": [],
            "removed_prompt_text": [],
            "preserved_media": [],
            "preserved_business_text": [],
        }

        filled_idx = self._populate_from_definitions(slide, slide_definition, archetype, mappings[archetype], report)
        self._cleanup_after_population(slide, filled_idx, mappings[archetype], report)

        self.last_cleanup_report = report
        self.cleanup_reports.append(report)

    def _load_placeholder_definitions(self) -> dict[str, list[PlaceholderDefinition]]:
        if self.archetype_placeholders is not None:
            return self.archetype_placeholders
        return EXACT_MATCH_PLACEHOLDER_MAPPINGS

    def _populate_from_definitions(
        self,
        slide: Any,
        slide_definition: Mapping[str, Any],
        archetype: str,
        definitions: list[PlaceholderDefinition],
        report: dict[str, Any],
    ) -> set[int]:
        filled_idx: set[int] = set()

        for definition in definitions:
            value = self._value_from_path(slide_definition, definition.source)
            text = self._normalise_value(value, definition.join_with)

            if definition.is_media:
                if self._placeholder_by_idx(slide).get(definition.idx) is not None:
                    report["preserved_media"].append({
                        "idx": definition.idx,
                        "name": definition.name,
                        "content_type": definition.content_type,
                        "reason": "reserved for future media handler",
                    })
                if definition.required and text is None:
                    raise PlaceholderBuilderException(f"Missing required media value for {archetype}.{definition.name} from source '{definition.source}'.")
                continue

            if text is None:
                if definition.required:
                    raise PlaceholderBuilderException(f"Missing required value for {archetype}.{definition.name} from source '{definition.source}'.")
                continue

            self._fill_text_placeholder(slide, definition, text, filled_idx, report)

        return filled_idx

    def _fill_text_placeholder(
        self,
        slide: Any,
        definition: PlaceholderDefinition,
        value: str,
        filled_idx: set[int],
        report: dict[str, Any],
    ) -> None:
        placeholder = self._placeholder_by_idx(slide).get(definition.idx)
        if placeholder is None:
            if definition.required:
                raise PlaceholderBuilderException(f"Required placeholder idx {definition.idx} was not found on the slide.")
            raise PlaceholderBuilderException(f"Optional field supplied but placeholder idx {definition.idx} was not found.")

        if not getattr(placeholder, "has_text_frame", True):
            raise PlaceholderBuilderException(f"Placeholder idx {definition.idx} exists but is not text-capable.")

        placeholder.text = value
        filled_idx.add(definition.idx)
        report["populated"].append({"idx": definition.idx, "name": definition.name, "source": definition.source})

    def _cleanup_after_population(
        self,
        slide: Any,
        filled_idx: set[int],
        definitions: list[PlaceholderDefinition],
        report: dict[str, Any],
    ) -> None:
        media_idx = {definition.idx for definition in definitions if definition.is_media}

        for shape in list(getattr(slide, "shapes", [])):
            idx = self._placeholder_idx(shape)
            text = self._shape_text(shape)

            if idx in filled_idx:
                continue

            if idx in media_idx or self._is_media_placeholder(shape):
                report["preserved_media"].append({"idx": idx, "name": self._shape_name(shape), "content_type": "media", "reason": "media placeholder preserved"})
                continue

            if not getattr(shape, "has_text_frame", False):
                continue

            if self._is_default_prompt_text(text):
                self._remove_shape(shape)
                report["removed_prompt_text"].append({"idx": idx, "name": self._shape_name(shape), "text": text})
                continue

            if self._is_placeholder(shape) and not text.strip():
                self._remove_shape(shape)
                report["removed_unfilled_text"].append({"idx": idx, "name": self._shape_name(shape), "text": text})
                continue

            if text.strip():
                report["preserved_business_text"].append({"idx": idx, "name": self._shape_name(shape), "text": text[:120]})

    def _placeholder_by_idx(self, slide: Any) -> dict[int, Any]:
        placeholders: dict[int, Any] = {}
        for placeholder in getattr(slide, "placeholders", []):
            idx = self._placeholder_idx(placeholder)
            if idx is not None:
                placeholders[idx] = placeholder
        return placeholders

    def _placeholder_idx(self, shape: Any) -> int | None:
        try:
            return int(shape.placeholder_format.idx)
        except Exception:
            return None

    def _shape_name(self, shape: Any) -> str | None:
        return getattr(shape, "name", None)

    def _shape_text(self, shape: Any) -> str:
        if not getattr(shape, "has_text_frame", False):
            return ""
        return (getattr(shape, "text", "") or "").strip()

    def _is_placeholder(self, shape: Any) -> bool:
        return bool(getattr(shape, "is_placeholder", self._placeholder_idx(shape) is not None))

    def _is_media_placeholder(self, shape: Any) -> bool:
        try:
            placeholder_type = str(shape.placeholder_format.type).upper()
        except Exception:
            return False
        return any(token in placeholder_type for token in ("PICTURE", "CHART", "TABLE", "MEDIA", "OBJECT"))

    def _is_default_prompt_text(self, text: str) -> bool:
        normalized = " ".join((text or "").split())
        if not normalized:
            return False
        # Multi-line prompt boxes often contain the same default prompt repeated.
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        if lines and all(any(pattern.search(line) for pattern in DEFAULT_PROMPT_PATTERNS) for line in lines):
            return True
        return any(pattern.search(normalized) for pattern in DEFAULT_PROMPT_PATTERNS)

    def _remove_shape(self, shape: Any) -> None:
        element = shape._element
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    def _read_archetype(self, slide_definition: Mapping[str, Any]) -> str:
        archetype = slide_definition.get("archetype")
        if not isinstance(archetype, str) or not archetype.strip():
            raise PlaceholderBuilderException("Slide definition must contain a non-empty 'archetype'.")
        return archetype.strip().lower()

    def _canonical_archetype(self, archetype: str) -> str:
        return BASELINE_ID_TO_ARCHETYPE.get(archetype.upper(), archetype)

    def _value_from_path(self, item: Mapping[str, Any], source: str) -> Any:
        current: Any = item
        for part in source.split("."):
            if isinstance(current, Mapping):
                current = current.get(part)
            elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
                if part.isdigit():
                    index = int(part)
                    current = current[index] if index < len(current) else None
                else:
                    return None
            else:
                return None
        return current

    def _normalise_value(self, value: Any, join_with: str) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            values = []
            for entry in value:
                if isinstance(entry, str) and entry.strip():
                    values.append(entry.strip())
                elif isinstance(entry, Mapping):
                    title = entry.get("title") or entry.get("heading") or entry.get("name") or entry.get("number")
                    body = entry.get("body") or entry.get("text") or entry.get("label") or entry.get("role")
                    parts = [str(part).strip() for part in (title, body) if part is not None and str(part).strip()]
                    if parts:
                        values.append(" - ".join(parts))
            return join_with.join(values) if values else None
        return str(value).strip() if str(value).strip() else None
