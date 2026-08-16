from pathlib import Path

from PIL import Image

from src.pdf_generator import (
    MAX_PIXELS_PER_IMAGE,
    collect_images,
    create_pdf,
    is_supported_image,
    make_page,
)


def test_supported_extensions(tmp_path):
    good = tmp_path / "photo.JPG"
    bad = tmp_path / "notes.txt"
    good.write_bytes(b"x")
    bad.write_bytes(b"x")
    assert is_supported_image(good)
    assert not is_supported_image(bad)


def test_collect_images_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    Image.new("RGB", (10, 10), "white").save(tmp_path / "a.jpg")
    Image.new("RGB", (10, 10), "white").save(tmp_path / "sub" / "b.png")
    assert len(collect_images(tmp_path, recursive=True)) == 2


def test_make_a4_page():
    image = Image.new("RGB", (100, 100), "white")
    page = make_page(image, (595, 842), True)
    assert page.size == (595, 842)


def test_create_pdf(tmp_path):
    first = tmp_path / "1.png"
    second = tmp_path / "2.png"
    Image.new("RGB", (50, 50), "white").save(first)
    Image.new("RGB", (50, 50), "black").save(second)

    output = tmp_path / "out.pdf"
    create_pdf([first, second], output)
    assert output.exists()
    assert output.stat().st_size > 0
