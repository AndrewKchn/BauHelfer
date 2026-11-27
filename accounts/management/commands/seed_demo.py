"""`manage.py seed_demo`: demo data for the defense and for mentors (#47).

Spec: docs/specs/demo-data.md. Deletes every account on @demo.example with everything that
hangs on it, then creates 3 employers, 5 workers, open jobs ahead and done jobs with reviews.
Run it again to reset the demo data; no other account is touched (D3).

On the live site it runs from my computer with the production database address (D1):

    DATABASE_URL='<Supabase URL>' uv run python manage.py seed_demo

It sends no email and translates nothing (D6, D13), so the local settings it runs with
cannot leak into the live site. Photos only go into a database on this computer: with the
local settings their files land on this disk, which the live site cannot see (D17).
"""

import datetime
import getpass
import io
from decimal import Decimal
from typing import override

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from accounts.models import EmployerProfile, User, WorkerProfile
from jobs.models import Application, Job, JobPhoto
from reviews.models import Review

# Reserved for examples (RFC 2606): no mail can reach it, and the local dev users on
# @example.com are not deleted with the demo accounts (D10).
DOMAIN = "demo.example"

DAY = datetime.timedelta(days=1)

# Database hosts that mean "this computer" (D17); empty = a local socket.
LOCAL_HOSTS = {"", "localhost", "127.0.0.1"}

# The demo accounts (R3, D4). "key" is the part of the address before the @.
EMPLOYERS = [
    {
        "key": "thomas.berger",
        "name": "Thomas Berger",
        "language": "de",
        "company_name": "",  # a private person
        "trades": ["private_person"],
    },
    {
        "key": "ewa.nowak",
        "name": "Ewa Nowak",
        "language": "pl",
        "company_name": "Nowak Renovierung",
        "trades": ["drywall", "painting", "plastering"],
    },
    {
        "key": "sergej.wolf",
        "name": "Sergej Wolf",
        "language": "ru",
        "company_name": "Wolf Abbruch GmbH",
        "trades": ["demolition", "general_contractor"],
    },
]

WORKERS = [
    {
        "key": "lukas.bauer",
        "name": "Lukas Bauer",
        "language": "de",
        "team_size": 1,
        "skills": ["carrying", "site_cleaning"],
        "languages": ["de", "en"],
        "legal_status": "minijob",
    },
    {
        "key": "andrei.popescu",
        "name": "Andrei Popescu",
        "language": "ro",
        "team_size": 3,  # a crew: Andrei and two more
        "skills": ["demolition", "debris_clearing", "earthworks"],
        "languages": ["ro", "en", "de"],
        "legal_status": "gewerbe",
    },
    {
        "key": "taras.melnyk",
        "name": "Taras Melnyk",
        "language": "uk",
        "team_size": 1,
        "skills": ["drywall", "painting", "plastering"],
        "languages": ["uk", "ru", "de"],
        "legal_status": "gewerbe",
    },
    {
        "key": "piotr.wisniewski",
        "name": "Piotr Wiśniewski",
        "language": "pl",
        "team_size": 1,
        "skills": ["masonry", "scaffolding", "plastering"],
        "languages": ["pl", "de"],
        "legal_status": "employed",
    },
    {
        "key": "emre.demir",
        "name": "Emre Demir",
        "language": "tr",
        "team_size": 1,
        "skills": ["demolition", "carrying"],
        "languages": ["tr", "de"],
        "legal_status": "gewerbe",
    },
]

