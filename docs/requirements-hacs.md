# LandPlan HACS Integration — Requirements

**Status:** Draft / conceptual
**Scope:** A Home Assistant custom integration (distributed via HACS) that surfaces LandPlan data, plus a kiosk-style Lovelace view that fuses LandPlan's authoritative data with near-real-time data from smartfarmview.com.
**Last updated:** 2026-05-29

---

## 1. Background and architecture

The system is a three-tier split. Naming each tier by its job drives the rest of the design decisions.

- **LandPlan.app — system of record.** Slow-moving, durable, authoritative. Owns the spatial model, object identity, plans, and the task/activity schedule. Long planning horizon.
- **smartfarmview.com — real-time read model.** Fast, fused, partly ephemeral. Owns live camera feeds, drone/robot footage, Insta360 stills/video, and the navigable "poor man's Street View" experience. It *projects* LandPlan's truth and layers motion on top. Currently conceptual; public repo today focuses on mesh security cameras.
- **HA integration + kiosk — consumer.** Pulls slow/authoritative data from LandPlan directly (e.g. today's task list via the same API the iOS app uses), and constantly-refreshed views from smartfarmview. Chooses the source per card.

**Governing principle:** The integration is a *reader* of both sources, never the synchronizer. The "must stay in sync" relationship lives entirely between LandPlan and smartfarmview. This keeps HA dumb, resilient, and easy to fix.

### 1.1 Object identity (the decision that governs everything)

LandPlan map objects already have stable IDs (e.g. `cmpexjm31...`) and an `updatedAt` timestamp on every object. Rules:

- smartfarmview treats LandPlan IDs as **foreign keys, never forks**.
- Physical devices (camera nodes, mesh nodes, robot dock) are modeled **once** as LandPlan map objects and carry LandPlan IDs.
- smartfarmview attaches live streams to those IDs.
- A kiosk marker is therefore identified the same way regardless of whether HA fetched it from LandPlan or smartfarmview. No reconciliation logic in the integration.

### 1.2 Sync direction and the "promotion" path

- **Primary flow:** LandPlan → smartfarmview, one-way, for the durable base model. Cheap delta poll or webhook keyed on `updatedAt`. Self-healing because LandPlan changes infrequently.
- **Write-back (the only one):** Selected real-time captures may be **promoted** into LandPlan as durable objects — a kept Insta360 panorama becomes a `photo_point`; a saved robot route becomes a `generic_line`. Promotion is deliberate, never automatic. The constant stream otherwise stays in smartfarmview and never pollutes LandPlan.

### 1.3 Reusing LandPlan object types for Street View

The existing LandPlan model maps onto "poor man's Street View" with little or no schema change:

- **`photo_point` + `photoHeading`** = a positioned, oriented image = a Street View node. Existing points already carry headings. Swap the flat photo for an Insta360 360° still and each point becomes a panorama anchor.
- **`generic_line` walking paths** (ordered coords + `distanceM` + `durationS` + `walkingPathId`) = the traversable "streets." Existing recorded traversals already exist (e.g. "Old trail hike," "Insta360 test").
- **Moving cams (robot, drone)** = ephemeral tracks that belong in smartfarmview's real-time layer, *not* durable LandPlan objects (optionally promoted to a saved line afterward).

---

## 2. Kiosk view: panels and data sources

The kiosk is a **separate deliverable** from the integration (a Lovelace dashboard / custom map card). Each panel declares its source.

| Panel | LandPlan provides | smartfarmview / HA-native provides | Primary source |
|---|---|---|---|
| Per-node camera + latest shot + minutes-since + battery % | Node position, label, documentation photo (`photoId` + `updatedAt`) | Live camera snapshot, battery sensor, live "minutes since" | smartfarmview (live) / LandPlan (doc photo fallback) |
| Map + blinking most-recently-triggered mesh node + its capture | Where each mesh node sits | Trigger event (`last_triggered`), capture snapshot | smartfarmview |
| Today's task list + status | Activities across plan's projects, filtered to today | — | **LandPlan-direct** |
| Robot location + current view | Base map, dock/home position | `device_tracker` position + onboard camera | smartfarmview |

**Note:** "Most recent shot + minutes since" is intentionally ambiguous and must be specified per panel — a *live* shot is an HA/smartfarmview camera snapshot; a LandPlan documentation photo uses the object's `updatedAt`.

---

## 3. Integration requirements

### 3.1 Authentication and plan selection (HA config flow)

Two steps:

1. **Auth.** *(Method must be confirmed against LandPlan API docs — see Open Questions.)* Two realistic options:
   - **API token** pasted into the config flow (simpler to ship first).
   - **OAuth2** via HA's `config_entry_oauth2_flow` helpers if LandPlan exposes a client.
2. **Plan selection.** After auth, the flow calls the list-plans endpoint (no-args) and presents a dropdown. Current known plans on the test account:
   - `Smart Forest, LLC` — `cmn1uj27z00023l906e4qpuok`
   - `MacArthur Home` — `cmnai1oy80006imepbm1y51mr`
   - `Maui Surf Shack` — `cmojgegfv0002tj5dhqyisu95`

The chosen `planId` is saved on the config entry. **Multiple config entries must be supported** so each plan can be its own dashboard.

**Stored on the entry:** the token (HA encrypts entry data at rest), the `planId`, and a device-mapping table (via options flow).

### 3.2 Data refresh: two coordinators by cadence

- **Slow LandPlan coordinator** (minutes): base spatial model, node positions, today's tasks. Proven against the live API.
- **Fast smartfarmview coordinator** (seconds; ideally push — websocket/SSE rather than polling): live camera/battery/trigger state, robot position, fused overlays.

### 3.3 Node-mapping convention

LandPlan map objects carry `tags` and `label`, and tags are already in active use (`cleanup`, `road`, `bridge`, `planned-building`). Extend this:

- Tag device objects `camera-node`, `mesh-node`, `robot`.
- The integration filters map objects by those tags to discover nodes + coordinates.
- An options flow binds each discovered node to a matching HA entity via entity selectors (auto-match where `label` == entity name).
- This binding lets the kiosk draw a marker at the LandPlan coordinate and fill it with the live camera/battery/trigger.

> **Note:** The Smart Forest plan currently has *no* map objects representing cameras, mesh nodes, or the robot (only photo points, ravines, roads, cleanup polygons, the property boundary, planned buildings). **Step zero is modeling the physical devices as tagged map objects.**

### 3.4 Module / file layout

```
custom_components/landplan/
├── __init__.py            # setup, coordinator wiring
├── manifest.json          # domain, version, codeowners, etc. (required keys)
├── config_flow.py         # auth step + plan dropdown + options flow (node mapping)
├── coordinator.py         # slow LandPlan DataUpdateCoordinator (plans→projects→activities→map_objects)
├── api.py                 # thin client wrapper around LandPlan endpoints (isolate breakage)
├── camera.py / image.py   # each photo-point's latest image + timestamp
├── calendar.py            # project activities as a calendar (cleanest "today's tasks" feed)
├── sensor.py              # task-count/status summary, per-project status, "minutes since last photo"
├── device_tracker.py      # node/dock positions for map placement (or geo_location.py)
└── const.py
hacs.json                  # repo root
README.md                  # repo root
brand/icon.png             # brand assets
```

**Design caution — wrap the private API.** Hitting the same endpoints the iOS app uses means depending on a private API that can change without notice. Wrap it behind a thin `api.py` client so a breakage is a one-file fix, and prefer documented/MCP surfaces where they exist (tasks already work there).

**Design caution — fallbacks.** Because smartfarmview is still conceptual, every smartfarmview-sourced panel must have a LandPlan-direct fallback or placeholder so the integration can ship now and light up real-time panels as the platform matures.

---

## 4. HACS packaging requirements

### 4.1 Repository structure (HACS is strict here)

```
custom_components/landplan/__init__.py
custom_components/landplan/manifest.json
custom_components/landplan/...
hacs.json
README.md
```

Hard rules:

- **One integration per repository** — only one subdirectory under `custom_components/`. If more than one, only the first is managed.
- All files required to run must live inside `custom_components/INTEGRATION_NAME/`.
- Files in the repo root (or a named folder without the `custom_components/` parent) fail validation unless `content_in_root: true` is set in `hacs.json`.

### 4.2 The two config files

**`hacs.json`** (repo root) — minimum a `name` key. Example:

```json
{
  "name": "LandPlan",
  "render_readme": true,
  "homeassistant": "2024.1.0"
}
```

**`manifest.json`** (inside the integration dir) — must at least define: `domain`, `documentation`, `issue_tracker`, `codeowners`, `name`, `version`. Example:

```json
{
  "domain": "landplan",
  "name": "LandPlan",
  "version": "0.1.0",
  "documentation": "https://github.com/YOURUSER/landplan-hacs",
  "issue_tracker": "https://github.com/YOURUSER/landplan-hacs/issues",
  "codeowners": ["@YOURUSER"],
  "requirements": [],
  "iot_class": "cloud_polling",
  "config_flow": true
}
```

### 4.3 Other repository requirements

- Repository must be **public** on GitHub.
- Repository needs a **GitHub description** (displayed in HACS).
- Provide **brand assets** — a `brand/` directory with at least `icon.png`.
- A README explaining setup/usage.
- Releases are **preferred but not strictly required**. If you publish releases, HACS shows the 5 latest plus the default branch; if not, it uses the default branch. A plain tag is **not** enough — publish full GitHub releases for version tracking.

---

## 5. Steps to set up a test HACS package for LandPlan

These steps get a minimal, installable test integration running via the HACS **custom repository** route (no default-store approval needed).

1. **Scaffold the repo.** Start from the official `custom-components/blueprint` template or the `cookiecutter-homeassistant-custom-component` generator. Rename the integration domain to `landplan`.
2. **Create `manifest.json`** with the required keys (§4.2). Set `config_flow: true` and `iot_class: cloud_polling`.
3. **Create `hacs.json`** at the repo root with at least `name` (§4.2).
4. **Add a minimal `config_flow.py`** that:
   - accepts an API token (start with token auth),
   - calls the list-plans endpoint,
   - presents the three plans as a dropdown,
   - stores `{token, planId}` on the config entry.
5. **Add a minimal `coordinator.py`** (slow tier) polling: plans → projects → activities. Validate against the Smart Forest plan ID `cmn1uj27z00023l906e4qpuok`.
6. **Add one platform first** — `calendar.py` exposing today's activities — as the simplest end-to-end proof, since the task data is already reachable.
7. **Add `brand/icon.png`** and a `README.md`.
8. **Push to a public GitHub repo** with a description.
9. **(Optional) Cut a `v0.1.0` GitHub release** for clean version tracking.
10. **Install in HA via HACS:** HACS → three-dot menu → *Add custom repository* → paste repo URL → category *Integration* → install. Restart HA.
11. **Add the integration:** Settings → Devices & Services → Add Integration → LandPlan → enter token → pick a plan.
12. **Verify** the calendar entity populates with today's tasks; iterate by adding `sensor.py`, `camera.py`/`image.py`, and `device_tracker.py`.
13. **Model device nodes** (step zero from §3.3): add tagged `camera-node` / `mesh-node` / `robot` map objects to the test plan so node-discovery and mapping can be exercised.

### 5.1 Local dev tips

- Develop against a HA dev container or a throwaway HA instance; symlink `custom_components/landplan` for fast iteration before testing the full HACS install path.
- Validate the repo with the HACS Action and `hassfest` early — both are required for any future default-store submission.
- Keep all LandPlan HTTP calls inside `api.py` so private-endpoint changes are contained.

---

## 6. Open questions

1. **LandPlan auth method.** Token vs. OAuth2 — what does the public/iOS API actually use, and is there a documented client? Determines §3.1.
2. **Private vs. documented API surface.** Which endpoints are stable/documented vs. iOS-app-private? Tasks work via the documented/MCP surface; what else does?
3. **smartfarmview real-time transport.** Websocket, SSE, or polling? Determines the fast coordinator design (§3.2).
4. **Sync mechanism LandPlan → smartfarmview.** Delta poll on `updatedAt` vs. webhooks. What can LandPlan emit?
5. **"Minutes since photo" semantics per panel.** Live snapshot age vs. LandPlan `updatedAt` — which applies where?
6. **Device node modeling.** Final tag vocabulary (`camera-node`/`mesh-node`/`robot`) and whether device metadata lives in the map object `metadata` field.
7. **Promotion workflow.** Who triggers promotion of a real-time capture into a durable LandPlan object, and through which write API?
8. **Multi-plan kiosk.** One dashboard per plan (per config entry) vs. a combined view across Smart Forest / MacArthur / Maui.
9. **Moving-cam representation in HA.** `device_tracker` vs. `geo_location` for robot/drone, and how the kiosk renders a moving marker + live feed.
10. **Default-store ambitions.** Is eventual submission to the HACS default store a goal (stricter validation, brand PR), or is custom-repository distribution sufficient?
11. **smartfarmview repo internals.** The current repo wasn't reachable via search; confirm its existing structure, language, and API shape before designing the fast coordinator's contract.
12. **Rate limits / quotas** on the LandPlan API for polling cadence.
