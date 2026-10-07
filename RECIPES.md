# Derived sensor recipes

The meter reports each channel as an unsigned power reading plus an export
flag. These recipes turn those into the sensors most dashboards need: signed
grid power, import and export power, house consumption and unmetered load.

Each recipe is a **Template sensor helper**, created in the UI with no YAML:

1. Settings > Devices & services > Helpers > **Create helper** > **Template** > **Template sensor**.
2. Paste the recipe into **State template**.
3. Edit only the lines at the top, marked *Edit these*. Everything below
   *No changes needed below* works as it is.
4. Set **Name**, **Unit**, **Device class** and **State class** as listed with the recipe.
   Using the suggested names gives the entity IDs the later recipes and the
   dashboard card expect (for example `sensor.net_grid_power`).

The preview under the template shows the result straight away, so you can
check it before saving.

## Which recipes do I need?

| Your layout | Recipes |
|---|---|
| Whole-house clip (grid feed) plus circuit clips | 1, 2, 3, 5 (add 4 if you have solar) |
| Whole-house clip only | 1, 2, 3 (add 4 if you have solar) |
| Circuit clips only, no grid clip | None needed: use the channel power sensors directly |

Any channel can be the grid channel. Nothing assumes channel 1.

The ATMS100115 is a single-phase meter. For a three-phase supply, Ourtop
makes a separate model (ATMS100133), which Tuya Local already supports.

## 1. Net grid power

Positive when importing from the grid, negative when exporting. Normally the
list holds just your grid channel. If your supply arrives on more than one
clipped feed, list each one and they are added together.

If any listed sensor is unavailable (for example an export sensor that has
been disabled), the result is **unknown** rather than a wrong number.

```jinja
{# Edit these: (power sensor, export sensor) for each grid channel #}
{% set grid = [
  ('sensor.5_channel_energy_meter_channel_1_power',
   'binary_sensor.5_channel_energy_meter_channel_1_export'),
] %}
{# No changes needed below #}
{% set ns = namespace(total=0, ok=true) %}
{% for power, export in grid %}
  {% if not has_value(power) or not has_value(export) %}
    {% set ns.ok = false %}
  {% endif %}
  {% set w = states(power) | float(0) %}
  {% set ns.total = ns.total + (-w if is_state(export, 'on') else w) %}
{% endfor %}
{{ ns.total | round(0) if ns.ok else none }}
```

Name **Net grid power** · Unit **W** · Device class **Power** · State class **Measurement**

## 2. Grid import power

```jinja
{# Edit this: your net grid power sensor from recipe 1 #}
{% set net = 'sensor.net_grid_power' %}
{# No changes needed below #}
{{ [states(net) | float(0), 0] | max | round(0) if has_value(net) else none }}
```

Name **Grid import power** · Unit **W** · Device class **Power** · State class **Measurement**

## 3. Grid export power

```jinja
{# Edit this: your net grid power sensor from recipe 1 #}
{% set net = 'sensor.net_grid_power' %}
{# No changes needed below #}
{{ [-(states(net) | float(0)), 0] | max | round(0) if has_value(net) else none }}
```

Name **Grid export power** · Unit **W** · Device class **Power** · State class **Measurement**

## 4. House consumption (solar)

Everything the house is using: grid power plus solar generation. The solar
sensor counts as 0 W when it is unavailable, as many inverters go offline
overnight. Without solar, net grid power already *is* house consumption, so
you don't need this recipe.

```jinja
{# Edit these #}
{% set net = 'sensor.net_grid_power' %}
{% set solar = 'sensor.solar_power' %}
{# No changes needed below #}
{% if has_value(net) %}
  {{ (states(net) | float(0) + states(solar) | float(0)) | round(0) }}
{% else %}
  {{ none }}
{% endif %}
```

Name **House consumption** · Unit **W** · Device class **Power** · State class **Measurement**

Check your solar sensor's unit. If it reports kW, use
`states(solar) | float(0) * 1000` instead.

## 5. Unmetered load

House consumption that isn't on a clipped circuit or a listed device. Add
any other power-metered devices (smart plugs, a heat pump with its own power
sensor) to the list to narrow it down further.

```jinja
{# Edit these #}
{% set house = 'sensor.house_consumption' %}
{% set metered = [
  'sensor.5_channel_energy_meter_channel_2_power',
  'sensor.5_channel_energy_meter_channel_3_power',
  'sensor.5_channel_energy_meter_channel_4_power',
] %}
{# No changes needed below #}
{% set ns = namespace(total=0, ok=has_value(house)) %}
{% for s in metered %}
  {% if not has_value(s) %}{% set ns.ok = false %}{% endif %}
  {% set ns.total = ns.total + states(s) | float(0) %}
{% endfor %}
{{ [states(house) | float(0) - ns.total, 0] | max | round(0) if ns.ok else none }}
```

Name **Unmetered load** · Unit **W** · Device class **Power** · State class **Measurement**

Small negative values are possible when readings from different devices
arrive at slightly different times, so the result is floored at 0 W.
Without solar, use your net grid power sensor as `house`.

## Energy dashboard

No recipes are needed for energy (kWh). The meter's own per-channel counters
already split by direction:

- **Grid consumption:** the grid channel's *energy consumed* sensor.
- **Return to grid:** the grid channel's *energy produced* sensor.
- **Individual devices:** each circuit channel's *energy consumed* sensor.

If you listed more than one feed in recipe 1, combine each direction's
counters with the built-in **Combine the state of several sensors** helper
(type *Sum*), again with no template needed.

For the dashboard's live power view, use recipe 1 (net grid power).
