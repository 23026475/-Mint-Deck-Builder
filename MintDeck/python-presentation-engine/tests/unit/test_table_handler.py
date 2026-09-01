from __future__ import annotations

import unittest
from types import SimpleNamespace

from presentation_engine.handlers.table_handler import (
    InvalidTableDataException,
    TableHandler,
    TablePlaceholderNotFoundException,
)


class FakeCell:
    def __init__(self) -> None:
        self.text = ""


class FakeTable:
    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self.cells = [
            [FakeCell() for _ in range(cols)]
            for _ in range(rows)
        ]

    def cell(self, row: int, col: int) -> FakeCell:
        return self.cells[row][col]


class FakeTableShape:
    def __init__(self, rows: int, cols: int) -> None:
        self.name = "Inserted Table"
        self.table = FakeTable(rows, cols)
        self.left = None
        self.top = None
        self.width = None
        self.height = None


class FakeTablePlaceholder:
    def __init__(self, idx: int) -> None:
        self.placeholder_format = SimpleNamespace(idx=idx)
        self.left = 10
        self.top = 20
        self.width = 300
        self.height = 200
        self.inserted_tables: list[FakeTableShape] = []

    def insert_table(self, rows: int, cols: int) -> FakeTableShape:
        shape = FakeTableShape(rows, cols)
        self.inserted_tables.append(shape)
        return shape


class FakeSlide:
    def __init__(self, placeholders: list[object]) -> None:
        self.placeholders = placeholders


class TableHandlerTests(unittest.TestCase):
    def test_insert_table_into_configured_placeholder(self):
        placeholder = FakeTablePlaceholder(idx=10)
        slide = FakeSlide([placeholder])

        handler = TableHandler()

        report = handler.insert_tables(
            slide,
            {
                "archetype": "table",
                "action_title": "Table validation",
                "fields": {
                    "table": {
                        "headers": ["Capability", "Status"],
                        "rows": [
                            ["ImageHandler", "Complete"],
                            ["TableHandler", "In progress"],
                        ],
                    }
                },
            },
        )

        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["status"], "inserted")
        self.assertEqual(report[0]["placeholder_idx"], 10)
        self.assertEqual(report[0]["row_count"], 3)
        self.assertEqual(report[0]["column_count"], 2)

        inserted = placeholder.inserted_tables[0]

        self.assertEqual(inserted.left, 10)
        self.assertEqual(inserted.top, 20)
        self.assertEqual(inserted.width, 300)
        self.assertEqual(inserted.height, 200)

        self.assertEqual(inserted.table.cell(0, 0).text, "Capability")
        self.assertEqual(inserted.table.cell(0, 1).text, "Status")
        self.assertEqual(inserted.table.cell(1, 0).text, "ImageHandler")
        self.assertEqual(inserted.table.cell(1, 1).text, "Complete")
        self.assertEqual(inserted.table.cell(2, 0).text, "TableHandler")
        self.assertEqual(inserted.table.cell(2, 1).text, "In progress")

    def test_missing_table_placeholder_raises_clear_error(self):
        slide = FakeSlide([])

        handler = TableHandler()

        with self.assertRaises(TablePlaceholderNotFoundException):
            handler.insert_tables(
                slide,
                {
                    "archetype": "table",
                    "fields": {
                        "table": {
                            "headers": ["A"],
                            "rows": [["B"]],
                        }
                    },
                },
            )

    def test_empty_optional_table_is_skipped(self):
        placeholder = FakeTablePlaceholder(idx=10)
        slide = FakeSlide([placeholder])

        handler = TableHandler()

        report = handler.insert_tables(
            slide,
            {
                "archetype": "table",
                "fields": {
                    "table": {
                        "headers": [],
                        "rows": [],
                    }
                },
            },
        )

        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["status"], "skipped_empty_table")
        self.assertEqual(len(placeholder.inserted_tables), 0)

    def test_invalid_table_data_raises_clear_error(self):
        placeholder = FakeTablePlaceholder(idx=10)
        slide = FakeSlide([placeholder])

        handler = TableHandler()

        with self.assertRaises(InvalidTableDataException):
            handler.insert_tables(
                slide,
                {
                    "archetype": "table",
                    "fields": {
                        "table": "not a valid table payload"
                    },
                },
            )


if __name__ == "__main__":
    unittest.main()