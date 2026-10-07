# Ourtop ATMS100115 5-channel Wi-Fi energy meter for Home Assistant

> **Status: pre-release (v0.1.0).** Working and in daily use, but still being
> tested from a clean install. Feedback and issue reports are welcome.

A setup kit for the Ourtop **ATMS100115** CT clip energy meter (a Tuya Wi-Fi
device) in Home Assistant, fully local through
[Tuya Local](https://github.com/make-all/tuya-local). No cloud connection is
needed once the meter is set up.

It gives you per-channel power, current and energy, the meter's own totals and
supply voltage, live readings at an interval you choose (1 minute day to day,
down to 15 seconds when you need detail), automatic recovery if readings stop,
and a dashboard card to control and watch it all.

> **Before you start: you need the meter's local key.** Like every local Tuya
> integration, Tuya Local needs the meter's device ID and **local key** (a
> secret that the meter only shares with Tuya's cloud). You have to obtain
> these yourself before you can add the meter, usually through a free Tuya
> developer account or a tool such as `tinytuya`. Tuya Local's documentation
> explains the options. Allow some time for this if you haven't done it before.

## Is this my meter?

It's a DIN-rail meter with five CT clip inputs (C1–C5), labelled on the
front **Ourtop Wifi Smart Meter ATMS100115**, 100–240 VAC 50–60 Hz,
0–100 A, with a Tuya logo and a "Touch 5s to Connect" button. The side
label reads *WiFi Smart Meter: Bidirectional Metering, Single Phase, 5 Loads
Metering*. Sellers often list it as a generic "Smart WiFi Energy Meter".
Tuya's cloud lists it as **WiFi Smart Meter 5 CT**, model `ATMS1001315`
(slightly different from the label), product ID `eedoqrlzlhrgkqnu`. That
product ID is what Tuya Local uses to recognise it.

The three-phase model, **ATMS100133**, is a different device that Tuya Local
already supports. It may have the same refresh behaviour, in which case the
blueprints here could help with it too, but that is untested.

## What's in the kit

| File | What it is |
|---|---|
| `devices/ourtop_atms100115_energymeter.yaml` | Tuya Local device config: defines all the meter's entities |
| `blueprints/tuya_meter_refresh.yaml` | Automation blueprint: keeps readings fresh, with an optional high-res mode |
| `blueprints/tuya_meter_stale_recovery.yaml` | Automation blueprint: reloads the meter if readings stop, and alerts you if that doesn't help |
| `dashboard/energy_meter_card.yaml` | Dashboard card: high-res controls, status, live power and history |
| [`RECIPES.md`](RECIPES.md) | Template recipes for net grid power, import/export, house consumption and unmetered load |

## Why the meter needs a refresh automation

This meter doesn't behave like most Tuya energy devices:

- **It only measures when asked.** It sends a fresh set of readings when its
  refresh datapoint (DP 35) is set to `online`, which is what the vendor app
  does while it's open. Each request gives exactly one report, delivered over
  about 3–4 seconds.
- **Otherwise it reports every 15 minutes** on its own.
- **Polling doesn't help.** Tuya Local's regular status poll returns the
  meter's last stored snapshot, and the per-channel readings aren't included
  at all. The meter also ignores Tuya's "update datapoints" request.

So something has to write DP 35 regularly, and that is the refresh blueprint's
job.

## Requirements

- Home Assistant 2024.10 or later
- [Tuya Local](https://github.com/make-all/tuya-local), installed through HACS
- The meter's device ID and local key (see *Before you start* above)

> **Safety:** the meter and its CT clips are installed in your switchboard.
> In many countries, including Australia and New Zealand, that is licensed
> electrical work. Use a licensed electrician.

## Installation

### 1. Device config

Until this config is included in Tuya Local itself:

1. Copy `devices/ourtop_atms100115_energymeter.yaml` to
   `/config/custom_components/tuya_local/devices/`.
2. Restart Home Assistant.
3. Add the meter in Tuya Local (Settings > Devices & services > Add
   integration > Tuya Local). It should be offered as **5-channel energy
   meter**.

Tuya Local updates replace its `devices` folder, so copy the file back after
each update until it's included upstream. Keep a copy outside
`custom_components`.

### 2. Timer helper (optional, for high-res mode)

Settings > Devices & services > Helpers > Create helper > **Timer**:

- Name: **Energy meter high-res** (the dashboard card expects
  `timer.energy_meter_high_res`)
- Duration: anything, for example 1 hour (the card's buttons set their own)
- Tick **Restore**, so a running high-res period survives a restart

### 3. Refresh blueprint

[![Import the refresh blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fr5e%2Fha-ourtop-atms100115-energy-meter%2Fblob%2Fmain%2Fblueprints%2Ftuya_meter_refresh.yaml)

Create an automation from it:

- **Refresh entity:** the meter's Refresh select
- **Standard interval:** 1 minute is recommended
- **High-res timer:** the timer from step 2 (or leave empty)
- **High-res interval:** 15 or 30 seconds

High-res mode runs **only while the timer is counting down**. Start it from
the dashboard card's buttons (step 5) or the timer itself. When the timer
finishes, the standard interval resumes automatically.

### 4. Recovery blueprint (recommended)

[![Import the recovery blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fr5e%2Fha-ourtop-atms100115-energy-meter%2Fblob%2Fmain%2Fblueprints%2Ftuya_meter_stale_recovery.yaml)

Create an automation from it:

- **Sensor to watch:** the meter's **Supply voltage** sensor
- **Timings:** the defaults (5, 2 and 5 minutes) suit a 1- or 2-minute
  standard interval. For longer intervals, set *stale after* to about
  2.5 times the standard interval.

If readings stop, it reloads the meter's Tuya Local entry. If that doesn't
bring them back, it raises a notification (plus any action you add, such as a
phone notification), which clears itself once readings return.

### 5. Dashboard card

Edit a dashboard > Add card > **Manual**, clear the editor, and paste
`dashboard/energy_meter_card.yaml`. The comment at the top lists the entity
IDs it uses. Adjust them if your device, timer or recipe sensors have
different names.

The card has the high-res buttons (30 minutes, 1 hour, 4 hours, stop), the
current mode and last reading time, live power tiles, and a history graph
whose time range follows the high-res period.

### 6. Derived sensors

See [RECIPES.md](RECIPES.md) for net grid power, import and export power,
house consumption and unmetered load. Each one is a copy-and-paste Template
helper; no YAML files needed.

## Entities

| Entity | Notes |
|---|---|
| Channel N power (W) | Always positive; check the channel's export sensor for direction |
| Channel N current (A) | Diagnostic |
| Channel N export | On while the channel's power flows outwards (for example solar export on a grid clip) |
| Channel N energy consumed / produced (kWh) | Per-channel counters, split by direction |
| Supply voltage (V) | Measured from the meter's own mains supply, whatever is clipped where |
| Energy consumed / produced, Energy, Power, Reactive power, Power factor | The meter's own totals across all channels |
| Refresh | Used by the refresh blueprint; always shows `online` |

**Export sensors** are only meaningful on channels that can actually carry
power outwards, such as a grid clip with solar, or a solar or battery clip.
On other channels the direction flag is random whenever the current is close
to zero, which fills the logbook with on/off flips. Disable the export sensor
for any channel that can never export (Settings > Entities > the entity >
Enabled off). Don't disable one that a recipe uses.

**The meter's totals** add up all channels. That's correct when every clip is
on a separate circuit, but if one clip is on the whole-house feed and others
on circuits inside the house, those circuits are counted twice. In that
layout, hide the totals and use the recipes instead.

## Example layouts

- **Whole house plus circuits:** grid feed on one channel, individual circuits
  (air conditioner, oven, pool, …) on the others. Use recipe 1 for the grid
  channel and recipe 5 for unmetered load. This is the layout the kit was
  developed on.
- **Circuits only:** no grid clip. Use the channel power sensors directly;
  the meter's totals are a valid sum.
- **Solar:** a clip on the grid feed shows import and export through its
  export sensor. A clip on the inverter output can be treated like any other
  channel.
- **Three-phase:** not supported by this single-phase meter. See the
  ATMS100133 above.

## What's been tested

On a single-phase supply with a whole-house clip and three circuit clips:

- **1-minute standard interval:** run for several days without gaps.
- **30-second interval:** run overnight with no missed readings.
- **15-second high-res periods:** working over short test periods.
- **Recovery blueprint:** tested end to end (stale detection, reload, alert,
  automatic clearing).

Database growth at a 30-second interval was roughly 25 MB a day for the whole
Home Assistant database. That's a rough figure, but it's why high-res mode is
time-limited rather than permanent.

## Limitations

- **One report per refresh.** Shorter intervals mean more writes and more
  network traffic. Each report takes about 3–4 seconds to arrive, so very
  short intervals leave little margin.
- **Short gaps after a reload or restart.** The channel sensors show
  `unknown` until the next refresh.
- **No Wi-Fi signal reporting.** The meter doesn't report its own signal
  strength. The optional Ping integration on its hostname gives a useful
  substitute; the card shows its status if the sensor exists.
- **Single-phase only** (see above for the three-phase model).

## Troubleshooting

- **Channel sensors stay `unknown`:** check the refresh automation is on and
  its Refresh entity is selected. A status poll alone never fills them in.
- **"receive loop has terminated" in the log:** Tuya Local logs this
  whenever the connection to the meter closes, including every reload. If it
  appears without a reload, the connection genuinely dropped.
- **"Energy meter not updating" notification:** check the refresh automation
  first, then the meter's Wi-Fi. A power cycle at the meter's isolator is the
  last resort.

## Maintenance note

Tuya Local builds each entity's unique ID from its **name** in the device
config. Renaming an entity in the config creates a new entity and orphans the
old one, with its history. Entity names in `ourtop_atms100115_energymeter.yaml` are
therefore fixed once published. Rename entities in the Home Assistant UI
instead, which is always safe.

## Credits

Built on [Tuya Local](https://github.com/make-all/tuya-local) by make-all.

## Licence

MIT. See [LICENSE](LICENSE).
