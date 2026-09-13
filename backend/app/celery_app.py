import os

from celery import Celery
from dotenv import load_dotenv


load_dotenv()


CELERY_BROKER_URL = os.getenv(
    "AEGISAI_CELERY_BROKER_URL",
    "redis://localhost:6379/0",
)

CELERY_RESULT_BACKEND = os.getenv(
    "AEGISAI_CELERY_RESULT_BACKEND",
    "redis://localhost:6379/1",
)


celery_app = Celery(
    "aegisai",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    imports=("backend.app.tasks",),
)
