import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image
from src.preprocessing.ocr import DocumentImageRenderer, OcrEngine, OcrPipeline, OcrResult


class TestDocumentImageRenderer(unittest.TestCase):
    def setUp(self):
        self.renderer = DocumentImageRenderer(width=600, seed=1)

    def test_render_returns_image(self):
        img = self.renderer.render("This is a short FIR narrative for testing.")
        self.assertIsInstance(img, Image.Image)

    def test_render_handles_long_text_with_wrapping(self):
        long_text = "word " * 300
        img = self.renderer.render(long_text)
        self.assertGreater(img.height, 200)

    def test_render_handles_empty_text(self):
        img = self.renderer.render("")
        self.assertIsInstance(img, Image.Image)


class TestOcrEngine(unittest.TestCase):
    def test_engine_name_reports_backend(self):
        engine = OcrEngine()
        self.assertIn(engine.engine_name, {"tesseract", "fallback"})

    def test_extract_text_returns_string(self):
        engine = OcrEngine()
        renderer = DocumentImageRenderer(seed=2)
        img = renderer.render("Simple test sentence for OCR extraction.")
        result = engine.extract_text(img, fallback_text="Simple test sentence for OCR extraction.")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result.strip()), 0)


class TestOcrPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = OcrPipeline(seed=3)

    def test_process_text_returns_ocr_result(self):
        result = self.pipeline.process_text("The suspect was seen near the warehouse district.")
        self.assertIsInstance(result, OcrResult)
        self.assertTrue(0.0 <= result.similarity <= 1.0)

    def test_process_text_similarity_reasonably_high_for_clean_render(self):
        text = "On January 5th the complainant filed a report regarding theft."
        result = self.pipeline.process_text(text)
        # OCR won't be pixel-perfect, but should be substantially similar.
        self.assertGreater(result.similarity, 0.6)

    def test_process_image_bytes_accepts_png(self):
        img = self.pipeline.renderer.render("Report content for byte-level OCR test.")
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        text = self.pipeline.process_image_bytes(buf.getvalue())
        self.assertIsInstance(text, str)


if __name__ == "__main__":
    unittest.main()
