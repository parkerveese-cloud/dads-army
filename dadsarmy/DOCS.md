# Dads Army

A stores tracker for food, water and emergency kit, built to be used from your phone.

## Opening it

- **In Home Assistant:** click **Dads Army** in the sidebar. This also works in the Home Assistant Companion app, including away from home if you use Home Assistant Cloud.
- **Straight from the phone's browser:** open `http://<your-home-assistant-address>:8080` while on the home Wi-Fi, then use **Add to Home Screen** to give it its own app icon.

## Dashboard sensors

While Dads Army is running, it keeps these sensors up to date in Home Assistant. They change within a few seconds of any update in the app.

| Sensor | Shows | Extra details (attributes) |
|---|---|---|
| `sensor.dads_army_readiness` | How close you are to your readiness target, in %. 100% means you could hold out for the full target. | `hold_out_days`, `target_days`, `target_met` |
| `sensor.dads_army_hold_out` | Days you could hold out (the lower of food and water) | `food_days`, `water_days`, `runs_out_first`, `target_days`, `target_met`, `people` |
| `sensor.dads_army_food_days` | Days of food | |
| `sensor.dads_army_water_days` | Days of water | |
| `sensor.dads_army_kit_stocked` | Kit and supplies against their targets, in % | |
| `sensor.dads_army_out_of_stock` | Items with a target but none in stock | `items` (each has `name`, `get`, `unit` and `text`), `total` |
| `sensor.dads_army_low_stock` | Items with some stock, but below target | `items`, `total`, `below_target_total` |
| `sensor.dads_army_expired` | Items with stock past its best-before date | `items` (each has `name`, `qty`, `expiry`, `days`, `location` and `text`), `total`, `newly_expired` (went out of date overnight) |
| `sensor.dads_army_expiring_soon` | Items reaching their best-before date within your warning window (HQ) | `items`, `total`, `warn_days`, `expires_today` (on their last day) |
| `sensor.dads_army_next_expiry` | Date of the next thing to expire | `name`, `qty`, `location`, `days` |
| `sensor.dads_army_supply_run` | Number of things on the shopping list | `items`, `extras` |
| `binary_sensor.dads_army_attention` | **On** if anything has expired or run out | `reasons` |

Each list holds up to 30 entries; `total` gives the full count. The numbers are recorded in Home Assistant's history, so you can chart how your readiness changes over time.

Home Assistant doesn't keep these sensors after it restarts, so Dads Army sends them again within a minute. While Dads Army is stopped, they show as unavailable.

When the last of something is used up, Dads Army also fires a `dads_army_ran_out` event. Its data has `message` (ready to send, such as "Baked beans has run out. It's on the supply run: get 6 tins."), `names`, `count` and `items`. The phone alerts below use it.

## Dashboard card

To add it:

1. Open a dashboard, click the pencil (**Edit dashboard**), then **Add card**.
2. Scroll to the bottom and choose **Manual**.
3. Paste everything below in place of what's there, then click **Save**.

```yaml
type: vertical-stack
cards:
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.dads_army_readiness
        name: Readiness
        min: 0
        max: 100
        severity:
          green: 100
          yellow: 50
          red: 0
      - type: vertical-stack
        cards:
          - type: tile
            entity: sensor.dads_army_hold_out
            name: Hold out
            icon: mdi:shield-home
          - type: tile
            entity: sensor.dads_army_food_days
            name: Food
          - type: tile
            entity: sensor.dads_army_water_days
            name: Water
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

The gauge is red below half your target, amber from half, and green once you've reached it.

You can also put any single sensor on its own card, such as a **Tile** card. On your phone, the Companion app's home-screen widgets can show them too. If you link the supply run to a to-do list (below), a **To-do list** card shows it on the dashboard and lets you tick things off.

## Phone alerts

Two ready-made automations (blueprints) send Dads Army news to your phone. You need the Home Assistant Companion app on the phone.

| Blueprint | What it sends |
|---|---|
| **Dads Army: phone alerts** | Straight away when something runs out. Every morning (8:30 unless you change it), anything that went out of date overnight and anything on its last day. |
| **Dads Army: weekly round-up** | Once a week (Sunday 6pm unless you change it): what to use first, anything out of date, the supply run and how long you could hold out. |

To set one up:

1. Import it with its button:

   [![Import Dads Army: phone alerts](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fparkerveese-cloud%2Fdads-army%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fdads_army_phone_alerts.yaml)
   [![Import Dads Army: weekly round-up](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fparkerveese-cloud%2Fdads-army%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fdads_army_weekly_roundup.yaml)

   Or go to **Settings → Automations & scenes → Blueprints → Import blueprint** and paste its address:
   - `https://github.com/parkerveese-cloud/dads-army/blob/main/blueprints/automation/dads_army_phone_alerts.yaml`
   - `https://github.com/parkerveese-cloud/dads-army/blob/main/blueprints/automation/dads_army_weekly_roundup.yaml`
2. On the **Blueprints** tab, click the blueprint, choose your phone (and change the times if you like), then **Save**.

Tapping a notification opens Dads Army. On Android the notifications have their own **Dads Army** channel, so you can set their sound in the phone's settings. For another phone, make a second automation from the same blueprint.

## Supply run on a to-do list

Dads Army can keep the supply run on a Home Assistant to-do list. It then shows in the **To-do lists** panel and the Companion app, and you can add to it by voice through Assist: *"Add matches to the supply run list"*.

To turn it on, open Dads Army, go to **HQ → Home Assistant**, and tap **Make a "Supply run" list**. This makes a Local To-do list for you. You can choose a list you already have instead, but it's best to keep one just for Dads Army.

How it works:

- **Below-target items** appear as, for example, *Bottled water (5L): 16 bottles*. They update as your stores change and come off the list once you're back up to target.
- **Ticking off** a below-target item in Home Assistant marks it on the supply run in Dads Army. Tap **Got it** there to put it away with its best-before date.
- **Deleting** a below-target item in Home Assistant keeps it off the list until the amount you need changes.
- **Extras** (the "Also get" list) are shared both ways. Add, tick, rename or delete them on either side.
- Anything added to the list in Home Assistant, including by voice, becomes an extra on the supply run.

Changes show up on the other side within about half a minute.

## Automation ideas

- Use `binary_sensor.dads_army_attention` for a warning light: it's **on** whenever something has expired or run out, and its `reasons` attribute says what.
- Flash a light or announce on a speaker when the `dads_army_ran_out` event fires.
- Get a reminder when `sensor.dads_army_readiness` drops below 100%.

## Your data

Your data is kept in the app's own storage. It survives restarts and updates, and it's included in your Home Assistant backups. On top of that:

- Dads Army saves a copy of its database every day and keeps the last 14.
- HQ → **Download backup** saves a copy to your phone.
- HQ → **Print full inventory** gives you a paper copy to keep with the stores.

## Security

There's no separate login. Anyone who can reach port 8080 on your home network can open it. Through the sidebar, only signed-in Home Assistant users can open it. Don't port-forward 8080 on your router.
