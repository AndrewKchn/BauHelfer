"""Checking and preparing a job photo before it is stored (#64, docs/specs/job-photos.md).

Every form that takes a photo calls prepare_photo() (D3): the admin now, the job form later.
"""

import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_LONG_SIDE = 1600  # pixels
# Pillow's names, read from the file's content (D4).
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Pillow's default is 75; 85 keeps fine detail (cracks, debris) with hardly visible loss (D5).
JPEG_QUALITY = 85

INVALID_IMAGE = _("Upload a photo in JPEG, PNG or WebP format.")
TOO_MANY_PIXELS = _("This picture has too many pixels. Please upload a normal photo.")


def prepare_photo(file):
    """Check an uploaded photo and return it resized, upright, as a JPEG without EXIF.

    Raises ValidationError (codes "too_large", "invalid_image", "too_many_pixels") with a
    message for the user. The returned file is new; the uploaded one is not changed.
    """
    # The size is known before the file is read, so a huge file is never opened.
    if file.size > MAX_PHOTO_BYTES:
        raise ValidationError(_("A photo can be at most 5 MB."), code="too_large")

    file.seek(0)
    try:
        # open() reads only the header: format and size, not the pixels yet.
        image = Image.open(file)
    except Image.DecompressionBombError:
        # Pillow itself refuses more than twice its limit.
        raise ValidationError(TOO_MANY_PIXELS, code="too_many_pixels") from None
    except (UnidentifiedImageError, OSError):
        raise ValidationError(INVALID_IMAGE, code="invalid_image") from None

    # The format from the content: a text file named photo.jpg has none Pillow knows, a GIF
    # named photo.jpg says "GIF".
    if image.format not in ALLOWED_FORMATS:
        raise ValidationError(INVALID_IMAGE, code="invalid_image")
    # Between its limit and twice the limit Pillow only warns; a "decompression bomb" (a
    # small file that unpacks to a gigantic picture) is refused before the pixels are read.
    # Read on every call, so a test can lower the limit.
    if image.width * image.height > Image.MAX_IMAGE_PIXELS:
        raise ValidationError(TOO_MANY_PIXELS, code="too_many_pixels")

    try:
        # Shrink first: for a JPEG, Pillow then decodes straight at a smaller scale, which
        # keeps memory low on the 512 MB free server. The box is square, so turning the
        # picture afterwards cannot make it larger than 1600 px. Smaller ones stay as they
        # are.
        image.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE))
        # Phones save a portrait photo lying on its side plus a "rotate" note in EXIF; turn
        # it upright now, because the note goes away with the EXIF below.
        image = ImageOps.exif_transpose(image)
    except OSError:  # a file cut off in the middle: the header was fine, the pixels not
        raise ValidationError(INVALID_IMAGE, code="invalid_image") from None

    # JPEG has no transparency and no palette: PNGs and WebPs become plain RGB.
    if image.mode != "RGB":
        image = image.convert("RGB")

    output = io.BytesIO()
    # No exif= argument: Pillow writes no EXIF at all (no GPS, camera, date). The colour
    # profile is kept, it holds nothing personal and phone photos look wrong without it.
    image.save(
        output,
        "JPEG",
        quality=JPEG_QUALITY,
        icc_profile=image.info.get("icc_profile"),
    )
    # The name is replaced by job_photo_path() when the photo is saved.
    return ContentFile(output.getvalue(), name="photo.jpg")
