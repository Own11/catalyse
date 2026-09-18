import json
import os
import re
import logging
import base64
import asyncio
from concurrent.futures import ThreadPoolExecutor
import httpx
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from university_profile import build_profile

logger = logging.getLogger(__name__)


def identity_tokens(name: str) -> list[str]:
    tokens = [x.lower() for x in name.replace("-", " ").split() if len(x) >= 3 and x.lower() not in {"university", "institute", "college", "of", "the"}]
    return tokens or [name.strip().lower()]


def gemini_alias(name: str) -> str:
    """Resolve abbreviations with Gemini; local aliases keep demo reliable."""
    fallback = name.strip()
    key = os.getenv("GEMINI_API_KEY")
    if not key or len(name.strip()) > 48:
        return fallback
    prompt = f'Return JSON only: {{"official_name":"..."}}. Expand this university abbreviation or normalize its name: {name}'
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    try:
        model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        req = Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={quote(key)}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=6) as response:
            data = json.loads(response.read())
        official = json.loads(data["candidates"][0]["content"]["parts"][0]["text"]).get("official_name", "").strip()
        return official[:120] if official else fallback
    except Exception:
        return fallback


def gemini_verify_image(name: str, item: dict) -> bool:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return True
    try:
        image = httpx.get(item["image_url"], timeout=6).content
        prompt = f"Is this clearly a real photo of the {name} university campus or its student facilities? Return JSON only: {{\"keep\":true or false}}. Reject portraits, logos, unrelated buildings, animals, generic stock photos and unrelated events."
        body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image).decode()}}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
        model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        req = Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={quote(key)}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=12) as response:
            data = json.loads(response.read())
        return bool(json.loads(data["candidates"][0]["content"]["parts"][0]["text"]).get("keep"))
    except Exception:
        return False
def duckduckgo_images(name: str) -> list[dict]:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        queries = (("campus", "campus"), ("dormitory", "dormitory"), ("library", "auditoriums"), ("auditorium", "auditoriums"), ("sports center", "sport"), ("students", "student_life"))

        def search_category(query_category, category):
            try:
                with DDGS() as ddgs:
                    return [{"image_url": x.get("thumbnail") or x.get("image"), "source_url": x.get("url"), "title": x.get("title", name) + " " + query_category, "university_match": True, "category": category} for x in ddgs.images(f"{name} official {query_category}", max_results=8) if x.get("image") and x.get("url")]
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=6) as pool:
            batches = pool.map(lambda item: search_category(*item), queries)
            return [image for batch in batches for image in batch]
    except Exception:
        return []


