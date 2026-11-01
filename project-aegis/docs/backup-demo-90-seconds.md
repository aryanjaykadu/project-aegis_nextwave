# 90-second backup demo: Project Aegis

## Recorded-video shot list and narration

| Time | Shot | Narration |
|---|---|---|
| 0–10s | Open on Patna map; include the OSM attribution and persistent disclaimer. | “Project Aegis is a software-only research prototype for flood-data awareness—not an official warning or dispatch system.” |
| 10–24s | Open Monitor; show source health and the estimate card. | “The estimate is uncalibrated. We show the inputs and data coverage, and distinguish modeled discharge from a local gauge.” |
| 24–38s | Open Plan; adjust one model-backed slider and compare current vs. simulated result. | “This is a what-if simulation inside the training ranges, not a forecast. If current data is missing or outside support, the app withholds it.” |
| 38–50s | Open the share card; show freshness and rounded location before export. | “The share card carries source freshness, approximate location, and the prototype disclaimer.” |
| 50–64s | Open Respond; show nearest cached OSM listing and route warning. | “A mapped facility is not verified open, and the road route is not checked against flood depth or closures.” |
| 64–76s | Open Community; show an unverified report, report-as-false, and expiry state. | “Crowd reports are separate from official alerts and never change the model estimate.” |
| 76–90s | Turn on airplane mode; reopen Emergency Mode and show Call 112, cached resources, SMS draft flow. | “Core emergency actions are available offline. SMS opens a draft for the user to review; no help is claimed to be dispatched.” |

## Offline demo path

1. Before recording, open the app online once so the service worker can cache the app shell and static assets. Load the Patna map and nearest-resource results once if you want to show cached resources. Avoid describing cached facilities as available.
2. Keep the computer/server on the same LAN for the live demo, or use the recording if Wi-Fi is not reliable. The offline emergency screen itself uses local UI and cache; live estimate, geocoding, fresh OSM lookup, and server report submission still need a working server/network.
3. If demonstrating offline mode live, use browser DevTools’ Offline toggle or airplane mode only after confirming the app shell loaded. Show the offline banner, cached resource empty/stale messaging, and queued report state. Do not imply the server received a queued report until the UI says SENT.
4. Do not submit a real emergency report as part of the demo. Use an explicitly labeled demo observation only when the demo backend is configured for it.

## Recording notes

- Use the default Patna target and show the full prototype notice.
- Keep personal phone numbers and exact device location out of frame.
- Do not stage a fake confirmed report, live gauge, responder dispatch, open shelter, or safe route.
- Do not claim physical-iPhone performance or offline behavior unless separately tested on that device.
