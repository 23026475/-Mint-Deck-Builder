
"""Unit tests for exact-match placeholder mappings."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from presentation_engine.builders.placeholder_builder import PlaceholderBuilder, PlaceholderBuilderException
from presentation_engine.builders.slide_builder import SlideBuilder, SlideBuilderException


class FakeParent:
    def __init__(self, placeholders):
        self.placeholders = placeholders
    def remove(self, element):
        placeholder = element.placeholder
        if placeholder in self.placeholders:
            self.placeholders.remove(placeholder)


class FakeElement:
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.parent = None
    def getparent(self):
        return self.parent


class FakePlaceholder:
    def __init__(self, idx, text="PROMPT", has_text_frame=True):
        self.placeholder_format = SimpleNamespace(idx=idx)
        self.text = text
        self.has_text_frame = has_text_frame
        self._element = FakeElement(self)


class FakeSlide:
    def __init__(self, indexes):
        self.placeholders = [FakePlaceholder(idx) for idx in indexes]
        parent = FakeParent(self.placeholders)
        for placeholder in self.placeholders:
            placeholder._element.parent = parent
    def by_idx(self, idx):
        for placeholder in self.placeholders:
            if placeholder.placeholder_format.idx == idx:
                return placeholder
        raise KeyError(idx)
    def indexes(self):
        return {p.placeholder_format.idx for p in self.placeholders}


class FakeMapper:
    def __init__(self, missing=False):
        self.missing = missing
        self.calls = []
    def get_layout_for_archetype(self, archetype):
        self.calls.append(archetype)
        if self.missing:
            raise KeyError(archetype)
        return {"layout": archetype}


class FakeSlides:
    def add_slide(self, layout):
        return {"layout": layout}


class FakePresentation:
    def __init__(self):
        self.slides = FakeSlides()


class NoOpPlaceholderBuilder:
    def populate(self, slide, slide_definition):
        return None


class ExactMatchPlaceholderMappingTests(unittest.TestCase):
    def test_slide_builder_accepts_exact_match_archetypes(self):
        builder = SlideBuilder(archetype_mapper=FakeMapper(), placeholder_builder=NoOpPlaceholderBuilder())
        presentation = FakePresentation()
        for archetype in [
            "image_right", "statement", "quote", "comparison", "faq", "thesis", "process_flow",
            "table", "chart", "kpi", "matrix", "team", "org_chart", "logo_wall", "case_study",
            "pricing_stat", "summary_cta", "cover_dark"
        ]:
            slide = builder.build_slide(presentation, {"archetype": archetype, "fields": {}, "action_title": "Title"})
            self.assertEqual(slide["layout"], {"layout": archetype})

    def test_statement_mapping(self):
        slide = FakeSlide([0, 2, 11, 99])
        PlaceholderBuilder().populate(slide, {"archetype": "statement", "action_title": "The baseline shifted", "fields": {"statement": "Support line"}})
        self.assertEqual(slide.by_idx(0).text, "The baseline shifted")
        self.assertEqual(slide.by_idx(2).text, "Support line")
        self.assertNotIn(99, slide.indexes())

    def test_quote_mapping(self):
        slide = FakeSlide([20, 21, 22, 30])
        PlaceholderBuilder().populate(slide, {"archetype": "quote", "fields": {"quote": "Value is visible.", "attribution": "Operations Leader"}})
        self.assertEqual(slide.by_idx(20).text, "Value is visible.")
        self.assertEqual(slide.by_idx(21).text, "Operations Leader")
        self.assertNotIn(22, slide.indexes())
        self.assertNotIn(30, slide.indexes())

    def test_comparison_mapping(self):
        slide = FakeSlide([0, 11, 20, 21, 22, 23, 40])
        PlaceholderBuilder().populate(slide, {"archetype": "comparison", "action_title": "Two paths lead to different outcomes", "fields": {"columns": [{"heading": "Current", "points": ["Manual", "Slow"]}, {"heading": "Future", "points": ["Automated", "Measured"]}], "verdict": "Move forward"}})
        self.assertEqual(slide.by_idx(20).text, "Current")
        self.assertEqual(slide.by_idx(21).text, "Manual\nSlow")
        self.assertEqual(slide.by_idx(40).text, "Move forward")

    def test_thesis_mapping(self):
        slide = FakeSlide([0, 11, 20, 21, 22, 23, 24])
        PlaceholderBuilder().populate(slide, {"archetype": "thesis", "action_title": "A structured program reduces risk", "fields": {"claims": ["Outcomes first", "Governance scales"], "pivot_question": "How do we scale?", "verdict": "Use a phased model"}})
        self.assertEqual(slide.by_idx(20).text, "Outcomes first")
        self.assertEqual(slide.by_idx(21).text, "Governance scales")
        self.assertEqual(slide.by_idx(22).text, "How do we scale?")
        self.assertNotIn(24, slide.indexes())

    def test_process_flow_mapping(self):
        slide = FakeSlide([0, 11, 20, 21, 22, 23, 24, 25, 26, 27, 40])
        PlaceholderBuilder().populate(slide, {"archetype": "process_flow", "action_title": "Four workstreams move users", "fields": {"steps": [{"title": "Prepare"}, {"title": "Identify"}, {"title": "Enable"}, {"title": "Measure"}]}})
        self.assertEqual(slide.by_idx(20).text, "Prepare")
        self.assertEqual(slide.by_idx(26).text, "Measure")
        self.assertNotIn(40, slide.indexes())

    def test_case_study_mapping(self):
        slide = FakeSlide([0, 11, 13, 20, 21, 22, 40])
        PlaceholderBuilder().populate(slide, {"archetype": "case_study", "action_title": "A phased rollout delivered value", "fields": {"client_line": "Global manufacturer", "challenge": "Too much search time", "approach": "Targeted use cases", "outcome": "Expanded adoption", "headline_result": "Time savings reported"}})
        self.assertEqual(slide.by_idx(13).text, "Global manufacturer")
        self.assertEqual(slide.by_idx(40).text, "Time savings reported")

    def test_kpi_matrix_pricing_and_summary_mappings(self):
        kpi = FakeSlide([0, 11, 20, 21, 22, 23, 40])
        PlaceholderBuilder().populate(kpi, {"archetype": "kpi", "action_title": "Adoption improved", "fields": {"stats": [{"number": "42%", "label": "Adoption"}, {"number": "8h", "label": "Saved"}]}})
        self.assertEqual(kpi.by_idx(20).text, "42%")
        self.assertEqual(kpi.by_idx(23).text, "Saved")

        matrix = FakeSlide([0, 11, 20, 21, 30, 31])
        PlaceholderBuilder().populate(matrix, {"archetype": "matrix", "action_title": "Priorities are clear", "fields": {"quadrants": [{"title": "High", "items": ["One", "Two"]}], "vertical_axis": "Impact", "horizontal_axis": "Readiness"}})
        self.assertEqual(matrix.by_idx(21).text, "One\nTwo")

        pricing = FakeSlide([0, 11, 13, 14, 15, 20, 21, 22, 23, 24, 41])
        PlaceholderBuilder().populate(pricing, {"archetype": "pricing_stat", "action_title": "The model is measurable", "fields": {"stat": {"number": "R10k"}}})
        self.assertEqual(pricing.by_idx(21).text, "R10k")

        summary = FakeSlide([0, 2, 3, 4])
        PlaceholderBuilder().populate(summary, {"archetype": "summary_cta", "action_title": "Next step", "fields": {"body": "Start pilot", "cta": "Approve scope"}})
        self.assertEqual(summary.by_idx(3).text, "Start pilot")

    def test_missing_required_field_raises(self):
        with self.assertRaisesRegex(PlaceholderBuilderException, "Missing required value"):
            PlaceholderBuilder().populate(FakeSlide([0, 2, 11]), {"archetype": "statement", "fields": {}})

    def test_missing_required_placeholder_raises(self):
        with self.assertRaisesRegex(PlaceholderBuilderException, "Required placeholder idx 0"):
            PlaceholderBuilder().populate(FakeSlide([2, 11]), {"archetype": "statement", "action_title": "Title", "fields": {}})

    def test_unknown_archetype_raises(self):
        with self.assertRaisesRegex(PlaceholderBuilderException, "Unsupported archetype"):
            PlaceholderBuilder().populate(FakeSlide([0]), {"archetype": "B07", "fields": {}})

    def test_missing_layout_mapping_raises_from_slide_builder(self):
        builder = SlideBuilder(archetype_mapper=FakeMapper(missing=True), placeholder_builder=NoOpPlaceholderBuilder())
        with self.assertRaisesRegex(SlideBuilderException, "Failed to resolve layout"):
            builder.build_slide(FakePresentation(), {"archetype": "statement", "fields": {}, "action_title": "Title"})


if __name__ == "__main__":
    unittest.main()
