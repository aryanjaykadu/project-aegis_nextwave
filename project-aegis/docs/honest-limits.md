# Honest limits — judge slide

## What this app can show

- Source-backed historical context and available model inputs for a Patna-area research experiment.
- An uncalibrated model score and a simulation using supported inputs; neither is an official forecast.
- Nearby OpenStreetMap listings and route geometry when services respond, plus locally cached data.
- User-submitted observations that remain unverified until enough independent review and are never treated as official alerts.

## What it cannot do

- Issue official warnings, detect flooding from hardware, dispatch responders, send SMS automatically, or confirm that anyone received help.
- Verify current road closures, flood depth, shelter capacity/open status, hospital services, or facility availability.
- Guarantee a fresh feed while offline. Cached data can be old; source timestamps must be checked.
- Offer reliable street-level risk. The model is single-point, sparse-label, uncalibrated, and not operationally validated.

## Thin and uncertain data

- The overlapping Patna training record has 3,287 daily feature rows and 14 documented event windows; the source inventory is incomplete and an unlisted date is not a flood-free observation.
- Weather and river discharge are gridded/model data. The modeled discharge is not a Patna gauge reading; no authorized live gauge feed is configured by default.
- Bihar satellite inundation is a monthly, sub-district historical summary, not live classification or a point-level flood map.
- OpenStreetMap resources may be missing, duplicated, stale, closed, or misclassified. OSRM geometry is not flood-aware.
- Community signals can be mistaken, coordinated, disputed, or old. Crowd trust is not independent verification.

## Safety and official sources

This is a research prototype, not an official alert or emergency service. Use India’s emergency number **112** when appropriate and consult official Bihar Disaster Management/FMISC and Central Water Commission warnings. The app does not provide false reassurance and does not label a route safe.

Source detail: [Bihar FMISC](https://www.fmiscwrdbihar.gov.in/), [CWC](https://cwc.gov.in/), [India emergency response support system](https://112.gov.in/), [OpenStreetMap attribution](https://www.openstreetmap.org/copyright). Verify official instructions and contacts for the current locality.
