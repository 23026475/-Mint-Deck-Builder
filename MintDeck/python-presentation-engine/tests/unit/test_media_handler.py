from __future__ import annotations

import unittest

from presentation_engine.handlers.media_handler import MediaHandler


class FakeProcessor:
    def __init__(self):
        self.calls = []

    def process(self, slide, slide_definition):
        self.calls.append((slide, slide_definition))
        return [{"ok": True}]


class MediaHandlerTests(unittest.TestCase):
    def test_media_handler_delegates_to_image_processor(self):
        processor = FakeProcessor()
        handler = MediaHandler(processors=(processor,))
        slide = object()
        definition = {"archetype": "image_right"}

        report = handler.process(slide, definition)

        self.assertEqual(len(processor.calls), 1)
        self.assertEqual(report, [{"ok": True}])


if __name__ == "__main__":
    unittest.main()
