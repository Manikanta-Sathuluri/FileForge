from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp",
    ".tif", ".tiff", ".avif"
}

MAX_IMAGES = 500
MAX_PIXELS_PER_IMAGE = 100_000_000


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def collect_images(folder: Path, recursive: bool = True) -> list[Path]:
    """Return supported image files in stable alphabetical order."""
    if not folder.is_dir():
        raise ValueError(f"Not a folder: {folder}")

    iterator: Iterable[Path] = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(
        (p.resolve() for p in iterator if is_supported_image(p)),
        key=lambda p: str(p).lower(),
    )


def open_safe(path: Path) -> Image.Image:
    """Open a local image with basic resource limits and EXIF orientation."""
    img = Image.open(path)
    if img.width <= 0 or img.height <= 0:
        raise ValueError("Image has invalid dimensions.")
    if img.width * img.height > MAX_PIXELS_PER_IMAGE:
        raise ValueError(
            f"Image is too large ({img.width}x{img.height}). "
            f"Maximum is {MAX_PIXELS_PER_IMAGE:,} pixels."
        )
    return ImageOps.exif_transpose(img)


def make_page(
    image: Image.Image,
    page_size: tuple[int, int] | None,
    fit_to_page: bool = True,
) -> Image.Image:
    """Convert one source image into an RGB PDF page."""
    img = image.convert("RGB")

    if not page_size:
        return img

    page_w, page_h = page_size

    if fit_to_page:
        ratio = min(page_w / img.width, page_h / img.height)
        new_size = (
            max(1, int(img.width * ratio)),
            max(1, int(img.height * ratio)),
        )
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", page_size, "white")
        canvas.paste(
            img,
            ((page_w - new_size[0]) // 2, (page_h - new_size[1]) // 2),
        )
        return canvas

    img.thumbnail(page_size, Image.Resampling.LANCZOS)
    return img


def create_pdf(
    image_paths: list[Path],
    output: Path,
    page_size: tuple[int, int] | None = None,
    fit_to_page: bool = True,
    jpeg_quality: int = 92,
    rotations: dict[Path, int] | None = None,
    progress_callback=None,
) -> Path:
    """Create one PDF from ordered local image paths."""
    if not image_paths:
        raise ValueError("At least one image is required.")

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    quality = max(40, min(100, int(jpeg_quality)))
    rotations = rotations or {}
    pages: list[Image.Image] = []

    for index, path in enumerate(image_paths):
        img = open_safe(path)
        rotation = rotations.get(path, 0) % 360
        if rotation:
            img = img.rotate(rotation, expand=True)

        pages.append(make_page(img, page_size, fit_to_page))

        if progress_callback:
            progress_callback(index + 1, len(image_paths))

    pages[0].save(
        output,
        "PDF",
        resolution=100.0,
        save_all=True,
        append_images=pages[1:],
        quality=quality,
    )
    return output
