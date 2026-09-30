import io
import docx
import pypdf
import pytest

from backend.app.services.text_extraction_service import TextExtractionService


def create_sample_pdf(text: str = "Hello DailyBlog AI PDF World!") -> bytes:
    escaped_text = text.replace("(", "\\(").replace(")", "\\)")
    stream_content = f"BT\n/F1 12 Tf\n72 712 Td\n({escaped_text}) Tj\nET\n".encode("utf-8")
    stream_len = len(stream_content)
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length " + str(stream_len).encode("utf-8") + b" >> stream\n"
        + stream_content +
        b"endstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n0\n%%EOF"
    )
    return pdf


def test_text_extraction_pdf():
    pdf_bytes = create_sample_pdf("Enterprise Architecture Knowledge PDF")
    extracted = TextExtractionService.extract_text(pdf_bytes, "architecture.pdf")
    assert "Enterprise Architecture Knowledge PDF" in extracted


def create_sample_docx(text: str) -> bytes:
    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_text_extraction_txt():
    content = "DailyBlog AI is an enterprise automated blog generation platform.\nIt uses RAG."
    file_bytes = content.encode("utf-8")
    extracted = TextExtractionService.extract_text(file_bytes, "knowledge.txt")
    assert "DailyBlog AI" in extracted
    assert "It uses RAG" in extracted


def test_text_extraction_docx():
    content = "Enterprise whitepaper on generative AI agents and deterministic safety."
    file_bytes = create_sample_docx(content)
    extracted = TextExtractionService.extract_text(file_bytes, "whitepaper.docx")
    assert "Enterprise whitepaper on generative AI agents" in extracted


def test_text_extraction_markdown():
    content = "# Knowledge Title\n\n- Point 1: RAG\n- Point 2: Embeddings\n"
    file_bytes = content.encode("utf-8")
    extracted = TextExtractionService.extract_text(file_bytes, "notes.md")
    assert "# Knowledge Title" in extracted
    assert "Point 1: RAG" in extracted


def test_text_extraction_empty_file_rejected():
    with pytest.raises(ValueError, match="empty"):
        TextExtractionService.extract_text(b"", "empty.txt")


def test_text_extraction_unsupported_file_type_rejected():
    with pytest.raises(ValueError, match="Unsupported file type"):
        TextExtractionService.extract_text(b"some content", "malicious.exe")


def test_text_extraction_corrupted_docx_handled_gracefully():
    corrupted_bytes = b"PK\x03\x04not a real docx archive"
    with pytest.raises(ValueError, match="Failed to extract text from DOCX"):
        TextExtractionService.extract_text(corrupted_bytes, "corrupted.docx")


def test_text_extraction_corrupted_pdf_handled_gracefully():
    corrupted_bytes = b"%PDF-1.4 not a real pdf"
    with pytest.raises(ValueError, match="Failed to extract text from PDF|No readable text"):
        TextExtractionService.extract_text(corrupted_bytes, "corrupted.pdf")


def test_text_normalization_removes_null_bytes():
    raw_text = "Clean text\x00with null\x00bytes\r\nand CRLF."
    normalized = TextExtractionService.normalize_text(raw_text)
    assert "\x00" not in normalized
    assert "\r" not in normalized
    assert "Clean textwith nullbytes\nand CRLF." == normalized
