# Additive feature walkthrough

## 60-second judge demo

1. **Monitor (0–12 s):** point at the research estimate, expand “Why this estimate?”, and show the observed inputs, global feature weights, source freshness, confidence formula, and prototype disclaimer.
2. **Plan (12–24 s):** show the original sliders as a clearly marked DEMO. After a current Patna scan, adjust a model-backed input and compare its 24/48/72-hour output with the scan; note that the point model does not update a flood polygon.
3. **Situation Card (24–34 s):** create the PNG and share sheet, show source freshness and up to three resources cached for that same rounded location, then show the privacy-rounded link and disclaimer.
4. **Respond/Layers (34–46 s):** find the nearest OpenStreetMap facility, show straight-line distance and road ETA when OSRM responds, then share a route link. State that routes are not checked against flood depth or closures.
5. **Community (46–60 s):** show the no-data state or submit a real observation, then demonstrate confirmation/dispute controls, crowd-trust badge, and delete action. If practical, disable the network first to show Pending and retry; never invent reports.

## Sources and attribution

- **OpenStreetMap / Overpass:** live facility listings, including the new water, fuel, and market tags. Attribute as “© OpenStreetMap contributors · ODbL”. OSM listings are incomplete and do not establish opening status or capacity. Review ODbL and provider usage limits before deployment.
- **OSRM public routing service:** standard road geometry only. The route response is not checked against flood depth or road closures. The straight-line fallback is explicitly marked non-navigable.
- **Existing model sources:** Open-Meteo weather and Flood API modeled discharge; the local Patna training CSV and sparse IIT Delhi India Flood Inventory labels. The new what-if bounds are computed from the CSV’s observed training ranges; the model output remains uncalibrated.
- **Historical inundation:** CivicDataLab, Bihar Sub-District Level Flood Inundation (2021–2025), CC BY-SA 4.0; district aggregate only, not a point-level forecast.
- No hardware feeds or new hazard datasets were introduced. The model-backed what-if reuses the existing trained model and inputs.

## Real data, local input, and limitations

- OSM results are live when Overpass responds and otherwise may come from a timestamped browser cache. Users should confirm facilities directly.
- Community reports are user-submitted, location-rounded to three decimal degrees, initially unverified, and rate-limited. Crowd trust is only a bounded heuristic based on confirmations/disputes, pseudonymous browser history, and age; it is not identity verification or official validation. One browser can still create multiple identities. Abuse flags are stored for moderator review; they do not automatically reject reports.
- Optional images are resized to 720 px maximum dimension and compressed to JPEG under 100 KB before upload. They are community evidence, not analyzed by a vision model.
- Confidence is a data-coverage indicator capped at medium, not statistical model confidence. Independent source agreement is explicitly unassessed. Provider timestamps for modeled river discharge are not retained by the current adapter, so that source is labeled stale/unverified.
- The model-backed what-if accepts only trained numeric features, uses min/max bounds from the local training data, and is withheld outside approximate Patna coverage or when a scan input is outside those bounds. The legacy simplified scenario remains available as DEMO and is not the trained model.
- “Safer route” output is intentionally unavailable until authoritative, time-stamped flood depth and road-closure geometry can be integrated. Current route overlays must not be used for emergency navigation.
- Scan history, pending community submissions, and resource/route caches are local to the browser. “Delete my reports” clears the local community queue immediately; server records associated with the browser’s pseudonymous reporter token require a connection. Clearing browser storage also discards that token.
- The feature-copy catalog is `frontend/aegis-translations.js`; English is the fallback and Hindi entries cover feature labels and controls. Dynamic status messages and safety-critical source wording may remain English and should be reviewed by a native speaker before operational use.

## Verification notes

Run the browser queue tests with `node --test tests/aegis-offline-queue.test.cjs` and the Python suite with `python -m pytest`. A real iPhone Safari FPS/offline measurement requires a physical iPhone and Web Inspector; desktop/mobile browser emulation is not a substitute.
