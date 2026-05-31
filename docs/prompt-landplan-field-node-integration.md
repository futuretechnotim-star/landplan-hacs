# Prompt: LandPlan field node integration (Tailscale + camera + telemetry)

Use this prompt in a Claude Code session inside the LandPlan monorepo
(`packages/api`, `packages/shared`, `packages/mobile`, `packages/web`).

---

## Codebase implementation notes (read before starting)

These notes correct assumptions in the spec and add context derived from reading the
current LandPlan codebase. Follow these over the generic spec text where they conflict.

### 1. `ObjectType` is a TypeScript string union, not an enum
Add `"field_node"` to the union in `packages/shared/src/types/object.ts`. Also add
`"field_node"` to the `z.enum([...])` array in `createObjectSchema` and
`updateObjectTypeSchema` in `packages/api/src/routes/objects.ts`. Do NOT add it to
`RESERVED_OBJECT_TYPES`.

### 2. `ObjectMetadata` already accepts arbitrary fields
`ObjectMetadata` has `[key: string]: unknown`, so add the typed `fieldNode?` field
to the interface directly — no DB migration needed for the metadata column (it is
already a `Json` blob). The `fieldNode` data persists via the existing `metadata`
field on `MapObject`.

### 3. `photoHeading` is already on `MapObject` — reuse it
Confirmed in codebase: `photoHeading?: number | null` exists on the `MapObject`
interface and is stored via raw SQL. No new column needed for the field node heading.

### 4. `haToken` encryption — no existing pattern; implement from scratch
`driveRefreshToken` is stored plaintext in the current codebase — there is no
existing encryption utility to reuse. Implement:
- `packages/api/src/services/encryption.ts` — `encryptSecret(plaintext): string`
  and `decryptSecret(ciphertext): string` using Node `crypto` AES-256-GCM.
  Ciphertext format: `iv:authTag:ciphertext` (all hex).
- Key: env var `HA_TOKEN_ENCRYPTION_KEY` (32-byte hex). Add to
  `packages/api/src/config/env.ts` Zod schema as optional — field-node features
  are disabled if the key is absent.
- Prisma columns: add `haBaseUrlEncrypted String?`, `haTokenEncrypted String?`,
  `haConnectedAt DateTime?` to the `LandPlan` model in
  `packages/api/prisma/schema.prisma`.

### 5. Historic snapshots — use Option A (GCS)
LandPlan already uses GCS via `ASSETS_BUCKET` and a `storageService` wrapper (see
`packages/api/src/routes/photos.ts`). Use Option A: upload a copy to GCS keyed as
`field-nodes/{planId}/{objectId}/{timestamp}.jpg` whenever the HA `last_updated`
timestamp is newer than the last stored copy.

### 6. Plan-level settings UI — greenfield on both platforms
There is no plan-level settings screen on web or mobile. The web has a user-level
`SettingsPage.tsx` (`packages/web/src/routes/SettingsPage.tsx`); mobile uses Zustand
+ MMKV stores with no dedicated settings screen. Both "Plan Settings → Connections"
screens are new.

### 7. Object creation flow — extend `PlaceObjectForm.tsx`
`packages/web/src/components/objects/PlaceObjectForm.tsx` handles `generic_point` and
`photo_point` via map click → form → save. Extend this for `field_node` by adding:
heading picker (reuse existing compass-rose UX), variant picker (Fixed / Gateway /
Rover), and HA node dropdown populated by `GET /plans/:planId/ha/nodes`.

### 8. SSRF validation — implement as Zod `.refine()` on `haBaseUrl`
Allow `*.ts.net` Tailscale hostnames and RFC-1918 CIDRs (`10.x.x.x`,
`172.16-31.x.x`, `192.168.x.x`). Reject all other URLs at the route handler level.

### 9. Add `GET /plans/:planId/ha/nodes` for node discovery
This endpoint is needed by the placement UX but is not in the spec's endpoint list.
It calls `GET {haBaseUrl}/api/states`, filters for `camera.*_camera` entities, strips
the `_camera` suffix, and returns `{ nodePrefix: string; label: string }[]`.

---

## Context and goals

