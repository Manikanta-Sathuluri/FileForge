from __future__ import annotations

from pathlib import Path
from typing import Callable

from pypdf import PdfReader, PdfWriter
from docx import Document
from docxcompose.composer import Composer


def merge_pdfs(
    input_paths: list[Path],
    output: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """Merge PDFs in the supplied order into one PDF."""
    if not input_paths:
        raise ValueError("At least one PDF is required.")

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    total = len(input_paths)

    for index, path in enumerate(input_paths, 1):
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise ValueError(
                    f"'{path.name}' is password-protected and could not be opened."
                ) from exc
        for page in reader.pages:
            writer.add_page(page)

        if progress_callback:
            progress_callback(index, total)

    with output.open("wb") as handle:
        writer.write(handle)

    return output


def merge_docx(
    input_paths: list[Path],
    output: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """Merge DOCX files in the supplied order, preserving common Word content."""
    if not input_paths:
        raise ValueError("At least one DOCX file is required.")

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    # docxcompose is used because directly copying XML between documents
    # can break relationships for images, headers, numbering and other parts.
    master = Document(str(input_paths[0]))
    composer = Composer(master)

    total = len(input_paths)
    if progress_callback:
        progress_callback(1, total)

    for index, path in enumerate(input_paths[1:], 2):
        composer.append(Document(str(path)))
        if progress_callback:
            progress_callback(index, total)

    composer.save(str(output))
    return output
