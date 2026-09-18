from django.core.management.base import BaseCommand
from profiles.models import UniversityProfile
from profiles.services import create_profile


class Command(BaseCommand):
    help = "Create a deterministic profile for offline demos"

    def handle(self, *args, **kwargs):
        base = "https://commons.wikimedia.org/wiki/Special:FilePath/"
        files = [("Nazarbayev_University.jpg", "campus"), ("Nazarbayev_University_ панорама.jpg", "campus"), ("Nazarbayev_University_library.jpg", "auditoriums"), ("Nazarbayev_University_sport.jpg", "sport")]
        raw = {"name": "Nazarbayev University", "description": "Modern research campus in Astana.", "images": [{"image_url": base + url, "source_url": "https://commons.wikimedia.org/", "title": category, "category": category, "university_match": True} for url, category in files]}
        profile = create_profile(raw)
        item = UniversityProfile.objects.create(name=profile["name"], payload=profile)
        self.stdout.write(self.style.SUCCESS(f"Demo profile created: {item.pk}"))
