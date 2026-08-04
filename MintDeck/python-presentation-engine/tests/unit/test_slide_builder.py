"""Unit tests for SlideBuilder."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from presentation_engine.builders.slide_builder import (
    SlideBuilder,
    SlideBuilderException,
)


class FakeArchetypeMapper:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_layout_for_archetype(self, archetype: str) -> object:
        self.calls.append(archetype)
        return {"layout_for": archetype}


class FakePlaceholderBuilder:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def populate(self, slide: object, slide_definition: object) -> None:
        self.calls.append((slide, slide_definition))


class FakeSlides:
    def __init__(self) -> None:
        self.created: list[object] = []

    def add_slide(self, slide_layout: object) -> object:
        slide = {"created_from_layout": slide_layout}
        self.created.append(slide)
        return slide


class FakePresentation:
    def __init__(self) -> None:
        self.slides = FakeSlides()


class FakePresentationFactory:
    def __init__(self) -> None:
        self.template_paths: list[Path] = []
        self.presentation = FakePresentation()

    def create_from_template(self, template_path: Path) -> FakePresentation:
        self.template_paths.append(template_path)
        return self.presentation


class SlideBuilderTests(unittest.TestCase):
    def _create_template_file(self, temp_dir: str) -> Path:
        template_path = Path(temp_dir) / "FY27 AI-Ready v3.0.work.pptx"
        template_path.write_bytes(b"fake pptx")
        return template_path

    def test_successfully_creates_three_supported_slide_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = self._create_template_file(temp_dir)
            archetype_mapper = FakeArchetypeMapper()
            placeholder_builder = FakePlaceholderBuilder()
            presentation_factory = FakePresentationFactory()

            builder = SlideBuilder(
                archetype_mapper=archetype_mapper,
                presentation_factory=presentation_factory,
                placeholder_builder=placeholder_builder,
            )

            contract = {
                "slides": [
                    {"archetype": "cover", "fields": {}},
                    {"archetype": "cards3", "fields": {}},
                    {"archetype": "closing", "fields": {}},
                ]
            }

            result = builder.build(contract, template_path=template_path)

            self.assertEqual(len(result.slides), 3)
            self.assertEqual(archetype_mapper.calls, ["cover", "cards3", "closing"])
            self.assertEqual(len(placeholder_builder.calls), 3)
            self.assertEqual(presentation_factory.template_paths, [template_path.resolve()])

    def test_unsupported_archetype_raises_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = self._create_template_file(temp_dir)
            archetype_mapper = FakeArchetypeMapper()
            placeholder_builder = FakePlaceholderBuilder()

            builder = SlideBuilder(
                archetype_mapper=archetype_mapper,
                presentation_factory=FakePresentationFactory(),
                placeholder_builder=placeholder_builder,
            )

            contract = {"slides": [{"archetype": "agenda"}]}

            with self.assertRaisesRegex(SlideBuilderException, "Unsupported archetype"):
                builder.build(contract, template_path=template_path)

            self.assertEqual(archetype_mapper.calls, [])
            self.assertEqual(placeholder_builder.calls, [])

    def test_layouts_are_obtained_only_through_archetype_mapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = self._create_template_file(temp_dir)
            archetype_mapper = FakeArchetypeMapper()
            placeholder_builder = FakePlaceholderBuilder()
            presentation_factory = FakePresentationFactory()

            builder = SlideBuilder(
                archetype_mapper=archetype_mapper,
                presentation_factory=presentation_factory,
                placeholder_builder=placeholder_builder,
            )

            contract = {"slides": [{"archetype": "cover"}]}
            result = builder.build(contract, template_path=template_path)

            self.assertEqual(archetype_mapper.calls, ["cover"])
            self.assertEqual(len(placeholder_builder.calls), 1)
            self.assertEqual(
                result.slides[0],
                {"created_from_layout": {"layout_for": "cover"}},
            )


if __name__ == "__main__":
    unittest.main()