def discover_reviews(name: str, limit: int = 8) -> list[dict]:
    """Collect public review snippets with links to the original pages.

    Search snippets are deliberately labelled as excerpts: we do not present
    them as verified ratings or invent missing author/date information.
    """
    reviews = []
    seen = set()
    def add_result(url, title, snippet, published_at=None):
        if not url or not snippet or url in seen:
            return False
        haystack = f"{title} {snippet} {url}".lower()
        # Search engines often omit the full name from the excerpt. Accept a
        # distinctive token or the university name itself in that case.
        tokens = identity_tokens(name)
        matched_tokens = sum(
            bool(re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", haystack))
            for token in tokens
        )
        required_tokens = 2 if len(tokens) > 1 else 1
        if matched_tokens < required_tokens and name.lower() not in haystack:
            return False
        seen.add(url)
        reviews.append({
            "title": title or "Отзыв об университете",
            "text": snippet,
            "author": None,
            "rating": None,
            "published_at": published_at,
            "source": urlparse(url).netloc.removeprefix("www."),
            "source_url": url,
            "verified": False,
        })
        return True

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        queries = (
            f'"{name}" student review campus',
            f'"{name}" experience students review',
            f'"{name}" отзывы студентов',
            f'"{name}" site:reddit.com student experience',
            f'"{name}" site:gradreports.com review',
            f'"{name}" site:thegradcafe.com students',
        )
        with DDGS() as ddgs:
            for query in queries:
                for result in ddgs.text(query, max_results=limit):
                    url = result.get("href") or result.get("url")
                    title = str(result.get("title") or "").strip()
                    snippet = str(result.get("body") or result.get("snippet") or "").strip()
                    add_result(url, title, snippet, result.get("date") or None)
                    if len(reviews) >= limit:
                        return reviews
    except Exception:
        # The package is optional in lightweight/demo environments.
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urlencode
            query = f'"{name}" student reviews university'
            request = Request(
                "https://html.duckduckgo.com/html/?" + urlencode({"q": query}),
                headers={"User-Agent": "Mozilla/5.0 (Catalys/1.0)"},
            )
            with urlopen(request, timeout=8) as response:
                soup = BeautifulSoup(response.read(), "html.parser")
            for result in soup.select(".result"):
                link = result.select_one(".result__a")
                snippet = result.select_one(".result__snippet")
                if not link or not snippet:
                    continue
                add_result(link.get("href"), link.get_text(" ", strip=True), snippet.get_text(" ", strip=True))
                if len(reviews) >= limit:
                    break
        except Exception:
            pass
    return reviews


SOCIAL_DOMAINS = {
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.com"),
    "youtube": ("youtube.com", "youtu.be"),
    "telegram": ("t.me", "telegram.me"),
    "whatsapp": ("wa.me", "whatsapp.com"),
}


def _is_social_profile(url: str, network: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().split(":", 1)[0].removeprefix("www.")
        path = parsed.path.strip("/").lower()
        if not any(host == domain or host.endswith("." + domain) for domain in SOCIAL_DOMAINS[network]):
            return False
        if not path or path.startswith(("search", "results", "explore", "watch")):
            return False
        if network == "youtube":
            return path.startswith(("@", "channel/", "c/", "user/"))
        if network == "whatsapp":
            return host == "wa.me" or path.startswith(("channel/", "community/"))
        return True
    except (TypeError, ValueError):
        return False


def discover_socials(name: str) -> dict[str, str]:
    """Find actual university social profiles using web search and Gemini."""
    found = {}
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            for network, domains in SOCIAL_DOMAINS.items():
                queries = (f'"{name}" official site:{domains[0]}', f'"{name}" {network} site:{domains[0]}', f'{name} official {network} site:{domains[0]}')
                for query in queries:
                    for result in ddgs.text(query, max_results=8):
                        url = result.get("href") or result.get("url")
                        if not url or not _is_social_profile(url, network):
                            continue
                        text = " ".join(str(result.get(key, "")) for key in ("title", "body")).lower()
                        if not any(token in text or token in url.lower() for token in identity_tokens(name)):
                            continue
                        found[network] = url
                        break
                    if network in found:
                        break
    except Exception:
        # Search is optional; Gemini can still provide the second source.
        pass

    # Let Gemini fill only networks that web search did not find.
    key = os.getenv("GEMINI_API_KEY")
    if key and len(found) < len(SOCIAL_DOMAINS):
        prompt = (
            f"Find the official social media profiles of the university {name}. "
            "Return JSON only with keys instagram, facebook, youtube, telegram, whatsapp. "
            "Use a direct official profile/channel URL or null when it cannot be identified. "
            "Never return search URLs, guesses, or unrelated student/community accounts."
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        try:
            model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
            req = Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={quote(key)}",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
            raw = data["candidates"][0]["content"]["parts"][0]["text"]
            suggestions = json.loads(raw)
            for network in SOCIAL_DOMAINS:
                url = suggestions.get(network)
                if network not in found and isinstance(url, str) and _is_social_profile(url, network) and _social_url_matches_name(url, name) and _url_is_alive(url):
                    found[network] = url
        except (KeyError, TypeError, ValueError, OSError):
            pass
    return found


def _url_is_alive(url: str) -> bool:
    try:
        response = httpx.get(url, follow_redirects=True, timeout=5, headers={"User-Agent": "CatalysMVP/1.0"})
        return response.status_code < 400
    except httpx.HTTPError:
        return False


def _social_url_matches_name(url: str, name: str) -> bool:
    """Require the university identity to appear in an AI-suggested handle/URL."""
    normalized_url = urlparse(url).path.lower().replace("-", "").replace("_", "")
    return any(token.replace(" ", "") in normalized_url for token in identity_tokens(name))


async def validate_urls(items: list[dict]) -> list[dict]:
    async with httpx.AsyncClient(timeout=5, follow_redirects=True, headers={"User-Agent": "CatalysMVP/1.0"}) as client:
        async def check(item):
            try:
                # Many image CDNs reject HEAD although the image is publicly readable.
                response = await client.get(item["image_url"], headers={"Range": "bytes=0-1024"})
                return item if response.status_code < 500 else None
            except Exception:
                # Do not discard a relevant search result only because its CDN
                # rejects a probe request; the browser may still load it.
                return item
        return [x for x in await asyncio.gather(*(check(i) for i in items)) if x]


def vision_check(name: str, item: dict) -> dict:
    """Optional visual verification; falls back safely when no API key exists."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return {"verified": bool(item.get("university_match")), "reason": "source and metadata heuristic"}
    prompt = f'Is this image plausibly an official photo of {name}? Return JSON only with keys verified, category, confidence.'
    payload = {"model": os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini"), "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}, {"type": "input_image", "image_url": item["image_url"], "detail": "low"}]}], "text": {"format": {"type": "json_object"}}}
    try:
        req = Request("https://api.openai.com/v1/responses", data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=12) as response:
            data = json.loads(response.read())
        text = data.get("output_text", "{}"); return json.loads(text)
    except Exception:
        return {"verified": False, "reason": "vision_unavailable"}


def gemini_insights(profile: dict) -> dict:
    """Optional text intelligence layer using Gemini GenerateContent."""
    labels = {
        "campus": "кампус",
        "dormitory": "общежития",
        "auditoriums": "аудитории и лаборатории",
        "sport": "спортивная инфраструктура",
        "student_life": "студенческая жизнь",
    }
    counts = {labels[key]: len(value) for key, value in profile["photos"].items() if value}
    if counts:
        parts = ", ".join(f"{label} ({count})" for label, count in counts.items())
        summary = f"Короткий визуальный профиль {profile['name']}: найдены материалы по направлениям — {parts}."
    else:
        summary = f"Для {profile['name']} пока не найдено достаточно подтверждённых фотографий."
    fallback = {"summary": summary, "highlights": list(counts), "mode": "fallback"}
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return fallback
    prompt = (
        f"Составь краткое описание университета {profile['name']} для абитуриента. "
        "Ответ должен быть на русском языке, максимум 2 коротких предложения. "
        "Опирайся только на название, описание и реально найденные категории фотографий. "
        "Не придумывай город, рейтинги, программы, инфраструктуру или другие факты, "
        "если их нет в данных. Верни JSON строго с полями summary, highlights и recommendation. "
        f"Описание источника: {profile.get('campus_description') or 'нет данных'}. "
        f"Количество подтверждённых материалов по категориям: "
        f"{ {k: len(v) for k, v in profile['photos'].items()} }."
    )
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    try:
        model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        req = Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={quote(key)}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
        result = json.loads(data["candidates"][0]["content"]["parts"][0]["text"]); result["mode"] = "gemini"; return result
    except Exception as error:
        logger.warning("Gemini profile description failed: %s", error)
        return fallback


def create_profile(raw_data: dict) -> dict:
    """Single application entry point for API, Celery and management commands."""
    return build_profile(raw_data)


def discover_profile(name: str) -> dict:
    """Fast keyless MVP discovery via Wikimedia's public image API."""
    resolved_name = gemini_alias(name)
    # Keep both the user-entered acronym and the normalized official name.
    # Wikimedia commonly uses filenames such as "MIT Building" rather than
    # the full "Massachusetts Institute of Technology" name.
    search_tokens = set(identity_tokens(name) + identity_tokens(resolved_name))
    raw_name = name.strip().lower().replace("-", " ")
    if raw_name and len(raw_name.split()) == 1 and len(raw_name) <= 8:
        search_tokens.add(raw_name)
    query = quote(resolved_name)
    endpoint = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={query}&gsrnamespace=6&gsrlimit=50&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=1200&format=json"
    def commons_images():
        found = []
        try:
            request = Request(endpoint, headers={"User-Agent": "CatalysMVP/1.0"})
            with urlopen(request, timeout=6) as response:
                pages = json.loads(response.read()).get("query", {}).get("pages", {}).values()
                for page in pages:
                    info = (page.get("imageinfo") or [{}])[0]
                    url = info.get("thumburl") or info.get("url")
                    title = page.get("title", "").lower()
                    named = any(token in title for token in search_tokens)
                    if url and named:
                        found.append({"image_url": url, "source_url": "https://commons.wikimedia.org/wiki/" + quote(page.get("title", "").replace(" ", "_")), "title": page.get("title", ""), "university_match": True})
        except Exception:
            pass
        return found

    with ThreadPoolExecutor(max_workers=2) as search_pool:
        image_future = search_pool.submit(duckduckgo_images, name)
        commons_future = search_pool.submit(commons_images)
        try:
            images = image_future.result(timeout=9)
        except Exception:
            images = []
        try:
            images.extend(commons_future.result(timeout=1))
        except Exception:
            pass
    if images:
        images = asyncio.run(validate_urls(images[:60]))
    if os.getenv("GEMINI_API_KEY") and images:
        images = [item for item in images[:24] if gemini_verify_image(name, item)]
    # Wikipedia is a second independent source and often has the official hero image.
    try:
        wiki = f"https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={query}&gsrnamespace=0&gsrlimit=3&prop=pageimages|info&pithumbsize=1200&inprop=url&format=json"
        with urlopen(Request(wiki, headers={"User-Agent": "CatalysMVP/1.0"}), timeout=6) as response:
            for page in json.loads(response.read()).get("query", {}).get("pages", {}).values():
                thumb = page.get("thumbnail", {}).get("source")
                page_title = page.get("title", "").lower()
                name_tokens = search_tokens
                context = any(word in page_title for word in ("university", "institute", "college", "campus"))
                exact_identity = name.strip().lower() in page_title or page_title.replace(" ", "") == name.strip().lower()
                if thumb and (context or exact_identity) and any(token in page_title for token in name_tokens):
                    images.append({"image_url": thumb, "source_url": page.get("fullurl", "https://wikipedia.org"), "title": page.get("title", "") + " university campus", "university_match": True})
    except Exception:
        pass
    if os.getenv("OPENAI_API_KEY"):
        checked = []
        for item in images[:12]:
            verdict = vision_check(name, item)
            if verdict.get("verified"):
                item["category"] = verdict.get("category")
                item["vision_confidence"] = verdict.get("confidence")
                checked.append(item)
        images = checked
    logo_candidates = [x for x in images if any(word in x.get("title", "").lower() for word in ("logo", "seal", "emblem", "symbol")) or ".svg" in x.get("image_url", "").lower()]
    gallery_images = [x for x in images if x not in logo_candidates]
    profile = build_profile({"name": name, "description": f"Visual profile discovered for {name}.", "images": gallery_images})
    profile["logo_url"] = logo_candidates[0]["image_url"] if logo_candidates else (sum(profile["photos"].values(), [None])[0] or {}).get("image_url")
    profile["socials"] = discover_socials(resolved_name)
    profile["reviews"] = discover_reviews(resolved_name)
    profile["ai_insights"] = gemini_insights(profile)
    return profile
