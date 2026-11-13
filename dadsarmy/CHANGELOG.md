# Changelog

## 2.0.0

Re-formatted for wall tablets, with live information added. Everything you could do before still works, and phones keep the bottom tabs. On a wall tablet or desktop the screens use the full width.

### Layout for wall tablets and larger screens

- **Sitrep:** on a wall tablet or desktop the alert level and resilience sit side by side at the top. Below them, how long you could hold out with rings for food, water and kit, and a trend over the last weeks. **Next actions** lists the few most useful things to do now. Tiles for expired, expiring, below target and out of stock show their trend. An **expiry timeline** shows what goes out of date month by month, and **stock by category** shows what's complete.
- **Stores:** a table on desktop with stock against target, the soonest expiry, where it's kept and how fast you use it. The toolbar stays in view. Item details open in a side drawer (a sheet on phones) with batches in the order to use them.
- **Supply run:** progress at a glance, what's most urgent, a breakdown by category, and the checklist.
- **HQ:** sections with a menu (Household, Targets and warnings, Live alerts, Backups, Home Assistant, Appearance, Activity), sliders for targets, and switches.
- **History:** Dads Army now keeps a daily record of readiness, so trends build up from today.
- **Usage:** it notes what you use, and works out how fast each thing goes and when it will run out.
- **First run:** a three-step start for new stores.
- Navigation moves into the header on tablets and desktops. Light and dark themes throughout.
- Charts are drawn by the app itself (no outside libraries or requests).
- **Colours:** a brighter green palette with stronger blue, amber and red, so status reads from across the room on a wall tablet. The header stays dark green.

### Live alerts (UK)

These sit alongside the warnings, household alert level and resilience from 1.6.0 to 1.9.0, which lead the Sitrep. Live alerts add the map, more sources and trends. With live alerts on, weather, flood and fire warnings show once on the Sitrep, on the live map and in Things to watch; the Plan tab still lists every warning.