We are adding support for **SmartFarmView field nodes** — Raspberry Pi security
camera nodes that run a Python agent (`smartfarmview-web/packages/field-node`).
Each node publishes telemetry and JPEG snapshots over MQTT to a Home Assistant
(HA) instance. The HA instance is accessible on the user's Tailscale tailnet
(via the official Tailscale HA add-on).

**Four things LandPlan needs to add:**

1. **Plan-level HA connection** — `haBaseUrl` (Tailscale URL) and `haToken`
   (HA long-lived access token) stored once per plan, encrypted at rest. All
   field node data for that plan flows through this single HA connection. Do NOT
   store connection details per node object.

2. **New map object type `field_node`** — placed on the map at the node's
   physical GPS location. Heading is set at placement time (same compass-rose UX
   as `photo_point`). Stores only the node-specific identifier (`nodePrefix` +
   `mqttNodeId`); connection details live on the plan.

3. **Latest snapshot + historic snapshots** — proxied from HA's camera proxy
   endpoint. The mobile and web apps render these in a new camera-focused map
   view and in the object detail view.

4. **Live telemetry** — battery SoC %, voltage, power mode, solar net current,
   projected end-of-day SoC. Read from HA sensor entities via the HA REST API.

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

## Plan-level HA connection (new — add to Plan schema)

Store once per plan, not per node:

```typescript
// Add to Plan type in packages/shared/src/types/plan.ts (or equivalent)
haConnection?: {
  haBaseUrl: string;   // Tailscale URL, e.g. "https://homeassistant.your-tailnet.ts.net"
  haToken: string;     // HA long-lived access token — store encrypted in DB
}
```

This is configured in a new **Plan Settings → Connections** screen. All field
node API calls for the plan use this connection. If `haConnection` is absent,
field node features are disabled for the plan.

---

## How a new node is assigned a map object (node discovery flow)

The field nodes already publish HA MQTT auto-discovery, so HA has a registry of
every connected node. Use this to drive the assignment UX:

1. **User places a `field_node` object on the map** — long-press → Add object →
   field node. Sets GPS position and heading at this point.

2. **LandPlan calls `GET {haBaseUrl}/api/states`** and filters for entities
   matching `camera.*_camera`. Strips the `_camera` suffix to extract the
   available `nodePrefix` values (e.g. `landplanmesh1`, `landplanmesh2`).

3. **User picks a node from the dropdown** — the selected `nodePrefix` (and
   derived `mqttNodeId`) is saved on the map object. If the node isn't in HA yet
   (not yet connected), a manual entry fallback allows typing the prefix directly.

4. **Object is saved** — position, heading, `nodePrefix`, `mqttNodeId`, and
   `nodeVariant` are stored. The node is now linked.

---

## What to store on each `field_node` map object

### New `objectType` value
Add `"field_node"` to the `ObjectType` **string union** in
`packages/shared/src/types/object.ts`. (`ObjectType` is a union type, not a
TypeScript `enum` — see codebase note 1 above.)

### Metadata fields (extend `ObjectMetadata`)
```typescript
fieldNode?: {
  // Node variant — determines icon, position behaviour, and available features.
  // "fixed"   — standard camera node, static position set at placement
  // "gateway" — gateway Pi with camera, static position, distinct map icon
  // "rover"   — moving node, position comes from HA device_tracker entity
  nodeVariant: "fixed" | "gateway" | "rover";

  // HA entity prefix for this node. All HA entities follow the pattern:
  //   {entityType}.{nodePrefix}_{entitySuffix}
  // Example "landplanmesh1" → camera.landplanmesh1_camera, etc.
  nodePrefix: string;

  // MQTT node_id used in topic paths (may differ from nodePrefix in casing).
  // Topic pattern: securitymesh/{mqttNodeId}/snapshot|telemetry|cmd
  // Example: "LandPlanMesh1"
  mqttNodeId: string;
}
```

### Tags (reuse existing tag system)
Use the existing `ObjectTag` values already established in the HACS integration:
- `"camera-node"` — fixed camera node
- `"gateway"` — gateway node
- `"rover"` — rover node

The `nodeVariant` metadata field and the tag should agree; derive one from the
other if possible.

### Heading
Use the existing `photoHeading` field (already on `MapObject` — confirmed in
codebase as `photoHeading?: number | null`). Set at placement time via the
compass-rose UX used for `photo_point` objects. No new DB column needed.

