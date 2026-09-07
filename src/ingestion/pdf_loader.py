"""
pdf_loader.py
-------------
Optional PDF ingestion loader (Phase: ingestion).

Extracts per-page text from PDF documents so downstream preprocessing
(cleaning / OCR fallback / NER) can treat them like any other text source.

Dependency policy (mirrors the project's adapter philosophy):

* :class:`PdfLoader` uses :mod:`pypdf` when available;
* if the dependency is missing, ``available()`` reports False and
  instantiation raises :class:`PdfLoaderError` with an actionable message -
  the rest of the pipeline keeps working without it;
* scanned PDFs with no embedded text are reported per page so the OCR stage
  (preprocessing.ocr) can take over.

The loader never executes embedded code or fetches remote resources; it
only reads local files passed to it.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:  # optional dependency
    from pypdf import PdfReader  # type: ignore

    _HAS_PYPDF = True
except ImportError:  # pragma: no cover - depends on env
    _HAS_PYPDF = False


class PdfLoaderError(RuntimeError):
    """Base class for PDF ingestion failures."""


class PdfDependencyError(PdfLoaderError):
    """Raised when pypdf is not installed."""


@dataclass
class PdfPage:
    page_number: int          # 1-based
    text: str
    char_count: int
    needs_ocr: bool


@dataclass
class PdfDocument:
    source_path: str
    doc_id: str
    title: Optional[str]
    num_pages: int
    pages: List[PdfPage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: str = ""

    def to_records(self) -> List[Dict[str, Any]]:
        """Flatten to cleaned-record-shaped dicts the preprocessing stage
        can consume directly."""
        return [
            {
                "record_id": f"{self.doc_id}-P{page.page_number}",
                "record_type": "document_page",
                "text": page.text,
                "language": None,
                "is_duplicate": False,
                "duplicate_of": None,
                "metadata": {
                    "source_path": self.source_path,
                    "doc_id": self.doc_id,
                    "page_number": page.page_number,
                    "needs_ocr": page.needs_ocr,
                    "title": self.title,
                },
            }
            for page in self.pages
            if page.text.strip() and not page.needs_ocr
        ]


class PdfLoader:
    """Load local PDF files into text records (pypdf backend)."""

    def __init__(self, *, ocr_char_threshold: int = 25) -> None:
        if not _HAS_PYPDF:
            raise PdfDependencyError(
                "pypdf is not installed. Install it with: pip install pypdf"
            )
        self.ocr_char_threshold = ocr_char_threshold

    @staticmethod
    def available() -> bool:
        return _HAS_PYPDF

    def load(self, path: str | Path) -> PdfDocument:
        src = Path(path)
        if not src.exists():
            raise PdfLoaderError(f"PDF not found: {src}")
        if src.suffix.lower() != ".pdf":
            raise PdfLoaderError(f"not a PDF file: {src.name}")
        try:
            reader = PdfReader(str(src))
        except Exception as exc:  # noqa: BLE001 - pypdf raises many types
            raise PdfLoaderError(f"could not parse {src.name}: {exc}") from exc

        pages: List[PdfPage] = []
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:  # noqa: BLE001 - individual pages may be corrupt
                logger.warning("page %s of %s failed to extract", idx, src.name)
                text = ""
            pages.append(
                PdfPage(
                    page_number=idx,
                    text=text,
                    char_count=len(text),
                    needs_ocr=len(text) < self.ocr_char_threshold,
                )
            )

        metadata: Dict[str, Any] = {}
        title = None
        try:
            raw_meta = reader.metadata or {}
            metadata = {k.lstrip("/"): str(v) for k, v in raw_meta.items()}
            title = metadata.get("title")
        except Exception:  # noqa: BLE001
            pass

        doc_id = "DOC-" + uuid.uuid5(
            uuid.NAMESPACE_URL, f"file://{src.resolve()}"
        ).hex[:12].upper()
        return PdfDocument(
            source_path=str(src),
            doc_id=doc_id,
            title=title,
            num_pages=len(pages),
            pages=pages,
            metadata=metadata,
            ingested_at=datetime.now(timezone.utc).isoformat(),
        )

    def load_to_records(self, path: str | Path) -> List[Dict[str, Any]]:
        """Convenience: directly usable by the preprocessing pipeline."""
        return self.load(path).to_records()

    def checksum(self, path: str | Path) -> str:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
