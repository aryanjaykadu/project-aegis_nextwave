"""OpenStreetMap resource categories used by the public nearby lookup."""
from __future__ import annotations

RESOURCE_CATEGORIES = {
    "hospital": {
        "label": "Hospitals",
        "symbol": "H+",
        "selectors": (("amenity", "hospital"),),
    },
    "clinic": {
        "label": "Clinics",
        "symbol": "+",
        "selectors": (("amenity", "clinic"),),
    },
    "doctors": {
        "label": "Doctors",
        "symbol": "MD",
        "selectors": (("amenity", "doctors"),),
    },
    "pharmacy": {
        "label": "Pharmacies",
        "symbol": "Rx",
        "selectors": (("amenity", "pharmacy"), ("shop", "chemist")),
    },
    "blood_bank": {
        "label": "Blood donation points",
        "symbol": "B+",
        "selectors": (("healthcare", "blood_donation"),),
    },
    "ambulance": {
        "label": "Ambulance stations",
        "symbol": "A",
        "selectors": (("emergency", "ambulance_station"),),
    },
    "veterinary": {
        "label": "Veterinary services",
        "symbol": "V",
        "selectors": (("amenity", "veterinary"),),
    },
    "defibrillator": {
        "label": "Defibrillators",
        "symbol": "AED",
        "selectors": (("emergency", "defibrillator"),),
    },
    "police": {
        "label": "Police stations",
        "symbol": "P",
        "selectors": (("amenity", "police"),),
    },
    "fire_station": {
        "label": "Fire stations",
        "symbol": "F",
        "selectors": (("amenity", "fire_station"),),
    },
    "fire_hydrant": {
        "label": "Fire hydrants",
        "symbol": "H2O",
        "selectors": (("emergency", "fire_hydrant"),),
    },
    "shelter": {
        "label": "Mapped shelters and assembly points",
        "symbol": "S",
        "selectors": (
            ("amenity", "shelter"),
            ("social_facility", "shelter"),
            ("emergency", "assembly_point"),
        ),
    },
    "school": {
        "label": "Schools",
        "symbol": "SCH",
        "selectors": (("amenity", "school"), ("amenity", "college"), ("amenity", "university")),
    },
    "water": {
        "label": "Drinking water and wells",
        "symbol": "W",
        "selectors": (
            ("amenity", "drinking_water"),
            ("man_made", "water_well"),
            ("man_made", "water_tower"),
            ("emergency", "water_tank"),
        ),
    },
    "fuel": {
        "label": "Fuel stations",
        "symbol": "⛽",
        "selectors": (("amenity", "fuel"),),
    },
    "ev_charging": {
        "label": "EV charging",
        "symbol": "EV",
        "selectors": (("amenity", "charging_station"),),
    },
    "market": {
        "label": "Markets and groceries",
        "symbol": "M",
        "selectors": (
            ("shop", "supermarket"),
            ("shop", "convenience"),
            ("shop", "grocery"),
            ("shop", "marketplace"),
            ("amenity", "marketplace"),
        ),
    },
    "bank_atm": {
        "label": "Banks and ATMs",
        "symbol": "₹",
        "selectors": (("amenity", "bank"), ("amenity", "atm")),
    },
    "toilets": {
        "label": "Public toilets",
        "symbol": "WC",
        "selectors": (("amenity", "toilets"),),
    },
    "community_centre": {
        "label": "Community centres",
        "symbol": "CC",
        "selectors": (("amenity", "community_centre"),),
    },
    "post_office": {
        "label": "Post offices",
        "symbol": "PO",
        "selectors": (("amenity", "post_office"),),
    },
    "railway_station": {
        "label": "Railway stations",
        "symbol": "R",
        "selectors": (("railway", "station"),),
    },
    "bus_station": {
        "label": "Bus stations",
        "symbol": "BUS",
        "selectors": (("amenity", "bus_station"),),
    },
    "airport_helipad": {
        "label": "Airports and helipads",
        "symbol": "AIR",
        "selectors": (("aeroway", "aerodrome"), ("aeroway", "helipad")),
    },
    "bridge": {
        "label": "Bridges",
        "symbol": "BR",
        "selectors": (("man_made", "bridge"), ("bridge", "yes")),
    },
    "waterway": {
        "label": "Mapped waterways",
        "symbol": "RIV",
        "selectors": (("waterway", "river"), ("waterway", "stream")),
    },
    "substation": {
        "label": "Power substations",
        "symbol": "⚡",
        "selectors": (("power", "substation"),),
    },
    "emergency_phone": {
        "label": "Emergency phones",
        "symbol": "TEL",
        "selectors": (("emergency", "phone"),),
    },
}

OSM_ATTRIBUTION = "© OpenStreetMap contributors · ODbL"
OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright"
OSM_DATA_URL = "https://www.openstreetmap.org/"
OSM_TRUST_TIER = {
    "code": "B",
    "label": "Map data",
    "notice": "OpenStreetMap listing; may be outdated. Verify before relying on it.",
}


def public_categories() -> list[dict[str, str]]:
    return [
        {"id": key, "label": value["label"], "symbol": value["symbol"]}
        for key, value in RESOURCE_CATEGORIES.items()
    ]