---

## Node variant behaviours

### Fixed node and gateway
- Position: set at placement, never changes
- Gateway has a distinct map icon (tower) vs fixed node (camera)
- Otherwise identical schema and API surface

### Rover (moving node)
- **Placement position** = dock / home position (where the rover parks when idle)
- **Live position** = read from `device_tracker.{nodePrefix}` HA entity
- LandPlan polls `GET {haBaseUrl}/api/states/device_tracker.{nodePrefix}` at a
  faster cadence (e.g. every 5 s when the rover map view is open)
- The map renders a moving marker at the live position; falls back to dock
  position when the device_tracker state is `home` or `not_home` without coords
- No changes needed to the Pi software for this — HA's device_tracker entity
  already exists via MQTT discovery

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
LandPlan has two options for historic access — **use Option A** (confirmed
decision; see codebase note 5):

**Option A (chosen):** LandPlan stores each snapshot it proxies in GCS
(reusing the existing `storageService` and `ASSETS_BUCKET`), keyed as
`field-nodes/{planId}/{nodeObjectId}/{timestamp}.jpg`. On each API call for the
latest snapshot, upload a copy if HA's `last_updated` is newer than the last
stored timestamp.

**Option B (future):** Add a minimal HTTP file server to the field node Python
package that lists and serves files from `capture_dir`. This is a future
addition to `smartfarmview-web` and is out of scope for this session.

---

## New LandPlan API endpoints to add

### Discover available nodes (new — needed for placement UX)
```
GET /plans/{planId}/ha/nodes
```
- Calls `GET {haBaseUrl}/api/states`, filters entities matching `camera.*_camera`
- Strips `_camera` suffix to extract `nodePrefix` values
- Returns `{ nodePrefix: string; label: string }[]`
- Returns `[]` if plan has no haConnection; returns error if HA unreachable

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

- `haToken` and `haBaseUrl` live on the plan record, not on individual map
  objects. Encrypt `haToken` at rest using AES-256-GCM — there is no existing
  encryption utility; implement `packages/api/src/services/encryption.ts` (see
  codebase note 4). Store as `haBaseUrlEncrypted` and `haTokenEncrypted`
  columns on the `LandPlan` Prisma model.
- Never expose `haBaseUrl` or `haToken` to the client. All HA calls are
  server-side proxies only — the client calls LandPlan API endpoints, which
  proxy to HA internally.
- The LandPlan backend must be on the same Tailscale tailnet as the HA instance
  to reach it. For local dev, use the HA Tailscale IP directly.
- Validate that `haBaseUrl` is a Tailscale hostname or RFC-1918 private IP —
  reject public internet URLs to prevent SSRF.

---

## Mobile and web UI

### New: Plan Settings → Connections screen
- Input fields for `haBaseUrl` and `haToken`
- "Test connection" button — calls `GET {haBaseUrl}/api/` and displays
  HA version on success, error message on failure
- Save stores to plan record (encrypted token)

### New: Camera map view
A dedicated map view (separate from the standard plan map) focused on field
nodes:
- Shows only `field_node` objects as markers
- Tapping a marker opens a slide-up panel with live snapshot + telemetry
- Rover markers animate to live position when device_tracker data is available
- Gateway node uses a distinct icon (e.g. tower/signal)

### Field node object detail card (new variant of map object detail view)
- **Header:** node label + variant badge (Camera Node / Gateway / Rover)
- **Image panel:** latest snapshot, tap to full-screen, "Capture" button
- **Telemetry row:** battery gauge (SoC %), power mode chip (`normal` / `eco`),
  solar net current indicator
- **Detail section:** voltage, current (mA), estimated runtime, CPU temp,
  storage %

### Node placement flow (new object creation)
1. User long-presses map → Add object → Field Node
2. Heading picker (compass rose — same UX as photo_point)
3. Node variant picker: Fixed / Gateway / Rover
4. Node assignment: dropdown of nodes discovered from HA (or manual entry)
5. Label input → Save

### Historic images
- Horizontal scroll of stored snapshots with timestamps (Option A: LandPlan
  stores a copy of each proxied snapshot)
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
