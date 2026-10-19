"""Unit tests: checking and preparing an uploaded job photo, prepare_photo() (#64).

Spec: docs/specs/job-photos.md, iteration 1 (R4-R5, AC1-AC7, D3-D5). No database: the
function gets a file and returns a file.
"""

import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import ExifTags, Image

from jobs.photos import prepare_photo
from jobs.tests.images import camera_exif, make_upload

pytestmark = [pytest.mark.story(64)]


def open_result(photo):
    """The picture inside the file prepare_photo() returned."""
    photo.seek(0)
    return Image.open(photo)


# Accepted formats (R4, AC1, D5)


@pytest.mark.parametrize("image_format", ["JPEG", "PNG", "WEBP"])
def test_accepted_formats_come_back_as_jpeg(image_format):
    """A JPEG, PNG or WebP photo is accepted and stored as JPEG.

    1. Prepare a small picture in the given format
    2. Expect: no error, and the result is a JPEG
    """
    photo = prepare_photo(make_upload(image_format))

    assert open_result(photo).format == "JPEG"


@pytest.mark.story(21)
@pytest.mark.parametrize("mode", ["RGBA", "P"])
def test_png_with_transparency_or_palette_comes_back_as_jpeg(mode):
    """A PNG with transparency or a colour palette becomes a plain RGB JPEG.

    JPEG has neither, so Pillow cannot save such a picture as JPEG without converting it
    first; the PNG in the test above is plain RGB and never reaches the conversion.

    1. Prepare a PNG in the given mode (RGBA: with transparency, P: with a palette)
    2. Expect: no error, and the result is an RGB JPEG
    """
    buffer = io.BytesIO()
    Image.new(mode, (300, 200)).save(buffer, "PNG")

    photo = prepare_photo(SimpleUploadedFile("logo.png", buffer.getvalue()))

    result = open_result(photo)
    assert (result.format, result.mode) == ("JPEG", "RGB")


# Refused files (R4, AC2-AC4, D4)


def test_text_file_named_jpg_is_refused():
    """A text file with a .jpg name is not a photo.

    1. Prepare a file named photo.jpg that holds text
    2. Expect: ValidationError with the code "invalid_image"
    """
    upload = SimpleUploadedFile("photo.jpg", b"this is not a picture")

    with pytest.raises(ValidationError) as error:
        prepare_photo(upload)

    assert error.value.code == "invalid_image"


def test_gif_is_refused():
    """A real picture in a format we do not take (GIF) is refused.

    1. Prepare a GIF named photo.jpg
    2. Expect: ValidationError with the code "invalid_image"
    """
    with pytest.raises(ValidationError) as error:
        prepare_photo(make_upload("GIF"))

    assert error.value.code == "invalid_image"


def test_file_over_5_mb_is_refused():
    """A file over 5 MB is refused before it is opened, and the message names the limit.

    1. Prepare a file of 5 MB + 1 byte (its content does not matter)
    2. Expect: ValidationError with the code "too_large" and "5 MB" in the message
    """
    upload = SimpleUploadedFile("big.jpg", b"x" * (5 * 1024 * 1024 + 1))

    with pytest.raises(ValidationError) as error:
        prepare_photo(upload)

    assert error.value.code == "too_large"
    assert "5 MB" in str(error.value.message)


# Pillow warns about the picture before prepare_photo() refuses it; expected here.
@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_picture_over_pixel_limit_is_refused(monkeypatch):
    """A small file that unpacks to too many pixels ("decompression bomb") is refused.

    1. Lower Pillow's pixel limit to 10,000 for this test
    2. Prepare a 150 × 100 picture (15,000 pixels: over the limit, under twice the limit,
       where Pillow only warns)
    3. Expect: ValidationError with the code "too_many_pixels"
    """
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10_000)

    with pytest.raises(ValidationError) as error:
        prepare_photo(make_upload("PNG", size=(150, 100)))

    assert error.value.code == "too_many_pixels"


@pytest.mark.story(21)
def test_picture_over_twice_the_pixel_limit_is_refused(monkeypatch):
    """Over twice the pixel limit Pillow refuses to open the file; the user gets our message.

    1. Lower Pillow's pixel limit to 10,000 for this test
    2. Prepare a 150 × 150 picture (22,500 pixels: over twice the limit, where Pillow raises
       DecompressionBombError instead of warning)
    3. Expect: ValidationError with the code "too_many_pixels", not Pillow's error
    """
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10_000)

    with pytest.raises(ValidationError) as error:
        prepare_photo(make_upload("PNG", size=(150, 150)))

    assert error.value.code == "too_many_pixels"


@pytest.mark.story(21)
def test_cut_off_file_is_refused():
    """A JPEG cut off in the middle (a broken upload) is refused with our message.

    Its header is fine, so Image.open() accepts it; the missing pixels show up only when
    the picture is read for resizing.

    1. Prepare a JPEG and keep only the first half of its bytes
    2. Expect: ValidationError with the code "invalid_image", not Pillow's OSError
    """
    data = make_upload(size=(800, 600)).read()
    upload = SimpleUploadedFile("photo.jpg", data[: len(data) // 2])

    with pytest.raises(ValidationError) as error:
        prepare_photo(upload)

    assert error.value.code == "invalid_image"


# Resizing (R5, AC5)


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((4000, 3000), (1600, 1200)),  # landscape: the width is the long side
        ((3000, 4000), (1200, 1600)),  # portrait: the height is the long side
        ((800, 600), (800, 600)),  # small: not enlarged
    ],
)
def test_long_side_at_most_1600(size, expected):
    """The long side is shrunk to 1600 px with the same proportions; small ones stay.

    1. Prepare a JPEG of the given size
    2. Expect: the expected size
    """
    photo = prepare_photo(make_upload(size=size))

    assert open_result(photo).size == expected


# EXIF (R5, AC6, AC7)


def test_exif_is_removed():
    """GPS position, camera model and every other EXIF tag are gone.

    1. Prepare a JPEG with GPS and camera EXIF
    2. Expect: the result has no EXIF at all
    """
    photo = prepare_photo(make_upload(exif=camera_exif()))

    assert dict(open_result(photo).getexif()) == {}


def test_photo_on_its_side_is_turned_upright():
    """A phone photo saved lying down with "rotate 90°" in EXIF comes back upright.

    1. Prepare a 300 × 200 JPEG with EXIF orientation 6 (turn 90° clockwise to view)
    2. Expect: 200 × 300 (width and height swapped) and no EXIF orientation left
    """
    photo = prepare_photo(make_upload(exif=camera_exif(orientation=6)))

    result = open_result(photo)
    assert result.size == (200, 300)
    assert ExifTags.Base.Orientation not in result.getexif()
