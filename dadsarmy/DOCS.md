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
| `sensor.dads_army_supply_run` | Number of things on the shopping list | `items`, `extras`, `cost` (from the prices you've set, in £) |
| `sensor.dads_army_supplies` | Days until the first thing with a daily use runs out (such as tablets or toilet roll). Unknown if nothing has a daily use set. | `items` (each has `name`, `days`, `have`, `per_day` and `text`), `runs_out_first`, `target_days` |
| `sensor.dads_army_checks_due` | Routine checks that are due, overdue or not done yet | `items` (each has `name`, `due`, `days`, `every` and `text`), `due_today`, `due_soon` (within a week), `next_check`, `checks_total` |
| `sensor.dads_army_stores_value` | What the stores are worth, in £, from the prices you've set | `supply_run_cost`, `priced_items`, `items_total` |
| `sensor.dads_army_warnings` | Official warnings in force for where you live (see **Warnings** below). 0 while warnings are switched off. | `items` (each has `title`, `level`, `severity` 1–3, `source`, `area`, `when`, `url` and `text`), `highest` (yellow, amber or red), `max_severity`, `enabled`, `checked_at`, `health_news` |
| `sensor.dads_army_alert_level` | The household alert level: LOW, MODERATE, SUBSTANTIAL, SEVERE or CRITICAL (see below) | `level` (1–5), `meaning`, `reasons`, `guidance` (each with `label`, `source` and `text`), `scale`, `escalated`, `escalated_why`, `notes` |
| `sensor.dads_army_resilience` | How resilient the household is, in %: the average of ten areas, from water and power to communications and safety (see **Resilience** below) | `areas` (each with `name`, `pct`, `dot`, `done`, `total`, `essentials_missing` and `next`), `next_steps`, `measures` (every recommendation, by area), `done`, `total` |
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
- **Today's checklist:** the routine checks that are due, ready to tick off (see below)
- **Resilience:** how ready you are in each of the ten areas, two to a row, with the next things to do. **All recommendations** (or the **Resilience** badge) opens a page with every recommendation, area by area, and what's done.
- **Stores:** expired, expiring soon, out of stock, running low, kit stocked, what the stores are worth, and what to use first
- **Supply run**, with your supply run list if you've linked one, and a button that opens Dads Army
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
| ⬛ | **CRITICAL** | Danger to life, now or very soon: an Emergency Alert, a severe flood warning, or a gas, carbon monoxide or smoke alarm. Follow the emergency services' instructions. |

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
| 🔋 | Power & light | Torches and batteries, a charged power bank, a UPS for the router and Home Assistant, the Priority Services Register |
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

## Warnings

Dads Army can show official warnings for where you live: on the Sitrep, on the **Plan** tab, in `sensor.dads_army_warnings`, and on your phone through the phone alerts blueprint. They're off until you switch them on under **HQ → Warnings**.

| Source | What you get |
|---|---|
| Met Office | Yellow, amber and red weather warnings for your region |
| Environment Agency | Flood alerts, flood warnings and severe flood warnings near you (England only) |
| GOV.UK Emergency Alerts | Alerts about a danger to life, while they're being sent and for 12 hours after |
| GDACS (the UN and EU disaster alert system) | Orange and red alerts for earthquakes, floods, storms, volcanoes and tsunamis within 1,000 km |
| NASA FIRMS (optional) | Possible fires within 10 km: hotspots seen by satellite in the last 24 hours |
| UK Health Security Agency (optional) | Its latest news, such as cold-weather and heat-health alerts |
| WHO (optional) | Disease outbreak news |

How it works:

- Dads Army checks every 15 minutes while the internet is up. It downloads the same public files for everyone and works out which warnings are near you on your own machine, so your location is never sent anywhere.
- Your location comes from Home Assistant's home location. You can set it by hand instead in the warnings settings. The Met Office region is worked out from it, and you can change that too.
- Tap a warning for the full message, a link to the official page, what to do, and the parts of your emergency plan that matter, such as where to meet and how to turn things off.
- If the internet goes down, everything else carries on, and the last warnings found stay on show with when they were checked.
- Keep **Emergency Alerts** switched on in your phone's settings too. They reach the phone directly, much faster than any feed.

Flood warnings outside England come from SEPA (Scotland), Natural Resources Wales and NI Direct, which Dads Army doesn't read yet.

**About possible fires.** There's no public feed of UK wildfire warnings, so this uses NASA's satellite fire detections. They're the only live source that covers the whole UK.
- A satellite sees any large heat source. Most UK detections are controlled heather burning (allowed in autumn and winter), farm fires or industrial flares, not wildfires. That's why they show as a yellow **Possible fire**.
- Dads Army learns to leave out places that come up again and again over a week or more, such as refinery flares. For anything else that isn't a wildfire, open it and tap **Not a wildfire: ignore this spot**.
- Satellites only pass over a few times a day, so a fire can be a few hours old before it shows.
- If you can see a fire that looks out of control, call 999.

## Routine checks, daily use and the emergency plan

The **Plan** tab in Dads Army holds two things:

- **Routine checks:** jobs that come round regularly, such as testing the smoke alarms, charging the power banks or rotating stored water. Tap **Done** when you've done one, and Dads Army works out when it's next due. **Add suggested checks** gives you a starting set. Checks that are due show on the Sitrep, in `sensor.dads_army_checks_due`, and in the phone alerts.
- **Emergency plan:** who to call, where to meet, how to turn off the water, gas and electricity, medical needs, pets and where the documents are. It's stored with the stores, so it works with the internet down, and it prints on a page for the grab bag. **Add UK emergency numbers** fills in 999, 111, 105 (power cuts), the gas emergency line, Floodline and 101.

When you edit an item, **Used a day** says how many your household gets through each day (tablets, nappies, toilet roll, gas canisters). Dads Army then shows how long each one lasts, and the Sitrep's **Daily supplies** bar shows the first to run out. **Price each** adds up what the stores are worth and what the supply run will cost.

## Automation ideas

- Use `binary_sensor.dads_army_attention` for a warning light: it's **on** when something needs doing now (expired stock, an overdue check or a serious warning), and its `reasons` attribute says what.
- Flash a light or announce on a speaker when the `dads_army_ran_out` event fires.
- Get a reminder when `sensor.dads_army_readiness` drops below 100%.
- Get a warning when `sensor.dads_army_supplies` drops below a week, so there's time to get more of your medicines.
- Turn a light red, or announce on a speaker, when `sensor.dads_army_warnings` has a `max_severity` of 3 (a red warning, a severe flood warning or an Emergency Alert).

## Your data

Your data is kept in the app's own storage. It survives restarts and updates, and it's included in your Home Assistant backups. On top of that:

- Dads Army saves a copy of its database every day and keeps the last 14.
- HQ → **Download backup** saves a copy to your phone.
- HQ → **Print full inventory** gives you a paper copy to keep with the stores, and **Print emergency plan & checks** gives you the plan.

## Security

There's no separate login. Anyone who can reach port 8080 on your home network can open it. Through the sidebar, only signed-in Home Assistant users can open it. Don't port-forward 8080 on your router.
