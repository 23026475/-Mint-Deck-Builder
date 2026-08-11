from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from presentation_engine.builders.slide_builder import SlideBuilder


class FakeArchetypeMapper:
    def get_layout_for_archetype(self, archetype: str) -> object:
        return {"layout_for": archetype}


class FakePlaceholderBuilder:
    def __init__(self):
        self.calls = []
    def populate(self, slide, slide_definition):
        self.calls.append((slide, slide_definition))


class FakeMediaHandler:
    def __init__(self):
        self.calls = []
    def process(self, slide, slide_definition):
        self.calls.append((slide, slide_definition))
        return []


class FakeSlides:
    def __init__(self):
        self.created = []
    def add_slide(self, slide_layout):
        slide = {"created_from_layout": slide_layout}
        self.created.append(slide)
        return slide


class FakePresentation:
    def __init__(self):
        self.slides = FakeSlides()


class FakePresentationFactory:
    def __init__(self):
        self.presentation = FakePresentation()
    def create_from_template(self, template_path: Path):
        return self.presentation


class SlideBuilderMediaInvocationTests(unittest.TestCase):
    def test_slide_builder_invokes_media_handler_after_placeholder_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract = {"slides": [{"archetype": "cover", "fields": {}}]}
            template_path = Path(tmp) / "template.pptx"
            template_path.write_bytes(b"fake")
            placeholders = FakePlaceholderBuilder()
            media = FakeMediaHandler()
            builder = SlideBuilder(
                archetype_mapper=FakeArchetypeMapper(),
                presentation_factory=FakePresentationFactory(),
                placeholder_builder=placeholders,
                media_handler=media,
            )

            builder.build(contract, template_path=template_path)

            self.assertEqual(len(placeholders.calls), 1)
            self.assertEqual(len(media.calls), 1)
            self.assertIs(placeholders.calls[0][0], media.calls[0][0])
            self.assertEqual(placeholders.calls[0][1], media.calls[0][1])


if __name__ == "__main__":
    unittest.main()
