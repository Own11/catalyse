import json

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from .models import UniversityProfile
from .services import create_profile
from .services import discover_profile, discover_socials, _social_url_matches_name


def landing(request):
    recent = UniversityProfile.objects.all()[:8]
    return render(request, "landing.html", {"recent": recent, "hero_image": "/static/nazarbayev-university.png"})


def profile_history(request):
    items = UniversityProfile.objects.all()[:20]
    return JsonResponse({"items": [{"id": x.pk, "name": x.name, "created_at": x.created_at.isoformat()} for x in items]})


def profile_detail(request, profile_id):
    if "text/html" in request.headers.get("Accept", ""):
        return redirect("profile-page", profile_id=profile_id)
    try:
        item = UniversityProfile.objects.get(pk=profile_id)
    except UniversityProfile.DoesNotExist:
        return JsonResponse({"error": "profile_not_found"}, status=404)
    return JsonResponse({"id": item.pk, "profile": item.payload}, json_dumps_params={"ensure_ascii": False})


def profile_page(request, profile_id):
    try:
        item = UniversityProfile.objects.get(pk=profile_id)
    except UniversityProfile.DoesNotExist:
        return render(request, "profile.html", {"error": "Профиль не найден"}, status=404)
    # Backfill profiles created before social discovery was added.
    socials = item.payload.get("socials") or {}
    if not socials or any(not _social_url_matches_name(url, item.name) for url in socials.values()):
        item.payload["socials"] = discover_socials(item.name)
        item.save(update_fields=["payload"])
    photos = item.payload.get("photos", {})
    total = sum(len(value) for value in photos.values())
    return render(request, "profile.html", {"item": item, "recent": UniversityProfile.objects.all()[:20], "photo_total": total, "category_total": sum(bool(value) for value in photos.values())})


def health(request):
    return JsonResponse({"status": "ok", "service": "catalys"})


@csrf_exempt
def profile_create(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "JSON body must be an object"}, status=400)
    profile = create_profile(data)
    saved = UniversityProfile.objects.create(name=profile["name"], payload=profile)
    return JsonResponse({"id": saved.pk, "profile": profile}, status=201, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def profile_delete(request, profile_id):
    if request.method not in {"POST", "DELETE"}:
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    deleted, _ = UniversityProfile.objects.filter(pk=profile_id).delete()
    if not deleted:
        return JsonResponse({"error": "profile_not_found"}, status=404)
    return JsonResponse({"deleted": profile_id})


@csrf_exempt
def profile_discover(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    name = data.get("name", "").strip() if isinstance(data, dict) else ""
    if len(name) < 2:
        return JsonResponse({"error": "Введите название университета"}, status=400)
    try:
        profile = discover_profile(name)
    except Exception:
        profile = create_profile({"name": name, "description": f"Visual profile discovered for {name}.", "images": []})
        profile["ai_insights"] = {"summary": f"{name} profile is ready; external image sources are temporarily unavailable.", "highlights": [], "mode": "fallback"}
    saved = UniversityProfile.objects.create(name=profile["name"], payload=profile)
    return JsonResponse({"id": saved.pk, "profile": profile}, json_dumps_params={"ensure_ascii": False})
