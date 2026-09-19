import json

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from .models import UniversityProfile
from .services import create_profile
from .services import discover_profile, _is_social_profile


def concise_description(name: str) -> str:
    return f"Визуальный профиль {name} на основе доступных открытых материалов."


def landing(request):
    recent = UniversityProfile.objects.all()[:8]
    return render(request, "landing.html", {"recent": recent})


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
    # Remove obsolete timeout markers from profiles created before the search
    # flow stopped using a global time limit.
    if "sources_timeout" in item.payload.get("warnings", []):
        item.payload["warnings"] = [w for w in item.payload["warnings"] if w != "sources_timeout"]
    # Opening a profile must be read-only and fast. Discovery happens once in
    # the API request; never repeat network searches during page rendering.
    socials = item.payload.get("socials") or {}
    socials = {
        network: url for network, url in socials.items()
        if network in {"instagram", "facebook", "youtube", "telegram", "whatsapp"}
        and _is_social_profile(url, network)
    }
    item.payload["socials"] = socials
    if item.payload.get("socials") != socials:
        item.save(update_fields=["payload"])
    insights = item.payload.get("ai_insights") or {}
    if ("создан за ограниченное время" in str(insights.get("summary", ""))
            or str(insights.get("summary", "")).startswith("Краткий визуальный профиль")):
        insights["summary"] = concise_description(item.name)
        item.payload["ai_insights"] = insights
        item.save(update_fields=["payload"])
    photos = item.payload.get("photos", {})
    if not any(photos.values()):
        refreshed = discover_profile(item.name)
        if any(refreshed.get("photos", {}).values()):
            item.payload.update(refreshed)
            item.save(update_fields=["payload"])
            photos = item.payload.get("photos", {})
    if photos and not any(photos.values()) and "sources_unavailable" not in item.payload.get("warnings", []):
        item.payload.setdefault("warnings", []).append("sources_unavailable")
        item.save(update_fields=["payload"])
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
    profile.setdefault("warnings", [])
    if not profile.get("name"):
        profile["warnings"].append("name_missing")
    if not any(profile.get("photos", {}).values()):
        profile["warnings"].append("insufficient_data")
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
        profile["ai_insights"] = {"summary": concise_description(name), "highlights": [], "mode": "fallback"}
        profile.setdefault("warnings", []).extend(["sources_unavailable", "insufficient_data"])
    saved = UniversityProfile.objects.create(name=profile["name"], payload=profile)
    return JsonResponse({"id": saved.pk, "profile": profile}, json_dumps_params={"ensure_ascii": False})
