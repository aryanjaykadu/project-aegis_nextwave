from __future__ import annotations

import unittest
from argparse import ArgumentTypeError

from scripts.build_osm_region_pack import build_pack, overpass_query, parse_bbox


class OSMRegionPackTests(unittest.TestCase):
    def test_bbox_validation_rejects_bad_and_oversized_regions(self):
        self.assertEqual(parse_bbox("25.5,85.0,25.7,85.3"), (25.5, 85.0, 25.7, 85.3))
        with self.assertRaises(ArgumentTypeError):
            parse_bbox("25.7,85.0,25.5,85.3")
        with self.assertRaises(ArgumentTypeError):
            parse_bbox("0,0,20,20")

    def test_query_is_bounded_to_requested_region(self):
        query = overpass_query((25.5, 85.0, 25.7, 85.3))
        self.assertIn('(25.5,85.0,25.7,85.3)', query)
        self.assertIn('["amenity"="hospital"]', query)
        self.assertIn('out center meta tags', query)

    def test_pack_deduplicates_points_and_keeps_source_provenance(self):
        elements = [
            {
                "type": "node", "id": 1, "lat": 25.6, "lon": 85.1,
                "timestamp": "2026-10-30T08:00:00Z",
                "tags": {"name": "Clinic and pharmacy", "amenity": "hospital", "shop": "chemist"},
            },
            {
                "type": "node", "id": 1, "lat": 25.6, "lon": 85.1,
                "timestamp": "2026-10-30T08:00:00Z",
                "tags": {"name": "Clinic and pharmacy", "amenity": "hospital", "shop": "chemist"},
            },
            {"type": "node", "id": 2, "lat": 120, "lon": 85, "tags": {"amenity": "hospital"}},
            {"type": "node", "id": 3, "lat": 25.8, "lon": 85.1, "tags": {"amenity": "hospital"}},
        ]
        pack, report = build_pack(
            elements, (25.5, 85.0, 25.7, 85.3), "test-area", "2026-11-01T10:00:00+00:00"
        )
        self.assertEqual(len(pack["features"]), 1)
        feature = pack["features"][0]
        self.assertEqual(set(feature["properties"]["category_ids"]), {"hospital", "pharmacy"})
        self.assertEqual(feature["properties"]["license"], "Open Database License (ODbL)")
        self.assertEqual(feature["properties"]["trust_tier"]["code"], "B")
        self.assertEqual(report["quality"]["duplicates_merged"], 1)
        self.assertEqual(report["quality"]["invalid_coordinates_or_ids"], 2)


if __name__ == "__main__":
    unittest.main()
