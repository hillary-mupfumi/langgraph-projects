"""Render a tailored resume/cover letter to a one-page, ATS-friendly DOCX
(no tables, columns or images), named per rules.yaml style.filename_pattern.
"""

from pathlib import Path

from docx import Document
from docx.shared import Pt

from jobagent.config import load_rules


def _slug(text: str) -> str:
    return "".join(c for c in text if c.isalnum()) or "Unknown"


def build_filename(doc_type: str, company: str, tag: str) -> str:
    pattern = load_rules().style.filename_pattern
    return pattern.format(doc_type=doc_type, company=_slug(company), tag=_slug(tag)) + ".docx"


def render_resume(
    candidate_name: str, tailored: dict, out_dir: Path, company: str, tag: str
) -> Path:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading(candidate_name, level=1)
    if tailored.get("summary"):
        doc.add_paragraph(tailored["summary"])

    doc.add_heading("Experience", level=2)
    for bullet in tailored.get("bullets", []):
        doc.add_paragraph(bullet["text"], style="List Bullet")

    if tailored.get("skills"):
        doc.add_heading("Skills", level=2)
        doc.add_paragraph(", ".join(tailored["skills"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / build_filename("Resume", company, tag)
    doc.save(out_path)
    return out_path


def render_cover_letter(cover_letter: str, out_dir: Path, company: str, tag: str) -> Path:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    for paragraph in cover_letter.split("\n\n"):
        doc.add_paragraph(paragraph)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / build_filename("CoverLetter", company, tag)
    doc.save(out_path)
    return out_path
