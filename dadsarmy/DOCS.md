# Dads Army

A stores tracker for food, water and emergency kit, built to be used from your phone.

## Opening it

- **In Home Assistant:** click **Dads Army** in the sidebar. This also works in the Home Assistant Companion app, including away from home if you use Home Assistant Cloud.
- **Straight from the phone's browser:** open `http://<your-home-assistant-address>:8080` while on the home Wi-Fi, then use **Add to Home Screen** to give it its own app icon.

## Dashboard sensors

While Dads Army is running, it keeps these sensors up to date in Home Assistant. They change within a few seconds of any update in the app.

| Sensor | Shows | Extra details (attributes) |
|---|---|---|
| `sensor.dads_army_hold_out` | Days you could hold out (the lower of food and water) | `food_days`, `water_days`, `runs_out_first`, `target_days`, `target_met`, `people` |
| `sensor.dads_army_food_days` | Days of food | |
| `sensor.dads_army_water_days` | Days of water | |
| `sensor.dads_army_kit_stocked` | Kit and supplies against their targets, in % | |
| `sensor.dads_army_out_of_stock` | Items with a target but none in stock | `items` (each has `name`, `get`, `unit` and `text`), `total` |
| `sensor.dads_army_low_stock` | Items with some stock, but below target | `items`, `total`, `below_target_total` |
| `sensor.dads_army_expired` | Items with stock past its best-before date | `items` (each has `name`, `qty`, `expiry`, `days`, `location` and `text`), `total` |
| `sensor.dads_army_expiring_soon` | Items reaching their best-before date within your warning window (HQ) | `items`, `total`, `warn_days` |
| `sensor.dads_army_next_expiry` | Date of the next thing to expire | `name`, `qty`, `location`, `days` |
| `sensor.dads_army_supply_run` | Number of things on the shopping list | `items`, `extras` |
| `binary_sensor.dads_army_attention` | **On** if anything has expired or run out | `reasons` |

Each list holds up to 30 entries; `total` gives the full count. The numbers are recorded in Home Assistant's history, so you can chart how your readiness changes over time.

Home Assistant doesn't keep these sensors after it restarts, so Dads Army sends them again within a minute. While Dads Army is stopped, they show as unavailable.

## Dashboard card

To add it:

1. Open a dashboard, click the pencil (**Edit dashboard**), then **Add card**.
2. Scroll to the bottom and choose **Manual**.
3. Paste everything below in place of what's there, then click **Save**.

```yaml
type: vertical-stack
cards:
  - type: tile
    entity: sensor.dads_army_hold_out
    name: Could hold out for
    icon: mdi:shield-home
  - type: grid
    columns: 2
    square: false
    cards:
      - type: tile
        entity: sensor.dads_army_expired
        name: Expired
        color: red
      - type: tile
        entity: sensor.dads_army_expiring_soon
        name: Expiring soon
        color: amber
      - type: tile
        entity: sensor.dads_army_out_of_stock
        name: Out of stock
        color: deep-orange
      - type: tile
        entity: sensor.dads_army_low_stock
        name: Running low
        color: amber
      - type: tile
        entity: sensor.dads_army_supply_run
        name: Supply run
      - type: tile
        entity: sensor.dads_army_kit_stocked
        name: Kit stocked
  - type: markdown
    title: Needs attention
    content: |
      {% macro part(icon, title, entity, n) -%}
      {% set rows = state_attr(entity, 'items') or [] -%}
      {% if rows -%}
      #### <ha-icon icon="{{ icon }}"></ha-icon> {{ title }} ({{ states(entity) }})
      {% for i in rows[:n] -%}
      - **{{ i.name }}** · {{ i.text }}
      {% endfor -%}
      {% set more = (state_attr(entity, 'total') | int(0)) - n -%}
      {% if more > 0 -%}
      - …and {{ more }} more
      {% endif %}
      {% endif -%}
      {%- endmacro -%}
      {{ part('mdi:calendar-remove', 'Expired', 'sensor.dads_army_expired', 6) }}
      {{- part('mdi:calendar-alert', 'Expiring soon', 'sensor.dads_army_expiring_soon', 6) }}
      {{- part('mdi:package-variant-remove', 'Out of stock', 'sensor.dads_army_out_of_stock', 5) }}
      {{- part('mdi:package-down', 'Running low', 'sensor.dads_army_low_stock', 5) }}
      {%- if states('sensor.dads_army_expired') in ['unknown', 'unavailable'] -%}
      <ha-icon icon="mdi:lan-disconnect"></ha-icon> Dads Army isn't sending updates. Check the app is running.
      {%- elif states('sensor.dads_army_expired') | int(0) == 0
            and states('sensor.dads_army_expiring_soon') | int(0) == 0
            and states('sensor.dads_army_out_of_stock') | int(0) == 0
            and states('sensor.dads_army_low_stock') | int(0) == 0 -%}
      <ha-icon icon="mdi:check-circle"></ha-icon> All squared away: nothing expired, expiring or short.
      {%- endif %}
  - type: history-graph
    title: Days you could last
    hours_to_show: 720
    entities:
      - entity: sensor.dads_army_food_days
        name: Food
      - entity: sensor.dads_army_water_days
        name: Water
```

You can also put any single sensor on its own card, such as a **Tile** card or a **Gauge** card for `sensor.dads_army_hold_out`. On your phone, the Companion app's home-screen widgets can show it too.

## Automation ideas

- Get a notification when `binary_sensor.dads_army_attention` turns **on**. Its `reasons` attribute says what's wrong.
- Get a weekly digest of `sensor.dads_army_expiring_soon`, so you use things up before they go off.

## Your data

Your data is kept in the app's own storage. It survives restarts and updates, and it's included in your Home Assistant backups. On top of that:

- Dads Army saves a copy of its database every day and keeps the last 14.
- HQ → **Download backup** saves a copy to your phone.
- HQ → **Print full inventory** gives you a paper copy to keep with the stores.

## Security

There's no separate login. Anyone who can reach port 8080 on your home network can open it. Through the sidebar, only signed-in Home Assistant users can open it. Don't port-forward 8080 on your router.
