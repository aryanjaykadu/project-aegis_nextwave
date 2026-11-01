# Aegis deployment and data-trust notes

## Local demo versus operations

The app defaults to local demo mode. Until authoritative feeds, authentication, and local validation are configured, it is not an emergency dispatch or evacuation authority. Generated SOS, microgrid, detour, and economic-loss layers are labeled as illustrative. Satellite display is imagery only; no image classifier is connected.

## Authentication setup

1. Set `AEGIS_AUTH_ENABLED=true` and a random `AEGIS_AUTH_SECRET` of at least 32 characters in the deployment environment.
2. Run `python scripts/hash_password.py` for each operator and copy the emitted PBKDF2 hash into `AEGIS_USERS_JSON`, for example: `{"operator":{"password_hash":"pbkdf2_sha256$...","role":"admin"}}`.
3. Restart the service and verify `/api/auth/status`. Log in at `POST /api/auth/login`; send the resulting bearer token to protected write endpoints.
4. Public incident reports remain available without an operator login. Operator incident updates, responder/resource/shelter registration, alert creation, and outbound notifications require a role token when auth is enabled.

The UI now has an operator sign-in control. Tokens are kept in `sessionStorage` for the current browser tab and attached to same-origin API calls. Sign out when the device is shared. Live alert submission is blocked unless authentication is enabled, a different authenticated operator approves the draft, and an administrator submits it. A successful Twilio API response means **accepted by provider**, not delivered to or read by a recipient; delivery receipts need a separately configured Twilio status callback before they can be reported.

`AEGIS_LAN_MODE=true` disables demo operator privileges even for local access. Without authentication, requests from non-loopback clients cannot use responder/admin endpoints. Keep this setting on for a LAN deployment. CORS uses exact origins from `AEGIS_ALLOWED_ORIGINS`; wildcard origins are rejected. Same-origin phone access does not need a CORS exception.

Do not commit `.env`, auth secrets, password hashes, or provider credentials. Configure secrets in the host's secret store for production.

## Flood model

`models/aegis_rf_model.pkl` contains separate 24/48/72-hour Extra Trees classifiers trained from Patna-area Open-Meteo weather and GloFAS discharge history, with positive windows derived from documented Patna events in IIT Delhi's India Flood Inventory. Training data has 3,287 daily rows and 14 documented Patna events in the weather period. Exploratory year-grouped cross-validation produced ROC-AUC about 0.80/0.78/0.75 and average precision about 0.041/0.048/0.052, against event-window prevalence of 0.013/0.017/0.020. At the uncalibrated 0.5 threshold, event precision was only about 0.04/0.05/0.06 and recall 0.30/0.35/0.36. This is a modest ranking signal, not useful stand-alone alert precision or operational validation. Unlisted inventory dates are not guaranteed flood-free, and probabilities are uncalibrated. Always consult official Bihar and CWC warnings.

The live model fills missing features from training medians when the local weather/discharge provider cannot supply them; `/api/trigger` returns provider availability. The district flood severity and impact tables are reference context, not model targets. Improve this model only with traceable Patna/Bihar gauge observations, mapped inundation labels, and independent temporal/spatial validation.

## External providers and route safety

- `GAUGE_FEED_URL` accepts a configured JSON gauge feed. No feed is configured by default.
- A gauge feed must use HTTPS and return either an array or `{"gauges": [...]}`. Each usable reading needs `lat`, `lon`, `level_m`, and an ISO-8601 `observed_at` timestamp with a timezone; `id`/`station_id` and `source` are recommended. Readings older than `GAUGE_MAX_AGE_HOURS` (default 12) are marked stale and are not silently made fresh.

Example shape only (replace with an authorized provider response; these values are placeholders):

```json
{
  "gauges": [
    {
      "id": "PROVIDER-STATION-ID",
      "lat": 25.59,
      "lon": 85.14,
      "level_m": 0.0,
      "observed_at": "2026-01-01T00:00:00Z",
      "source": "Authorized gauge provider"
    }
  ]
}
```
- Twilio variables enable SMS delivery. No real message is sent in local mode.
- Voice calls are disabled unless an explicitly approved call is requested and both authentication and `AEGIS_ENABLE_LIVE_VOICE=true` are configured. The browser-based “disaster report” helper does not submit to a government authority; no such provider integration is configured.
- `SATELLITE_TILE_URL` controls a background imagery provider; imagery is not flood classification.
- OSRM routes are road geometry only and are not checked against live closures or flood depth. Straight-line fallback is neither navigable nor verified safe.
- Offline incident reports are stored in browser local storage and retried with idempotency keys. Map tiles and geocoding still require network access.
- `/api/evidence-timeline` combines dated inventory entries, monthly district inundation summaries, and submitted Aegis reports. It aligns records by date only; it does not calculate overlap, causality, street-level extent, or a flood replay.

