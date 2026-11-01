# Project Aegis

Project Aegis is a software-only flood-data awareness and community-resilience research prototype for Patna, Bihar. It is **not an official alert, emergency service, validated forecast, or safe-route authority**. Call official emergency services and use Bihar/CWC warnings for decisions.

## Run locally

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_lan.ps1
```

For phone access, connect the computer and phone to the same trusted Wi-Fi and open the LAN URL printed by the launcher. Do not expose the development server to the public internet. See [LAN operations and safety](./OPERATIONS.md#lan-and-phone-access).

## Data sources, licenses, and attribution

| Source | Used for | License / terms and attribution |
|---|---|---|
| OpenStreetMap | Natural map tiles, place search, regional Overpass lookup for health, safety, water, fuel, transport, and daily-needs categories, plus one small central-Patna sample pack | © OpenStreetMap contributors; Open Database License (ODbL). [Attribution and license](https://www.openstreetmap.org/copyright). Nearby listings include source links, available OSM edit time, retrieval time, and a “Map data · may be outdated” trust label. The sample pack is not city- or district-wide coverage. |
| Nominatim | Place search/geocoding | OpenStreetMap-derived database; comply with its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) and ODbL attribution. |
| Open-Meteo Historical Weather / Flood APIs and point Forecast API | Patna model inputs and a cached, hourly/daily point weather forecast | Weather/reanalysis and flood model products, not Patna gauge observations. Forecast attribution: “Weather data by Open-Meteo.com”; see [license](https://open-meteo.com/en/licence) and [API terms](https://open-meteo.com/en/terms). Free API terms are for non-commercial use; replace/configure a suitable provider plan for commercial deployment. |
| GloFAS / Copernicus | Modeled river discharge distributed through the Open-Meteo Flood API | Model output, not a local observed gauge. Follow the [GloFAS/Copernicus access and reuse terms](https://global-flood.emergency.copernicus.eu/). |
| IIT Delhi HydroSense Lab, India Flood Inventory with Impacts, Zenodo record 16994648 | Historical event labels and district context | Record metadata lists **CC BY-NC 4.0**. Cite Saharia et al. and the [dataset DOI](https://doi.org/10.5281/zenodo.16994648); non-commercial terms apply. |
| CivicDataLab, Bihar Sub-District Level Flood Inundation (2021–2025) | Bundled monthly district/sub-district inundation context | Dataset lists **CC BY-SA 4.0**. Attribute CivicDataLab; review share-alike requirements before redistribution. [Dataset](https://civicdataspace.in/datasets/2c10ed21-6f6b-4f58-83dc-5406fb048e25). |
| OSRM public routing service | Road geometry and estimated route time | Public demo routing service; not a closure or flood-safety feed. Follow [OSRM project terms](https://project-osrm.org/) and service provider policy. |
| Optional satellite tile provider | Background imagery only | Provider and license depend on the deployment's `SATELLITE_TILE_URL`; verify and display its attribution before enabling. Imagery is not a flood classifier. |
| Aegis-trained model and local demo logic | Research score, scenarios, and demo action flows | Generated/implemented by this project from the above data; no independent operational validation or additional sensor source. Demo fallback behavior must remain labeled. |
| Optional gauge, satellite imagery, and user reports | Only when configured, available, or submitted | No official live gauge feed is configured by default. User reports are unverified and crowd signals do not alter the model risk estimate. |

### Real data vs. DEMO data

- **Real/source-backed:** bundled Patna-area Open-Meteo/GloFAS training series, the cited event and inundation datasets, live-on-request OpenStreetMap tiles/geocoding/Overpass listings, and OSRM route geometry when the service responds. Source timestamps/coverage vary; a mapped resource is not confirmed open or available.
- **DEMO/illustrative:** seeded or synthetic response workflows, microgrid/drone/SOS examples, simplified rainfall/river sliders, generic fallback scores, non-navigable straight-line route fallback, and training/exercise records. Demo controls are labeled. No demo number is a real incident or sensor reading.
- **Not operationally validated:** model probabilities, flood-depth road closure avoidance, resource capacity, shelter availability, and emergency dispatch. The persistent prototype disclaimer is intentional.

See [data notes](./data/README.md), [operations and safety](./OPERATIONS.md), and the [honest limits slide](./docs/honest-limits.md).

See the maintained [source register](./data/SOURCES.md) for what is currently used, candidate sources that are not integrated, attribution, and coverage limits. The resource browser queries nearby OpenStreetMap data and offers categories such as clinics, blood-donation points, ambulance stations, fire services, water, transport, and daily needs. A single small central-Patna sample pack is included; this is not a nationwide facility registry. The Forecast button now opens a separate Open-Meteo point forecast and Aegis estimate; no official-warning feed or spatial forecast layer is connected.

### Build a regional offline resource pack

The repeatable OSM pack builder creates a compressed GeoJSON and quality report from a small, user-supplied bounding box. Keep each box within the intended Indian region; the builder does not verify national borders or infer missing points. Large areas must be tiled. The app lists packs placed under `data/region-packs/`, shows their size, and caches an explicitly downloaded pack for offline retrieval.

```powershell
python scripts/build_osm_region_pack.py --region-id my-area --bbox <south>,<west>,<north>,<east>
```

The Overpass request requires an internet connection and may be rate-limited. No nationwide pack is bundled. Review ODbL obligations before redistributing generated data; a downloaded map listing is not evidence that a facility is open or available.
