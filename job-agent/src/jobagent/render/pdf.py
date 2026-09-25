"""Convert a rendered DOCX to PDF via docx2pdf, which drives MS Word through
COM. Windows + Word only (that's what's on this machine) -- the import stays
lazy so importing this module doesn't break on a non-Windows CI runner.
"""

from pathlib import Path


def docx_to_pdf(docx_path: Path) -> Path:
    from docx2pdf import convert

    pdf_path = docx_path.with_suffix(".pdf")
    convert(str(docx_path), str(pdf_path))
    return pdf_path
