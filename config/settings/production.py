"""Settings for the live server (Render). DEBUG is always off here."""

from .base import *
from .base import env

DEBUG = False

# Render sets this to the service's own address, e.g. bauhelfer.onrender.com.
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, RENDER_EXTERNAL_HOSTNAME]

# One line per request in Render's logs (#137, docs/specs/request-logging.md). Right after
# WhiteNoise, so static files never reach it. A new list: base's is shared with local.py,
# where runserver prints its own request lines (D6).
_after_whitenoise = MIDDLEWARE.index("whitenoise.middleware.WhiteNoiseMiddleware") + 1
MIDDLEWARE = [
    *MIDDLEWARE[:_after_whitenoise],
    "config.middleware.RequestLogMiddleware",
    *MIDDLEWARE[_after_whitenoise:],
]

STORAGES = {
    # Uploaded photos (#64): a Supabase Storage bucket through its S3 protocol, because the
    # Render disk is wiped on every deploy (docs/specs/job-photos.md D2). Every value is
    # required: without one the server does not start, instead of writing photos to a disk
    # that loses them (D31). Values in Supabase: Storage -> Settings -> S3 Connection.
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": env("MEDIA_S3_ENDPOINT_URL"),
            "region_name": env("MEDIA_S3_REGION"),
            "access_key": env("MEDIA_S3_ACCESS_KEY_ID"),
            "secret_key": env("MEDIA_S3_SECRET_ACCESS_KEY"),
            "bucket_name": env("MEDIA_S3_BUCKET"),
            # The bucket is public (D30): photos get a fixed address the browser can cache,
            # on Supabase's public path. With custom_domain django-storages builds plain
            # URLs, never signed ones that expire. It adds "https://" itself, so one copied
            # with it (or with a "/" at the end) is trimmed: "https://https://…" would break
            # every photo without any error.
            "custom_domain": env("MEDIA_PUBLIC_URL")
            .removeprefix("https://")
            .rstrip("/"),
            # Supabase wants the bucket in the path (…/s3/job-photos/…), not in the host.
            "addressing_style": "path",
            # Names are random already; never replace a stored file by accident.
            "file_overwrite": False,
        },
    },
    # Compressed copies and a content hash in each file name (style.3f9a1c.css), so browsers
    # can cache static files for a long time. Needs collectstatic, which only runs on the
    # server.
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Render terminates HTTPS in front of the app and tells Django via this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600  # raise once HTTPS is confirmed working
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
