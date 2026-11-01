# Who Project Aegis helps — and why

## A clearer starting point for local preparedness

Residents, campus teams, and local relief planners around Patna need to answer practical questions quickly: what source is this estimate based on, how old is the information, where are mapped services, and what can still be done if the connection drops? Project Aegis brings source status, an explicitly uncalibrated research estimate, privacy-rounded community observations, and cached map context into one map-first interface. It helps people inspect information and prepare; it does not dispatch help or decide whether a route or area is safe.

The limits are part of the story. The current Patna training series contains **3,287 daily feature rows** and only **14 documented Patna event windows** in the overlapping weather period, according to the project’s training audit and [IIT Delhi HydroSense Lab’s India Flood Inventory](https://doi.org/10.5281/zenodo.16994648). Those are dataset counts, not a count of all floods, affected people, or lives saved. A missing inventory event is not evidence that no flood occurred. The model is uncalibrated, single-point, and not operationally validated. Its purpose here is to make uncertainty and input coverage visible—not to provide reassurance.

The app also shows nearby places from OpenStreetMap when available. They are map listings, not verified open facilities. A cached list can be stale. Road geometry does not know current water depth or closures. Community reports stay visibly unverified, expire visually, and never raise or lower the research estimate.

## Data-to-screen architecture

```text
Open-Meteo weather + GloFAS modeled discharge
                 │
                 ▼
       Patna research model ─────► Estimate + input coverage
                 │                         │
IIT Delhi IFI ───┴──► training context     ├──► Monitor / Plan
                                           │
OSM tiles + Nominatim + Overpass ──────────┼──► Map / Resources
OSRM route geometry ───────────────────────┤
                                           │
Community user input ─► local offline queue┴──► Community (unverified)
                                                  │
Browser local storage ◄── cached app shell,      └──► Reports API when online
                          settings, saved places,
                          rounded scan/report data

All screens retain: “Research prototype · not an official alert.”
```

### Sources for the claims

- Training counts and model limitations: [Project data notes](../data/README.md) and [Operations notes](../OPERATIONS.md#flood-model).
- Event inventory source: Saharia et al., IIT Delhi HydroSense Lab, [IFI-Impacts, DOI 10.5281/zenodo.16994648](https://doi.org/10.5281/zenodo.16994648), CC BY-NC 4.0 per current Zenodo record.
- Map source and license: [OpenStreetMap copyright and ODbL attribution](https://www.openstreetmap.org/copyright).
- Monthly inundation context: CivicDataLab, [Bihar Sub-District Level Flood Inundation](https://civicdataspace.in/datasets/2c10ed21-6f6b-4f58-83dc-5406fb048e25), listed CC BY-SA 4.0.
