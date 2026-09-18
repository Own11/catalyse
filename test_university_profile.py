import json

from university_profile import build_profile, profile_json


def test_filters_sources_deduplicates_and_keeps_empty_categories():
    raw = {
        "name": "Example University",
        "description": "Official campus near the city center.",
        "images": [
            {"image_url": "https://uni.example/campus.jpg", "source_url": "https://uni.example/campus", "title": "Official campus", "university_match": True, "visual_hash": "same"},
            {"image_url": "https://uni.example/campus-copy.jpg", "source_url": "https://uni.example/campus", "visual_hash": "same", "title": "Campus"},
            {"image_url": "https://shutterstock.com/photo.jpg", "source_url": "https://uni.example/page", "title": "Campus"},
            {"image_url": "https://uni.example/no-source.jpg", "source_url": "not-a-url", "title": "Campus"},
        ],
    }
    result = build_profile(raw)
    assert len(result["photos"]["campus"]) == 1
    assert result["photos"]["dormitory"] == []
    assert result["photos"]["campus"][0]["confidence"] == 1.0
    assert json.loads(profile_json(raw))["name"] == "Example University"
