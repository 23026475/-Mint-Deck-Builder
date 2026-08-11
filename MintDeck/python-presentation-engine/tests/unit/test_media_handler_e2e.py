from __future__ import annotations

import unittest
from presentation_engine.handlers.media_handler import MediaHandler

class FakeProcessor:
    def __init__(self):
        self.calls = []
    def process(self, slide, slide_definition):
        self.calls.append((slide, slide_definition))
        return [{"processor": "fake"}]

class MediaHandlerEndToEndTests(unittest.TestCase):
    def test_media_handler_delegates_to_registered_processors(self):
        processor = FakeProcessor()
        handler = MediaHandler(processors=(processor,))
        slide = object()
        definition = {"archetype": "image_right"}
        report = handler.process(slide, definition)
        self.assertEqual(len(processor.calls), 1)
        self.assertEqual(report, [{"processor": "fake"}])

if __name__ == "__main__":
    unittest.main()
