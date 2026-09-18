from django.urls import path
from profiles.views import health, profile_create, profile_delete, profile_discover, profile_history, profile_detail, profile_page, landing

urlpatterns = [
    path("", landing, name="landing"),
    path("health/", health, name="health"),
    path("api/v1/profiles/", profile_create, name="profile-create"),
    path("api/v1/discover/", profile_discover, name="profile-discover"),
    path("api/v1/profiles/history/", profile_history, name="profile-history"),
    path("api/v1/profiles/<int:profile_id>/", profile_detail, name="profile-detail"),
    path("api/v1/profiles/<int:profile_id>/delete/", profile_delete, name="profile-delete"),
    path("profile/<int:profile_id>/", profile_page, name="profile-page"),
]
