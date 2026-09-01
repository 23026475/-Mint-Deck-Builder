from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


logger = logging.getLogger(__name__)


class TableHandlerException(Exception):
    """Raised when table handling fails."""


class TablePlaceholderNotFoundException(TableHandlerException):
    """Raised when a table placeholder cannot be found."""


class InvalidTableDataException(TableHandlerException):
    """Raised when table data cannot be normalised into rows and columns."""


@dataclass(frozen=True)
class TableRequest:
    archetype: str
    media_field: str
    source: str
    placeholder_idx: int
    table_data: Any


@dataclass(frozen=True)
class NormalizedTable:
    headers: list[str]
    rows: list[list[str]]

    @property
    def row_count(self) -> int:
        return len(self.rows) + (1 if self.headers else 0)

    @property
    def column_count(self) -> int:
        candidates: list[int] = []

        if self.headers:
            candidates.append(len(self.headers))

        candidates.extend(len(row) for row in self.rows)

        return max(candidates) if candidates else 0


class TableHandler:
    """
    Handles table insertion into existing PowerPoint table placeholders.

    This handler does not create slides, select layouts, populate text, or
    modify image handling. It only inserts table data into configured table
    placeholders.
    """

    DEFAULT_TABLE_PLACEHOLDERS: dict[str, dict[str, int]] = {
        "table": {
            "table": 10,
        }
    }

    def __init__(
        self,
        placeholder_mappings: Mapping[str, Mapping[str, int]] | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self.placeholder_mappings = placeholder_mappings or self.DEFAULT_TABLE_PLACEHOLDERS
        self.log = log or logger

    def process(self, slide: Any, slide_definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        return self.insert_tables(slide, slide_definition)

    def insert_tables(self, slide: Any, slide_definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        requests = self._collect_table_requests(slide_definition)
        reports: list[dict[str, Any]] = []

        for request in requests:
            placeholder = self._placeholder_by_idx(slide).get(request.placeholder_idx)

            if placeholder is None:
                raise TablePlaceholderNotFoundException(
                    f"Table placeholder idx {request.placeholder_idx} was not found "
                    f"for archetype '{request.archetype}', media field '{request.media_field}'."
                )

            normalized = self._normalize_table_data(request.table_data)

            if normalized.row_count == 0 or normalized.column_count == 0:
                reports.append(
                    {
                        "archetype": request.archetype,
                        "media_field": request.media_field,
                        "source": request.source,
                        "placeholder_idx": request.placeholder_idx,
                        "status": "skipped_empty_table",
                        "row_count": normalized.row_count,
                        "column_count": normalized.column_count,
                    }
                )
                continue

            table_shape = self._insert_table(placeholder, normalized)

            reports.append(
                {
                    "archetype": request.archetype,
                    "media_field": request.media_field,
                    "source": request.source,
                    "placeholder_idx": request.placeholder_idx,
                    "status": "inserted",
                    "row_count": normalized.row_count,
                    "column_count": normalized.column_count,
                    "shape_name": getattr(table_shape, "name", None),
                }
            )

        return reports

    def _collect_table_requests(self, slide_definition: Mapping[str, Any]) -> list[TableRequest]:
        archetype_value = slide_definition.get("archetype")

        if not isinstance(archetype_value, str):
            return []

        archetype = archetype_value.strip().lower()
        fields = slide_definition.get("fields", {})

        if not isinstance(fields, Mapping):
            return []

        table_data = fields.get("table")

        if table_data is None:
            return []

        placeholder_idx = self._resolve_placeholder_idx(archetype, "table")

        return [
            TableRequest(
                archetype=archetype,
                media_field="table",
                source="fields.table",
                placeholder_idx=placeholder_idx,
                table_data=table_data,
            )
        ]

    def _resolve_placeholder_idx(self, archetype: str, media_field: str) -> int:
        archetype_mapping = self.placeholder_mappings.get(archetype)

        if not archetype_mapping:
            raise TableHandlerException(
                f"No table placeholder mapping found for archetype '{archetype}'."
            )

        if media_field not in archetype_mapping:
            raise TableHandlerException(
                f"No table placeholder mapping found for archetype '{archetype}', field '{media_field}'."
            )

        return int(archetype_mapping[media_field])

    def _normalize_table_data(self, table_data: Any) -> NormalizedTable:
        if table_data is None:
            return NormalizedTable(headers=[], rows=[])

        if isinstance(table_data, Mapping):
            headers = table_data.get("headers") or []
            rows = table_data.get("rows") or []

            if not isinstance(headers, Sequence) or isinstance(headers, (str, bytes)):
                raise InvalidTableDataException("fields.table.headers must be a list of strings.")

            if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
                raise InvalidTableDataException("fields.table.rows must be a list of rows.")

            normalized_headers = [str(value).strip() for value in headers]
            normalized_rows = self._normalize_rows(rows)

            return self._pad_table(NormalizedTable(normalized_headers, normalized_rows))

        if isinstance(table_data, Sequence) and not isinstance(table_data, (str, bytes)):
            rows = self._normalize_rows(table_data)
            return self._pad_table(NormalizedTable(headers=[], rows=rows))

        raise InvalidTableDataException(
            "fields.table must be either an object with headers/rows or a list of rows."
        )

    def _normalize_rows(self, rows: Sequence[Any]) -> list[list[str]]:
        normalized_rows: list[list[str]] = []

        for row in rows:
            if isinstance(row, Mapping):
                normalized_rows.append([str(value).strip() for value in row.values()])
                continue

            if isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
                normalized_rows.append([str(value).strip() for value in row])
                continue

            raise InvalidTableDataException(
                "Each table row must be a list, tuple, or object."
            )

        return normalized_rows

    def _pad_table(self, table: NormalizedTable) -> NormalizedTable:
        column_count = table.column_count

        if column_count == 0:
            return table

        headers = list(table.headers)

        if headers:
            headers = headers + [""] * (column_count - len(headers))

        rows = [
            row + [""] * (column_count - len(row))
            for row in table.rows
        ]

        return NormalizedTable(headers=headers, rows=rows)

    def _insert_table(self, placeholder: Any, table: NormalizedTable) -> Any:
        if not hasattr(placeholder, "insert_table"):
            raise TablePlaceholderNotFoundException(
                "Target placeholder does not support insert_table()."
            )

        left = getattr(placeholder, "left", None)
        top = getattr(placeholder, "top", None)
        width = getattr(placeholder, "width", None)
        height = getattr(placeholder, "height", None)

        table_shape = placeholder.insert_table(table.row_count, table.column_count)
        pptx_table = table_shape.table

        current_row = 0

        if table.headers:
            for column_index, value in enumerate(table.headers):
                pptx_table.cell(current_row, column_index).text = value
            current_row += 1

        for row_index, row in enumerate(table.rows):
            for column_index, value in enumerate(row):
                pptx_table.cell(current_row + row_index, column_index).text = value

        if left is not None:
            table_shape.left = left
        if top is not None:
            table_shape.top = top
        if width is not None:
            table_shape.width = width
        if height is not None:
            table_shape.height = height

        return table_shape

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
