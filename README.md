# FileForge 3.2.0 — PDF & Document Toolbox

A polished Windows desktop utility for everyday image, PDF and Word-document work.

## What it can do

### Images

- Images → PDF
- Batch image conversion: JPG / PNG / WebP
- Folder import
- Thumbnail preview
- Drag/reorder
- Rotate
- A4 / Letter / original-size PDF pages
- Quality controls
- EXIF orientation handling

### PDF Toolbox

- Merge multiple PDFs into one
- Split a PDF into one PDF per page
- Extract selected page ranges
- Delete selected pages
- Rotate all pages
- Reorder pages
- Lossless structural compression
- PDF → PNG/JPG images
- PDF → DOCX text extraction
- PDF metadata: page count and size shown in the file list

### Word

- Merge multiple DOCX files into one
- DOCX → PDF through locally installed LibreOffice

### Convenience

- Dark mode
- Recent outputs
- Open output / open containing folder
- Drag-and-drop ordering, including dropping supported files onto the application window
- Overwrite protection
- Batch operations
- Local/offline processing

## Important conversion limitation

`PDF → DOCX` is provided as **text extraction**, not a promise of perfect Word layout reconstruction. Complex PDFs containing columns, scanned pages, forms, vector artwork or unusual positioning may not reproduce accurately.

`DOCX → PDF` uses LibreOffice locally. FileForge does not upload the document.

## Privacy

FileForge processes documents locally and does not require a cloud service.

The application does not intentionally collect telemetry, credentials or browser data and does not start a network listener.

## Security

No desktop application can honestly be guaranteed "100% virus-free." Release builds should be scanned with your antivirus and distributed with SHA-256 checksums.

The application uses explicit file extensions, local libraries and no shell command execution except the optional, user-invoked LibreOffice conversion. That conversion uses `shell=False`.

## Run

Install the requirements:

    py -m pip install -r requirements.txt

Set the source directory:

    $env:PYTHONPATH="src"

Run FileForge:

    py src\app.py

Or use:

    run.bat

## Build Windows EXE

Run:

    build.bat

The build creates:

    dist\FileForge.exe

## PDF → Images

PDF page rendering uses PyMuPDF and is included in the default requirements.

## Optional DOCX → PDF

Install LibreOffice separately and ensure it is installed in one of the standard Windows locations or that `soffice` is available on PATH.

## Tests

Install the development dependencies:

    py -m pip install -r requirements-dev.txt

Run the test suite:

    py -m pytest

Run the dependency security audit:

    py -m pip_audit

The project also runs automated tests through GitHub Actions across supported Python versions.

## License

MIT. See `LICENSE`.

Third-party packages retain their own licenses. See `THIRD_PARTY_NOTICES.md`.

## Compatibility

FileForge uses `docxcompose 2.2.0` and a modern setuptools version for compatibility with current Python environments.

## Word Merger

The Word Merger supports a professional multi-file workflow:

- Add multiple DOCX files at once.
- Add files one at a time from different folders.
- Drag and drop DOCX files into the list.
- Reorder documents with Move Up / Move Down.
- Remove selected files or clear the list.
- Duplicate file paths are ignored automatically.
- Choose the final merged DOCX output location.

## History UX

History actions are disabled until an output is selected, and missing outputs/folders now show a clear warning instead of doing nothing.

## Image Tools 3.2

- Batch image conversion: JPG, PNG and WebP.
- Safe PNG/alpha handling when converting to JPG.
- Collision-safe output names (`_2`, `_3`, ...).
- Image compression with High Quality, Balanced and Maximum Compression modes.
- Optional compression output format: Keep original, JPG, PNG or WebP.
- Image resizing with high-quality Lanczos resampling and aspect-ratio preservation.

## About

A fast, private, offline desktop toolbox for images, PDFs and Word documents.
