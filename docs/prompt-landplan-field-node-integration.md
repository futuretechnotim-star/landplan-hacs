# Prompt: LandPlan field node integration (Tailscale + camera + telemetry)

Use this prompt in a Claude Code session inside the LandPlan monorepo
(`packages/api`, `packages/shared`, `packages/mobile`, `packages/web`).

---

## Context and goals

We are adding support for **SmartFarmView field nodes** — Raspberry Pi security
camera nodes that run a Python agent (`smartfarmview-web/packages/field-node`).
Each node publishes telemetry and JPEG snapshots over MQTT to a Home Assistant
(HA) instance. The HA instance is now accessible on the user's Tailscale tailnet
(via the official Tailscale HA add-on). The field nodes themselves are also on
the same tailnet.

**Three things LandPlan needs to add:**

1. **New map object type `field_node`** — stores the connection metadata for a
   field node (Tailscale-reachable HA instance URL + node entity prefix). The
   type is placed on the map at the node's physical GPS location, the same as
   any other map object.

2. **Latest snapshot + historic snapshots** — the LandPlan API fetches the
   current JPEG and a list of historic captures, proxied from HA's camera proxy
   endpoint (authenticated with a stored HA long-lived access token). The mobile
   and web apps render these in the object detail view.

3. **Live telemetry** — battery SoC %, voltage, power mode, solar net current,
   and projected end-of-day SoC. These are HA sensor entities read via the HA
   REST API and surfaced on the field node object card.

---

## Architecture: how the data flows

```
Raspberry Pi field node
  │  publishes MQTT (retain=true)
  ▼
Home Assistant (on Tailscale, e.g. https://homeassistant.your-tailnet.ts.net)
  │  exposes HA REST API + camera proxy
  ▼
LandPlan API backend  (calls HA REST API using a stored HA token)
  │
  ▼
LandPlan mobile / web apps
```

**There is no HTTP API on the field nodes themselves** — all data surfaces
through Home Assistant. LandPlan never calls a field node directly; it calls
the HA instance that the node publishes to.

---

## What to store on each `field_node` map object

### New `objectType` value
Add `"field_node"` to the `ObjectType` enum in
`packages/shared/src/types/object.ts` (alongside existing types like
`photo_point`, `generic_point`, etc.).

### Metadata fields (extend `ObjectMetadata`)
```typescript
fieldNode?: {
  // HA instance reachable on Tailscale. Include protocol and port.
  // Example: "https://homeassistant.your-tailnet.ts.net"
  haBaseUrl: string;

  // HA long-lived access token for this instance. Stored encrypted.
  haToken: string;

  // MQTT node_id / HA entity prefix for this specific node.
  // All HA entities for the node are named: {entityType}.{nodePrefix}_{entitySuffix}
  // Example prefix "landplanmesh1" → entities:
  //   camera.landplanmesh1_camera
  //   sensor.landplanmesh1_battery_soc_pct
  //   sensor.landplanmesh1_battery_voltage
  //   sensor.landplanmesh1_power_mode
  //   sensor.landplanmesh1_solar_net_current
  //   sensor.landplanmesh1_solar_projected_eod_soc
  //   button.landplanmesh1_capture_snapshot
  nodePrefix: string;

  // MQTT node_id used in MQTT topic paths (may differ from nodePrefix casing).
  // Topic pattern: securitymesh/{mqttNodeId}/snapshot
  //                securitymesh/{mqttNodeId}/telemetry
  //                securitymesh/{mqttNodeId}/cmd
  // Example: "LandPlanMesh1"
  mqttNodeId: string;
}
```

**Note:** `haBaseUrl` and `haToken` will be shared across all field nodes on
the same HA instance. Consider whether these belong at the plan level (a single
HA connection per plan) rather than per-node, to avoid duplicating secrets.

---

## HA REST API endpoints to call

All requests require header: `Authorization: Bearer {haToken}`

### Latest snapshot image
```
GET {haBaseUrl}/api/camera_proxy/{cameraEntityId}
```
- `cameraEntityId` = `camera.{nodePrefix}_camera`
- Returns raw JPEG bytes
- Always returns the most recent retained snapshot

### HA entity state (telemetry)
```
GET {haBaseUrl}/api/states/{entityId}
```
Returns:
```json
{
  "state": "63",
  "attributes": { ... },
  "last_updated": "2026-05-31T14:00:00Z"
}
```

### Telemetry entities per node (replace `{nodePrefix}` with actual prefix)

| LandPlan field | HA entity ID | Unit |
|---|---|---|
| `batterySocPct` | `sensor.{nodePrefix}_battery_soc_pct` | % |
| `batteryVoltage` | `sensor.{nodePrefix}_battery_voltage` | V |
| `batteryCurrentMa` | `sensor.{nodePrefix}_battery_current` | mA |
| `batteryDischarging` | `sensor.{nodePrefix}_battery_soc_pct` attributes | bool |
| `batteryRuntimeHours` | `sensor.{nodePrefix}_battery_runtime` | h |
| `powerMode` | `sensor.{nodePrefix}_power_mode` | string: `normal` \| `eco` |
| `solarNetAvgMa` | `sensor.{nodePrefix}_solar_net_current` | mA |
| `solarProjectedEodSoc` | `sensor.{nodePrefix}_solar_projected_eod_soc` | % |
| `cpuTemp` | `sensor.{nodePrefix}_cpu_temp` | °C |
| `storagePct` | `sensor.{nodePrefix}_storage_pct` | % |