# Open jobs; "days" counts from the day the command runs (D8); "photos" are the scenes of
# the drawn photos, made only locally (D17). The rest are Job fields.
OPEN_JOBS = [
    {
        "employer": "thomas.berger",
        "days": 1,
        "job_type": "demolition",
        "district": "pasing_obermenzing",
        "start_time": "08:00",
        "hours": 5,
        "workers_needed": 2,
        "hourly_rate": "16.00",
        "original_language": "de",
        "photos": ["shed", "skip"],
        "description": (
            "Gartenhaus aus Holz abreißen und den Schutt in den Container laden. "
            "Werkzeug ist da, bitte Arbeitshandschuhe mitbringen."
        ),
    },
    {
        "employer": "thomas.berger",
        "days": 3,
        "job_type": "carrying",
        "district": "schwabing_west",
        "start_time": "09:00",
        "hours": 4,
        "workers_needed": 2,
        "hourly_rate": "15.00",
        "original_language": "en",
        "description": (
            "Carry 40 bags of plaster from the courtyard to the third floor. "
            "There is no lift."
        ),
    },
    {
        "employer": "ewa.nowak",
        "days": 2,
        "job_type": "drywall",
        "district": "maxvorstadt",
        "start_time": "07:30",
        "hours": 8,
        "workers_needed": 1,
        "hourly_rate": "17.50",
        "original_language": "pl",
        "description": (
            "Pomoc przy montażu płyt gipsowo-kartonowych w mieszkaniu. "
            "Doświadczenie mile widziane."
        ),
    },
    {
        "employer": "ewa.nowak",
        "days": 4,
        "job_type": "painting",
        "district": "au_haidhausen",
        "start_time": "08:00",
        "hours": 6,
        "workers_needed": 2,
        "hourly_rate": "16.50",
        "original_language": "de",
        "photos": ["painting"],
        "description": (
            "Wände abkleben, Böden abdecken und nach dem Streichen aufräumen. "
            "Wohnung im 2. Stock."
        ),
    },
    {
        "employer": "ewa.nowak",
        "days": 6,
        "job_type": "site_cleaning",
        "district": "bogenhausen",
        "start_time": "09:00",
        "hours": 5,
        "workers_needed": 3,
        "hourly_rate": "15.00",
        "original_language": "pl",
        "description": (
            "Sprzątanie mieszkania po remoncie: kurz, folie, resztki materiałów. "
            "Środki czystości zapewniamy."
        ),
    },
    {
        "employer": "sergej.wolf",
        "days": 1,
        "job_type": "demolition",
        "district": "sendling",
        "start_time": "07:00",
        "hours": 8,
        "workers_needed": 4,
        "hourly_rate": "18.00",
        "original_language": "ru",
        "photos": ["tiles", "broken_tiles"],
        "description": (
            "Демонтаж старой кухни и плитки в ресторане. "
            "Нужна бригада, отбойные молотки предоставим."
        ),
    },
    {
        "employer": "sergej.wolf",
        "days": 5,
        "job_type": "debris_clearing",
        "district": "laim",
        "start_time": "07:30",
        "hours": 6,
        "workers_needed": 3,
        "hourly_rate": "16.00",
        "original_language": "ru",
        "description": (
            "Вынос строительного мусора из подвала и погрузка в контейнер. "
            "Обязательна защитная обувь."
        ),
    },
    {
        "employer": "sergej.wolf",
        "days": 7,
        "job_type": "earthworks",
        "district": "trudering_riem",
        "start_time": "07:00",
        "hours": 8,
        "workers_needed": 2,
        "hourly_rate": "17.00",
        "original_language": "en",
        "description": (
            "Dig a trench of about 15 m for a drainage pipe in a garden. "
            "Spades and a mini digger are on site."
        ),
    },
]

# Done jobs inside the 14 days of #38; each accepted worker and the employer review each
# other: stars and tags for the workers, then for the employer.
DONE_JOBS = [
    {
        "employer": "sergej.wolf",
        "days_ago": 1,
        "job_type": "demolition",
        "district": "ramersdorf_perlach",
        "original_language": "ru",
        "description": "Снос перегородок в офисе, вынос мусора.",
        "workers": ["andrei.popescu"],
        "for_workers": (5, ["on_time", "hard_working"]),
        "for_employer": (5, ["paid_on_time", "clear_instructions"]),
    },
    {
        "employer": "ewa.nowak",
        "days_ago": 3,
        "job_type": "plastering",
        "district": "neuhausen_nymphenburg",
        "original_language": "pl",
        "description": "Pomoc przy tynkowaniu ścian w domu jednorodzinnym.",
        "workers": ["taras.melnyk", "piotr.wisniewski"],
        "for_workers": (4, ["careful_work"]),
        "for_employer": (5, ["as_described", "respectful"]),
    },
    {
        "employer": "thomas.berger",
        "days_ago": 5,
        "job_type": "carrying",
        "district": "untergiesing_harlaching",
        "original_language": "de",
        "description": "Möbel und Kartons aus dem Keller in den Transporter tragen.",
        "workers": ["lukas.bauer", "emre.demir"],
        "for_workers": (5, ["on_time", "clean_site"]),
        "for_employer": (4, ["paid_on_time"]),
    },
]


def database_is_local():
    """True when the database runs on this computer, not on Supabase (D17)."""
    return connection.settings_dict["HOST"] in LOCAL_HOSTS


