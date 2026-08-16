from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageOps

SUPPORTED_IMAGES = {
    ".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".tif", ".tiff", ".avif"
}


def _flatten_for_jpeg(image: Image.Image, background=(255, 255, 255)) -> Image.Image:
    """Safely convert any transparency/palette image to RGB for JPEG."""
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or ("transparency" in image.info):
        rgba = image.convert("RGBA")
        bg = Image.new("RGB", rgba.size, background)
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    if image.mode == "P":
        # Palette images may contain transparency; convert through RGBA when present.
        if "transparency" in image.info:
            rgba = image.convert("RGBA")
            bg = Image.new("RGB", rgba.size, background)
            bg.paste(rgba, mask=rgba.getchannel("A"))
            return bg
        return image.convert("RGB")
    return image.convert("RGB")


def _output_ext(fmt: str) -> str:
    f = fmt.upper()
    return ".jpg" if f in {"JPG", "JPEG"} else f".{f.lower()}"


def _unique_output(output_dir: Path, stem: str, ext: str) -> Path:
    out = output_dir / f"{stem}{ext}"
    if not out.exists():
        return out
    n = 2
    while True:
        candidate = output_dir / f"{stem}_{n}{ext}"
        if not candidate.exists():
            return candidate
        n += 1


def convert_images(paths: list[Path], output_dir: Path, fmt: str, quality: int = 92):
    """Convert images reliably across JPG/PNG/WEBP, including transparent PNGs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fmt = fmt.upper()
    if fmt not in {"JPG", "JPEG", "PNG", "WEBP"}:
        raise ValueError(f"Unsupported output format: {fmt}")

    ext = _output_ext(fmt)
    created = []

    for path in paths:
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original)

            if fmt in {"JPG", "JPEG"}:
                image = _flatten_for_jpeg(image)
                save_kwargs = {"quality": max(1, min(100, int(quality))), "optimize": True, "progressive": True}
                save_format = "JPEG"
            elif fmt == "PNG":
                # Preserve alpha where present; avoid palette/CMYK incompatibilities.
                if image.mode not in ("RGB", "RGBA", "L", "LA"):
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                save_kwargs = {"optimize": True, "compress_level": 9}
                save_format = "PNG"
            else:  # WEBP
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                save_kwargs = {"quality": max(1, min(100, int(quality))), "method": 6}
                save_format = "WEBP"

            out = _unique_output(output_dir, path.stem, ext)
            image.save(out, format=save_format, **save_kwargs)
            created.append(out)

    return created


def compress_images(
    paths: list[Path],
    output_dir: Path,
    mode: str = "Balanced",
    output_format: str = "Keep original",
):
    """
    Compress images.

    Balanced / High Quality / Maximum Compression map to sensible quality levels.
    JPG/WebP can use lossy quality; PNG remains lossless when kept as PNG.
    """
    quality = {
        "High Quality": 88,
        "Balanced": 76,
        "Maximum Compression": 55,
    }.get(mode, 76)

    output_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for path in paths:
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original)
            source = path.suffix.lower()

            if output_format == "Keep original":
                if source in {".jpg", ".jpeg", ".jfif"}:
                    fmt = "JPG"
                elif source == ".png":
                    fmt = "PNG"
                elif source == ".webp":
                    fmt = "WEBP"
                else:
                    fmt = "WEBP"
            else:
                fmt = output_format.upper()

            if fmt == "JPG":
                image = _flatten_for_jpeg(image)
                kwargs = {"quality": quality, "optimize": True, "progressive": True}
                save_format = "JPEG"
            elif fmt == "PNG":
                if image.mode not in ("RGB", "RGBA", "L", "LA"):
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                kwargs = {"optimize": True, "compress_level": 9}
                save_format = "PNG"
            elif fmt == "WEBP":
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                kwargs = {"quality": quality, "method": 6}
                save_format = "WEBP"
            else:
                raise ValueError(f"Unsupported compression format: {fmt}")

            out = _unique_output(output_dir, path.stem + "_compressed", _output_ext(fmt))
            image.save(out, format=save_format, **kwargs)
            created.append(out)

    return created


def resize_images(
    paths: list[Path],
    output_dir: Path,
    width: int,
    height: int,
    keep_aspect: bool = True,
    mode: str = "Fit within",
):
    """Resize images safely with high-quality Lanczos resampling."""
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be greater than zero.")

    output_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for path in paths:
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original)

            if keep_aspect:
                if mode == "Percentage":
                    raise ValueError("Percentage mode requires the percentage UI path.")
                image.thumbnail((width, height), Image.Resampling.LANCZOS)
            else:
                image = image.resize((width, height), Image.Resampling.LANCZOS)

            # Keep the source format where practical; normalize unsupported modes.
            fmt = (original.format or path.suffix.lstrip(".")).upper()
            if fmt == "JPG":
                fmt = "JPEG"
            if fmt not in {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}:
                fmt = "PNG"

            if fmt == "JPEG":
                image = _flatten_for_jpeg(image)
                kwargs = {"quality": 92, "optimize": True}
            elif fmt == "PNG":
                if image.mode not in ("RGB", "RGBA", "L", "LA"):
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                kwargs = {"optimize": True, "compress_level": 9}
            elif fmt == "WEBP":
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                kwargs = {"quality": 92, "method": 6}
            else:
                kwargs = {}

            ext = ".jpg" if fmt == "JPEG" else f".{fmt.lower()}"
            out = _unique_output(output_dir, path.stem + "_resized", ext)
            image.save(out, format=fmt, **kwargs)
            created.append(out)

    return created
