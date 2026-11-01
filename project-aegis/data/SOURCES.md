# Project Aegis source register

This register distinguishes sources currently used by the app from candidates that have not been integrated. A URL or a category listing is not evidence that a feed is complete, current, or suitable for emergency decisions. Last reviewed: 2026-11-01.

## In-app data sources

| Source | Current use | Access and coverage | License / attribution | Known limits |
|---|---|---|---|---|
| OpenStreetMap | Nearby mapped facilities via Overpass, map tiles, place search, and one small central-Patna sample pack | Nearby queries are regional. The included `patna-core` pack covers only 25.55–25.64°N, 85.08–85.20°E; built 2026-11-01 with 1,065 mapped features (59,784 compressed bytes). | ODbL. Attribute **© OpenStreetMap contributors** and link to [copyright / license](https://www.openstreetmap.org/copyright). | This is not all of Patna. In the retrieved sample, 421/1,065 features have no name and Overpass supplied no last-edit timestamp for 1,065/1,065; retrieval time is present. 8 returned elements were excluded for invalid/out-of-box coordinates or missing IDs. Community map data can be missing, duplicated, stale, or misclassified. A listing is not evidence of opening status, capacity, safety, or availability. |
| Open-Meteo | Existing scan inputs use forecast and flood APIs; the added point forecast endpoint requests hourly and daily weather values and caches rounded grid coordinates for 15 minutes | Forecast API at [api.open-meteo.com](https://api.open-meteo.com/v1/forecast); point values are not a gridded map layer | [Open-Meteo attribution and license](https://open-meteo.com/en/licence); show “Weather data by Open-Meteo.com”. The free API terms restrict use to non-commercial purposes; [terms](https://open-meteo.com/en/terms). | Model output, not station readings. Provider response does not expose a model run timestamp or uncertainty range in the fields currently requested. Commercial deployment needs a compatible plan/provider. |
| GloFAS / Copernicus modeled discharge | Modeled discharge may be used in the existing Patna research model through the Open-Meteo Flood API | Grid/model-derived data; no default live Patna gauge feed | Follow the source/product license and attribution obligations through [Copernicus GloFAS](https://global-flood.emergency.copernicus.eu/). | Not a local observed gauge. |
| IIT Delhi HydroSense Lab India Flood Inventory with Impacts | Sparse Patna event labels and contextual training data | Project's local dataset snapshot; see [dataset DOI](https://doi.org/10.5281/zenodo.16994648) | Current Zenodo record lists CC BY-NC 4.0; cite the researchers and review non-commercial conditions before redistribution. | Incomplete inventory; absence of a listed event is not evidence that no flood occurred. |
| CivicDataLab Bihar inundation | Local historical monthly district/sub-district context | Bundled local dataset; source record at [CivicDataSpace](https://civicdataspace.in/datasets/2c10ed21-6f6b-4f58-83dc-5406fb048e25) | Listed CC BY-SA 4.0; retain attribution and review share-alike terms. | Historical aggregate only; not a current image, point classification, forecast, or national coverage layer. |
| OSRM public routing service | Road geometry and travel-time estimates when the public router responds | Public routing endpoint; see [OSRM project](https://project-osrm.org/) | Follow the actual router provider's service policy and data attribution. | Not flood-aware and does not verify closures or safe passage. |

## Candidate sources not yet integrated as nationwide datasets

These are not presented as app coverage. Verify current access, file date, geographic completeness, field definitions, terms, attribution, and legal compatibility before building redistributable packages.

| Candidate | Intended use | Verification / decision |
|---|---|---|
| [Geofabrik India extract](https://download.geofabrik.de/asia/india.html) | Regional OSM data pipeline | Page checked 2026-11-01. It advertised a roughly 1.6 GB India PBF updated daily and regional downloads. Not downloaded or bundled: national file size, update pipeline, and ODbL derivative obligations require a separate deployment design. |
| data.gov.in health directories and PIN code directory | Official facility names, attributes, and possible geocodes | Not ingested. Verify the current dataset/API release, coordinates, “as on” date, GODL terms, and record-level completeness. Do not treat address geocoding as exact coordinates. |
| Aikosh and state health portals | Potential health-facility datasets | Not ingested. Dataset versions and reuse conditions need per-resource verification. |
| data.opencity.in police datasets | City-specific police locations | Not ingested. Verify the license and publication date for each city file; no national geocoded official police dataset is claimed. |
| Jan Aushadhi locator / PIB counts | Facility lookup or coverage checks | Not ingested. Counts do not provide point locations; verify locator access and terms before use. |
| State disaster-management shelter and relief-camp lists | Official or extracted shelter points | Not ingested. No single national open shelter dataset is claimed. Any school/community-center fallback must be labeled “possible, not confirmed.” |
| CWC Flood Forecasting Services / India-WRIS | Official river and flood observations/warnings | Not connected by default. Access, station coverage, formats, and terms may vary; no live gauge values are claimed. |
| IMD gridded, observed, and warning products; NDMA SACHET | Rainfall and official hazard warnings | Not connected by default. Verify terms and feed access before implementation; official warnings must remain separate from modeled outputs. |
| GPM IMERG / CHIRPS | Satellite or gridded precipitation | Not currently part of the app forecast endpoint. Check product-specific licenses, resolution, access, and temporal availability before adding. |
| Global Flood Database / Sen1Floods11 / Prithvi flood model | Flood labels or future water-detection model | Not used for the current model or UI. Verify each dataset license separately from model license and perform Indian spatial/temporal validation before displaying derived results. |
| NASA Global Landslide Catalog, NCS earthquake catalogue, BIS seismic zones, IBTrACS/IMD cyclone tracks, WorldPop/GHSL, SRTM/Copernicus DEM, Bhuvan layers | Future hazard and susceptibility features | Not integrated. Terms, access, update schedule, boundary policy, and model validation remain unverified. |

## Coverage and quality limits

- The current trained susceptibility-related model is a Patna-area point model, not an India-wide susceptibility map.
- The current facility browser queries OSM around the target. One small central-Patna OSM sample pack is included; there are no national region packs, comprehensive facility coverage, or official-status feed.
- The forecast endpoint is a selected-point weather forecast. It does not create a flood forecast, spatial map overlay, official warning, or flood-depth estimate.
- When a requested category has no local results, the app must report that no mapped result was found; it must not imply the facility does not exist.
