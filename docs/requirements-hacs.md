# LandPlan HACS Integration — Requirements

**Status:** In progress
**Scope:** A Home Assistant custom integration (distributed via HACS) that surfaces LandPlan data, plus a kiosk-style Lovelace view that fuses LandPlan's authoritative data with near-real-time data from the SmartFarmView field node mesh.
**Last updated:** 2026-05-31

---

## 1. Background and architecture

The system is a three-tier split. Naming each tier by its job drives the rest of the design decisions.

- **LandPlan.app — system of record.** Slow-moving, durable, authoritative. Owns the spatial model, object identity, plans, and the task/activity schedule. Long planning horizon. Physical field nodes (cameras, gateway, rover) are modeled as `field_node` map objects in LandPlan with GPS position, heading, and node metadata.
- **Home Assistant — real-time gateway.** Raspberry Pi field nodes publish MQTT telemetry and JPEG snapshots to a local HA instance accessible on the user's Tailscale tailnet. HA exposes a REST API and camera proxy. It is the live data layer — it does not own the spatial model.
- **HA integration + kiosk — consumer.** Reads slow/authoritative data from LandPlan (tasks, spatial model, node positions) and live data from HA (camera snapshots, battery sensors, rover device_tracker). Chooses the source per entity type.

**Governing principle:** The HACS integration is a *reader* of both sources, never the synchronizer. LandPlan is authoritative for node identity and position. HA is authoritative for live state. This keeps HA dumb, resilient, and easy to fix.

### 1.1 Object identity (governs the entity model)

LandPlan map objects have stable IDs and an `updatedAt` on every object. The new `field_node` objectType stores a `nodePrefix` in its metadata (e.g. `"landplanmesh1"`). This prefix directly derives all HA entity IDs:

```
camera.{nodePrefix}_camera
device_tracker.{nodePrefix}
sensor.{nodePrefix}_battery_soc_pct
sensor.{nodePrefix}_battery_voltage
sensor.{nodePrefix}_battery_current
sensor.{nodePrefix}_battery_runtime
sensor.{nodePrefix}_power_mode
sensor.{nodePrefix}_solar_net_current
sensor.{nodePrefix}_solar_projected_eod_soc
sensor.{nodePrefix}_cpu_temp
sensor.{nodePrefix}_storage_pct
button.{nodePrefix}_capture_snapshot
```

The HACS integration reads `nodePrefix` from the LandPlan map object — **no manual options-flow entity binding is needed**. Node discovery is automatic once the user has added `field_node` objects to their plan in LandPlan.app.

### 1.2 Node variants

LandPlan models three variants of `field_node`:

| Variant | Tag | Position | Notes |
|---|---|---|---|
| `fixed` | `camera-node` | Static, set at placement | Standard camera node |
| `gateway` | `gateway` | Static, set at placement | Gateway Pi with camera; distinct icon |
| `rover` | `rover` | Dynamic — from `device_tracker.{nodePrefix}` | Moving node; dock position is fallback |

The HACS integration handles each variant differently. The rover uses the `device_tracker` HA entity for its live position; fixed and gateway nodes use the stored LandPlan GPS coordinate.

### 1.3 Data flow

```
Raspberry Pi field node
  │  publishes MQTT (retain=true) — snapshot, telemetry, detection, motion
  ▼
Home Assistant (on Tailscale)
  │  REST API + camera proxy; entity names derived from nodePrefix
  ▼
HACS integration (slow coordinator: LandPlan; fast coordinator: HA entities)
  │
  ▼
HA entities surfaced by the HACS integration
```

LandPlan.app proxies snapshot and telemetry through its own API (server-side, using a stored HA token). The HACS integration reads the same HA entities directly, since it runs inside HA and can call the HA WebSocket/REST API natively without Tailscale concerns.

---

## 2. Kiosk view: panels and data sources

The kiosk is a **separate deliverable** — a Lovelace dashboard using the SmartFarmView snapshot card (already built) plus standard HA cards.

