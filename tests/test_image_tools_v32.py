
from pathlib import Path
from PIL import Image
from image_tools import convert_images, compress_images, resize_images


def test_png_to_jpg_transparency(tmp_path):
    src = tmp_path / "transparent.png"
    Image.new("RGBA", (100, 80), (255, 0, 0, 128)).save(src)
    out = convert_images([src], tmp_path / "out", "JPG")
    assert out and out[0].suffix == ".jpg"
    with Image.open(out[0]) as im:
        assert im.format == "JPEG"
        assert im.mode == "RGB"


def test_compress_webp(tmp_path):
    src = tmp_path / "photo.png"
    Image.new("RGB", (400, 300), "white").save(src)
    out = compress_images([src], tmp_path / "compressed", "Balanced", "WEBP")
    assert out and out[0].exists()


def test_resize_keeps_aspect_ratio(tmp_path):
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (400, 200), "blue").save(src)
    out = resize_images([src], tmp_path / "resized", 100, 100, True)
    with Image.open(out[0]) as im:
        assert im.size == (100, 50)
