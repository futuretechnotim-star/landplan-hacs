# LandPlan HACS Integration

## Project overview

Home Assistant custom integration for [LandPlan.app](https://landplan.app), distributed via HACS. It surfaces LandPlan data inside HA and (eventually) fuses it with near-real-time data from smartfarmview.com for a kiosk-style Lovelace dashboard.

**Three-tier architecture — each tier has one job:**

| Tier | Role |
|---|---|
| LandPlan.app | System of record. Slow-moving, durable, authoritative. Owns the spatial model, object identity, plans, and the task/activity schedule. |
| smartfarmview.com | Real-time read model. Owns live camera feeds, drone/robot footage, and the navigable Street View experience. Projects LandPlan's truth and layers motion on top. (Currently conceptual — public repo focuses on mesh security cameras.) |
| HA integration | Consumer only. Reads from LandPlan (slow/authoritative data) and smartfarmview (constantly-refreshed views). Chooses source per card. |

**Governing principle:** The integration is a *reader* of both sources, never the synchronizer. It must never write back to either source except through deliberate "promotion" actions (out of scope for v0.1).

---

## Repository layout

```
custom_components/landplan/
├── __init__.py            # setup, coordinator wiring, card JS static path registration
├── manifest.json          # domain, version, codeowners, etc.
├── config_flow.py         # auth step + plan dropdown + options flow (node mapping)
├── coordinator.py         # slow LandPlan DataUpdateCoordinator
├── api.py                 # thin client — all LandPlan HTTP calls live here
├── calendar.py            # project activities as HA calendar (today's tasks)
├── camera.py / image.py   # photo-point images + timestamps
├── sensor.py              # task-count/status summary, "minutes since last photo"
├── device_tracker.py      # node/dock positions (or geo_location.py)
├── const.py
└── www/
    └── smartfarmview-snapshot-card.js   # Lovelace card — served at /landplan/smartfarmview-snapshot-card.js
hacs.json                  # repo root — HACS metadata
README.md                  # repo root — user-facing setup guide
brand/icon.png             # required by HACS
docs/                      # requirements and design notes
```

**HACS hard rule:** only one subdirectory under `custom_components/`. Adding a second breaks HACS management.

---

## Design rules

### Bundled Lovelace card
`www/smartfarmview-snapshot-card.js` ships inside the integration directory. `async_setup()` in `__init__.py` registers it as a static path at `/landplan/smartfarmview-snapshot-card.js` and injects it into `frontend_extra_module_url` so HA loads it automatically — no manual resource registration in Lovelace settings needed.

Card config:
```yaml
type: custom:smartfarmview-snapshot-card
camera_entity: camera.landplanmesh1_camera
button_entity: button.landplanmesh1_capture_snapshot
title: Field Node 1        # optional
```

### All HTTP calls go through `api.py`
Never call LandPlan endpoints directly from platform files (`calendar.py`, `sensor.py`, etc.). The integration depends on a private API (same endpoints as the iOS app) that can change without notice. Isolating calls in `api.py` means a breaking change is a one-file fix.

### Two coordinator tiers
- **Slow coordinator** (`coordinator.py`) — polls LandPlan every few minutes: plans → projects → activities → map objects. This is the only coordinator in v0.1.
- **Fast coordinator** (future) — seconds or push (websocket/SSE) for smartfarmview live state: camera snapshots, battery, trigger events, robot position. Not built until smartfarmview's real-time transport is confirmed.

### Object identity
LandPlan map objects carry stable IDs (e.g. `cmpexjm31...`) and `updatedAt` timestamps. smartfarmview treats these as **foreign keys, never forks**. Physical devices (camera nodes, mesh nodes, robot dock) are modeled once as LandPlan map objects and carry LandPlan IDs. No reconciliation logic anywhere in the integration.

### Node discovery via tags
The integration discovers physical devices by filtering map objects on LandPlan tags:
- `camera-node` — mesh security camera
- `mesh-node` — mesh network node
- `robot` — robot dock / home position

An options flow then binds each discovered node to a matching HA entity (auto-match where `label` == entity name).

> **Step zero before node discovery can be tested:** the Smart Forest plan currently has no tagged device map objects. Add `camera-node` / `mesh-node` / `robot` tagged objects to the plan first.

### smartfarmview fallbacks
smartfarmview is still conceptual. Every panel or entity that is intended to show live smartfarmview data **must** have a LandPlan-direct fallback or a placeholder so the integration ships and works today. Real-time panels light up as smartfarmview matures.

### Config entry stores
`{ token, planId }` — HA encrypts config entry data at rest. Multiple config entries must be supported so each plan can be its own HA instance / dashboard. The device-mapping table lives in the options flow (not the initial config flow).

---

## Authentication

Auth method is **TBD** — see Open Questions below. Two options under consideration:
- **API token** — paste into config flow. Simpler, ship first.
- **OAuth2** — via HA's `config_entry_oauth2_flow` helpers if LandPlan exposes a client.

### Test account plan IDs

| Plan | ID |
|---|---|
| Smart Forest, LLC | `cmn1uj27z00023l906e4qpuok` |
| MacArthur Home | `cmnai1oy80006imepbm1y51mr` |
| Maui Surf Shack | `cmojgegfv0002tj5dhqyisu95` |

---

## HACS packaging checklist

**`hacs.json`** (repo root):
```json
{
  "name": "LandPlan",
  "render_readme": true,
  "homeassistant": "2024.1.0"
}
```

**`manifest.json`** (inside `custom_components/landplan/`):
```json
{
  "domain": "landplan",
  "name": "LandPlan",
  "version": "0.1.0",
  "documentation": "https://github.com/futuretechnotim-star/landplan-hacs",
  "issue_tracker": "https://github.com/futuretechnotim-star/landplan-hacs/issues",
  "codeowners": ["@futuretechnotim-star"],
  "requirements": [],
  "iot_class": "cloud_polling",
  "config_flow": true
}
```

**Other requirements:**
- Repo must be **public** on GitHub with a description (shown in HACS)
- `brand/icon.png` required
- Use full **GitHub Releases** for version tracking — plain tags alone are not enough

---

## Development workflow

**Fast iteration:**
```bash
# Symlink integration into a local HA dev container
ln -s $(pwd)/custom_components/landplan \
  /path/to/ha-config/custom_components/landplan
```

**First platform to implement:** `calendar.py` — today's activities from the tasks API. This is the simplest end-to-end proof because the tasks/activities data is already reachable via documented/MCP endpoints.

**Build order after that:**
1. `sensor.py` — task count/status summary
2. `camera.py` / `image.py` — photo-point images
3. `device_tracker.py` — node positions

**Validation before any default-store submission:**
- Run the [HACS Action](https://github.com/hacs/action) against the repo
- Run `hassfest` (HA's integration validator)

**Install via HACS custom repository:**
HACS → three-dot menu → *Add custom repository* → paste repo URL → category *Integration* → install → restart HA → Settings → Devices & Services → Add Integration → LandPlan.

---

## Open questions

Before coding key modules, resolve these (full context in [docs/requirements-hacs.md](docs/requirements-hacs.md)):

1. **LandPlan auth method** — token vs. OAuth2. What does the iOS API actually use?
2. **Private vs. documented API surface** — which endpoints are stable? Tasks work via MCP; what else?
3. **smartfarmview real-time transport** — websocket, SSE, or polling? Determines fast coordinator design.
4. **smartfarmview sync mechanism** — delta poll on `updatedAt` vs. webhooks from LandPlan.
5. **Tag vocabulary finalization** — confirm `camera-node` / `mesh-node` / `robot` and whether device metadata goes in the map object `metadata` field.
6. **Rate limits / quotas** on LandPlan API for polling cadence.
