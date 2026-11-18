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
| `sensor.dads_army_food_days` | Days of food, eating whatever goes off first | `goes_off_first_days` |
| `sensor.dads_army_water_days` | Days of water | |
| `sensor.dads_army_kit_stocked` | Kit and supplies against their targets, in % | |
| `sensor.dads_army_out_of_stock` | Items with a target but none in stock that's still in date | `items` (each has `name`, `get`, `unit` and `text`), `total` |
| `sensor.dads_army_low_stock` | Items with some stock, but below target. Out-of-date stock doesn't count towards a target, so it shows here as needing replacing. | `items` (each also has `out_of_date`), `total`, `below_target_total` |
| `sensor.dads_army_expired` | Items with stock past its best-before date | `items` (each has `name`, `qty`, `expiry`, `days`, `location` and `text`), `total`, `newly_expired` (went out of date overnight) |
| `sensor.dads_army_expiring_soon` | Items reaching their best-before date within your warning window (HQ), which can be earlier for some categories, such as medicines | `items`, `total`, `warn_days`, `expires_today` (on their last day), `expires_in_7_days` (exactly a week to go: time to use them up) |
| `sensor.dads_army_next_expiry` | Date of the next thing to expire | `name`, `qty`, `location`, `days` |
| `sensor.dads_army_supply_run` | Number of things on the shopping list | `items`, `extras`, `cost` (from the prices you've set, in £) |
| `sensor.dads_army_supplies` | Days until the first thing with a daily use runs out (such as tablets or toilet roll). Unknown if nothing has a daily use set. | `items` (each has `name`, `days`, `have`, `per_day` and `text`), `runs_out_first`, `target_days` |
| `sensor.dads_army_checks_due` | Routine checks that are due, overdue or not done yet | `items` (each has `name`, `due`, `days`, `every` and `text`), `due_today`, `due_soon` (within a week), `next_check`, `checks_total` |
| `sensor.dads_army_stores_value` | What the stores are worth, in £, from the prices you've set | `supply_run_cost`, `priced_items`, `items_total` |
| `sensor.dads_army_warnings` | Official warnings in force for where you live (see **Warnings** below). 0 while warnings are switched off. | `items` (each has `title`, `level`, `severity` 1–3, `source`, `area`, `when`, `url` and `text`), `highest` (yellow, amber or red), `max_severity`, `enabled`, `checked_at`, `health_news` |
| `sensor.dads_army_alert_level` | The household alert level: LOW, MODERATE, SUBSTANTIAL, SEVERE or CRITICAL (see below) | `level` (1–5), `meaning`, `reasons`, `guidance` (each with `label`, `source` and `text`), `scale`, `escalated`, `escalated_why`, `notes` |
| `sensor.dads_army_resilience` | How resilient the household is, in %: the average of ten areas, from water and power to communications and safety (see **Resilience** below) | `areas` (each with `name`, `pct`, `dot`, `done`, `total`, `essentials_missing` and `next`), `next_steps`, `measures` (every recommendation, by area), `done`, `total` |
| `sensor.dads_army_live` | The wider picture: how many of the live feeds have something worth watching (see **The wider picture** below) | `rows` (each with `name`, `emoji`, `text`, `state` good, warn or bad, and `dot`), `enabled`, `checked_at` |
| `sensor.dads_army_trends` | How many counts in the wider picture are well up on the last two weeks (see **Trends in the wider picture** below). 0 while warnings are off. | `trends` (each with `title`, `text`, `source`, `name`, `value` and `usual`), `enabled` |
| `sensor.dads_army_reservoirs` | How full England's reservoirs are, in %, from the Environment Agency's weekly drought report. Only once there's a report. | `vs_average` (against the time of year), `week_to`, `area`, `drought_stage`, `hosepipe_ban`, `stale`, `url` |
| `sensor.dads_army_uk_threat_level` | The UK national threat level: Low, Moderate, Substantial, Severe or Critical. Only with the threat level source on. | `means`, `northern_ireland`, `raised_on`, `since`, `options` |
| `sensor.dads_army_pet_food_days` | Days the pet food lasts, from its **Used a day**. Only once pet food has one. | `runs_out_first`, `pets`, `target_days` |
| `sensor.dads_army_places` | How many places are on the map (see **Places to go** below) | `located`, `active` (emergencies happening now), `hazards` (each with `what`, `emoji`, `active`, `advice` and `places`), `help` |
| `geo_location.dads_army_*` | Home and each place to go, for Home Assistant's map card. The state is the distance from home in km. | `latitude`, `longitude`, `source` (`dads_army`, or `dads_army_far` for places over 20 km away), `what`, `direction`, `for` |
| `binary_sensor.dads_army_attention` | **On** when something needs doing now: stock past its best-before date, a check that's overdue, or a serious warning (amber or worse). Things you haven't bought yet don't count: they're on the supply run. | `reasons` |

Each list holds up to 30 entries; `total` gives the full count. The numbers are recorded in Home Assistant's history, so you can chart how your readiness changes over time.

Home Assistant doesn't keep these sensors after it restarts, so Dads Army sends them again within a minute. While Dads Army is stopped, they show as unavailable.

When the household alert level changes, Dads Army fires a `dads_army_alert_level` event. Its data has `level`, `name`, `previous`, `previous_name`, `rising`, `reasons` and `message` (ready to send, with the main reason and the first thing to do).

When a new warning comes in, Dads Army fires a `dads_army_warning` event. Its data has `message`, `count`, `max_severity` and `items` (each with `title`, `level`, `severity`, `source`, `area` and `url`).

When the last of something is used up, Dads Army also fires a `dads_army_ran_out` event. Its data has `message` (ready to send, such as "Baked beans has run out. It's on the supply run: get 6 tins."), `names`, `count` and `items`. The phone alerts below use it.

## The Home front dashboard

The quickest way to get Dads Army on your Home Assistant dashboards. Dads Army offers to make it the first time you open it in Home Assistant. You can also tap **?** at the top of the app, then **Put Dads Army on your Home Assistant dashboard**, or go to **HQ → Home Assistant**. It can set up today's checklist and the supply run list at the same time.

A **Home front** dashboard appears in the Home Assistant sidebar and in the Companion app. It's built from Home Assistant's own cards, so there's nothing extra to install. It has:

- **The household alert level** in a compact, colour-coded card: the level, the main reason, and the whole scale on one line.
  - **Why, and what to do now** (or the **Alert level** badge at the top) opens a page with every reason and all the labelled advice.
  - The **i** next to the heading opens **What the levels mean**.
  - Home Assistant has no pop-ups of its own, so these open as pages with a back arrow.
- **Warnings** in force for where you live
- **The wider picture:** rivers and power cuts near home, the electricity grid, gas storage, air quality, space weather and the pound, one line each with a green, amber or red dot
- **Today's checklist:** the routine checks that are due, ready to tick off (see below)
- **Resilience:** how ready you are in each of the ten areas, two to a row, with the next things to do. **All recommendations** (or the **Resilience** badge) opens a page with every recommendation, area by area, and what's done.
- **Stores:** expired, expiring soon, out of stock, running low, kit stocked, what the stores are worth, and what to use first
- **Supply run**, with your supply run list if you've linked one, and a button that opens Dads Army
- **Places to go:** a map of home and the places near it, and where you could go for each kind of emergency, with what's happening now at the top (see below)
- a graph of the days you could last, over the last month

If you link a list afterwards, tap **Rebuild it** so the list shows on the dashboard. Rebuilding replaces any changes you've made to the dashboard. To customise it safely, copy cards from it into a dashboard of your own.

## Today's checklist

Dads Army can put your routine checks on a Home Assistant to-do list. In **HQ → Home Assistant**, tap **Make a "Dads Army checks" list**, or choose a list you already have.

- Checks that are due, overdue or not done yet go on the list, with their due dates. Home Assistant shows overdue ones in red.
- Tick one off on the dashboard or in the Companion app, and Dads Army marks it done and works out when it's next due.
- Do a check in Dads Army instead, and it comes off the list.
- Delete one from the list and it stays off until it's next due.
- Anything else you put on the list is left alone.

## Dashboard card

To add Dads Army to a dashboard of your own:

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
      - type: tile
        entity: sensor.dads_army_checks_due
        name: Checks due
        color: purple
      - type: tile
        entity: sensor.dads_army_supplies
        name: Daily supplies
  - type: markdown
    title: Needs attention
    content: |
      {% set warns = state_attr('sensor.dads_army_warnings', 'items') or [] -%}
      {% if warns -%}
      #### <ha-icon icon="mdi:alert-octagon"></ha-icon> Warnings ({{ states('sensor.dads_army_warnings') }})
      {% for i in warns[:5] -%}
      - **{{ i.level }}** · {{ i.title }}
      {% endfor %}
      {% endif -%}
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
      {{- part('mdi:clipboard-check-outline', 'Checks due', 'sensor.dads_army_checks_due', 5) }}
      {%- if states('sensor.dads_army_expired') in ['unknown', 'unavailable'] -%}
      <ha-icon icon="mdi:lan-disconnect"></ha-icon> Dads Army isn't sending updates. Check the app is running.
      {%- elif states('sensor.dads_army_expired') | int(0) == 0
            and states('sensor.dads_army_expiring_soon') | int(0) == 0
            and states('sensor.dads_army_out_of_stock') | int(0) == 0
            and states('sensor.dads_army_low_stock') | int(0) == 0
            and states('sensor.dads_army_checks_due') | int(0) == 0
            and states('sensor.dads_army_warnings') | int(0) == 0 -%}
      <ha-icon icon="mdi:check-circle"></ha-icon> All squared away: no warnings, and nothing expired, expiring, short or due.
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
| **Dads Army: phone alerts** | When the household alert level goes up (to SUBSTANTIAL or higher unless you choose otherwise). Straight away when a new warning comes in (amber and worse unless you choose otherwise), and when something runs out. Every morning (8:30 unless you change it), anything that went out of date overnight, anything on its last day, and any routine check that falls due that day. |
| **Dads Army: weekly round-up** | Once a week (Sunday 6pm unless you change it): any warnings in force, what to use first, anything out of date, checks that are due, the supply run, what runs out first, how long you could hold out, and how resilient you are, with the next things to do. |

**Already set these up before Dads Army 1.6.0?** Re-import them to get warnings, checks and daily supplies: go to **Settings → Automations & scenes → Blueprints**, open the **⋮** menu next to each Dads Army blueprint, and choose **Re-import blueprint**. Your automations keep their settings.

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

## Household alert level

Dads Army works out where the household stands on a five-step scale. It shows at the top of the Sitrep and the Home front dashboard, in `sensor.dads_army_alert_level`, and on your phone through the phone alerts blueprint.

The names are the UK's own five national threat levels, the nearest British equivalent to America's DEFCON. This is the household's own level, though, not the official threat level, which is set by MI5's Joint Terrorism Analysis Centre.

| | Level | What it means for the household |
|:-:|:--|:--|
| 🟩 | **LOW** | Nothing is threatening the household and the stores would last at least 3 days. Carry on as normal. |
| 🟨 | **MODERATE** | Something to keep an eye on: a yellow warning, a minor problem at home, or stores that wouldn't last 3 days. Stay aware. |
| 🟧 | **SUBSTANTIAL** | Disruption is likely: an amber warning, a power cut, a leak, or a cold or hot home. Get ready. |
| 🟥 | **SEVERE** | Disruption is highly likely or under way: a red warning, a flood warning, a long power cut, or a dangerously cold or hot home. Act now. |
| ⬛ | **CRITICAL** | Danger to life, now or very soon: an Emergency Alert for your area, a severe flood warning, or a gas, carbon monoxide or smoke alarm. Follow the emergency services' instructions. |

It's worked out from three things:

- **Warnings in force**, if you've switched them on.
- **Your home's own sensors**, if you've chosen them (see below).
- **Your stores and resilience:** food or water for under 3 days, or any area of resilience missing an essential, makes it at least MODERATE.

If it's SUBSTANTIAL and you'd be less able to cope, it goes up to SEVERE: when the food or water wouldn't last 3 days, when there's a power cut and you have no torches or power bank, or when the home is cold and you have no blankets or warm clothes. Only real danger makes it CRITICAL.

The exact rules are on the dashboard's **What the levels mean** page, and behind the **i** next to the level in the app.

Each level comes with **what to do now**, worst problem first. Each piece of advice is labelled with where it comes from:

- **UK Government:** advice from Be Ready (gov.uk), Ofcom, the NHS, UKHSA, the Met Office, the Environment Agency, DEFRA, Ofgem, the Foreign Office and the Fire Kills campaign. It's put into plain statements, not quoted word for word.
- **SAS Survival Handbook:** John "Lofty" Wiseman's PLAN priorities (Protection, Location, Acquisition of water and food, Navigation), applied to a household. These are paraphrased, not quoted.
- **Fire & rescue services**, **Electricity networks (105)** and **Dads Army tip** for the rest.

### Home sensors

In Dads Army, open **HQ → Home sensors** (or tap **?**, then **Choose home sensors**). Tap **Suggest sensors for me**, check the choices, then **Save**. Dads Army reads the sensors every 15 seconds and uses them like this:

| Sensor | Raises the level when |
|:--|:--|
| Indoor temperature (the coldest and warmest room) | Under 16°C (MODERATE), 12°C (SUBSTANTIAL) or 9°C (SEVERE); 27°C or more (MODERATE), 30°C (SUBSTANTIAL) or 33°C (SEVERE). Under 18°C brings UKHSA's cold-home advice. |
| Outdoor temperature (a sensor or your weather forecast) | −5°C or colder, or 30°C or hotter (MODERATE); −10°C or 35°C (SUBSTANTIAL) |
| Indoor humidity | 80% or more (MODERATE), for damp and mould |
| Mains electricity | A power cut (SUBSTANTIAL); over 12 hours (SEVERE) |
| Backup battery or UPS charge | Under 20% during a power cut (SEVERE) |
| Gas or carbon monoxide alarm | Going off (CRITICAL) |
| Smoke or heat alarm | Going off (CRITICAL) |
| Water leak sensor | A leak (SUBSTANTIAL) |
| Internet connection | Down (MODERATE): warnings can't update |
| Outdoor air quality (PM2.5) | 35 µg/m³ or more (MODERATE), 55 (SUBSTANTIAL) or 75 (SEVERE) |

For **mains electricity**, choose something that only changes in a power cut, such as a UPS status, a mains voltage sensor or a power-cut sensor. Without a UPS, Home Assistant itself stops in a power cut. Power cuts and their length are noted in Dads Army's activity log.

## Resilience

Being ready isn't just food and water. Dads Army looks at ten areas, and food and water are two of them:

| | Area | For example |
|:-:|:--|:--|
| 💧 | Water | 3 days of drinking water, a way to make water safe, knowing where the stopcock is |
| 🥫 | Food & cooking | 3 days of food that needs no fridge, a tin opener, a camping stove and fuel |
| 🔋 | Power & light | Torches and batteries, a charged power bank, a UPS for the router and Home Assistant (a step higher if *Your power supply* shows your local network has more faults than most), the Priority Services Register |
| 🧣 | Warmth | Blankets or sleeping bags, warm layers, a room you can keep warm |
| 📻 | Communications | A battery or wind-up radio, numbers on paper, Emergency Alerts, a battery backup for a digital landline, walkie-talkies |
| 🩹 | Health & medicines | A first aid kit, spare medicines, a written list of medicines, ICE contacts on phones |
| 🧻 | Hygiene & sanitation | Sanitiser, wipes and toilet roll, an emergency toilet |
| 🧯 | Fire & home safety | Smoke and carbon monoxide alarms, knowing how to turn off the gas, a fire blanket |
| 💷 | Money & documents | Cash in coins and notes, copies of documents, insurance details |
| 🎒 | Plan & getting out | A household plan, two meeting places, a grab bag, escape routes, neighbours who need checking on |

There are about 65 recommendations in all. Each one is marked **essential**, **recommended** or **extra**, and labelled with where it comes from: mostly the UK Government's **Be Ready** checklist, **Ofcom** (staying connected in a power cut) and the **Fire Kills** campaign, plus a few Dads Army tips.

**Dads Army ticks off what it can see for itself:**

- **Your stores:** a radio, torches, a power bank, a first aid kit and so on, against their targets.
- **The emergency plan:** where the stopcock is, meeting places, numbers on paper.
- **Routine checks**, if they're up to date.
- **Warnings**, if they're switched on.
- **Home sensors:** a UPS battery, smoke and carbon monoxide alarms.

**You tick the rest off yourself.** Or tap **Not for us**, for example for a gas tap if you have no gas. **Add to stores** puts anything missing into the stores at zero, so it's on the supply run.

**How it's scored:** each area's score is how much of it is done. Essentials count three times as much as extras, and recommended things twice as much. Partly done counts in part, and anything not for you is left out. The overall figure is the average of the ten areas.

It shows on the Sitrep, under the alert level, with the next steps. Tap an area to see what's done and what's left. An area missing an essential keeps the household alert level at MODERATE or higher.

Some recommendations only show when they apply. Baby supplies and school numbers show if you have children, pet food if you have pets, and the sensor ones only in Home Assistant.

## Places to go

If staying at home isn't safe, where could you go? Dads Army suggests places near home for each kind of emergency, and shows them on a map:

| | If it's… | Dads Army suggests |
|:-:|:--|:--|
| 🌊 | Flooding | High ground, then community halls and leisure centres away from the flood |
| 🌬️ | Storms and high winds | Sturdy public buildings: community halls, leisure centres, libraries |
| 🔥 | A wildfire | Community halls, leisure centres and libraries further from the fire than you are |
| 🫨 | An earthquake | Parks and open spaces, and emergency assembly points |
| 🚧 | Civil unrest | Your own places: family or friends outside the area |
| 🌡️ | A heatwave | Cool spaces: libraries, leisure centres and community centres |
| 🧣 | Cold, or a long power cut | Warm spaces: libraries and community centres |
| 🎒 | Having to leave home | Where rest centres usually open: leisure centres and community halls |
| 🏥 | A medical emergency | The nearest hospitals with emergency care |

Each comes with a line of advice. The nearest fire station, police station and hospital are listed too.

**What's happening now comes first.** A flood warning, a wildfire nearby, an amber storm warning, a cold home or a power cut all put that kind of emergency at the top. The suggestions then appear in the alert level's **What to do now**. While there's a flood warning or a fire nearby, Dads Army leaves out places that are nearer to it than you are.

**Your own places come first, too.** On the **Plan** tab, under **Places to go**, add family or friends you could stay with, and your meeting places, and say what each one is for. To say where a place is, paste a link from Google Maps, Apple Maps or OpenStreetMap, or type its coordinates (long-press the place in your maps app to get them).

**Where the suggestions come from.** The app comes with a list of about 58,000 places across the UK, built from OpenStreetMap: community centres and halls, leisure centres, libraries, hospitals with emergency care, fire and police stations, emergency assembly points, named hills and parks. Dads Army picks the ones near home on your own machine, so nothing is looked up online and nobody is told where you live. The list is updated with new versions of the app. Place data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), under the Open Database Licence.

