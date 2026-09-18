from celery import shared_task
from .services import discover_profile

@shared_task
def discover_profile_task(name: str) -> dict:
    return discover_profile(name)
