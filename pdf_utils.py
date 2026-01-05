"""
PDF Utility functions for text extraction.
Used to convert PDF resumes to text for LLM processing.
"""
from PyPDF2 import PdfReader


def extract_text_from_pdf(pdf_path):
    """
    Extract text content from a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        str: Extracted text content
    """
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error extracting PDF text: {str(e)}")
        return ""


def extract_text_from_pdf_bytes(pdf_bytes):
    """
    Extract text content from PDF bytes (for in-memory PDFs).

    Args:
        pdf_bytes: PDF file content as bytes

    Returns:
        str: Extracted text content
    """
    import io
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error extracting PDF text from bytes: {str(e)}")
        return ""