They're possibilities, not official refuges. In an emergency, councils decide where rest centres open and announce it at the time, on local radio and their websites.

**Where home is:** Dads Army uses the location in the warnings settings, or Home Assistant's home location if that's empty.

**On the Home front dashboard**, the map is Home Assistant's own map card. The places on it are `geo_location` entities with the source `dads_army`. Ones more than 20 km away use `dads_army_far`, so the map doesn't zoom right out to fit them in. Home Assistant's map downloads its map images from the internet, unlike the rest of Dads Army. In the app, the Plan tab shows a simple sketch of home and the places around it, which needs no internet.

## Warnings

Dads Army can show official warnings for where you live: on the Sitrep, on the **Plan** tab, in `sensor.dads_army_warnings`, and on your phone through the phone alerts blueprint. They're off until you switch them on under **HQ → Warnings**.

| Source | What you get |
|---|---|
| Met Office | Yellow, amber and red weather warnings for your region |
| Environment Agency, SEPA and Natural Resources Wales | Flood alerts, flood warnings and severe flood warnings near you: England's, Scotland's and Wales' (see [The rest of the UK](#the-rest-of-the-uk)) |
| GOV.UK Emergency Alerts | Alerts about a danger to life, while they're being sent and for 12 hours after. Only one whose area takes in home (your district, county, region, constituency or police force area, or the whole UK, Great Britain or your nation, compared as whole names) raises your alert level, if you tick **Only alerts for my area**: to know that, home's location rounded to about 100 m is looked up once at postcodes.io. It's off until you tick it, and until then every alert counts |
| GDACS (the UN and EU disaster alert system) | Orange and red alerts for earthquakes, floods, storms, volcanoes and tsunamis within 1,000 km, and volcanoes within 2,000 km. Only one in the UK or Ireland, within 300 km, or a volcano within 2,000 km (ash closes airports) raises your alert level: an earthquake in Norway shows here but doesn't, and nor does a drought across Europe that lists Ireland among many countries |
| NASA FIRMS (optional) | Possible fires within 10 km: hotspots seen by satellite in the last 24 hours |
| UK Health Security Agency (optional) | Its latest news, such as cold-weather and heat-health alerts |
| WHO (optional) | Disease outbreak news |