def photo_bytes(scene):
    """A drawn "photo" of what the job's text says, as JPEG bytes (D17).

    Scenes: "shed" and "skip" (a garden shed to tear down, the container for it),
    "painting" (a wall half painted, tape, a roller), "tiles" and "broken_tiles" (a kitchen
    wall before and after the tiles come off, with a hammer).
    """
    image = Image.new("RGB", (1200, 900), (170, 215, 240))  # the sky
    draw = ImageDraw.Draw(image)
    if scene in ("shed", "skip"):
        draw.rectangle((0, 700, 1200, 900), fill=(110, 150, 80))  # the grass
        draw.rectangle((140, 380, 190, 700), fill=(110, 80, 50))  # a tree
        draw.ellipse((40, 200, 290, 450), fill=(70, 130, 60))
    if scene == "shed":
        draw.rectangle((450, 380, 1000, 700), fill=(160, 110, 60))
        for x in range(480, 1000, 50):  # the planks
            draw.line([(x, 380), (x, 700)], fill=(120, 80, 40), width=6)
        draw.polygon([(420, 390), (725, 220), (1030, 390)], fill=(90, 60, 40))
        draw.rectangle((660, 520, 790, 700), fill=(100, 65, 35))  # the door
    elif scene == "skip":
        for x1, y1, x2, y2 in [
            (450, 560, 640, 380),
            (560, 580, 820, 420),
            (700, 560, 900, 360),
        ]:
            draw.line([(x1, y1), (x2, y2)], fill=(150, 100, 55), width=28)  # old planks
        draw.polygon(
            [(380, 520), (1020, 520), (960, 760), (440, 760)], fill=(240, 180, 30)
        )
    elif scene == "painting":
        draw.rectangle((0, 0, 1200, 700), fill=(235, 228, 210))  # the old wall
        draw.rectangle((0, 0, 600, 700), fill=(150, 200, 190))  # the new paint
        draw.rectangle((0, 660, 1200, 700), fill=(60, 120, 220))  # the masking tape
        draw.rectangle((0, 700, 1200, 900), fill=(215, 220, 225))  # the plastic sheet
        draw.rectangle((640, 300, 820, 360), fill=(150, 200, 190))  # the roller
        draw.line([(730, 360), (730, 520)], fill=(60, 60, 60), width=14)
    else:  # "tiles", "broken_tiles": a kitchen wall of blue tiles in a chequer pattern
        draw.rectangle((0, 0, 1200, 900), fill=(240, 240, 235))  # the grout
        for x in range(0, 1200, 100):
            for y in range(0, 900, 100):
                shade = (70, 130, 190) if (x + y) % 200 else (110, 165, 215)
                draw.rectangle((x + 6, y + 6, x + 94, y + 94), fill=shade)
        if scene == "broken_tiles":
            draw.polygon(
                [(300, 0), (900, 0), (800, 500), (350, 600)], fill=(150, 140, 130)
            )
            for x, y, r in [
                (500, 820, 90),
                (650, 840, 70),
                (580, 760, 60),
                (760, 850, 50),
            ]:
                draw.ellipse((x - r, y - r, x + r, y + r), fill=(205, 200, 190))
        # a hammer: the handle, then the head across its top
        draw.line([(900, 860), (1080, 560)], fill=(150, 100, 55), width=34)
        draw.polygon(
            [(1000, 500), (1150, 590), (1110, 655), (960, 565)], fill=(80, 80, 85)
        )
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


def street_address(district):
    """A made-up address in the job's district: no real house is named."""
    return f"{district.replace('_', ' ').title()}, München"


