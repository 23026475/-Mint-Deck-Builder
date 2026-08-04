"""Unit tests for ArchetypeMapper."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from presentation_engine.services.archetype_mapper import (
    ArchetypeMapper,
    ArchetypeMappingException,
)


class FakeLayoutMapper:
    def __init__(self, available_layouts: set[str]) -> None:
        self.available_layouts = available_layouts

    def get_layout(self, name: str) -> object:
        if name not in self.available_layouts:
            raise KeyError(name)
        return {"layout_name": name}


class ArchetypeMapperTests(unittest.TestCase):
    def _write_baseline(self, temp_dir: str, data: object) -> Path:
        path = Path(temp_dir) / "archetype-baseline.json"
        path.write_text(json.dumps(data), encoding="utf8")
        return path

    def test_successful_archetype_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_path = self._write_baseline(
                temp_dir,
                {
                    "archetypes": [
                        {"archetype": "cards3", "layout": "Content - Cards 3"}
                    ]
                },
            )
            layout_mapper = FakeLayoutMapper({"Content - Cards 3"})

            mapper = ArchetypeMapper(
                layout_mapper=layout_mapper,
                baseline_path=baseline_path,
            )

            layout = mapper.get_layout_for_archetype("cards3")

            self.assertEqual(layout, {"layout_name": "Content - Cards 3"})
            self.assertEqual(mapper.get_layout_name_for_archetype("cards3"), "Content - Cards 3")

    def test_unknown_archetype_raises_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_path = self._write_baseline(
                temp_dir,
                {
                    "archetypes": [
                        {"archetype": "cards3", "layout": "Content - Cards 3"}
                    ]
                },
            )
            layout_mapper = FakeLayoutMapper({"Content - Cards 3"})
            mapper = ArchetypeMapper(layout_mapper=layout_mapper, baseline_path=baseline_path)

            with self.assertRaisesRegex(ArchetypeMappingException, "Unknown archetype"):
                mapper.get_layout_for_archetype("unknown")

    def test_missing_layout_in_template_raises_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_path = self._write_baseline(
                temp_dir,
                {
                    "archetypes": [
                        {
                            "archetype": "cards3",
                            "layout": "Content - Cards 3",
                        }
                    ]
                },
            )

            layout_mapper = FakeLayoutMapper(set())

            mapper = ArchetypeMapper(
                layout_mapper=layout_mapper,
                baseline_path=baseline_path,
            )

            with self.assertRaisesRegex(
                ArchetypeMappingException,
                "could not be found",
            ):
                mapper.get_layout_for_archetype("cards3")

    def test_duplicate_archetype_definitions_raise_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_path = self._write_baseline(
                temp_dir,
                {
                    "archetypes": [
                        {"archetype": "cards3", "layout": "Content - Cards 3"},
                        {"archetype": "cards3", "layout": "Content - Cards 4"},
                    ]
                },
            )
            layout_mapper = FakeLayoutMapper({"Content - Cards 3", "Content - Cards 4"})

            with self.assertRaisesRegex(ArchetypeMappingException, "Duplicate archetype"):
                ArchetypeMapper(layout_mapper=layout_mapper, baseline_path=baseline_path)

    def test_duplicate_layout_mappings_raise_exception_when_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_path = self._write_baseline(
                temp_dir,
                {
                    "archetypes": [
                        {"archetype": "cards3", "layout": "Content - Cards 3"},
                        {"archetype": "summary", "layout": "Content - Cards 3"},
                    ]
                },
            )
            layout_mapper = FakeLayoutMapper({"Content - Cards 3"})

            with self.assertRaisesRegex(ArchetypeMappingException, "Duplicate layout mappings"):
                ArchetypeMapper(
                    layout_mapper=layout_mapper,
                    baseline_path=baseline_path,
                    require_unique_layout_mappings=True,
                )


if __name__ == "__main__":
    unittest.main()