How it works:

- Dads Army checks every 15 minutes while the internet is up. It downloads the same public files for everyone and works out which warnings are near you on your own machine. Your location isn't sent with them, except by the few options that say so, each off until you tick it (see [What leaves your network](#what-leaves-your-network)).
- Your location comes from Home Assistant's home location. You can set it by hand instead in the warnings settings. The Met Office region is worked out from it, and you can change that too.
- Tap a warning for the full message, a link to the official page, what to do, and the parts of your emergency plan that matter, such as where to meet and how to turn things off.
- If the internet goes down, everything else carries on, and the last warnings found stay on show with when they were checked.
- **Show a map** (under Map in the warnings settings, off to start with) adds a map of the warnings and nearby reports to the wider picture. Its map pictures come from OpenStreetMap: see [The live alerts map](#the-live-alerts-map-1190).
- Keep **Emergency Alerts** switched on in your phone's settings too. They reach the phone directly, much faster than any feed.
- Every request carries only Dads Army's name: no cookies, no referrer and nothing about you.

Flood warnings in Scotland come from SEPA, and in Wales from Natural Resources Wales. Northern Ireland has no public flood warning feed yet, so there the source says it's not available for your area.

**About possible fires.** There's no public feed of UK wildfire warnings, so this uses NASA's satellite fire detections. They're the only live source that covers the whole UK.
- A satellite sees any large heat source. Most UK detections are controlled heather burning (allowed in autumn and winter), farm fires or industrial flares, not wildfires. That's why they show as a yellow **Possible fire**.
- Dads Army learns to leave out places that come up again and again over a week or more, such as refinery flares. For anything else that isn't a wildfire, open it and tap **Not a wildfire: ignore this spot**.
- Satellites only pass over a few times a day, so a fire can be a few hours old before it shows.
- If you can see a fire that looks out of control, call 999.

## The wider picture

Switched on with the warnings, and listed under **Live information** in the warnings settings, where each can be switched off. On the Sitrep, the Home front dashboard and `sensor.dads_army_live`. Tap a line for the details.

| Feed | What you get | Warns when |
|---|---|---|
| River levels (Environment Agency, England; SEPA, Scotland) | The river gauges within 10 km, against their usual range, and whether each is rising or falling | A river is above its usual range, or above its highest in recent years |
| Power cuts (UK Power Networks, National Grid, SSEN, Northern Powergrid; Electricity North West and NIE Networks near their networks) | Power cuts and planned work within your near you distance (10 km unless you change it) | A power cut within 2 km, or planned work there |
| The electricity grid (NESO, through Elexon) | Electricity margin and capacity market notices | A notice is in force; a warning of planned rota power cuts counts as serious |
| Gas storage (National Gas) | How full Great Britain's gas storage is, against a year ago | It's emptying much faster than a year ago over two weeks, or it's nearly empty in winter |
| Air quality (Defra UK-AIR) | The Daily Air Quality Index at the nearest monitoring site, and the forecast | It's high (7 or more) now or in the next two days |
| Space weather (NOAA) | The geomagnetic storm scale, now and for the next three days | A severe storm (G4 or G5) |
| The pound (Bank of England) | The pound against the dollar and the euro, and Bank Rate | The pound falls 3% in a week, or 5% in two weeks. A Bank Rate change shows as news. |

- Like the warnings, each feed is the whole country (or a whole network) in one download, and Dads Army picks out what's near home itself. Nothing about you is sent with them.
- Slow-changing feeds are fetched less often: gas storage every three hours, the pound every six.
- A power cut within 2 km, a high river, high air pollution, a severe solar storm or a warning of rota power cuts raises the household alert level to at least MODERATE. A very high river raises it to SUBSTANTIAL. Gas storage and the pound don't change the level.
- Not covered yet: river levels in Wales (Natural Resources Wales publishes them, but not a usual range to compare them with) and Northern Ireland, and power cuts from SP Energy Networks, which only publishes them to registered users: a home on its network gets a note saying so. There's no official free source for the FTSE 100, so it isn't included.

Sources: Environment Agency flood and river level data from the real-time data API (Beta), SEPA's water levels and Defra's UK-AIR, under the Open Government Licence; power cut data from UK Power Networks, National Grid Electricity Distribution, SSEN and Northern Powergrid under their open data licences, and from Electricity North West's and NIE Networks' power cut maps; system warnings from Elexon's BMRS; National Gas's data portal; NOAA's Space Weather Prediction Center; and the Bank of England's database, under the Open Government Licence.

### Affecting you, and the lines in groups (1.18.0)

On the Sitrep, the wider picture starts with what's affecting home:

- **Affecting you:** each warning in force from the sources that touch daily life (water supply, power cuts, flood warnings, Met Office warnings, Emergency Alerts, high rivers, possible fires, heavy rain, the flood risk forecast, air quality and drought), worst first, then nearest. Each line says how serious it is, how far away, the postcodes a power cut covers, when it started or when power's expected back, and the first sentence of the details, with a colour down its left side for how serious it is. Tap it for that source's details, or the warning itself.
- It's exactly the warnings that turn a line amber or red, so a line never says all's well while Affecting you lists something from it. When there's nothing, one line says *Nothing affecting you*.
- **Nearby, not in your area:** power cuts and water supply reports within your near you distance that aren't warnings (a power cut more than 2 km away; a supply problem the water company doesn't say is yours, and that isn't close enough to count). The nearest three, and how many more. Planned work isn't listed here.
- **Then the lines:** those that need attention first, worst first (or *Nothing needs attention*), and the rest under Water and weather, Power and energy, Home, and The wider world.

**Near you** in the warnings settings (5 to 40 km, 10 km to start with) is how far power cuts and water supply reports are listed. It doesn't change what's a warning, and flood warnings and fires keep their own distances. River gauges are always within 10 km, as a high river near home is a warning.

### The live alerts map (1.19.0)

Off until you tick **Show a map** in the warnings settings (under **Map**). Then the wider picture on the Sitrep has a map under Affecting you:

- **Home**, with your near you distance as a dashed ring round it.
- **Each warning with a place** (power cuts, water supply problems, flood warnings, high rivers, possible fires and disasters near the UK) as a badge showing what it is, ringed in yellow, amber or red as in the lists. Met Office warnings and Emergency Alerts cover areas, not places, so they aren't on it.
- **Nearby, not in your area:** power cuts and water supply reports within your near you distance that aren't warnings, as smaller grey badges.
- **Routine** things are hidden until you tap **Show routine (N)** at the top left, under the zoom buttons: planned power cuts and water company work, leaks, and river gauges at their usual level. Each phone or browser remembers your choice (in its own storage).
- Tap a badge for its details. **🏠** goes back to home. **UK** shows the whole country when a warning is well outside the ring (**All** when one is abroad, such as a disaster).
- The key under the map lists only what's on it. The map follows the app's dark theme.

The map pictures are OpenStreetMap's, loaded by your phone or browser straight from `tile.openstreetmap.org` (see What leaves your network). Everything on them comes from the feeds the warnings already read, worked out on the Pi: nothing new is fetched or sent for the map. Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). The map is drawn by [Leaflet](https://leafletjs.com) (BSD 2-Clause licence), which comes with the app.

### More of the wider picture (1.15.0)

Under **More of the wider picture** in the warnings settings. All public; the rain gauges and boreholes are the whole national list, and Dads Army picks the nearest itself. Rainfall and groundwater are off until you tick them, because their readings are then asked for by the nearest gauges' and boreholes' ids, which says roughly where home is.

| Feed | What you get | Warns when |
|---|---|---|
| UK threat level (GOV.UK) | The national level set by the Joint Terrorism Analysis Centre and MI5, and Northern Ireland's | It goes up (for a week), or it's critical |
| Cyber security (NCSC) | The NCSC's news from the last two weeks | A critical flaw or live attack in the last three days |
| Travel advice (FCDO) | Countries whose advice changed in the last three days | Shown, but not a warning |
| Drought, reservoirs and hosepipe bans (Environment Agency, England) | Reservoir storage, your area's drought status, your water company's hosepipe ban | Your area is in drought, or your water company has a hosepipe ban |
| Water supply problems (six water companies) | Supply reports within your near you distance (10 km unless you change it) | A supply problem that's yours: the company says your area is affected, or two are reported within 3 km, or one within 1 km |
| Flood risk forecast (Flood Forecasting Centre's outlook for England, five days, from Check for flooding; Scottish Flood Forecast, three days) | The risk where you live, which day, and whether it's rising | Medium or high (in Scotland: flooding possible, or significant flooding possible) |
| Rainfall near you (Environment Agency, SEPA, Natural Resources Wales) | Rain in 24 hours and 7 days at the nearest gauges (within 25 km) | 30 mm or more in a day |
| Groundwater near you (Environment Agency, England) | The nearest boreholes (within 30 km) against the time of year; a deep borehole below sea level is marked, as it follows decades rather than this year's rain | Shown, but not a warning |
| The grid now (NESO, Elexon) | Carbon intensity for your region and Great Britain, the generation mix, the frequency, and the greenest 3 hours in the next day | The frequency dips below 49.8 Hz |
| Electricity margin (Elexon, NESO) | The tightest spare margin in the next 14 hours and two weeks, and Demand Flexibility Service events | The margin is under 3 GW |

- Choose your **Environment Agency area** and **water company** in the warnings settings for drought status and hosepipe bans.
- **Water supply** covers Cambridge Water, South Staffs Water, Yorkshire Water, South West Water, Bournemouth Water and NI Water customers, the companies that publish their incidents this way. Choose yours in the warnings settings: it isn't guessed from where home is (the companies' areas are too tangled for that), except in Northern Ireland, where NI Water supplies everyone. For any other company it isn't fetched or shown, and its switch says why.
- Not included: stock markets and commodity prices, as there's no free official source.

Sources: the threat level, the FCDO's travel advice and the Environment Agency's drought reports on GOV.UK; the National Cyber Security Centre; the Flood Forecasting Centre's five-day flood risk outlook (from GOV.UK's Check for flooding); Environment Agency rainfall (real-time data API) and groundwater (Hydrology API) data, all under the Open Government Licence; NESO's Carbon Intensity API (CC BY 4.0) and Data Portal; Elexon's BMRS; the regional providers below; and the water companies' public incident maps and pages.