### Trigger a manual capture
```
POST {haBaseUrl}/api/services/button/press
Content-Type: application/json
{ "entity_id": "button.{nodePrefix}_capture_snapshot" }
```

### Historic snapshots
HA does not retain image history. Historic snapshots exist as timestamped JPEG
files on the Pi's local disk at:
```
/opt/field-node/captures/{mqttNodeId}_{YYYYMMDD_HHMMSS}.jpg
```
LandPlan has two options for historic access — decide during implementation:

**Option A (simpler):** LandPlan stores each snapshot it proxies in its own
object storage (S3/GCS), keyed by `{planId}/{nodeObjectId}/{timestamp}.jpg`.
On each API call for the latest snapshot, store a copy if the `last_updated`
timestamp is newer than the last stored copy.

**Option B (complete history):** Add a minimal HTTP file server to the field
node Python package that lists and serves files from `capture_dir`. The node's
Tailscale address would then be needed directly. This is a future addition to
`smartfarmview-web`.

---

## New LandPlan API endpoints to add

### Get latest snapshot
```
GET /plans/{planId}/objects/{objectId}/field-node/snapshot
```
- Fetches from `{haBaseUrl}/api/camera_proxy/camera.{nodePrefix}_camera`
- Returns JPEG bytes (or a signed URL if storing in object storage)
- Cache: max 10 seconds (respect `last_updated` from HA state endpoint)

### Get telemetry
```
GET /plans/{planId}/objects/{objectId}/field-node/telemetry
```
Response:
```json
{
  "batterySocPct": 63,
  "batteryVoltage": 3.898,
  "batteryCurrentMa": 5.2,
  "batteryDischarging": false,
  "batteryRuntimeHours": null,
  "powerMode": "normal",
  "solarNetAvgMa": 1.5,
  "solarProjectedEodSoc": 64.1,
  "cpuTemp": 63.4,
  "storagePct": 13.0,
  "lastUpdated": "2026-05-31T14:00:00Z"
}
```
- Fetches relevant HA sensor states in parallel (one request per sensor or
  use `GET /api/states` to fetch all and filter client-side)

### Trigger capture
```
POST /plans/{planId}/objects/{objectId}/field-node/capture
```
- Calls `POST {haBaseUrl}/api/services/button/press`
- Returns 204 on success

---

## Security requirements

- `haToken` is a HA long-lived access token. Store it encrypted at rest in the
  database (same treatment as API keys in other integrations).
- `haBaseUrl` is a private Tailscale address — never expose it to the client.
  All HA calls are server-side proxies only.
- The LandPlan backend must be on the same Tailscale tailnet as the HA instance
  to make these calls. For local dev, use the HA Tailscale IP directly.
- Validate that `haBaseUrl` is a `https://` or private-IP URL — reject public
  internet URLs to prevent SSRF.

---

## Mobile and web UI

### Field node object card (new variant of the map object detail view)
- **Header:** node label + `field_node` type badge
- **Image panel:** latest snapshot, tap to full-screen, "Capture" button
- **Telemetry row:** battery gauge (SoC %), power mode chip, solar current
- **Detail section:** voltage, current, runtime estimate, CPU temp, storage

### Historic images (future / Option A from above)
- Horizontal scroll of stored snapshots with timestamps
- Tap to full-screen

---

## MQTT topic reference (for future direct subscription)

If LandPlan ever subscribes to MQTT directly (bypassing HA):

| Topic | Payload | Retain |
|---|---|---|
| `securitymesh/{mqttNodeId}/snapshot` | Raw JPEG bytes | Yes |
| `securitymesh/{mqttNodeId}/telemetry` | JSON (see fields above) | No |
| `securitymesh/{mqttNodeId}/detection` | JSON `{ ts, summary, objects[] }` | Yes |
| `securitymesh/{mqttNodeId}/motion_state` | String `"ON"` or `"OFF"` | No |
| `securitymesh/{mqttNodeId}/cmd` | JSON `{ "cmd": "capture" }` | No (subscribe to send) |

MQTT broker is accessed via the HA Tailscale address on port 1883 (or 8883 for
TLS). Auth credentials are in the HA MQTT integration config.

---

## Related codebase paths

- Field node source: `smartfarmview-web/packages/field-node/src/field_node/`
- HA HACS integration (reads HA entities, shows snapshot card):
  `landplan-hacs/custom_components/landplan/`
- Existing `ObjectType` enum: `packages/shared/src/types/object.ts`
- Existing `ObjectMetadata` type: `packages/shared/src/types/object.ts`
- Existing photo proxy pattern (reference for image proxying):
  `packages/api/src/routes/photos.ts`
- Existing map object routes: `packages/api/src/routes/objects.ts` (or similar)