- **Live alerts.** Flood warnings (Environment Agency), severe weather (Met Office), power cuts (UK Power Networks), national grid warnings (Elexon), air quality (DEFRA UK-AIR) and space weather (NOAA), straight from the official open feeds. A card on the Sitrep, settings in HQ, and `sensor.dads_army_live_alerts` / `sensor.dads_army_alert_level` in Home Assistant. Off until you switch it on.
- **Live alerts map** on the Sitrep: home, a ring for the distance you choose, every flood warning area in your county (outlined and coloured when there's an alert), and power cuts around home. Tap anything for the details and a link to the official page.
- **Colour-coded summaries** under the map, one per source (All clear, Be aware, Be prepared, Take action). Tap one for its details.
- Power cuts near home but outside your postcode districts show on the map as "nearby", without raising an alert.
- HQ → Live alerts: map on or off, and how far around home to show (5 to 40 km). Home comes from Home Assistant's own settings.
- The map uses the bundled Leaflet 1.9.4 library (BSD-2-Clause) with OpenStreetMap tiles, darkened in the dark theme.
- **Across the UK:** floods (all of England), Met Office warnings (every region, shaded on the map) and the bigger power cuts nationwide now show on the map. Only alerts near you raise the alert level and the Home Assistant sensors; the rest are context, drawn smaller and fainter. Switch them off in HQ if you'd rather not see them.
- **Map centred on a postcode** of your choice (HQ → Live alerts), with Home and UK buttons on the map.
- **Wildfires:** NASA satellite heat detections from the last 24 hours across the UK and Ireland, with offshore platform flares left out. One within your "near you" distance counts as an alert.
- **Gas storage:** how full Great Britain's gas storage is, the week's change and roughly how long it would last at the current rate (National Gas).
- **More power cuts:** National Grid (NGED) live power cuts added alongside UK Power Networks, covering the Midlands, South West and Wales too.
- The map no longer shows every quiet flood area: only what's happening.
- Fixed: two Met Office region codes (London & South East England is "se"; "ls" didn't exist).
- Privacy: no feed is told where you live any more. Every one is a national list filtered on the Pi.
- **River levels:** a new live alert. It shows every Environment Agency river gauge within your "near you" distance against its normal range, with the trend, and flags any that are above normal. Rivers running high elsewhere in England appear on the map. A gauge above its normal range near you counts as an alert.
- **Trends to watch:** Dads Army now keeps a few numbers from every check for two weeks (power cuts, flood warnings, rivers above normal, heat detections, grid notices) and looks for a worrying direction of travel: a river near you rising towards the top of its normal range, power cuts or flood warnings climbing, gas storage emptying faster. Trends appear at the top of Live alerts and count as alerts. Each source's details show its history as a chart.
- **The pound:** sterling against the US dollar, euro, yen, yuan, Canadian and Australian dollars and Swiss franc, with day, week and month moves. A fall of 3% in a week (or 6% in a month) against the dollar or euro is flagged.
- **Markets:** nine major stock indices plus Brent crude, wheat and gold, refreshed every three hours. A fall of 7% in a week (12% in a month) in an index, or a rise of 15% in a week in oil or wheat, is flagged. Context only, not financial advice.
- **Home Assistant:** a new `sensor.dads_army_trends`, and a `dads_army_alert` event for each new live alert or trend (kind, level, level_word, source, title, message, url), for phone notifications. The same alert doesn't repeat within six hours.
- **Things to watch** is now a banner at the very top of the Sitrep, showing trends and anything active near you. Tap one to jump to its details.
- **Live alerts:** a source with a trend or alert now turns amber or red, says what it is on the tile, and moves to the front. The pill on the card names the source when there's only one. The trend's explanation shows in the source's details.
- Live alerts show on the Sitrep even before you've added any stock.

### Also new

- **Pets.** HQ → Household now has pets, with the calories and water they need a day. They count towards food days, water days and hold-out. With no pets nothing changes.
- **Starter targets keep up with the household.** Change the people, pets or readiness target and the starter list's targets are worked out again. Targets you set yourself stay as they are.
- **Expiry warning by category**, for example 90 days for Medical.
- **Restore an automatic copy** from HQ, with the date and number of items for each.
- **Supply run extras:** change the text, or tap **Got it** to add one to the stores as a new item.
- **Undo** after **Add stock** and **Got it**.
- **Home Assistant:** `sensor.dads_army_expiring_soon` now lists what goes out of date in exactly seven days (`expires_in_7_days`) alongside `expires_today`, for phone reminders.
- Daily use and prices (1.5.0) are part of the wider layout: Stores shows how long each thing lasts, the Sitrep has **Daily supplies** and **Checks due** cards, and the supply run adds up the cost.

### Fixes

- Expired stock no longer counts towards targets, running low, out of stock or kit stocked. The supply run says how much to replace (*Get 3 tins · 2 expired*).
- Undo won't overwrite a newer change: if the item has changed since, it says so. The Undo offer goes as soon as you change something else.
- "Went out of date overnight" and "last day" alerts include every batch, not just each item's oldest.
- Home Assistant to-do list: an emptied list no longer forgets which items aren't Dads Army's; a below-target line that changes is unticked; changes made in Dads Army during a sync aren't overwritten; the link table is only rewritten when something changed.
- "Ran out" events are no longer lost when Home Assistant can't be reached for a while.
- Backups are checked before they're kept and never overwrite each other. Copies made before a restore are kept for 14 days. Restoring an empty backup asks first.
- The household needs at least one person. The health check now checks the database too.
- Safer input: dates, numbers and ids take plain digits only; "done" on the supply run must be true or false; spreadsheet export can't be made to run formulas. Quantities accept a comma ("1,5") and show up to 3 decimals.
- Editing a batch with the quantity left empty no longer deletes it. Setting it to 0 asks first.
- Accessibility: calmer screen reader announcements, focus moves into and back out of sheets, named buttons and meters, better contrast for muted and green text.
- The offline banner now fits Home Assistant: "Can't reach Dads Army. Check Home Assistant is running and you're connected."
- Saving a setting no longer wipes out another one you're typing. Several smaller fixes to refreshing and the supply run tick.
## 1.9.0

- **Resilience, in ten areas.** Being ready isn't just food and water. Dads Army now looks at:
  - water
  - food and cooking
  - power and light
  - warmth
  - communications
  - health
  - hygiene
  - fire and home safety
  - money and documents
  - your plan for getting out

  Each area has a score, and the Sitrep shows them all just under the alert level.
- **About 65 recommendations**, each marked essential, recommended or extra, and labelled with its source: mostly the UK Government's **Be Ready** checklist, **Ofcom** and **Fire Kills**. They include:
  - a UPS for the router and Home Assistant
  - a battery or wind-up radio
  - a battery backup for a digital landline
  - walkie-talkies
  - power banks and spare batteries
  - smoke and carbon monoxide alarms
  - the Priority Services Register
- **Ticked off for you** where Dads Army can see it, in your stores, plan, checks, warnings and home sensors. Tick the rest off yourself, or say they're not for you.
  - **Add to stores** puts anything missing on the supply run.
  - **Next steps** shows what to do first.
- **The alert level** now takes resilience into account. An area missing an essential keeps it at MODERATE or higher, in place of the old "kit under half stocked" rule. In a power cut with no torches or power bank, or a cold home with no blankets or warm clothes, SUBSTANTIAL goes up to SEVERE.
- **Home Assistant.**
  - New `sensor.dads_army_resilience`.
  - The Home front dashboard has a **Resilience** section, in place of the food-and-water gauge, and an **All recommendations** page. Dads Army offers to update the dashboard.
  - The weekly round-up ends with your resilience and what to do next. Re-import the blueprint.
- The UK Government's Prepare campaign is now called **Be Ready**, and the advice is labelled to match.

## 1.8.1

- **A smaller alert level on the Home front dashboard**, so everything else fits on a tablet without scrolling far.
  - The level now has a compact card: its name and colour, the main reason, and the whole scale on one line. It takes one column, so the warnings and today's checklist sit beside it.
  - **Why, and what to do now** opens on its own page, with the big scale, every reason and all the labelled advice. The **Alert level** badge at the top opens it too.
  - The **i** next to the heading opens **What the levels mean**.
  - Dads Army offers to update a dashboard you've already made. Tap **Update the dashboard**.

## 1.8.0

- **Household alert level.** A five-step scale for the household, from LOW (green) through MODERATE, SUBSTANTIAL and SEVERE to CRITICAL (black). It uses the names of the UK's national threat levels, the British equivalent of DEFCON, but it's the household's own level, not the official one.
  - It shows big at the top of the Sitrep, with the full scale and why it's at that level.
  - Tap **i** for what each level means, how it's worked out, and where the advice comes from.
  - It's worked out from warnings in force, your stores, and your home's own sensors. Stores too low to last 3 days make a SUBSTANTIAL situation SEVERE.
- **What to do now.** Every level comes with plain advice for the situation, worst problem first. Each piece is labelled with its source: **UK Government** (Prepare, the NHS, UKHSA, the Met Office, the Environment Agency and others), the **SAS Survival Handbook**'s PLAN priorities applied to a household, fire and rescue services, or the 105 power cut line.
- **Home sensors.** Dads Army can watch your Home Assistant sensors for:
  - indoor and outdoor temperature
  - humidity
  - mains power or UPS, and a backup battery
  - gas, carbon monoxide and smoke alarms
  - water leaks
  - the internet
  - outdoor air quality

  For example, a cold bedroom, a power cut, a leak or a carbon monoxide alarm raises the level and brings the right advice. **Suggest sensors for me** picks likely ones.
- **Home front dashboard.** The alert level now leads the dashboard, big and colour-coded with the full scale. Underneath are the reasons and labelled advice, and a **What the levels mean** page. Dads Army offers to update a dashboard you've already made.
- **Home Assistant.**
  - New `sensor.dads_army_alert_level`, and a `dads_army_alert_level` event when the level changes.
  - The phone alerts blueprint tells you when it goes up (to SUBSTANTIAL or higher unless you choose otherwise).
  - The weekly round-up starts with the level.
  - Re-import both blueprints.

## 1.7.2

- **A quieter Activity log in Home Assistant.** **Dads Army needs attention** no longer turns "Unavailable" and back again every time Dads Army restarts, which happens for each update and for Home Assistant's nightly backup. That added two lines to the Activity log each time. The number sensors still show "Unavailable" while Dads Army is stopped, so dashboards can still tell.
- **Needs attention now means "needs doing now".** It comes on for stock past its best-before date, checks that are overdue, and serious warnings (amber or worse). It no longer counts things you haven't bought yet (they're on the supply run), or checks you haven't done for the first time yet. Before, it stayed on for weeks while you built up your stores.

## 1.7.1

- **Easier to set up the Home front dashboard.** When you open Dads Army in Home Assistant, it offers to make the dashboard for you. It shows a preview with your own numbers and can set up today's checklist and the supply run list at the same time. One tap does the lot, with each step ticked off as it goes.
  - **Not now** asks again in two weeks, and **Don't ask again** stops it.
- **Help.** A new **?** button at the top of every screen leads to the dashboard set-up, warnings, routine checks and the emergency plan, the supply run, and how to get phone alerts.

## 1.7.0

- **Home front dashboard.** In **HQ → Home Assistant**, tap **Make the dashboard**. A new **Home front** dashboard appears in the Home Assistant sidebar and the Companion app, built from Home Assistant's own cards. It shows:
  - warnings in force
  - today's checklist
  - the readiness gauge, hold-out, food, water and daily supplies
  - the stores: expired, expiring soon, out of stock, running low, kit and value, plus what to use first
  - the supply run, with a button to open Dads Army
  - a graph of the days you could last
- **Today's checklist.** Your routine checks can go on a Home Assistant to-do list. Checks that are due, overdue or not done yet appear with their due dates. Tick one off on the dashboard or in the Companion app and it's marked done in Dads Army, with the next one worked out.

## 1.6.1

- **Possible fires nearby.** A new warnings source, off until you tick it in the warnings settings: hotspots NASA's satellites picked up in the last 24 hours within 10 km of home (you can change the distance).
  - Nearby hotspots are grouped into one **Possible fire**, such as "Possible fire 6 km north-east of home", with a link to NASA's fire map and fire safety advice.
  - Satellites also see controlled burns, farm fires and industrial flares. Places that come up again and again over a week or more are left out, and you can tap **Not a wildfire: ignore this spot** for any other.
- A warning that drops out for one check (if a feed hiccups) no longer sends a second phone alert when it comes back.

## 1.6.0

- **Warnings for where you live.** Switch them on under **HQ → Warnings** to see official warnings from:
  - the Met Office (yellow, amber and red weather warnings for your region)
  - the Environment Agency (flood alerts and warnings near you, England only)
  - GOV.UK Emergency Alerts
  - GDACS, the UN and EU disaster alert system (orange and red alerts within 1,000 km)
  - optionally, news from the UK Health Security Agency and WHO disease outbreak news
- The most serious warnings show at the top of the Sitrep. The Plan tab lists them all, with the health news.
- Tap a warning for the official message and a link to the full details. You also get what to do, and the parts of your emergency plan that matter, such as where to meet and how to turn off the gas, electricity and water.
- **Private and offline-friendly.** Dads Army downloads the same public files for everyone and works out what's near you on your own machine, so your location is never sent. Without the internet, everything else carries on and the last warnings stay on show with when they were checked.
- **Home Assistant.**
  - New `sensor.dads_army_warnings`, and a `dads_army_warning` event when a new warning comes in.
  - The phone alerts blueprint tells you straight away: amber and worse unless you choose otherwise.
  - The weekly round-up lists warnings in force, and **Needs attention** comes on for serious ones.
  - Re-import both blueprints to get these changes.

## 1.5.0

- **New Plan tab: routine checks.** Keep track of the jobs that keep your kit ready, such as testing the smoke alarms, charging the power banks, rotating stored water and checking the grab bag.
  - Tap **Done** when you've done one, and Dads Army works out when it's next due.
  - **Add suggested checks** gives you nine to start with, based on the usual advice.
  - Checks that are due show on the Sitrep, with a count on the Plan tab.
- **Household emergency plan.** Also on the Plan tab: contacts (tap to call), where to meet, how to turn off the water, gas and electricity, medical needs, pets, documents and local radio.
  - **Add UK emergency numbers** fills in 999, 111, 105, the gas emergency line, Floodline and 101.
  - It works with the internet down, and **Print** puts it on paper for the grab bag, with the checks.
- **How long things last.** Set **Used a day** on things like tablets, nappies or toilet roll.
  - Dads Army shows how long each one lasts, counting only stock that's still in date.
  - A new **Daily supplies** bar on the Sitrep shows the first thing to run out.
  - The form suggests a target that covers your readiness period.
  - The starter list now sets this for toilet roll, wet wipes, tea bags and gas canisters.
- **Prices.** Set **Price each** on an item. The Sitrep then shows what the stores are worth, and the supply run shows what it should cost.
- **Like last time.** When you add stock, a new button sets the best-before date as far ahead as last time.
- **Home Assistant.**
  - New sensors: `sensor.dads_army_checks_due`, `sensor.dads_army_supplies` and `sensor.dads_army_stores_value`.
  - The supply run sensor has a `cost`.
  - **Needs attention** also comes on when a check is due.
  - The phone alerts blueprint tells you each morning about checks that fall due that day.
  - The weekly round-up lists the checks that are due and what runs out first.
  - Re-import both blueprints to get these changes. The dashboard card on the Documentation tab has the new tiles.
- Backups and the spreadsheet export include the new details. Restoring a backup from an older version leaves your checks and plan as they are.

## 1.4.0

- **Delete several items at once.** In Stores, tap **Select to delete**, then tick the items you don't want to keep. **Select all** picks everything showing, so you can clear out a whole category or a search in one go. Before anything is deleted, Dads Army lists what's going and warns you about any stock that goes with it. **Undo** puts it all back.
- Deleted items also come off your Home Assistant supply run list.

## 1.3.0

- **Supply run on a Home Assistant to-do list.** In HQ → Home Assistant, tap **Make a "Supply run" list**, or pick a list you already have. The supply run then shows in Home Assistant's To-do lists and the Companion app, and stays in step both ways:
  - Below-target items come off the list once you're back up to target.
  - Tick off an item in Home Assistant and it's marked on the supply run here, ready for **Got it**.
  - Extras are shared. Add, tick, rename or delete them on either side.
  - Anything added in Home Assistant, including by voice ("Add matches to the supply run list"), becomes an extra.
- **Phone alerts.** Two blueprints:
  - **Phone alerts** tells you straight away when something runs out, and each morning about anything that went out of date overnight or is on its last day.
  - **Weekly round-up** lists what to use first, what's out of date, the supply run, and how long you could hold out.

  The setup steps are on the Documentation tab.
- **Readiness gauge.** A new sensor, `sensor.dads_army_readiness`, shows your hold-out as a percentage of your target. The dashboard card now opens with a red, amber and green gauge, next to hold-out, food and water.
- **For automations.** A `dads_army_ran_out` event fires when the last of something is used up. The expired and expiring-soon sensors also list what went off overnight (`newly_expired`) and what expires today (`expires_today`).

## 1.2.0

- **Dashboard sensors.** Dads Army now publishes sensors to Home Assistant for:
  - hold-out days, plus food and water days
  - kit stocked
  - out of stock and running low
  - expired, expiring soon, and next to expire
  - the supply run
  - a "needs attention" alert

  They update within seconds of any change. The item lists are in each sensor's attributes.
- **Dashboard card.** A ready-made card is in the Documentation tab: paste it into any dashboard.
- **Summary for other tools.** `GET /api/summary` gives the same figures as JSON.
- **Local dates.** "Today" now follows your Home Assistant time zone.

## 1.1.1

- The app's log now tells you how to open Dads Army from Home Assistant, instead of showing internal container addresses.

## 1.1.0

- Installs from the Dads Army app repository, so updates arrive in **Settings → Updates** like any other app.
- Home Assistant now restarts Dads Army automatically if it stops responding.
- Works inside the Home Assistant sidebar and the Companion app.

## 1.0.0

- First release. It includes the Sitrep, Stores, Supply run and HQ screens. Stock is tracked in batches with best-before dates and used oldest first. There's undo, a starter list, daily backups, a printed copy and CSV export.