**Your region's carbon (1.20.0).** The grid now also shows your region's carbon intensity (one of the Carbon Intensity API's 14 regions, which match the electricity networks' areas) and the greenest 3 hours in the next day. The region is worked out on the Pi from home's location, and only its number (13 is London) is asked for. In Northern Ireland, or without a location, it's Great Britain's.

### Road closures (1.20.0)

Closures on England's motorways and major A roads (National Highways' Strategic Road Network) within your near you distance. Council roads aren't included. Under **Road closures** in the warnings settings.

| Feed | What you get | Warns when |
|---|---|---|
| Road closures (National Highways, England, with your own key) | Unplanned closures on now, and planned roadworks and closures starting in the next 12 hours, nearest first (up to 40) | Amber: an unplanned closure of the whole road, on now. Yellow: lanes shut by the weather, flooding or damage to the road |

- **It needs your own free key.** Sign up at [developer.data.nationalhighways.co.uk](https://developer.data.nationalhighways.co.uk/), subscribe to **Road and Lane Closures**, and paste the key in the warnings settings. Adding it switches road closures on. The key stays on the Pi, is never shown back, and is left out of backup files and the automatic copies (paste it in again after a restore). Tick **Remove the saved key** to take it off.
- **What counts as closed.** The feed lists only the lanes affected, so a road counts as closed only when lanes are shut and none are left open, or National Highways says the road or carriageway is closed. A breakdown in one lane is listed, but isn't a warning. Planned roadworks never notify; each unplanned closure notifies once.
- **On the map** (if it's on), a closure is drawn along the stretch that's shut: unplanned ones solid in their colour with a white edge, planned roadworks dashed grey, with the routine things.
- Road closures don't change the household alert level.
- Checked about every 15 minutes. Closures are listed with the road, where, why (a collision, roadworks, the weather) and until when, with a link to Traffic England's live map.

Data: Powered by National Highways' Transport Data Feeds.

### Your power supply (1.21.0)

For homes on UK Power Networks' network (London, the South East and the East of England): the substation that supplies home, and how often that part of the network has had faults. Under **Your power supply** in the warnings settings. Elsewhere its switch says it's not for your area.

| Feed | What you get | Warns when |
|---|---|---|
| Your power supply (UK Power Networks' Open Data Portal, with your own key) | Your local substation, how many customers it serves and how much of its capacity is used; the primary substation it's fed from; that part of the network's faults each year against the network's average per substation, power cuts per customer, and the typical and longest recent cut | Never by itself. A power cut in your substation's area counts as yours (below) |

- **It needs your own free key.** Make an account on [UK Power Networks' Open Data Portal](https://ukpowernetworks.opendatasoft.com/), copy the API key from your account settings, and paste it in the warnings settings. Adding it switches the source on. Like the National Highways key, it stays on the Pi, is never shown back, and is left out of backup files and the automatic copies (paste it in again after a restore). Tick **Remove the saved key** to take it off.
- **It sends home's location to UK Power Networks.** Home's location, rounded to 4 decimal places (about 10 m), goes to UK Power Networks' portal with your key, to find which substation areas home is in. Nothing is sent until you add a key, and never for a home off its network. See *What leaves your network*.
- **A power cut at your substation is yours.** Once the area your local substation supplies is known, a live power cut inside it is a warning (*Power cut at your substation*), in Affecting you and on the map, wherever its pin is. The area's outline stays on the Pi.
- **Resilience.** If your local network had more faults than most last year (a fifth more than the average or worse), or a recent cut lasted 6 hours or more, the UPS and longer-lasting power recommendations go up a step (recommended to essential, extra to recommended), and say why.
- Checked once a day: the fault records are UK Power Networks' yearly returns to Ofgem (the Interruptions Incentive Scheme), and the network's average is asked for once a day too. The line is under Power and energy; the daily briefing isn't told the substation's name.

Data: UK Power Networks Open Data Portal (substation areas and utilisation, and the Interruptions Incentive Scheme's fault records), under the Creative Commons Attribution 4.0 licence (CC BY 4.0).

### Trends in the wider picture (1.17.0)

Each warnings check keeps a few counts, one a day for two weeks (the day's highest), and compares today's with the usual: the middle of the days before.

| Count | From |
|---|---|
| Power cuts near you (within your near you distance), and across the networks (every live power cut on the networks checked) | Power cuts |
| Flood warnings and alerts near you (within your flood distance), and across England | Flood warnings |
| Rivers above their usual range near you | River levels |
| Possible fires near you | NASA satellites |
| Grid notices | The electricity grid |

- **A trend** is today's count at twice the usual or more, and big enough to matter (2 power cuts near you, 30 across the networks, 20 flood warnings and alerts across England, and so on). It needs four days of counts before today, so a new install says nothing for the first few days, and a feed that failed doesn't count as a quiet day.
- **Things to watch** at the top of the Sitrep lists them, and the source's line turns amber. They don't raise the household alert level: they're a reason to look, not a warning.
- **Charts:** each source's details (tap a line in **The wider picture**) chart its counts a day at a time, with the usual as a dashed line. Flood warnings and fires are at the end. `GET /api/live/history?days=15` gives the figures.
- Nothing extra is fetched or sent: the counts come from the feeds already read. They're kept on the Pi for two weeks, and aren't in the downloaded backup file.

### The rest of the UK

England's feeds stop at its borders. Where they don't reach, Scotland's, Wales' and Northern Ireland's own take over, and so do the electricity networks and water companies that cover home. Each is asked only for homes it covers: in its nation or network, or near enough to the border to matter (flood warnings within your flood distance, river gauges within 30 km, rain gauges within 25 km, power cuts within your near you distance). Each is the provider's whole list, picked through on your own machine. If a neighbour's feed fails, home's own still shows; if home's own fails, the source keeps its last good result, as the others do.

| Source | Provider and feed | Licence | Covers |
|---|---|---|---|
| Flood warnings | SEPA: the flood warning and flood alert area layers behind its Floodline map (ArcGIS) | Not an official data feed: SEPA's public map | Scotland |
| Flood warnings | Natural Resources Wales: the data in its flood warning page | Not an official data feed: NRW's public page | Wales |
| River levels | SEPA's water levels service (its usual range is the median yearly low to high) | Open Government Licence | Scotland |
| Rainfall | SEPA's rain gauges (KiWIS time series, hourly totals) | Open Government Licence | Scotland |
| Rainfall | Natural Resources Wales' telemetry API (15-minute totals) | Open Government Licence | Wales |
| Flood risk forecast | The Scottish Flood Forecast's RSS feed (SEPA and the Met Office) | Public feed | Scotland |
| Power cuts | Electricity North West: the list behind its power cut map | Not an official data feed | North West England |
| Power cuts | NIE Networks: the list behind its PowerCheck map | Not an official data feed | Northern Ireland |
| Power cuts | SP Energy Networks: no public live feed, so a note with its power cut map | | Central and southern Scotland, Merseyside, Cheshire and North Wales |
| Water supply | Yorkshire Water's service events | Not an official data feed | Its customers |
| Water supply | South West Water's and Bournemouth Water's incident feeds | Not official data feeds | Their customers |
| Water supply | NI Water's current service updates page | Not an official data feed | Northern Ireland |
| Which network | Great Britain's 14 electricity licence areas, from NESO's GIS boundaries (bundled, see `places/README.md`) | NESO Open Data Licence | Great Britain |

- Which nation home is in comes from rough borders built in (a few km out near a border, which is why each feed reaches over it). Kintyre is Scotland.
- **Not for your area:** a source that can't cover home isn't fetched, and its switch in the warnings settings says why, rather than showing as failing. In Northern Ireland: flood warnings, river levels, rainfall, the flood risk forecast, and the three grid sources (Northern Ireland's grid is run with Ireland's). In Wales: the flood risk forecast (there's no open one just now). Outside England: groundwater and the drought report.
- The maps and pages that aren't official feeds could change without notice. If one does, that provider fails and says so; the others carry on.

## The daily briefing

Every morning at 6am, Claude or Gemini (your choice) reads what Dads Army already knows and searches the news, then writes one paragraph on the threats and risks to be aware of: locally, across the UK and in the world, against what's been usual over the last fortnight. Below that, kept apart, it says what people near you are posting on social media. It's at the top of the Sitrep.

- **Switch it on** in HQ, in the **Daily briefing** card under Scanning. It needs an Anthropic or a Google Gemini API key, because the news search runs on their side: Anthropic's web search, or Google's Grounding with Google Search. To add one, choose **Anthropic Claude** or **Google Gemini** under Scanning and paste your key. You can switch Scanning back afterwards; the key stays saved. Without a key, the card says so. OpenAI and Home Assistant's AI can't write it.
- **Written by:** Claude Haiku 5.5 (Standard, about 7p a day), Claude Sonnet 5.5 (Thorough, about 25p a day), Gemini 4 Hydrogen (Standard, about 10p a day) or Gemini 4 Argon (Thorough, about 20p a day). Only the ones whose key is saved can be chosen. With one key saved, its Standard is chosen for you; with both, the AI chosen under Scanning. The briefing counts towards the monthly AI limit and shows in the spending stats.
- **Searches cost extra:** Anthropic charges a cent for each search, on top of the tokens. Google charges 1.4¢ for each search, but the first 5,000 a month (across everything using the key) are free. Dads Army counts each Google search at 1.4¢ anyway, so the monthly limit errs on the safe side; the Gemini costs above include that, and are about half while the free searches last.
- **Social media too** (on unless you switch it off, in the same card): it also searches public posts on Reddit, X, Facebook pages and groups, Bluesky, Nextdoor and local forums for what people in and around your area are reporting, such as power or water cuts, flooding, fires, roads closed, trouble, or shops running short. That's a mix of official and social input, kept apart:
  - The paragraph, the headline and the ratings come from official and reputable sources. What people are posting goes in its own **On social media** paragraph underneath, marked *unconfirmed*, saying whether an official source backs it up. If there's nothing worth mentioning, it says so.
  - Social media on its own never raises a rating. It doesn't name, quote or identify anyone posting, and it's told to ignore anything in a post that tries to tell it what to write.
  - It sees what the search can see: public posts, not private groups or anything behind a login. Reddit and public Facebook pages turn up more often than posts on X.
  - It's up to two more searches a day (2¢ with Claude, 2.8¢ with Gemini) plus reading the results: a few pence a day more. Switching it off or on takes effect from the next briefing.
- **Gemini needs billing switched on** for your key, in Google AI Studio. Google's free tier doesn't include Grounding with Google Search, and the briefing's error says so if that's the trouble. With billing on, Google doesn't use what's sent to improve its products.
- **What's sent to Anthropic or Google** (whichever writes it): the area name (what you type under **Local news for**, or your Met Office region), the day's warnings and wider picture, health news, and how many days your food and water would last. Nothing else about you, and not your location: the warnings and live lines it's given leave out postcodes, streets, gauge and borehole names, and how far things are from home ("Power cut near home", "River Esk near home"). Gemini isn't given a location for its searches either. Social media is searched the same way, on their side, so nothing more is sent for it.
- **On the Sitrep:** Local, UK and World ratings from quiet to severe ("↑ above usual" when something's up), and the first sentence or two of the paragraph. **View more** shows the rest of it, **On social media** when that's on, and the sources it relied on (only ones that really came back from its searches). Sources from social media are marked with the site's name ("Reddit", "X"). Under Claude's, what it searched for. Under Gemini's, Google's search suggestions: chips that open those searches on Google in a new tab. Written by AI: check anything important with the official source.
- **Google's terms for Gemini's briefing:** an answer written with Google Search must be shown with Google's search suggestions, unchanged, and its links left as Google gave them. So Dads Army shows the suggestions exactly as Google sends them, in a sandboxed frame where nothing can run, and the sources' links go through Google's own redirect. A Gemini briefing is only shown in Dads Army. It isn't sent on to Claude if you switch, either: Claude's baseline starts from its own briefings.
- If it fails it tries again 20 minutes later, up to four times a day. If Anthropic or Google refuses the key, it switches itself off. **Write one now** writes one straight away.
- **While one's being written** (a minute or two), the switch and **Written by** are greyed out, and **Write one now** too. They come back as soon as it's done, and HQ says when it's ready. **Local news for** and **Social media too** can still be changed, for the next one.
- In Home Assistant: `sensor.dads_army_briefing`. For Claude's briefing, its state is the headline, and the paragraph, ratings, what's on social media (`social_media`) and sources are attributes. For Gemini's, the state is *Written by Gemini: read it in Dads Army*, with the day and time, and nothing of what it says (Google's terms, above).

## Read to me

**Read to me** reads the Sitrep out loud. It's on the daily briefing, or on the household alert level when there's no briefing to show. Press it again (**Stop reading**) to stop.

- **What it reads:** the household alert level, what it means and why; things to watch; the daily briefing in full, with its ratings and **On social media** (said to be unconfirmed); what's affecting you (or the warnings in force); how long the stores would last, and what's expired, expiring soon or below target; checks that are due; and how ready you are, with the next step. About two minutes.
- **It works without the internet.** Your phone, tablet or computer does the reading, with one of its own voices that works offline, so nothing is sent anywhere. Some voices need the internet (Chrome's "Google" voices and Edge's "Online (Natural)" ones send the words to Google or Microsoft to be spoken), so Dads Army never uses them.
- **Voice and speed** are in HQ's **Read to me** card: only voices that work offline are listed, English ones first. Each device has its own voices, so it's set on each one. **Try it** plays a sample.
- If a device has no offline voice, the card says so and how to add one (on Windows: Settings, Time & language, Speech; on Android: Settings, Text-to-speech output). If its browser can't read aloud at all, as some apps' built-in browsers can't, the button isn't shown: open Dads Army in Chrome, Edge, Safari or Firefox.

## Trends

The Sitrep's **Trends** card charts how many days the food and water would last, and the resilience score, day by day, over 30 days, 90 days, a year or everything. Point at the chart (or touch it) to see a day's figures, or open **Show as a table**.

Below it, the **Expiry timeline** shows the batches in stock by the month they go out of date, for the next twelve months, after a column for what already has: red for out of date, amber for expiring soon, green for fine. A tall column is a month when a lot goes at once, in time to use it up or swap it out. Tap a month to see the stores soonest first.

Dads Army records one line a day from 1.11.0, and keeps five years. When it first runs as a Home Assistant app, it fills in the days Home Assistant still remembers for the Dads Army sensors (usually the last ten).

## Scanning

**Adding things.** In **Stores**, tap **📷 Scan** and hold the barcode inside the box. Underneath are the other ways in: take a photo, read the label, type the number, or pick from your stores. On a phone using the Home Assistant app over https, the camera reads it as soon as it's in view. Browsers only allow a live camera over https, so on plain http (or if you say no to the camera), Scan takes a photo instead. **Type the numbers** is always there too.

- **A barcode you've scanned before** goes straight to its item. Choose **Putting it in the stores** or **Taking it out to use**.
- **A new barcode** is looked up in Open Food Facts, a free database of food products. Only the barcode is sent. You get the name (in English), the size and the calories. **Add as a new item**, or tap something you already keep: another brand of baked beans can go on the same line, with its own batches. The barcode is remembered either way.
- **No barcode, or Open Food Facts doesn't know it?** Tap **Read the label**. An AI reads the name, what the pack is (jar, carton, tin...), size, calories, best before date and "once opened" days from a photo of the pack, for you to check before adding. **📷 Add another photo** (the back, the nutrition panel, the date) adds to it. Anything the AI had to estimate, because it isn't printed, is marked **AI estimate**. If you scanned the barcode from a photo, the AI reads that same photo for whatever Open Food Facts is missing.
- **Barcode not reading?** A photo is read six ways (whole, the middle, smaller, turned) before giving up. If it still can't, it's usually distance or blur (get close enough that the barcode fills most of the photo), glare (tilt it), or a crease. The add-on's log notes how each scan went.
- **Known, but no calories?** Tap **📷 Read the nutrition label** and photograph the nutrition table. The AI reads the kcal per 100 g and the weight, and works out the calories for the whole pack ("78 kcal per 100 g × 415 g = 324 kcal"). The same button is next to the calories when you add or edit something.
- **Nothing to scan at all** (a single can from a multipack)? **Choose from your stores** lets you pick the item, then put one in or take one out.

The reader knows the usual shop barcodes (EAN and UPC), plus GS1 DataBar (the wide, stretched ones on some own-brand packs), Code 128 and ITF.

**Best before dates.** When adding stock or a new item, **📷 Read it from a photo** fills in the date for you to check. Or type it, or use **Same as …** for a date you already have.

**Taking one out.** If you have more than one batch, **Use** asks which it's from (the oldest is ticked). **📷 Match the date on it** reads the date from a photo and ticks that batch.

**Part of a pack.** In an item's details, **Each one holds** says what one holds: a 500 g bag, or 6 for a 6-pack. Then **Use** lets you say **an amount** (200 g, or 1 can) or **What's left** in the open one, and the item shows "1 bag + 300 g in the open one". **Once opened, use within** says how long it keeps once opened (an open tin of beans: about 3 days in the fridge). Using part of one makes the rest its own batch, marked as opened, which goes off then and is used first.

**Cupboard, fridge or freezer.** Food, drinks and pet food have **Kept before opening**: 🥫 Cupboard, ❄️ Fridge or 🧊 Freezer. Scans and the label reader fill it in; new ones start as Cupboard (the starter list too) unless the barcode or label says fridge or freezer, or you change it. **Fill in missing details** estimates it for what you already have. Fridge and freezer things show ❄️ or 🧊 in **Stores**, and the Sitrep says how many days of your food needs one: eat that first in a power cut, as it only lasts a day or two without power. The stores review goes by it too.

**Calories and how long the food lasts.** Calories are for **one whole unit as you count it**: the whole tin, the whole bag, the whole 6-pack, never a serving. Dads Army adds up the calories in date, then eats them in date order, a day at a time, against what the household needs a day (HQ → Household). Food that would go off before you got to it doesn't count, and the Sitrep says how much that is. **Drinks** (juice, milk, squash) count as food, and stand in for drinking water only: up to 1.5 litres a person a day, while cooking, washing and the pets' water have to come from plain water. A water item with no "litres in one" set takes it from its size (a 5000 ml bottle is 5 litres). Things with no calories set don't count at all: **Fill in missing details** in **HQ → Scanning** has the AI estimate them from their names, for you to check, marked **AI estimate** until you change them.

**Stores review.** With an AI set up, the Sitrep has a **Stores review** card. Tap **Review my stores** and the AI looks at your food as if there were no mains water, power, gas or fridge: can it be eaten cold or with a little heat from what's stored, does it need water to cook, will it keep once opened, is it a balanced diet for your household, and will it keep. Then a line on the rest of the stores. It suggests up to six things to add, each one tap onto the supply run. Only item names, amounts and your household's make-up are sent. About 0.3p a go.

Without an AI set up, the buttons that need one are hidden, and adding an item says what an AI would add.

**Which AI reads the photos.** In **HQ → Scanning**:

- **Home Assistant AI Task** (the default) uses whatever AI you've set up in Home Assistant under **Settings → Devices & services**: Google Gemini, Anthropic or OpenAI. Gemini is tried first, then the others.
- Or choose **Anthropic Claude** (Claude Haiku 5.5), **Google Gemini** or **OpenAI** and paste an API key. The key stays on the Pi, is never shown back, and is left out of backup files and the automatic database copies (paste it in again after a restore). The National Highways key for road closures, and the UK Power Networks key for your power supply, are kept the same way.

It costs about 0.1p a photo. The photo is put in Home Assistant's media folder only while the AI reads it, then deleted.

**AI use and spending.** **HQ → Scanning** shows what the AI has cost this month (worked out from each call's tokens and the provider's list price), how many answers it has given, today's, and what's left of your **monthly limit**, with the last 15 calls underneath. Once the limit is reached, nothing more is sent to Claude, Gemini or OpenAI with your key until the 1st. The limit doesn't cover the Home Assistant AI Task route, which is billed there. `sensor.dads_army_ai_spend` has the same figures for a dashboard or an automation. If the AI fails, it says why in plain words: busy on the provider's side (it tries once more), allowance used up, no credit, or the key not accepted.

**Scanning with the internet down.** Barcodes you've scanned before always work. For new ones, switch on **Keep a list of UK products on the Pi** in **HQ → Scanning**. Dads Army then downloads Open Food Facts' public export (about 1.5 GB) and keeps the products sold in the UK, about 180,000 of them in 25 MB. It does this straight away, then once a month between 2 and 5 in the morning; **Update now** does it on demand. If a download goes wrong, the old list stays. The list is left out of Home Assistant backups. Reading a date or a label from a photo still needs the internet: type the date instead. Product data © Open Food Facts contributors, under the Open Database Licence.

## On a tablet or a wider screen

On a screen 900 pixels wide or more, such as a landscape tablet on the wall:

- the tabs move to a rail down the left
- the Sitrep, Plan, Supply run and HQ cards flow into two or three columns
- **Stores** becomes a table: item, in stock, target, best before, where, how long it lasts and status. Tap a heading to sort by it.
- details open in the middle of the screen

## Routine checks, daily use and the emergency plan

The **Plan** tab in Dads Army holds two things:

- **Routine checks:** jobs that come round regularly, such as testing the smoke alarms, charging the power banks or rotating stored water. Tap **Done** when you've done one, and Dads Army works out when it's next due. **Add suggested checks** gives you a starting set. Checks that are due show on the Sitrep, in `sensor.dads_army_checks_due`, and in the phone alerts.
- **Emergency plan:** who to call, where to meet, how to turn off the water, gas and electricity, medical needs, pets and where the documents are. It's stored with the stores, so it works with the internet down, and it prints on a page for the grab bag. **Add UK emergency numbers** fills in 999, 111, 105 (power cuts), the gas emergency line, Floodline and 101.

**Also get**, on the supply run, is for anything else you want from the shops. Tap ✏️ to change what one says. **Got it** opens a new item with its words as the name: add the amount and best-before date, and once it's saved it comes off the list.

When you edit an item, **Used a day** says how many your household gets through each day (tablets, nappies, toilet roll, gas canisters). Dads Army then shows how long each one lasts, and the Sitrep's **Daily supplies** bar shows the first to run out. **Price each** adds up what the stores are worth and what the supply run will cost.

Dads Army also notices how fast you actually use things. Once you've tapped **−** on something twice or more, its page says something like "You use about 2 tins a week, lasts 6 weeks", from the last three months.

**Pets.** In **HQ → Household**, say how many dogs, cats and other pets you have. Their drinking water is added to the household's (about a litre a day for a medium dog and a quarter for a cat; you can change these). Set **Used a day** on their food, and the Sitrep shows how long it lasts. The starter list then adds dog or cat food, pet medicines and a carrier.

**Starter list targets follow the household.** Targets from the starter list are sized for your household and readiness target. Change either, and those targets change with them, unless you've set one yourself.

**Expiry warnings by category.** In **HQ → Expiry warning**, you can warn earlier (or later) for some categories: 90 days for medicines, say, so there's time to get a new prescription.

## Automation ideas

- Use `binary_sensor.dads_army_attention` for a warning light: it's **on** when something needs doing now (expired stock, an overdue check or a serious warning), and its `reasons` attribute says what.
- Flash a light or announce on a speaker when the `dads_army_ran_out` event fires.
- Get a reminder when `sensor.dads_army_readiness` drops below 100%.
- Get a warning when `sensor.dads_army_supplies` drops below a week, so there's time to get more of your medicines.
- Get a notification when `sensor.dads_army_ai_spend` passes most of its `limit_usd`.
- Turn a light red, or announce on a speaker, when `sensor.dads_army_warnings` has a `max_severity` of 3 (a red warning, a severe flood warning or an Emergency Alert).

## Credits

Help → **Credits**, or the link at the foot of HQ, thanks the people who built Dads Army and lists them, with the open data it uses. The list comes from `CREDITS.md` in the GitHub repository. The app carries its own copy, so it shows with no internet.

**Check GitHub for new names** fetches the latest list, and adds anyone who has changed the code on GitHub. It's only fetched when you tap the button. Nothing about you is sent: it asks for two fixed public addresses on GitHub, the same place Home Assistant gets Dads Army's updates from.

## Your data

Your data is kept in the app's own storage. It survives restarts and updates, and it's included in your Home Assistant backups. On top of that:

- Dads Army saves a copy of its database every day and keeps the last 14. Each copy is checked before it's kept, and if one isn't sound, the earlier ones stay.
- HQ → **Restore an automatic copy** lists those daily copies, and the ones saved just before a restore, newest first, with the date and how many items each has. Pick one to put the stores back as they were then. It goes through the same checks as restoring a file: a copy of what you have is saved first, and it asks before restoring one with nothing in it. A damaged copy is listed, but can't be picked.
- Out-of-date stock doesn't count towards a target, so out-of-date tins show on the supply run as needing replacing.
- **Restore from a backup** checks the whole file before changing anything, saves a copy of what you have first, and asks before restoring a backup with nothing in it.
- An undo never overwrites a newer change: if someone has used or changed the same thing on another phone since, the undo says so and leaves it.
- The spreadsheet export can't be made to run formulas: a cell starting with = + − or @ is saved as plain text.
- HQ → **Download backup** saves a copy to your phone.
- HQ → **Print full inventory** gives you a paper copy to keep with the stores, and **Print emergency plan & checks** gives you the plan.

## What leaves your network

Dads Army needs no internet to run. With warnings and the wider picture switched on, it downloads public feeds: each is the whole country, a whole network or a company's whole list, and it works out what's near home itself, so your location isn't sent with them. Which regional feeds it asks for says roughly where you are (Scotland's feeds for a home in or near Scotland, your network's and your water company's), but nothing finer. Every request carries only Dads Army's name: no cookies, no referrer.

What goes, and when:

- **Only alerts for my area (off until you tick it):** home's location rounded to about 100 m goes once to postcodes.io (ONS data), to find your district, county, region and constituency, so that an Emergency Alert for somewhere else doesn't raise your alert level. Again if you move. Untick it and Dads Army forgets the answer, and every alert counts again.
- **Road closures (when switched on, with your key):** your National Highways key goes to National Highways' API (`api.data.nationalhighways.co.uk`) in a header, with England's whole list asked for by time only. Home's location isn't sent.
- **Your power supply (when switched on, with your key, for a home on UK Power Networks' network):** **home's location, rounded to about 10 m (4 decimal places), goes to UK Power Networks' Open Data Portal (`ukpowernetworks.opendatasoft.com`)**, with your key in a header, to find the substation that supplies you. Then the substation's id and name are asked for, to find its fault records. Once a day. Nothing goes until you add your key.
- **The grid now (when switched on):** your carbon intensity region's number (one of 14, worked out on the Pi) goes to NESO's Carbon Intensity API. That says roughly which part of Great Britain home is in, and nothing finer.
- **Rainfall near you (off until you tick it):** each of the three nearest rain gauges' readings is asked for by the gauge's id, at the Environment Agency, SEPA or Natural Resources Wales. That says home is within 25 km of those gauges.
- **Groundwater near you (off until you tick it):** the readings of up to three of the nearest boreholes are asked for by their ids, at the Environment Agency. That says home is within 30 km of them.
- **Scanning:** a new barcode goes to Open Food Facts (only the barcode), unless you use the offline list. A photo of a date or label goes to the AI you choose.
- **The stores review:** your item names and amounts, to that AI, when you ask.
- **The daily briefing (when switched on):** the area name, the day's warnings and wider picture (without postcodes, streets, gauge names or distances), health news and how long your stores would last, once a day, to Anthropic or Google, whichever you chose to write it. Under a Gemini briefing, your phone or browser opens Google only when you tap one of its search suggestions.
- **Read to me:** nothing. Your phone or computer reads it out with one of its own voices that works offline; voices that need the internet aren't used.
- **Credits:** two fixed public addresses on GitHub, only when you tap **Check GitHub for new names**.
- **The live alerts map (when switched on):** your phone or browser loads the map pictures from OpenStreetMap's tile server, `tile.openstreetmap.org`. OpenStreetMap sees your IP address and which map squares you look at, so roughly the area round home, as the map opens there, and nothing else: no cookies, no referrer, nothing from Dads Army. The Pi itself fetches nothing for the map. Switched off (as it starts), the app doesn't load the map at all, and the page's security policy blocks pictures from anywhere but Dads Army itself.

## Security

There's no separate login. Anyone who can reach port 8080 on your home network can open it. Through the sidebar, only signed-in Home Assistant users can open it. Don't port-forward 8080 on your router.
