"""Download reproducible India flood and Bihar satellite reference datasets."""
from pathlib import Path
import hashlib
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RECORD = "https://zenodo.org/records/16994648/files/{}?download=1"
BIHAR_DATASET_ID = "2c10ed21-6f6b-4f58-83dc-5406fb048e25"
BIHAR_FILENAME = "bihar_subdistrict_inundation_2021_2025.csv"
FILES = {
    "india_flood_inventory_v3.csv": "fea75a9ff9eba8fb328eaddfacd21d67",
    "dfsi_india.csv": "d15cbab2f15c3a6c393fd45220665211",
    "district_flooded_area_india.csv": "52744304c21f28b841fb3a28e510e789",
    "district_flood_impact_india.csv": "231d4157f462ea6c9bfd728c9dfbf520",
}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Project-Aegis/2.1 (research data preparation)"
    for filename, expected_md5 in FILES.items():
        response = session.get(RECORD.format(filename), timeout=180)
        response.raise_for_status()
        digest = hashlib.md5(response.content).hexdigest()
        if digest != expected_md5:
            raise ValueError(f"Checksum mismatch for {filename}: {digest}")
        output = DATA / filename
        output.write_bytes(response.content)
        print(f"Downloaded {filename} ({len(response.content):,} bytes; verified MD5)")

    # CivicDataSpace exposes public dataset resources through its GraphQL API.
    query = "query DatasetResources($id: UUID!) { dataset(id: $id) { datasetResources { id name } } }"
    response = session.post(
        "https://api.datakeep.civicdays.in/api/graphql",
        json={"query": query, "variables": {"id": BIHAR_DATASET_ID}},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    resources = payload.get("data", {}).get("dataset", {}).get("datasetResources", [])
    resource = next((item for item in resources if "sub-district" in item.get("name", "").lower() and "inundation" in item.get("name", "").lower()), None)
    if not resource:
        raise RuntimeError("Could not locate the Bihar sub-district inundation CSV resource in CivicDataSpace.")
    response = session.get(
        f"https://api.datakeep.civicdays.in/api/download/resource/{resource['id']}",
        timeout=180,
    )
    response.raise_for_status()
    output = DATA / BIHAR_FILENAME
    output.write_bytes(response.content)
    if output.stat().st_size < 100_000 or b"object_id" not in response.content[:4096]:
        output.unlink(missing_ok=True)
        raise ValueError("Downloaded Bihar inundation resource failed basic CSV validation.")
    print(f"Downloaded {BIHAR_FILENAME} ({len(response.content):,} bytes; CivicDataSpace resource {resource['id']})")


if __name__ == "__main__":
    main()
