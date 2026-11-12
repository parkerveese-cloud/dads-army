# Changelog

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