| Panel | LandPlan provides | HA provides | Primary source |
|---|---|---|---|
| Per-node camera + latest snapshot + age + battery % | Node position, label, `nodePrefix` | `camera.{nodePrefix}_camera` snapshot, `sensor.*_battery_soc_pct` | HA (live) |
| Map + most-recently-triggered node + its capture | Node positions from `field_node` objects | `device_tracker.{nodePrefix}` for rover; sensor states | HA |
| Today's task list + status | Activities across projects, filtered to today | — | **LandPlan-direct** |
| Rover location + current view | Dock/home position | `device_tracker.{nodePrefix}` + `camera.{nodePrefix}_camera` | HA |

---

## 3. Integration requirements

### 3.1 Authentication and plan selection (HA config flow) — DONE

- **Auth:** API token (Bearer). Validated via `GET /auth/me` on the LandPlan API.
- **Plan selection:** list-plans dropdown, stored as `{token, planId}` on config entry.
- **Multiple config entries** supported (one per plan).
- See `config_flow.py` — complete.

### 3.2 Data refresh: two coordinators by cadence

- **Slow LandPlan coordinator (5 min) — DONE:** polls `get_plan`, `list_projects`, `list_all_activities`, `list_map_objects`. Returns `LandPlanData` with `device_nodes` property.
- **Fast HA coordinator (future):** reads HA entities for live camera/battery/tracker state. Cadence: seconds, ideally WebSocket push. Not yet built. When built, it should use `nodePrefix` values extracted from `field_node` map objects returned by the slow coordinator.

### 3.3 Node discovery — UPDATE NEEDED

**Current state:** The integration filters `map_objects` by `DEVICE_TAGS = {"camera-node", "mesh-node", "robot"}` in `coordinator.py` / `const.py`. The options flow was intended to manually bind each node to an HA entity.

**Required change:** Now that LandPlan stores `nodePrefix` directly on `field_node` map objects, the manual binding options flow is no longer needed. The integration should:

1. Filter `map_objects` by `objectType == "field_node"` (in addition to or replacing tag-based filtering).
2. Read `obj["metadata"]["fieldNode"]["nodePrefix"]` to derive all HA entity IDs automatically.
3. Update `DEVICE_TAGS` to include `"gateway"` and `"rover"` — `"robot"` is retired.
4. Remove or deprecate the manual node-mapping options flow.

### 3.4 Module / file layout — CURRENT STATE

```
custom_components/landplan/
├── __init__.py            # setup, card JS copy to www/landplan/
├── manifest.json
├── config_flow.py         # DONE — token auth + plan dropdown; options flow stub
├── coordinator.py         # DONE — slow tier, LandPlanData, device_nodes
├── api.py                 # DONE — all LandPlan endpoints + get_photo_download_url
├── calendar.py            # DONE — one CalendarEntity per project
├── sensor.py              # DONE — task count per project
├── image.py               # DONE — one ImageEntity per photo_point with photoId
├── device_tracker.py      # DONE — one TrackerEntity per device-tagged map object
├── helpers.py             # DONE — remove_stale_entities()
├── const.py               # DONE — DEVICE_TAGS needs gateway/rover update
└── www/
    └── smartfarmview-snapshot-card.js   # DONE — push + polling auto-refresh
hacs.json                  # DONE
README.md                  # DONE
brand/icon.png             # DONE
```

---

## 4. HACS packaging — DONE

All HACS/hassfest validation passing. See `.github/workflows/validate.yml`.

---

## 5. Remaining work

### 5.1 Update node discovery for `field_node` object type

**Files:** `const.py`, `coordinator.py`, `device_tracker.py`, `image.py`

