"""Deterministic sanitizer for raw university search results.

The module intentionally uses only fields supplied by the caller. It does not
invent facts and is safe to put behind a Django REST Framework endpoint.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse


CATEGORIES = ("campus", "dormitory", "auditoriums", "sport", "student_life")
BLOCKED_IMAGE_DOMAINS = {
    "pinterest.com", "www.pinterest.com", "shutterstock.com", "www.shutterstock.com",
    "istockphoto.com", "www.istockphoto.com", "gettyimages.com", "www.gettyimages.com",
    "unsplash.com", "www.unsplash.com", "pexels.com", "www.pexels.com",
}

KEYWORDS = {
    "dormitory": ("dorm", "dormitory", "residence", "hostel", "housing", "общежит", "резиденц"),
    "auditoriums": ("auditor", "classroom", "lecture", "laborator", "lab", "seminar", "аудитор", "лаборатор", "лекцион"),
    "sport": ("sport", "stadium", "gym", "arena", "fitness", "athletic", "recreation", "спорт", "стадион", "зал"),
    "student_life": ("student life", "students", "event", "club", "union", "cafe", "city", "студент", "клуб", "город"),
    "campus": ("campus", "building", "university", "college", "кампус", "здани", "университет"),
}


def _url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    return value.strip() if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0]


def _blocked(url: str) -> bool:
    domain = _domain(url)
    return domain in BLOCKED_IMAGE_DOMAINS or any(domain.endswith("." + d) for d in BLOCKED_IMAGE_DOMAINS)


def _text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(k, "")) for k in ("title", "alt", "caption", "snippet", "text")).lower()


def _category(item: dict[str, Any]) -> str:
    text = _text(item)
    scores = {category: sum(bool(re.search(r"\b" + re.escape(word), text)) for word in words)
              for category, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "campus"


def _confidence(item: dict[str, Any], image_url: str, source_url: str) -> float:
    """Conservative heuristic; an LLM may later refine this score."""
    score = 0.35
    if _domain(source_url) == _domain(image_url):
        score += 0.25
    if any(token in _text(item) for token in ("official", "university", "университет", "campus", "кампус")):
        score += 0.2
    if item.get("university_match") is True:
        score += 0.2
    return round(min(score, 1.0), 2)


def build_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert search output into a strict, JSON-serializable profile."""
    result: dict[str, Any] = {
        "name": raw.get("name") if isinstance(raw.get("name"), str) else None,
        "campus_description": raw.get("description") if isinstance(raw.get("description"), str) else None,
        "photos": {category: [] for category in CATEGORIES},
        "additional_data": {},
        "warnings": [],
    }
    for key in ("cost_of_living", "climate", "transport"):
        if isinstance(raw.get(key), (str, int, float, dict, list)):
            result["additional_data"][key] = raw[key]

    seen_urls: set[str] = set()
    seen_fingerprints: set[str] = set()
    for item in raw.get("images", []) if isinstance(raw.get("images"), list) else []:
        if not isinstance(item, dict):
            continue
        image_url, source_url = _url(item.get("image_url")), _url(item.get("source_url"))
        if not image_url or not source_url or _blocked(image_url) or _blocked(source_url):
            continue
        fingerprint = str(item.get("visual_hash") or hashlib.sha256(image_url.encode()).hexdigest())
        if image_url in seen_urls or fingerprint in seen_fingerprints:
            continue
        seen_urls.add(image_url); seen_fingerprints.add(fingerprint)
        category = item.get("category") if item.get("category") in CATEGORIES else _category(item)
        result["photos"][category].append({
            "image_url": image_url, "category": category, "source_url": source_url,
            "confidence": round(float(item.get("vision_confidence", _confidence(item, image_url, source_url))), 2),
        })
    if not result["name"]:
        result["warnings"].append("name_missing")
    if not result["campus_description"]:
        result["warnings"].append("description_missing")
    return result


def profile_json(raw: dict[str, Any]) -> str:
    return json.dumps(build_profile(raw), ensure_ascii=False, separators=(",", ":"))
