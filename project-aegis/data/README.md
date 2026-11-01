# Flood model data and limits

## What the current model uses

The research model is trained on daily Patna-area weather and river-discharge history from the Open-Meteo Historical Weather Archive and Flood APIs, joined with documented Patna district flood events in the IIT Delhi HydroSense Lab India Flood Inventory. Features include daily precipitation, 7-day antecedent precipitation, soil moisture, river discharge, and month-of-year seasonality. Positive labels mark a documented Patna event that is active or begins in the following 24, 48, or 72 hours.

The event inventory is sparse: a date not listed is **not proof that no flood happened**. The weather series is one model grid point, and the event inventory is not a complete local gauge record. Model probabilities are uncalibrated and are **not operationally validated**. Treat outputs as research/demo estimates only; use official Bihar and CWC warnings for decisions.

## Bihar satellite inundation reference

`bihar_subdistrict_inundation_2021_2025.csv` contains monthly satellite-mapped inundation statistics by sub-district from CivicDataLab's Bihar Sub-District Level Flood Inundation dataset. The UI aggregates Patna district map IDs into a weighted district-wide inundated-pixel share for historical context. This is not a live satellite classification, not point-specific, and not used as daily training labels because monthly area summaries do not identify event timing. The dataset is listed as CC BY-SA 4.0; retain attribution and review share-alike obligations before redistribution.

## Rebuild and train

Download the India event inventory and district context tables:

```powershell
python scripts/download_public_datasets.py
```

Fetch the Patna weather/discharge series, attach documented event labels, and train the Extra Trees model:

```powershell
python scripts/build_patna_dataset.py
python scripts/train_model.py
```

Once the weather series is present, rebuild labels without network access:

```powershell
python scripts/build_patna_dataset.py --offline
```

## Sources

- IIT Delhi HydroSense Lab, [India Flood Inventory with Impacts, Zenodo v4 record](https://zenodo.org/records/16994648), DOI [10.5281/zenodo.16994648](https://doi.org/10.5281/zenodo.16994648). It documents India flood events sourced from IMD, 1967–2023, and supplies a district flood severity index, flooded-area table, and impact table. The current record metadata lists **CC BY-NC 4.0**; cite the researchers and review the non-commercial terms before reuse. Earlier versions may have different terms.
- Open-Meteo [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) and [Flood API](https://open-meteo.com/en/docs/flood-api). Daily precipitation and soil moisture are reanalysis/model data; discharge is GloFAS-modeled discharge, not an observed Patna gauge reading. Follow Open-Meteo attribution and terms for your use case.
- Government of Bihar FMISC [Flood Management Information System](https://www.fmiscwrdbihar.gov.in/), [Bihar Disaster Management GIS](https://gis.bihar.gov.in/DEPTS/Disaster.aspx), and [ISRO/NRSC flood products](https://www.isro.gov.in/SpaceBasedEarthObservationServices.html) are stronger future sources for local gauge, inundation, shelter, and road validation. Several products require portal access or registration.
- CivicDataLab, [Bihar Sub-District Level Flood Inundation (2021–2025)](https://civicdataspace.in/datasets/2c10ed21-6f6b-4f58-83dc-5406fb048e25), monthly satellite inundation summaries for Bihar sub-districts, listed under CC BY-SA 4.0. The downloader retrieves the public resource through CivicDataSpace's dataset API.

`patna_training_metadata.json` records the retrieval settings, source, coverage, and label caveat. The source CSV files are retained in this directory for reproducibility. The previous nonlocal training artifact and heuristic-label training flow have been removed.
