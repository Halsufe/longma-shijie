from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class ParseResult:
    text: str
    pages: int = 1
    status: str = "parsed"
    media_type: str = "text/plain"
    error_summary: str | None = None
    used_ocr: bool = False


def clean_html(html: str) -> ParseResult:
    cleaned = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "\n", cleaned)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return ParseResult(text=text, media_type="text/html")


def parse_file(path: str | Path, media_type: str | None = None) -> ParseResult:
    file_path = Path(path)
    media_type = (media_type or "").lower()
    suffix = file_path.suffix.lower()
    try:
        if suffix in {".html", ".htm"} or "html" in media_type:
            return clean_html(file_path.read_text(encoding="utf-8", errors="replace"))
        if suffix == ".pdf" or "pdf" in media_type:
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
            if not text:
                return ParseResult("", len(pages), "partial", "application/pdf", "scanned PDF requires OCR", True)
            return ParseResult(text, len(pages), "parsed", "application/pdf")
        if suffix == ".docx" or "wordprocessingml" in media_type:
            import docx2txt
            return ParseResult(docx2txt.process(str(file_path)).strip(), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        if suffix in {".jpg", ".jpeg", ".png"} or media_type.startswith("image/"):
            return ParseResult("", 1, "partial", media_type or "image/*", "OCR engine unavailable", True)
        return ParseResult("", 1, "unsupported", media_type or "application/octet-stream")
    except Exception as exc:
        return ParseResult("", 1, "failed", media_type or "application/octet-stream", str(exc)[:300])

