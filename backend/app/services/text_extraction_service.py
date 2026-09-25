import io
import re
from typing import Tuple

import docx
import pypdf


class TextExtractionService:
    """
    Extracts and normalizes raw text from uploaded document files (PDF, DOCX, TXT).
    Guarantees safe failure handling without crashing the application.
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
    SUPPORTED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "application/octet-stream",  # Fallback for some clients
    }

    @classmethod
    def extract_text(cls, file_bytes: bytes, filename: str, content_type: str = "") -> str:
        """
        Extract text from file bytes based on filename extension and content type.
        Raises ValueError with clear message if the file is invalid, empty, or unparseable.
        """
        if not file_bytes:
            raise ValueError("Uploaded file is empty (0 bytes).")

        ext = cls._get_extension(filename)
        if ext not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. Supported formats: {', '.join(sorted(cls.SUPPORTED_EXTENSIONS))}"
            )

        if ext == ".pdf":
            raw_text = cls._extract_from_pdf(file_bytes)
        elif ext == ".docx":
            raw_text = cls._extract_from_docx(file_bytes)
        elif ext in {".txt", ".md"}:
            raw_text = cls._extract_from_text(file_bytes)
        else:
            raise ValueError(f"No extraction strategy for extension '{ext}'")

        normalized = cls.normalize_text(raw_text)
        if not normalized or len(normalized.strip()) == 0:
            raise ValueError("No readable text could be extracted from document.")

        return normalized

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Normalize text by removing null bytes (PostgreSQL incompatible),
        unifying line breaks, and stripping redundant whitespace.
        """
        if not text:
            return ""
        # Remove null characters which cannot be stored in PostgreSQL text columns
        text = text.replace("\x00", "")
        # Normalize newlines
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse excessive newlines (more than 2 consecutive newlines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def _extract_from_pdf(cls, file_bytes: bytes) -> str:
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise ValueError("PDF is encrypted and cannot be read.") from exc

            pages_text = []
            for i, page in enumerate(reader.pages):
                page_content = page.extract_text() or ""
                if page_content.strip():
                    pages_text.append(page_content.strip())

            return "\n\n".join(pages_text)
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Failed to extract text from PDF: {str(exc)}") from exc

    @classmethod
    def _extract_from_docx(cls, file_bytes: bytes) -> str:
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        paragraphs.append(row_text)
            return "\n\n".join(paragraphs)
        except Exception as exc:
            raise ValueError(f"Failed to extract text from DOCX: {str(exc)}") from exc

    @classmethod
    def _extract_from_text(cls, file_bytes: bytes) -> str:
        # Try UTF-8 first, fallback to latin-1
        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Failed to decode text file with supported encodings (UTF-8, Latin-1).")

    @classmethod
    def _get_extension(cls, filename: str) -> str:
        parts = filename.lower().rsplit(".", 1)
        if len(parts) > 1:
            return f".{parts[1]}"
        return ""