class Command(BaseCommand):
    help = "Delete and re-create the demo accounts on @demo.example and their jobs."

    @override
    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            help="Password of every demo account. Without it the command asks for it.",
        )

    @override
    def handle(self, *args, **options):
        # Asked without showing it, so it is not in the shell history either (D5).
        password = options["password"] or getpass.getpass(
            "Password for the demo accounts: "
        )
        if not password:
            raise CommandError("The demo accounts need a password.")

        self.with_photos = database_is_local()

        # All or nothing: a half-seeded live database is worse than none (D9).
        with transaction.atomic():
            # The @ is part of the test: "anna@olddemo.example" is not ours (D10).
            old = User.objects.filter(email__endswith=f"@{DOMAIN}")
            deleted, _per_model = old.delete()  # profiles, jobs, reviews… go along
            users = self.create_accounts(password)
            self.create_open_jobs(users)
            self.create_done_jobs(users)

        self.report(deleted, users)

    def create_accounts(self, password):
        """The employers and workers with their profiles; returns the users by key."""
        users = {}
        for data in EMPLOYERS:
            user = self.create_user(data, "employer", password, number=len(users))
            EmployerProfile.objects.create(
                user=user, company_name=data["company_name"], trades=data["trades"]
            )
            users[data["key"]] = user
        for data in WORKERS:
            user = self.create_user(data, "worker", password, number=len(users))
            WorkerProfile.objects.create(
                user=user,
                team_size=data["team_size"],
                skills=data["skills"],
                languages=data["languages"],
                legal_status=data["legal_status"],
            )
            users[data["key"]] = user
        return users

    def create_user(self, data, role, password, number):
        """An active account with an unconfirmed address: #27 sends it no email (D6)."""
        return User.objects.create_user(
            email=f"{data['key']}@{DOMAIN}",
            password=password,
            name=data["name"],
            phone=f"+49 151 0000 {101 + number:04d}",  # 0101, 0102, …: not real numbers
            role=role,
            preferred_language=data["language"],
            # Workers have said they may work in Germany, so they could apply (#13).
            work_permit_confirmed_at=timezone.now() if role == "worker" else None,
        )

    def create_open_jobs(self, users):
        """The open jobs, from tomorrow to a week ahead (D8)."""
        today = timezone.localdate()
        for data in OPEN_JOBS:
            job = dict(data)  # a copy: the table stays as it is for the next run
            scenes = job.pop("photos", [])
            created = Job.objects.create(
                employer=users[job.pop("employer")],
                date=today + job.pop("days") * DAY,
                start_time=datetime.time.fromisoformat(job.pop("start_time")),
                hourly_rate=Decimal(job.pop("hourly_rate")),
                address=street_address(job["district"]),
                **job,  # job_type, district, hours, workers_needed, language, description
            )
            if self.with_photos:
                for scene in scenes:
                    # save() makes the thumbnail too (#64), as for an uploaded photo.
                    picture = photo_bytes(scene)
                    JobPhoto.objects.create(
                        job=created, image=ContentFile(picture, name="photo.jpg")
                    )

    def create_done_jobs(self, users):
        """Done jobs where both sides reviewed each other.

        A review is visible once the other side has reviewed too (reviews.md R6), so with
        both reviews the workers' pages show a rating at once (#39).
        """
        now = timezone.now()
        for data in DONE_JOBS:
            employer = users[data["employer"]]
            workers = [users[key] for key in data["workers"]]
            job = Job.objects.create(
                employer=employer,
                job_type=data["job_type"],
                district=data["district"],
                address=street_address(data["district"]),
                original_language=data["original_language"],
                description=data["description"],
                date=timezone.localdate() - (data["days_ago"] + 1) * DAY,
                start_time=datetime.time(8, 0),
                hours=6,
                workers_needed=sum(w.worker_profile.team_size for w in workers),
                hourly_rate=Decimal("16.00"),
                status=Job.Status.DONE,
                done_at=now - data["days_ago"] * DAY,
            )
            for worker in workers:
                team = worker.worker_profile.team_size
                application = Application.objects.create(
                    job=job,
                    worker=worker,
                    workers_offered=team,
                    workers_accepted=team,
                    status=Application.Status.ACCEPTED,
                )
                self.review(application, employer, *data["for_workers"])
                self.review(application, worker, *data["for_employer"])

    def review(self, application, author, rating, tags):
        """One side's review of the other; save() so a test can make it fail (AC8)."""
        Review.objects.create(
            application=application, author=author, rating=rating, tags=tags
        )

    def report(self, deleted, users):
        """What changed, the demo logins (not the password) and what to do next (R9)."""
        self.stdout.write(f"Deleted {deleted} old demo rows.")
        self.stdout.write(
            f"Created {len(users)} demo accounts, {len(OPEN_JOBS)} open jobs and "
            f"{len(DONE_JOBS)} done jobs with reviews."
        )
        if not self.with_photos:
            self.stdout.write(
                "Photos skipped: the database is not on this computer, and the files "
                "would stay on this disk (D17). Add photos through the site."
            )
        self.stdout.write("Demo logins (all with the password you gave):")
        for user in users.values():
            self.stdout.write(f"  {user.role:<9} {user.email}")
        self.stdout.write(
            "Next: register an employer and a worker on the site and follow the "
            "scenario of #49."
        )
