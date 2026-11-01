"""Build a versioned, compressed OSM resource pack for a small bounding box."""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.resource_catalog import (  # noqa: E402
    OSM_ATTRIBUTION,
    OSM_COPYRIGHT_URL,
    OSM_DATA_URL,
    OSM_TRUST_TIER,
    RESOURCE_CATEGORIES,
)

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
MAX_BBOX_AREA_DEGREES = 25.0


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        south, west, north, east = (float(part.strip()) for part in value.split(","))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("Bounding box must be south,west,north,east.") from exc
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise argparse.ArgumentTypeError("Bounding box coordinates are invalid.")
    if (north - south) * (east - west) > MAX_BBOX_AREA_DEGREES:
        raise argparse.ArgumentTypeError(
            "Region is too large for one Overpass export; split it into smaller regional tiles."
        )
    return south, west, north, east


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    bounds = ",".join(str(value) for value in bbox)
    clauses = []
    for category in RESOURCE_CATEGORIES.values():
        for key, value in category["selectors"]:
            clauses.append(f'nwr["{key}"="{value}"]({bounds});')
    return f'[out:json][timeout:90];({"".join(clauses)});out center meta tags;'


def build_pack(
    elements: list[dict[str, Any]],
    bbox: tuple[float, float, float, float],
    region_id: str,
    retrieved_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    south, west, north, east = bbox
    category_lookup: dict[tuple[str, str], set[str]] = {}
    for category_id, category in RESOURCE_CATEGORIES.items():
        for key, value in category["selectors"]:
            category_lookup.setdefault((key, value), set()).add(category_id)

    unique: dict[tuple[str, Any], dict[str, Any]] = {}
    invalid_coordinates = 0
    duplicate_count = 0
    missing_name = 0
    missing_edit_time = 0
    for element in elements:
        tags = {
            str(key): unicodedata.normalize("NFC", value) if isinstance(value, str) else value
            for key, value in (element.get("tags") or {}).items()
        }
        matched_categories = sorted({
            category_id
            for key, value in tags.items()
            for category_id in category_lookup.get((key, str(value)), ())
        })
        if not matched_categories:
            continue
        center = element.get("center") or {}
        try:
            lat = float(element.get("lat", center.get("lat")))
            lon = float(element.get("lon", center.get("lon")))
        except (TypeError, ValueError, OverflowError):
            invalid_coordinates += 1
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and south <= lat <= north and west <= lon <= east):
            invalid_coordinates += 1
            continue

        element_type = str(element.get("type") or "")
        element_id = element.get("id")
        if not element_type or element_id is None:
            invalid_coordinates += 1
            continue
        key = (element_type, element_id)
        if key in unique:
            duplicate_count += 1
            unique[key]["category_ids"] = sorted(set(unique[key]["category_ids"]) | set(matched_categories))
            continue

        name = tags.get("name") or tags.get("brand")
        if not name:
            missing_name += 1
        timestamp = element.get("timestamp")
        if not timestamp:
            missing_edit_time += 1
        osm_url = f"https://www.openstreetmap.org/{element_type}/{element_id}"
        unique[key] = {
            "id": element_id,
            "osm_type": element_type,
            "name": name,
            "lat": lat,
            "lon": lon,
            "category_ids": matched_categories,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "last_edited_at": timestamp,
            "source": "OpenStreetMap",
            "source_url": osm_url,
            "license": "Open Database License (ODbL)",
            "license_url": OSM_COPYRIGHT_URL,
            "retrieved_at": retrieved_at,
            "trust_tier": OSM_TRUST_TIER,
            "availability": "unverified",
            "tags": tags,
        }

    features = list(unique.values())
    pack = {
        "type": "FeatureCollection",
        "metadata": {
            "region_id": region_id,
            "version": datetime.fromisoformat(retrieved_at).strftime("%Y%m%dT%H%M%SZ"),
            "created_at": retrieved_at,
            "bounds": {"south": south, "west": west, "north": north, "east": east},
            "source": "OpenStreetMap via Overpass",
            "source_url": OSM_DATA_URL,
            "attribution": OSM_ATTRIBUTION,
            "license": "ODbL",
            "license_url": OSM_COPYRIGHT_URL,
            "trust_tier": OSM_TRUST_TIER,
            "notice": "Community map data may be incomplete or outdated. Facility availability is not verified.",
            "feature_count": len(features),
        },
        "features": [
            {
                "type": "Feature",
                "id": f"{feature['osm_type']}/{feature['id']}",
                "geometry": {"type": "Point", "coordinates": [feature["lon"], feature["lat"]]},
                "properties": {key: value for key, value in feature.items() if key not in {"lat", "lon"}},
            }
            for feature in features
        ],
    }
    quality = {
        **pack["metadata"],
        "quality": {
            "raw_elements": len(elements),
            "accepted_features": len(features),
            "duplicates_merged": duplicate_count,
            "invalid_coordinates_or_ids": invalid_coordinates,
            "missing_names": missing_name,
            "missing_names_percent": round(missing_name / len(features) * 100, 2) if features else 0,
            "missing_edit_timestamps": missing_edit_time,
            "missing_edit_timestamps_percent": round(missing_edit_time / len(features) * 100, 2) if features else 0,
        },
    }
    return pack, quality


def download_elements(bbox: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    query = overpass_query(bbox)
    last_error: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(3):
            try:
                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers={"User-Agent": "Project-Aegis/2.3 (regional OSM data pack)"},
                    timeout=110,
                )
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "")
                    try:
                        delay = min(60, max(1, int(retry_after)))
                    except ValueError:
                        delay = min(30, 2 ** attempt)
                    time.sleep(delay)
                    last_error = requests.HTTPError("Overpass rate limited this request (HTTP 429).")
                    continue
                response.raise_for_status()
                payload = response.json()
                elements = payload.get("elements") if isinstance(payload, dict) else None
                if not isinstance(elements, list):
                    raise ValueError("Overpass returned no elements array.")
                return elements
            except (requests.RequestException, ValueError, TypeError) as exc:
                last_error = exc
                break
    raise RuntimeError(f"Unable to download regional OSM data: {last_error}") from last_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region-id", required=True, help="Short region name, such as patna-core.")
    parser.add_argument("--bbox", required=True, type=parse_bbox, help="south,west,north,east")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "region-packs")
    args = parser.parse_args()
    region_id = args.region_id.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", region_id):
        parser.error("--region-id must contain 2-64 lowercase letters, digits, or hyphens.")

    elements = download_elements(args.bbox)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    pack, quality = build_pack(elements, args.bbox, region_id, retrieved_at)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    version=pack["metadata"]["version"]
    base = args.output_dir / f"{region_id}-{version}"
    pack_path = base.with_suffix(".geojson.gz")
    quality_path = base.with_suffix(".quality.json")
    with gzip.open(pack_path, "wt", encoding="utf-8") as stream:
        json.dump(pack, stream, ensure_ascii=False, separators=(",", ":"))
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pack": str(pack_path),
        "pack_bytes": pack_path.stat().st_size,
        "quality_report": str(quality_path),
        "features": quality["feature_count"],
        "quality": quality["quality"],
        "attribution": OSM_ATTRIBUTION,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
