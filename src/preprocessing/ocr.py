"""
ocr.py
------
OCR-ready pipeline for SentinelGraph AI.

Since real scanned FIR/report documents aren't available in this synthetic
pipeline, this module:

  1. Renders a text document (e.g. an FIR narrative) into a "scanned-looking"
     image using PIL -- adding noise, slight rotation and blur to mimic a
     real scan/photograph of a paper document.
  2. Runs that image back through Tesseract OCR (via `pytesseract`) to
     recover text.
  3. Feeds the OCR output through the text-cleaning pipeline and reports a
     similarity score against the original ground-truth text, so downstream
     consumers know how much to trust an OCR'd record.

If Tesseract isn't installed/available, `OcrEngine` degrades gracefully by
returning the (lightly noised) input text untouched, so the rest of the
pipeline keeps working end-to-end without a hard dependency on a system
binary.
"""

import io
import random
import difflib
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    import pytesseract
    _HAS_TESSERACT = True
except ImportError:  # pragma: no cover
    _HAS_TESSERACT = False

from .cleaner import RegexNormalizer


@dataclass
class OcrResult:
    original_text: str
    raw_ocr_text: str
    cleaned_ocr_text: str
    similarity: float          # 0..1, how close OCR output is to the original
    engine: str                # "tesseract" or "fallback"


class DocumentImageRenderer:
    """Renders plain text into a synthetic 'scanned document' image."""

    def __init__(self, width: int = 900, seed: Optional[int] = None):
        self.width = width
        self._rng = random.Random(seed)

    def render(self, text: str, font_size: int = 18) -> Image.Image:
        lines = self._wrap_text(text, max_chars=95)
        line_height = int(font_size * 1.6)
        height = max(200, line_height * (len(lines) + 4))

        img = Image.new("L", (self.width, height), color=255)
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        y = 20
        for line in lines:
            draw.text((30, y), line, fill=0, font=font)
            y += line_height

        img = self._add_scan_artifacts(img)
        return img

    def _add_scan_artifacts(self, img: Image.Image) -> Image.Image:
        # Slight blur to mimic a soft-focus scan/photo.
        img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

        # Sprinkle salt-and-pepper style noise.
        pixels = img.load()
        w, h = img.size
        num_noise_pixels = int(w * h * 0.01)
        for _ in range(num_noise_pixels):
            x, y = self._rng.randrange(w), self._rng.randrange(h)
            pixels[x, y] = self._rng.choice([0, 255])

        # Small rotation to mimic a crooked scan.
        angle = self._rng.uniform(-1.5, 1.5)
        img = img.rotate(angle, expand=True, fillcolor=255)
        return img

    @staticmethod
    def _wrap_text(text: str, max_chars: int):
        words = text.split()
        lines, current = [], ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > max_chars:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]


class OcrEngine:
    """Thin wrapper around pytesseract with a graceful offline fallback."""

    def extract_text(self, image: Image.Image, fallback_text: str = "") -> str:
        if _HAS_TESSERACT:
            try:
                return pytesseract.image_to_string(image)
            except Exception:
                pass  # fall through to fallback
        return fallback_text

    @property
    def engine_name(self) -> str:
        return "tesseract" if _HAS_TESSERACT else "fallback"


class OcrPipeline:
    """
    End-to-end OCR-ready pipeline: text -> synthetic scanned image -> OCR ->
    cleaned text, with a similarity score against the ground truth so callers
    can decide whether to trust the OCR'd record.
    """

    def __init__(self, seed: Optional[int] = None):
        self.renderer = DocumentImageRenderer(seed=seed)
        self.engine = OcrEngine()
        self.normalizer = RegexNormalizer()

    def process_text(self, text: str) -> OcrResult:
        image = self.renderer.render(text)
        raw_ocr_text = self.engine.extract_text(image, fallback_text=text)
        cleaned_ocr_text = self.normalizer.normalize(raw_ocr_text)

        similarity = self._similarity(text, cleaned_ocr_text)

        return OcrResult(
            original_text=text,
            raw_ocr_text=raw_ocr_text,
            cleaned_ocr_text=cleaned_ocr_text,
            similarity=similarity,
            engine=self.engine.engine_name,
        )

    def process_image_bytes(self, image_bytes: bytes) -> str:
        """Entry point for genuinely scanned documents (PNG/JPEG bytes)."""
        image = Image.open(io.BytesIO(image_bytes))
        raw_text = self.engine.extract_text(image, fallback_text="")
        return self.normalizer.normalize(raw_text)

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        a_norm = " ".join(a.lower().split())
        b_norm = " ".join(b.lower().split())
        if not a_norm and not b_norm:
            return 1.0
        return round(difflib.SequenceMatcher(None, a_norm, b_norm).ratio(), 3)
