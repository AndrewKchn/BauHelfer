# Spec: request lines in production logs (#137)

Status: **agreed**. I decided the questions on 2026-10-20, before any tests.

## Goal

Render's logs show one short line per request (method, path, status, time), so I can see
what happens on the live site. The lines hold no personal data and never a password reset
token, and Render's health check does not fill the logs.

Today Render turns on gunicorn's access log by default (`GUNICORN_CMD_ARGS` =
`--preload --access-logfile - --bind=0.0.0.0:10000`): every request, the health check every
5 seconds included, is a line with the full path, the browser's User-Agent and the Referer.

## Requirements

R1. `render.yaml` sets `GUNICORN_CMD_ARGS` itself: `--preload --bind=0.0.0.0:10000`, the
    platform default without `--access-logfile` (D1). gunicorn writes no access log.
R2. A middleware `config.middleware.RequestLogMiddleware` logs one INFO line per request
    after the response: `<METHOD> <path> <status> <ms>ms`, e.g. `GET /jobs/42/ 200 35ms` (D2).
R3. The path is `request.path`: no query string, no host (D5).
R4. For the password reset link (`url_name` `password_reset_confirm`) the URL pattern is
    logged instead of the path: `/accounts/reset/<uidb64>/<token>/`. This covers the link
    from the email and Django's redirect to `…/set-password/` (D3).
R5. A request whose User-Agent starts with `Render/` (the health check) is answered as
    before but not logged (D4).
R6. The middleware is added in `production.py` only, right after WhiteNoise, so static
    files are not logged and every page, redirects included, is (D6).
R7. The logger is `config.middleware`; `LOGGING` gives the `config` logger level INFO.

## Out of scope

- A separate health check path without the database (H2): rejected, see D4.
- The visitor's IP (`X-Forwarded-For`): not logged.
- Log retention and search: Render's free plan keeps logs for a limited time; not changed.

## Acceptance criteria (→ tests)

AC1. `GUNICORN_CMD_ARGS` in `render.yaml`, parsed by gunicorn's own argument parser, has no
     access log and binds to `0.0.0.0:10000`.
AC2. A GET to a page logs one INFO record from `config.middleware` with method, path,
     status and time.
AC3. A POST that redirects logs `POST <path> 302 …`.
AC4. A 404 is logged with its status.
AC5. A path with a query string is logged without it.
AC6. The password reset link and its `set-password` redirect are logged as
     `/accounts/reset/<uidb64>/<token>/`; the real uid and token are in no record.
AC7. A request with User-Agent `Render/1.0` logs nothing from `config.middleware`.
AC8. No line holds the User-Agent or the Referer sent with the request.
AC9. `production.py` has the middleware right after WhiteNoise; `local.py` does not have it.
AC10. A request for a static file logs nothing from `config.middleware`.

## Limitations (for docs/SECURITY.md)

- Anyone can send the User-Agent `Render/1.0`; such requests are not logged. Our own events
  (#124) and Django's 4xx/5xx warnings are still logged for them.
- Paths with ids (`/jobs/42/`) are logged as they are: job ids are not personal data.
- A path that matches no URL (404) is logged as sent, whatever a visitor typed into it.

## Decisions (me, 2026-10-20)

My criteria: informative lines, no noise from the health check, no personal data, never a
reset token. Each question was offered with options, their cost and a recommendation.

D1. **gunicorn's access log is off; `render.yaml` sets the gunicorn arguments.** Setting
    `GUNICORN_CMD_ARGS` replaces Render's value whole, so `--bind` and `--preload` are
    written out again. Rejected: keep the default format (User-Agent, Referer, token).
    Revisit when Render changes its port or its default arguments.
D2. **Django middleware writes the request line (C), not gunicorn (B).** Same format and
    `LOGGING` as our events from #124, tested with the Django test client, and Django knows
    which URL pattern matched. Rejected: B, gunicorn's `--access-logformat` and our own
    logger class (a regex copy of the reset URL, a line per static file, a second line
    format, code that runs only under gunicorn); A, no request lines at all (not
    informative). Revisit when a request can fail before Django (a gunicorn timeout) and
    we need to see it.
D3. **Hide the reset link by URL name, not by a pattern on the path.** If the URL in
    `accounts/urls.py` changes, the mask keeps working. Revisit when another URL carries a
    secret or personal data: add its name to the set.
D4. **The health check stays on `/`, only its lines are skipped (H3, my idea).** It keeps
    checking the page and the database; 3 queries every 5 seconds are no problem for
    Supabase's free plan. Rejected: H1, no health check (Render would switch to a broken
    version); H2, a `/health/` page without the database (more code, misses a dead
    database). Revisit when the database load matters or someone hides requests behind
    the `Render/` User-Agent.
D5. **No query string.** Search filters are not needed in the log, and a query string could
    carry anything. Revisit when we need to see which filters people use.
D6. **Production only, right after WhiteNoise.** Locally `runserver` prints its own request
    lines; a second one would be a duplicate. Revisit when we stop using `runserver`.
