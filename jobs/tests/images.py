"""Test pictures made in memory with Pillow, for the job photo tests (#64).

Not a test file (no `test_` prefix): the tests import `make_upload` from here.
"""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import ExifTags, Image


def make_upload(
    image_format="JPEG", size=(300, 200), exif=None, name="photo.jpg"
) -> SimpleUploadedFile:
    """A file as Django gets it from a form: a one-colour picture in `image_format`.

    `exif` is a Pillow `Image.Exif` to write into the file (JPEG and WebP only).
    """
    buffer = io.BytesIO()
    extra = {"exif": exif.tobytes()} if exif is not None else {}
    Image.new("RGB", size, "orange").save(buffer, image_format, **extra)
    return SimpleUploadedFile(name, buffer.getvalue())


def camera_exif(orientation=None) -> Image.Exif:
    """EXIF like a phone writes it: camera model, GPS position, optionally orientation."""
    exif = Image.Exif()
    exif[ExifTags.Base.Model] = "TestPhone 12"
    # Marienplatz, Munich: the place where the photo was taken.
    exif[ExifTags.IFD.GPSInfo] = {
        ExifTags.GPS.GPSLatitudeRef: "N",
        ExifTags.GPS.GPSLatitude: (48.0, 8.0, 0.0),
        ExifTags.GPS.GPSLongitudeRef: "E",
        ExifTags.GPS.GPSLongitude: (11.0, 34.0, 0.0),
    }
    if orientation is not None:
        exif[ExifTags.Base.Orientation] = orientation
    return exif
