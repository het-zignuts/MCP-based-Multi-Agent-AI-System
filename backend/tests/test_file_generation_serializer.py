from app.services.file_generation.models import ArtifactDocument, ArtifactSection
from app.services.file_generation.serializer import render_document_bytes


def test_render_document_bytes_pdf_contains_text():
    document = ArtifactDocument(
        title="Test Title",
        summary="This is a summary.",
        sections=[
            ArtifactSection(
                heading="Section 1",
                paragraphs=["Line one.", "Line two."],
                bullets=["item 1", "item 2"],
            )
        ],
    )

    pdf_bytes = render_document_bytes(document, "pdf")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100

    import fitz

    pdf = fitz.open("pdf", pdf_bytes)
    assert pdf.page_count >= 1
    text = pdf[0].get_text().strip()
    assert "Test Title" in text or "Section 1" in text