## Persistent data

Operational entities use SQLite at `data/aegis.db`. Back up this file while the service is stopped or use SQLite's online backup API. For multi-instance production deployments, migrate to PostgreSQL/PostGIS with managed backups and schema migrations.

## LAN and phone access

For same-Wi-Fi access, bind Uvicorn to `0.0.0.0` and open the host computer's LAN address from the phone. Keep `AEGIS_LAN_MODE=true`; configure authentication before responder actions are used. Do not expose the development server to the public internet. On a phone, a plain `http://192.168...` origin is not a secure context: geolocation and service-worker/PWA features may be unavailable. Use HTTPS with a certificate trusted by the phone (for example, a local development certificate installed on both devices) before evaluating those features. A self-signed certificate warning is not equivalent to a trusted secure context.

On Windows, connect the computer and phone to the same Wi-Fi, then run `powershell -ExecutionPolicy Bypass -File scripts/run_lan.ps1` from the project folder. The script starts the development server on port 8001, enables LAN safety mode, and prints the phone URL using an active network adapter (preferring Wi-Fi). Open that exact `http://<computer-LAN-IP>:8001/` URL on the phone; `localhost` and `127.0.0.1` on the phone refer to the phone itself, not this computer.

If the phone cannot connect, check that both devices are on the same non-guest network and that router client isolation is disabled. Windows Firewall may need a one-time inbound rule. In an elevated PowerShell, allow only local-subnet clients on the app port:

```powershell
New-NetFirewallRule -DisplayName "Project Aegis LAN (8001)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8001 -RemoteAddress LocalSubnet -Profile Any
```

Remove the rule when no longer needed with `Remove-NetFirewallRule -DisplayName "Project Aegis LAN (8001)"`. Do not expose this development server to the public internet. The script does not install a TLS certificate; plain HTTP may disable phone geolocation and service-worker/PWA features. Use HTTPS with a certificate trusted by the phone for those features.

## Repeatable judge walkthrough

1. Open the default Patna view and the source panel; explain each feed's scope and freshness.
2. Run the sample scan and point out that model outputs are uncalibrated research estimates.
3. Open the evidence timeline and compare a district event, a monthly district satellite summary, and a user report without interpreting them as the same measurement.
4. Submit a sample incident, then review it as an operator and leave it unverified until an authorized person checks it.
5. Create an alert draft; demonstrate approval separately. Use a test provider account only, and show “accepted by provider” as distinct from delivery confirmation.
6. Reset the demo view. Do not delete actual community reports as part of a demo reset.

## Release gate

- Run `python -m pytest` from the project root; tests use a temporary SQLite database and do not call live providers.
- Verify auth with configured admin, supervisor, and responder accounts; confirm unauthenticated LAN writes and audit/resource reads are rejected.
- Verify a trusted HTTPS origin on actual iOS and Android phones/tablets; test map gestures, offline incident queue and replay, keyboard/screen-reader controls, and reduced motion.
- Obtain permission and stable schemas for CWC/FMISC observations and dated NRSC flood extents before connecting those sources. Document timestamps, datum, station coordinates, licensing, outages, and historical revisions.
- Validate routes against authoritative closures and flood depth before describing any route as safe. Field-check shelters, accessibility, capacity, and phone numbers.
- Configure and test SMS callbacks, recipient consent, rate limits, delivery receipts, and operator audit retention before live alert use.
- Review all supported-language strings with native speakers, especially safety instructions. Unreviewed machine translation must not be presented as official guidance.
- Test backup restore, database migration, server restart, stale-feed banners, API provider outages, and Android/iOS offline behavior.

The bundled monthly inundation dataset cannot identify which streets or facilities were flooded, and no CWC/FMISC/NRSC live feed credentials are bundled. Therefore facility impact overlays against observed flood polygons, verified flood-safe routing, true live gauge trends, native-reviewed 22-language safety copy, trusted phone HTTPS certificates, and real-device performance measurements remain deployment/data-validation work—not synthetic features to be simulated.

## Hackathon package

- [Who this helps and why, with cited source counts and architecture](./docs/who-this-helps.md)
- [90-second recorded demo script and offline path](./docs/backup-demo-90-seconds.md)
- [Honest limits slide](./docs/honest-limits.md)
- [Addendum edge-case matrix](./docs/addendum-edge-case-matrix.md)
- [Data source/license table and real-vs-demo split](./README.md#data-sources-licenses-and-attribution)
