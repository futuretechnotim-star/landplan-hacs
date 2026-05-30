# LandPlan — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration that surfaces [LandPlan.app](https://landplan.app) data — spatial model, project activities, photo points, and physical device locations — inside Home Assistant.

## Features

- **Calendar** — today's project activities and tasks from any LandPlan plan
- **Sensors** — task-count and status summaries per project
- **Camera / Image** — photo-point images with timestamps
- **Device Tracker** — node and dock positions on the HA map
- **SmartFarmView Snapshot Card** — Lovelace card showing the latest JPEG from a SecurityMesh field node, with age indicator and on-demand capture button (auto-registered, no manual resource step)

> Kiosk-style Lovelace dashboard fusing LandPlan data with live smartfarmview.com feeds is a planned follow-on feature.

## Requirements

- Home Assistant 2024.1.0 or later
- HACS installed
- A LandPlan account with at least one plan

## Installation

### Via HACS (recommended)

1. Open HACS → three-dot menu → **Add custom repository**
2. Paste `https://github.com/futuretechnotim-star/landplan-hacs` and select category **Integration**
3. Install **LandPlan** and restart Home Assistant

### Manual

Copy `custom_components/landplan/` into your HA `config/custom_components/` directory and restart.

## Setup

### 1. Generate an API token in LandPlan

1. Open [LandPlan.app](https://landplan.app) in a browser
2. Go to **Settings → API Tokens**
3. Click **Generate new token** and copy it

### 2. Add the integration in Home Assistant

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **LandPlan**
3. Paste your API token into the **API Token** field
4. Select the plan you want to track

Repeat from step 2 to connect additional plans — each plan gets its own config entry.

Multiple config entries are supported — add one per plan to have separate dashboards.

## Configuration

All configuration is done via the UI config flow. No `configuration.yaml` changes needed.

| Option | Description |
|---|---|
| API Token | Your LandPlan authentication token |
| Plan | The LandPlan plan to surface in HA |

## SmartFarmView Snapshot Card

The integration bundles a Lovelace card for SecurityMesh field node cameras. The JS file is served at `/landplan/smartfarmview-snapshot-card.js` — register it once as a Lovelace resource and it will be available as a custom card on all dashboards.

### Register the card resource (one-time setup)

1. Go to **Settings → Dashboards → Resources**
2. Click **Add Resource**
3. URL: `/landplan/smartfarmview-snapshot-card.js`
4. Resource type: **JavaScript module**
5. Click **Create**, then hard-refresh your browser or app

```yaml
type: custom:smartfarmview-snapshot-card
camera_entity: camera.landplanmesh1_camera
button_entity: button.landplanmesh1_capture_snapshot
title: Field Node 1        # optional
```

| Option | Required | Description |
|---|---|---|
| `camera_entity` | Yes | HA MQTT camera entity for the node |
| `button_entity` | Yes | HA button entity that triggers snapshot capture |
| `title` | No | Card header text |

The card shows the latest JPEG via the HA camera proxy, displays how long ago it was captured (updated every 30 s), and lets you trigger a new capture on demand.

## Contributing

Issues and PRs welcome at [github.com/futuretechnotim-star/landplan-hacs](https://github.com/futuretechnotim-star/landplan-hacs).
