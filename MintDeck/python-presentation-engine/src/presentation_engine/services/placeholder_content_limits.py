"""Load and evaluate data-driven placeholder content ceilings.

This module does not render PowerPoint content. It reads
``config/placeholder-content-limits.json`` and validates proposed text or table
content before a builder or media handler writes it to a slide.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


class PlaceholderContentLimitError(Exception):
    """Base error for placeholder content-limit operations."""


class PlaceholderContentLimitConfigurationError(PlaceholderContentLimitError):
    """Raised when the content-limit configuration is missing or invalid."""


class PlaceholderContentOverflowError(PlaceholderContentLimitError):
    """Raised when supplied content exceeds an approved placeholder ceiling."""


@dataclass(frozen=True)
class ContentLimitRule:
    """Resolved limit for one placeholder content type."""

    name: str
    content_kind: str
    max_lines: int | None = None
    recommended_max_lines: int | None = None
    max_characters: int | None = None
    max_total_rows: int | None = None
    overflow_action: str = "reject"


@dataclass(frozen=True)
class PlaceholderLimitBinding:
    """Mapping from an archetype placeholder to a reusable content rule."""

    archetype: str
    placeholder_name: str
    placeholder_idx: int
    limit_name: str
    rule: ContentLimitRule


@dataclass(frozen=True)
class ContentMeasurement:
    """Measured size of proposed placeholder content."""

    characters: int = 0
    explicit_lines: int = 0
    estimated_lines: int = 0
    total_rows: int = 0


@dataclass(frozen=True)
class ContentLimitResult:
    """Result returned by a non-raising validation call."""

    allowed: bool
    binding: PlaceholderLimitBinding | None
    measurement: ContentMeasurement
    violations: tuple[str, ...]


class PlaceholderContentLimitPolicy:
    """Read and evaluate placeholder ceilings from JSON configuration."""

    DEFAULT_CONFIG_PATH = Path("config/placeholder-content-limits.json")

    def __init__(
        self,
        config_path: str | Path | None = None,
        config_data: Mapping[str, Any] | None = None,
    ) -> None:
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self._config = dict(config_data) if config_data is not None else self._load_config()
        self._validate_config_shape()

    @property
    def config(self) -> Mapping[str, Any]:
        return self._config

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise PlaceholderContentLimitConfigurationError(
                f"Placeholder content-limit configuration does not exist: {self.config_path}"
            )

        try:
            raw = self.config_path.read_text(encoding="utf8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PlaceholderContentLimitConfigurationError(
                f"Placeholder content-limit configuration is not valid JSON: {self.config_path}"
            ) from exc
        except OSError as exc:
            raise PlaceholderContentLimitConfigurationError(
                f"Could not read placeholder content-limit configuration: {self.config_path}"
            ) from exc

        if not isinstance(data, dict):
            raise PlaceholderContentLimitConfigurationError(
                "Placeholder content-limit configuration must contain a JSON object."
            )

        return data

    def _validate_config_shape(self) -> None:
        limits = self._config.get("content_limits")
        bindings = self._config.get("archetype_placeholders")

        if not isinstance(limits, Mapping):
            raise PlaceholderContentLimitConfigurationError(
                "Configuration must contain a 'content_limits' object."
            )

        if not isinstance(bindings, Mapping):
            raise PlaceholderContentLimitConfigurationError(
                "Configuration must contain an 'archetype_placeholders' object."
            )

        for rule_name, payload in limits.items():
            if not isinstance(payload, Mapping):
                raise PlaceholderContentLimitConfigurationError(
                    f"Content limit '{rule_name}' must be an object."
                )

            if not isinstance(payload.get("content_kind"), str):
                raise PlaceholderContentLimitConfigurationError(
                    f"Content limit '{rule_name}' must define content_kind."
                )

            for number_field in (
                "max_lines",
                "recommended_max_lines",
                "max_characters",
                "max_total_rows",
            ):
                value = payload.get(number_field)
                if value is not None and (not isinstance(value, int) or value < 1):
                    raise PlaceholderContentLimitConfigurationError(
                        f"Content limit '{rule_name}.{number_field}' must be a positive integer."
                    )

        for archetype, placeholders in bindings.items():
            if not isinstance(placeholders, Mapping):
                raise PlaceholderContentLimitConfigurationError(
                    f"Archetype binding '{archetype}' must be an object."
                )

            for placeholder_name, binding in placeholders.items():
                if not isinstance(binding, Mapping):
                    raise PlaceholderContentLimitConfigurationError(
                        f"Placeholder binding '{archetype}.{placeholder_name}' must be an object."
                    )

                limit_name = binding.get("limit")
                idx = binding.get("idx")

                if limit_name not in limits:
                    raise PlaceholderContentLimitConfigurationError(
                        f"Placeholder binding '{archetype}.{placeholder_name}' references "
                        f"unknown limit '{limit_name}'."
                    )

                if not isinstance(idx, int):
                    raise PlaceholderContentLimitConfigurationError(
                        f"Placeholder binding '{archetype}.{placeholder_name}.idx' must be an integer."
                    )

    def resolve_binding(
        self,
        archetype: str,
        placeholder_name: str,
    ) -> PlaceholderLimitBinding | None:
        archetype_key = (archetype or "").strip().lower()
        placeholder_key = (placeholder_name or "").strip()

        archetype_bindings = self._config["archetype_placeholders"].get(archetype_key)
        if not isinstance(archetype_bindings, Mapping):
            return None

        binding_payload = archetype_bindings.get(placeholder_key)
        if not isinstance(binding_payload, Mapping):
            return None

        limit_name = str(binding_payload["limit"])
        rule_payload = self._config["content_limits"][limit_name]

        rule = ContentLimitRule(
            name=limit_name,
            content_kind=str(rule_payload["content_kind"]),
            max_lines=rule_payload.get("max_lines"),
            recommended_max_lines=rule_payload.get("recommended_max_lines"),
            max_characters=rule_payload.get("max_characters"),
            max_total_rows=rule_payload.get("max_total_rows"),
            overflow_action=str(
                rule_payload.get(
                    "overflow_action",
                    self._config.get("defaults", {}).get("overflow_action", "reject"),
                )
            ),
        )

        return PlaceholderLimitBinding(
            archetype=archetype_key,
            placeholder_name=placeholder_key,
            placeholder_idx=int(binding_payload["idx"]),
            limit_name=limit_name,
            rule=rule,
        )

    def measure_text(self, value: Any, binding: PlaceholderLimitBinding) -> ContentMeasurement:
        text = self._normalise_text(value)
        if not text:
            return ContentMeasurement()

        explicit_lines = max(1, len(text.splitlines()))
        max_characters = binding.rule.max_characters

        if max_characters:
            estimated_lines = sum(
                max(1, (len(line) + max_characters - 1) // max_characters)
                for line in text.splitlines() or [text]
            )
        else:
            estimated_lines = explicit_lines

        return ContentMeasurement(
            characters=len(text),
            explicit_lines=explicit_lines,
            estimated_lines=estimated_lines,
        )

    def measure_table(self, value: Any) -> ContentMeasurement:
        if value is None:
            return ContentMeasurement()

        if isinstance(value, Mapping):
            headers = value.get("headers") or []
            rows = value.get("rows") or []
            header_count = 1 if self._is_non_string_sequence(headers) and len(headers) > 0 else 0
            row_count = len(rows) if self._is_non_string_sequence(rows) else 0
            return ContentMeasurement(total_rows=header_count + row_count)

        if self._is_non_string_sequence(value):
            return ContentMeasurement(total_rows=len(value))

        return ContentMeasurement()

    def validate(
        self,
        archetype: str,
        placeholder_name: str,
        value: Any,
    ) -> ContentLimitResult:
        binding = self.resolve_binding(archetype, placeholder_name)
        if binding is None:
            return ContentLimitResult(
                allowed=True,
                binding=None,
                measurement=ContentMeasurement(),
                violations=(),
            )

        if binding.rule.content_kind == "table":
            measurement = self.measure_table(value)
        else:
            measurement = self.measure_text(value, binding)

        violations: list[str] = []
        rule = binding.rule

        if rule.max_characters is not None and measurement.characters > rule.max_characters:
            violations.append(
                f"received {measurement.characters} characters; maximum is {rule.max_characters}"
            )

        if rule.max_lines is not None and measurement.estimated_lines > rule.max_lines:
            violations.append(
                f"requires approximately {measurement.estimated_lines} lines; maximum is {rule.max_lines}"
            )

        if rule.max_total_rows is not None and measurement.total_rows > rule.max_total_rows:
            violations.append(
                f"received {measurement.total_rows} total rows; maximum is {rule.max_total_rows}"
            )

        return ContentLimitResult(
            allowed=not violations,
            binding=binding,
            measurement=measurement,
            violations=tuple(violations),
        )

    def validate_or_raise(
        self,
        archetype: str,
        placeholder_name: str,
        value: Any,
    ) -> ContentLimitResult:
        result = self.validate(archetype, placeholder_name, value)

        if result.allowed:
            return result

        assert result.binding is not None
        details = "; ".join(result.violations)
        raise PlaceholderContentOverflowError(
            f"Content exceeds approved ceiling for "
            f"{result.binding.archetype}.{result.binding.placeholder_name} "
            f"(placeholder idx {result.binding.placeholder_idx}, "
            f"limit '{result.binding.limit_name}'): {details}."
        )

    def _normalise_text(self, value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if self._is_non_string_sequence(value):
            return "\n".join(str(item).strip() for item in value if str(item).strip())

        return str(value).strip()

    def _is_non_string_sequence(self, value: Any) -> bool:
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