- Update `DEVICE_TAGS`: replace `"robot"` with `"gateway"` and `"rover"`.
- Add `field_node` object detection: filter by `objectType == "field_node"` and extract `metadata.fieldNode.nodePrefix`.
- `LandPlanData.device_nodes` should return `field_node` objects (in addition to tag-matched objects for backwards compatibility during transition).
- `device_tracker.py`: for `nodeVariant == "rover"` objects, mark the entity as needing live position from HA `device_tracker.{nodePrefix}`. For fixed/gateway, use stored LandPlan coordinates as before.

### 5.2 Fast HA coordinator (live camera + battery + rover position)

**New file:** `ha_coordinator.py` — a second `DataUpdateCoordinator` that reads HA entities directly. This is distinct from the LandPlan coordinator because it needs a much faster update cadence and a different data source.

Inputs: `nodePrefix` values from `field_node` objects in `LandPlanData`.

Entities to fetch per node:
- `camera.{nodePrefix}_camera` state (for `last_updated` / image freshness)
- `sensor.{nodePrefix}_battery_soc_pct` → battery gauge sensor
- `sensor.{nodePrefix}_power_mode` → power mode sensor
- `sensor.{nodePrefix}_solar_net_current` → solar sensor
- `device_tracker.{nodePrefix}` → rover live position

Data access: use HA's `homeassistant.helpers.entity_registry` and state machine directly (no HTTP round-trip needed — the data is already in HA memory).

### 5.3 Battery and power mode sensors from HA

**New file:** `sensor.py` additions (or separate `ha_sensor.py`)

New sensor entities sourced from HA (not LandPlan):
- Battery SoC % per `field_node` — from `sensor.{nodePrefix}_battery_soc_pct`
- Power mode per `field_node` — from `sensor.{nodePrefix}_power_mode`
- Solar net current — from `sensor.{nodePrefix}_solar_net_current`

These complement the existing LandPlan-sourced task-count sensors.

### 5.4 Kiosk Lovelace dashboard

A `lovelace/` directory with a starter dashboard YAML for the kiosk view. Not a Python platform — a configuration deliverable. Includes:

- SmartFarmView snapshot card per node (one card per `field_node` in the plan)
- Battery gauge and power mode per node
- Today's task list via the LandPlan calendar entity
- Rover map card if a rover node exists

### 5.5 Options flow update

The node-mapping options flow (currently a stub) should be updated to reflect the new automatic binding. Instead of manual entity assignment, it should allow:
- Confirming / overriding the detected `nodePrefix` per node
- Setting polling cadence for the fast coordinator
- Enabling/disabling specific sensor types

---

## 6. Resolved questions (previously open)

1. **Auth method** — API token (Bearer). Confirmed and implemented.
2. **Private vs. documented API surface** — tasks/activities/map-objects work via the MCP-documented surface. New `field_node` endpoints (`/ha/nodes`, `/field-node/snapshot`, `/field-node/telemetry`) are being added to LandPlan.
3. **Device node modeling** — `field_node` objectType with `nodeVariant` and `nodePrefix` in metadata. Tags: `camera-node`, `gateway`, `rover`. `robot` retired.
4. **Moving-cam representation** — `device_tracker.{nodePrefix}` for rover confirmed. Fixed/gateway use stored LandPlan coordinates.
5. **smartfarmview real-time transport** — HA is the real-time layer. HACS reads HA state directly (no smartfarmview.com dependency for field node features).
6. **"Minutes since photo" semantics** — `last_updated` on the HA camera entity state. Implemented in SmartFarmView snapshot card.

## 7. Still open

1. **Fast coordinator push vs. poll** — HA state machine is in-process; prefer HA event bus subscription (`EVENT_STATE_CHANGED`) over polling. Confirm whether `DataUpdateCoordinator` or direct event bus subscription is better for per-entity HA state.
2. **Multi-plan kiosk** — one dashboard per plan config entry vs. combined view.
3. **Default-store ambitions** — custom-repository distribution is sufficient for now.
4. **Rate limits** on LandPlan API for the slow coordinator.
5. **Rover live position update cadence** — how frequently to read `device_tracker.{nodePrefix}`. 5 s when map view is open; what when backgrounded?
